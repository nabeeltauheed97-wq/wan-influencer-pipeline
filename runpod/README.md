# RunPod deployment

Production-grade cloud GPU deployment of `wan-influencer-pipeline` on **RunPod** (or any CUDA 12.8 cloud GPU host). Containerized, env-var driven, with optional S3 sync for inputs and outputs.

This directory holds:

| File | Purpose |
|---|---|
| `Dockerfile` | Builds the container image (CUDA 12.8 + PyTorch nightly cu128 + ComfyUI + 6 custom nodes + Wan 2.2-Animate runtime deps). |
| `entrypoint.sh` | Container start: download models → optional S3 asset pull → start ComfyUI → run the batch → optional S3 output push. |
| `runpod_batch.py` | Multi-patch ComfyUI batch runner. Same CLI as the repo's root `run_batch.py` but tolerates chunked workflows (multiple `LoadImage` / `VHS_LoadVideo` nodes — see `workflows/wan22_animate_chunked.json`). |
| `s3_sync.py` | Tiny boto3 helper for `down BUCKET PREFIX LOCAL_DIR` / `up LOCAL_DIR BUCKET PREFIX`. |

## When to use this vs. running locally

- **Local** (`bash setup.sh` on a 16 GB+ RTX card / WSL2 Arch): use the root `run_batch.py` against `workflows/wan22_animate_16gb.json`. ~12 min/clip on RTX 5080.
- **RunPod** (A100 80GB recommended): build this Dockerfile, push it, deploy on RunPod. ~4-6 min/clip on A100 with sdpa; ~3-4 min with sageattn. Headroom for the chunked workflow (longer videos) that does not fit comfortably on a 5080.

## Build the image

```bash
# From the repo root (build context must be the repo root so .gitignored
# assets/, outputs/, and workflows/*.json are NOT shipped in the image).
docker build -t wan-influencer-pipeline:latest -f runpod/Dockerfile .
```

Push to your registry (Docker Hub, GHCR, ECR — whichever RunPod will pull from):

```bash
docker tag wan-influencer-pipeline:latest YOUR_REGISTRY/wan-influencer-pipeline:latest
docker push YOUR_REGISTRY/wan-influencer-pipeline:latest
```

## Deploy on RunPod

1. **Create a Pod** → choose **GPU Cloud** → filter to **A100 80GB**. Either Secure Cloud or Community Cloud works; Community is cheaper.
2. **Image**: paste `YOUR_REGISTRY/wan-influencer-pipeline:latest`.
3. **Volume mount**: attach a Network Volume at `/opt/ComfyUI/models` (so the ~25-30 GB model download survives container restarts). Recommended size: 60 GB.
4. **Expose ports**: TCP 8188 (ComfyUI UI — optional, for debugging).
5. **Environment variables** — see the table below.
6. **Start the pod**. First boot downloads models (~30 min for ~25-30 GB at typical RunPod ingress); subsequent boots are seconds.

### Required / optional env vars

| Var | Default | Notes |
|---|---|---|
| `WORKFLOW` | `workflows/wan22_animate_16gb.json` | Path inside `/app` to the ComfyUI workflow JSON. Use `workflows/wan22_animate_chunked.json` for ~16 s output via 4× 65-frame chunks. |
| `SOURCE_VIDEO` | `assets/source/dancer.mp4` | Path inside `/app` to the driving video. Provided via volume mount or S3 sync. |
| `LIMIT` | _(unset)_ | Positive int. If set, run only the first N influencers (use `LIMIT=1` for a smoke test). Mutually exclusive with `ONLY`. |
| `ONLY` | _(unset)_ | Influencer id (e.g. `influencer_03`). Mutually exclusive with `LIMIT`. |
| `IMAGE_NODE_ID` / `VIDEO_NODE_ID` / `SAVE_NODE_ID` | _(unset)_ | Pin a specific node id if auto-detection picks the wrong one. |
| `SKIP_MODEL_DOWNLOAD` | `0` | Set to `1` when models are already on the mounted volume — saves a startup `hf download` round-trip. |
| `HF_TOKEN` | _(unset)_ | Set if any HuggingFace repo you depend on is gated. |
| `S3_BUCKET` | _(unset)_ | If set, sync `s3://$S3_BUCKET/[S3_PREFIX/]assets/` → `/app/assets/` on start and `/app/outputs/` → `s3://$S3_BUCKET/[S3_PREFIX/]outputs/` on completion. |
| `S3_PREFIX` | _(unset)_ | Sub-prefix inside the bucket, e.g. `runs/2026-05-19`. |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_DEFAULT_REGION` | _(unset)_ | Standard boto3 credentials. Use an IAM user with `s3:GetObject` + `s3:PutObject` + `s3:ListBucket` scoped to your bucket. |
| `COMFYUI_EXTRA_ARGS` | _(unset)_ | Extra args to `python main.py`. Useful: `--use-sage-attention` (with sageattention installed by the Dockerfile). |

### Two run modes

**Single-chunk smoke test** (default workflow, single influencer, ~5 min on A100):

```
WORKFLOW=workflows/wan22_animate_16gb.json
LIMIT=1
```

**Full chunked batch** (~16 s output × 10 influencers):

```
WORKFLOW=workflows/wan22_animate_chunked.json
```

## Storage layout

The Dockerfile copies the repo to `/app`. ComfyUI lives at `/opt/ComfyUI`. Mount a Network Volume at `/opt/ComfyUI/models` so the ~25-30 GB of weights are not re-downloaded on every pod restart.

If you use S3:
- Put your inputs at `s3://YOUR_BUCKET/[PREFIX/]assets/source/dancer.mp4` and `s3://YOUR_BUCKET/[PREFIX/]assets/influencers/{01..10}.png`.
- Outputs land at `s3://YOUR_BUCKET/[PREFIX/]outputs/`.

If you skip S3, mount a Network Volume at `/app/assets` and `/app/outputs` instead, and upload your files via RunPod's file browser or `scp`.

## Cost & time estimate (smoke test)

A single-influencer / 65-frame / 576×1024 / 25-step run on A100 80GB:

| Phase | Estimated time |
|---|---|
| Cold start: container pull (~12 GB) + model download (~25-30 GB) | 25-45 min |
| Warm start (volume cache): container start + ComfyUI boot | ~1-2 min |
| First sampler step (Triton JIT cache warmup) | 1-3 min |
| Per-clip sampler + decode (with sdpa) | ~4-6 min |
| Per-clip sampler + decode (with sageattn, `COMFYUI_EXTRA_ARGS=--use-sage-attention`) | ~3-4 min |

**RunPod A100 80GB pricing (rough — verify on the RunPod console before launching):**

| Tier | $/hr (approx.) |
|---|---|
| Community Cloud | ~$1.89/hr |
| Secure Cloud | ~$2.89/hr |

Cold-start smoke test (1 clip, sdpa): ~30-50 min wall time → ~**$1.00-1.60** on Community Cloud. Subsequent warm runs amortize the model-download cost.

Full chunked batch (10 influencers × 4 chunks each = 40 sampler runs, ~4 min each on A100 sdpa, plus RIFE interpolation overhead): ~3-4 hours → ~**$6-12** on Community Cloud. Set `COMFYUI_EXTRA_ARGS=--use-sage-attention` to cut this by ~30%.

Live pricing changes; always check https://www.runpod.io/pricing before committing to a multi-hour run.

## Monitoring & error recovery

- ComfyUI logs stream to the pod's stdout (visible in the RunPod console). Look for `to_torch` warnings, `RuntimeError: no kernel image` (wrong CUDA build), or `CUDA out of memory` (drop frame count from 65 to 49 in the workflow).
- `runpod_batch.py` polls `/history/{prompt_id}` every 10 s and prints `✓ influencer_NN done` per completion.
- If the batch crashes mid-run, `entrypoint.sh` still attempts the S3 output upload — partial results are recoverable.
- If ComfyUI fails to come up within 5 minutes, the entrypoint exits with code 1.

## Swapping in a different model

The workflow JSON references `Wan2.2-Animate-14B-Q8_0.gguf` via `UnetLoaderGGUF`. To use a smaller / faster quantization (e.g. Q4_K_M for ~50% VRAM and ~30% speed), download the alternate file:

```bash
hf download QuantStack/Wan2.2-Animate-14B-GGUF Wan2.2-Animate-14B-Q4_K_M.gguf \
  --local-dir /opt/ComfyUI/models/diffusion_models
```

…and edit the workflow JSON's node `1` to point at the new filename. Note: Q4 will hit lower quality; use Q8 unless you're VRAM-constrained.

To swap the entire model architecture (e.g. AnimateDiffXL, future Wan3): replace the `UnetLoaderGGUF` node and surrounding wiring per that model's reference workflow on the ComfyUI-Manager template list. The runpod_batch.py multi-patch logic is workflow-agnostic — it patches by `class_type`, so any workflow with `LoadImage` / `VHS_LoadVideo` / `VHS_VideoCombine` works.

## A/B testing Wan 2.2 vs LTX-2.3

This repo ships **two parallel container tracks** built from the same CI workflow. Both use the same `runpod_batch.py` multi-patch runner, the same S3 sync layer, the same `INFLUENCERS` list, and the same `LIMIT` / `ONLY` / `SOURCE_VIDEO` env vars — only the Dockerfile, entrypoint, and workflow JSON differ. Pick one, change the image tag on the RunPod pod, and the rest of the deploy stays identical.

### Image tags

Replace `OWNER` with the lowercased GitHub owner (e.g. `nabeeltauheed97-wq`):

| Track | Image tag | Default workflow | Built from |
|---|---|---|---|
| Wan 2.2-Animate (14B) | `ghcr.io/OWNER/wan-influencer-pipeline:wan22` *(or `:latest`)* | `workflows/wan22_animate_16gb.json` | `runpod/Dockerfile` + `runpod/entrypoint.sh` |
| LTX-2.3 (22B FP8 dev) | `ghcr.io/OWNER/wan-influencer-pipeline:ltx23` | `workflows/ltx23_pose.json` | `runpod/Dockerfile.ltx23` + `runpod/entrypoint.ltx23.sh` |

The `:latest` tag is **pinned to the Wan 2.2 build** so existing pod references and the deploy instructions above don't break. New deployments should pin an explicit `:wan22` or `:ltx23` tag.

### Switching tracks on RunPod

Spin up two pods (one per track) with the same network volume mounted at `/opt/ComfyUI/models` and the same S3 inputs/outputs prefix. Recommended env vars per track:

**Wan 2.2 pod**
```
WORKFLOW=workflows/wan22_animate_16gb.json
SOURCE_VIDEO=assets/source/dancer.mp4
LIMIT=1
COMFYUI_EXTRA_ARGS=--use-sage-attention
S3_BUCKET=...
S3_PREFIX=runs/2026-05-19/wan22
```

**LTX-2.3 pod**
```
WORKFLOW=workflows/ltx23_pose.json
SOURCE_VIDEO=assets/source/dancer.mp4
LIMIT=1
COMFYUI_EXTRA_ARGS=--use-sage-attention
S3_BUCKET=...
S3_PREFIX=runs/2026-05-19/ltx23
```

Different `S3_PREFIX` per pod keeps the two output sets cleanly separated for side-by-side review.

### Per-clip cost on A100 80GB Community ($1.19/hr)

These are the per-influencer smoke-test costs for one ~4 s output at 25 sampler steps, with sage-attention enabled. Cold-start / model-download is amortized once per pod lifetime against the mounted network volume.

| Track | Resolution | Frames | Sampler time / clip | Cost / clip @ $1.19/hr |
|---|---|---|---|---|
| Wan 2.2-Animate Q8 | 576×1024 | 65 @ 16 fps | ~3-4 min | **~$0.07-0.08** |
| LTX-2.3 22B FP8 dev | 736×1280 | 97 @ 24 fps | ~5-7 min | **~$0.10-0.14** |

Full 10-influencer batches scale linearly. LTX renders ~50% more frames at ~70% higher pixel count, so the per-second-of-output cost is closer than the raw per-clip numbers suggest. Adjust workflow `length` / `width` / `height` to normalize.

### Strategic differences

- **Wan 2.2-Animate** — purpose-built for pose-driven character animation. 14B parameters, Q8 GGUF fits comfortably in 16 GB VRAM. Uses `WanAnimateToVideo` (built-in pose + reference image conditioning), DWPose stick figures, separate VAE / CLIP / CLIP-Vision. Mature, well-tested workflow. **No native audio.**
- **LTX-2.3** — general-purpose video diffusion at 22B parameters, FP8-quantized for a ~22 GB checkpoint. **Native audio generation** (HiFi-GAN vocoder per LTX docs), built-in VAE, IC-LoRA Union Control adapter handles pose / depth / canny / motion-track conditioning from a single LoRA. Supports up to 4K with the spatial upscaler chain. Newer, fewer pose-tuned reference workflows in the wild.

The same `runpod_batch.py` drives both — it auto-detects `LoadImage` / `VHS_LoadVideo` / `VHS_VideoCombine` and patches every match, so neither workflow needs override flags for the smoke test.

### Known assumptions in `workflows/ltx23_pose.json`

A few node-input keys in the LTX workflow were inferred from ComfyUI conventions and cross-referenced against `ComfyUI-LTXVideo/example_workflows/2.3/LTX-2.3_ICLoRA_Union_Control_Distilled.json`, but the Lightricks docs don't enumerate every input key:

- `LTXAVTextEncoderLoader.encoder_path` — assumed to take the folder name under `models/text_encoders/`. Verify by running the workflow once; if it errors, check the loader's actual input key with `curl http://127.0.0.1:8188/object_info | jq '.LTXAVTextEncoderLoader'` from inside the pod.
- `LTXICLoRALoaderModelOnly.lora_name` / `strength_model` — standard ComfyUI LoRA loader convention.
- `LTXAddVideoICLoRAGuide.guide_type` set to `"pose"` to indicate the IC-LoRA Union Control branch. If the node expects an integer enum or different string, adjust.
- Audio passthrough is **not wired** in the smoke workflow: `VHS_LoadVideo` does not emit an audio tensor and `VHS_VideoCombine`'s audio input is left empty. To enable LTX's native audio generation or driving-video audio passthrough, swap to LTX-native `LoadVideo` + `GetVideoComponents` + `CreateVideo` + `SaveVideo` and add `SaveVideo` to the `SAVE_CLASSES` set in `runpod/runpod_batch.py`.

The smoke test is intentionally "fair" with the Wan track: same single ~4 s output, same reference image, same driving video, same multi-patch wiring through `runpod_batch.py`.
