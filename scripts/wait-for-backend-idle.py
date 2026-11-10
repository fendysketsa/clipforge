#!/usr/bin/env python3
"""Wait for deployment safety without changing jobs or upload records."""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import subprocess
import time
import urllib.request


ENDPOINTS = ("jobs", "youtube/uploads", "tiktok/uploads", "automation/viral-cc")
MEDIA_PROCESS = re.compile(
    r"(^|[/\s])(ffmpeg|ffprobe|yt-dlp)(\s|$)"
    r"|(?:clipper|youtube_uploader|tiktok_uploader|long_animate)\.py(?:\s|$)"
    r"|-m\s+yt_dlp(?:\s|$)"
)


def classify_work(snapshots, recover_stalled_cron, now, allow_capacity_wait=False):
    blockers, stalled = [], []
    for endpoint in ENDPOINTS[:-1]:
        for row in snapshots[endpoint]:
            if row.get("status") in {"queued", "running"}:
                blockers.append(
                    f"{endpoint}:{row['id']} ({row['status']}, "
                    f"stage={row.get('progress_stage') or '-'}, updated={row.get('updated_at') or '-'})"
                )
    job_ids = {row["id"] for row in snapshots["jobs"]}
    for run in snapshots["automation/viral-cc"]:
        if run.get("status") not in {"queued", "running"}:
            continue
        if (allow_capacity_wait and run.get("trigger") == "schedule"
                and run.get("progress_stage") == "cron_capacity_wait"
                and run.get("processed") and all(
                    item.get("job_id") and item.get("job_status") == "completed"
                    and item.get("status") == "awaiting_upload"
                    for item in run["processed"])):
            # Its saved batch resumes after restart. API jobs/uploads and real
            # subprocesses are still checked independently; none may be active.
            continue
        children = {
            str(item.get(key) or "")
            for item in run.get("processed", [])
            for key in ("job_id", "long_job_id")
        } - {""}
        try:
            updated = datetime.fromisoformat(run["updated_at"])
            old = updated.tzinfo is not None and updated <= now - timedelta(minutes=15)
        except (KeyError, TypeError, ValueError):
            old = False
        if (recover_stalled_cron and run.get("trigger") == "schedule"
                and run.get("progress_stage") in {"social_upload", "youtube_upload", "resume_pending_upload"}
                and old and children and not children.intersection(job_ids)):
            stalled.append(run["id"])
        else:
            blockers.append(
                f"automation/viral-cc:{run['id']} ({run['status']}, "
                f"stage={run.get('progress_stage') or '-'}, updated={run.get('updated_at') or '-'})"
            )
    return blockers, stalled


def read_snapshots(base_url):
    snapshots = {}
    for endpoint in ENDPOINTS:
        with urllib.request.urlopen(base_url.rstrip("/") + "/" + endpoint, timeout=15) as response:
            rows = json.load(response)
        if not isinstance(rows, list) or any(not isinstance(row, dict) or not row.get("id") for row in rows):
            raise ValueError(f"Unexpected response from {endpoint}; activation stopped safely.")
        snapshots[endpoint] = rows
    return snapshots


def active_subprocesses(container):
    # Docker parses ps output by PID to map/filter the container's processes.
    # Requesting args alone makes the daemon reject it before returning rows.
    commands = subprocess.check_output(["docker", "top", container, "-eo", "pid,args"], text=True)
    return [line for line in commands.splitlines()[1:] if MEDIA_PROCESS.search(line)]


def wait_until_idle(*, base_url, container, recover_stalled_cron, wait_seconds, poll_seconds=15, allow_capacity_wait=False):
    deadline = time.monotonic() + wait_seconds
    while True:
        blockers, stalled = classify_work(
            read_snapshots(base_url), recover_stalled_cron, datetime.now(timezone.utc), allow_capacity_wait
        )
        if not blockers:
            # Missing/terminal API rows alone cannot justify interrupting media work.
            processes = active_subprocesses(container)
            if processes:
                blockers.append(f"{len(processes)} renderer/downloader/uploader subprocess(es) still active")
        if not blockers:
            print(f"Idle queues and subprocesses verified; orphaned cron runs eligible for recovery: {len(stalled)}", flush=True)
            return stalled
        message = "; ".join(blockers)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SystemExit("Activation timed out safely; active work: " + message)
        print(f"Waiting for active work ({remaining:.0f}s remaining): {message}", flush=True)
        time.sleep(min(poll_seconds, remaining))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8010/api/")
    parser.add_argument("--container", default="fendy-clipper-backend")
    parser.add_argument("--recover-stalled-cron", action="store_true")
    parser.add_argument("--allow-capacity-wait", action="store_true")
    parser.add_argument("--wait-seconds", type=int, default=21600)
    parser.add_argument("--state-file", type=Path, required=True)
    args = parser.parse_args()
    if args.wait_seconds < 0:
        parser.error("--wait-seconds must be nonnegative")
    stalled = wait_until_idle(
        base_url=args.base_url, container=args.container,
        recover_stalled_cron=args.recover_stalled_cron, wait_seconds=args.wait_seconds,
        allow_capacity_wait=args.allow_capacity_wait,
    )
    previous = json.loads(args.state_file.read_text()) if args.state_file.exists() and args.state_file.stat().st_size else {}
    args.state_file.write_text(json.dumps({
        "stalled_run_ids": sorted(set(previous.get("stalled_run_ids", [])) | set(stalled)),
    }))


if __name__ == "__main__":
    main()
