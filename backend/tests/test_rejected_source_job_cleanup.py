"""Exhausted selections disappear only after cron saves their failure evidence."""
from copy import deepcopy

import pytest

import api


URL = "https://www.youtube.com/watch?v=abcdefghijk"


@pytest.fixture
def rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "OUTPUTS_DIR", tmp_path / "outputs")
    monkeypatch.setattr(api, "job_processes", {})
    monkeypatch.setattr(api, "job_secrets", {})
    monkeypatch.setattr(api, "cancelled_job_ids", set())
    stamp = api.now_iso()
    job = api.ClipJob(id="rejected", status="failed", created_at=stamp, updated_at=stamp,
        request=api.ClipJobRequest(url=URL),
        error=api.SHORT_SELECTION_REJECTION_PREFIX + " Gunakan sumber lain.",
        director_recovery={"attempted": True, "outcome": "replace_source"})
    row = dict(job_id=job.id, job_status="failed", status="failed", clip_count=0,
        url=URL, error=job.error, selection_rejected_at=stamp)
    run = api.AutoViralRun(id="campaign", status="running", trigger="schedule",
        created_at=stamp, updated_at=stamp, request=api.AutoViralRequest(), processed=[row])
    api.jobs[job.id] = job
    api.auto_viral_runs[run.id] = run
    api.save_jobs_unlocked()
    api.save_auto_viral_runs_unlocked()
    return job, run


def test_cleanup_keeps_checkpoint_cooldown_and_other_running_job(rejected):
    job, run = rejected
    active = job.model_copy(update={"id": "active", "status": "running", "error": None})
    api.jobs[active.id] = active
    before = api.AUTO_VIRAL_RUNS_PATH.read_bytes()
    api.job_secrets[job.id] = {"fixture": "secret"}
    assert api.cleanup_rejected_source_jobs_once() == 1
    assert api.jobs == {active.id: active}
    assert job.id not in api.job_secrets
    assert api.AUTO_VIRAL_RUNS_PATH.read_bytes() == before
    assert URL in api.recently_rejected_scheduled_source_urls()
    assert api.load_jobs().keys() == {active.id}
    assert api.cleanup_rejected_source_jobs_once() == 0


@pytest.mark.parametrize("guard", [
    "unread_result", "no_checkpoint", "manual", "held", "review", "worker",
    "workspace", "clips", "candidates", "network_error", "running", "repair", "rescue",
    "youtube", "tiktok", "other_consumer",
])
def test_recoverable_or_unconsumed_results_are_retained(rejected, guard):
    job, run = rejected
    if guard == "unread_result":
        run.processed[0].update(status="running", job_status="running")
    elif guard == "no_checkpoint":
        run.processed.clear()
    elif guard == "manual":
        run.trigger = "manual"
    elif guard == "held":
        job.request.publication_review_required = True
    elif guard == "review":
        job.request.review_only = True
    elif guard == "worker":
        api.job_processes[job.id] = object()
    elif guard == "workspace":
        (api.OUTPUTS_DIR / job.id).mkdir(parents=True)
        (api.OUTPUTS_DIR / job.id / "partial.mp4").write_bytes(b"partial")
    elif guard == "clips":
        job.clips = [api.ClipFile(name="clip.mp4", url="/outputs/clip.mp4", size_bytes=1)]
    elif guard == "candidates":
        job.candidates = [object()]
    elif guard == "network_error":
        job.error = "Download timeout"
    elif guard == "running":
        job.status = "running"
    elif guard in {"repair", "rescue"}:
        key = "repair_source_job_id" if guard == "repair" else "source_recovery_parent_job_id"
        api.jobs["child"] = job.model_copy(update={"id": "child", "status": "queued", key: job.id})
    elif guard == "youtube":
        api.youtube_uploads["upload"] = api.YouTubeUploadJob(id="upload", source_job_id=job.id,
            clip_url="/outputs/clip.mp4", clip_name="clip.mp4", title="Fixture",
            created_at=api.now_iso(), updated_at=api.now_iso(), status="failed")
    elif guard == "tiktok":
        api.tiktok_uploads["upload"] = api.TikTokUploadJob(id="upload", source_job_id=job.id,
            clip_url="/outputs/clip.mp4", clip_name="clip.mp4", caption="Fixture",
            target_handle="fixture",
            created_at=api.now_iso(), updated_at=api.now_iso(), status="failed",
            submission_accepted=True)
    elif guard == "other_consumer":
        run.processed.append(dict(job_id=job.id, status="running", job_status="running"))
    snapshot = deepcopy(run.processed)
    assert api.cleanup_rejected_source_jobs_once() == 0
    assert job.id in api.jobs
    assert run.processed == snapshot


def test_startup_cleans_legacy_card_without_enabling_uploads(rejected, monkeypatch):
    monkeypatch.setenv("AUTO_UPLOAD_COMPLETED_JOBS", "false")
    monkeypatch.setattr(api, "auto_viral_schedule_enabled_override", False)
    api.cleanup_rejected_source_jobs_on_startup()
    assert api.jobs == {}
    assert api.youtube_uploads == api.tiktok_uploads == {}
