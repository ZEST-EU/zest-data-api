#!/usr/bin/env python3
"""Upload SIM-01-format datasets to a running zest-data-api via POST /datasets.

Discovers run groups in a directory by the ``<run_id>_log.csv`` /
``<run_id>_labels.csv`` / ``<run_id>_truth.json`` naming convention and uploads
each run as one multipart request. Standard library only.

Usage:
    python scripts/upload_dataset.py ../data-temp
    python scripts/upload_dataset.py ../data-temp --api-url http://localhost:8091 --replace
"""

from __future__ import annotations

import argparse
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path

SUFFIXES = {
    "log": "_log.csv",
    "labels": "_labels.csv",
    "truth": "_truth.json",
}
CONTENT_TYPES = {
    "log": "text/csv",
    "labels": "text/csv",
    "truth": "application/json",
}


def discover_runs(directory: Path) -> dict[str, dict[str, Path]]:
    """Map run_id -> {field: path} for every run found in *directory*."""
    runs: dict[str, dict[str, Path]] = {}
    for path in sorted(directory.iterdir()):
        for field, suffix in SUFFIXES.items():
            if path.name.endswith(suffix):
                run_id = path.name[: -len(suffix)]
                runs.setdefault(run_id, {})[field] = path
    return runs


def encode_multipart(files: dict[str, Path]) -> tuple[bytes, str]:
    """Encode {field: path} as multipart/form-data. Returns (body, content_type)."""
    boundary = "----zestdataapi" + secrets.token_hex(16)
    out = bytearray()
    for field, path in files.items():
        out += f"--{boundary}\r\n".encode()
        out += (
            f'Content-Disposition: form-data; name="{field}"; filename="{path.name}"\r\n'
        ).encode()
        out += f"Content-Type: {CONTENT_TYPES[field]}\r\n\r\n".encode()
        out += path.read_bytes()
        out += b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def upload_run(api_url: str, run_id: str, files: dict[str, Path], replace: bool) -> int:
    body, content_type = encode_multipart(files)
    url = f"{api_url.rstrip('/')}/datasets"
    if replace:
        url += "?replace=true"
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"[{run_id}] {resp.status} {resp.read().decode()}")
            return 0
    except urllib.error.HTTPError as exc:
        print(f"[{run_id}] HTTP {exc.code}: {exc.read().decode()}", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Directory containing dataset files")
    parser.add_argument("--api-url", default="http://localhost:8091", help="Base API URL")
    parser.add_argument("--replace", action="store_true", help="Overwrite existing runs")
    args = parser.parse_args()

    if not args.directory.is_dir():
        print(f"Not a directory: {args.directory}", file=sys.stderr)
        return 2

    runs = discover_runs(args.directory)
    if not runs:
        print(f"No SIM-01-format datasets found in {args.directory}", file=sys.stderr)
        return 2

    print(f"Found {len(runs)} run(s): {', '.join(runs)}")
    failures = 0
    for run_id, files in runs.items():
        if "log" not in files and "truth" not in files:
            print(f"[{run_id}] skipped (needs a log or truth file)", file=sys.stderr)
            failures += 1
            continue
        failures += upload_run(args.api_url, run_id, files, args.replace)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
