"""Read-only evidence for releasing reservations of deleted remote videos."""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse


def uploader_deleted_video(response: dict) -> str | None:
    status = response.get("playabilityStatus")
    if not isinstance(status, dict) or status.get("status") != "ERROR":
        return None

    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for child in value.values():
                yield from strings(child)
        elif isinstance(value, list):
            for child in value:
                yield from strings(child)

    for value in strings(status.get("errorScreen", {})):
        if value.strip().casefold() in {
            "video ini telah dihapus oleh uploader",
            "this video has been removed by the uploader",
        }:
            return value.strip()
    return None


def read_deleted_video_evidence(video_id: str, cdp_url: str) -> dict | None:
    """Borrow one page from Chrome, read playability, and close only that page.

    Private videos, unavailable videos, login failures, timeouts, and claims
    are not evidence of deletion. Never choose a file or edit Studio metadata.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=10_000)
        if not browser.contexts:
            return None
        page = browser.contexts[0].new_page()
        try:
            page.goto(
                f"https://www.youtube.com/watch?v={video_id}&autoplay=0",
                wait_until="domcontentloaded", timeout=20_000,
            )
            page.wait_for_function(
                "() => !!window.ytInitialPlayerResponse?.playabilityStatus",
                timeout=12_000,
            )
            if parse_qs(urlparse(page.url).query).get("v") != [video_id]:
                return None
            response = page.evaluate("() => window.ytInitialPlayerResponse")
            reason = uploader_deleted_video(response) if isinstance(response, dict) else None
            if not reason:
                return None
            return {
                "video_id": video_id, "deleted_by_uploader": True,
                "reason": reason, "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            # This is the user's borrowed browser; do not close its context or
            # browser, or touch any pre-existing upload tab.
            page.close()
