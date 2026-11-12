# Changelog

## 0.2.0 (2026-11-12)

### 新增：UI 截图审查 `vlm ui-review`

给「改完页面 → 截图 → 让本地模型挑刺」一条现成的路：

```bash
vlm ui-review shot.png --context "设置页卡片操作区"        # 人读结论
vlm ui-review shot.png --fail-on-issues --json            # 验收门禁（有问题退出码 1）
```

- 输出三态 `PASS / ISSUES_FOUND / NOT_DETERMINED`；每条问题带位置、图中证据、建议；截图证明不了的事（交互、响应式、可访问性）进 `limits`，不冒充结论。
- 模型没按契约回 JSON 时判 `NOT_DETERMINED`，不把「看不懂」当「没问题」。
- 实测抓得住「标题被截断」「按钮大小不一」；小模型偶有多报，evidence 当线索核对。

为什么复核优先（实测数据）：4B 模型看整页会降采样，480px 截图里被截断的标题被答成「完整显示」。放大 6 倍后，「结构化扫描」问法仍不稳（同一缺陷图 8 次里 3 次整段漏报），而「是否存在裁切/遮挡/不齐」的复合提问 10/10 稳定召回、干净页零误报。故复核段打头并连跑两轮（两轮全空才 PASS），结构化扫描降级为补 summary/limits 的描述器。带 PASS 模板或逐项是/否清单的问法会诱发附和漏报，弃用。缺陷页 ~30s 出 ISSUES_FOUND，干净页 ~80s 出 PASS——放行更费劲是设计取向。

### 新增：图片按内容识别格式

系统截图、聊天工具导出的**无扩展名**文件直接用，不再报「不支持的图片格式」；`collect_images`（`--batch`）同样按内容识别，误把文本文件当图片的路径不再出现。

### 改进

- `--json` / `--max-tokens` / `--model` 现在写在子命令后面也能用（`vlm ask img --q "…" --json`），不必挪到 `vlm` 后面。
- 新增单元测试 21 条（格式识别、JSON 解析容错、放大逻辑），`python -m unittest discover -s tests`；纯逻辑测试不加载模型，Linux CI 也能跑。

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
