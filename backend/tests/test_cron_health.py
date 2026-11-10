from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import api


@pytest.fixture
def schedule_state(monkeypatch):
    for key, value in {
        "AUTO_VIRAL_SCHEDULE_ENABLED": "true",
        "AUTO_VIRAL_SCHEDULE_AUTO_UPLOAD_YOUTUBE": "true",
        "AUTO_VIRAL_SCHEDULE_AUTO_UPLOAD_TIKTOK": "false",
        "AUTO_VIRAL_SCHEDULE_PAIRED_LONG_AUTO_PUBLIC": "false",
        "AUTO_VIRAL_SCHEDULE_SOURCE_RIGHTS_CONFIRMED": "true",
        "AUTO_VIRAL_SCHEDULE_SOURCE_RIGHTS_EVIDENCE": "Written permission covers all source audio and visuals",
        "AUTO_VIRAL_SCHEDULE_CREATOR_PERSPECTIVE": "Explain the original source with clear context and an accurate editorial takeaway",
        "YOUTUBE_CRON_BUFFER_ENABLED": "true",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(api, "auto_viral_active_run_id", None)
    monkeypatch.setattr(api, "auto_viral_scheduler_running", True)
    monkeypatch.setattr(api, "latest_scheduled_auto_viral_run", lambda: None)
    monkeypatch.setattr(api, "auto_viral_daily_youtube_content_counts", lambda: {"short": 0, "long": 0})
    monkeypatch.setattr(api, "scheduled_auto_viral_youtube_browser_ready", lambda: True)
    monkeypatch.setattr(api, "youtube_cron_capacity_room", lambda: 0)
    # Capacity disables the next request's YouTube flag even with valid rights.
    monkeypatch.setattr(api, "scheduled_auto_viral_request", lambda: api.AutoViralRequest(auto_upload_youtube=False))


def test_full_capacity_is_not_reported_as_missing_permission(schedule_state):
    status = api.auto_viral_schedule_status()
    assert "penuh" in status.message
    assert "izin" not in status.message


def test_schedule_reports_actual_recovery_tick_even_while_new_production_waits_for_capacity(schedule_state,monkeypatch):
    state={'last_tick_at':'2026-11-10T10:00:00+00:00',
        'queued':{'youtube':1,'tiktok':0},'errors':{'tiktok':'OSError'}}
    monkeypatch.setattr(api,'auto_viral_upload_recovery_status',state)
    status=api.auto_viral_schedule_status()
    assert not status.background_upload_enabled
    assert status.cron_upload_recovery==dict(state,enabled=True)


def test_active_run_takes_priority_over_next_request_capacity(schedule_state, monkeypatch):
    monkeypatch.setattr(api, "auto_viral_active_run_id", "active-run")
    status = api.auto_viral_schedule_status()
    assert status.active_run_id == "active-run"
    assert "sedang berjalan" in status.message
    assert "ditahan" not in status.message


def test_missing_rights_still_reports_real_hold(schedule_state, monkeypatch):
    monkeypatch.setenv("AUTO_VIRAL_SCHEDULE_SOURCE_RIGHTS_CONFIRMED", "false")
    assert "referensi bukti izin" in api.auto_viral_schedule_status().message


def test_unavailable_browser_does_not_report_missing_rights(schedule_state, monkeypatch):
    monkeypatch.setattr(api, "scheduled_auto_viral_youtube_browser_ready", lambda: False)
    message = api.auto_viral_schedule_status().message
    assert "browser Studio" in message
    assert "izin" not in message


def test_disabled_paired_long_does_not_report_missing_rights(schedule_state, monkeypatch):
    monkeypatch.setenv("AUTO_VIRAL_SCHEDULE_PAIRED_LONG_AUTO_PUBLIC", "true")
    monkeypatch.setenv("AUTO_VIRAL_SCHEDULE_PAIRED_LONG_ENABLED", "false")
    monkeypatch.setattr(api, "youtube_cron_capacity_room", lambda: 6)
    message = api.auto_viral_schedule_status().message
    assert "izin" not in message
    assert "ditahan" not in message


@pytest.mark.parametrize("ready", [True, False])
def test_forced_cdp_checks_actual_browser_readiness(monkeypatch, ready):
    monkeypatch.setattr(api, "youtube_upload_uses_cdp", lambda: False)
    monkeypatch.setattr(api, "youtube_upload_force_cdp", lambda: True)
    monkeypatch.setattr(api, "youtube_cdp_ready", lambda: ready)
    assert api.scheduled_auto_viral_youtube_browser_ready() is ready


@pytest.mark.parametrize("failing_step", [
    "reconcile_interrupted_scheduled_clip_runs",
    "latest_scheduled_auto_viral_run",
    "pending_scheduled_auto_viral_upload_run",
    "auto_viral_next_run_at",
])
def test_scheduler_recovers_from_transient_tick_failure(monkeypatch, failing_step):
    waits = []
    calls = []
    monkeypatch.setattr(api, "auto_viral_schedule_enabled", lambda: len(waits) < 2)
    monkeypatch.setattr(api, "auto_viral_active_run_id", None)
    monkeypatch.setattr(api, "queue_youtube_private_buffer_promotions_once", lambda: 0)
    monkeypatch.setattr(api, "reconcile_interrupted_scheduled_clip_runs", lambda: 0)
    monkeypatch.setattr(api, "latest_scheduled_auto_viral_run", lambda: None)
    monkeypatch.setattr(api, "pending_scheduled_auto_viral_upload_run", lambda: None)
    monkeypatch.setattr(api, "auto_viral_next_run_at", lambda *_: datetime.now(timezone.utc) + timedelta(minutes=1))
    original = getattr(api, failing_step)

    def transient_failure(*args):
        calls.append(1)
        if len(calls) == 1:
            raise OSError("temporary checkpoint read error")
        return original(*args)

    monkeypatch.setattr(api, failing_step, transient_failure)
    monkeypatch.setattr(api, "auto_viral_scheduler_wakeup", SimpleNamespace(wait=waits.append, clear=lambda: None))
    api.auto_viral_scheduler_loop()
    assert len(calls) == 2
    assert waits[0] == 30.0
    assert len(waits) == 2
    assert api.auto_viral_scheduler_running is False


@pytest.mark.parametrize("blocking", [False, True, None])
def test_display_rehydrates_qc_blocking_from_existing_sidecar(monkeypatch, blocking):
    clip = api.ClipFile(name="clip.mp4", url="/outputs/demo/clips/clip.mp4", size_bytes=2048, render_qc_passed=False)
    job = api.ClipJob(id="demo", status="completed", created_at=api.now_iso(), updated_at=api.now_iso(), request=api.ClipJobRequest(source_file="owned.mp4"), clips=[clip])
    for helper in ["enrich_job_source_metadata", "enrich_job_codex_feedback", "enrich_job_clip_titles", "attach_job_telemetry"]:
        monkeypatch.setattr(api, helper, lambda value: value)
    monkeypatch.setattr(api, "clip_sidecar_payload", lambda _: {"render_quality_qc": {"blocking": blocking}})
    monkeypatch.setattr(api, "youtube_monetization_preflight_issue", lambda *_: "Advertiser review required")
    monkeypatch.setattr(api, "codex_monetization_strategy", lambda *_: [])
    displayed = api.enrich_job_for_display(job).clips[0]
    assert displayed.render_qc_blocking is blocking
    assert displayed.render_qc_passed is False
    assert displayed.youtube_upload_ready is False
    assert displayed.youtube_upload_issue == "Advertiser review required"
