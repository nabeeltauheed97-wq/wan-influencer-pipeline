# Claude Opus 4.7 Prompt: End-to-End RunPod ComfyUI Wan Animate Pipeline

**Instructions for Claude:**
You are an expert in AI video generation, cloud GPU deployment, and workflow automation. I have no coding experience and only use Claude to generate and run code. I have access to AI tokens and can approve all permissions. Your job is to generate everything needed for an end-to-end, production-grade ComfyUI + Wan Animate pipeline on RunPod (or similar cloud GPU), with no manual coding required.



- **No coding knowledge required**: All scripts, configs, and instructions must be copy-paste ready.
- **End-to-end**: From cloud setup, model/assets download, workflow execution, to output retrieval.
- **Cloud GPU**: Use RunPod or similar (A100 80GB recommended; optimize for this hardware).
- **ComfyUI + Wan Animate (or LTX2/AnimateDiffXL if preferred)**: Use the best available model for your needs.
- **Chunked long video support**: Handles >20s source videos by chaining multiple `WanAnimateToVideo` nodes.
- **Automation**: All steps automated (Docker, scripts, workflow, asset handling, output upload).
- **Cloud storage**: Use S3/GCS or persistent volume for assets and outputs.
- **No manual path editing**: All paths and configs must work out-of-the-box.
- **Documentation**: Clear, step-by-step usage for non-coders.

## Prompt

---

You are an expert in AI video pipelines and cloud automation. I have no coding experience. Please generate everything needed for an end-to-end, production-grade ComfyUI + Wan Animate (or LTX2/AnimateDiffXL if better) pipeline on RunPod (or similar cloud GPU), with the following requirements:



### 2. Containerization & Environment
- Write a Dockerfile that:
  - Installs Python 3.13+ and all system dependencies for ComfyUI and custom nodes.
  - Installs PyTorch nightly cu128 (not stable).
  - Installs ComfyUI and these custom nodes: ComfyUI-WanVideoWrapper, ComfyUI-GGUF, ComfyUI-KJNodes, ComfyUI-VideoHelperSuite, ComfyUI-Frame-Interpolation, comfyui_controlnet_aux.
  - Installs all required Python packages (triton, sageattention, onnxruntime-gpu, etc.).
  - Optionally, pre-downloads model files or provides a script to do so at container start.
  - Exposes port 8188 for ComfyUI.

### 3. Cloud Storage Integration
- Show how to mount or sync assets (source videos, influencer images) and outputs using S3/GCS or a persistent volume.
- Ensure workflow JSON and model paths are compatible with this storage layout.

### 4. Workflow Improvements
- Generate a ComfyUI API-format workflow JSON that:
  - Uses chunked video generation: splits long source videos into N chunks (e.g., 65 frames each), chains `WanAnimateToVideo` nodes, and combines outputs for full-length video.
  - Uses DWPose for pose extraction, with ONNX weights correctly mapped.
  - Supports higher quantization (Q4_K_M or better) if VRAM allows.
  - Optionally, adds post-processing (frame interpolation, upscaling).
  - Is parameterized for easy adjustment of resolution, frame count, and steps.

### 5. Automation Script
- Write a Python or bash script that:
  - Downloads any missing models/assets at startup.
  - Starts ComfyUI in the background.
  - Submits jobs via the ComfyUI API (using the improved workflow).
  - Monitors job status and uploads outputs to cloud storage.

### 6. RunPod/Cloud GPU Guidance
- Recommend optimal RunPod instance types for the selected model (A100 80GB required).
- Provide instructions for setting environment variables, mounting storage, and exposing ports.
- Suggest best practices for monitoring, error recovery, and scaling.
- **Estimate the cost and runtime for a smoke test** (single influencer, 65 frames, 576x1024, 25 steps) on A100 80GB, using current RunPod pricing.

### 7. Documentation
- Include clear usage instructions for launching the container, submitting jobs, and retrieving outputs.
- Document all environment variables and configuration options.

### 8. (Optional) Model Upgrades
- If newer/better models (Wan3, AnimateDiffXL, etc.) are available and compatible, describe how to swap them in.

**Input assets:**
- One source video (e.g., `assets/source/dancer.mp4`)
- N influencer images (e.g., `assets/influencers/01.png` ... `10.png`)

**Output:**
- N full-length portrait videos, one per influencer, matching the source video duration.

**Deliverables:**
- Dockerfile
- Improved workflow JSON (API format, chunked)
- Automation script
- Usage documentation

---

**See also:**
If you want to optimize or modernize your workflow JSON, use the included prompt in [Claude_Workflow_Improvement_Prompt.md](Claude_Workflow_Improvement_Prompt.md) for easy, non-coder-friendly workflow upgrades.

---

**Instructions:**
Generate all code, config, and documentation needed for a non-coder to deploy and run this pipeline on RunPod, with all improvements and automation as described. All steps must be copy-paste ready and require only permission approval, not coding knowledge. Use web search to ensure the model and workflow are state-of-the-art as of May 2026, and provide a cost/time estimate for a smoke test on A100 80GB.
