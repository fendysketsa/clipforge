"""Small dashboard views; persisted upload evidence remains complete."""
from __future__ import annotations

# These earlier events still drive queue/retry/claim indicators in the UI.
_INDICATOR_PREFIXES = (
    "Video dipilih:", "Menyerahkan file ke YouTube Studio:", "REMOTE_UPLOAD_CHECKPOINT",
    "POST_SUBMIT_INTENT:", "POST_API_ACCEPTED:", "CLAIMED_UPLOAD_ABORTED:",
    "THUMBNAIL_SKIPPED",
)


def compact_upload(upload):
    updates = {"performance_snapshots": []}
    if upload.status not in {"queued", "running"}:
        tail = max(0, len(upload.logs) - 8)
        updates["logs"] = [line for index, line in enumerate(upload.logs)
                           if index >= tail or line.startswith(_INDICATOR_PREFIXES)]
    return upload.model_copy(update=updates)
