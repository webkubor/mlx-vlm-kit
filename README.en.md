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
| 🔍 **Nitpick** | Pixel-level UI screenshot review | Truncated titles, mismatched buttons, broken spacing |
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

# UI screenshot review (catch pixel-level defects after a change)
vlm ui-review shot.png --context "settings page card actions"

# Review + acceptance criteria + gate exit code (non-zero when issues found)
vlm ui-review shot.png --criteria "buttons must be the same size" --fail-on-issues

# Reverse-engineer a generation prompt (English, feed straight into an image gen model)
vlm reverse-prompt great-cover.jpg --lang en
```

Human-readable output by default; `--json` for programmatic use (pipe-friendly):

```bash
vlm ask shot.png --q "How many people?" --json | jq -r .text
```

Image formats are detected by **content**, not filename extension — extensionless screenshots from system capture tools or chat apps work directly.

## How ui-review decides

`vlm ui-review` outputs three states: `PASS` / `ISSUES_FOUND` / `NOT_DETERMINED`. Each finding carries location + in-image evidence + suggestion, plus explicit scope limits:

- Only checks what a **screenshot can prove**: clipped/occluded/overflowing text, misaligned elements, inconsistent spacing, poor contrast, broken hierarchy
- Never guesses what a screenshot cannot prove: clickability, form submission, responsive breakpoints, accessibility — these are listed in `limits`
- If the model fails to answer in the required format, the result is `NOT_DETERMINED` — "didn't understand" is **never** treated as "no problems"

Known boundary (honest): a 4B model downsamples full-page screenshots, so pixel-level defects can fall below its perception. How ui-review handles it (tuned by measurement, see CHANGELOG):

1. Upscale 6× first.
2. **Problem-hunt pass leads**: a compound "any clipping/occlusion/misalignment?" probe — 10/10 stable recall on a seeded-defect page, zero false positives on a clean page. Any hit → ISSUES_FOUND in ~30s.
3. A clean probe runs twice; only when both come back empty does a structured description run to fill summary/limits, then PASS (~80s — slower by design: clearing a page should cost more than flagging it).

In testing this reliably catches truncated titles and mismatched button sizes, but a small model occasionally over-reports questionable findings — treat each finding's evidence as a lead to verify, not gospel.

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