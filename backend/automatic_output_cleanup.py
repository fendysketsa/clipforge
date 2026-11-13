"""Decide when cron may discard a local output, never a remote post."""
from __future__ import annotations

import automatic_retry

MAX_RECOVERY_ATTEMPTS = 3
BEFORE_FILE_FAILURE = "UPLOAD_FAILED_BEFORE_FILE_SELECTION:"
EXHAUSTED_BEFORE_FILE = "AUTOMATIC_UPLOAD_RECOVERY_EXHAUSTED_BEFORE_FILE:"


def terminal_reason(qc: dict, youtube: list, tiktok: list) -> str | None:
    """Unknown remote outcomes and active workers always retain their media."""
    youtube = [row for row in youtube if not row.dry_run]
    tiktok = [row for row in tiktok if not row.dry_run]
    if any(row.status in {"queued", "running"} for row in [*youtube, *tiktok]):
        return None
    for row in youtube:
        if row.status == "completed" and row.upload_confirmed and row.video_url:
            continue
        if (row.video_url or row.upload_confirmed or row.file_selection_started or any(str(line).startswith((
                "Video dipilih:", "Menyerahkan file ke YouTube Studio:",
                "Transfer file ke Chrome", "VIDEO_URL:", "REMOTE_UPLOAD_CHECKPOINT:",
                "UPLOAD_CONFIRMED:")) for line in row.logs)):
            return None
        # A missing id or a timeout alone does not prove no remote submission.
        if not any(str(line).startswith(EXHAUSTED_BEFORE_FILE) for line in row.logs):
            return None
    for row in tiktok:
        if row.status == "completed" and row.upload_confirmed and row.profile_url:
            continue
        if (row.profile_url or row.upload_confirmed or row.resume_existing_draft_only
                or automatic_retry.tiktok_submission_possible(row.logs,
                    started=row.submission_started, accepted=row.submission_accepted)):
            return None
        if not automatic_retry.tiktok_retry_reason(row.error, row.logs):
            return None
        if automatic_retry.retry_count(row) < automatic_retry.MAX_RETRIES:
            return None
    decision = (qc.get("audit") or {}).get("decision")
    if qc.get("status") == "reviewed" and decision == "DROP_SOURCE":
        return "long_qc_drop_source"
    if qc.get("status") == "reviewed" and decision == "REPAIR_ONCE":
        # The existing repair executor only supports Shorts. Discard this
        # Long and let production select another source, without a fake PASS.
        return "long_repair_unavailable"
    if qc.get("cleanup_requested_reason"):
        return qc["cleanup_requested_reason"]
    if any(row.status == "failed" and any(str(line).startswith(EXHAUSTED_BEFORE_FILE)
            for line in row.logs) for row in youtube):
        return "youtube_recovery_exhausted_before_file"
    if any(row.status == "failed" for row in tiktok):
        return "tiktok_recovery_exhausted_before_post"
    return None


def record_review_attempt(result: dict, previous: dict) -> dict:
    record = {**result, "review_attempts": int(previous.get("review_attempts", 0)) + 1}
    if result.get("status") != "reviewed" and record["review_attempts"] >= MAX_RECOVERY_ATTEMPTS:
        record["cleanup_requested_reason"] = "long_qc_unavailable_exhausted"
    return record
