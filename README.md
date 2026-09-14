# mlx-vlm-kit

**Mac 本地看图理解引擎** —— 让你的 Mac 看懂图片、回答关于图片的任何问题。
Qwen3-VL-4B（Apple MLX 原生），免费、离线、可被任何项目调用。

[![npm](https://img.shields.io/badge/pipx-install-2ea043?style=flat-square)](#-安装)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)

## 为什么

| | 云端 VLM API | **mlx-vlm-kit（本地）** |
|---|---|---|
| 单次调用 | ¥0.01~0.05/张 | **¥0** |
| 月度成本 | 用量越大越贵 | **固定零成本** |
| 隐私 | 图片上传 | **不出机** |
| 调用方式 | 每家 SDK 不同 | **一个 CLI，所有项目 shell 调用** |

定位一句话：

> **mlx-vlm-kit = Mac 的「看图理解引擎」——任何项目、任何 agent，对任何图片提问。**

不只是「眼睛」——四层能力：

| 层 | 是什么 | 例子 |
|---|---|---|
| 👁 **看见** | 图片里有什么 | 截图读字、封面有无标题 |
| ⚖️ **判断** | 拿图片做评估 | 封面质检合不合格、缩略图够不够抓人 |
| 🔄 **反推** | 从图片倒推生成 prompt | 好封面 → 反推 → 出图模型复刻变体 |
| 💬 **问答** | `--ask` 任意问题 | 「这张图适合投小红书吗」 |

**不是什么**：不看视频（只吃静态图）、不生成图片（配合 [museav gen](https://github.com/webkubor/museav-cli) 出图）、不是专业 OCR 引擎。

## 安装

```bash
# pipx 装（推荐，隔离环境）
pipx install git+https://github.com/webkubor/mlx-vlm-kit.git

# 首次使用时自动下载模型（约 2.9 GB，一次性）
vlm describe any-image.jpg
```

要求：**macOS + Apple Silicon（M1+）**，Python 3.12+，16 GB 统一内存起步。

## 用法

```bash
# 描述一张图
vlm describe cover.jpg

# 任意提问
vlm ask screenshot.png --q "这个报错是什么意思？"

# 音乐封面质检（voxflow 用）
vlm cover-check ~/Music/album/cover.jpg

# 批量质检（递归子目录）
vlm cover-check ~/out/待上传 --batch

# 反推出图 prompt（英文，直接喂出图模型）
vlm reverse-prompt great-cover.jpg --lang en
```

输出默认给人看；`--json` 给程序调用（管道友好）：

```bash
vlm ask shot.png --q "几个人？" --json | jq -r .text
```

## 被谁使用

| 项目 | 用法 |
|---|---|
| [voxflow](https://github.com/webkubor/voxflow) | 封面语义质检（原来只查尺寸，现在连内容一起查） |
| [reel-kit](https://github.com/webkubor/reel-kit) | 分镜帧理解、缩略图吸引力评估 |
| [voiceinput](https://github.com/webkubor/voiceinput) | 截图读字、界面理解（`visionkit` crate 桥接本 CLI） |
| [museav-mcp](https://github.com/webkubor/museav-mcp) | 注册为 satellite tool，agent 通过 MCP 调用 |

## 模型

- 默认：[mlx-community/Qwen3-VL-4B-Instruct-4bit](https://huggingface.co/mlx-community/Qwen3-VL-4B-Instruct-4bit)（2.9 GB）
- 位置：`~/.cache/mlx-vlm-kit/models/`（`MLX_VLM_MODEL_DIR` 可覆盖）
- 懒加载：首次调用才加载进统一内存；同进程内复用

实测（M3 Pro · 18GB）：加载 2-4s（热）、推理 6-28s/张（视输出长度）。

## LICENSE

MIT。模型权重另行遵循 [Qwen3-VL 的模型协议](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct)。
