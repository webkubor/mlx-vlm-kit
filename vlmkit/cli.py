"""vlm CLI — 本地视觉理解、封面质检与 UI 截图审查。

用法：
    vlm describe <图片>                          # 描述主体与色调
    vlm ask <图片> --q "这个问题怎么回答"         # 任意提问
    vlm cover-check <图片|目录> [--batch]        # 音乐封面质检
    vlm ui-review <截图> [--context 页面说明]     # UI 截图审查
    vlm reverse-prompt <图片> [--lang en|zh]     # 反推出图 prompt
"""
import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core import ask, collect_images, cleanup_temp_image, upscaled_for_review, is_supported_image, VisionError

PROMPTS = {
    "describe": "用两句话描述这张图片：画面主体、色调氛围。",
    "cover_check": (
        "这是一张音乐单曲封面。检查：1)是否有文字/标题 2)主体是什么 3)色调 "
        "4)作为音乐封面是否合格。简洁回答。"
    ),
    "reverse_prompt_en": (
        "You are an AI image-prompt expert. Reverse-engineer the drawing prompt "
        "of this image, covering: subject, style, lighting, color palette, "
        "composition. Output the prompt itself, no explanation."
    ),
    "reverse_prompt_zh": (
        "你是 AI 出图提示词专家。反推这张图片的绘画提示词，包含：主体、风格、"
        "光线、色调、构图。直接输出中文提示词本身，不要解释。"
    ),
}

UI_REVIEW_PROMPT = """你是 UI 视觉审查助手。根据截图中实际可见的像素，审查页面的布局与视觉缺陷。
{context}
{criteria}

仅检查此截图能证明的事项：文字或控件被裁切、遮挡或溢出；对齐与间距明显不一致；层级不清；文字难以辨认；可见的视觉状态与页面用途冲突。
不要推断按钮是否可点击、表单是否能提交、响应式断点是否正常、键盘/屏幕阅读器可访问性、截图以外的设计规范或用户行为。缺少设计要求时，只报告明确可见且可复现的视觉问题。
若截图不足以判断，使用 NOT_DETERMINED。不要为了给出问题而编造问题。

只输出一个 JSON 对象，不要 Markdown 代码围栏，格式必须为：
{{"status":"PASS|ISSUES_FOUND|NOT_DETERMINED","summary":"一句话结论","findings":[{{"severity":"high|medium|low","issue":"具体问题","evidence":"截图中的位置和可见证据","suggestion":"可执行的修改建议"}}],"limits":["此截图无法证明的事项"]}}
PASS 表示在本截图和以上范围内没有发现明确问题；不是整个页面或交互已通过验收。ISSUES_FOUND 至少有一条带截图证据的问题。NOT_DETERMINED 表示图像信息不足。"""

_REVIEW_STATUSES = {"PASS", "ISSUES_FOUND", "NOT_DETERMINED"}
_REVIEW_SEVERITIES = {"high", "medium", "low"}

UI_RECHECK_PROMPT = """这张放大的页面截图里，是否存在文字被裁切、溢出容器、被其他元素遮挡，或者元素之间明显不齐（例如按钮大小不一、间距不一致）的地方？
如果有，逐条说明：问题是什么、在截图的什么位置、看到什么现象。

只列最重要的 {max_findings} 条，每条必须引用图中实际存在的文字或控件名称作为定位。

输出 JSON：{{"findings":[{{"issue":"","location":"","evidence":""}}]}}
如果没有发现任何问题，findings 输出空数组。"""




def _extract_json_object(text: str) -> dict:
    """从模型回复里抠出 JSON 对象（容忍围栏、前后废话）。"""
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        candidate = "\n".join(lines[1:]) if len(lines) > 1 else ""
        candidate = candidate.rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        pass
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end > start:
        try:
            parsed = json.loads(candidate[start:end + 1])
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def parse_ui_review(text: str) -> dict:
    """解析结构化审查；模型没遵守 JSON 契约时绝不假报通过。"""
    review = _extract_json_object(text)
    if not review or review.get("status") not in _REVIEW_STATUSES:
        review = {}
    findings = review.get("findings") if isinstance(review.get("findings"), list) else []
    clean_findings = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        clean_findings.append({
            "severity": finding.get("severity") if finding.get("severity") in _REVIEW_SEVERITIES else "low",
            "issue": str(finding.get("issue", "")),
            "evidence": str(finding.get("evidence", "")),
            "suggestion": str(finding.get("suggestion", "")),
        })

    status = review.get("status", "NOT_DETERMINED")
    if status == "PASS" and clean_findings:
        status = "ISSUES_FOUND"
    if status == "ISSUES_FOUND" and not clean_findings:
        status = "NOT_DETERMINED"
    limits = review.get("limits") if isinstance(review.get("limits"), list) else []
    return {
        "status": status,
        "summary": str(review.get("summary", "")),
        "findings": clean_findings,
        "limits": [str(item) for item in limits],
    }


def parse_recheck_findings(text: str) -> list:
    """解析复核阶段的 findings（只有 issue/location/evidence 三项）。"""
    payload = _extract_json_object(text)
    raw = payload.get("findings") if isinstance(payload.get("findings"), list) else []
    findings = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        issue = str(item.get("issue", "")).strip()
        if not issue:
            continue
        findings.append({
            "severity": item.get("severity") if item.get("severity") in _REVIEW_SEVERITIES else "medium",
            "issue": issue,
            "evidence": str(item.get("evidence", "")).strip(),
            "suggestion": str(item.get("suggestion", "")).strip(),
            "location": str(item.get("location", "")).strip(),
        })
    return findings



def _print_result(text: str, elapsed: float, as_json: bool):
    if as_json:
        print(json.dumps(
            {"ok": True, "text": text, "elapsed_secs": elapsed},
            ensure_ascii=False,
        ))
    else:
        print(text)
        print(f"\n⏱ {elapsed:.1f}s", file=sys.stderr)


def cmd_describe(args):
    text = ask(args.image, args.ask or PROMPTS["describe"],
               model_dir=args.model, max_tokens=args.max_tokens,
               verbose=False)
    _print_result(text["text"], text["elapsed_secs"], args.json)
    return 0


def cmd_ask(args):
    if not args.q:
        print("--q 必填（要问图片的问题）", file=sys.stderr)
        return 2
    text = ask(args.image, args.q, model_dir=args.model,
               max_tokens=args.max_tokens)
    _print_result(text["text"], text["elapsed_secs"], args.json)
    return 0


def cmd_cover_check(args):
    target = Path(args.image)
    if target.is_dir() and args.batch:
        paths = collect_images(str(target))
        if not paths:
            print(f"目录里没有图片：{target}", file=sys.stderr)
            return 1
    else:
        paths = [str(target)]

    results = []
    for p in paths:
        if args.json:
            pass
        else:
            print(f"\n📄 {Path(p).name}\n{'-' * 46}")
        try:
            r = ask(p, PROMPTS["cover_check"], model_dir=args.model,
                    max_tokens=args.max_tokens)
        except VisionError as e:
            print(f"✗ {e}", file=sys.stderr)
            continue
        if args.json:
            print(json.dumps({"image": p, **r}, ensure_ascii=False))
        else:
            print(r["text"])
            print(f"  ⏱ {r['elapsed_secs']:.1f}s")
        results.append((p, r))

    if args.batch and not args.json:
        print(f"\n{'=' * 46}")
        bad = [
            Path(p).name for p, r in results
            if any(k in r["text"] for k in ("不合格", "不建议", "存在明显问题"))
        ]
        print(f"批量结果：{len(results) - len(bad)}/{len(results)} 合格", end="")
        if bad:
            print(f"｜需人工复核：{', '.join(bad)}")
        else:
            print()
    return 0


def cmd_ui_review(args):
    """两段式审查。

    为什么要两段：4B 模型看整页截图会把它降采样，标题被裁切、按钮没对齐
    这类像素级缺陷会直接消失（实测被截断的标题被答成「完整显示」）。
    第一段给结构化结论，第二段用「复合提问 + 最多 N 条 + 引用控件名」的
    问法在放大图上复查——实测只有这种问法能稳定召回真实缺陷，
    而带 PASS 模板或逐项是/否清单的问法会诱发模型附和或漏报。
    """
    context = f"页面用途：{args.context}" if args.context else "页面用途：未提供。"
    criteria = f"验收要求：{args.criteria}" if args.criteria else "验收要求：未提供；不要臆造规范。"
    question = UI_REVIEW_PROMPT.format(context=context, criteria=criteria)

    original = args.image
    zoomed = upscaled_for_review(original, factor=args.zoom) if args.zoom > 0 else original
    try:
        scan = ask(zoomed, question, model_dir=args.model, max_tokens=args.max_tokens)
        review = parse_ui_review(scan["text"])
        elapsed = scan["elapsed_secs"]

        if review["status"] == "PASS":
            # 第一段说没问题，就用更细的问法在放大图上再查一遍。
            recheck = ask(
                zoomed,
                UI_RECHECK_PROMPT.format(max_findings=args.max_findings),
                model_dir=args.model,
                max_tokens=args.max_tokens,
            )
            elapsed = round(elapsed + recheck["elapsed_secs"], 2)
            extra = parse_recheck_findings(recheck["text"])
            if extra:
                review["status"] = "ISSUES_FOUND"
                review["findings"] = extra
                review["summary"] = review["summary"] or f"放大复核发现 {len(extra)} 处可见问题。"
    finally:
        cleanup_temp_image(zoomed if zoomed != original else "")

    output = {
        "ok": review["status"] != "NOT_DETERMINED",
        "image": original,
        **review,
        "elapsed_secs": elapsed,
    }
    if args.json:
        print(json.dumps(output, ensure_ascii=False))
    else:
        print(f"{review['status']}: {review['summary']}")
        for finding in review["findings"]:
            print(f"- [{finding['severity']}] {finding['issue']}")
            if finding["evidence"]:
                print(f"  证据：{finding['evidence']}")
            if finding["suggestion"]:
                print(f"  建议：{finding['suggestion']}")
        for limit in review["limits"]:
            print(f"- 范围限制：{limit}")
        if not review["summary"] and review["status"] == "NOT_DETERMINED":
            print("原始回复见 JSON 输出的 raw 字段。")
        print(f"\n⏱ {output['elapsed_secs']:.1f}s", file=sys.stderr)
    if args.fail_on_issues and review["status"] != "PASS":
        return 1
    return 0 if review["status"] != "NOT_DETERMINED" else 2


def cmd_reverse_prompt(args):
    key = "reverse_prompt_zh" if args.lang == "zh" else "reverse_prompt_en"
    text = ask(args.image, PROMPTS[key], model_dir=args.model,
               max_tokens=args.max_tokens)
    _print_result(text["text"], text["elapsed_secs"], args.json)
    return 0


def _add_subcommand_output_options(parser):
    # 根级与子命令级都能写这些标志：调用方常用 `vlm ask img --q "..." --json`。
    # 用 SUPPRESS 作默认值，子命令没写这个标志时不会覆盖根级解析出的值。
    parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="输出 JSON（供程序调用）")
    parser.add_argument("--max-tokens", type=int, default=argparse.SUPPRESS,
                        help="最大生成 token 数")
    parser.add_argument("--model", default=argparse.SUPPRESS,
                        help="MLX 模型目录（默认 ~/.cache/mlx-vlm-kit/models/qwen3-vl-4b-4bit）")


def main():
    ap = argparse.ArgumentParser(
        prog="vlm",
        description="Mac 本地看图理解引擎（Qwen3-VL · MLX）— 免费、离线、可问任何问题",
    )
    ap.add_argument("--model", default=None,
                    help="MLX 模型目录（默认 ~/.cache/mlx-vlm-kit/models/qwen3-vl-4b-4bit）")
    ap.add_argument("--json", action="store_true",
                    help="输出 JSON（供程序调用）")
    ap.add_argument("--max-tokens", type=int, default=400)
    # 装在机器上的到底是哪版得能问出来：它常被 pipx / MCP 包着跑，出问题第一句话
    # 往往是「你装的哪个版本」，没有这个就只能去翻 site-packages。
    ap.add_argument("--version", action="version",
                    version=f"%(prog)s {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("describe", help="描述图片主体与色调")
    p.add_argument("image")
    p.add_argument("--ask", help="自定义问题（覆盖默认描述）")
    _add_subcommand_output_options(p)
    p.set_defaults(func=cmd_describe)

    p = sub.add_parser("ask", help="对图片任意提问")
    p.add_argument("image")
    p.add_argument("--q", required=True, help="要问的问题")
    _add_subcommand_output_options(p)
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("cover-check", help="音乐封面质检（--batch 支持目录递归）")
    p.add_argument("image", help="图片路径或目录")
    p.add_argument("--batch", action="store_true")
    _add_subcommand_output_options(p)
    p.set_defaults(func=cmd_cover_check)

    p = sub.add_parser("ui-review", help="审查 UI 截图（只判断图中可见问题）")
    p.add_argument("image", help="UI 截图路径")
    p.add_argument("--context", help="页面用途或用户任务")
    p.add_argument("--criteria", help="设计稿、验收标准或必须满足的要求")
    p.add_argument("--fail-on-issues", action="store_true",
                   help="发现问题或无法判断时返回非零，供验收脚本使用")
    p.add_argument("--zoom", type=float, default=3.0,
                   help="审查前的放大倍数（默认 3；0 表示不放大）")
    p.add_argument("--max-findings", type=int, default=3,
                   help="复核阶段最多报几条问题（默认 3）")
    _add_subcommand_output_options(p)
    p.set_defaults(func=cmd_ui_review)

    p = sub.add_parser("reverse-prompt", help="反推出图 prompt")
    p.add_argument("image")
    p.add_argument("--lang", choices=["en", "zh"], default="en")
    _add_subcommand_output_options(p)
    p.set_defaults(func=cmd_reverse_prompt)

    args = ap.parse_args()
    try:
        sys.exit(args.func(args))
    except VisionError as e:
        print(f"✗ {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
