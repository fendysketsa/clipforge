from datetime import datetime, timezone
import pytest
import api


@pytest.fixture
def draft(monkeypatch):
    row = api.YouTubeUploadJob(
        id="orphan-draft", source_job_id="removed-job", clip_url="/outputs/removed-job/long.mp4",
        clip_name="resume_cerita_long.mp4", title="Existing reviewed title", description="Reviewed description",
        visibility="public", publish_at="2026-12-08T13:30:00+00:00", status="failed",
        created_at="2026-11-07T00:00:00+00:00", updated_at=datetime.now(timezone.utc).isoformat(),
        video_url="https://www.youtube.com/watch?v=abcDEF12345",
        error="Step 3 Checks belum selesai/tercentang", thumbnail_attached=True, playlist_confirmed=True,
    )
    monkeypatch.setattr(api, "jobs", {})
    monkeypatch.setattr(api, "youtube_uploads", {row.id: row})
    return row


def test_missing_job_resumes_exact_remote_id_without_local_file_or_new_metadata(draft):
    result = api.create_youtube_upload_record(draft.source_job_id, api.YouTubeUploadRequest(clip_url=draft.clip_url))
    assert result.id == draft.id and result.status == "queued"
    assert result.video_url == draft.video_url
    assert result.title == draft.title and result.description == draft.description
    assert result.visibility == draft.visibility and result.publish_at == draft.publish_at
    command = api.build_youtube_restart_verification_command(result)
    assert command[2] == "verify-upload" and draft.video_url in command
    assert draft.clip_url not in command


def test_missing_job_dry_run_does_not_finalize_remote_video(draft):
    with pytest.raises(api.HTTPException) as exc:
        api.create_youtube_upload_record(draft.source_job_id, api.YouTubeUploadRequest(clip_url=draft.clip_url, dry_run=True))
    assert exc.value.status_code == 404
    assert api.youtube_uploads[draft.id].status == "failed"


def test_claimed_orphan_draft_stays_held(draft):
    draft.logs.append(api.YOUTUBE_CLAIM_ABORT_PREFIX + " Content ID")
    with pytest.raises(api.HTTPException) as exc:
        api.create_youtube_upload_record(draft.source_job_id, api.YouTubeUploadRequest(clip_url=draft.clip_url))
    assert exc.value.status_code == 409
    assert api.youtube_uploads[draft.id].status == "failed"


def test_automatic_orphan_resume_is_once_and_keeps_saved_publication_target(draft, monkeypatch):
    monkeypatch.setenv("YOUTUBE_AUTO_RECOVER_DRAFTS", "true")
    queued = []
    monkeypatch.setattr(api, "queue_youtube_upload_jobs", lambda rows: queued.extend(rows))
    assert api.queue_youtube_draft_recoveries_once() == 1
    assert len(queued) == 1 and queued[0].id == draft.id
    assert queued[0].publish_at == draft.publish_at
    api.set_youtube_upload(draft.id, status="failed")
    assert api.queue_youtube_draft_recoveries_once() == 0


def test_missing_job_prefers_active_duplicate_over_old_failed_draft(draft):
    active = draft.model_copy(update={"id": "active", "status": "running"})
    api.youtube_uploads[active.id] = active
    result = api.create_youtube_upload_record(draft.source_job_id, api.YouTubeUploadRequest(clip_url=draft.clip_url))
    assert result.id == active.id
    assert api.youtube_uploads[draft.id].status == "failed"
