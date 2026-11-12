"""核心推理封装：加载模型 + 单次问答。

约定：
- 模型懒加载（模块级缓存），首次调用才真正吃内存
- 支持的图片格式：jpg / jpeg / png / webp
- 输出纯文本，管道友好
"""
import os
import tempfile
import time
from pathlib import Path
from typing import Optional

from PIL import Image, UnidentifiedImageError

from . import DEFAULT_MODEL_REPO, default_model_dir

_SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP"}
_SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

_MODEL_CACHE = {"model": None, "processor": None, "path": None}


class VisionError(Exception):
    """vlmkit 错误。"""


def image_format(path: str) -> Optional[str]:
    """按图片内容识别格式，不依赖文件名扩展名。"""
    try:
        with Image.open(path) as image:
            image_format = image.format
            image.verify()
        return image_format if image_format in _SUPPORTED_FORMATS else None
    except (FileNotFoundError, OSError, UnidentifiedImageError, ValueError):
        return None


def is_supported_image(path: str) -> bool:
    """JPEG/PNG/WebP 按文件内容识别，支持系统生成的无扩展名截图。"""
    return image_format(path) is not None


def collect_images(root: str, recursive: bool = True) -> list:
    """收集目录下的图片；按内容识别格式并跳过 macOS 元数据文件。"""
    rootp = Path(root)
    if not rootp.is_dir():
        return []
    it = rootp.rglob("*") if recursive else rootp.iterdir()
    return sorted(
        str(p) for p in it
        if p.is_file() and not p.name.startswith("._")
        and is_supported_image(str(p))
    )


def ensure_model(model_dir: Optional[str] = None, repo: str = DEFAULT_MODEL_REPO) -> str:
    """确保模型在本地；没有就下载。返回本地路径。"""
    d = model_dir or default_model_dir()
    if os.path.isdir(d) and any(
        f.endswith(".safetensors") for f in os.listdir(d)
    ):
        return d
    print(f"模型不在 {d}，从 {repo} 下载（约 2.9 GB）...", file=sys_stderr())
    from huggingface_hub import snapshot_download
    snapshot_download(repo_id=repo, local_dir=d)
    return d


def sys_stderr():
    import sys
    return sys.stderr


def upscaled_for_review(image_path: str, factor: float = 3.0,
                        max_side: int = 4000) -> str:
    """把截图放大后另存，供细粒度审查使用。

    为什么：模型看整页截图时会把它降采样，标题被裁切、按钮没对齐这类
    像素级缺陷会直接看不见（实测 480px 宽截图里被截断的标题被答成
    「完整显示」）。放大后同一个缺陷能被稳定识别。
    返回临时文件路径，调用方负责清理。
    """
    from PIL import Image

    with Image.open(image_path) as image:
        width, height = image.size
        scale = factor
        longest = max(width, height)
        if longest * scale > max_side:
            scale = max_side / longest
        if scale <= 1.05:
            # 已经够大，放大只会白烧 token 和时间。
            return image_path
        resized = image.resize((int(width * scale), int(height * scale)), Image.LANCZOS)

    handle, target = tempfile.mkstemp(prefix="vlm-review-", suffix=".png")
    os.close(handle)
    resized.save(target, format="PNG")
    return target


def cleanup_temp_image(path: str) -> None:
    """删掉放大产生的临时图；原图不动。"""
    if path and os.path.isfile(path):
        try:
            os.unlink(path)
        except OSError:
            pass


def ask(
    image_path: str,
    question: str,
    model_dir: Optional[str] = None,
    max_tokens: int = 400,
    verbose: bool = False,
) -> dict:
    """对一张图片提问，返回 {"text", "elapsed_secs", "load_secs"}。"""
    if not Path(image_path).is_file():
        raise VisionError(f"图片不存在: {image_path}")
    if not is_supported_image(image_path):
        raise VisionError(f"不支持或无法读取的图片格式（支持 JPEG/PNG/WebP）: {image_path}")

    d = ensure_model(model_dir)

    # 模型缓存：同一路径不重复加载
    if _MODEL_CACHE["model"] is None or _MODEL_CACHE["path"] != d:
        from mlx_vlm import load
        t0 = time.time()
        model, processor = load(d)
        _MODEL_CACHE.update(model=model, processor=processor, path=d)
        if verbose:
            print(f"[load {time.time()-t0:.1f}s]", file=sys_stderr())
    model, processor = _MODEL_CACHE["model"], _MODEL_CACHE["processor"]

    from mlx_vlm import generate
    from mlx_vlm.prompt_utils import apply_chat_template

    t0 = time.time()
    formatted = apply_chat_template(
        processor, model.config, question, num_images=1
    )
    result = generate(
        model, processor, formatted, [image_path],
        max_tokens=max_tokens, verbose=False,
    )
    dt = time.time() - t0
    text = result.text if hasattr(result, "text") else str(result)
    return {"text": text.strip(), "elapsed_secs": round(dt, 2)}
