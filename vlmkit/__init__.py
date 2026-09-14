"""mlx-vlm-kit — Mac 本地看图理解引擎。

定位：任何项目、任何 agent，对任何图片提问。
- 免费：一次部署零调用成本
- 离线：图片不出机（Qwen3-VL-4B，Apple Silicon 原生 MLX）
- 纯文本输出：说不说、念给谁听，下游自己接（管道友好）
"""

__version__ = "0.1.0"

DEFAULT_MODEL_REPO = "mlx-community/Qwen3-VL-4B-Instruct-4bit"
DEFAULT_MODEL_DIR_NAME = "qwen3-vl-4b-4bit"


def default_model_dir() -> str:
    """模型默认真源目录（可用环境变量 MLX_VLM_MODEL_DIR 覆盖）。"""
    import os
    override = os.environ.get("MLX_VLM_MODEL_DIR")
    if override:
        return override
    return os.path.expanduser(
        f"~/.cache/mlx-vlm-kit/models/{DEFAULT_MODEL_DIR_NAME}"
    )
