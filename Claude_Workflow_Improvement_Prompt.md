# Claude Opus 4.7 Prompt: Improve My ComfyUI Workflow JSON

**Instructions for Claude:**
You are an expert in ComfyUI, AI video pipelines, and workflow automation. I have a working ComfyUI workflow JSON (attached below) for Wan2.2-Animate, but I want you to improve it for best quality, efficiency, and ease of use. I do not know how to use the ComfyUI UI or edit workflows by hand. I want to run everything with a single terminal command or prompt, with no manual editing or UI steps.

## What to do
- Analyze the attached workflow JSON and explain any issues or bottlenecks.
- Improve the workflow for:
  - Full-length video generation (handle long source videos by chunking and chaining as needed)
  - Best possible quality for my GPU/VRAM (suggest quantization, resolution, steps, etc.)
  - Automation: make it so I can run the improved workflow with a single command (no UI, no manual path edits)
  - Add any recommended post-processing (frame interpolation, upscaling, etc.)
  - Make all paths, node IDs, and parameters robust for batch runs
- Output ONLY the improved workflow JSON (API format), ready to use with ComfyUI/run_batch.py, and a short summary of what changed and why.
- If any new models or nodes are needed, add download/install instructions.
- Make sure the improved workflow is copy-paste ready and will run end-to-end with a single terminal command, with no UI steps.

## My current workflow JSON

```json
[PASTE THE CONTENTS OF wan22_animate_16gb.json HERE]
```

---

**Instructions:**
- Output only the improved workflow JSON and a short summary of changes.
- All steps must be copy-paste ready for a non-coder.
- If you need to split the video into chunks, do so automatically in the workflow.
- If you add new nodes or models, give clear install/download instructions.
- Do not require any manual UI or JSON editing.
