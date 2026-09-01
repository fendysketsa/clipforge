import clipper
import api


def test_cpu_threads_per_job_uses_parallel_safe_config(monkeypatch):
    monkeypatch.setattr(clipper.os, "cpu_count", lambda: 20)
    monkeypatch.setenv("FENDY_CLIPPER_CPU_THREADS_PER_JOB", "6")

    assert clipper.cpu_threads_per_job() == 6


def test_cpu_threads_per_job_clamps_invalid_and_oversized_values(monkeypatch):
    monkeypatch.setattr(clipper.os, "cpu_count", lambda: 8)
    monkeypatch.setenv("FENDY_CLIPPER_CPU_THREADS_PER_JOB", "invalid")
    assert clipper.cpu_threads_per_job() == 2

    monkeypatch.setenv("FENDY_CLIPPER_CPU_THREADS_PER_JOB", "99")
    assert clipper.cpu_threads_per_job() == 8


def test_high_quality_uses_fast_social_delivery_encode():
    preset = clipper.quality_preset("high")

    assert preset["preset"] == "fast"
    assert preset["crf"] == "18"
    assert preset["max_download_height"] == 2160


def test_standard_remains_full_hd_fast_path():
    preset = clipper.quality_preset("standard")

    assert preset["preset"] == "veryfast"
    assert preset["max_download_height"] == 1080


def test_startup_resumes_queued_and_interrupted_jobs(monkeypatch):
    queued = api.ClipJob(
        id="queued-job",
        status="queued",
        request=api.ClipJobRequest(source_file="queued.mp4"),
        created_at="2026-09-01T00:00:00+00:00",
        updated_at="2026-09-01T00:00:00+00:00",
    )
    running = api.ClipJob(
        id="running-job",
        status="running",
        request=api.ClipJobRequest(source_file="running.mp4"),
        created_at="2026-09-01T00:01:00+00:00",
        updated_at="2026-09-01T00:01:00+00:00",
        progress_percent=70,
        progress_stage="render",
    )
    retired = api.ClipJob(
        id="retired-job",
        status="running",
        request=api.ClipJobRequest(clip_mode="original_rebuild", url="https://youtu.be/old"),
        created_at="2026-09-01T00:02:00+00:00",
        updated_at="2026-09-01T00:02:00+00:00",
        progress_percent=40,
        progress_stage="selection",
    )
    started: list[str] = []

    class ImmediateThread:
        def __init__(self, *, target, args, daemon):
            self.args = args

        def start(self):
            started.append(self.args[0])

    monkeypatch.setattr(
        api,
        "jobs",
        {queued.id: queued, running.id: running, retired.id: retired},
    )
    monkeypatch.setattr(api, "save_jobs_unlocked", lambda: None)
    monkeypatch.setattr(api.threading, "Thread", ImmediateThread)

    api.resume_interrupted_clipping_jobs()

    assert started == ["queued-job", "running-job"]
    assert api.jobs["running-job"].status == "queued"
    assert api.jobs["running-job"].progress_stage == "queued"
    assert "backend restart" in api.jobs["running-job"].progress_detail.casefold()
    assert api.jobs["retired-job"].status == "failed"
    assert "dinonaktifkan" in (api.jobs["retired-job"].error or "")
