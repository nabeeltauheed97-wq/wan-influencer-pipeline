#!/usr/bin/env python3
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


def find_node(wf, class_types, override, role):
    if override is not None:
        return str(override)
    matches = []
    for node_id, node in wf.items():
        if isinstance(node, dict) and node.get("class_type") in class_types:
            matches.append((node_id, node.get("class_type")))
    if len(matches) == 1:
        return matches[0][0]
    if len(matches) == 0:
        print(
            f"ERROR: Could not auto-detect the {role} node. "
            f"Looked for class_type in {sorted(class_types)} but found none."
        )
        sys.exit(1)
    print(
        f"ERROR: Found multiple candidate nodes for the {role}. "
        f"Pass the correct --*-node-id flag to disambiguate:"
    )
    for node_id, class_type in matches:
        print(f"  node_id={node_id}  class_type={class_type}")
    if role == "reference image":
        flag = "--image-node-id"
    elif role == "source video":
        flag = "--video-node-id"
    else:
        flag = "--save-node-id"
    print(f"Use {flag} <node_id> to pick one.")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
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

    image_node_id = find_node(
        workflow, {"LoadImage"}, args.image_node_id, "reference image"
    )
    video_node_id = find_node(
        workflow, {"VHS_LoadVideo", "LoadVideo"}, args.video_node_id, "source video"
    )
    save_node_id = find_node(
        workflow,
        {"VHS_VideoCombine", "SaveAnimatedWEBP", "SaveImage"},
        args.save_node_id,
        "output save",
    )

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
        wf_copy[image_node_id]["inputs"]["image"] = inf["image"]
        wf_copy[video_node_id]["inputs"]["video"] = args.source
        wf_copy[save_node_id]["inputs"]["filename_prefix"] = inf["id"]

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
                print("ERROR: Could not connect to ComfyUI. Start it first with:")
                print("  source ~/wan-pipeline/venv/bin/activate")
                print("  cd ~/wan-pipeline/ComfyUI")
                print("  python main.py --listen 0.0.0.0 --port 8188")
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
