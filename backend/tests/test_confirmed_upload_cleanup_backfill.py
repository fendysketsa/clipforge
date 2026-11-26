"""A confirmed remote upload must not keep its local clip, manual or cron."""
import api


def _upload(uid, **updates):
    row = api.YouTubeUploadJob(
        id=uid,
        source_job_id='job-' + uid,
        clip_url='/outputs/job-' + uid + '/clips/clip.mp4',
        clip_name='clip.mp4',
        title='Fixture',
        status='completed',
        created_at=api.now_iso(),
        updated_at=api.now_iso(),
        upload_confirmed=True,
        video_url='https://www.youtube.com/watch?v=' + uid,
    )
    return row.model_copy(update=updates)


def test_backfill_rearms_confirmed_uploads_without_a_cleanup_marker(monkeypatch):
    scheduled = []
    monkeypatch.setattr(api, 'youtube_uploads', {})
    monkeypatch.setattr(api, 'schedule_completed_upload_cleanup', scheduled.append)
    monkeypatch.setattr(api, 'save_youtube_uploads_unlocked', lambda: None)

    old = _upload('old', publish_at='2026-12-06T03:00:00+00:00')
    fresh = _upload('fresh', clip_delete_after=api.now_iso())
    done = _upload('done', clip_deleted_at=api.now_iso())
    pending_remote = _upload('pending', status='queued', video_url=None, upload_confirmed=False)
    trial = _upload('dry', dry_run=True)

    for row in (old, fresh, done, pending_remote, trial):
        api.youtube_uploads[row.id] = row

    assert api.schedule_confirmed_upload_cleanup_backfill() == 1
    assert scheduled == ['old']
    assert api.youtube_uploads['old'].clip_delete_after
    assert api.youtube_uploads['fresh'].clip_delete_after == fresh.clip_delete_after
    assert api.youtube_uploads['done'].clip_deleted_at
    assert api.schedule_confirmed_upload_cleanup_backfill() == 0
