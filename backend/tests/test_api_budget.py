from datetime import datetime, timedelta, timezone
from pathlib import Path

from api import (
    ClipFile,
    ClipJob,
    ClipJobRequest,
    MAX_AUTO_ANALYSIS_SECONDS,
    MAX_REQUESTED_CLIPS,
    ViralVideoSearchRequest,
    _models_from_payload,
    auto_viral_candidate_score,
    build_clipper_command,
    choose_auto_analyze_seconds,
    default_viral_video_search_queries,
    is_creative_commons_info,
    is_fresh_viral_upload,
    max_clips_for_duration,
    normalize_job_request,
    processed_job_source_urls,
    safe_youtube_visibility,
    unresolved_codex_ideas,
    youtube_cdp_start_needed,
    youtube_upload_staging_filter,
    user_error_from_logs,
    viral_source_rejection_reason,
    youtube_upload_clean_metadata_args,
    youtube_published_after,
)


def test_max_clips_basic():
    # 600s video, 80% budget = 480s, min 35s -> 13 clips.
    assert max_clips_for_duration(600, 35) == 13


def test_max_clips_short_video():
    # 120s * 0.8 = 96s, min 35s -> 2 clips.
    assert max_clips_for_duration(120, 35) == 2


def test_max_clips_none_duration():
    assert max_clips_for_duration(None, 35) is None


def test_legacy_codex_ideas_are_hidden_when_saved_plan_already_resolved_them():
    sidecar = {
        "enhanced_edit": True,
        "output_format": "vertical_short",
        "codex_edit_plan": {
            "hook_boost": True,
            "tempo_boost": True,
            "ending_boost": True,
            "loop_boost": False,
        },
    }
    ideas = [
        "Alur — ringkas konteks awal.",
        "Ending — sisakan jawaban paling tegas.",
        "Loop — buat callback ke hook.",
    ]

    assert unresolved_codex_ideas(sidecar, ideas) == []


def test_upload_staging_keeps_compilation_landscape():
    value = youtube_upload_staging_filter(Path("highlight_5menit_pilihan.mp4"))

    assert "scale=1280:720" in value
    assert "pad=1280:720" in value


def test_upload_staging_keeps_short_vertical():
    value = youtube_upload_staging_filter(Path("clip_01_pilihan.mp4"))

    assert "scale=720:1280" in value
    assert "pad=720:1280" in value


def test_max_clips_at_least_one():
    assert max_clips_for_duration(40, 35) == 1


def test_normalize_clamps_target_to_budget(monkeypatch):
    import api

    monkeypatch.setattr(api, "probe_media_duration", lambda path: 120.0)
    req = ClipJobRequest(source_file="fake.mp4", top=20, min_duration=35, max_duration=180)
    out = normalize_job_request(req)
    assert out.top == 2  # clamped from 20 to budget cap
    assert out.max_duration == 60


def test_short_defaults_are_fast_fyp_length():
    request = ClipJobRequest(source_file="fake.mp4")

    assert request.min_duration == 15
    assert request.max_duration == 60


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


def test_viral_search_only_accepts_uploads_from_last_30_days():
    today = datetime.now(timezone.utc)
    fresh = {"upload_date": (today - timedelta(days=30)).strftime("%Y%m%d")}
    stale = {"upload_date": (today - timedelta(days=31)).strftime("%Y%m%d")}

    assert is_fresh_viral_upload(fresh, 30) is True
    assert is_fresh_viral_upload(stale, 30) is False
    assert is_fresh_viral_upload({"upload_date": ""}, 30) is False


def test_youtube_published_after_uses_requested_search_window():
    threshold = datetime.fromisoformat(youtube_published_after(30).replace("Z", "+00:00"))
    age = datetime.now(timezone.utc) - threshold

    assert timedelta(days=29, hours=23) < age < timedelta(days=30, minutes=1)
    fallback_threshold = datetime.fromisoformat(youtube_published_after(180).replace("Z", "+00:00"))
    fallback_age = datetime.now(timezone.utc) - fallback_threshold
    assert timedelta(days=179, hours=23) < fallback_age < timedelta(days=180, minutes=1)


def test_viral_search_is_broad_and_supports_staged_fallback():
    import pytest
    from pydantic import ValidationError

    queries = default_viral_video_search_queries()
    assert len(queries) >= 120
    assert "misteri dalam islam" in queries
    assert "podcast horor indonesia" in queries
    assert "podcast cerita seram indonesia" in queries
    assert "cerita horor pendakian gunung" in queries
    assert "cerita horor kos angker" in queries
    assert "urban legend kalimantan" in queries
    assert queries.index("podcast horor indonesia") < 12
    assert "mitos dan fakta menurut islam" in queries
    assert ViralVideoSearchRequest().search_limit_per_query == 25
    assert ViralVideoSearchRequest().max_metadata_checks == 200
    assert ViralVideoSearchRequest(max_age_days=180).max_age_days == 180
    with pytest.raises(ValidationError):
        ViralVideoSearchRequest(max_age_days=366)


def test_configured_viral_queries_are_extended_not_replaced(monkeypatch):
    monkeypatch.setenv("VIRAL_CC_SEARCH_QUERIES", "topik khusus|podcast indonesia terbaru")

    queries = default_viral_video_search_queries()

    assert queries[0] == "topik khusus"
    assert queries.count("podcast indonesia terbaru") == 1
    assert len(queries) >= 120
    assert queries.index("misteri dalam islam") < 10
    assert queries.index("podcast horor indonesia") < 12


def test_processed_job_sources_are_always_excluded(monkeypatch):
    import api

    job = ClipJob(
        id="processed-job",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/abcDEF12345"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        source_url="https://www.youtube.com/watch?v=secondID6789",
    )
    monkeypatch.setattr(api, "jobs", {job.id: job})
    monkeypatch.setattr(api, "processed_source_history", {"https://youtu.be/permanent77"})

    assert processed_job_source_urls() == {
        "https://www.youtube.com/watch?v=abcDEF12345",
        "https://www.youtube.com/watch?v=secondID6789",
        "https://www.youtube.com/watch?v=permanent77",
    }


def test_viral_score_prefers_faster_recent_growth():
    today = datetime.now(timezone.utc)
    recent = {
        "upload_date": (today - timedelta(days=2)).strftime("%Y%m%d"),
        "view_count": 100_000,
        "like_count": 5_000,
        "duration": 600,
    }
    older = {
        **recent,
        "upload_date": (today - timedelta(days=25)).strftime("%Y%m%d"),
    }

    assert auto_viral_candidate_score(recent) > auto_viral_candidate_score(older)


def test_viral_score_rewards_real_engagement_not_views_alone():
    today = datetime.now(timezone.utc)
    base = {
        "upload_date": (today - timedelta(days=3)).strftime("%Y%m%d"),
        "view_count": 100_000,
        "duration": 600,
    }

    assert auto_viral_candidate_score({**base, "like_count": 8_000}) > auto_viral_candidate_score(
        {**base, "like_count": 100}
    )


def test_viral_license_must_be_explicit_creative_commons():
    assert is_creative_commons_info({"license": "Creative Commons Attribution license"})
    assert is_creative_commons_info({"license": "CC-BY-4.0"})
    assert not is_creative_commons_info({"license": "reuse allowed"})
    assert not is_creative_commons_info({"license": ""})


def test_viral_source_rejects_live_restricted_or_non_public_video():
    base = {"license": "Creative Commons", "availability": "public"}

    assert viral_source_rejection_reason(base) is None
    assert "live" in (viral_source_rejection_reason({**base, "is_live": True}) or "")
    assert "berusia" in (viral_source_rejection_reason({**base, "age_limit": 18}) or "")
    assert "publik" in (
        viral_source_rejection_reason({**base, "availability": "subscriber_only"}) or ""
    )


def test_upload_staging_drops_source_metadata():
    args = youtube_upload_clean_metadata_args()

    assert args[:2] == ["-map_metadata", "-1"]
    assert "-map_metadata:s:v" in args
    assert "-map_metadata:s:a" in args
    assert "handler_name=" in args
    assert "license=" in args


def test_youtube_auto_upload_is_private_unless_public_is_explicitly_allowed(monkeypatch):
    monkeypatch.setenv("YOUTUBE_DEFAULT_VISIBILITY", "public")
    monkeypatch.delenv("YOUTUBE_ALLOW_PUBLIC_AUTO_UPLOAD", raising=False)

    assert safe_youtube_visibility() == "private"
    assert safe_youtube_visibility("public") == "private"

    monkeypatch.setenv("YOUTUBE_ALLOW_PUBLIC_AUTO_UPLOAD", "true")
    assert safe_youtube_visibility("public") == "public"


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


def test_user_error_from_logs_detects_missing_ffmpeg_text_filter():
    logs = [
        "[AVFilterGraph] No such filter: 'drawtext'",
        "Error initializing a simple filtergraph",
    ]

    assert "FFmpeg backend" in (user_error_from_logs(logs) or "")


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


def test_build_clipper_command_includes_five_minute_highlight_mode():
    request = ClipJobRequest(
        source_file="/tmp/source.mp4",
        clip_mode="highlight_5m",
        compilation_target_seconds=300,
    )

    command = build_clipper_command(request)

    assert command[command.index("--clip-mode") + 1] == "highlight_5m"
    assert command[command.index("--compilation-target") + 1] == "300.0"


def test_build_clipper_command_enables_enhanced_edit_by_default():
    command = build_clipper_command(
        ClipJobRequest(source_file="/tmp/source.mp4", require_creative_commons=False)
    )

    assert "--no-enhanced-edit" not in command
    assert "--keep-running-text" not in command


def test_build_clipper_command_caps_short_render_at_one_minute():
    command = build_clipper_command(
        ClipJobRequest(
            source_file="/tmp/source.mp4",
            min_duration=35,
            max_duration=180,
        )
    )

    assert command[command.index("--max") + 1] == "60.0"


def test_build_clipper_command_can_disable_enhanced_edit():
    command = build_clipper_command(
        ClipJobRequest(
            source_file="/tmp/source.mp4",
            require_creative_commons=False,
            enhanced_edit=False,
        )
    )

    assert "--no-enhanced-edit" in command


def test_build_clipper_command_can_keep_source_running_text():
    command = build_clipper_command(
        ClipJobRequest(
            source_file="/tmp/source.mp4",
            require_creative_commons=False,
            remove_running_text=False,
        )
    )

    assert "--keep-running-text" in command


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


def test_delete_job_allows_queued_job_that_is_not_running(monkeypatch, tmp_path):
    import api

    queued = ClipJob(
        id="queued-job",
        status="queued",
        request=ClipJobRequest(url="https://youtu.be/queued"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )

    monkeypatch.setattr(api, "OUTPUTS_DIR", tmp_path / "outputs")
    monkeypatch.setattr(api, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(api, "JOBS_PATH", tmp_path / "jobs.json")
    monkeypatch.setattr(api, "jobs", {queued.id: queued})
    monkeypatch.setattr(api, "job_processes", {})
    monkeypatch.setattr(api, "job_secrets", {queued.id: "secret"})
    monkeypatch.setattr(api, "cancelled_job_ids", set())

    result = api.delete_job(queued.id)

    assert result["status"] == "ok"
    assert result["removed_jobs"] == 1
    assert queued.id not in api.jobs
    assert queued.id not in api.job_secrets


def test_youtube_cdp_start_needed_detects_remote_debugging_error():
    assert youtube_cdp_start_needed(
        "Chrome remote debugging belum aktif. Jalur utama upload memakai Playwright storage-state"
    )
    assert youtube_cdp_start_needed("connect_over_cdp failed: ECONNREFUSED")
