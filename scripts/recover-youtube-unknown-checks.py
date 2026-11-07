#!/usr/bin/env python3
"""Release one stuck Checks worker and resume its existing remote draft."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import time
import urllib.request
from urllib.error import HTTPError

API = "http://127.0.0.1:8010/api/"
UNKNOWN = ("Checks belum menampilkan hasil final;", "Checks masih berjalan; status modal belum terbaca,")


def request(path, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(API + path, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)


def eligible(row):
    logs = row.get("logs", [])
    state = row.get("status")
    recent_failed_checks = False
    if state == "failed":
        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(row["updated_at"])).total_seconds()
            recent_failed_checks = 0 <= age <= 7200 and any(
                text in (row.get("error") or "")
                for text in ("Step 3 Checks belum selesai", "Checks tidak terbaca", "CHECKS_STATUS_UNREADABLE")
            )
        except (KeyError, ValueError, TypeError):
            pass
    return bool(
        (state == "running" or recent_failed_checks) and not row.get("dry_run")
        and not row.get("upload_confirmed")
        and re.fullmatch(r"https://www\.youtube\.com/watch\?v=[A-Za-z0-9_-]{11}", row.get("video_url") or "")
        and logs and (recent_failed_checks or logs[-1].startswith(UNKNOWN))
        and sum(line.startswith(UNKNOWN) for line in logs) >= 3
        and not any(line.startswith(("Tombol final diklik", "UPLOAD_CONFIRMED:", "CHECKS_DRAFT_RECOVERY_ONCE:", "CLAIMED_UPLOAD_ABORTED:", "Memulihkan konfirmasi upload dari video tersimpan")) for line in logs)
    )


def matching_worker(args, row):
    if len(args) < 4 or Path(args[1]).name != "youtube_uploader.py" or args[2] != "upload":
        return False
    def value(flag):
        return args[args.index(flag) + 1] if flag in args and args.index(flag) + 1 < len(args) else ""
    return bool(
        value("--title") == row.get("title")
        and value("--publish-at") == (row.get("publish_at") or "")
        and Path(args[3]).stem.startswith(Path(row["clip_name"]).stem)
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upload-id")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    rows = request("youtube/uploads")
    candidates = [row for row in rows if eligible(row) and (not args.upload_id or row["id"] == args.upload_id)]
    if not candidates:
        print(json.dumps({"action": "none", "reason": "no eligible stuck Checks worker"}))
        return
    if len(candidates) != 1:
        raise RuntimeError("Recovery requires exactly one unambiguous running upload")
    row = candidates[0]
    pids = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            argv = (entry / "cmdline").read_bytes().decode().strip("\0").split("\0")
        except (OSError, UnicodeError):
            continue
        if matching_worker(argv, row):
            pids.append(int(entry.name))
    if row["status"] == "running" and (len(pids) != 1 or sum(r.get("status") == "running" for r in rows) != 1):
        raise RuntimeError("Cannot identify exactly one uploader process for this checkpoint")
    plan = {"action": "resume_existing_draft", "upload_id": row["id"], "video_url": row["video_url"], "pid": pids[0] if row["status"] == "running" else None}
    if not args.apply:
        print(json.dumps(plan))
        return
    # Revalidate immediately before stopping only this worker. The backend
    # remains up and owns all status writes and subsequent queue transitions.
    current = request("youtube/uploads/" + row["id"])
    if not eligible(current) or current.get("video_url") != row["video_url"]:
        raise RuntimeError("Checkpoint changed before recovery; no process stopped")
    if current["status"] == "running":
        argv = Path(f"/proc/{pids[0]}/cmdline").read_bytes().decode().strip("\0").split("\0")
        if not matching_worker(argv, current):
            raise RuntimeError("Uploader process identity changed; no process stopped")
        os.kill(pids[0], signal.SIGTERM)
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        current = request("youtube/uploads/" + row["id"])
        if current.get("status") != "running":
            break
        time.sleep(.5)
    else:
        raise RuntimeError("Backend has not settled the original worker; checkpoint left untouched")
    if current.get("status") == "completed" and current.get("upload_confirmed"):
        print(json.dumps({**plan, "result": "already_confirmed"}))
        return
    if current.get("status") != "failed" or current.get("video_url") != row["video_url"]:
        raise RuntimeError("Unexpected terminal checkpoint; not requeued")
    if any(line.startswith("CLAIMED_UPLOAD_ABORTED:") for line in current.get("logs", [])):
        raise RuntimeError("Claim detected; recovery held")
    try:
        resumed = request("jobs/" + row["source_job_id"] + "/youtube-uploads", {
            "clip_url": row["clip_url"], "visibility": row["visibility"],
            "publish_at": row.get("publish_at"), "playlist": row.get("playlist", ""),
            "made_for_kids": row.get("made_for_kids", False),
        })
    except HTTPError as exc:
        if exc.code != 404:
            raise
        print(json.dumps({**plan, "result": "awaiting_api_activation", "reason": "local source job is gone; new API recovers directly from the remote record"}))
        return
    if resumed["id"] != row["id"] or resumed.get("video_url") != row["video_url"]:
        raise RuntimeError("Recovery endpoint did not preserve the original checkpoint")
    print(json.dumps({**plan, "result": resumed["status"]}))


if __name__ == "__main__":
    main()
