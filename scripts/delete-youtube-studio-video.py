#!/usr/bin/env python3
"""Delete one exact YouTube Studio video through the authenticated CDP browser."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, "/app")

from youtube_uploader import (  # noqa: E402
    DEFAULT_STUDIO_URL,
    DEFAULT_STATE_PATH,
    DEFAULT_TARGET_CHANNEL_ID,
    DEFAULT_TARGET_EMAIL,
    chromium_executable_kwargs,
    chromium_launch_args,
    discard_studio_video,
    ensure_logged_in,
    ensure_target_identity,
    goto_studio,
    import_playwright,
    install_browser_dialog_guard,
    install_context_dialog_guard,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video_url")
    parser.add_argument(
        "--cdp-url",
        default=os.environ.get("YOUTUBE_CDP_URL", "http://127.0.0.1:9333"),
    )
    parser.add_argument(
        "--target-channel",
        default=os.environ.get("YOUTUBE_TARGET_CHANNEL", "ryuundyofficial"),
    )
    parser.add_argument(
        "--target-email",
        default=os.environ.get("YOUTUBE_TARGET_EMAIL", DEFAULT_TARGET_EMAIL),
    )
    parser.add_argument(
        "--target-channel-id",
        default=os.environ.get("YOUTUBE_TARGET_CHANNEL_ID", DEFAULT_TARGET_CHANNEL_ID),
    )
    parser.add_argument(
        "--studio-url",
        default=os.environ.get("YOUTUBE_STUDIO_URL", DEFAULT_STUDIO_URL),
    )
    parser.add_argument(
        "--state",
        default=os.environ.get("YOUTUBE_PLAYWRIGHT_STATE", str(DEFAULT_STATE_PATH)),
    )
    args = parser.parse_args()

    sync_playwright, _ = import_playwright()
    with sync_playwright() as playwright:
        launched_locally = False
        try:
            browser = playwright.chromium.connect_over_cdp(args.cdp_url, no_defaults=True, timeout=8000)
            contexts = browser.contexts
            if not contexts:
                raise RuntimeError("Chrome CDP tidak memiliki browser context aktif.")
            context = contexts[0]
        except Exception:
            state_path = Path(args.state).expanduser().resolve()
            if not state_path.is_file():
                raise RuntimeError(
                    f"CDP tidak tersedia dan session YouTube tidak ditemukan: {state_path}"
                )
            browser = playwright.chromium.launch(
                headless=True,
                args=chromium_launch_args(),
                **chromium_executable_kwargs(),
            )
            launched_locally = True
            context = browser.new_context(
                locale=os.environ.get("YOUTUBE_BROWSER_LOCALE", "en-US"),
                storage_state=str(state_path),
                viewport={"width": 1440, "height": 1000},
            )
        install_context_dialog_guard(context)
        page = context.new_page()
        install_browser_dialog_guard(page)
        try:
            goto_studio(page, studio_url=args.studio_url)
            ensure_logged_in(page)
            ensure_target_identity(
                page,
                args.target_channel,
                args.target_email,
                args.target_channel_id,
            )
            if not discard_studio_video(page, args.video_url, timeout_ms=45000):
                raise RuntimeError("YouTube Studio belum mengonfirmasi penghapusan.")
        finally:
            try:
                if not page.is_closed():
                    page.close()
            except Exception:
                pass
            if launched_locally:
                browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
