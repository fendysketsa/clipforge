from datetime import datetime, timezone
from copy import deepcopy

import pytest
import api
from daily_cron_plan import build_plan, next_short_lane

NOW = datetime(2026, 11, 14, 1, tzinfo=timezone.utc)
TARGETS = {"scheduled_short": 17, "private_short": 4, "long": 2}


def plan(**changes):
    return build_plan(**(dict(now=NOW, targets=TARGETS, jobs=[], runs=[], uploads=[], attempts=[]) | changes))


def upload(index=0, **changes):
    return dict(source_job_id=f"j{index}", clip_url=f"/c{index}.mp4", created_at=NOW.isoformat(),
        cron_daily_lane="scheduled_short", cron_production_day="2026-11-14", status="completed",
        visibility="public", publish_at="2026-11-16T02:00:00Z", verified=True,
        remote_id=f"video{index:06}", **changes)


def test_seventeen_four_two_is_a_daily_production_plan_not_a_future_backlog_limit():
    old = [dict(upload(i), cron_production_day="2026-11-13") for i in range(57)]
    result = plan(uploads=old)
    assert result["total_target"] == 23
    assert result["total_used"] == 0
    assert next_short_lane(result) == "scheduled_short"
    assert result["lanes"]["private_short"]["remaining"] == 4


def test_all_three_quotas_are_independent_and_private_uploads_are_not_public_slots():
    rows = [upload(i) for i in range(17)]
    rows += [dict(upload(i+20), cron_daily_lane="private_short", visibility="private", publish_at=None) for i in range(4)]
    rows += [dict(upload(i+30), cron_daily_lane="long", visibility="private", publish_at=None) for i in range(2)]
    result = plan(uploads=rows)
    assert result["total_uploaded"] == 23
    assert next_short_lane(result) is None
    assert all(row["remaining"] == 0 for row in result["lanes"].values())


def test_wib_midnight_resets_without_relabeling_old_pending_work():
    rows = [dict(upload(), status="running", verified=False)]
    assert plan(uploads=rows)["total_used"] == 1
    assert plan(now=datetime(2026, 11, 14, 17, tzinfo=timezone.utc), uploads=rows)["total_used"] == 0
    assert rows[0]["cron_production_day"] == "2026-11-14"


def test_same_remote_video_and_retry_records_are_counted_once():
    rows = [upload(), dict(upload(), status="failed", verified=False), dict(upload(1), remote_id="video000000")]
    result = plan(uploads=rows)
    assert result["total_uploaded"] == result["total_used"] == 1


def test_missing_confirmation_and_ambiguous_remote_outcome_are_reserved_not_reported_uploaded():
    rows = [dict(upload(), status="failed", verified=False)]
    result = plan(uploads=rows)
    assert result["total_uploaded"] == 0
    assert result["lanes"]["scheduled_short"]["held"] == 1
    rows[0]["remote_id"] = None
    assert plan(uploads=rows)["total_used"] == 0
    rows[0]["uncertain"] = True
    assert plan(uploads=rows)["lanes"]["scheduled_short"]["held"] == 1


def test_one_in_flight_artifact_never_reserves_both_render_and_upload_slots():
    row = dict(upload(), status="running", verified=False)
    job = dict(id="j0",status="running",created_at=NOW.isoformat(),
        request={"cron_daily_lane":"scheduled_short","cron_production_day":"2026-11-14","top":1},clips=[])
    result = plan(uploads=[row],jobs=[job])
    assert result["total_used"] == result["lanes"]["scheduled_short"]["active"] == 1


def test_reusing_an_older_remote_video_does_not_inflate_today_production():
    job = dict(id="j0",status="completed",created_at=NOW.isoformat(),
        request={"cron_daily_lane":"scheduled_short","cron_production_day":"2026-11-14"},clips=[{"url":"/c0.mp4"}])
    result = plan(jobs=[job],uploads=[dict(upload(),cron_production_day="2026-11-13")])
    assert result["total_uploaded"] == result["total_used"] == 0


def test_manual_uploads_and_dry_runs_do_not_consume_cron_quota():
    manual = upload(); manual.pop("cron_daily_lane"); manual.pop("cron_production_day")
    assert plan(uploads=[manual, dict(upload(1), dry_run=True)])["total_used"] == 0


def test_legacy_owned_private_and_standalone_long_survive_job_cleanup():
    run = dict(trigger="schedule", created_at=NOW.isoformat(), request={}, processed=[{"job_id":"j0"}])
    short = upload(); short.pop("cron_daily_lane"); short.pop("cron_production_day")
    short.update(visibility="private", publish_at=None)
    long = dict(upload(1), cron_daily_lane="", cron_production_day="", visibility="private", publish_at=None)
    result = plan(runs=[run], uploads=[short,long], attempts=[dict(job_id="j1",day="2026-11-14",status="completed")])
    assert result["lanes"]["private_short"]["uploaded"] == 1
    assert result["lanes"]["long"]["uploaded"] == 1


def test_completed_render_reserves_its_slot_while_qc_waits_and_does_not_double_count_upload():
    job = dict(id="j0", status="completed", created_at=NOW.isoformat(), request={"cron_daily_lane":"long","cron_production_day":"2026-11-14"}, clips=[{"url":"/c0.mp4"}])
    result = plan(jobs=[job])
    assert result["lanes"]["long"]["ready"] == 1
    assert result["total_uploaded"] == 0
    result = plan(jobs=[job],uploads=[dict(upload(),cron_daily_lane="long")])
    assert result["lanes"]["long"]["ready"] == 0
    assert result["lanes"]["long"]["uploaded"] == 1
    result = plan(jobs=[job],attempts=[dict(job_id="j0",day="2026-11-14",qc_decision="DROP_SOURCE")])
    assert result["total_used"] == 0


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("AUTO_VIRAL_DAILY_PLAN_ENABLED","true")
    monkeypatch.setenv("AUTO_VIRAL_DAILY_UPLOAD_LIMIT","23")
    monkeypatch.setenv("AUTO_VIRAL_DAILY_LONG_UPLOAD_TARGET","2")
    monkeypatch.setenv("AUTO_VIRAL_SCHEDULE_NEWS_HOT_ENABLED","false")
    monkeypatch.setenv("AUTO_VIRAL_SCHEDULE_AUTO_UPLOAD_YOUTUBE","true")


def test_old_eleven_plus_five_backlog_never_blocks_today_production(enabled, monkeypatch):
    monkeypatch.setattr(api,"youtube_scheduled_backlog_count",lambda **k:57)
    monkeypatch.setattr(api,"youtube_cron_private_buffer_count",lambda:5)
    assert api.youtube_cron_capacity_room() == 21
    assert api.auto_viral_daily_mix_not_before(NOW) is None
    assert api.auto_viral_daily_mix_incomplete(NOW)
    assert api.auto_viral_daily_short_upload_target() == 21
    assert api.auto_viral_daily_long_upload_target() == 2


def test_long_target_is_two_without_resetting_operator_holds_or_attempts(enabled):
    state={"enabled":False,"daily_target":1,"auto_qc_enabled":False,"attempts":[{"job_id":"old","day":"2026-11-13","status":"completed"}]}
    api.save_long_production_state(deepcopy(state))
    effective=api.long_production_state()
    assert effective["daily_target"] == 2
    assert effective["enabled"] is False
    assert effective["auto_qc_enabled"] is False
    assert effective["attempts"] == state["attempts"]


def test_private_reserves_are_never_automatically_promoted_in_the_new_plan(enabled, monkeypatch):
    monkeypatch.setenv("YOUTUBE_CRON_BUFFER_ENABLED","true")
    assert api.queue_youtube_private_buffer_promotions_once() == 0


def test_public_quota_does_not_consume_the_four_private_slots(enabled, monkeypatch):
    snapshot = plan(uploads=[upload(i) for i in range(17)])
    monkeypatch.setattr(api, "daily_cron_plan_status", lambda *a: snapshot)
    monkeypatch.setattr(api, "scheduled_auto_viral_youtube_browser_ready", lambda: True)
    monkeypatch.setattr(api, "scheduled_auto_viral_rights_profile_ready", lambda: True)
    request = api.scheduled_auto_viral_request()
    assert request.cron_daily_lane == "private_short"
    assert request.top == request.clips_per_video == 1
    assert request.auto_upload_youtube
    assert not request.create_paired_long_video
    assert not request.auto_publish_paired_long_video
    assert request.video_count * request.clips_per_video <= 4
    assert api.auto_viral_daily_mix_not_before(NOW) is None


def test_completed_short_quotas_wait_until_next_wib_day_without_stopping_long_worker(enabled, monkeypatch):
    snapshot = plan(uploads=[upload(i) for i in range(17)] + [dict(upload(i+20),cron_daily_lane="private_short") for i in range(4)])
    monkeypatch.setattr(api, "daily_cron_plan_status", lambda *a: snapshot)
    assert next_short_lane(snapshot) is None
    assert snapshot["lanes"]["long"]["remaining"] == 2
    assert api.auto_viral_daily_mix_not_before(NOW) == datetime(2026,11,14,17,1,tzinfo=timezone.utc)


def test_legacy_same_day_jobs_in_a_multi_day_run_use_the_child_production_date():
    run = dict(trigger="schedule",created_at="2026-11-12T00:00:00Z",request={},processed=[{"job_id":"legacy"}])
    job = dict(id="legacy",status="completed",created_at=NOW.isoformat(),request={},clips=[{"url":"/legacy.mp4"}])
    result=plan(runs=[run],jobs=[job])
    assert result["lanes"]["scheduled_short"]["ready"] == 1


@pytest.mark.parametrize('lane', ['scheduled_short', 'private_short'])
def test_daily_upload_routing_ignores_old_full_buffers_and_preserves_private_destination(enabled, monkeypatch, lane):
    clip=api.ClipFile(name='clip.mp4',url='/outputs/daily/clip.mp4',size_bytes=100,is_correct=True)
    job=api.ClipJob(id='daily',status='completed',created_at=NOW.isoformat(),updated_at=NOW.isoformat(),
        request=api.ClipJobRequest(source_file='owned.mp4',scheduled_public_source_credit=True,cron_daily_lane=lane),clips=[clip])
    monkeypatch.setattr(api,'jobs',{job.id:job})
    monkeypatch.setenv('YOUTUBE_ALLOW_PUBLIC_AUTO_UPLOAD','true')
    monkeypatch.setattr(api,'youtube_scheduled_backlog_count',lambda **k:57)
    monkeypatch.setattr(api,'youtube_cron_private_buffer_count',lambda:5)
    monkeypatch.setattr(api,'youtube_next_publish_slot',lambda **k:datetime(2099,1,1,tzinfo=timezone.utc))
    requests=[]
    def create(job_id,request):
        requests.append(request)
        return api.YouTubeUploadJob(id='upload',source_job_id=job_id,clip_url=clip.url,clip_name=clip.name,title='Video',
            status='queued',created_at=NOW.isoformat(),updated_at=NOW.isoformat(),visibility=request.visibility,publish_at=request.publish_at)
    monkeypatch.setattr(api,'create_youtube_upload_record',create)
    api.create_youtube_upload_batch_records(job.id,api.YouTubeBatchUploadRequest(clip_urls=[clip.url],visibility='public'))
    assert requests[0].visibility == ('private' if lane=='private_short' else 'public')
    assert bool(requests[0].publish_at) == (lane=='scheduled_short')
    assert not requests[0].cron_private_buffer


def test_seventeen_produced_shorts_fill_five_slots_per_date_while_longs_remain_independent(enabled, monkeypatch):
    from collections import Counter
    monkeypatch.setenv("YOUTUBE_PUBLIC_DAILY_LIMIT","7")
    monkeypatch.setenv("YOUTUBE_PUBLIC_MIN_GAP_HOURS","1")
    monkeypatch.setenv("YOUTUBE_SHORT_PUBLISH_SLOTS",','.join(f'{h:02}:00' for h in range(6,23)))
    monkeypatch.setenv("YOUTUBE_LONG_PUBLISH_SLOTS","05:00,23:00")
    monkeypatch.setenv("YOUTUBE_CHANNEL_RECOVERY_MODE","false")
    monkeypatch.setenv("YOUTUBE_SCHEDULE_MIN_LEAD_MINUTES","30")
    monkeypatch.setenv("YOUTUBE_PUBLIC_PAUSE_UNTIL","")
    monkeypatch.setattr(api,"youtube_recent_publication_times",lambda **k:[])
    stamp=datetime(2026,11,13,17,tzinfo=timezone.utc)
    reserved=set();shorts=[];longs=[]
    for is_long in [True]+[False]*17+[True]:
        slot=api.youtube_next_publish_slot(long_form=is_long,reserved=reserved,now=stamp,short_reserved=shorts)
        reserved.add(slot)
        (longs if is_long else shorts).append(slot)
    assert len(reserved)==19
    assert sorted(Counter(api.daily_cron_plan.wib_day(value.isoformat()) for value in shorts).values()) == [2,5,5,5]
    assert {api.daily_cron_plan.wib_day(value.isoformat()) for value in longs} == {"2026-11-14"}
