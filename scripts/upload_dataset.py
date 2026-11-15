#!/usr/bin/env python3
"""Upload a directory of files to zest-data-api as a single dataset (POST /datasets).

Standard library only. All regular files directly inside the directory are sent as
one dataset bundle (stored in MinIO behind the API).

Usage:
    python scripts/upload_dataset.py ../data-temp
    python scripts/upload_dataset.py ../data-temp --name SIM-01 --api-url http://localhost:8091
"""

from __future__ import annotations

import argparse
import mimetypes
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path


def encode_multipart(files: list[Path], fields: dict[str, str]) -> tuple[bytes, str]:
    """Encode files (field name 'files') + simple form fields as multipart/form-data."""
    boundary = "----zestdataapi" + secrets.token_hex(16)
    out = bytearray()
    for key, value in fields.items():
        if value is None:
            continue
        out += f"--{boundary}\r\n".encode()
        out += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
        out += f"{value}\r\n".encode()
    for path in files:
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        out += f"--{boundary}\r\n".encode()
        out += (
            f'Content-Disposition: form-data; name="files"; filename="{path.name}"\r\n'
        ).encode()
        out += f"Content-Type: {ctype}\r\n\r\n".encode()
        out += path.read_bytes()
        out += b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Directory of files to upload as one dataset")
    parser.add_argument("--name", default=None, help="Dataset name (default: directory name)")
    parser.add_argument("--description", default=None, help="Optional dataset description")
    parser.add_argument("--api-url", default="http://localhost:8091", help="Base API URL")
    args = parser.parse_args()

    if not args.directory.is_dir():
        print(f"Not a directory: {args.directory}", file=sys.stderr)
        return 2

    files = sorted(p for p in args.directory.iterdir() if p.is_file())
    if not files:
        print(f"No files found in {args.directory}", file=sys.stderr)
        return 2

    fields = {"name": args.name or args.directory.resolve().name, "description": args.description}
    body, content_type = encode_multipart(files, fields)

    url = f"{args.api_url.rstrip('/')}/datasets"
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", content_type)
    print(f"Uploading {len(files)} file(s) to {url} …")
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"{resp.status} {resp.read().decode()}")
            return 0
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode()}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
