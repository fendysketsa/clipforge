from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
import api


@pytest.fixture(autouse=True)
def cron_policy(monkeypatch):
    for key, value in {
        "YOUTUBE_CRON_BUFFER_ENABLED": "true", "YOUTUBE_AUTO_SCHEDULE_ENABLED": "true",
        "YOUTUBE_CRON_PRIVATE_BUFFER_LIMIT": "5", "YOUTUBE_SCHEDULE_BACKLOG_LIMIT": "11",
        "YOUTUBE_PUBLIC_DAILY_LIMIT": "7", "YOUTUBE_PUBLIC_MIN_GAP_HOURS": "2.25",
        "YOUTUBE_CHANNEL_RECOVERY_MODE": "false", "YOUTUBE_PUBLIC_PAUSE_UNTIL": "",
        "YOUTUBE_SHORT_PUBLISH_SLOTS": "07:00,09:15,11:30,13:45,16:00,18:15,20:30",
        "YOUTUBE_LONG_PUBLISH_SLOTS": "20:30", "YOUTUBE_PUBLISH_TIMEZONE": "Asia/Jakarta",
        "YOUTUBE_SCHEDULE_MIN_LEAD_MINUTES": "30",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(api, "youtube_uploads", {})
    monkeypatch.setattr(api, "auto_viral_runs", {})
    monkeypatch.setattr(api, "youtube_recent_publication_times", lambda **_kwargs: [])


def record(index, **updates):
    values = dict(
        id=f"upload-{index}", source_job_id=f"job-{index}", clip_url=f"/outputs/job-{index}/clip.mp4",
        clip_name="clip_01.mp4", title="Video", status="completed", visibility="private",
        created_at="2026-11-03T00:00:00+00:00", updated_at="2026-11-03T00:00:00+00:00",
        video_url=f"https://www.youtube.com/watch?v=video{index:06d}", upload_confirmed=True,
    )
    values.update(updates)
    return api.YouTubeUploadJob(**values)


def test_five_short_slots_then_next_day():
    now = datetime(2099, 1, 1, 21, tzinfo=timezone.utc)
    reserved = set()
    slots = []
    for index in range(15):
        slot = api.youtube_next_publish_slot(long_form=False, reserved=reserved, now=now)
        reserved.add(slot)
        slots.append(slot)
    dates = Counter(slot.astimezone(ZoneInfo("Asia/Jakarta")).date() for slot in slots)
    assert sorted(dates.values()) == [5, 5, 5]
    assert all(b - a >= timedelta(hours=2.25) for a, b in zip(slots, slots[1:]))


def test_today_full_from_public_channel_activity_pushes_to_tomorrow(monkeypatch):
    now = datetime(2099, 1, 2, 5, tzinfo=timezone.utc)
    published = [now] * 7  # Seven distinct videos may share a publication second.
    monkeypatch.setattr(api, "youtube_recent_publication_times", lambda **_kwargs: published)
    slot = api.youtube_next_publish_slot(long_form=False, now=now, reserved=set())
    assert slot.astimezone(ZoneInfo("Asia/Jakarta")).date() > now.astimezone(ZoneInfo("Asia/Jakarta")).date()


def test_future_neighbor_gap_and_midnight_are_respected():
    now = datetime(2099, 1, 1, 21, tzinfo=timezone.utc)
    occupied = {datetime(2099, 1, 2, 1, tzinfo=timezone.utc)}  # 08:00 WIB
    slot = api.youtube_next_publish_slot(long_form=False, now=now, reserved=occupied)
    assert slot.astimezone(ZoneInfo("Asia/Jakarta")).strftime("%H:%M") == "11:30"


def test_private_buffer_ignores_legacy_manual_and_failed_before_transfer(monkeypatch):
    uploads = [record(0), record(1, cron_private_buffer=True), record(2, cron_private_buffer=True, status="queued"),
               record(3, cron_private_buffer=True, status="failed", video_url=None), record(4, dry_run=True, cron_private_buffer=True)]
    monkeypatch.setattr(api, "youtube_uploads", {u.id: u for u in uploads})
    assert api.youtube_cron_private_buffer_count() == 2


def test_promote_only_one_new_reserve_when_ten_schedules_exist(monkeypatch):
    queued = []
    reserve = record(1, cron_private_buffer=True)
    legacy = record(2)
    monkeypatch.setattr(api, "youtube_uploads", {u.id: u for u in [reserve, legacy]})
    monkeypatch.setattr(api, "youtube_scheduled_backlog_count", lambda **_kwargs: 10)
    monkeypatch.setattr(api, "queue_youtube_upload_jobs", lambda uploads: queued.extend(uploads))
    assert api.queue_youtube_private_buffer_promotions_once() == 1
    assert queued[0].id == reserve.id
    assert queued[0].video_url == reserve.video_url
    assert queued[0].visibility == "public" and queued[0].publish_at
    assert api.youtube_uploads[legacy.id].visibility == "private"
    command = api.build_youtube_restart_verification_command(queued[0])
    assert "verify-upload" in command and "--schedule-existing" in command
    assert queued[0].video_url in command


def test_full_buffers_wake_after_next_release_instead_of_waiting_a_day(monkeypatch):
    now = datetime.now(timezone.utc)
    monkeypatch.setenv("AUTO_VIRAL_SCHEDULE_AUTO_UPLOAD_YOUTUBE", "true")
    future = record(1, visibility="public", publish_at=(now + timedelta(hours=1)).isoformat())
    monkeypatch.setattr(api, "youtube_uploads", {future.id: future})
    monkeypatch.setattr(api, "youtube_cron_capacity_room", lambda: 0)
    assert api.auto_viral_daily_mix_not_before(now) == now + timedelta(hours=1, minutes=1)
    assert api.auto_viral_daily_mix_incomplete(now) is False


def test_reconcile_preserves_ids_and_reserves_at_most_five_shorts_per_day(monkeypatch):
    now = datetime.now(timezone.utc)
    uploads = [record(index, visibility="public", publish_at=(now + timedelta(days=2, minutes=index)).isoformat()) for index in range(11)]
    monkeypatch.setattr(api, "youtube_uploads", {u.id: u for u in uploads})
    monkeypatch.setattr(api, "scheduled_auto_viral_job_ids", lambda: {u.source_job_id for u in uploads})
    monkeypatch.setattr(api, "queue_youtube_upload_jobs", lambda _uploads: None)
    changed = api.reconcile_youtube_cron_schedules()
    assert {u.id for u in changed} == {u.id for u in uploads[1:]}
    assert api.youtube_uploads[uploads[0].id].publish_at == uploads[0].publish_at
    times = sorted(api.parsed_datetime(u.publish_at) for u in api.youtube_uploads.values())
    assert max(Counter(t.astimezone(ZoneInfo("Asia/Jakarta")).date() for t in times).values()) <= 5
    assert all(b - a >= timedelta(hours=2.25) for a, b in zip(times, times[1:]))


@pytest.mark.parametrize('correct', [True, False])
@pytest.mark.parametrize('original_public', [False, True])
def test_saved_schedule_verifies_persisted_model_on_same_id(monkeypatch, correct, original_public):
    import youtube_uploader as uploader
    from types import SimpleNamespace
    from contextlib import contextmanager
    calls = []
    logs = []
    model = {'date': {'year': 2099, 'month': 0, 'day': 2}, 'selectedTimeOfDayValue': 25200 if correct else 0, 'selectedTimezoneIndex': 0}
    class Control:
        def __init__(self, selector=''): self.selector = selector
        @property
        def first(self): return self
        def wait_for(self, **kwargs): pass
        def click(self, **kwargs): calls.append('click')
        def press(self, key): calls.append(key)
        def is_enabled(self): return True
        def count(self): return int('reload' in calls)
        def evaluate(self, _script):
            if self.selector == 'ytcp-video-visibility-select':
                return {'visibility': 'PUBLIC' if original_public and 'reload' not in calls else 'PRIVATE'}
            return model
        def locator(self, selector): return Control(selector)
    class Page:
        def evaluate(self, _script): return 'Asia/Jakarta'
        def goto(self, url, **kwargs): calls.append(url)
        def locator(self, selector): return Control(selector)
        def get_by_role(self, *args, **kwargs): return Control()
        @contextmanager
        def expect_response(self, *args, **kwargs):
            yield SimpleNamespace(value=SimpleNamespace(status=200, json=lambda: {}))
            calls.append('server-confirmed')
        def wait_for_function(self, *args, **kwargs): calls.append('saved')
        def reload(self, **kwargs): calls.append('reload')
    monkeypatch.setattr(uploader, 'ensure_logged_in', lambda _page: None)
    monkeypatch.setattr(uploader, 'normalized_page_text', lambda _page: '')
    monkeypatch.setattr(uploader, 'set_scheduled_publish_time', lambda _page, when: calls.append(when))
    monkeypatch.setattr(uploader, 'log', logs.append)
    target = '2099-01-02T00:00:00+00:00'
    if correct:
        assert uploader.schedule_saved_video(Page(), 'https://www.youtube.com/watch?v=abcDEF12345', target).endswith('abcDEF12345')
        assert any(line.startswith('SCHEDULE_PERSISTED_CONFIRMED:') for line in logs)
    else:
        with pytest.raises(uploader.UploadError, match='belum cocok'):
            uploader.schedule_saved_video(Page(), 'https://www.youtube.com/watch?v=abcDEF12345', target)
        assert not any(line.startswith('SCHEDULE_PERSISTED_CONFIRMED:') for line in logs)
    assert calls[0] == 'https://studio.youtube.com/video/abcDEF12345/edit'
    assert 'saved' in calls and 'reload' in calls
    assert calls.index('server-confirmed') < calls.index('reload')
    assert calls.count('saved') == (2 if original_public else 1)


def test_batch_uses_only_remaining_schedule_then_private_capacity(monkeypatch):
    clips = [api.ClipFile(name=f'clip_{i}.mp4', url=f'/outputs/job/clip_{i}.mp4', size_bytes=10) for i in range(3)]
    job = api.ClipJob(id='job', status='completed', request=api.ClipJobRequest(source_file='owned.mp4', scheduled_public_source_credit=True), created_at='2026-11-03T00:00:00+00:00', updated_at='2026-11-03T00:00:00+00:00', clips=clips)
    monkeypatch.setattr(api, 'jobs', {job.id: job})
    monkeypatch.setenv('YOUTUBE_ALLOW_PUBLIC_AUTO_UPLOAD', 'true')
    monkeypatch.setattr(api, 'youtube_scheduled_backlog_count', lambda **kwargs: 10)
    monkeypatch.setattr(api, 'youtube_cron_private_buffer_count', lambda: 4)
    requests = []
    def create(job_id, request):
        requests.append(request)
        return record(len(requests), status='queued', visibility=request.visibility, publish_at=request.publish_at, cron_private_buffer=request.cron_private_buffer)
    monkeypatch.setattr(api, 'create_youtube_upload_record', create)
    result = api.create_youtube_upload_batch_records(job.id, api.YouTubeBatchUploadRequest(clip_urls=[c.url for c in clips], visibility='public'))
    assert len(result) == 2
    assert requests[0].visibility == 'public' and requests[0].publish_at
    assert requests[1].visibility == 'private' and requests[1].publish_at is None
    assert requests[1].cron_private_buffer
