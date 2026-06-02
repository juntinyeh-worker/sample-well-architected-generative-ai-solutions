"""Steering file loader — loads kiro-style .md steering files into agent context.

Supports loading from:
- Local path (e.g. /app/steering/ or relative ./steering/)
- S3 path (e.g. s3://bucket/steering/)

Steering files are organized as:
  steering/
  ├── product.md        # What this agent does
  ├── flow.md           # The review flow/process
  ├── pillars/          # WA pillar-specific guidance
  │   ├── security.md
  │   ├── reliability.md
  │   ├── performance.md
  │   ├── cost.md
  │   └── operational-excellence.md
  └── checks/           # Specific check procedures
      ├── iam-review.md
      ├── network-review.md
      └── ...

All .md files found are concatenated into the system prompt with headers.
"""
import os
import logging
import boto3

logger = logging.getLogger(__name__)

STEERING_PATH = os.getenv("STEERING_PATH", "/app/steering")
STEERING_S3_URI = os.getenv("STEERING_S3_URI", "")  # e.g. s3://bucket/prefix/steering/


def load_steering_files() -> str:
    """Load all steering .md files and return as combined system prompt section."""
    if STEERING_S3_URI:
        return _load_from_s3(STEERING_S3_URI)
    if os.path.isdir(STEERING_PATH):
        return _load_from_local(STEERING_PATH)
    logger.warning(f"No steering files found at {STEERING_PATH} or S3")
    return ""


def _load_from_local(path: str) -> str:
    """Recursively load all .md files from a local directory."""
    sections = []
    for root, _, files in sorted(os.walk(path)):
        for fname in sorted(files):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, path)
            try:
                with open(fpath, "r") as f:
                    content = f.read().strip()
                if content:
                    sections.append(f"--- STEERING: {rel} ---\n{content}")
            except Exception as e:
                logger.warning(f"Failed to read {fpath}: {e}")
    if sections:
        logger.info(f"Loaded {len(sections)} steering files from {path}")
    return "\n\n".join(sections)


def _load_from_s3(s3_uri: str) -> str:
    """Load all .md files from an S3 prefix."""
    s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-west-2"))
    # Parse s3://bucket/prefix/
    parts = s3_uri.replace("s3://", "").split("/", 1)
    bucket = parts[0]
    prefix = parts[1] if len(parts) > 1 else ""
    if not prefix.endswith("/"):
        prefix += "/"

    sections = []
    try:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if not key.endswith(".md"):
                    continue
                rel = key[len(prefix):]
                try:
                    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8").strip()
                    if body:
                        sections.append(f"--- STEERING: {rel} ---\n{body}")
                except Exception as e:
                    logger.warning(f"Failed to read s3://{bucket}/{key}: {e}")
    except Exception as e:
        logger.warning(f"Failed to list S3 steering files: {e}")

    if sections:
        logger.info(f"Loaded {len(sections)} steering files from {s3_uri}")
    return "\n\n".join(sections)
