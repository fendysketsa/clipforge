#!/usr/bin/env python3
"""Download or verify the curated CC0 background-music cache.

This is a setup/rebuild tool. The render pipeline intentionally never imports
or invokes it, so a clip job cannot trigger network access for music.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ALLOWED_AUDIO_SUFFIXES = {".flac", ".m4a", ".mp3", ".ogg", ".wav"}
ALLOWED_SOURCE_HOSTS = {"opengameart.org", "www.opengameart.org"}
CC0_LICENSE_URL = "https://creativecommons.org/publicdomain/zero/1.0/"
MAX_DOWNLOAD_BYTES = 32 * 1024 * 1024


class AllowlistedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Keep media redirects inside the explicitly reviewed provider."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        host = (urllib.parse.urlparse(newurl).hostname or "").casefold()
        if host not in ALLOWED_SOURCE_HOSTS:
            raise urllib.error.URLError(f"redirect host tidak diizinkan: {host or '(kosong)'}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validated_https_url(value: object, field: str, allowed_hosts: set[str]) -> str:
    url = str(value or "").strip()
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or host not in allowed_hosts or parsed.username or parsed.password:
        raise ValueError(f"{field} harus HTTPS pada domain yang diizinkan")
    return url


def validate_entry(entry: object, root: Path) -> tuple[dict[str, object], Path]:
    if not isinstance(entry, dict):
        raise ValueError("entri katalog bukan object")
    relative_file = str(entry.get("file") or "").strip()
    if not relative_file or Path(relative_file).name != relative_file:
        raise ValueError("nama file harus basename lokal")
    target = (root / relative_file).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("path file keluar dari folder pustaka") from exc
    if target.suffix.casefold() not in ALLOWED_AUDIO_SUFFIXES:
        raise ValueError("ekstensi audio tidak diizinkan")
    if str(entry.get("license") or "").strip() != "CC0-1.0":
        raise ValueError("hanya aset CC0-1.0 yang diterima otomatis")
    if str(entry.get("license_url") or "").strip() != CC0_LICENSE_URL:
        raise ValueError("URL lisensi CC0 tidak cocok")
    if entry.get("attribution_required") is not False:
        raise ValueError("aset yang membutuhkan atribusi tidak diterima")
    if entry.get("instrumental") is not True or str(entry.get("kind") or "").casefold() != "music":
        raise ValueError("aset harus berupa musik instrumental")
    validated_https_url(entry.get("source_url"), "source_url", ALLOWED_SOURCE_HOSTS)
    validated_https_url(entry.get("download_url"), "download_url", ALLOWED_SOURCE_HOSTS)
    expected = str(entry.get("sha256") or "").strip().casefold()
    if re.fullmatch(r"[0-9a-f]{64}", expected) is None:
        raise ValueError("SHA-256 tidak valid")
    return entry, target


def audio_signature_is_valid(path: Path, expected_suffix: str | None = None) -> bool:
    with path.open("rb") as handle:
        header = handle.read(16)
    suffix = (expected_suffix or path.suffix).casefold()
    if suffix == ".ogg":
        return header.startswith(b"OggS")
    if suffix == ".flac":
        return header.startswith(b"fLaC")
    if suffix == ".wav":
        return header.startswith(b"RIFF") and header[8:12] == b"WAVE"
    if suffix == ".m4a":
        return len(header) >= 12 and header[4:8] == b"ftyp"
    if suffix == ".mp3":
        has_frame_sync = len(header) >= 2 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0
        return header.startswith(b"ID3") or has_frame_sync
    return False


def cached_asset_is_valid(path: Path, expected_sha256: str) -> bool:
    return (
        path.is_file()
        and 0 < path.stat().st_size <= MAX_DOWNLOAD_BYTES
        and audio_signature_is_valid(path)
        and file_sha256(path).casefold() == expected_sha256
    )


def download_entry(entry: dict[str, object], target: Path) -> None:
    url = str(entry["download_url"])
    opener = urllib.request.build_opener(AllowlistedRedirectHandler())
    request = urllib.request.Request(url, headers={"User-Agent": "ClipForgeMusicSync/1.0"})
    temporary_path: Path | None = None
    try:
        with opener.open(request, timeout=90) as response:
            response_host = (urllib.parse.urlparse(response.geturl()).hostname or "").casefold()
            if response_host not in ALLOWED_SOURCE_HOSTS:
                raise ValueError(f"host respons tidak diizinkan: {response_host or '(kosong)'}")
            declared_size = response.headers.get("Content-Length")
            if declared_size and int(declared_size) > MAX_DOWNLOAD_BYTES:
                raise ValueError("file melebihi batas 32 MiB")
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                downloaded = 0
                while chunk := response.read(1024 * 1024):
                    downloaded += len(chunk)
                    if downloaded > MAX_DOWNLOAD_BYTES:
                        raise ValueError("file melebihi batas 32 MiB")
                    temporary.write(chunk)
        if temporary_path is None or not audio_signature_is_valid(temporary_path, target.suffix):
            raise ValueError("hasil unduhan bukan audio yang dikenali")
        expected = str(entry["sha256"]).casefold()
        actual = file_sha256(temporary_path).casefold()
        if actual != expected:
            raise ValueError(f"SHA-256 berbeda: diharapkan {expected}, diterima {actual}")
        os.replace(temporary_path, target)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def sync_library(library_dir: Path, *, verify_only: bool = False) -> tuple[int, int]:
    root = library_dir.expanduser().resolve()
    catalog_path = root / "catalog.json"
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("runtime_downloads") is not False:
        raise ValueError("catalog.json wajib menonaktifkan runtime_downloads")
    tracks = payload.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        raise ValueError("catalog.json tidak memiliki track")

    root.mkdir(parents=True, exist_ok=True)
    ready = 0
    downloaded = 0
    failures: list[str] = []
    for index, raw_entry in enumerate(tracks, start=1):
        try:
            entry, target = validate_entry(raw_entry, root)
            expected = str(entry["sha256"]).casefold()
            if cached_asset_is_valid(target, expected):
                print(f"READY {target.name} (cache + SHA-256 valid)")
                ready += 1
                continue
            if verify_only:
                raise ValueError("file hilang, rusak, atau hash tidak cocok")
            download_entry(entry, target)
            print(f"DOWNLOADED {target.name} (CC0-1.0 + SHA-256 valid)")
            ready += 1
            downloaded += 1
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
            failures.append(f"track #{index}: {exc}")

    if failures:
        raise RuntimeError("; ".join(failures))
    return ready, downloaded


def main() -> int:
    parser = argparse.ArgumentParser(description="Sinkronkan cache backsound CC0 terkurasi.")
    parser.add_argument(
        "--library-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "backend" / "assets" / "background_music",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Jangan memakai jaringan; gagal jika aset lokal belum lengkap.",
    )
    args = parser.parse_args()
    try:
        ready, downloaded = sync_library(args.library_dir, verify_only=args.verify_only)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"BACKGROUND_MUSIC_SYNC_ERROR: {exc}")
        return 1
    print(f"Background music ready: {ready} track(s), downloaded now: {downloaded}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
