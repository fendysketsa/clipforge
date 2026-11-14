import json

import pytest

from failed_upload_cleanup import apply_requested_cleanup, cleanup_block


def row(**changes):
    return dict(id="failed-one", status="failed", updated_at="snapshot", clip_url="/outputs/missing.mp4", logs=[], **changes)


def request(tmp_path, items=None):
    path = tmp_path / "failed_cleanup_requests.json"
    path.write_text(json.dumps(dict(schema=1, authorized_by="operator", items=items or [dict(id="failed-one", updated_at="snapshot", state="pending")])))
    return path


def test_explicit_list_backs_up_then_removes_missing_pre_post_record_once(tmp_path):
    path = request(tmp_path)
    rows = {"failed-one": row(), "untargeted": dict(row(), id="untargeted")}
    saved = []
    result = apply_requested_cleanup(path, rows, tmp_path / "outputs", lambda: saved.append(dict(rows)))
    assert result == dict(removed=1, skipped=0)
    assert list(rows) == ["untargeted"]
    backup = next((tmp_path / "failed-cleanup-audit").glob("*.json"))
    assert json.loads(backup.read_text())["records"][0]["id"] == "failed-one"
    assert apply_requested_cleanup(path, rows, tmp_path / "outputs", lambda: saved.append(None))["removed"] == 0
    assert len(saved) == 1


@pytest.mark.parametrize("changes", [dict(profile_url="https://www.tiktok.com/@account/video/1234567890123456789"), dict(submission_started=True), dict(submission_accepted=True), dict(upload_confirmed=True), dict(logs=["POST_SUBMIT_INTENT: sent"]), dict(logs=["POST_API_ACCEPTED: accepted"])])
def test_remote_identity_and_uncertain_submissions_stay_reserved(tmp_path, changes):
    assert cleanup_block(dict(row(), **changes), tmp_path) == "remote_outcome_reserved"


def test_status_snapshot_and_available_media_protect_recoverable_work(tmp_path):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "missing.mp4").write_bytes(b"preserve")
    assert cleanup_block(row(), outputs) == "local_media_retained"
    assert cleanup_block(dict(row(), status="running"), outputs) == "status_changed"
    rows = {"failed-one": dict(row(), updated_at="new")}
    result = apply_requested_cleanup(request(tmp_path), rows, outputs, lambda: pytest.fail("must not save"))
    assert result["skipped"] == 1
    assert "failed-one" in rows


def test_path_traversal_is_never_treated_as_missing_media(tmp_path):
    assert cleanup_block(dict(row(), clip_url="/outputs/%2e%2e/protected.mp4"), tmp_path / "outputs") == "invalid_local_path"


def test_failed_persistence_restores_live_records_and_leaves_request_pending(tmp_path):
    rows = {"failed-one": row()}
    path = request(tmp_path)
    def fail():
        raise OSError("disk unavailable")
    with pytest.raises(OSError):
        apply_requested_cleanup(path, rows, tmp_path / "outputs", fail)
    assert "failed-one" in rows
    assert json.loads(path.read_text())["items"][0]["state"] == "pending"


@pytest.mark.parametrize("payload", [[], {"schema": 1, "items": [{"id": "failed-one", "state": "pending"}]}])
def test_unapproved_or_malformed_request_cannot_remove_records(tmp_path, payload):
    path = tmp_path / "request.json"
    path.write_text(json.dumps(payload))
    rows = {"failed-one": row()}
    assert apply_requested_cleanup(path, rows, tmp_path, lambda: pytest.fail("must not save"))["removed"] == 0
    assert "failed-one" in rows
