#!/usr/bin/env python3
"""
RunPod / cloud variant of run_batch.py.

Differences from the top-level run_batch.py:
  - Multi-patch: when a workflow contains MULTIPLE nodes of the same role
    (e.g. four VHS_LoadVideo nodes in workflows/wan22_animate_chunked.json),
    every matching node is patched with the same value. The top-level
    run_batch.py errors out on ambiguity by design; this script accepts it
    because chunked workflows are deliberately ambiguous.
  - Override flags (--image-node-id / --video-node-id / --save-node-id) still
    pin a specific node when given, exactly like run_batch.py.
"""
import argparse
import copy
import json
import sys
import time
import uuid

import requests

INFLUENCERS = [
    {"id": f"influencer_{i:02d}", "image": f"assets/influencers/{i:02d}.png"}
    for i in range(1, 11)
]

IMAGE_CLASSES = {"LoadImage"}
VIDEO_CLASSES = {"VHS_LoadVideo", "LoadVideo"}
SAVE_CLASSES = {"VHS_VideoCombine", "SaveAnimatedWEBP", "SaveImage"}


def find_nodes(wf, class_types, override, role):
    if override is not None:
        return [str(override)]
    matches = [
        node_id
        for node_id, node in wf.items()
        if isinstance(node, dict) and node.get("class_type") in class_types
    ]
    if not matches:
        print(
            f"ERROR: Could not auto-detect any {role} node. "
            f"Looked for class_type in {sorted(class_types)}."
        )
        sys.exit(1)
    return matches


def main():
    parser = argparse.ArgumentParser(
        description="Multi-patch ComfyUI batch runner for single- or chunked-workflow runs."
    )
    parser.add_argument("--workflow", required=True, type=str)
    parser.add_argument("--source", required=True, type=str)
    parser.add_argument("--host", default="127.0.0.1:8188", type=str)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--limit", type=int, default=None)
    group.add_argument("--only", type=str, default=None)
    parser.add_argument("--image-node-id", type=int, default=None)
    parser.add_argument("--video-node-id", type=int, default=None)
    parser.add_argument("--save-node-id", type=int, default=None)
    args = parser.parse_args()

    with open(args.workflow, "r") as f:
        workflow = json.load(f)

    image_ids = find_nodes(workflow, IMAGE_CLASSES, args.image_node_id, "reference image")
    video_ids = find_nodes(workflow, VIDEO_CLASSES, args.video_node_id, "source video")
    save_ids = find_nodes(workflow, SAVE_CLASSES, args.save_node_id, "output save")

    print(f"[runpod_batch] image nodes: {image_ids}")
    print(f"[runpod_batch] video nodes: {video_ids}")
    print(f"[runpod_batch] save nodes:  {save_ids}")

    if args.only is not None:
        effective = [inf for inf in INFLUENCERS if inf["id"] == args.only]
        if not effective:
            print(f"ERROR: --only {args.only!r} did not match any influencer id.")
            print("Valid ids:")
            for inf in INFLUENCERS:
                print(f"  {inf['id']}")
            sys.exit(1)
    elif args.limit is not None:
        if args.limit < 1:
            print("ERROR: --limit must be >= 1.")
            sys.exit(1)
        effective = INFLUENCERS[: args.limit]
    else:
        effective = list(INFLUENCERS)

    n = len(effective)
    print(
        f"Queueing {n} job(s). Estimated total time: ~{n*12} minutes "
        f"(~12 min/clip on RTX 5080 @ 576x1024 portrait, 65 frames, 25 steps, "
        f"Q8 GGUF, sdpa attention)."
    )

    queued = []
    for inf in effective:
        wf_copy = copy.deepcopy(workflow)
        for nid in image_ids:
            wf_copy[nid]["inputs"]["image"] = inf["image"]
        for nid in video_ids:
            wf_copy[nid]["inputs"]["video"] = args.source
        for nid in save_ids:
            wf_copy[nid]["inputs"]["filename_prefix"] = inf["id"]

        payload = {"prompt": wf_copy, "client_id": uuid.uuid4().hex}
        try:
            resp = requests.post(f"http://{args.host}/prompt", json=payload)
        except (ConnectionRefusedError, requests.ConnectionError):
            print("ERROR: Could not connect to ComfyUI. Start it first with:")
            print("  source ~/wan-pipeline/venv/bin/activate")
            print("  cd ~/wan-pipeline/ComfyUI")
            print("  python main.py --listen 0.0.0.0 --port 8188")
            sys.exit(1)
        if resp.status_code != 200:
            raise RuntimeError(
                f"ComfyUI returned HTTP {resp.status_code}: {resp.text}"
            )
        data = resp.json()
        prompt_id = data["prompt_id"]
        queued.append((inf["id"], prompt_id))
        print(f"queued {inf['id']} -> prompt_id {prompt_id}")

    pending = list(queued)
    while pending:
        still_pending = []
        for inf_id, prompt_id in pending:
            try:
                resp = requests.get(f"http://{args.host}/history/{prompt_id}")
            except (ConnectionRefusedError, requests.ConnectionError):
                print("ERROR: Lost connection to ComfyUI during polling.")
                sys.exit(1)
            done = False
            if resp.status_code == 200:
                body = resp.json()
                if isinstance(body, dict) and body and prompt_id in body:
                    done = True
            if done:
                print(f"✓ {inf_id} done")
            else:
                still_pending.append((inf_id, prompt_id))
        pending = still_pending
        if pending:
            time.sleep(10)


if __name__ == "__main__":
    main()
