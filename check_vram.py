#!/usr/bin/env python3
import sys
import torch

NIGHTLY_LINE = (
    'pip install --pre torch torchvision torchaudio '
    '--index-url https://download.pytorch.org/whl/nightly/cu128'
)

print(f"torch.__version__ = {torch.__version__}")
print(f"torch.version.cuda = {torch.version.cuda}")

if not torch.cuda.is_available():
    print("ERROR: torch.cuda.is_available() is False.")
    print("       PyTorch cannot see the GPU. Re-install PyTorch nightly cu128:")
    print(f"       {NIGHTLY_LINE}")
    print("       (see setup.sh — the line under step 10).")
    sys.exit(1)

print(f"Device name: {torch.cuda.get_device_name(0)}")

cap = torch.cuda.get_device_capability(0)
print(f"Device capability: {cap}")
if cap != (12, 0):
    print("WARNING: Expected compute capability (12, 0) for RTX 5080 Blackwell (sm_120).")
    print("         PyTorch was likely installed from the wrong index.")
    print("         Reinstall PyTorch nightly cu128 with:")
    print(f"         {NIGHTLY_LINE}")

free_bytes, total_bytes = torch.cuda.mem_get_info()
total_gb = total_bytes / (1024 ** 3)
free_gb = free_bytes / (1024 ** 3)
print(f"Total VRAM: {total_gb:.2f} GB")
print(f"Free VRAM:  {free_gb:.2f} GB")
if total_gb < 14:
    print("WARNING: Total VRAM < 14 GB. Wan 2.2 Animate 14B Q8 GGUF expects ~16 GB.")

try:
    a = torch.randn(1024, 1024, device="cuda")
    b = torch.randn(1024, 1024, device="cuda")
    c = a @ b
    torch.cuda.synchronize()
except RuntimeError as e:
    msg = str(e)
    if "no kernel image" in msg.lower():
        print("ERROR: CUDA matmul failed with 'no kernel image' — your PyTorch build")
        print("       does not include sm_120 (Blackwell) kernels.")
        print("       Reinstall PyTorch nightly cu128:")
        print(f"       {NIGHTLY_LINE}")
        sys.exit(1)
    raise

print("CUDA matmul OK")
