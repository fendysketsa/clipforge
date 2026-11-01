#!/usr/bin/env python3
"""Delete one exact TikTok Studio post by its unique caption text."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
from types import SimpleNamespace
import sys
import time

sys.path.insert(0, "/app")

from tiktok_uploader import (  # noqa: E402
    DEFAULT_EMAIL,
    DEFAULT_HANDLE,
    DEFAULT_PROFILE_DIR,
    DEFAULT_PROFILE_NAME,
    DEFAULT_STATE_PATH,
    TIKTOK_CONTENT_URL,
    first_visible,
    goto,
    import_playwright,
    open_context,
    save_debug,
    select_tiktok_page,
    validate_target_account,
)


def locate_caption_row(page, caption: str):
    page.goto(TIKTOK_CONTENT_URL, wait_until="domcontentloaded", timeout=45_000)
    page.wait_for_timeout(2_000)
    caption_locator = page.get_by_text(caption, exact=False).first
    caption_locator.wait_for(state="visible", timeout=20_000)
    for xpath in (
        "xpath=ancestor::tr[1]",
        "xpath=ancestor::*[@role='row'][1]",
    ):
        row = caption_locator.locator(xpath)
        try:
            if row.count() and row.first.is_visible(timeout=1_000):
                return row.first
        except Exception:
            pass

    caption_locator.evaluate(
        """
        node => {
          let current = node;
          for (let depth = 0; current && depth < 9; depth += 1, current = current.parentElement) {
            const controls = current.querySelectorAll?.('button,[role="button"]') || [];
            if (controls.length > 0) {
              current.setAttribute('data-clipforge-delete-row', 'true');
              return;
            }
          }
          throw new Error('Baris post tidak memiliki kontrol aksi');
        }
        """
    )
    return page.locator('[data-clipforge-delete-row="true"]').first


def open_delete_action(page, row) -> None:
    menu = first_visible(
        row,
        (
            'button[aria-label*="more" i]',
            'button[aria-label*="action" i]',
            'button[aria-label*="option" i]',
            '[role="button"][aria-label*="more" i]',
            '[data-e2e*="more"]',
            '[class*="more"] button',
            '[class*="action"] button',
        ),
        timeout_ms=1_500,
    )
    if menu is None:
        controls = row.locator('button,[role="button"]')
        count = controls.count()
        if count < 1:
            raise RuntimeError("Menu aksi post TikTok tidak ditemukan.")
        menu = controls.nth(count - 1)
    menu.click(timeout=10_000)
    page.wait_for_timeout(600)

    delete_action = first_visible(
        page,
        (
            '[role="menuitem"]:has-text("Delete")',
            '[role="menuitem"]:has-text("Hapus")',
            'button:has-text("Delete")',
            'button:has-text("Hapus")',
            'text="Delete"',
            'text="Hapus"',
        ),
        timeout_ms=2_000,
    )
    if delete_action is None:
        raise RuntimeError("Aksi Delete/Hapus pada menu post TikTok tidak ditemukan.")
    delete_action.click(timeout=10_000)
    page.wait_for_timeout(600)

    dialog = first_visible(page, ('[role="dialog"]', '[class*="modal"]'), timeout_ms=2_000)
    scope = dialog if dialog is not None else page
    confirm = first_visible(
        scope,
        (
            'button:has-text("Delete")',
            'button:has-text("Hapus")',
            'button:has-text("Confirm")',
            'button:has-text("Konfirmasi")',
        ),
        timeout_ms=2_000,
    )
    if confirm is None:
        raise RuntimeError("Tombol konfirmasi hapus TikTok tidak ditemukan.")
    confirm.click(timeout=10_000)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--caption", required=True)
    parser.add_argument("--target-handle", default=os.environ.get("TIKTOK_TARGET_HANDLE", DEFAULT_HANDLE))
    parser.add_argument("--target-email", default=os.environ.get("TIKTOK_TARGET_EMAIL", DEFAULT_EMAIL))
    parser.add_argument("--cdp-url", default=os.environ.get("TIKTOK_CDP_URL", "http://127.0.0.1:9444"))
    parser.add_argument("--state", default=os.environ.get("TIKTOK_PLAYWRIGHT_STATE", str(DEFAULT_STATE_PATH)))
    args = parser.parse_args()
    caption = re.sub(r"\s+", " ", args.caption).strip()[:160]
    if len(caption) < 20:
        raise RuntimeError("Caption target terlalu pendek untuk penghapusan yang aman.")

    browser_args = SimpleNamespace(
        cdp_url=args.cdp_url,
        state=Path(args.state),
        chromium_user_data_dir=DEFAULT_PROFILE_DIR,
        chromium_profile_directory=DEFAULT_PROFILE_NAME,
        no_headless=False,
    )
    sync_playwright, _ = import_playwright()
    with sync_playwright() as playwright:
        context, browser = open_context(playwright, browser_args)
        page = select_tiktok_page(context)
        page.set_default_timeout(20_000)
        try:
            validate_target_account(page, args.target_handle, args.target_email)
            row = locate_caption_row(page, caption)
            matches = page.get_by_text(caption, exact=False).count()
            if matches != 1:
                raise RuntimeError(
                    f"Caption target ditemukan {matches} kali; penghapusan otomatis dibatalkan."
                )
            open_delete_action(page, row)
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                page.wait_for_timeout(2_000)
                try:
                    page.reload(wait_until="domcontentloaded", timeout=30_000)
                    page.wait_for_timeout(1_000)
                    if page.get_by_text(caption, exact=False).count() == 0:
                        print(f"Remote TikTok terhapus: {caption}", flush=True)
                        return 0
                except Exception:
                    pass
            save_debug(page, "delete-post-not-confirmed")
            raise RuntimeError("TikTok belum mengonfirmasi bahwa post target sudah terhapus.")
        except Exception:
            save_debug(page, "delete-post-failed")
            raise
        finally:
            if not args.cdp_url:
                try:
                    context.close()
                except Exception:
                    pass
                if browser is not None:
                    browser.close()


if __name__ == "__main__":
    raise SystemExit(main())
