from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
import api

WIB = ZoneInfo('Asia/Jakarta')
NOW = datetime(2099, 1, 1, 17, tzinfo=timezone.utc)  # Jan 2, 00:00 WIB.


@pytest.fixture(autouse=True)
def policy(monkeypatch):
    for key,value in {'YOUTUBE_SHORT_SCHEDULE_DAILY_LIMIT':'5','YOUTUBE_PUBLIC_DAILY_LIMIT':'7',
        'YOUTUBE_PUBLIC_MIN_GAP_HOURS':'1','YOUTUBE_CHANNEL_RECOVERY_MODE':'false',
        'YOUTUBE_SHORT_PUBLISH_SLOTS':'07:00,10:00,13:00,16:00,19:00',
        'YOUTUBE_LONG_PUBLISH_SLOTS':'05:00,23:00','YOUTUBE_PUBLISH_TIMEZONE':'Asia/Jakarta',
        'YOUTUBE_PUBLIC_PAUSE_UNTIL':'','YOUTUBE_SCHEDULE_MIN_LEAD_MINUTES':'30',
        'YOUTUBE_CRON_BUFFER_ENABLED':'true'}.items():
        monkeypatch.setenv(key,value)
    monkeypatch.setattr(api,'youtube_recent_publication_times',lambda **k:[])


def row(index, hour, **changes):
    values=dict(id=f'u{index}',source_job_id=f'j{index}',clip_url=f'/clip{index}.mp4',clip_name='clip_01.mp4',title='Clip',
        status='completed',created_at=NOW.isoformat(),updated_at=NOW.isoformat(),visibility='public',upload_confirmed=True,
        publish_at=datetime(2099,1,2,hour,tzinfo=WIB).isoformat(),video_url=f'https://www.youtube.com/watch?v=video{index:06}',
        clip_sha256=f'hash-{index}',source_video_url=f'https://www.youtube.com/watch?v=source{index:05}')
    values.update(changes)
    return api.YouTubeUploadJob(**values)


def test_seventeen_shorts_produce_a_five_five_five_two_publication_queue():
    reserved=set();shorts=[]
    for _ in range(17):
        slot=api.youtube_next_publish_slot(long_form=False,now=NOW,reserved=reserved,short_reserved=shorts)
        reserved.add(slot);shorts.append(slot)
    assert sorted(Counter(when.astimezone(WIB).date() for when in shorts).values()) == [2,5,5,5]
    assert len(set(shorts))==17


def test_completed_and_future_shorts_on_the_same_wib_date_share_five_slots(monkeypatch):
    uploads=[row(i,hour) for i,hour in enumerate([7,10,13,16,19])]
    uploads[0].publish_at=None
    uploads[0].finished_at=datetime(2099,1,2,7,tzinfo=WIB).isoformat()
    monkeypatch.setattr(api,'youtube_uploads',{r.id:r for r in uploads})
    slot=api.youtube_next_publish_slot(long_form=False,now=NOW+timedelta(hours=9))
    assert slot.astimezone(WIB).date().isoformat()=='2099-01-03'


def test_two_longs_do_not_consume_the_five_short_slots(monkeypatch):
    uploads=[row(50,5,clip_name='resume_cerita_1.mp4'),row(51,23,cron_daily_lane='long')]
    monkeypatch.setattr(api,'youtube_uploads',{r.id:r for r in uploads})
    assert len(api.youtube_short_publication_times([]))==0
    assert api.youtube_next_publish_slot(long_form=False,now=NOW).astimezone(WIB).hour==7


def test_alias_records_for_one_remote_video_reserve_one_slot(monkeypatch):
    original=row(0,7)
    alias=original.model_copy(update={'id':'alias','source_job_id':'copy'})
    monkeypatch.setattr(api,'youtube_uploads',{r.id:r for r in [original,alias]})
    assert len(api.youtube_short_publication_times([api.parsed_datetime(original.publish_at)]))==1
    assert api.youtube_short_publication_times([api.parsed_datetime(original.publish_at)],exclude_upload_ids={original.id})==[]


def test_failed_remote_save_remains_reserved_but_private_and_dry_run_do_not(monkeypatch):
    uploads=[row(0,7,status='failed'),row(1,10,visibility='private'),row(2,13,dry_run=True)]
    monkeypatch.setattr(api,'youtube_uploads',{r.id:r for r in uploads})
    assert len(api.youtube_short_publication_times([]))==1


def test_a_source_cannot_fill_two_short_slots_on_the_same_date(monkeypatch):
    original=row(0,7)
    monkeypatch.setattr(api,'youtube_uploads',{original.id:original})
    slot=api.youtube_next_publish_slot(long_form=False,now=NOW,source_url=original.source_video_url)
    assert slot.astimezone(WIB).date().isoformat()=='2099-01-03'
    assert 'Sumber' in api.youtube_short_schedule_issue(api.parsed_datetime(original.publish_at),source_url=original.source_video_url)


def test_reconcile_moves_only_the_sixth_short_and_keeps_remote_identity_and_longs(monkeypatch):
    uploads=[row(i,hour) for i,hour in enumerate([7,10,13,16,19,21])]
    long=row(99,23,clip_name='resume_cerita_1.mp4')
    uploads.append(long)
    monkeypatch.setattr(api,'youtube_uploads',{r.id:r for r in uploads})
    monkeypatch.setattr(api,'scheduled_auto_viral_job_ids',lambda:{r.source_job_id for r in uploads})
    queued=[]
    monkeypatch.setattr(api,'queue_youtube_upload_jobs',lambda rows:queued.extend(rows))
    changed=api.reconcile_youtube_cron_schedules()
    assert [r.id for r in changed]==['u5']
    assert changed[0].video_url==uploads[5].video_url
    assert api.parsed_datetime(changed[0].publish_at)>api.parsed_datetime(uploads[5].publish_at)
    assert api.parsed_datetime(changed[0].publish_at).astimezone(WIB).date().isoformat()=='2099-01-03'
    assert api.youtube_uploads[long.id].publish_at==long.publish_at
    assert len(queued)==1 and api.YOUTUBE_RESTART_VERIFY_MARKER in queued[0].logs


def test_an_explicit_six_short_plan_is_rejected_before_any_mutation(monkeypatch):
    uploads=[row(i,hour) for i,hour in enumerate([7,9,11,13,15,17])]
    monkeypatch.setattr(api,'youtube_uploads',{r.id:r for r in uploads})
    monkeypatch.setattr(api,'scheduled_auto_viral_job_ids',lambda:{r.source_job_id for r in uploads})
    with pytest.raises(api.HTTPException,match='') as error:
        api.reconcile_youtube_cron_schedules({r.id:r.publish_at for r in uploads})
    assert error.value.status_code==409
    assert all(r.status=='completed' for r in api.youtube_uploads.values())


def test_identical_files_on_distinct_remote_ids_require_review_and_are_not_rescheduled(monkeypatch):
    uploads=[row(0,7),row(1,10,clip_sha256='hash-0')]
    monkeypatch.setattr(api,'youtube_uploads',{r.id:r for r in uploads})
    monkeypatch.setattr(api,'scheduled_auto_viral_job_ids',lambda:{r.source_job_id for r in uploads})
    with pytest.raises(api.HTTPException) as error:api.reconcile_youtube_cron_schedules()
    assert 'duplikat' in error.value.detail
    assert all(r.status=='completed' for r in api.youtube_uploads.values())


def test_daily_limit_cannot_be_configured_above_five(monkeypatch):
    monkeypatch.setenv('YOUTUBE_SHORT_SCHEDULE_DAILY_LIMIT','999')
    assert api.youtube_short_schedule_daily_limit()==5
