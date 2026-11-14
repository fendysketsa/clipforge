"""Read-only activity summaries from scheduler and worker snapshots."""
from __future__ import annotations

from typing import Any


def summarize_activity(
    *, reason: str, message: str, run: dict[str, Any] | None,
    jobs: list[dict[str, Any]], uploads: list[dict[str, Any]],
    runtime: dict[str, Any],
) -> dict[str, Any]:
    activity: dict[str, Any] = {
        "state": reason, "label": {
            "disabled": "Cron nonaktif", "worker_unavailable": "Worker cron belum berjalan",
            "capacity_wait": "Menunggu kapasitas", "rights_hold": "Upload menunggu bukti hak",
            "browser_wait": "Menunggu browser Studio", "daily_target": "Target harian tercapai",
            "retry_wait": "Menunggu percobaan berikutnya", "scheduled": "Menunggu jadwal",
            "short_quota_reserved": "Slot Short hari ini terisi",
        }.get(reason, "Menunggu jadwal"),
        "detail": message, "progress_percent": None, "stage": None,
        "updated_at": runtime.get("last_checked_at"), "source_title": None,
    }
    running_uploads = [row for row in uploads if row["status"] == "running"]
    running_jobs = [row for row in jobs if row["status"] == "running"]
    if run and run["status"] in {"queued", "running"}:
        activity.update(
            state=run["status"], label=("Cron mengantre" if run["trigger"] == "schedule" else "Proses manual mengantre") if run["status"] == "queued"
            else ("Cron sedang bekerja" if run["trigger"] == "schedule" else "Proses manual berjalan"),
            detail=run.get("message") or "Menyiapkan proses berikutnya.",
            stage=run.get("progress_stage"), progress_percent=run.get("progress_percent"),
            updated_at=run["updated_at"],
        )
        owned = {str(item.get(key)) for item in run.get("processed", [])
                 for key in ("job_id", "long_job_id", "repair_job_id") if item.get(key)}
        child = next((row for row in running_jobs if row["id"] in owned), None)
        if child:
            activity["source_title"] = child.get("source_title")
    elif running_jobs:
        job = running_jobs[0]
        activity.update(
            state="running", label="Render Long berjalan" if job["request"].get("clip_mode") == "highlight_5m" else "Proses video berjalan",
            detail=job.get("progress_detail") or "Menjalankan pipeline video.",
            progress_percent=job.get("progress_percent"), stage=job.get("progress_stage"),
            updated_at=job["updated_at"], source_title=job.get("source_title"),
        )
    elif running_uploads:
        upload = running_uploads[0]
        activity.update(
            state="uploading", label=f"Upload {upload['platform']} berjalan",
            detail="Memproses antrean upload; hasil publikasi menunggu verifikasi platform.",
            stage="social_upload", updated_at=upload["updated_at"],
            source_title=upload.get("title"),
        )
    elif runtime.get("last_error") and reason != "disabled":
        activity.update(state="retry_wait", label="Pemeriksaan cron akan diulang",
                        detail=f"Pemeriksaan terakhir mengalami {runtime['last_error']}; menunggu pemeriksaan berikutnya.")
    elif reason != "disabled" and runtime.get("phase") == "checking":
        activity.update(state="checking", label="Memeriksa antrean dan jadwal",
                        detail="Memeriksa pemulihan upload, kapasitas publikasi, dan produksi video.")
    elif any(row["status"] == "queued" for row in jobs):
        activity.update(state="queued", label="Video menunggu worker",
                        detail="Pekerjaan video sudah mengantre dan menunggu giliran diproses.")
    return activity
