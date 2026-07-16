import json
from pathlib import Path

from telegram_bot import (
    DEFAULT_SETTINGS,
    build_job_payload,
    canonical_youtube_url,
    format_duration,
    is_supported_video_url,
    load_state,
    normalize_settings,
    output_path_from_url,
    save_state,
    split_text,
)


def test_accepts_supported_youtube_urls():
    assert is_supported_video_url("https://youtu.be/demo")
    assert is_supported_video_url("https://www.youtube.com/watch?v=demo")
    assert is_supported_video_url("https://m.youtube.com/shorts/demo")


def test_rejects_non_youtube_and_invalid_urls():
    assert not is_supported_video_url("https://example.com/video")
    assert not is_supported_video_url("javascript:alert(1)")
    assert not is_supported_video_url("youtube.com/watch?v=demo")


def test_canonical_youtube_url_normalizes_common_forms():
    assert canonical_youtube_url("https://youtu.be/abcDEF12345") == "https://www.youtube.com/watch?v=abcDEF12345"
    assert canonical_youtube_url("https://www.youtube.com/watch?v=abcDEF12345&t=30") == (
        "https://www.youtube.com/watch?v=abcDEF12345"
    )
    assert canonical_youtube_url("https://youtube.com/shorts/abcDEF12345") == (
        "https://www.youtube.com/watch?v=abcDEF12345"
    )


def test_normalize_settings_keeps_only_clickable_options():
    settings = normalize_settings(
        {
            "top": 8,
            "min_duration": 15,
            "max_duration": 60,
            "video_quality": "max",
            "crop_mode": "streamer",
            "burn_subtitles": False,
            "ai_enabled": False,
            "caption_position": "bottom",
            "caption_font_size": 24,
        }
    )

    assert settings == {
        "top": 8,
        "min_duration": 15,
        "max_duration": 60,
        "video_quality": "max",
        "crop_mode": "streamer",
        "burn_subtitles": False,
        "ai_enabled": False,
        "caption_position": "bottom",
        "caption_font_size": 24,
    }


def test_invalid_settings_fall_back_to_defaults():
    settings = normalize_settings(
        {
            "top": 50,
            "min_duration": 1,
            "max_duration": 999,
            "video_quality": "ultra",
            "crop_mode": "unknown",
            "caption_font_size": 100,
        }
    )

    assert settings == DEFAULT_SETTINGS


def test_build_job_payload_matches_backend_contract():
    payload = build_job_payload(" https://youtu.be/demo ", {"top": 5, "crop_mode": "center"})

    assert payload["url"] == "https://youtu.be/demo"
    assert payload["top"] == 5
    assert payload["crop_mode"] == "center"
    assert payload["min_duration"] == 35
    assert payload["caption_font_size"] == 9


def test_output_path_is_confined_to_outputs(tmp_path: Path):
    clip = tmp_path / "video" / "clips" / "clip_01.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"video")

    assert output_path_from_url("/outputs/video/clips/clip_01.mp4", tmp_path) == clip
    assert output_path_from_url("/outputs/../secret.txt", tmp_path) is None
    assert output_path_from_url("/api/jobs", tmp_path) is None


def test_state_round_trip_and_recovery(tmp_path: Path):
    state_path = tmp_path / "data" / "telegram_state.json"
    state = load_state(state_path)
    state["update_offset"] = 42
    state["pending_url"] = "https://youtu.be/demo"
    save_state(state, state_path)

    restored = load_state(state_path)
    assert restored["update_offset"] == 42
    assert restored["pending_url"] == "https://youtu.be/demo"

    state_path.write_text("not-json", encoding="utf-8")
    recovered = load_state(state_path)
    assert recovered["update_offset"] == 0
    assert recovered["settings"] == DEFAULT_SETTINGS


def test_saved_state_is_valid_utf8_json(tmp_path: Path):
    state_path = tmp_path / "state.json"
    state = load_state(state_path)
    state["pending_url"] = "https://youtu.be/pendidikan"
    save_state(state, state_path)

    assert json.loads(state_path.read_text(encoding="utf-8"))["pending_url"].endswith("pendidikan")


def test_text_and_duration_formatting():
    assert format_duration(3723) == "1j 2m 3d"
    assert format_duration(65) == "1m 5d"
    assert format_duration(8) == "8d"
    assert split_text("satu dua tiga empat", 10) == ["satu dua", "tiga empat"]
