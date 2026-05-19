#!/usr/bin/env python3
"""Tiny S3 push/pull helper used by runpod/entrypoint.sh.

Uses boto3's default credentials chain (env vars AWS_ACCESS_KEY_ID /
AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN, ~/.aws/credentials, or an
instance role). Optional AWS_REGION / AWS_DEFAULT_REGION is honored.

Usage:
    python3 s3_sync.py down BUCKET PREFIX LOCAL_DIR
        Download every object under s3://BUCKET/PREFIX/ into LOCAL_DIR/,
        preserving relative paths under PREFIX.

    python3 s3_sync.py up LOCAL_DIR BUCKET PREFIX
        Upload every file under LOCAL_DIR/ to s3://BUCKET/PREFIX/,
        preserving relative paths under LOCAL_DIR.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _eprint(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _norm_prefix(prefix: str) -> str:
    """Strip leading slashes and trailing slashes, collapse empties.

    S3 keys never start with a slash. We accept "", "foo", "foo/",
    "/foo/bar/" and normalize to "" or "foo" or "foo/bar".
    """
    return prefix.strip("/").strip()


def _make_s3_client():
    try:
        import boto3  # type: ignore
    except ImportError as exc:
        _eprint(f"ERROR: boto3 not installed: {exc}")
        sys.exit(1)
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    if region:
        return boto3.client("s3", region_name=region)
    return boto3.client("s3")


def download_prefix(bucket: str, prefix: str, local_dir: str) -> int:
    """Download all objects under s3://bucket/prefix/ to local_dir/.

    Returns number of files downloaded.
    """
    norm = _norm_prefix(prefix)
    # When listing, we want a trailing slash for non-empty prefixes so we
    # only match objects under that "directory" (not e.g. "assetsX/").
    list_prefix = (norm + "/") if norm else ""

    client = _make_s3_client()
    local_root = Path(local_dir)
    local_root.mkdir(parents=True, exist_ok=True)

    print(f"[s3_sync] DOWN s3://{bucket}/{list_prefix} -> {local_root}/")

    paginator = client.get_paginator("list_objects_v2")
    count = 0
    try:
        for page in paginator.paginate(Bucket=bucket, Prefix=list_prefix):
            for obj in page.get("Contents", []) or []:
                key = obj["Key"]
                # Skip "directory marker" keys ending in "/".
                if key.endswith("/"):
                    continue
                rel = key[len(list_prefix):] if list_prefix else key
                if not rel:
                    continue
                dest = local_root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                print(f"  pull s3://{bucket}/{key} -> {dest}")
                client.download_file(bucket, key, str(dest))
                count += 1
    except Exception as exc:  # noqa: BLE001
        _eprint(f"ERROR: download failed: {exc}")
        sys.exit(1)

    print(f"[s3_sync] DOWN done, {count} file(s)")
    return count


def upload_prefix(local_dir: str, bucket: str, prefix: str) -> int:
    """Upload all files under local_dir/ to s3://bucket/prefix/.

    Returns number of files uploaded.
    """
    norm = _norm_prefix(prefix)
    local_root = Path(local_dir)
    if not local_root.exists():
        print(f"[s3_sync] UP source {local_root} does not exist, nothing to upload")
        return 0
    if not local_root.is_dir():
        _eprint(f"ERROR: upload source {local_root} is not a directory")
        sys.exit(1)

    client = _make_s3_client()
    dest_disp = f"s3://{bucket}/{norm + '/' if norm else ''}"
    print(f"[s3_sync] UP {local_root}/ -> {dest_disp}")

    count = 0
    try:
        for path in local_root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(local_root).as_posix()
            key = f"{norm}/{rel}" if norm else rel
            print(f"  push {path} -> s3://{bucket}/{key}")
            client.upload_file(str(path), bucket, key)
            count += 1
    except Exception as exc:  # noqa: BLE001
        _eprint(f"ERROR: upload failed: {exc}")
        sys.exit(1)

    print(f"[s3_sync] UP done, {count} file(s)")
    return count


def _usage_and_exit() -> None:
    _eprint(__doc__ or "")
    sys.exit(2)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        _usage_and_exit()
    mode = argv[1]
    if mode == "down":
        if len(argv) != 5:
            _usage_and_exit()
        _, _, bucket, prefix, local_dir = argv
        download_prefix(bucket, prefix, local_dir)
        return 0
    if mode == "up":
        if len(argv) != 5:
            _usage_and_exit()
        _, _, local_dir, bucket, prefix = argv
        upload_prefix(local_dir, bucket, prefix)
        return 0
    _eprint(f"ERROR: unknown mode {mode!r}; expected 'down' or 'up'")
    _usage_and_exit()
    return 2  # unreachable


if __name__ == "__main__":
    sys.exit(main(sys.argv))
