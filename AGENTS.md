# AGENTS.md — AI 助手工作守则

## 这是什么

mlx-vlm-kit —— Apple Silicon 本地视觉语言模型 CLI：MLX / Qwen3-VL，
离线做图片描述、图像问答、提示词反推。定位就是「不联网、不出本机」。

## 关键文件

- `vlmkit/`：全部源码（CLI 子命令与模型调用都在里面）。
- `pyproject.toml`：包定义、依赖与入口。
- `README.md` / `README.en.md`：双语 README，同步改。

## 约定

- 本地推理是产品定位：不引入任何强制联网 / 云端 API 路径。
- 模型加载注意内存分级（不同 Mac 的统一内存差异），默认参数要在小内存机型上可跑。
- 双语文档同步维护；CHANGELOG 走既有发布流程。
