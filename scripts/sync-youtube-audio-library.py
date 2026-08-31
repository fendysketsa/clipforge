#!/usr/bin/env python3
"""Download one attribution-free YouTube Audio Library track for a clip theme."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path


THEME_MOODS = {
    "mystery": (("Dramatic", "Dramatis"), ("dark", "dramatic", "suspense", "cinematic")),
    "islamic": (("Calm", "Tenang"), ("reflective", "calm", "inspirational", "ambient")),
    "warning": (("Dramatic", "Dramatis"), ("warning", "dramatic", "tense", "suspense")),
    "inspiring": (("Inspirational", "Inspiratif"), ("inspiring", "inspirational", "hopeful", "uplifting")),
    "knowledge": (("Calm", "Tenang"), ("knowledge", "educational", "calm", "documentary")),
}
AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}


def emit(payload: dict[str, object]) -> None:
    print("YOUTUBE_AUDIO_SYNC:" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def visible_first(locator):
    for index in range(min(locator.count(), 20)):
        candidate = locator.nth(index)
        try:
            if candidate.is_visible():
                return candidate
        except Exception:
            continue
    return None


def click_named(page, patterns: tuple[str, ...], *, role: str | None = None, timeout: int = 5000) -> bool:
    regex = re.compile("|".join(re.escape(item) for item in patterns), re.IGNORECASE)
    locators = []
    if role:
        locators.append(page.get_by_role(role, name=regex))
    locators.extend((page.get_by_text(regex, exact=True), page.get_by_text(regex, exact=False)))
    for locator in locators:
        candidate = visible_first(locator)
        if candidate is None:
            continue
        try:
            candidate.click(timeout=timeout)
            return True
        except Exception:
            continue
    return False


def open_filter_menu(page) -> bool:
    patterns = ("Filter", "Filter koleksi audio", "Search filters", "Telusuri atau filter")
    if click_named(page, patterns, role="button", timeout=3500):
        return True
    selectors = (
        'button[aria-label*="filter" i]',
        '[role="button"][aria-label*="filter" i]',
        'ytcp-icon-button[aria-label*="filter" i]',
    )
    for selector in selectors:
        candidate = visible_first(page.locator(selector))
        if candidate is not None:
            try:
                candidate.click(timeout=3500)
                return True
            except Exception:
                continue
    return False


def apply_filter(page, category: tuple[str, ...], values: tuple[str, ...]) -> bool:
    if not open_filter_menu(page):
        return False
    if not click_named(page, category, timeout=4000):
        return False
    page.wait_for_timeout(350)
    return click_named(page, values, timeout=5000)


def parse_download_name(filename: str) -> tuple[str, str]:
    stem = Path(filename).stem
    parts = [part.strip() for part in re.split(r"\s+-\s+", stem) if part.strip()]
    if len(parts) >= 2:
        return " - ".join(parts[:-1]), parts[-1]
    return stem or "YouTube Audio Library Track", "YouTube Audio Library"


def import_download(download_path: Path, suggested_name: str, root: Path, theme: str) -> dict[str, object]:
    suffix = Path(suggested_name).suffix.casefold() or download_path.suffix.casefold()
    if suffix not in AUDIO_SUFFIXES:
        raise RuntimeError(f"File unduhan bukan audio yang didukung: {suggested_name}")
    title, artist = parse_download_name(suggested_name)
    content = download_path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    safe_title = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-") or "track"
    destination = root / f"{safe_title[:72]}-{digest[:10]}{suffix}"
    destination.write_bytes(content)
    _display_moods, catalog_moods = THEME_MOODS[theme]
    catalog_path = root / "catalog.json"
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        catalog = {"version": 1, "tracks": []}
    if not isinstance(catalog, dict):
        catalog = {"version": 1, "tracks": []}
    tracks = catalog.get("tracks")
    if not isinstance(tracks, list):
        tracks = []
    entry = {
        "file": destination.name,
        "title": title[:180],
        "artist": artist[:180],
        "kind": "music",
        "instrumental": True,
        "themes": [theme],
        "moods": list(catalog_moods),
        "genres": ["cinematic" if theme in {"mystery", "warning"} else "ambient"],
        "license": "YouTube Audio Library License",
        "attribution_required": False,
        "source_url": "https://youtube.com/audiolibrary",
        "sha256": digest,
        "downloaded_via": "youtube_studio_audio_library_attribution_not_required_filter",
    }
    tracks = [item for item in tracks if not isinstance(item, dict) or item.get("sha256") != digest]
    tracks.append(entry)
    catalog["version"] = 1
    catalog["tracks"] = sorted(
        tracks,
        key=lambda item: str(item.get("title") if isinstance(item, dict) else "").casefold(),
    )
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description="Sinkronkan satu backsong dari YouTube Studio Audio Library.")
    parser.add_argument("--theme", required=True, choices=sorted(THEME_MOODS))
    parser.add_argument("--library-dir", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--studio-url", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=75)
    args = parser.parse_args()

    root = args.library_dir.expanduser().resolve()
    state_path = args.state.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    if not state_path.is_file():
        emit({"ok": False, "reason": "youtube_storage_state_missing"})
        return 2

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        emit({"ok": False, "reason": "playwright_unavailable", "detail": str(exc)[:300]})
        return 2

    base_url = args.studio_url.split("?", 1)[0].rstrip("/")
    if base_url.endswith("/music"):
        music_url = base_url + "?theme=dark"
    else:
        music_url = base_url + "/music?theme=dark"
    timeout_ms = max(30, min(180, args.timeout_seconds)) * 1000
    browser = None
    context = None
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                locale=os.environ.get("YOUTUBE_BROWSER_LOCALE", "en-US"),
                storage_state=str(state_path),
                accept_downloads=True,
                viewport={"width": 1600, "height": 1000},
            )
            page = context.new_page()
            page.goto(music_url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(2200)
            if "accounts.google.com" in page.url.casefold() or "signin" in page.url.casefold():
                raise RuntimeError("Sesi YouTube Studio sudah kedaluwarsa; jalankan Login Sekali")
            if not click_named(page, ("Music", "Musik"), timeout=5000):
                raise RuntimeError("Tab Musik YouTube Audio Library tidak ditemukan")
            page.wait_for_timeout(800)
            attribution_ok = apply_filter(
                page,
                ("Attribution", "Atribusi"),
                (
                    "Attribution not required",
                    "Atribusi tidak diperlukan",
                    "Tidak perlu atribusi",
                ),
            )
            if not attribution_ok:
                raise RuntimeError("Filter Attribution not required tidak dapat diverifikasi")
            page.wait_for_timeout(700)
            display_moods, _catalog_moods = THEME_MOODS[args.theme]
            if not apply_filter(page, ("Mood", "Suasana", "Suasana hati"), display_moods):
                raise RuntimeError(f"Filter mood untuk tema {args.theme} tidak dapat diverifikasi")
            page.wait_for_timeout(1800)

            rows = page.locator("ytcp-audio-library-track-row")
            if rows.count() == 0:
                rows = page.locator('[role="row"]')
            downloaded = None
            for index in range(min(rows.count(), 20)):
                row = rows.nth(index)
                try:
                    if not row.is_visible():
                        continue
                    row.hover(timeout=3000)
                except Exception:
                    continue
                button = visible_first(
                    row.get_by_role(
                        "button",
                        name=re.compile(r"download|unduh", re.IGNORECASE),
                    )
                )
                if button is None:
                    button = visible_first(
                        row.locator(
                            '[aria-label*="download" i], [aria-label*="unduh" i], '
                            'button:has-text("DOWNLOAD"), button:has-text("UNDUH")'
                        )
                    )
                if button is None:
                    continue
                try:
                    with page.expect_download(timeout=12000) as download_info:
                        button.click(timeout=5000)
                    downloaded = download_info.value
                    break
                except Exception:
                    continue
            if downloaded is None:
                raise RuntimeError("Tidak menemukan tombol Download pada hasil Audio Library")
            temporary = root / f".download-{os.getpid()}.tmp"
            downloaded.save_as(str(temporary))
            entry = import_download(temporary, downloaded.suggested_filename, root, args.theme)
            temporary.unlink(missing_ok=True)
            context.storage_state(path=str(state_path))
            emit({"ok": True, "theme": args.theme, "track": entry})
            context.close()
            browser.close()
            return 0
    except Exception as exc:
        emit({"ok": False, "reason": "youtube_audio_sync_failed", "detail": str(exc)[:500]})
        try:
            if context is not None:
                context.close()
        except Exception:
            pass
        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
