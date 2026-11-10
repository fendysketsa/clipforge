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


def test_dialog_readiness_retry_resumes_exact_existing_id_once_even_after_legacy_restart(draft,monkeypatch):
    draft.error='Video pasca-restart belum terverifikasi. ID draft aktif berubah; perubahan metadata dihentikan.'
    draft.logs=[api.YOUTUBE_RESTART_VERIFY_MARKER]
    queued=[]
    monkeypatch.setattr(api,'queue_youtube_upload_jobs',lambda rows:queued.extend(rows))
    assert api.queue_youtube_draft_recoveries_once()==1
    result=queued[0]
    assert (result.id,result.video_url,result.title,result.description,result.visibility,result.publish_at)==(
        draft.id,draft.video_url,draft.title,draft.description,draft.visibility,draft.publish_at)
    command=api.build_youtube_restart_verification_command(result)
    assert command[2]=='verify-upload' and draft.video_url in command and draft.clip_url not in command
    api.set_youtube_upload(draft.id,status='failed',error=draft.error,logs=[])
    assert api.queue_youtube_draft_recoveries_once()==0


@pytest.mark.parametrize('risk',['claimed','confirmed','dry_run','accepted_final','invalid_id','already_attempted','durable_flag','old','other_success'])
def test_dialog_readiness_retry_preserves_unknown_or_confirmed_remote_states(draft,monkeypatch,risk):
    draft.error='ID draft aktif berubah; perubahan metadata dihentikan.'
    if risk=='claimed':draft.logs.append(api.YOUTUBE_CLAIM_ABORT_PREFIX+' Content ID')
    if risk=='confirmed':draft.upload_confirmed=True
    if risk=='dry_run':draft.dry_run=True
    if risk=='accepted_final':draft.logs.append('Tombol final diklik dan diterima: Simpan')
    if risk=='invalid_id':draft.video_url='not-a-video-id'
    if risk=='already_attempted':draft.logs.append('DRAFT_UI_READY_RECOVERY_ONCE:v1')
    if risk=='durable_flag':draft.draft_ui_recovery_attempted=True
    if risk=='old':draft.updated_at='2020-01-01T00:00:00+00:00'
    if risk=='other_success':
        api.youtube_uploads['success']=draft.model_copy(update={'id':'success','status':'completed','upload_confirmed':True})
    monkeypatch.setattr(api,'queue_youtube_upload_jobs',lambda rows:pytest.fail('unsafe retry queued'))
    assert api.queue_youtube_draft_recoveries_once()==0
