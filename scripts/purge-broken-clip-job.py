#!/usr/bin/env python3
"""Purge one known-broken clip job and its exact in-flight YouTube draft."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

import psutil


API_BASE = "http://127.0.0.1:8010"
OUTPUTS_ROOT = Path("/app/outputs")


def api_json(path: str, *, method: str = "GET") -> tuple[int, object]:
    request = urllib.request.Request(f"{API_BASE}{path}", method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload: object = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"detail": raw}
        return exc.code, payload


def terminate_exact_uploaders(clip_name: str) -> list[int]:
    stopped: list[int] = []
    for process in psutil.process_iter(["pid", "cmdline"]):
        try:
            command = [str(item) for item in (process.info.get("cmdline") or [])]
            joined = " ".join(command)
            if (
                ("youtube_uploader.py" in joined or "tiktok_uploader.py" in joined)
                and " upload " in f" {joined} "
                and clip_name in joined
            ):
                process.terminate()
                stopped.append(int(process.pid))
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    if stopped:
        _gone, alive = psutil.wait_procs(
            [psutil.Process(pid) for pid in stopped if psutil.pid_exists(pid)],
            timeout=10,
        )
        for process in alive:
            try:
                process.kill()
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
    return stopped


def tiktok_uploads_for_clip(job_id: str, clip_url: str) -> list[dict[str, object]]:
    status, payload = api_json("/api/tiktok/uploads")
    if status != 200 or not isinstance(payload, list):
        raise RuntimeError(f"Daftar upload TikTok tidak dapat dibaca: HTTP {status} {payload}")
    return [
        item
        for item in payload
        if isinstance(item, dict)
        and str(item.get("source_job_id") or "") == job_id
        and str(item.get("clip_url") or "") == clip_url
    ]


def actual_clip_duration(clip_url: str) -> float:
    if not clip_url.startswith("/outputs/"):
        raise RuntimeError("Clip URL target bukan file outputs; purge dibatalkan.")
    clip_path = (Path("/app") / clip_url.lstrip("/")).resolve()
    if OUTPUTS_ROOT.resolve() not in clip_path.parents or not clip_path.is_file():
        raise RuntimeError(f"File clip target tidak ditemukan: {clip_path}")
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(clip_path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    match = re.search(
        r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)",
        f"{result.stderr}\n{result.stdout}",
    )
    if not match:
        raise RuntimeError("Durasi aktual clip tidak dapat dibaca; purge dibatalkan.")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--upload-id", required=True)
    parser.add_argument("--video-url", required=True)
    args = parser.parse_args()

    status, upload = api_json(f"/api/youtube/uploads/{args.upload_id}")
    if status != 200 or not isinstance(upload, dict):
        raise RuntimeError(f"Upload record tidak ditemukan: HTTP {status} {upload}")
    if str(upload.get("source_job_id") or "") != args.job_id:
        raise RuntimeError("Upload ID tidak dimiliki job target; purge dibatalkan.")
    if str(upload.get("video_url") or "") != args.video_url:
        raise RuntimeError("Video URL tidak sama dengan target; purge dibatalkan.")
    clip_name = str(upload.get("clip_name") or "").strip()
    clip_url = str(upload.get("clip_url") or "").strip()
    if not clip_name:
        raise RuntimeError("Nama clip target kosong; purge dibatalkan.")
    duration = actual_clip_duration(clip_url)
    if duration > 5.0:
        raise RuntimeError(
            f"Clip aktual {duration:.3f} detik, bukan output rusak <=5 detik; purge dibatalkan."
        )
    print(f"Output rusak terverifikasi: {clip_name} ({duration:.3f} detik)", flush=True)

    tiktok_records = tiktok_uploads_for_clip(args.job_id, clip_url)
    confirmed_tiktok = [
        item
        for item in tiktok_records
        if item.get("upload_confirmed") is True or item.get("profile_url")
    ]
    if confirmed_tiktok:
        if len(confirmed_tiktok) != 1:
            raise RuntimeError(
                f"Ditemukan {len(confirmed_tiktok)} post TikTok terkonfirmasi; purge otomatis dibatalkan."
            )
        caption = str(confirmed_tiktok[0].get("caption") or "").strip()
        if not caption:
            raise RuntimeError("Caption post TikTok target kosong; purge otomatis dibatalkan.")
        subprocess.run(
            [
                sys.executable,
                "/app/scripts/delete-tiktok-studio-post.py",
                "--caption",
                caption,
            ],
            check=True,
            timeout=120,
        )

    # Stop both platform uploaders for this exact corrupt file. The TikTok
    # worker can start immediately after YouTube fails, so stopping YouTube
    # alone leaves the job protected and makes the UI deletion fail forever.
    stopped = terminate_exact_uploaders(clip_name)
    print(f"Uploader YouTube/TikTok dihentikan: {stopped or 'sudah berhenti'}", flush=True)

    terminal_status = ""
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        status, current = api_json(f"/api/youtube/uploads/{args.upload_id}")
        if status == 404:
            terminal_status = "removed"
            break
        if isinstance(current, dict):
            terminal_status = str(current.get("status") or "")
            if terminal_status in {"failed", "cancelled"}:
                break
        time.sleep(0.5)
    if terminal_status not in {"failed", "cancelled", "removed"}:
        raise RuntimeError(
            f"Uploader belum terminal setelah dihentikan: {terminal_status or 'unknown'}"
        )

    tiktok_deadline = time.monotonic() + 30
    while time.monotonic() < tiktok_deadline:
        tiktok_records = tiktok_uploads_for_clip(args.job_id, clip_url)
        if all(
            str(item.get("status") or "") not in {"queued", "running"}
            for item in tiktok_records
        ):
            break
        time.sleep(0.5)
    else:
        raise RuntimeError("Uploader TikTok belum terminal setelah dihentikan.")

    newly_confirmed_tiktok = [
        item for item in tiktok_records if item.get("upload_confirmed") is True
    ]
    if newly_confirmed_tiktok and not confirmed_tiktok:
        if len(newly_confirmed_tiktok) != 1:
            raise RuntimeError(
                "Lebih dari satu TikTok terkonfirmasi tepat sebelum uploader dihentikan."
            )
        caption = str(newly_confirmed_tiktok[0].get("caption") or "").strip()
        subprocess.run(
            [
                sys.executable,
                "/app/scripts/delete-tiktok-studio-post.py",
                "--caption",
                caption,
            ],
            check=True,
            timeout=120,
        )

    # Remove the source job as soon as both subprocesses are terminal. This
    # prevents the automatic uploader sweeper from immediately queuing the same
    # 2-second file on another platform while remote YouTube cleanup runs.
    status, payload = api_json(f"/api/jobs/{args.job_id}", method="DELETE")
    if status != 200:
        raise RuntimeError(f"Gagal menghapus card job: HTTP {status} {payload}")
    print(f"Card dan output lokal terhapus: {args.job_id}", flush=True)

    subprocess.run(
        [
            sys.executable,
            "/app/scripts/delete-youtube-studio-video.py",
            args.video_url,
        ],
        check=True,
        timeout=90,
    )
    print(f"Remote YouTube terhapus: {args.video_url}", flush=True)

    if terminal_status != "removed":
        status, payload = api_json(
            f"/api/youtube/uploads/{args.upload_id}",
            method="DELETE",
        )
        if status != 200:
            raise RuntimeError(f"Gagal menghapus record upload: HTTP {status} {payload}")
        print(f"Record upload terhapus: {args.upload_id}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
