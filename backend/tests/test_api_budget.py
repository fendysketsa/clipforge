from api import (
    ClipFile,
    ClipJob,
    ClipJobRequest,
    MAX_AUTO_ANALYSIS_SECONDS,
    MAX_REQUESTED_CLIPS,
    _models_from_payload,
    build_clipper_command,
    choose_auto_analyze_seconds,
    max_clips_for_duration,
    normalize_job_request,
    user_error_from_logs,
)


def test_max_clips_basic():
    # 600s video, 80% budget = 480s, min 35s -> 13 clips.
    assert max_clips_for_duration(600, 35) == 13


def test_max_clips_short_video():
    # 120s * 0.8 = 96s, min 35s -> 2 clips.
    assert max_clips_for_duration(120, 35) == 2


def test_max_clips_none_duration():
    assert max_clips_for_duration(None, 35) is None


def test_max_clips_at_least_one():
    assert max_clips_for_duration(40, 35) == 1


def test_normalize_clamps_target_to_budget(monkeypatch):
    import api

    monkeypatch.setattr(api, "probe_media_duration", lambda path: 120.0)
    req = ClipJobRequest(source_file="fake.mp4", top=20, min_duration=35, max_duration=180)
    out = normalize_job_request(req)
    assert out.top == 2  # clamped from 20 to budget cap


def test_normalize_keeps_under_budget_target(monkeypatch):
    import api

    monkeypatch.setattr(api, "probe_media_duration", lambda path: 600.0)
    req = ClipJobRequest(source_file="fake.mp4", top=3, min_duration=35, max_duration=180)
    out = normalize_job_request(req)
    assert out.top == 3


def test_normalize_clamps_manual_target_to_request_cap(monkeypatch):
    import api

    monkeypatch.setattr(api, "fetch_video_duration", lambda url: 7200.0)
    req = ClipJobRequest(url="https://youtu.be/x", top=30, min_duration=35, max_duration=180)
    out = normalize_job_request(req)
    assert out.top == MAX_REQUESTED_CLIPS


def test_auto_analyze_seconds_for_long_video_is_capped():
    assert choose_auto_analyze_seconds(7200) == MAX_AUTO_ANALYSIS_SECONDS


def test_models_from_openai_compatible_payload():
    payload = {"data": [{"id": "qwen2.5"}, {"id": "llama3.1"}]}
    assert _models_from_payload(payload) == ["llama3.1", "qwen2.5"]


def test_models_from_ollama_native_payload():
    payload = {"models": [{"name": "llama3.1:8b"}, {"name": "qwen2.5:7b"}]}
    assert _models_from_payload(payload) == ["llama3.1:8b", "qwen2.5:7b"]


def test_caption_color_validation():
    req = ClipJobRequest(url="https://youtu.be/x", caption_color="#abc")
    assert req.caption_color == "#ABC"


def test_caption_color_rejects_injection():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ClipJobRequest(url="https://youtu.be/x", caption_color="white' rm -rf")


def test_user_error_from_logs_prefers_cli_message():
    logs = [
        "Fetching metadata...",
        "USER_ERROR: Koneksi server ke YouTube gagal saat membaca metadata.",
    ]

    assert user_error_from_logs(logs) == "Koneksi server ke YouTube gagal saat membaca metadata."


def test_user_error_from_logs_detects_network_error():
    logs = ["ERROR: [download] Got error: [Errno 101] Network is unreachable"]

    assert "Upload Video" in (user_error_from_logs(logs) or "")


def test_create_job_rejects_when_another_job_is_active(monkeypatch):
    import api
    import pytest
    from fastapi import HTTPException

    active = ClipJob(
        id="active-job",
        status="running",
        request=ClipJobRequest(url="https://youtu.be/active"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    monkeypatch.setattr(api, "jobs", {active.id: active})

    with pytest.raises(HTTPException) as error:
        api.create_job(ClipJobRequest(url="https://youtu.be/new"))

    assert error.value.status_code == 409
    assert "aktif" in str(error.value.detail)


def test_build_clipper_command_forces_creative_commons_for_url_jobs():
    request = ClipJobRequest(url="https://youtu.be/source", require_creative_commons=False)

    command = build_clipper_command(request)

    assert "--require-creative-commons" in command


def test_build_clipper_command_does_not_require_creative_commons_for_uploaded_files():
    request = ClipJobRequest(source_file="/tmp/source.mp4", require_creative_commons=False)

    command = build_clipper_command(request)

    assert "--require-creative-commons" not in command


def test_delete_all_jobs_removes_only_process_jobs_and_preserves_clips(monkeypatch, tmp_path):
    import api

    outputs = tmp_path / "outputs"
    clip_path = outputs / "finished" / "clips" / "clip_01.mp4"
    clip_path.parent.mkdir(parents=True)
    clip_path.write_bytes(b"done")

    queued = ClipJob(
        id="queued-job",
        status="queued",
        request=ClipJobRequest(url="https://youtu.be/queued"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    failed = ClipJob(
        id="failed-job",
        status="failed",
        request=ClipJobRequest(url="https://youtu.be/failed"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[
            ClipFile(
                name="clip_01.mp4",
                url="/outputs/finished/clips/clip_01.mp4",
                size_bytes=4,
            )
        ],
    )
    completed = ClipJob(
        id="completed-job",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/completed"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[
            ClipFile(
                name="clip_01.mp4",
                url="/outputs/finished/clips/clip_01.mp4",
                size_bytes=4,
            )
        ],
    )

    monkeypatch.setattr(api, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(api, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(api, "JOBS_PATH", tmp_path / "jobs.json")
    monkeypatch.setattr(api, "jobs", {queued.id: queued, failed.id: failed, completed.id: completed})
    monkeypatch.setattr(api, "job_processes", {})
    monkeypatch.setattr(api, "job_secrets", {queued.id: "secret"})
    monkeypatch.setattr(api, "cancelled_job_ids", set())
    monkeypatch.setattr(api, "preserve_job_files_on_cancel", set())

    result = api.delete_all_jobs()

    assert result["status"] == "ok"
    assert result["removed_jobs"] == 2
    assert result["removed_outputs"] == 0
    assert api.jobs == {completed.id: completed}
    assert api.job_secrets == {}
    assert clip_path.exists()

    api.run_job(queued.id)
    assert queued.id not in api.cancelled_job_ids
