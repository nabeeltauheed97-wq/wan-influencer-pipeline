# AGENTS.md

## Context

You are operating inside the `wan-influencer-pipeline` repo on the user's WSL2 Arch Linux machine. Hardware: RTX 5080 (Blackwell sm_120, 16 GB VRAM). Goal: set up ComfyUI + Wan2.2-Animate 14B and produce N portrait videos from one source dance video and N reference images. Always run commands via the terminal tool; do NOT modify `setup.sh`, `run_batch.py`, or `check_vram.py` unless the user explicitly asks.

## Hard constraints

- Use PyTorch **nightly cu128** only (never stable cu124 — sm_120 has no kernels there).
- Use system Python 3.13; create the venv at `~/wan-pipeline/venv`.
- Never download model files without confirming with the user first (each is multi-GB).
- Never commit anything under `assets/`, `outputs/`, `workflows/*.json`, or any `*.safetensors`/`*.gguf`/`*.onnx`/`*.mp4`/`*.png`/`*.jpg` — `.gitignore` already covers them; do not override with `git add -f`.
- Do not start long-running processes (ComfyUI server, batch jobs) without telling the user the expected runtime first.

## Ordered task list

1. Run `bash setup.sh`. Stream output. If it fails on the driver check, stop and surface the message.
2. Activate the venv and run `python check_vram.py`. **Hard gate:** if device capability is not `(12, 0)` or the matmul fails, stop and tell the user to reinstall PyTorch from the cu128 nightly index — do not proceed.
3. Ask the user whether to download the five model files (~25–30 GB). If yes, run the five `huggingface-cli` commands from `README.md` sequentially. Skip any whose target file already exists.
4. Ask whether to install the optional sage attention (`pip install triton sageattention`). Recommend yes on Blackwell.
5. Verify the user has placed:
   - `assets/source/dancer.mp4` (the driving video)
   - at least one `assets/influencers/NN.png` (01..10)
   If missing, stop and ask the user to add them.
6. Verify `workflows/wan22_animate_16gb.json` exists. If not, point the user at `workflows/README.md` and stop — the agent cannot export the workflow itself (it's a manual step in the ComfyUI browser UI).
7. Start ComfyUI in a background terminal: `cd ~/wan-pipeline/ComfyUI && source ~/wan-pipeline/venv/bin/activate && python main.py --listen 0.0.0.0 --port 8188`. Wait for the "To see the GUI go to" line before continuing.
8. **Always run a single-clip smoke test first:** `python run_batch.py --workflow workflows/wan22_animate_16gb.json --source assets/source/dancer.mp4 --limit 1`. Estimated ~12 min. Show the user the resulting file in `outputs/` and ask for go/no-go before the full batch.
9. On user approval, run the full batch (drop `--limit 1`). Estimated ~1.5–2 hours.

## Troubleshooting cheatsheet

- **`no kernel image is available for execution on the device`** → wrong PyTorch index; reinstall from nightly cu128.
- **`CUDA out of memory` during VAE decode** → confirm workflow has `vae_decode_mode: tiled, tile_size 256` and `cpu_offload: sequential`; if still OOM, lower frames from 81/65 to 49.
- **`ConnectionRefusedError` from `run_batch.py`** → ComfyUI server isn't running; restart it per step 7.
- **`LoadImage` / `VHS_LoadVideo` node not found in workflow** → user exported the UI format instead of API format; re-export per `workflows/README.md` step 4.
- **Multiple `LoadImage` candidates detected by `run_batch.py`** → re-run with `--image-node-id <id>` using the IDs printed by the script.

## What the agent must NOT do

- Do not `pip install torch` from the default PyPI index.
- Do not edit the workflow JSON by hand to "fix" node IDs — use `run_batch.py`'s `--*-node-id` flags instead.
- Do not `rm -rf` the `~/wan-pipeline/` directory to "start fresh" without explicit user confirmation (it contains 25–30 GB of downloaded models).
- Do not push to git on the user's behalf.
