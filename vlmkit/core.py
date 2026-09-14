"""核心推理封装：加载模型 + 单次问答。

约定：
- 模型懒加载（模块级缓存），首次调用才真正吃内存
- 支持的图片格式：jpg / jpeg / png / webp
- 输出纯文本，管道友好
"""
import os
import time
from pathlib import Path
from typing import Optional

from . import DEFAULT_MODEL_REPO, default_model_dir

_SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

_MODEL_CACHE = {"model": None, "processor": None, "path": None}


class VisionError(Exception):
    """vlmkit 错误。"""


def is_supported_image(path: str) -> bool:
    return Path(path).suffix.lower() in _SUPPORTED_EXTS


def collect_images(root: str, recursive: bool = True) -> list:
    """收集目录下的图片；跳过 macOS 元数据文件（._ 前缀）。"""
    rootp = Path(root)
    if not rootp.is_dir():
        return []
    it = rootp.rglob("*") if recursive else rootp.iterdir()
    return sorted(
        str(p) for p in it
        if p.is_file() and p.suffix.lower() in _SUPPORTED_EXTS
        and not p.name.startswith("._")
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


def ask(
    image_path: str,
    question: str,
    model_dir: Optional[str] = None,
    max_tokens: int = 400,
    verbose: bool = False,
) -> dict:
    """对一张图片提问，返回 {"text", "elapsed_secs", "load_secs"}。"""
    if not is_supported_image(image_path):
        raise VisionError(f"不支持的图片格式: {image_path}")
    if not Path(image_path).exists():
        raise VisionError(f"图片不存在: {image_path}")

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
