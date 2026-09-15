# Changelog

## 0.1.0 (2026-09-15)

### 首个公开版本：Mac 的看图理解引擎

Qwen3-VL-4B（Apple MLX 原生）包成一个 CLI，四个子命令，全部本地跑：

| 子命令 | 干什么 |
| --- | --- |
| `vlm describe <图>` | 描述主体与色调（`--ask` 可换成自己的问题） |
| `vlm ask <图> --q "…"` | 对图片任意提问 |
| `vlm cover-check <图\|目录>` | 音乐封面语义质检，`--batch` 递归整个目录 |
| `vlm reverse-prompt <图> --lang en\|zh` | 从图片反推出图 prompt |

设计约定：

- **免费**：模型在本地，单次调用成本为 0；模型权重不进包，放 `~/.cache/mlx-vlm-kit/`，首次用时下载
- **离线**：图片不出机；`MLX_VLM_MODEL_DIR` 可换模型目录
- **管道友好**：`--json` 输出 `{ok, text, elapsed_secs}`，给人看时耗时走 stderr

### 本版新增

- `--version`：装在机器上的是哪一版能直接问出来。

  它常被 pipx 和 [museav-mcp](https://github.com/webkubor/museav-mcp) 包着跑（MCP 用
  `execFile` 调 `vlm`，进程里看不到版本），没有这个标志时，报错排查只能去翻
  site-packages。更早的版本里 `vlm --version` 会被 argparse 判成「缺少子命令」而报错。

### 被谁使用

[voxflow](https://github.com/webkubor/voxflow)（封面语义质检）·
[reel-kit](https://github.com/webkubor/reel-kit)（分镜帧理解）·
[voiceinput](https://github.com/webkubor/voiceinput)（截图读字）·
[museav-mcp](https://github.com/webkubor/museav-mcp)（`vlm_describe` / `vlm_ask` /
`vlm_cover_check` / `vlm_reverse_prompt` 四个 MCP 工具）

### 环境要求

macOS + Apple Silicon（M1 起），Python 3.12+，16 GB 统一内存起步。
