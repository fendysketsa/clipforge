"""Reconcile only an already-public remote video; never force an upload."""
import pytest
from fastapi import HTTPException

import api


VIDEO = "https://www.youtube.com/watch?v=NdEKBl4Xfrg"


def _upload(upload_id="verify", **updates):
    row = api.YouTubeUploadJob(
        id=upload_id, source_job_id="job", clip_url="/outputs/job/clips/clip.mp4",
        clip_name="clip.mp4", title="Fixture", status="failed",
        created_at=api.now_iso(), updated_at=api.now_iso(),
        video_url=VIDEO, upload_confirmed=False,
        error="Video pasca-restart belum terverifikasi",
    )
    return row.model_copy(update=updates)


def _setup(monkeypatch, payload):
    monkeypatch.setattr(api, "youtube_uploads", {})
    monkeypatch.setattr(api, "save_youtube_uploads_unlocked", lambda: None)
    api.youtube_uploads["verify"] = _upload()
    monkeypatch.setattr(api, "youtube_data_api_get", lambda *a, **k: payload)
    scheduled = []
    monkeypatch.setattr(api, "schedule_completed_upload_cleanup", scheduled.append)
    return scheduled


def test_public_video_is_reconciled_and_local_cleanup_scheduled(monkeypatch):
    scheduled = _setup(monkeypatch, {"items": [{"id": "NdEKBl4Xfrg", "status": {"privacyStatus": "public"}}]})
    result = api.verify_youtube_upload_is_public("verify", api.YouTubePublicVerifyRequest(confirm=True))
    assert result.status == "completed" and result.upload_confirmed is True
    assert result.error is None and scheduled == ["verify"]


@pytest.mark.parametrize("payload", [
    {"items": []},
    {"items": [{"id": "NdEKBl4Xfrg", "status": {"privacyStatus": "private"}}]},
    {"items": [{"id": "other", "status": {"privacyStatus": "public"}}]},
])
def test_absent_private_or_mismatched_video_is_rejected(monkeypatch, payload):
    scheduled = _setup(monkeypatch, payload)
    with pytest.raises(HTTPException) as exc:
        api.verify_youtube_upload_is_public("verify", api.YouTubePublicVerifyRequest(confirm=True))
    assert exc.value.status_code == 409
    assert api.youtube_uploads["verify"].upload_confirmed is False
    assert scheduled == []


def test_requires_explicit_operator_confirmation(monkeypatch):
    scheduled = _setup(monkeypatch, {"items": [{"id": "NdEKBl4Xfrg", "status": {"privacyStatus": "public"}}]})
    with pytest.raises(HTTPException) as exc:
        api.verify_youtube_upload_is_public("verify", api.YouTubePublicVerifyRequest())
    assert exc.value.status_code == 409
    assert scheduled == []
