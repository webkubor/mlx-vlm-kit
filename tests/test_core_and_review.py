"""测试：图片格式识别与 UI 审查解析。

跑法：python -m unittest discover -s tests
不加载 MLX 模型（这里只测纯逻辑），所以没有 Apple Silicon 也能跑。
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vlmkit.cli import parse_recheck_findings, parse_ui_review  # noqa: E402
from vlmkit.core import (  # noqa: E402
    collect_images,
    image_format,
    is_supported_image,
    upscaled_for_review,
)


def _make_image(path: Path, fmt: str = "PNG") -> Path:
    from PIL import Image

    Image.new("RGB", (8, 8), (10, 20, 30)).save(path, format=fmt)
    return path


class TestImageFormatDetection(unittest.TestCase):
    def test_detects_format_without_extension(self):
        """系统截图常没有扩展名；只看扩展名会把它挡在门外。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "screenshot-no-extension"
            _make_image(path, "PNG")
            self.assertEqual(image_format(str(path)), "PNG")
            self.assertTrue(is_supported_image(str(path)))

    def test_detects_jpeg_and_webp(self):
        with tempfile.TemporaryDirectory() as tmp:
            for fmt, suffix in (("JPEG", ".jpg"), ("WEBP", ".webp")):
                path = Path(tmp) / f"image{suffix}"
                _make_image(path, fmt)
                self.assertEqual(image_format(str(path)), fmt)
                self.assertTrue(is_supported_image(str(path)))

    def test_rejects_non_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notes.txt"
            path.write_text("not an image")
            self.assertIsNone(image_format(str(path)))
            self.assertFalse(is_supported_image(str(path)))

    def test_missing_file(self):
        self.assertIsNone(image_format("/nonexistent/path/image.png"))
        self.assertFalse(is_supported_image("/nonexistent/path/image.png"))

    def test_collect_images_finds_extensionless_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_image(Path(tmp) / "shot-1")
            _make_image(Path(tmp) / "shot-2.png")
            (Path(tmp) / "notes.txt").write_text("x")
            found = collect_images(tmp)
            names = sorted(Path(p).name for p in found)
            self.assertEqual(names, ["shot-1", "shot-2.png"])


class TestUiReviewParsing(unittest.TestCase):
    def test_parses_valid_pass(self):
        payload = json.dumps({
            "status": "PASS",
            "summary": "未发现明显问题",
            "findings": [],
            "limits": ["无法判断交互行为"],
        }, ensure_ascii=False)
        review = parse_ui_review(payload)
        self.assertEqual(review["status"], "PASS")
        self.assertEqual(len(review["findings"]), 0)
        self.assertEqual(review["limits"], ["无法判断交互行为"])

    def test_parses_valid_issues(self):
        payload = json.dumps({
            "status": "ISSUES_FOUND",
            "summary": "标题被裁切",
            "findings": [{
                "severity": "high",
                "issue": "标题被裁切",
                "evidence": "右上角标题右侧缺字",
                "suggestion": "缩短标题或换行",
            }],
            "limits": [],
        }, ensure_ascii=False)
        review = parse_ui_review(payload)
        self.assertEqual(review["status"], "ISSUES_FOUND")
        self.assertEqual(review["findings"][0]["severity"], "high")

    def test_non_json_becomes_not_determined(self):
        """模型没遵守契约时不能假报通过。"""
        review = parse_ui_review("看起来没什么问题。")
        self.assertEqual(review["status"], "NOT_DETERMINED")
        self.assertEqual(review["findings"], [])

    def test_strips_code_fence(self):
        payload = "```json\n" + json.dumps({
            "status": "PASS", "summary": "ok", "findings": [], "limits": [],
        }) + "\n```"
        review = parse_ui_review(payload)
        self.assertEqual(review["status"], "PASS")

    def test_pass_with_findings_is_downgraded(self):
        payload = json.dumps({
            "status": "PASS",
            "summary": "ok",
            "findings": [{"severity": "medium", "issue": "对齐不一致", "evidence": "e", "suggestion": "s"}],
            "limits": [],
        }, ensure_ascii=False)
        self.assertEqual(parse_ui_review(payload)["status"], "ISSUES_FOUND")

    def test_issues_without_findings_is_not_determined(self):
        payload = json.dumps({
            "status": "ISSUES_FOUND", "summary": "有问题", "findings": [], "limits": [],
        }, ensure_ascii=False)
        self.assertEqual(parse_ui_review(payload)["status"], "NOT_DETERMINED")

    def test_unknown_status_is_not_determined(self):
        payload = json.dumps({"status": "MAYBE", "summary": "", "findings": [], "limits": []})
        self.assertEqual(parse_ui_review(payload)["status"], "NOT_DETERMINED")

    def test_invalid_severity_defaults_to_low(self):
        payload = json.dumps({
            "status": "ISSUES_FOUND",
            "summary": "s",
            "findings": [{"severity": "critical!!", "issue": "i", "evidence": "e", "suggestion": "g"}],
            "limits": [],
        }, ensure_ascii=False)
        self.assertEqual(parse_ui_review(payload)["findings"][0]["severity"], "low")


class TestUpscaleForReview(unittest.TestCase):
    """审查前的放大：模型看整页会被降采样，缺陷会消失。"""

    def test_upscales_small_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _make_image(Path(tmp) / "ui.png")
            zoomed = upscaled_for_review(str(path), factor=3.0)
            try:
                from PIL import Image

                with Image.open(zoomed) as image:
                    self.assertEqual(image.size, (24, 24))
            finally:
                from vlmkit.core import cleanup_temp_image

                cleanup_temp_image(zoomed)

    def test_keeps_large_image_unchanged(self):
        """已经够大的图不再放大：省时间也省 token。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "big.png"
            from PIL import Image

            Image.new("RGB", (5000, 100), (1, 2, 3)).save(path)
            zoomed = upscaled_for_review(str(path), factor=3.0, max_side=4000)
            self.assertEqual(zoomed, str(path))


class TestRecheckParsing(unittest.TestCase):
    def test_parses_findings_only_payload(self):
        payload = json.dumps({
            "findings": [
                {"issue": "长标题文字溢出容器", "location": "顶部卡片标题",
                 "evidence": "最后一个字被卡片边缘切断"},
            ],
        }, ensure_ascii=False)
        findings = parse_recheck_findings(payload)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["issue"], "长标题文字溢出容器")
        self.assertEqual(findings[0]["location"], "顶部卡片标题")
        self.assertEqual(findings[0]["severity"], "medium")

    def test_empty_findings(self):
        self.assertEqual(parse_recheck_findings('{"findings":[]}'), [])
        self.assertEqual(parse_recheck_findings("not json"), [])

    def test_skips_entries_without_issue(self):
        payload = json.dumps({"findings": [{"location": "x"}, {"issue": "真问题"}]},
                             ensure_ascii=False)
        findings = parse_recheck_findings(payload)
        self.assertEqual(len(findings), 1)

    def test_extracts_json_from_surrounding_text(self):
        text = '分析如下：\n{"findings":[{"issue":"按钮大小不一致"}]}\n以上。'
        findings = parse_recheck_findings(text)
        self.assertEqual(len(findings), 1)


class TestCliArguments(unittest.TestCase):
    """CLI 参数解析：子命令级标志也要能用。"""

    def test_ui_review_help(self):
        import subprocess

        result = subprocess.run(
            [sys.executable, "-m", "vlmkit.cli", "ui-review", "--help"],
            capture_output=True, text=True,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--context", result.stdout)
        self.assertIn("--criteria", result.stdout)
        self.assertIn("--fail-on-issues", result.stdout)

    def test_json_flag_accepted_after_subcommand(self):
        """`vlm ask img --q "..." --json` 是调用方的常用写法。"""
        import subprocess

        result = subprocess.run(
            [sys.executable, "-m", "vlmkit.cli", "ask", "missing.png",
             "--q", "x", "--json"],
            capture_output=True, text=True,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        # 图片不存在也会报错，但不该是「unrecognized arguments」。
        self.assertNotIn("unrecognized arguments", result.stderr)
        self.assertIn("图片不存在", result.stderr)


if __name__ == "__main__":
    unittest.main()
