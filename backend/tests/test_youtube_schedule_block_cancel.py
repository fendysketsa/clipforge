"""A confirmed Content ID claim cancels only the local future schedule."""
from datetime import datetime, timedelta, timezone

import api

FUTURE = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
PAST = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()


def upload(upload_id, *, logs=(), publish_at=FUTURE, confirmed=True, status='completed'):
    return api.YouTubeUploadJob(
        id=upload_id, source_job_id='job-' + upload_id, clip_url='/clip.mp4', clip_name='clip.mp4',
        status=status, created_at=PAST, updated_at=PAST, title='Short', visibility='public',
        publish_at=publish_at, upload_confirmed=confirmed,
        logs=list(logs), clip_sha256='0' * 64,
    )


def test_claim_cancels_future_schedule_and_keeps_remote_identity(monkeypatch):
    claimed = upload('claimed', logs=[api.YOUTUBE_CLAIM_ABORT_PREFIX + ' zero_active_claim_policy'])
    claimed.video_url = 'https://www.youtube.com/watch?v=' + 'b' * 11
    monkeypatch.setattr(api, 'youtube_uploads', {'claimed': claimed})
    monkeypatch.setattr(api, 'save_youtube_uploads_unlocked', lambda: None)
    assert api.cancel_confirmed_blocked_youtube_uploads() == 1
    after = api.youtube_uploads['claimed']
    assert after.status == 'cancelled' and after.publish_at is None
    assert after.video_url == claimed.video_url
    assert any(line.startswith('REMOTE_BLOCK_CONFIRMED:') for line in after.logs)


def test_scheduled_private_video_without_claim_keeps_its_slot(monkeypatch):
    row = upload('scheduled', logs=['SCHEDULE_PERSISTED_CONFIRMED'])
    row.video_url = 'https://www.youtube.com/watch?v=' + 'c' * 11
    monkeypatch.setattr(api, 'youtube_uploads', {'scheduled': row})
    monkeypatch.setattr(api, 'save_youtube_uploads_unlocked', lambda: None)
    assert api.cancel_confirmed_blocked_youtube_uploads() == 0
    assert api.youtube_uploads['scheduled'].publish_at == FUTURE


def test_past_schedule_is_not_cancelled(monkeypatch):
    row = upload('past', logs=[api.YOUTUBE_CLAIM_ABORT_PREFIX + ' claim'], publish_at=PAST)
    monkeypatch.setattr(api, 'youtube_uploads', {'past': row})
    monkeypatch.setattr(api, 'save_youtube_uploads_unlocked', lambda: None)
    assert api.cancel_confirmed_blocked_youtube_uploads() == 0
