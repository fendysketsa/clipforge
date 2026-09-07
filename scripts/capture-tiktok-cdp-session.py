#!/usr/bin/env python3
"""Compatibility wrapper for the validated TikTok Playwright session capture."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def uploader_path() -> Path:
    candidates = [
        Path(__file__).resolve().parents[1] / "backend" / "tiktok_uploader.py",
        Path("/app/tiktok_uploader.py"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError("backend/tiktok_uploader.py tidak ditemukan")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validasi akun TikTok di Chrome CDP lalu simpan Playwright storage-state."
    )
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9444")
    parser.add_argument("--state", required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--target-handle",
        default=os.environ.get("TIKTOK_TARGET_HANDLE", "titikbalikislami"),
    )
    parser.add_argument(
        "--target-email",
        default=os.environ.get("TIKTOK_TARGET_EMAIL", ""),
    )
    args = parser.parse_args()

    command = [
        sys.executable,
        str(uploader_path()),
        "--state",
        args.state,
        "--cdp-url",
        args.cdp_url,
        "--target-handle",
        args.target_handle,
        "--target-email",
        args.target_email,
        "login",
        "--timeout",
        str(max(30, args.timeout)),
    ]
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
