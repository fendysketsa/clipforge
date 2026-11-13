"""Cron cleanup must never erase an active or uncertain upload's input."""
import json
from types import SimpleNamespace

import pytest

import api
import automatic_output_cleanup as cleanup
import long_video_qc
import youtube_uploader


@pytest.fixture
def output(monkeypatch, tmp_path):
    root = tmp_path / "outputs"
    work = root / "cron" / "source"
    media = work / "clips" / "resume_cerita_demo.mp4"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"rendered output")
    media.with_suffix(".json").write_text("{}")
    (work / "audio.wav").write_bytes(b"intermediate")
    monkeypatch.setattr(api, "OUTPUTS_DIR", root)
    monkeypatch.setattr(api, "long_qc_active", set())
    monkeypatch.setattr(api, "job_processes", {})
    monkeypatch.setattr(api, "youtube_upload_processes", {})
    monkeypatch.setattr(api, "tiktok_upload_processes", {})
    monkeypatch.setattr(api, "long_qc_context", lambda *args: {"source": "fixture"})
    job = api.ClipJob(id="cron", status="completed", created_at=api.now_iso(), updated_at=api.now_iso(),
        request=api.ClipJobRequest(url="https://www.youtube.com/watch?v=abcdefghijk",
            clip_mode="highlight_5m", publication_review_required=True, scheduled_public_source_credit=True),
        clips=[api.ClipFile(name=media.name, url="/outputs/cron/source/clips/" + media.name,
            size_bytes=media.stat().st_size)])
    api.jobs[job.id] = job
    api.save_jobs_unlocked()
    api.save_long_production_state(dict(enabled=True, daily_target=1, auto_qc_enabled=True,
        auto_qc_private_upload=True, attempts=[dict(day="2026-11-13", job_id=job.id,
            short_job_id="short", status="completed")]))
    record = dict(status="reviewed", audit={"decision": "DROP_SOURCE", "upload_allowed": False},
        fingerprint=long_video_qc.fingerprint(media, api.long_qc_context(job, job.clips[0])))
    api.save_long_qc(api.long_qc_path(job.id, job.clips[0].url), record)
    return job, media, record


def youtube(job, **updates):
    return api.YouTubeUploadJob(id="youtube", source_job_id=job.id, clip_url=job.clips[0].url,
        clip_name=job.clips[0].name, title="Fixture", status="failed",
        created_at=api.now_iso(), updated_at=api.now_iso()).model_copy(update=updates)


def tiktok(job, **updates):
    return api.TikTokUploadJob(id="tiktok", source_job_id=job.id, clip_url=job.clips[0].url,
        clip_name=job.clips[0].name, caption="Fixture", status="failed", target_handle="fixture",
        created_at=api.now_iso(), updated_at=api.now_iso()).model_copy(update=updates)


def test_terminal_qc_deletes_card_and_workspace_but_keeps_confirmed_tiktok(output):
    job, media, record = output
    post = tiktok(job, status="completed", upload_confirmed=True,
        profile_url="https://www.tiktok.com/@fixture/video/7707449979572374804")
    api.tiktok_uploads[post.id] = post
    api.save_tiktok_uploads_unlocked()
    before = api.TIKTOK_UPLOADS_PATH.read_bytes()
    assert api.cleanup_terminal_cron_outputs_once() == 1
    assert job.id not in api.jobs and not media.parent.parent.exists()
    assert api.TIKTOK_UPLOADS_PATH.read_bytes() == before
    assert api.tiktok_uploads[post.id] == post
    assert api.long_production_state()["attempts"][0]["disposition"] == "deleted_terminal_output"
    audit = next(iter(json.loads(api.terminal_output_cleanup_path().read_text()).values()))
    assert audit["status"] == "deleted" and audit["reason"] == "long_qc_drop_source"
    assert audit["retained_upload_ids"] == [post.id]
    assert api.cleanup_terminal_cron_outputs_once() == 0


@pytest.mark.parametrize("platform,updates", [
    ("youtube", {"status": "running"}),
    ("youtube", {"status": "queued"}),
    ("youtube", {"video_url": "https://www.youtube.com/watch?v=abcdefghijk"}),
    ("youtube", {"logs": ["Video dipilih: fixture.mp4"]}),
    ("youtube", {"logs": ["Menyerahkan file ke YouTube Studio: fixture.mp4"]}),
    ("youtube", {"file_selection_started": True,
        "logs": [cleanup.EXHAUSTED_BEFORE_FILE + " stale marker"]}),
    ("youtube", {"error": "timeout"}),
    ("tiktok", {"status": "running"}),
    ("tiktok", {"submission_accepted": True}),
    ("tiktok", {"submission_started": True}),
    ("tiktok", {"logs": ["POST_SUBMIT_INTENT: requested"]}),
    ("tiktok", {"error": "unknown error"}),
    ("tiktok", {"auto_retry_count": 2, "error": api.automatic_retry.TIKTOK_BROWSER_UNAVAILABLE}),
])
def test_active_or_uncertain_platform_keeps_file_even_when_qc_rejects(output, platform, updates):
    job, media, _ = output
    row = youtube(job, **updates) if platform == "youtube" else tiktok(job, **updates)
    getattr(api, platform + "_uploads")[row.id] = row
    assert api.cleanup_terminal_cron_outputs_once() == 0
    assert media.exists() and job.id in api.jobs


@pytest.mark.parametrize("guard", ["manual", "disabled", "qc_active", "render_active", "repair_active", "admission"])
def test_only_idle_authorized_cron_artifacts_are_removed(output, monkeypatch, guard):
    job, media, _ = output
    if guard == "manual":
        job.request.scheduled_public_source_credit = False
    elif guard == "disabled":
        monkeypatch.setenv("AUTO_UPLOAD_TERMINAL_CLEANUP_ENABLED", "false")
    elif guard == "qc_active":
        api.long_qc_active.add(job.id + "\n" + job.clips[0].url)
    elif guard == "render_active":
        api.job_processes[job.id] = object()
    elif guard == "repair_active":
        api.jobs["repair"] = job.model_copy(update=dict(id="repair", status="running", clips=[],
            repair_source_job_id=job.id, repair_source_clip_url=job.clips[0].url))
    elif guard == "admission":
        api.youtube_upload_creation_lock.acquire()
    try:
        assert api.cleanup_terminal_cron_outputs_once() == 0
        assert media.exists()
    finally:
        if guard == "admission":
            api.youtube_upload_creation_lock.release()


def test_sibling_output_and_shared_workspace_survive(output):
    job, media, _ = output
    sibling = media.with_name("other.mp4")
    sibling.write_bytes(b"keep")
    clip = api.ClipFile(name=sibling.name, url=job.clips[0].url.replace(media.name, sibling.name), size_bytes=4)
    api.jobs["sibling"] = job.model_copy(update=dict(id="sibling", clips=[clip]))
    assert api.cleanup_terminal_cron_outputs_once() == 1
    assert not media.exists() and sibling.read_bytes() == b"keep"
    assert "sibling" in api.jobs


def test_partial_job_cleanup_does_not_mark_remaining_clips_discarded(output):
    job, media, _ = output
    sibling = media.with_name("other.mp4")
    sibling.write_bytes(b"keep")
    job.clips.append(api.ClipFile(name=sibling.name,
        url=job.clips[0].url.replace(media.name, sibling.name), size_bytes=4))
    assert api.cleanup_terminal_cron_outputs_once() == 1
    assert "disposition" not in api.long_production_state()["attempts"][0]
    assert job.id in api.jobs and sibling.exists()


def test_cron_checkpoint_is_terminal_after_its_last_output_is_deleted(output):
    job, _, _ = output
    run = api.AutoViralRun(id="parent", status="completed", trigger="schedule",
        created_at=api.now_iso(), updated_at=api.now_iso(), request=api.AutoViralRequest(),
        processed=[{"job_id": "short", "long_job_id": job.id, "status": "completed"}])
    api.auto_viral_runs[run.id] = run
    assert api.cleanup_terminal_cron_outputs_once() == 1
    assert run.processed[0]["status"] == "completed"
    assert run.processed[0]["long_upload_status"] == "output_deleted"


def test_shared_exact_media_is_never_unlinked(output):
    job, media, _ = output
    api.jobs["sibling"] = job.model_copy(update={"id": "sibling"})
    assert api.cleanup_terminal_cron_outputs_once() == 0
    assert media.exists()


def test_nested_workspace_referenced_by_another_job_is_preserved(output):
    job, media, _ = output
    nested = media.parent.parent / "nested" / "clips" / "keep.mp4"
    nested.parent.mkdir(parents=True)
    nested.write_bytes(b"keep nested output")
    clip = api.ClipFile(name=nested.name, url="/outputs/cron/source/nested/clips/keep.mp4", size_bytes=18)
    api.jobs["nested"] = job.model_copy(update=dict(id="nested", clips=[clip]))
    assert api.cleanup_terminal_cron_outputs_once() == 1
    assert not media.exists() and nested.read_bytes() == b"keep nested output"


def test_changed_evidence_is_not_deleted_from_stale_qc(output):
    _, media, _ = output
    media.write_bytes(b"changed artifact")
    assert api.cleanup_terminal_cron_outputs_once() == 0
    assert media.exists()


def test_proven_before_file_failure_cleans_after_bounded_recovery_without_qc(output):
    job, media, _ = output
    api.long_qc_path(job.id, job.clips[0].url).unlink()
    row = youtube(job, logs=[cleanup.EXHAUSTED_BEFORE_FILE + " exhausted"])
    api.youtube_uploads[row.id] = row
    assert api.cleanup_terminal_cron_outputs_once() == 1
    assert not media.exists() and api.youtube_uploads[row.id] == row


def test_tiktok_exhausted_pre_post_retry_is_terminal(output):
    job, _, _ = output
    api.long_qc_path(job.id, job.clips[0].url).unlink()
    row = tiktok(job, auto_retry_count=3, error=api.automatic_retry.TIKTOK_BROWSER_UNAVAILABLE)
    api.tiktok_uploads[row.id] = row
    assert api.cleanup_terminal_cron_outputs_once() == 1
    assert api.tiktok_uploads[row.id] == row


def test_qc_outage_gets_three_attempts_then_cleanup_without_fake_pass(output, monkeypatch):
    job, media, _ = output
    api.long_qc_path(job.id, job.clips[0].url).unlink()
    calls = []
    def audit(*args):
        calls.append(True)
        return dict(status="waiting_for_ai_or_evidence", audit=None, reason="ai_http_503")
    monkeypatch.setattr(long_video_qc, "audit_long", audit)
    for _ in range(3):
        api.run_long_qc(job.id, job.clips[0].url)
    record = json.loads(api.long_qc_path(job.id, job.clips[0].url).read_text())
    assert record["review_attempts"] == 3 and record["audit"] is None
    assert record["cleanup_requested_reason"] == "long_qc_unavailable_exhausted"
    api.run_long_qc(job.id, job.clips[0].url)
    assert len(calls) == 3
    assert api.cleanup_terminal_cron_outputs_once() == 1
    assert not media.exists()


def test_failed_enqueue_is_bounded_and_a_confirmed_tiktok_is_preserved(output, monkeypatch):
    job, media, record = output
    record["audit"] = dict(decision="PASS_UPLOAD", upload_allowed=True)
    api.save_long_qc(api.long_qc_path(job.id, job.clips[0].url), record)
    monkeypatch.setattr(api, "youtube_monetization_preflight_issue", lambda *args: None)
    def unavailable():
        raise RuntimeError("browser unavailable")
    monkeypatch.setattr(api, "require_youtube_ready", unavailable)
    post = tiktok(job, status="completed", upload_confirmed=True, profile_url="https://www.tiktok.com/@fixture/video/123")
    api.tiktok_uploads[post.id] = post
    for _ in range(3):
        api.run_long_qc(job.id, job.clips[0].url)
    saved = json.loads(api.long_qc_path(job.id, job.clips[0].url).read_text())
    assert saved["youtube_enqueue_failures"] == 3
    assert api.cleanup_terminal_cron_outputs_once() == 1
    assert api.tiktok_uploads[post.id] == post and not media.exists()


def test_delete_failure_keeps_card_and_retries_on_next_tick(output, monkeypatch):
    job, media, _ = output
    real_cleanup = api.cleanup_output_work_dirs
    def fail(*args, **kwargs):
        raise PermissionError("fixture")
    monkeypatch.setattr(api, "cleanup_output_work_dirs", fail)
    assert api.cleanup_terminal_cron_outputs_once() == 0
    assert job.id in api.jobs
    history = json.loads(api.terminal_output_cleanup_path().read_text())
    assert next(iter(history.values()))["status"] == "delete_failed"
    monkeypatch.setattr(api, "cleanup_output_work_dirs", real_cleanup)
    # The media may already be unlinked; its saved terminal decision still owns cleanup.
    assert api.cleanup_terminal_cron_outputs_once() == 1
    assert job.id not in api.jobs


@pytest.mark.parametrize("selection_started", [False, True])
def test_uploader_certifies_only_explicit_pre_file_failures(monkeypatch, capsys, selection_started):
    parser = SimpleNamespace(parse_args=lambda: SimpleNamespace(command="upload"))
    monkeypatch.setattr(youtube_uploader, "build_parser", lambda: parser)
    def fail(args):
        youtube_uploader.UPLOAD_FILE_SELECTION_STARTED = selection_started
        raise youtube_uploader.UploadError("fixture failure")
    monkeypatch.setattr(youtube_uploader, "run_upload", fail)
    assert youtube_uploader.main() == 2
    assert (cleanup.BEFORE_FILE_FAILURE in capsys.readouterr().out) is (not selection_started)
