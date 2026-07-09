from api import (
    ClipJobRequest,
    MAX_AUTO_ANALYSIS_SECONDS,
    MAX_REQUESTED_CLIPS,
    _models_from_payload,
    choose_auto_analyze_seconds,
    max_clips_for_duration,
    normalize_job_request,
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
