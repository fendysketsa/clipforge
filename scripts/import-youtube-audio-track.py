#!/usr/bin/env python3
"""Import one manually downloaded, attribution-free YouTube Audio Library track."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path


THEMES = {"mystery", "islamic", "warning", "inspiring", "knowledge"}
AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}


def clean_tags(values: list[str]) -> list[str]:
    return list(
        dict.fromkeys(
            clean
            for value in values
            if (clean := re.sub(r"\s+", " ", value).strip().casefold())
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import musik instrumental Attribution-not-required dari YouTube Audio Library.",
    )
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--artist", required=True)
    parser.add_argument("--theme", action="append", default=[], choices=sorted(THEMES))
    parser.add_argument("--mood", action="append", default=[])
    parser.add_argument("--genre", action="append", default=[])
    parser.add_argument(
        "--library-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "backend" / "assets" / "youtube_audio_library",
    )
    args = parser.parse_args()

    source = args.file.expanduser().resolve()
    if not source.is_file() or source.suffix.casefold() not in AUDIO_SUFFIXES:
        parser.error("--file harus menunjuk file audio MP3/WAV/M4A/FLAC/OGG yang valid")
    if not args.theme or not args.mood:
        parser.error("minimal satu --theme dan satu --mood wajib diisi agar pemilihan musik akurat")

    root = args.library_dir.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:10]
    stem = re.sub(r"[^a-z0-9]+", "-", args.title.casefold()).strip("-") or "track"
    destination = root / f"{stem[:72]}-{digest}{source.suffix.casefold()}"
    if source != destination:
        shutil.copy2(source, destination)

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
        "title": re.sub(r"\s+", " ", args.title).strip(),
        "artist": re.sub(r"\s+", " ", args.artist).strip(),
        "kind": "music",
        "instrumental": True,
        "themes": clean_tags(args.theme),
        "moods": clean_tags(args.mood),
        "genres": clean_tags(args.genre),
        "license": "YouTube Audio Library License",
        "attribution_required": False,
        "source_url": "https://youtube.com/audiolibrary",
        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
    }
    tracks = [item for item in tracks if not isinstance(item, dict) or item.get("sha256") != entry["sha256"]]
    tracks.append(entry)
    catalog["version"] = 1
    catalog["tracks"] = sorted(
        tracks,
        key=lambda item: str(item.get("title") if isinstance(item, dict) else "").casefold(),
    )
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Imported: {entry['title']} — {entry['artist']} -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
