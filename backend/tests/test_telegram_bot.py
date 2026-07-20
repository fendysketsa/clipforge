import json
from pathlib import Path

from telegram_bot import (
    ClipForgeTelegramBot,
    DEFAULT_SETTINGS,
    TELEGRAM_COMPILATION_MAX_SECONDS,
    battery_status_text,
    build_job_payload,
    canonical_youtube_url,
    collect_unuploaded_clip_entries,
    format_duration,
    is_supported_video_url,
    is_compilation_result,
    load_state,
    normalize_settings,
    output_path_from_url,
    parse_battery_alert_levels,
    read_battery_status,
    save_state,
    split_text,
    unuploaded_clip_status,
)


def test_accepts_supported_youtube_urls():
    assert is_supported_video_url("https://youtu.be/demo")
    assert is_supported_video_url("https://www.youtube.com/watch?v=demo")
    assert is_supported_video_url("https://m.youtube.com/shorts/demo")


def test_upload_preflight_queues_without_blocking_login_once():
    messages = []

    class Backend:
        def youtube_config(self):
            return {
                "playwright_installed": True,
                "enabled": True,
                "upload_uses_cdp": False,
                "direct_profile_upload": False,
            }

        def setup_youtube_one_time_login(self):
            raise AssertionError("preflight must not run the long Login Sekali request")

    bot = object.__new__(ClipForgeTelegramBot)
    bot.backend = Backend()
    bot.send_message = lambda chat_id, text, markup=None: messages.append((chat_id, text, markup))
    bot.youtube_control_keyboard = lambda: {}

    assert bot.prepare_youtube_upload_session(123, reason="retry upload") is True
    assert "Antrean dibuat sekarang" in messages[-1][1]


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
        "clip_mode": "short",
        "top": 8,
        "min_duration": 15,
        "max_duration": 60,
        "video_quality": "max",
        "crop_mode": "streamer",
        "burn_subtitles": False,
        "ai_enabled": False,
        "ai_base_url": DEFAULT_SETTINGS["ai_base_url"],
        "ai_model": DEFAULT_SETTINGS["ai_model"],
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
    assert payload["min_duration"] == 15
    assert payload["max_duration"] == 60
    assert payload["caption_font_size"] == 10
    assert payload["clip_mode"] == "short"
    assert payload["compilation_target_seconds"] == TELEGRAM_COMPILATION_MAX_SECONDS == 300
    assert payload["remove_running_text"] is True


def test_telegram_cta_migrates_highlight_state_to_short_only_mode():
    settings = normalize_settings({"clip_mode": "highlight_5m", "top": 5})
    payload = build_job_payload("https://youtu.be/demo", settings)

    assert settings["clip_mode"] == "short"
    assert payload["clip_mode"] == "short"
    assert payload["top"] == 5
    assert payload["compilation_target_seconds"] == 300


def test_compilation_result_is_detected_from_export_name():
    assert is_compilation_result({"name": "highlight_5menit_poin-penting.mp4"})
    assert not is_compilation_result({"name": "clip_01_poin-penting.mp4"})


def test_output_path_is_confined_to_outputs(tmp_path: Path):
    clip = tmp_path / "video" / "clips" / "clip_01.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"video")

    assert output_path_from_url("/outputs/video/clips/clip_01.mp4", tmp_path) == clip
    assert output_path_from_url("/outputs/../secret.txt", tmp_path) is None
    assert output_path_from_url("/api/jobs", tmp_path) is None


def test_unuploaded_clip_list_filters_completed_and_keeps_score_and_folder(tmp_path: Path):
    clips_dir = tmp_path / "kajian-malam" / "clips"
    clips_dir.mkdir(parents=True)
    for name, score in (
        ("clip_01_sudah.mp4", 91),
        ("clip_02_gagal.mp4", 82),
        ("highlight_5menit_pilihan.mp4", 76),
    ):
        path = clips_dir / name
        path.write_bytes(b"video")
        path.with_suffix(".json").write_text(
            json.dumps({"score": score, "fyp_label": "Kuat"}),
            encoding="utf-8",
        )
    clips = [
        {
            "name": "clip_01_sudah.mp4",
            "url": "/outputs/kajian-malam/clips/clip_01_sudah.mp4",
            "title": "Sudah Upload",
        },
        {
            "name": "clip_02_gagal.mp4",
            "url": "/outputs/kajian-malam/clips/clip_02_gagal.mp4",
            "title": "Upload Gagal",
        },
        {
            "name": "highlight_5menit_pilihan.mp4",
            "url": "/outputs/kajian-malam/clips/highlight_5menit_pilihan.mp4",
            "title": "Kompilasi Pilihan",
        },
    ]
    jobs = [
        {
            "id": "job-1",
            "status": "completed",
            "finished_at": "2026-07-19T10:00:00+07:00",
            "clips": clips,
            "candidates": [],
        }
    ]
    uploads = [
        {
            "id": "done",
            "clip_url": clips[0]["url"],
            "status": "completed",
            "updated_at": "2026-07-19T11:00:00+07:00",
        },
        {
            "id": "failed-after-done",
            "clip_url": clips[0]["url"],
            "status": "failed",
            "updated_at": "2026-07-19T12:00:00+07:00",
        },
        {
            "id": "failed",
            "clip_url": clips[1]["url"],
            "status": "failed",
            "updated_at": "2026-07-19T12:00:00+07:00",
        },
    ]

    entries = collect_unuploaded_clip_entries(jobs, uploads, tmp_path)

    assert [entry["clip_name"] for entry in entries] == [
        "clip_02_gagal.mp4",
        "highlight_5menit_pilihan.mp4",
    ]
    assert entries[0]["folder"] == "outputs/kajian-malam/clips"
    assert entries[0]["fyp_score"] == 82
    assert unuploaded_clip_status(entries[0]) == "Upload gagal"
    assert entries[1]["is_compilation"] is True
    assert unuploaded_clip_status(entries[1]) == "Belum pernah diupload"


def test_unuploaded_clip_keyboard_uses_retry_status_and_upload_actions():
    entries = [
        {
            "job_id": "job-a",
            "clip_index": 1,
            "fyp_score": 81,
            "latest_upload": {"id": "upload-failed", "status": "failed"},
        },
        {
            "job_id": "job-a",
            "clip_index": 2,
            "fyp_score": 74,
            "latest_upload": {"id": "upload-running", "status": "running"},
        },
        {
            "job_id": "job-a",
            "clip_index": 3,
            "fyp_score": 68,
            "latest_upload": None,
        },
    ]

    markup = ClipForgeTelegramBot.unuploaded_clips_keyboard(object(), entries, 0)
    callbacks = [
        item["callback_data"]
        for row in markup["inline_keyboard"]
        for item in row
        if "callback_data" in item
    ]

    assert "ytretry:upload-failed" in callbacks
    assert "ytview:upload-running" in callbacks
    assert "ytup:job-a:3" in callbacks
    assert "unuploaded:0" in callbacks


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


def test_reads_linux_battery_status(tmp_path: Path):
    battery = tmp_path / "BAT1"
    mains = tmp_path / "AC"
    battery.mkdir()
    mains.mkdir()
    (battery / "type").write_text("Battery\n", encoding="utf-8")
    (battery / "capacity").write_text("27\n", encoding="utf-8")
    (battery / "status").write_text("Charging\n", encoding="utf-8")
    (mains / "type").write_text("Mains\n", encoding="utf-8")

    status = read_battery_status(tmp_path)

    assert status == {
        "percent": 27,
        "status": "Charging",
        "device": "BAT1",
        "batteries": [{"device": "BAT1", "percent": 27, "status": "Charging"}],
    }
    assert "Sisa: 27%" in battery_status_text(status)
    assert "Sedang diisi" in battery_status_text(status)


def test_battery_reader_returns_none_when_no_battery_exists(tmp_path: Path):
    assert read_battery_status(tmp_path) is None


def test_battery_alert_levels_are_valid_unique_and_descending():
    assert parse_battery_alert_levels("5, 20,10,20,bad,0,101") == (20, 10, 5)


def test_viral_exclusions_include_every_displayed_suggestion():
    bot = object.__new__(ClipForgeTelegramBot)
    bot.state = {
        "viral_video_seen_urls": ["https://youtu.be/alreadySeen1"],
        "viral_video_suggestions": {
            "a": {"url": "https://youtu.be/displayed01"},
            "b": {"url": "https://www.youtube.com/watch?v=displayed02"},
        },
        "jobs": {},
        "pending_url": "",
    }

    assert ClipForgeTelegramBot.viral_exclude_urls(bot) == [
        "https://www.youtube.com/watch?v=alreadySeen1",
        "https://www.youtube.com/watch?v=displayed01",
        "https://www.youtube.com/watch?v=displayed02",
    ]


def test_remember_viral_sources_marks_all_results_not_only_selected_one():
    bot = object.__new__(ClipForgeTelegramBot)
    bot.state = {"viral_video_seen_urls": ["https://youtu.be/alreadySeen1"]}

    ClipForgeTelegramBot.remember_viral_sources(
        bot,
        [
            {"url": "https://youtu.be/newVideo001"},
            {"url": "https://www.youtube.com/watch?v=newVideo002"},
            {"url": "https://youtu.be/newVideo001"},
        ],
    )

    assert bot.state["viral_video_seen_urls"] == [
        "https://www.youtube.com/watch?v=alreadySeen1",
        "https://www.youtube.com/watch?v=newVideo001",
        "https://www.youtube.com/watch?v=newVideo002",
    ]


def test_youtube_control_keyboard_includes_merge_session():
    class DummyBot:
        def latest_retryable_youtube_upload_id(self):
            return None

    markup = ClipForgeTelegramBot.youtube_control_keyboard(DummyBot())
    callbacks = [
        button["callback_data"]
        for row in markup["inline_keyboard"]
        for button in row
        if "callback_data" in button
    ]

    assert "ytcdp" in callbacks
    assert "ytsync" in callbacks
    assert "ytnocdp" in callbacks
    assert "ytprofile" in callbacks
    assert "ytsession" in callbacks


def test_youtube_session_capture_lines_reports_success():
    lines = ClipForgeTelegramBot.youtube_session_capture_lines(
        object(),
        {"logs": ["Sesi YouTube dari browser tersimpan: /tmp/youtube_storage_state.json"]},
    )

    assert lines[0] == "Merge session YouTube selesai."
    assert "Storage-state: tersimpan/terbarui" in lines


def test_youtube_cdp_result_lines_reports_browser_login_fallback_as_in_progress():
    lines = ClipForgeTelegramBot.youtube_cdp_result_lines(
        object(),
        {
            "ok": False,
            "cdp_ready": False,
            "session_ready": False,
            "login_required": True,
            "message": "Selesaikan login; koneksi ulang berjalan otomatis.",
            "logs": [],
        },
        success_title="Session siap.",
        failure_title="Session gagal.",
    )

    assert lines[0] == "Jendela login YouTube sudah dibuka."
    assert "Info: Selesaikan login; koneksi ulang berjalan otomatis." in lines
    assert not any(line.startswith("Alasan:") for line in lines)


def test_job_keyboard_allows_delete_for_failed_and_queued_jobs():
    failed_markup = ClipForgeTelegramBot.job_keyboard(
        object(),
        {"id": "failed-job", "status": "failed", "clips": []},
    )
    queued_markup = ClipForgeTelegramBot.job_keyboard(
        object(),
        {"id": "queued-job", "status": "queued", "clips": []},
    )

    failed_callbacks = [
        button["callback_data"]
        for row in failed_markup["inline_keyboard"]
        for button in row
        if "callback_data" in button
    ]
    queued_callbacks = [
        button["callback_data"]
        for row in queued_markup["inline_keyboard"]
        for button in row
        if "callback_data" in button
    ]

    assert "deleteask:failed-job" in failed_callbacks
    assert "deleteask:queued-job" in queued_callbacks
