# wan-influencer-pipeline

Generate 10 AI influencer videos from a single dance source clip using Wan2.2-Animate 14B (Q8 GGUF) via ComfyUI.

## What this does

1 dance video + 10 reference face/body images → 10 AI influencer videos using Wan2.2-Animate 14B (Q8 GGUF) running locally in ComfyUI. Designed for a single RTX 5080 (Blackwell) on Linux/WSL2.

## System requirements

- NVIDIA RTX GPU with 16 GB+ VRAM (tested on RTX 5080 Blackwell sm_120)
- NVIDIA driver ≥ 570 on Linux (Blackwell requirement)
- Linux or WSL2 (Arch shown; any distro with `nvidia-smi` working will do)
- Python 3.13 (Arch default) or 3.12 / 3.11
- CUDA 12.8 runtime via PyTorch nightly cu128 wheels — **stable cu124 will NOT work on Blackwell**

## Setup

```bash
bash setup.sh
source ~/wan-pipeline/venv/bin/activate
python check_vram.py    # must report capability (12, 0) and a successful matmul
```

## Model downloads

Total ~25–30 GB. The five files must live under `~/wan-pipeline/ComfyUI/models/{diffusion_models,vae,text_encoders,clip_vision,onnx}`.

```bash
huggingface-cli download city96/Wan2.2-Animate-14B-gguf wan2.2_animate_14B_Q8_0.gguf \
  --local-dir ~/wan-pipeline/ComfyUI/models/diffusion_models

huggingface-cli download Comfy-Org/Wan_2.2_ComfyUI_Repackaged \
  split_files/vae/wan_2.1_vae.safetensors \
  --local-dir ~/wan-pipeline/ComfyUI/models/vae

huggingface-cli download Comfy-Org/Wan_2.2_ComfyUI_Repackaged \
  split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors \
  --local-dir ~/wan-pipeline/ComfyUI/models/text_encoders

huggingface-cli download Comfy-Org/Wan_2.1_ComfyUI_repackaged \
  split_files/clip_vision/clip_vision_h.safetensors \
  --local-dir ~/wan-pipeline/ComfyUI/models/clip_vision

huggingface-cli download yzd-v/DWPose dw-ll_ucoco_384.onnx yolox_l.onnx \
  --local-dir ~/wan-pipeline/ComfyUI/models/onnx
```

### DWPose / pose detector ONNX

Wan2.2-Animate uses pose conditioning, so WanVideoWrapper will fail on first run without the DWPose ONNX files — the last command above covers it.

## Optional speed-up: sage attention

Recommended on Blackwell (~30% faster).

```bash
source ~/wan-pipeline/venv/bin/activate
pip install triton sageattention
```

Then set `attention_mode: sageattn` in the workflow.

## Usage

See `workflows/README.md` for the one-time workflow export. Then run `python run_batch.py` per its `--help` / `workflows/README.md`.

Two workflows ship with this repo:

- **`workflows/wan22_animate_16gb.json`** — single 65-frame chunk (~4 s output at 16 fps). Use this for the local 16 GB RTX 5080 path and as the smoke-test workflow.
- **`workflows/wan22_animate_chunked.json`** — four chained 65-frame chunks (~16 s output at 16 fps, doubled to 32 fps via RIFE VFI). Drives `WanAnimateToVideo` four times in parallel and concatenates with `ImageBatch` before frame interpolation. This workflow has multiple `LoadImage` / `VHS_LoadVideo` nodes, so the root `run_batch.py` will refuse it — use `runpod/runpod_batch.py` instead, which patches every matching node uniformly. See `runpod/README.md`.

## Cloud deployment (RunPod / A100)

`runpod/` contains a `Dockerfile`, container `entrypoint.sh`, `runpod_batch.py` (multi-patch variant of `run_batch.py`), and `s3_sync.py` — everything needed to run this pipeline on a RunPod A100 80GB pod with optional S3 sync for inputs and outputs. The chunked workflow targets this path because long-video generation exceeds the headroom of a 16 GB card. See `runpod/README.md` for build instructions, env vars, storage layout, and a cost/time estimate.

**LTX-2.3 parallel track.** A second image is published alongside the Wan 2.2 build for direct A/B testing: `ghcr.io/<owner>/wan-influencer-pipeline:ltx23` (22B FP8 dev checkpoint, IC-LoRA Union Control for pose conditioning, native audio generation). Built from `runpod/Dockerfile.ltx23` + `runpod/entrypoint.ltx23.sh` and driven by `workflows/ltx23_pose.json`. The `:latest` tag continues to point at the Wan 2.2 image so existing references are unaffected. See `runpod/README.md` → *A/B testing Wan 2.2 vs LTX-2.3* for image tags, env-var presets per track, per-clip cost on A100 80GB Community, and the strategic trade-offs between the two models.

## Expected times

On RTX 5080 @ 576×1024 / 65 frames / 25 steps / Q8 GGUF / sequential offload:
- ~10–12 min per clip with sdpa
- ~7–9 min per clip with sageattn
- Full batch of 10: ~1.5–2 hours

## Notes on `.gitignore`

Media file types (`*.mp4 *.png *.jpg`) and model weights (`*.safetensors *.gguf *.onnx`) are git-ignored everywhere by design. The `.gitkeep` files inside `assets/influencers/`, `assets/source/`, and `outputs/` are explicitly un-ignored. Drop your inputs into those dirs and don't expect `git status` to show them.
