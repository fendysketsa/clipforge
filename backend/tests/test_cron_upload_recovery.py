from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import threading

import pytest

import api


@pytest.fixture
def stalled_run(monkeypatch):
    now = datetime.now(timezone.utc)
    run = api.AutoViralRun(
        id="stalled-cron", status="running", trigger="schedule",
        created_at=(now - timedelta(hours=2)).isoformat(),
        updated_at=(now - timedelta(hours=1)).isoformat(),
        progress_stage="social_upload", progress_percent=98,
        request=api.AutoViralRequest(auto_upload_youtube=True, auto_upload_tiktok=True),
        processed=[{"job_id": "missing-render", "job_status": "completed", "status": "awaiting_upload"}],
    )
    monkeypatch.setattr(api, "auto_viral_runs", {run.id: run})
    monkeypatch.setattr(api, "auto_viral_active_run_id", run.id)
    monkeypatch.setattr(api, "cancelled_auto_viral_run_ids", set())
    monkeypatch.setattr(api, "job_processes", {})
    monkeypatch.setattr(api, "youtube_upload_processes", {})
    monkeypatch.setattr(api, "tiktok_upload_processes", {})
    monkeypatch.setattr(api, "youtube_upload_creation_lock", threading.Lock())
    monkeypatch.setattr(api, "tiktok_upload_creation_lock", threading.Lock())
    return run


def upload(platform, *, status="completed"):
    fields = dict(
        id=platform + "-remote", source_job_id="missing-render",
        clip_url="/outputs/missing-render/clip.mp4", clip_name="clip.mp4",
        status=status, created_at=api.now_iso(), updated_at=api.now_iso(),
        upload_confirmed=status == "completed",
    )
    if platform == "youtube":
        return api.YouTubeUploadJob(**fields, title="Saved", video_url="https://www.youtube.com/watch?v=abcdefghijk")
    return api.TikTokUploadJob(**fields, caption="Saved post", target_handle="test", profile_url="https://www.tiktok.com/@test")


def test_observed_missing_job_with_tiktok_success_releases_cron(stalled_run, monkeypatch):
    posted = upload("tiktok")
    monkeypatch.setattr(api, "tiktok_uploads", {posted.id: posted})
    assert api.reconcile_stalled_scheduled_upload_runs() == 1
    recovered = api.auto_viral_runs[stalled_run.id]
    assert recovered.status == "failed"
    assert recovered.progress_stage == "upload_checkpoint_expired"
    assert api.auto_viral_active_run_id is None
    assert recovered.processed[0]["status"] == "checkpoint_missing"
    assert recovered.processed[0]["tiktok_uploads"][0]["id"] == posted.id
    assert api.tiktok_uploads[posted.id] is posted
    assert api.youtube_uploads == {}
    assert api.reconcile_stalled_scheduled_upload_runs() == 0


def test_expired_checkpoint_starts_fresh_source_even_when_upload_retry_is_disabled(stalled_run, monkeypatch):
    monkeypatch.setenv("AUTO_VIRAL_SCHEDULE_RETRY_UNTIL_SUCCESS", "false")
    monkeypatch.setenv("AUTO_VIRAL_CYCLE_DELAY_HOURS", "24")
    monkeypatch.setattr(api, "youtube_cron_buffer_enabled", lambda: False)
    monkeypatch.setattr(api, "scheduled_news_hot_due", lambda _now: False)
    monkeypatch.setattr(api, "auto_viral_retry_delay_minutes", lambda: 5)
    monkeypatch.setattr(api, "auto_viral_boot_not_before", lambda now: now)
    monkeypatch.setattr(api, "auto_viral_daily_mix_not_before", lambda now: None)
    now = datetime.now(timezone.utc)
    api.reconcile_stalled_scheduled_upload_runs(now)
    when = api.auto_viral_next_run_at(now, api.auto_viral_runs[stalled_run.id], api.auto_viral_active_run_id)
    assert when == now


@pytest.mark.parametrize("hold", ["capacity", "daily_quota"])
def test_expired_checkpoint_recovery_still_respects_capacity_and_daily_quota(stalled_run, monkeypatch, hold):
    now = datetime.now(timezone.utc)
    retry_at = now + timedelta(hours=4)
    monkeypatch.setenv("AUTO_VIRAL_SCHEDULE_RETRY_UNTIL_SUCCESS", "false")
    monkeypatch.setattr(api, "scheduled_news_hot_due", lambda now: False)
    monkeypatch.setattr(api, "youtube_cron_buffer_enabled", lambda: hold == "capacity")
    monkeypatch.setattr(api, "youtube_cron_capacity_room", lambda: 0)
    monkeypatch.setattr(api, "youtube_cron_capacity_retry_at", lambda now: retry_at)
    monkeypatch.setattr(api, "auto_viral_daily_mix_not_before", lambda now: retry_at)
    api.reconcile_stalled_scheduled_upload_runs(now)
    when = api.auto_viral_next_run_at(now, api.auto_viral_runs[stalled_run.id], None)
    assert when == retry_at


def test_existing_child_job_is_never_retired(stalled_run, monkeypatch):
    monkeypatch.setattr(api, "jobs", {"missing-render": SimpleNamespace(status="completed")})
    assert api.reconcile_stalled_scheduled_upload_runs() == 0
    assert api.auto_viral_active_run_id == stalled_run.id


@pytest.mark.parametrize("platform", ["youtube", "tiktok"])
@pytest.mark.parametrize("status", ["queued", "running"])
def test_active_remote_upload_is_never_retired(stalled_run, monkeypatch, platform, status):
    active = upload(platform, status=status)
    monkeypatch.setattr(api, platform + "_uploads", {active.id: active})
    assert api.reconcile_stalled_scheduled_upload_runs() == 0
    assert api.auto_viral_active_run_id == stalled_run.id


@pytest.mark.parametrize("kind", ["render", "youtube", "tiktok"])
def test_live_subprocess_is_protected_even_if_row_is_missing_or_terminal(stalled_run, monkeypatch, kind):
    process = SimpleNamespace(poll=lambda: None)
    if kind == "render":
        monkeypatch.setattr(api, "job_processes", {"missing-render": process})
    else:
        saved = upload(kind)
        monkeypatch.setattr(api, kind + "_uploads", {saved.id: saved})
        monkeypatch.setattr(api, kind + "_upload_processes", {saved.id: process})
    assert api.reconcile_stalled_scheduled_upload_runs() == 0


@pytest.mark.parametrize("stage", [
    "waiting_upload", "daily_upload_limit", "youtube_platform_daily_limit",
    "cron_capacity_wait", "retry_upload", "clip_rendering",
])
def test_intentional_waits_and_render_stages_are_protected(stalled_run, stage):
    api.auto_viral_runs[stalled_run.id] = stalled_run.model_copy(update={"progress_stage": stage})
    assert api.reconcile_stalled_scheduled_upload_runs() == 0


def test_recent_progress_is_protected(stalled_run):
    api.auto_viral_runs[stalled_run.id] = stalled_run.model_copy(update={"updated_at": api.now_iso()})
    assert api.reconcile_stalled_scheduled_upload_runs() == 0


def test_restart_checkpoint_without_jobs_is_retired_before_capacity_checks(stalled_run):
    api.auto_viral_runs[stalled_run.id] = stalled_run.model_copy(update={
        "status": "queued", "progress_stage": "resume_pending_upload", "updated_at": api.now_iso(),
    })
    assert api.reconcile_stalled_scheduled_upload_runs() == 1
    assert api.auto_viral_runs[stalled_run.id].progress_stage == "upload_checkpoint_expired"


@pytest.mark.parametrize("platform", ["youtube", "tiktok"])
def test_upload_creation_in_progress_is_protected(stalled_run, platform):
    lock = getattr(api, platform + "_upload_creation_lock")
    with lock:
        assert api.reconcile_stalled_scheduled_upload_runs() == 0
    assert api.reconcile_stalled_scheduled_upload_runs() == 1


def test_late_worker_cannot_revive_expired_run_or_start_another_upload(stalled_run, monkeypatch):
    api.reconcile_stalled_scheduled_upload_runs()
    api.update_auto_viral_run(stalled_run.id, status="running", progress_stage="social_upload")
    assert api.auto_viral_runs[stalled_run.id].status == "failed"
    monkeypatch.setattr(api, "upload_auto_viral_processed_jobs", lambda *args: pytest.fail("retired worker must stop"))
    with pytest.raises(api.AutoViralCampaignCancelled):
        api.upload_auto_viral_until_success(stalled_run.id, stalled_run.request, stalled_run.processed)


def test_terminal_active_reference_is_released(stalled_run):
    api.auto_viral_runs[stalled_run.id] = stalled_run.model_copy(update={"status": "cancelled"})
    assert api.reconcile_stalled_scheduled_upload_runs() == 0
    assert api.auto_viral_active_run_id is None


@pytest.mark.parametrize("waiter", [api.wait_for_uploads, api.wait_for_tiktok_uploads])
def test_missing_upload_record_fails_without_two_hour_wait(monkeypatch, waiter):
    monkeypatch.setattr(api.time, "sleep", lambda *args: pytest.fail("missing record cannot become terminal by waiting"))
    with pytest.raises(api.UploadCheckpointMissing):
        waiter(["missing-upload"])


def test_missing_upload_record_is_held_without_retry_or_duplicate(stalled_run, monkeypatch):
    processed = [{"job_id": "missing-render", "job_status": "completed", "status": "uploading"}]
    def missing(*args):
        raise api.UploadCheckpointMissing("Missing remote checkpoint")
    monkeypatch.setattr(api, "upload_auto_viral_processed_jobs", missing)
    monkeypatch.setattr(api.time, "sleep", lambda *args: pytest.fail("must not retry unknown remote outcome"))
    result = api.upload_auto_viral_until_success(stalled_run.id, stalled_run.request, processed)
    assert result[0]["status"] == "checkpoint_missing"


def test_cancelled_upload_does_not_enter_retry_loop(stalled_run, monkeypatch):
    def cancelled(*args):
        raise api.AutoViralCampaignCancelled("cancelled")
    monkeypatch.setattr(api, "upload_auto_viral_processed_jobs", cancelled)
    monkeypatch.setattr(api.time, "sleep", lambda *args: pytest.fail("must stop immediately"))
    with pytest.raises(api.AutoViralCampaignCancelled):
        api.upload_auto_viral_until_success(stalled_run.id, stalled_run.request, stalled_run.processed)


def test_private_promotion_does_not_block_scheduler_behind_metadata(stalled_run, monkeypatch):
    monkeypatch.setattr(api, "youtube_cron_buffer_enabled", lambda: True)
    with api.youtube_upload_creation_lock:
        assert api.queue_youtube_private_buffer_promotions_once() == 0
