# Workflows

This directory holds the ComfyUI workflow JSON used by `run_batch.py`. The workflow must be exported in **API Format**, not the UI format. The batch script reads the dict-of-nodes shape.

1. **Start ComfyUI**

   ```bash
   source ~/wan-pipeline/venv/bin/activate
   cd ~/wan-pipeline/ComfyUI
   python main.py --listen 0.0.0.0 --port 8188
   ```

   On WSL2, opening `http://localhost:8188` from the Windows browser works out of the box thanks to automatic port forwarding.

2. **Load the template** — In the browser, go to **Workflows → Templates → search "Wan 2.2 animate"** and load it.

3. **Apply these node settings for 16 GB VRAM on a 5080:**
   - `cpu_offload`: **sequential**
   - `attention_mode`: **sdpa** (or **sageattn** if you ran the optional sage-attention install — ~30% faster)
   - `vae_decode_mode`: **tiled**, `tile_size` 256
   - resolution: **576×1024**
   - frames: **65** (start here; bump to 81 only if VRAM headroom is comfortable — 81 is right on the edge with Q8 14B)
   - steps: **25**

4. **Save the workflow in "API Format"** — Settings → enable **Dev Mode** → a "Save (API Format)" entry appears in the menu. Save it as `workflows/wan22_animate_16gb.json`. The batch script needs API format, not the UI format.

5. **First run is slow** — model load + Triton JIT cache warmup, several minutes before the first sampler step. Subsequent runs are much faster.

6. **Run the batch**

   ```bash
   python run_batch.py --workflow workflows/wan22_animate_16gb.json --source assets/source/dancer.mp4
   ```

   Add `--limit 1` for a single-clip smoke test (~12 min) before committing to the full ~2-hour batch.
