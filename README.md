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

huggingface-cli download Comfy-Org/Wan_2.2_ComfyUI_Repackaged \
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

## Expected times

On RTX 5080 @ 576×1024 / 65 frames / 25 steps / Q8 GGUF / sequential offload:
- ~10–12 min per clip with sdpa
- ~7–9 min per clip with sageattn
- Full batch of 10: ~1.5–2 hours

## Notes on `.gitignore`

Media file types (`*.mp4 *.png *.jpg`) and model weights (`*.safetensors *.gguf *.onnx`) are git-ignored everywhere by design. The `.gitkeep` files inside `assets/influencers/`, `assets/source/`, and `outputs/` are explicitly un-ignored. Drop your inputs into those dirs and don't expect `git status` to show them.
