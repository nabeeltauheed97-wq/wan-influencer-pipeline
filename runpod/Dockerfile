# syntax=docker/dockerfile:1.6
#
# RunPod ComfyUI + Wan2.2-Animate image.
#
# Base: CUDA 12.8 runtime on Ubuntu 24.04. Ubuntu 24.04 ships Python 3.12,
# which is fully supported by the PyTorch nightly cu128 wheels we install
# below. The cuDNN runtime variant is used (cuDNN is required by torch
# nightly + sageattention/onnxruntime-gpu).
#
# Build context = repo root, e.g.:
#   docker build -f runpod/Dockerfile -t wan-influencer:latest .
#
# Layer ordering is optimized for cache reuse: heavy CUDA/torch/ComfyUI
# layers come first, then the (small, churn-heavy) repo source is copied
# last so editing Python files doesn't bust the multi-GB pip layers.

FROM nvidia/cuda:12.8.0-cudnn-runtime-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ---------------------------------------------------------------------------
# 1) System packages
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.12 \
        python3.12-venv \
        python3-pip \
        python3-dev \
        git \
        ffmpeg \
        build-essential \
        ca-certificates \
        curl \
        wget \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# 2) Python venv (isolated from system Python / PEP 668 lock)
# ---------------------------------------------------------------------------
RUN python3.12 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV=/opt/venv

RUN pip install --upgrade pip wheel

# ---------------------------------------------------------------------------
# 3) PyTorch nightly cu128 (Blackwell sm_120 + Ada/Ampere/Hopper supported)
# ---------------------------------------------------------------------------
RUN pip install --pre torch torchvision torchaudio \
        --index-url https://download.pytorch.org/whl/nightly/cu128

# ---------------------------------------------------------------------------
# 4) ComfyUI + its core requirements
# ---------------------------------------------------------------------------
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /opt/ComfyUI \
    && pip install -r /opt/ComfyUI/requirements.txt

# ---------------------------------------------------------------------------
# 5) Custom nodes + their requirements
#    NOTE: comfyui_controlnet_aux is REQUIRED for DWPreprocessor used by the
#          Wan2.2-Animate workflows.
# ---------------------------------------------------------------------------
RUN set -eux; \
    cd /opt/ComfyUI/custom_nodes; \
    for url in \
        https://github.com/kijai/ComfyUI-WanVideoWrapper \
        https://github.com/city96/ComfyUI-GGUF \
        https://github.com/kijai/ComfyUI-KJNodes \
        https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite \
        https://github.com/Fannovel16/ComfyUI-Frame-Interpolation \
        https://github.com/Fannovel16/comfyui_controlnet_aux \
    ; do \
        name="$(basename "$url")"; \
        git clone --depth 1 "$url" "$name"; \
    done; \
    for d in /opt/ComfyUI/custom_nodes/*/; do \
        if [ -f "$d/requirements.txt" ]; then \
            echo "Installing requirements for $d"; \
            pip install -r "$d/requirements.txt"; \
        fi; \
    done

# ---------------------------------------------------------------------------
# 6) Extras: sage-attention, triton, onnxruntime-gpu, boto3 (S3 sync)
# ---------------------------------------------------------------------------
RUN pip install triton sageattention onnxruntime-gpu boto3

# ---------------------------------------------------------------------------
# 7) Repo requirements (copy just the requirements file first so source-file
#    edits don't invalidate this pip layer)
# ---------------------------------------------------------------------------
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# ---------------------------------------------------------------------------
# 8) Model directory skeleton (matches setup.sh layout)
# ---------------------------------------------------------------------------
RUN mkdir -p \
        /opt/ComfyUI/models/diffusion_models \
        /opt/ComfyUI/models/vae \
        /opt/ComfyUI/models/text_encoders \
        /opt/ComfyUI/models/clip_vision \
        /opt/ComfyUI/models/onnx

# ---------------------------------------------------------------------------
# 9) Copy the rest of the repo last (cheap layer, busted by code changes)
# ---------------------------------------------------------------------------
COPY . /app/
RUN chmod +x /app/runpod/entrypoint.sh

# ---------------------------------------------------------------------------
# 10) Runtime config
# ---------------------------------------------------------------------------
ENV COMFY_ROOT=/opt/ComfyUI \
    REPO_ROOT=/app

EXPOSE 8188

ENTRYPOINT ["/app/runpod/entrypoint.sh"]
