from cron_activity import summarize_activity


def summary(**changes):
    values = dict(reason="capacity_wait", message="Antrean penuh", run=None,
                  jobs=[], uploads=[], runtime={"phase": "waiting", "last_checked_at": "2026-11-14T01:00:00Z"})
    return summarize_activity(**(values | changes))


def test_capacity_wait_has_no_fake_progress():
    activity = summary()
    assert activity["state"] == "capacity_wait"
    assert activity["detail"] == "Antrean penuh"
    assert activity["progress_percent"] is None


def test_live_campaign_progress_wins_over_full_capacity():
    run = dict(status="running", trigger="schedule", updated_at="now", progress_percent=48,
               progress_stage="clip_transcript", message="Sumber 1/2: Membuat transkrip", processed=[{"job_id": "child"}])
    activity = summary(run=run, jobs=[dict(id="child", status="running", source_title="Sumber asli")])
    assert activity["state"] == "running"
    assert activity["detail"] == run["message"]
    assert activity["progress_percent"] == 48
    assert activity["source_title"] == "Sumber asli"
    run["status"] = "completed"
    assert summary(run=run)["state"] == "capacity_wait"


def test_upload_work_continues_while_new_cron_launches_are_disabled():
    activity = summary(reason="disabled", uploads=[dict(status="running", platform="TikTok", title="Clip", updated_at="now")])
    assert activity["state"] == "uploading"
    assert "TikTok" in activity["label"]
    assert "verifikasi" in activity["detail"]
    assert activity["progress_percent"] is None


def test_queued_upload_alone_is_not_reported_as_running():
    assert summary(uploads=[dict(status="queued", platform="YouTube")])["state"] == "capacity_wait"


def test_queued_video_does_not_claim_to_be_rendering():
    activity = summary(jobs=[dict(status="queued")])
    assert activity["state"] == "queued"
    assert activity["progress_percent"] is None


def test_independent_long_worker_is_visible():
    activity = summary(jobs=[dict(id="long", status="running", request={"clip_mode": "highlight_5m"},
        progress_detail="Merender bagian 4/8", progress_percent=65, updated_at="now")])
    assert activity["label"] == "Render Long berjalan"
    assert activity["progress_percent"] == 65


def test_transient_error_has_priority_over_an_idle_capacity_message():
    activity = summary(runtime={"last_error": "OSError", "phase": "retry_wait"})
    assert activity["state"] == "retry_wait"
    assert "OSError" in activity["detail"]


def test_actual_maintenance_is_distinct_from_waiting():
    assert summary(runtime={"phase": "checking"})["state"] == "checking"
    assert summary(reason="disabled", runtime={"phase": "checking"})["state"] == "disabled"
