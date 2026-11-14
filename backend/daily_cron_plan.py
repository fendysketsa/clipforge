"""Daily production accounting, independent of future Studio backlog.

Only scheduler-owned artifacts count. A rendered or unresolved artifact reserves
its own slot; only a verified remote upload is reported as uploaded.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

LANES = {"scheduled_short": "Short terjadwal", "private_short": "Short Private", "long": "Long clip"}


def wib_day(value: str) -> str | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(ZoneInfo("Asia/Jakarta")).date().isoformat()
    except (ValueError, TypeError, AttributeError):
        return None


def build_plan(*, now: datetime, targets: dict[str, int], jobs: list[dict[str, Any]],
               runs: list[dict[str, Any]], uploads: list[dict[str, Any]],
               attempts: list[dict[str, Any]]) -> dict[str, Any]:
    day = now.astimezone(ZoneInfo("Asia/Jakarta")).date().isoformat()
    owners: dict[str, dict[str, Any]] = {}
    rejected: set[str] = set()
    for run in runs:
        if run.get("trigger") != "schedule":
            continue
        request = run.get("request", {})
        for item in run.get("processed", []):
            for field in ("job_id", "repair_job_id", "long_job_id"):
                job_id = item.get(field)
                if not job_id:
                    continue
                snapshot = item.get("paired_short_snapshot") or {}
                owners[job_id] = {"lane": "long" if field == "long_job_id" else request.get("cron_daily_lane") or "scheduled_short",
                                  "day": request.get("cron_production_day") or (wib_day(snapshot.get("created_at")) if field != "long_job_id" else None)}
                if item.get("status") in {"copyright_claimed", "ai_review_failed", "upload_failed", "failed", "discarded"}:
                    rejected.add(job_id)
    for row in attempts:
        if row.get("job_id"):
            owners[row["job_id"]] = {"lane": "long", "day": row.get("day")}
            if row.get("qc_decision") in {"DROP_SOURCE", "REPAIR_ONCE"} or row.get("disposition") == "deleted_terminal_output":
                rejected.add(row["job_id"])
    for job in jobs:
        req = job.get("request", {})
        if req.get("cron_daily_lane"):
            owners[job["id"]] = {"lane": req["cron_daily_lane"], "day": req.get("cron_production_day") or wib_day(job.get("created_at"))}
        elif job["id"] in owners and not owners[job["id"]].get("day"):
            owners[job["id"]]["day"] = wib_day(job.get("created_at"))
    slots: dict[tuple[str, str], dict[str, Any]] = {}
    remote_slots: dict[str, tuple[str, str]] = {}
    recorded_clips: set[tuple[str, str]] = set()
    uploaded_jobs: set[str] = set()
    priority = {"held": 1, "active": 2, "uploaded": 3}
    for row in sorted(uploads, key=lambda item: item.get("created_at", "")):
        job_id = row.get("source_job_id")
        owner = owners.get(job_id)
        lane = row.get("cron_daily_lane") or (owner or {}).get("lane")
        if not lane or row.get("dry_run") or row.get("claimed"):
            continue
        stamp = row.get("cron_production_day") or (owner or {}).get("day")
        if not stamp:
            stamp = wib_day(row.get("created_at"))
        if stamp != day:
            if row.get("verified") and owner and owner.get("day") == day:
                # An identical render reused an older remote video. It cannot
                # become a second video in today's production count.
                rejected.add(job_id)
            continue
        if not row.get("cron_daily_lane") and lane != "long" and row.get("visibility") == "private" and not row.get("publish_at"):
            lane = "private_short"
        state = "uploaded" if row.get("verified") else "active" if row.get("status") in {"queued", "running"} else "held" if row.get("remote_id") or row.get("uncertain") else None
        if not state:
            continue
        key = (job_id, row.get("clip_url", ""))
        recorded_clips.add(key)
        if row.get("remote_id") in remote_slots:
            key = remote_slots[row["remote_id"]]
        elif row.get("remote_id"):
            remote_slots[row["remote_id"]] = key
        if state == "uploaded":
            uploaded_jobs.add(job_id)
        previous = slots.get(key)
        if not previous or priority[state] > priority[previous["state"]]:
            slots[key] = {"lane": lane, "state": state}
    for job in jobs:
        owner = owners.get(job["id"])
        if not owner or owner["day"] != day or job["id"] in rejected:
            continue
        if job.get("status") not in {"queued", "running", "completed"}:
            continue
        clips = job.get("clips", [])
        if job["status"] in {"queued", "running"} and not clips:
            if job["id"] not in uploaded_jobs:
                expected = max(1, min(5, int(job.get("request", {}).get("top") or 1))) if owner["lane"] != "long" else 1
                already_recorded = sum(key[0] == job["id"] for key in recorded_clips)
                for index in range(max(0, expected - already_recorded)):
                    slots[(job["id"], f"pending-{index}")] = {"lane": owner["lane"], "state": "active"}
        for clip in clips:
            key = (job["id"], clip["url"])
            if key in recorded_clips or clip.get("render_qc_blocking") is True:
                continue
            slots[key] = {"lane": owner["lane"], "state": "ready"}
    lanes = {}
    for lane, target in targets.items():
        counts = {state: sum(row["lane"] == lane and row["state"] == state for row in slots.values())
                  for state in ("uploaded", "active", "ready", "held")}
        used = sum(counts.values())
        lanes[lane] = {"label": LANES[lane], "target": target, **counts, "used": used, "remaining": max(0, target - used)}
    return {"version": 1, "enabled": True, "day": day, "timezone": "Asia/Jakarta",
            "total_target": sum(targets.values()), "total_used": sum(row["used"] for row in lanes.values()),
            "total_uploaded": sum(row["uploaded"] for row in lanes.values()), "lanes": lanes}


def next_short_lane(plan: dict[str, Any]) -> str | None:
    available = [(key, plan["lanes"][key]) for key in ("scheduled_short", "private_short")
                 if plan["lanes"][key]["remaining"] > 0]
    return min(available, key=lambda item: item[1]["used"] / max(1, item[1]["target"]))[0] if available else None
