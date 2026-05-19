#!/usr/bin/env bash
# RunPod ComfyUI + Wan2.2-Animate container entrypoint.
#
# Responsibilities:
#   1. Resolve env-var driven config (workflow, source, node IDs, S3, etc.)
#   2. Download Wan2.2-Animate weights via `hf download` (skippable)
#   3. Optionally pull /app/assets from S3
#   4. Start ComfyUI on 0.0.0.0:8188 in the background and wait for /
#   5. Run runpod/runpod_batch.py against the local ComfyUI server
#   6. Optionally push /app/outputs to S3
#   7. Tear down ComfyUI cleanly on exit
set -euo pipefail

echo "=========================================================================="
echo " RunPod ComfyUI Wan2.2-Animate entrypoint"
echo "=========================================================================="

COMFY_ROOT="${COMFY_ROOT:-/opt/ComfyUI}"
REPO_ROOT="${REPO_ROOT:-/app}"

# ---------------------------------------------------------------------------
# 1) Env / defaults
# ---------------------------------------------------------------------------
WORKFLOW="${WORKFLOW:-workflows/wan22_animate_16gb.json}"
SOURCE_VIDEO="${SOURCE_VIDEO:-assets/source/dancer.mp4}"
LIMIT="${LIMIT:-}"
ONLY="${ONLY:-}"
IMAGE_NODE_ID="${IMAGE_NODE_ID:-}"
VIDEO_NODE_ID="${VIDEO_NODE_ID:-}"
SAVE_NODE_ID="${SAVE_NODE_ID:-}"
S3_BUCKET="${S3_BUCKET:-}"
S3_PREFIX="${S3_PREFIX:-}"
SKIP_MODEL_DOWNLOAD="${SKIP_MODEL_DOWNLOAD:-0}"
COMFYUI_EXTRA_ARGS="${COMFYUI_EXTRA_ARGS:-}"
HF_TOKEN="${HF_TOKEN:-}"

if [[ -n "$HF_TOKEN" ]]; then
    export HUGGING_FACE_HUB_TOKEN="$HF_TOKEN"
fi

# Validate LIMIT (if set) is a positive int.
if [[ -n "$LIMIT" ]]; then
    if ! [[ "$LIMIT" =~ ^[1-9][0-9]*$ ]]; then
        echo "ERROR: LIMIT must be a positive integer, got: $LIMIT" >&2
        exit 1
    fi
fi

# S3 prefix path (with trailing slash if non-empty, else empty).
S3_PREFIX_PATH=""
if [[ -n "$S3_PREFIX" ]]; then
    # Strip leading/trailing slashes.
    _stripped="${S3_PREFIX#/}"
    _stripped="${_stripped%/}"
    if [[ -n "$_stripped" ]]; then
        S3_PREFIX_PATH="$_stripped"
    fi
fi

echo "[entrypoint] WORKFLOW=$WORKFLOW"
echo "[entrypoint] SOURCE_VIDEO=$SOURCE_VIDEO"
[[ -n "$LIMIT" ]] && echo "[entrypoint] LIMIT=$LIMIT"
[[ -n "$ONLY"  ]] && echo "[entrypoint] ONLY=$ONLY"
[[ -n "$IMAGE_NODE_ID" ]] && echo "[entrypoint] IMAGE_NODE_ID=$IMAGE_NODE_ID"
[[ -n "$VIDEO_NODE_ID" ]] && echo "[entrypoint] VIDEO_NODE_ID=$VIDEO_NODE_ID"
[[ -n "$SAVE_NODE_ID"  ]] && echo "[entrypoint] SAVE_NODE_ID=$SAVE_NODE_ID"
[[ -n "$S3_BUCKET"     ]] && echo "[entrypoint] S3_BUCKET=$S3_BUCKET (prefix='$S3_PREFIX_PATH')"
echo "[entrypoint] SKIP_MODEL_DOWNLOAD=$SKIP_MODEL_DOWNLOAD"
[[ -n "$COMFYUI_EXTRA_ARGS" ]] && echo "[entrypoint] COMFYUI_EXTRA_ARGS=$COMFYUI_EXTRA_ARGS"

COMFY_PID=""
cleanup() {
    if [[ -n "$COMFY_PID" ]]; then
        kill "$COMFY_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# 2) Model downloads (idempotent)
# ---------------------------------------------------------------------------
download_model() {
    # Args: <repo_id> <local_dir> <target_file_relative_to_local_dir> [<file_arg> ...]
    # The `hf download` invocation uses positional file args after the repo id.
    local repo_id="$1"; shift
    local local_dir="$1"; shift
    local target_rel="$1"; shift
    local target_path="$local_dir/$target_rel"

    if [[ -f "$target_path" ]]; then
        echo "  [skip] $target_path already exists"
        return 0
    fi
    mkdir -p "$local_dir"
    echo "  [pull] $repo_id -> $local_dir ($*)"
    hf download "$repo_id" "$@" --local-dir "$local_dir"
}

if [[ "$SKIP_MODEL_DOWNLOAD" != "1" ]]; then
    echo "[entrypoint] Downloading Wan2.2-Animate model weights"

    download_model \
        "QuantStack/Wan2.2-Animate-14B-GGUF" \
        "$COMFY_ROOT/models/diffusion_models" \
        "Wan2.2-Animate-14B-Q8_0.gguf" \
        "Wan2.2-Animate-14B-Q8_0.gguf"

    download_model \
        "Comfy-Org/Wan_2.2_ComfyUI_Repackaged" \
        "$COMFY_ROOT/models/vae" \
        "split_files/vae/wan_2.1_vae.safetensors" \
        "split_files/vae/wan_2.1_vae.safetensors"

    download_model \
        "Comfy-Org/Wan_2.2_ComfyUI_Repackaged" \
        "$COMFY_ROOT/models/text_encoders" \
        "split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors" \
        "split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors"

    # clip_vision_h actually lives in the 2.1 repo (lowercase 'r'). The 2.2
    # repackage shares CLIP-Vision encoder with 2.1 and Comfy-Org keeps it
    # only in the 2.1 repo; the 2.2 repo has no split_files/clip_vision dir.
    download_model \
        "Comfy-Org/Wan_2.1_ComfyUI_repackaged" \
        "$COMFY_ROOT/models/clip_vision" \
        "split_files/clip_vision/clip_vision_h.safetensors" \
        "split_files/clip_vision/clip_vision_h.safetensors"

    # DWPose: two files. Existence check on dw-ll_ucoco_384.onnx covers both
    # (yolox_l.onnx will be pulled together by the same hf download call).
    if [[ -f "$COMFY_ROOT/models/onnx/dw-ll_ucoco_384.onnx" && \
          -f "$COMFY_ROOT/models/onnx/yolox_l.onnx" ]]; then
        echo "  [skip] DWPose onnx files already exist"
    else
        mkdir -p "$COMFY_ROOT/models/onnx"
        echo "  [pull] yzd-v/DWPose -> $COMFY_ROOT/models/onnx"
        hf download yzd-v/DWPose dw-ll_ucoco_384.onnx yolox_l.onnx \
            --local-dir "$COMFY_ROOT/models/onnx"
    fi
else
    echo "[entrypoint] SKIP_MODEL_DOWNLOAD=1, not downloading model weights"
fi

# ---------------------------------------------------------------------------
# 3) Optional: pull assets from S3
# ---------------------------------------------------------------------------
if [[ -n "$S3_BUCKET" ]]; then
    if [[ -n "$S3_PREFIX_PATH" ]]; then
        _assets_prefix="$S3_PREFIX_PATH/assets"
    else
        _assets_prefix="assets"
    fi
    echo "[entrypoint] Syncing s3://$S3_BUCKET/$_assets_prefix/ -> $REPO_ROOT/assets/"
    mkdir -p "$REPO_ROOT/assets"
    python3 "$REPO_ROOT/runpod/s3_sync.py" down "$S3_BUCKET" "$_assets_prefix" "$REPO_ROOT/assets"
fi

# ---------------------------------------------------------------------------
# 4) Start ComfyUI (background) and wait for it to come up
# ---------------------------------------------------------------------------
echo "[entrypoint] Starting ComfyUI on 0.0.0.0:8188"
cd "$COMFY_ROOT"
# shellcheck disable=SC2086
python main.py --listen 0.0.0.0 --port 8188 $COMFYUI_EXTRA_ARGS &
COMFY_PID=$!
echo "[entrypoint] ComfyUI PID=$COMFY_PID"

echo "[entrypoint] Waiting for ComfyUI HTTP to be ready (max 5 min)"
ready=0
for attempt in $(seq 1 60); do
    if ! kill -0 "$COMFY_PID" 2>/dev/null; then
        echo "ERROR: ComfyUI process exited before becoming ready" >&2
        exit 1
    fi
    if curl -sf "http://127.0.0.1:8188/" >/dev/null 2>&1; then
        echo "[entrypoint] ComfyUI is up (attempt $attempt)"
        ready=1
        break
    fi
    sleep 5
done
if [[ "$ready" != "1" ]]; then
    echo "ERROR: ComfyUI did not become ready after 5 minutes" >&2
    kill "$COMFY_PID" 2>/dev/null || true
    exit 1
fi

# ---------------------------------------------------------------------------
# 5) Run the batch
# ---------------------------------------------------------------------------
cd "$REPO_ROOT"

batch_cmd=( python "$REPO_ROOT/runpod/runpod_batch.py"
            --workflow "$WORKFLOW"
            --source "$SOURCE_VIDEO"
            --host 127.0.0.1:8188 )

if [[ -n "$LIMIT" ]]; then
    batch_cmd+=( --limit "$LIMIT" )
fi
if [[ -n "$ONLY" ]]; then
    batch_cmd+=( --only "$ONLY" )
fi
if [[ -n "$IMAGE_NODE_ID" ]]; then
    batch_cmd+=( --image-node-id "$IMAGE_NODE_ID" )
fi
if [[ -n "$VIDEO_NODE_ID" ]]; then
    batch_cmd+=( --video-node-id "$VIDEO_NODE_ID" )
fi
if [[ -n "$SAVE_NODE_ID" ]]; then
    batch_cmd+=( --save-node-id "$SAVE_NODE_ID" )
fi

echo "[entrypoint] Running: ${batch_cmd[*]}"
set +e
"${batch_cmd[@]}"
batch_rc=$?
set -e
echo "[entrypoint] runpod_batch.py exit code: $batch_rc"

# ---------------------------------------------------------------------------
# 6) Optional: push outputs to S3 (run regardless of batch_rc so partial
#    results are still recoverable)
# ---------------------------------------------------------------------------
if [[ -n "$S3_BUCKET" ]]; then
    if [[ -n "$S3_PREFIX_PATH" ]]; then
        _outputs_prefix="$S3_PREFIX_PATH/outputs"
    else
        _outputs_prefix="outputs"
    fi
    echo "[entrypoint] Syncing $REPO_ROOT/outputs/ -> s3://$S3_BUCKET/$_outputs_prefix/"
    if [[ -d "$REPO_ROOT/outputs" ]]; then
        python3 "$REPO_ROOT/runpod/s3_sync.py" up "$REPO_ROOT/outputs" "$S3_BUCKET" "$_outputs_prefix" || \
            echo "WARNING: outputs upload failed (continuing)" >&2
    else
        echo "[entrypoint] No $REPO_ROOT/outputs directory, nothing to upload"
    fi
fi

# ---------------------------------------------------------------------------
# 7) Clean shutdown (trap also covers abnormal exits)
# ---------------------------------------------------------------------------
echo "[entrypoint] Stopping ComfyUI (PID=$COMFY_PID)"
kill "$COMFY_PID" 2>/dev/null || true
COMFY_PID=""

exit "$batch_rc"
