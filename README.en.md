# mlx-vlm-kit

**Local image-understanding engine for Mac** — make your Mac see images and answer questions about them.
Qwen3-VL-4B (native Apple MLX), free, offline, callable from any project.

[![pipx install](https://img.shields.io/badge/pipx-install-2ea043?style=flat-square)](#-install)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)

## Why

| | Cloud VLM API | **mlx-vlm-kit (local)** |
|---|---|---|
| Per call | ¥0.01–0.05 / image | **¥0** |
| Monthly cost | Grows with usage | **Fixed at zero** |
| Privacy | Image uploaded | **Stays on machine** |
| Integration | Each SDK is its own thing | **One CLI, callable from any project via shell** |

One-liner:

> **mlx-vlm-kit = a "visual understanding engine" for your Mac — any project, any agent, any question about any image.**

Four layers of capability, not just "eyes":

| Layer | What | Example |
|---|---|---|
| 👁 **See** | What's in the image | Read text in a screenshot, check if a cover has a title |
| ⚖️ **Judge** | Evaluate against criteria | Is this cover good? Is the thumbnail eye-catching? |
| 🔄 **Reverse** | Derive a generation prompt from an image | Good cover → reverse → recreate variants with an image gen model |
| 💬 **Ask** | `--ask` any question | "Is this image a fit for Xiaohongshu?" |

**What it isn't**: doesn't handle video (static images only), doesn't generate images (pair with [museav gen](https://github.com/webkubor/museav-cli) for that), isn't a professional OCR engine.

## Install

```bash
# pipx (recommended — isolated env)
pipx install git+https://github.com/webkubor/mlx-vlm-kit.git

# First run auto-downloads the model (~2.9 GB, one-time)
vlm describe any-image.jpg
```

Requirements: **macOS + Apple Silicon (M1+)**, Python 3.12+, 16 GB unified memory minimum.

## Usage

```bash
# Describe an image
vlm describe cover.jpg

# Ask anything
vlm ask screenshot.png --q "What does this error mean?"

# Music cover quality check (used by voxflow)
vlm cover-check ~/Music/album/cover.jpg

# Batch quality check (recurses subdirectories)
vlm cover-check ~/out/pending --batch

# Reverse-engineer a generation prompt (English, feed straight into an image gen model)
vlm reverse-prompt great-cover.jpg --lang en
```

Human-readable output by default; `--json` for programmatic use (pipe-friendly):

```bash
vlm ask shot.png --q "How many people?" --json | jq -r .text
```

## Who uses it

| Project | Usage |
|---|---|
| [voxflow](https://github.com/webkubor/voxflow) | Cover semantic check (used to be size-only, now content-aware too) |
| [reel-kit](https://github.com/webkubor/reel-kit) | Storyboard frame understanding, thumbnail appeal scoring |
| [voiceinput](https://github.com/webkubor/voiceinput) | Screenshot OCR + UI comprehension (the `visionkit` crate bridges this CLI) |
| [cs-mcp](https://github.com/webkubor/cs-mcp) | Registered as a satellite tool, agents call via MCP (formerly museav-mcp) |

## Model

- Default: [mlx-community/Qwen3-VL-4B-Instruct-4bit](https://huggingface.co/mlx-community/Qwen3-VL-4B-Instruct-4bit) (2.9 GB)
- Location: `~/.cache/mlx-vlm-kit/models/` (override via `MLX_VLM_MODEL_DIR`)
- Lazy-loaded into unified memory on first call; reused within the same process

Measured on M3 Pro · 18 GB: load 2–4 s (warm), inference 6–28 s / image (depends on output length).

## LICENSE

MIT. Model weights are subject to the [Qwen3-VL model license](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct).