#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================================="
echo " Wan 2.2 Animate Influencer Pipeline — Arch Linux WSL2 setup"
echo "--------------------------------------------------------------------------"
echo " This script will:"
echo "   - Install system deps (pacman)"
echo "   - Verify NVIDIA driver"
echo "   - Clone ComfyUI into ~/wan-pipeline/ComfyUI"
echo "   - Create a Python venv at ~/wan-pipeline/venv"
echo "   - Install repo requirements + PyTorch nightly cu128 (Blackwell sm_120)"
echo "   - Install ComfyUI + custom node requirements"
echo "   - Create model subdirectories"
echo "   - PRINT (not run) the hf download commands"
echo "=========================================================================="

sudo pacman -S --needed --noconfirm git python python-pip python-virtualenv ffmpeg base-devel

if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "ERROR: nvidia-smi not found. Install the NVIDIA driver in Windows (host)" >&2
    echo "and ensure WSL2 GPU passthrough is enabled before re-running this script." >&2
    exit 1
fi

echo "nvidia-smi found. Driver info:"
nvidia-smi
DRIVER_VERSION="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -n1 | tr -d ' ')"
echo "Detected driver version: ${DRIVER_VERSION}"
DRIVER_MAJOR="${DRIVER_VERSION%%.*}"
if [[ "${DRIVER_MAJOR}" -lt 570 ]]; then
    echo "WARNING: Driver major version ${DRIVER_MAJOR} < 570."
    echo "         Blackwell (RTX 5080, sm_120) requires driver >= 570 on Linux."
    echo "         Continuing, but expect 'no kernel image' errors at runtime."
fi

PIPE_ROOT="$HOME/wan-pipeline"
mkdir -p "$PIPE_ROOT"

if [[ -d "$PIPE_ROOT/ComfyUI" ]]; then
    echo "ComfyUI already cloned, skipping"
else
    git clone https://github.com/comfyanonymous/ComfyUI.git "$PIPE_ROOT/ComfyUI"
fi

if [[ -f "$PIPE_ROOT/venv/bin/pip" ]]; then
    echo "venv already exists at $PIPE_ROOT/venv, skipping creation"
else
    python -m venv "$PIPE_ROOT/venv"
fi

VENV_PIP="$PIPE_ROOT/venv/bin/pip"

"$VENV_PIP" install --upgrade pip wheel

"$VENV_PIP" install -r requirements.txt

"$VENV_PIP" install --pre torch torchvision torchaudio \
  --index-url https://download.pytorch.org/whl/nightly/cu128

"$VENV_PIP" install -r "$PIPE_ROOT/ComfyUI/requirements.txt"

CUSTOM_NODES=(
    "https://github.com/kijai/ComfyUI-WanVideoWrapper"
    "https://github.com/city96/ComfyUI-GGUF"
    "https://github.com/kijai/ComfyUI-KJNodes"
    "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite"
    "https://github.com/Fannovel16/ComfyUI-Frame-Interpolation"
    "https://github.com/Fannovel16/comfyui_controlnet_aux"
)

for url in "${CUSTOM_NODES[@]}"; do
    name="$(basename "$url")"
    target="$PIPE_ROOT/ComfyUI/custom_nodes/$name"
    if [[ -d "$target" ]]; then
        echo "Custom node $name already cloned, skipping"
    else
        git clone "$url" "$target"
    fi
done

for url in "${CUSTOM_NODES[@]}"; do
    name="$(basename "$url")"
    req="$PIPE_ROOT/ComfyUI/custom_nodes/$name/requirements.txt"
    if [[ -f "$req" ]]; then
        echo "Installing requirements for $name"
        "$VENV_PIP" install -r "$req"
    fi
done

mkdir -p "$PIPE_ROOT/ComfyUI/models/diffusion_models"
mkdir -p "$PIPE_ROOT/ComfyUI/models/vae"
mkdir -p "$PIPE_ROOT/ComfyUI/models/text_encoders"
mkdir -p "$PIPE_ROOT/ComfyUI/models/clip_vision"
mkdir -p "$PIPE_ROOT/ComfyUI/models/onnx"

cat <<'EOF'

==========================================================================
 Model downloads — RUN THESE MANUALLY (total ~25-30 GB, not auto-run)
==========================================================================

hf download QuantStack/Wan2.2-Animate-14B-GGUF Wan2.2-Animate-14B-Q8_0.gguf \
  --local-dir ~/wan-pipeline/ComfyUI/models/diffusion_models

hf download Comfy-Org/Wan_2.2_ComfyUI_Repackaged \
  split_files/vae/wan_2.1_vae.safetensors \
  --local-dir ~/wan-pipeline/ComfyUI/models/vae

hf download Comfy-Org/Wan_2.2_ComfyUI_Repackaged \
  split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors \
  --local-dir ~/wan-pipeline/ComfyUI/models/text_encoders

hf download Comfy-Org/Wan_2.1_ComfyUI_repackaged \
  split_files/clip_vision/clip_vision_h.safetensors \
  --local-dir ~/wan-pipeline/ComfyUI/models/clip_vision

hf download yzd-v/DWPose dw-ll_ucoco_384.onnx yolox_l.onnx \
  --local-dir ~/wan-pipeline/ComfyUI/models/onnx

EOF

cat <<'EOF'
==========================================================================
 Next steps
==========================================================================
  1) source ~/wan-pipeline/venv/bin/activate
  2) python check_vram.py   (must report capability (12, 0) and successful matmul)
  3) Run the five hf download commands above
  4) Read workflows/README.md to export the workflow JSON in API Format
  5) python run_batch.py --workflow workflows/wan22_animate_16gb.json --source assets/source/dancer.mp4 --limit 1   (smoke test)
  6) If smoke test looks good: drop --limit 1 to run the full batch of 10.
==========================================================================
EOF
