"""Apply an operator's exact cleanup list, preserving ambiguous remote work."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.parse import unquote
from uuid import uuid4


def cleanup_block(row: dict, outputs: Path) -> str | None:
    if row.get("status") not in {"failed", "cancelled"}:
        return "status_changed"
    if any(row.get(key) for key in ("profile_url", "upload_confirmed", "submission_started", "submission_accepted")):
        return "remote_outcome_reserved"
    if any(str(line).startswith(("POST_SUBMIT_INTENT:", "POST_API_ACCEPTED:", "REMOTE_POST_CONFIRMED:")) for line in row.get("logs", [])):
        return "remote_outcome_reserved"
    url = row.get("clip_url", "")
    if not isinstance(url, str) or not url.startswith("/outputs/"):
        return "invalid_local_path"
    root = outputs.resolve()
    path = (root / unquote(url.removeprefix("/outputs/"))).resolve()
    if root not in path.parents:
        return "invalid_local_path"
    if path.exists():
        return "local_media_retained"
    return None


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            os.chmod(temporary, 0o600)
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def apply_requested_cleanup(request_path: Path, uploads: dict, outputs: Path, save) -> dict:
    """Called under the upload lock before workers start; never deletes media/posts."""
    if not request_path.is_file():
        return {"removed": 0, "skipped": 0}
    request = json.loads(request_path.read_text(encoding="utf-8"))
    if not isinstance(request, dict) or request.get("schema") != 1 or request.get("authorized_by") != "operator":
        return {"removed": 0, "skipped": 0}
    targets = request.get("items", [])
    if not isinstance(targets, list) or len(targets) > 500:
        return {"removed": 0, "skipped": 0}
    removed = {}
    results = []
    for target in targets:
        if not isinstance(target, dict) or target.get("state") != "pending":
            continue
        row = uploads.get(target.get("id"))
        if row is None:
            results.append((target, "already_absent"))
            continue
        data = row.model_dump() if hasattr(row, "model_dump") else dict(row)
        reason = "record_changed" if not target.get("updated_at") or data.get("updated_at") != target["updated_at"] else cleanup_block(data, outputs)
        if reason:
            results.append((target, reason))
            continue
        removed[data["id"]] = row
        results.append((target, "removed"))
    now = datetime.now(timezone.utc).isoformat()
    if removed:
        backup = request_path.parent / "failed-cleanup-audit" / f"{uuid4().hex}.json"
        write_json(backup, {"checked_at": now, "records": [row.model_dump() if hasattr(row, "model_dump") else row for row in removed.values()]})
        for upload_id in removed:
            uploads.pop(upload_id)
        try:
            save()
        except Exception:
            uploads.update(removed)
            raise
    for target, result in results:
        target.update(state="done" if result in {"removed", "already_absent"} else "skipped", result=result, checked_at=now)
    write_json(request_path, request)
    return {"removed": len(removed), "skipped": sum(target["state"] == "skipped" for target, _ in results)}
