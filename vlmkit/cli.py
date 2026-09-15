"""vlm CLI — 四个子命令：describe / ask / cover-check / reverse-prompt。

用法：
    vlm describe <图片>                          # 描述主体与色调
    vlm ask <图片> --q "这个问题怎么回答"         # 任意提问
    vlm cover-check <图片|目录> [--batch]        # 音乐封面质检
    vlm reverse-prompt <图片> [--lang en|zh]     # 反推出图 prompt
"""
import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core import ask, collect_images, is_supported_image, VisionError

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


def cmd_reverse_prompt(args):
    key = "reverse_prompt_zh" if args.lang == "zh" else "reverse_prompt_en"
    text = ask(args.image, PROMPTS[key], model_dir=args.model,
               max_tokens=args.max_tokens)
    _print_result(text["text"], text["elapsed_secs"], args.json)
    return 0


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
    p.set_defaults(func=cmd_describe)

    p = sub.add_parser("ask", help="对图片任意提问")
    p.add_argument("image")
    p.add_argument("--q", required=True, help="要问的问题")
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("cover-check", help="音乐封面质检（--batch 支持目录递归）")
    p.add_argument("image", help="图片路径或目录")
    p.add_argument("--batch", action="store_true")
    p.set_defaults(func=cmd_cover_check)

    p = sub.add_parser("reverse-prompt", help="反推出图 prompt")
    p.add_argument("image")
    p.add_argument("--lang", choices=["en", "zh"], default="en")
    p.set_defaults(func=cmd_reverse_prompt)

    args = ap.parse_args()
    try:
        sys.exit(args.func(args))
    except VisionError as e:
        print(f"✗ {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
