from datetime import datetime, timedelta, timezone
from pathlib import Path

from api import (
    AutoViralRequest,
    ClipFile,
    ClipJob,
    ClipJobRequest,
    MAX_AUTO_ANALYSIS_SECONDS,
    MAX_REQUESTED_CLIPS,
    ViralVideoSearchRequest,
    _models_from_payload,
    auto_viral_candidate_score,
    best_matching_niche,
    build_clipper_command,
    choose_auto_analyze_seconds,
    default_viral_video_search_queries,
    fresh_conversation_source_profile,
    indonesian_language_score,
    is_creative_commons_info,
    is_fresh_viral_upload,
    list_source_usage_log,
    max_clips_for_duration,
    niche_relevance_score,
    niche_candidate_rejection_reason,
    normalize_job_request,
    normalize_youtube_video_url,
    parse_clipper_progress,
    processed_job_source_urls,
    search_viral_video_sources,
    search_youtube_data_api_viral_sources,
    safe_youtube_visibility,
    source_rights_risk_reasons,
    source_history_for_url,
    unresolved_codex_ideas,
    youtube_cdp_start_needed,
    youtube_data_api_search_queries,
    youtube_upload_staging_filter,
    user_error_from_logs,
    viral_source_discovery_rejection_reason,
    viral_source_rejection_reason,
    viral_search_filter_rejection_reason,
    youtube_upload_clean_metadata_args,
    youtube_max_upload_bytes,
    youtube_published_after,
)


def test_parse_clipper_progress_maps_machine_milestone_to_job_state():
    assert parse_clipper_progress(
        "FENDY_CLIPPER_PROGRESS:73|render|Merender klip pendek 1 dari 3"
    ) == {
        "progress_percent": 73,
        "progress_stage": "render",
        "progress_detail": "Merender klip pendek 1 dari 3",
        "progress_step": 4,
        "progress_total_steps": 5,
    }


def test_parse_clipper_progress_rejects_regular_human_log():
    assert parse_clipper_progress("Exporting vertical short clips...") is None


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


def test_upload_staging_keeps_story_resume_landscape():
    value = youtube_upload_staging_filter(Path("resume_cerita_10menit_inti-cerita.mp4"))

    assert "scale=1280:720" in value
    assert "pad=1280:720" in value


def test_upload_staging_keeps_long_animate_landscape():
    value = youtube_upload_staging_filter(Path("long_animate_langkah-kecil.mp4"))

    assert "scale=1280:720" in value
    assert "pad=1280:720" in value


def test_upload_staging_keeps_short_vertical():
    value = youtube_upload_staging_filter(Path("clip_01_pilihan.mp4"))

    assert "scale=720:1280" in value
    assert "pad=720:1280" in value


def test_youtube_upload_size_defaults_to_quality_safe_256_mb(monkeypatch):
    monkeypatch.delenv("YOUTUBE_MAX_UPLOAD_MB", raising=False)
    monkeypatch.delenv("YOUTUBE_CDP_MAX_UPLOAD_MB", raising=False)

    assert youtube_max_upload_bytes() == 256 * 1024 * 1024


def test_max_clips_at_least_one():
    assert max_clips_for_duration(40, 35) == 1


def test_normalize_clamps_target_to_budget(monkeypatch):
    import api

    monkeypatch.setattr(api, "probe_media_duration", lambda path: 120.0)
    req = ClipJobRequest(source_file="fake.mp4", top=20, min_duration=35, max_duration=180)
    out = normalize_job_request(req)
    assert out.top == 2  # clamped from 20 to budget cap
    assert out.max_duration == 180


def test_short_defaults_allow_up_to_three_minutes():
    request = ClipJobRequest(source_file="fake.mp4")

    assert request.min_duration == 25
    assert request.max_duration == 180
    assert request.model == "Systran/faster-whisper-medium"
    assert request.crop_mode == "person"
    assert request.caption_position == "bottom"
    assert request.ai_base_url.endswith(":11434/v1")
    assert request.ai_model == "llama3.2-id:latest"
    assert request.required_hashtags == [
        "viralindonesia",
        "trendingindonesia",
        "kontenpilihan",
    ]


def test_story_resume_accepts_ten_minute_target():
    request = ClipJobRequest(
        source_file="fake.mp4",
        clip_mode="highlight_5m",
        compilation_target_seconds=600,
    )

    assert request.compilation_target_seconds == 600


def test_long_animate_normalization_and_command_use_script_file(tmp_path):
    script = (
        "Perubahan yang bertahan lama dimulai dari kebiasaan kecil. "
        "Kita menyusun satu tindakan sederhana, mengulanginya, lalu mengevaluasi hasilnya "
        "agar kemajuan tetap terasa nyata setiap hari."
    )
    request = normalize_job_request(
        ClipJobRequest(
            clip_mode="long_animate",
            script_text=script,
            confirm_long_animate_rights=True,
        )
    )
    script_path = tmp_path / "input_script.txt"
    script_path.write_text(script, encoding="utf-8")

    command = build_clipper_command(request, tmp_path, script_path)

    assert request.top == 1
    assert request.analyze_seconds is None
    assert request.burn_subtitles is True
    assert request.require_creative_commons is False
    assert command[command.index("--clip-mode") + 1] == "long_animate"
    assert command[command.index("--script-file") + 1] == str(script_path)


def test_original_rebuild_normalization_keeps_source_and_enforces_safe_flags(monkeypatch, tmp_path):
    import api

    monkeypatch.setattr(api, "fetch_video_duration", lambda _url: 600.0)
    request = normalize_job_request(
        ClipJobRequest(
            url="https://www.youtube.com/watch?v=safe-source",
            clip_mode="original_rebuild",
            confirm_source_rights=True,
            confirm_long_animate_rights=True,
            creator_perspective="Saya menilai perubahan kecil harus dibuktikan dengan evaluasi yang konsisten setiap minggu.",
            source_rights_evidence="CC source URL checked 2026-08-30",
            provider_rights_evidence="Provider commercial terms checked 2026-08-30",
            ai_enabled=True,
            ai_base_url="http://localhost:11434/v1",
            ai_model="test-model",
        )
    )

    command = build_clipper_command(request, tmp_path)

    assert request.top == 1
    assert request.burn_subtitles is True
    assert request.enhanced_edit is True
    assert command[command.index("--clip-mode") + 1] == "original_rebuild"
    assert command[1] == "clipper.py"
    assert request.url in command
    assert "--script-file" not in command
    assert "--require-creative-commons" in command
    assert "--confirm-source-rights" in command
    assert "--confirm-provider-rights" in command
    assert command[command.index("--creator-perspective") + 1] == request.creator_perspective
    assert command[command.index("--source-rights-evidence") + 1] == request.source_rights_evidence
    assert command[command.index("--provider-rights-evidence") + 1] == request.provider_rights_evidence


def test_automatic_topic_rebuild_needs_no_manual_compliance_form(monkeypatch, tmp_path):
    import api

    monkeypatch.setattr(api, "fetch_video_duration", lambda _url: 600.0)
    request = normalize_job_request(
        ClipJobRequest(
            url="https://www.youtube.com/watch?v=research-source",
            clip_mode="original_rebuild",
            automatic_topic_rebuild=True,
            auto_upload_youtube=True,
            ai_enabled=True,
            ai_base_url="http://localhost:11434/v1",
            ai_model="test-model",
        )
    )

    command = build_clipper_command(request, tmp_path)

    assert request.creator_perspective == ""
    assert request.confirm_source_rights is False
    assert request.confirm_long_animate_rights is False
    assert request.auto_upload_youtube is False
    assert "--automatic-topic-rebuild" in command
    assert "--confirm-source-rights" not in command
    assert "--confirm-provider-rights" not in command


def test_create_automatic_topic_rebuild_starts_without_manual_form(monkeypatch):
    import api

    class FakeThread:
        def __init__(self, *args, **kwargs):
            self.started = False

        def start(self):
            self.started = True

    monkeypatch.setattr(api, "jobs", {})
    monkeypatch.setattr(api, "processed_source_history", set())
    monkeypatch.setattr(api, "source_usage_history", {})
    monkeypatch.setattr(api, "fetch_video_duration", lambda _url: 600.0)
    monkeypatch.setattr(api.threading, "Thread", FakeThread)

    job = api.create_job(
        ClipJobRequest(
            url="https://www.youtube.com/watch?v=research-source",
            clip_mode="original_rebuild",
            automatic_topic_rebuild=True,
            allow_reprocess_source=True,
            auto_upload_youtube=True,
            ai_enabled=True,
            ai_base_url="http://localhost:11434/v1",
            ai_model="test-model",
        )
    )

    assert job.status == "queued"
    assert job.request.automatic_topic_rebuild is True
    assert job.request.confirm_source_rights is False
    assert job.request.confirm_long_animate_rights is False
    assert job.request.auto_upload_youtube is False


def test_create_original_rebuild_requires_human_perspective_before_source_access():
    import api
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException, match="perspektif|sudut pandang"):
        api.create_job(
            ClipJobRequest(
                source_file="not-opened.mp4",
                clip_mode="original_rebuild",
                confirm_source_rights=True,
                confirm_long_animate_rights=True,
                source_rights_evidence="Written permission checked today",
                provider_rights_evidence="Commercial provider terms checked today",
            )
        )


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
    assert ViralVideoSearchRequest().max_metadata_checks == 24
    assert ViralVideoSearchRequest(max_age_days=180).max_age_days == 180
    with pytest.raises(ValidationError):
        ViralVideoSearchRequest(max_age_days=366)


def test_new_jobs_default_to_clean_detail_auto_fyp_visuals():
    request = ClipJobRequest(source_file="/tmp/source.mp4")

    assert request.visual_mode == "auto_fyp"
    assert request.background_mode == "keep"
    assert AutoViralRequest().visual_mode == "auto_fyp"
    assert AutoViralRequest().background_mode == "keep"
    assert AutoViralRequest().niche == "islamic_practical_life"
    assert ViralVideoSearchRequest().niche == "islamic_practical_life"


def test_practical_life_niche_owns_default_search_positions():
    request = ViralVideoSearchRequest()

    assert request.queries[0] == "tanya jawab islam masalah orang tua"
    assert request.queries[2].startswith("kajian rumah tangga islami")
    assert request.queries.index("podcast horor indonesia") >= 12


def test_legacy_visual_modes_are_migrated_to_auto_fyp():
    request = ClipJobRequest(source_file="/tmp/source.mp4", visual_mode="retro_tv")
    auto_request = AutoViralRequest(visual_mode="retro_tv")

    assert request.visual_mode == "auto_fyp"
    assert auto_request.visual_mode == "auto_fyp"
    command = build_clipper_command(request)
    assert command[command.index("--visual-mode") + 1] == "auto_fyp"


def test_configured_viral_queries_are_extended_not_replaced(monkeypatch):
    monkeypatch.setenv("VIRAL_CC_SEARCH_QUERIES", "topik khusus|podcast indonesia terbaru")

    queries = default_viral_video_search_queries()

    assert queries[0] == "topik khusus"
    assert queries.count("podcast indonesia terbaru") == 1
    assert len(queries) >= 120
    assert queries.index("misteri dalam islam") < 10
    assert queries.index("podcast horor indonesia") < 12


def test_selected_evergreen_niche_owns_the_first_search_positions():
    mental = ViralVideoSearchRequest(niche="islamic_mental_health")
    finance = ViralVideoSearchRequest(niche="halal_wealth")

    assert mental.video_count == 3
    assert mental.queries[0] == "kesehatan mental islam overthinking"
    assert mental.queries.index("podcast horor indonesia") >= 12
    assert finance.queries[0] == "cara mencari rezeki halal berkah"
    assert finance.queries.index("podcast horor indonesia") >= 12


def test_current_viral_niche_uses_indonesian_freshness_queries():
    request = ViralVideoSearchRequest(niche="islamic_current_viral")

    assert request.queries[0] == "isu muslim indonesia viral hari ini"
    assert str(datetime.now(timezone.utc).year) in request.queries[1]
    assert "terbaru" in request.queries[1]


def test_search_filter_defaults_match_broad_cc_reference_layout():
    request = ViralVideoSearchRequest(niche="islamic_current_viral")

    assert request.duration_filter == "over_20"
    assert request.upload_date_filter == "this_week"
    assert request.definition_filter == "hd"
    assert request.sort_order == "popularity"
    assert request.max_age_days == 7


def test_search_filter_revalidates_duration_date_and_hd_metadata():
    request = ViralVideoSearchRequest(
        niche="islamic_history",
        duration_filter="over_20",
        upload_date_filter="this_year",
        definition_filter="hd",
    )
    valid = {
        "duration": 1800,
        "upload_date": datetime.now(timezone.utc).strftime("%Y%m%d"),
        "definition": "hd",
    }

    assert viral_search_filter_rejection_reason(valid, request) == ""
    assert "20 menit" in viral_search_filter_rejection_reason(
        {**valid, "duration": 900}, request
    )
    assert "HD" in viral_search_filter_rejection_reason(
        {**valid, "definition": "sd"}, request
    )


def test_niche_relevance_rewards_master_context_terms_not_generic_islam_label():
    aligned = {
        "title": "Cara Mengatasi Overthinking dan Cemas dengan Tawakal",
        "description": "Psikologi Islam untuk ketenangan hati dan emosi.",
    }
    generic = {
        "title": "Kajian Islam Terbaru",
        "description": "Ceramah umum untuk umat.",
    }

    assert niche_relevance_score(aligned, "islamic_mental_health") >= 50
    assert niche_relevance_score(generic, "islamic_mental_health") == 0


def test_auto_niche_selects_the_strongest_supported_theme():
    source = {
        "title": "Cara Mengatasi Overthinking dan Cemas dengan Tawakal",
        "description": "Psikologi Islam untuk ketenangan hati dan emosi.",
    }

    niche, score = best_matching_niche(source)

    assert niche == "islamic_mental_health"
    assert score >= 50
    assert niche_relevance_score(source, "auto") == score


def test_indonesian_niche_gate_rejects_english_zero_match_even_with_high_views():
    english = {
        "title": "Muslims Confront University Students You Need To See This",
        "description": "A popular discussion with millions of views.",
        "view_count": 10_000_000,
    }
    indonesian = {
        "title": "Kisah Nabi yang Jarang Diketahui",
        "description": "Kajian sejarah Islam untuk memahami hikmah para sahabat.",
        "default_audio_language": "id",
        "view_count": 5_000,
    }

    assert indonesian_language_score(english) == 0
    assert niche_candidate_rejection_reason(english, "islamic_history")
    assert indonesian_language_score(indonesian) == 100
    assert niche_candidate_rejection_reason(indonesian, "islamic_history") == ""


def test_selected_sources_limit_campaign_target_and_disable_auto_upload_when_requested():
    request = AutoViralRequest(
        niche="fiqih_harian",
        video_count=5,
        source_urls=[
            "https://youtu.be/abcDEF12345",
            "https://youtube.com/watch?v=xyzDEF12345",
        ],
        auto_upload_youtube=False,
    )

    assert request.video_count == 2
    assert request.auto_upload_youtube is False
    assert request.queries[0] == "kesalahan shalat yang sering tidak disadari"


def test_search_returns_ranked_top_three_from_larger_candidate_pool(monkeypatch):
    import api

    candidates = [
        {
            "url": f"https://youtube.com/watch?v=demoRank{i:02}",
            "title": f"Kandidat {i}",
            "score": float(i),
        }
        for i in range(1, 10)
    ]
    monkeypatch.delenv("YOUTUBE_DATA_API_KEY", raising=False)
    monkeypatch.setenv("VIRAL_CC_FAST_API_ONLY", "false")
    monkeypatch.setattr(api, "processed_job_source_urls", lambda: set())
    monkeypatch.setattr(
        api,
        "search_auto_viral_sources",
        lambda *_args, **_kwargs: list(candidates),
    )

    selected = search_viral_video_sources(
        ViralVideoSearchRequest(niche="islamic_history", video_count=3)
    )

    assert [item["score"] for item in selected] == [9.0, 8.0, 7.0]
    assert [item["rank"] for item in selected] == [1, 2, 3]


def test_fast_google_api_search_does_not_enter_slow_ytdlp_fallback(monkeypatch):
    import api

    monkeypatch.setenv("YOUTUBE_DATA_API_KEY", "configured-test-key")
    monkeypatch.setenv("VIRAL_CC_FAST_API_ONLY", "true")
    monkeypatch.setattr(api, "processed_job_source_urls", lambda: set())
    monkeypatch.setattr(
        api,
        "search_youtube_data_api_viral_sources",
        lambda *_args, **_kwargs: [
            {
                "url": "https://youtube.com/watch?v=fastApi12345",
                "title": "Kajian Indonesia Terbaru",
                "score": 90.0,
                "viral_score": 80.0,
                "search_provider": "youtube_data_api",
            }
        ],
    )

    def fail_slow_fallback(*_args, **_kwargs):
        raise AssertionError("yt-dlp fallback must not run in fast API mode")

    monkeypatch.setattr(api, "search_auto_viral_sources", fail_slow_fallback)

    selected = search_viral_video_sources(
        ViralVideoSearchRequest(niche="islamic_current_viral", video_count=3)
    )

    assert len(selected) == 1
    assert selected[0]["search_provider"] == "youtube_data_api"
    assert selected[0]["search_elapsed_ms"] >= 0


def test_fast_google_api_combines_niche_terms_into_one_quota_call(monkeypatch):
    monkeypatch.setenv("VIRAL_CC_FAST_API_ONLY", "true")
    monkeypatch.setenv("VIRAL_CC_MAX_API_QUERIES", "4")
    request = AutoViralRequest(niche="islamic_current_viral")

    queries = youtube_data_api_search_queries(request)

    assert len(queries) == 1
    assert "|" in queries[0]
    assert "isu muslim indonesia viral hari ini" in queries[0]


def test_quota_exceeded_uses_small_cc_verified_fallback(monkeypatch):
    import api

    monkeypatch.setenv("YOUTUBE_DATA_API_KEY", "configured-test-key")
    monkeypatch.setenv("VIRAL_CC_FAST_API_ONLY", "true")
    monkeypatch.setenv("VIRAL_CC_QUOTA_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("VIRAL_CC_QUOTA_FALLBACK_METADATA_CHECKS", "8")
    monkeypatch.setattr(api, "processed_job_source_urls", lambda: set())
    monkeypatch.setattr(
        api,
        "search_youtube_data_api_viral_sources",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("HTTP 429 quotaExceeded rate_limit")
        ),
    )
    observed: dict[str, object] = {}

    def fallback(request, *_args, **kwargs):
        observed["query_count"] = len(request.queries)
        observed["metadata_checks"] = kwargs["max_metadata_checks"]
        return []

    monkeypatch.setattr(api, "search_auto_viral_sources", fallback)

    selected = search_viral_video_sources(
        ViralVideoSearchRequest(niche="islamic_current_viral", video_count=3)
    )

    assert selected == []
    assert observed == {"query_count": 2, "metadata_checks": 8}


def test_api_search_adapts_soft_filters_but_keeps_cc_language_and_niche(monkeypatch):
    import api

    monkeypatch.setenv("YOUTUBE_DATA_API_KEY", "configured-test-key")
    monkeypatch.setenv("VIRAL_CC_FAST_API_ONLY", "true")
    monkeypatch.setenv("VIRAL_CC_ADAPTIVE_FILTERS", "true")

    def fake_api(path, _params):
        if path == "search":
            return {"items": [{"id": {"videoId": "adaptive123"}}]}
        return {
            "items": [
                {
                    "id": "adaptive123",
                    "snippet": {
                        "title": "Kajian Islam Viral Indonesia Terbaru",
                        "description": "Nasihat untuk umat Indonesia yang sedang ramai.",
                        "publishedAt": datetime.now(timezone.utc).isoformat(),
                        "defaultAudioLanguage": "id",
                        "liveBroadcastContent": "none",
                    },
                    "statistics": {"viewCount": "500", "likeCount": "25"},
                    "contentDetails": {"duration": "PT10M", "definition": "sd"},
                    "status": {"license": "creativeCommon"},
                }
            ]
        }

    monkeypatch.setattr(api, "youtube_data_api_get", fake_api)
    request = AutoViralRequest(
        niche="islamic_current_viral",
        video_count=3,
        duration_filter="over_20",
        definition_filter="hd",
        min_views=1000,
    )

    selected = search_youtube_data_api_viral_sources(request, "missing-run", stop_after=3)

    assert len(selected) == 1
    assert selected[0]["rights_verified"] is False
    assert selected[0]["license_metadata_verified"] is True
    assert selected[0]["source_preflight"] == "passed"
    assert selected[0]["filter_match"] == "adaptive"
    assert len(selected[0]["relaxed_filters"]) == 3


def test_api_search_skips_rights_risk_and_continues_to_safe_replacement(monkeypatch):
    import api

    monkeypatch.setenv("YOUTUBE_DATA_API_KEY", "configured-test-key")
    monkeypatch.setenv("VIRAL_CC_ADAPTIVE_FILTERS", "true")
    published_at = datetime.now(timezone.utc).isoformat()

    def video_item(video_id, title, channel_title):
        return {
            "id": video_id,
            "snippet": {
                "title": title,
                "channelTitle": channel_title,
                "description": "Kajian Islam Indonesia viral terbaru untuk umat dan kehidupan.",
                "publishedAt": published_at,
                "defaultAudioLanguage": "id",
                "liveBroadcastContent": "none",
            },
            "statistics": {"viewCount": "5000", "likeCount": "250"},
            "contentDetails": {"duration": "PT10M", "definition": "hd"},
            "status": {"license": "creativeCommon", "privacyStatus": "public"},
        }

    def fake_api(path, _params):
        if path == "search":
            return {
                "items": [
                    {"id": {"videoId": "risky-source"}},
                    {"id": {"videoId": "safe-source"}},
                ]
            }
        return {
            "items": [
                video_item(
                    "risky-source",
                    "Full Episode Kajian Islam Viral Indonesia",
                    "Contoh TV Reupload",
                ),
                video_item(
                    "safe-source",
                    "Kajian Islam Viral Indonesia Terbaru",
                    "Kajian Mandiri",
                ),
            ]
        }

    monkeypatch.setattr(api, "youtube_data_api_get", fake_api)
    request = AutoViralRequest(
        niche="islamic_current_viral",
        video_count=1,
        min_views=1000,
    )

    selected = search_youtube_data_api_viral_sources(request, "missing-run", stop_after=1)

    assert [item["url"] for item in selected] == [
        "https://www.youtube.com/watch?v=safe-source"
    ]
    assert selected[0]["source_preflight"] == "passed"
    assert selected[0]["content_id_risk"] == "review"
    assert selected[0]["content_id_risk_reasons"] == []


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


def test_youtube_source_normalizer_accepts_mobile_live_and_query_variants():
    expected = "https://www.youtube.com/watch?v=abcDEF12345"

    assert normalize_youtube_video_url(
        "https://m.youtube.com/watch?si=share123&v=abcDEF12345&t=30"
    ) == expected
    assert normalize_youtube_video_url("https://www.youtube.com/live/abcDEF12345") == expected
    assert normalize_youtube_video_url("https://youtu.be/abcDEF12345?si=share123") == expected


def test_source_history_reports_short_and_highlight_usage(monkeypatch):
    import api

    source = "https://www.youtube.com/watch?v=abcDEF12345"
    short_job = ClipJob(
        id="short-job",
        status="completed",
        request=ClipJobRequest(url=source, clip_mode="short"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[ClipFile(name="clip_01.mp4", url="/outputs/demo/clip_01.mp4", size_bytes=10)],
    )
    highlight_job = ClipJob(
        id="highlight-job",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/abcDEF12345", clip_mode="highlight_5m"),
        created_at="2026-01-02T00:00:00+00:00",
        updated_at="2026-01-02T00:00:00+00:00",
        clips=[
            ClipFile(
                name="resume_cerita_5menit_inti.mp4",
                url="/outputs/demo/resume_cerita_5menit_inti.mp4",
                size_bytes=10,
            )
        ],
    )
    monkeypatch.setattr(api, "jobs", {short_job.id: short_job, highlight_job.id: highlight_job})
    monkeypatch.setattr(api, "processed_source_history", {source})
    monkeypatch.setattr(api, "source_usage_history", {})

    result = source_history_for_url("https://m.youtube.com/watch?v=abcDEF12345&t=20")

    assert result.found
    assert result.archived
    assert result.has_short_clips
    assert result.has_highlight_5m
    assert result.attempted_modes == ["highlight_5m", "short"]
    assert [match.job_id for match in result.matches] == ["highlight-job", "short-job"]


def test_create_job_requires_explicit_approval_for_processed_source(monkeypatch):
    import api
    import pytest
    from fastapi import HTTPException

    source = "https://www.youtube.com/watch?v=abcDEF12345"
    completed = ClipJob(
        id="completed-source",
        status="completed",
        request=ClipJobRequest(url=source),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    monkeypatch.setattr(api, "jobs", {completed.id: completed})
    monkeypatch.setattr(api, "processed_source_history", {source})
    monkeypatch.setattr(api, "source_usage_history", {})

    with pytest.raises(HTTPException) as error:
        api.create_job(ClipJobRequest(url="https://youtu.be/abcDEF12345"))

    assert error.value.status_code == 409
    assert "pernah diproses" in str(error.value.detail)


def test_source_usage_log_only_lists_success_records(monkeypatch):
    import api

    source = "https://www.youtube.com/watch?v=abcDEF12345"
    monkeypatch.setattr(api, "jobs", {})
    monkeypatch.setattr(
        api,
        "source_usage_history",
        {
            source: {
                "modes": ["short", "highlight_5m"],
                "events": [
                    {
                        "job_id": "job-success-short",
                        "source_url": source,
                        "source_title": "Ceramah contoh",
                        "source_uploader": "Channel Contoh",
                        "clip_mode": "short",
                        "processed_at": "2026-08-02T10:00:00+00:00",
                        "clip_count": 3,
                        "output_names": ["clip_01.mp4", "clip_02.mp4", "clip_03.mp4"],
                        "processing_duration_seconds": 125.5,
                        "compilation_target_seconds": None,
                        "auto_upload_youtube": True,
                    },
                    {
                        "job_id": "job-success-highlight",
                        "source_url": source,
                        "source_title": "Ceramah contoh",
                        "source_uploader": "Channel Contoh",
                        "clip_mode": "highlight_5m",
                        "processed_at": "2026-08-03T10:00:00+00:00",
                        "clip_count": 1,
                        "output_names": ["resume_cerita_5menit_inti.mp4"],
                        "processing_duration_seconds": 245.0,
                        "compilation_target_seconds": 300,
                        "auto_upload_youtube": False,
                    },
                ],
            }
        },
    )

    result = list_source_usage_log()

    assert result.total == 2
    assert result.unique_sources == 1
    assert [item.job_id for item in result.items] == [
        "job-success-highlight",
        "job-success-short",
    ]
    assert result.items[0].output_names == ["resume_cerita_5menit_inti.mp4"]


def test_source_usage_log_backfills_completed_jobs_but_not_failed_jobs(monkeypatch, tmp_path):
    import api

    completed = ClipJob(
        id="completed-log-job",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/abcDEF12345", clip_mode="short"),
        created_at="2026-08-01T10:00:00+00:00",
        updated_at="2026-08-01T10:05:00+00:00",
        finished_at="2026-08-01T10:05:00+00:00",
        duration_seconds=300,
        source_title="Sumber berhasil",
        clips=[ClipFile(name="clip_01.mp4", url="/outputs/demo/clip_01.mp4", size_bytes=10)],
    )
    failed = ClipJob(
        id="failed-log-job",
        status="failed",
        request=ClipJobRequest(url="https://youtu.be/failed12345", clip_mode="highlight_5m"),
        created_at="2026-08-02T10:00:00+00:00",
        updated_at="2026-08-02T10:01:00+00:00",
        finished_at="2026-08-02T10:01:00+00:00",
        error="render failed",
    )
    monkeypatch.setattr(api, "jobs", {completed.id: completed, failed.id: failed})
    monkeypatch.setattr(api, "source_usage_history", {})
    monkeypatch.setattr(api, "SOURCE_USAGE_HISTORY_PATH", tmp_path / "source_usage_history.json")

    result = list_source_usage_log()

    assert result.total == 1
    assert result.items[0].job_id == completed.id
    assert result.items[0].processed_at == completed.finished_at
    assert all(item.job_id != failed.id for item in result.items)


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


def test_fresh_conversation_profile_rewards_recent_multi_angle_source():
    today = datetime.now(timezone.utc)
    conversation = {
        "upload_date": (today - timedelta(days=2)).strftime("%Y%m%d"),
        "title": "Podcast: Pengalaman dan Jawaban untuk Masalah Keluarga",
        "description": "Obrolan panjang membahas beberapa pengalaman nyata.",
        "duration": 3200,
        "view_count": 120_000,
    }
    generic = {
        **conversation,
        "title": "Renungan Harian",
        "description": "Satu materi singkat.",
    }

    profile = fresh_conversation_source_profile(conversation)

    assert profile["qualified"] is True
    assert profile["requires_distinct_clip_angles"] is True
    assert profile["rights_or_monetization_guarantee"] is False
    assert "podcast" in profile["matched_markers"]
    assert profile["score"] > fresh_conversation_source_profile(generic)["score"]


def test_current_viral_defaults_to_seven_day_window_but_respects_explicit_filter():
    automatic = AutoViralRequest(niche="islamic_current_viral")
    explicit_year = AutoViralRequest(
        niche="islamic_current_viral",
        upload_date_filter="this_year",
    )
    evergreen = AutoViralRequest(niche="islamic_practical_life")

    assert automatic.upload_date_filter == "this_week"
    assert automatic.max_age_days == 7
    assert explicit_year.upload_date_filter == "this_year"
    assert explicit_year.max_age_days == 365
    assert evergreen.max_age_days == 365


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


def test_source_rights_guard_rejects_claimed_tv_show_reupload_even_when_cc():
    source = {
        "license": "Creative Commons Attribution license",
        "availability": "public",
        "title": "Sintya Marisca - Islam Itu Indah 7 Feb 2k20",
        "uploader": "Sintya Marisca Support",
    }

    reasons = source_rights_risk_reasons(source)

    assert any("fan/support/reupload" in reason for reason in reasons)
    assert any("Content ID" in reason for reason in reasons)
    assert "uploader" in (viral_source_rejection_reason(source) or "")


def test_discovery_rejects_rights_risk_before_source_can_be_selected():
    source = {
        "license": "Creative Commons Attribution license",
        "availability": "public",
        "title": "Full Episode Islam Itu Indah",
        "uploader": "Contoh TV Reupload",
    }

    discovery_reason = viral_source_discovery_rejection_reason(source)

    assert discovery_reason
    assert "uploader" in discovery_reason
    assert viral_source_rejection_reason(source) == discovery_reason


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


def test_user_error_from_logs_reassembles_rich_wrapped_actionable_message():
    logs = [
        "Fetching metadata...",
        "USER_ERROR: Sumber ditolak sebelum download karena berisiko tinggi terkena",
        "Content ID: sumber terindikasi milik broadcaster/media/studio.",
        "Pilih Original Rebuild lalu isi perspektif dan referensi izin tertulis.",
    ]

    message = user_error_from_logs(logs) or ""

    assert "Content ID" in message
    assert "Original Rebuild" in message


def test_user_error_from_logs_detects_network_error():
    logs = ["ERROR: [download] Got error: [Errno 101] Network is unreachable"]

    assert "Upload Video" in (user_error_from_logs(logs) or "")


def test_user_error_from_logs_does_not_mislabel_image_connection_as_youtube():
    logs = [
        "[long_animate] INFO: Generating images and running vision QA",
        "Error: Generate gambar AI scene 1 gagal setelah 3 percobaan: <urlopen error [Errno 111] Connection refused>",
    ]

    message = user_error_from_logs(logs) or ""
    assert "Generator gambar lokal" in message
    assert "YouTube" not in message


def test_user_error_from_logs_detects_missing_ffmpeg_text_filter():
    logs = [
        "[AVFilterGraph] No such filter: 'drawtext'",
        "Error initializing a simple filtergraph",
    ]

    assert "FFmpeg backend" in (user_error_from_logs(logs) or "")


def test_user_error_from_logs_explains_incomplete_audio_download():
    logs = [
        "[out#0/wav] Output file does not contain any stream",
        "Error opening output files: Invalid argument",
    ]

    message = user_error_from_logs(logs) or ""
    assert "Track audio sumber belum terunduh lengkap" in message
    assert "ulangi job" in message


def test_create_job_accepts_another_job_while_one_is_active(monkeypatch):
    import api

    active = ClipJob(
        id="active-job",
        status="running",
        request=ClipJobRequest(url="https://youtu.be/active"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    monkeypatch.setattr(api, "jobs", {active.id: active})
    monkeypatch.setattr(api, "processed_source_history", set())
    monkeypatch.setattr(api, "source_usage_history", {})

    started_threads = []

    class FakeThread:
        def __init__(self, *, target, args, daemon):
            started_threads.append((target, args, daemon))

        def start(self):
            return None

    monkeypatch.setattr(api.threading, "Thread", FakeThread)

    created = api.create_job(ClipJobRequest(url="https://youtu.be/new"))

    assert created.status == "queued"
    assert created.id in api.jobs
    assert active.id in api.jobs
    assert started_threads == [(api.run_job, (created.id,), True)]


def test_build_clipper_command_can_isolate_parallel_job_output(tmp_path):
    request = ClipJobRequest(url="https://youtu.be/source")
    output_root = tmp_path / "job-123"

    command = build_clipper_command(request, output_root)

    output_index = command.index("--output")
    assert command[output_index + 1] == str(output_root)


def test_build_clipper_command_forces_creative_commons_for_url_jobs():
    request = ClipJobRequest(
        url="https://youtu.be/source",
        require_creative_commons=False,
        confirm_source_rights=True,
    )

    command = build_clipper_command(request)

    assert "--require-creative-commons" in command
    assert "--confirm-source-rights" in command


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
    assert command[command.index("--visual-mode") + 1] == "auto_fyp"
    assert command[command.index("--background-mode") + 1] == "keep"


def test_build_clipper_command_enables_enhanced_edit_by_default():
    command = build_clipper_command(
        ClipJobRequest(source_file="/tmp/source.mp4", require_creative_commons=False)
    )

    assert "--no-enhanced-edit" not in command
    assert "--keep-running-text" not in command
    assert "--remove-running-text" not in command


def test_build_clipper_command_caps_short_render_at_growth_window():
    command = build_clipper_command(
        ClipJobRequest(
            source_file="/tmp/source.mp4",
            min_duration=35,
            max_duration=180,
        )
    )

    assert command[command.index("--max") + 1] == "180.0"


def test_build_clipper_command_can_disable_enhanced_edit():
    command = build_clipper_command(
        ClipJobRequest(
            source_file="/tmp/source.mp4",
            require_creative_commons=False,
            enhanced_edit=False,
        )
    )

    assert "--no-enhanced-edit" in command


def test_build_clipper_command_preserves_source_running_text_by_default():
    command = build_clipper_command(
        ClipJobRequest(
            source_file="/tmp/source.mp4",
            require_creative_commons=False,
            remove_running_text=False,
        )
    )

    assert "--keep-running-text" not in command
    assert "--remove-running-text" not in command


def test_build_clipper_command_enables_local_watermark_detection_by_default():
    command = build_clipper_command(
        ClipJobRequest(source_file="/tmp/source.mp4", require_creative_commons=False)
    )

    assert "--auto-blur-watermarks" in command


def test_build_clipper_command_can_disable_local_watermark_detection():
    command = build_clipper_command(
        ClipJobRequest(
            source_file="/tmp/source.mp4",
            require_creative_commons=False,
            auto_blur_watermarks=False,
        )
    )

    assert "--auto-blur-watermarks" not in command


def test_build_clipper_command_can_explicitly_remove_source_running_text():
    command = build_clipper_command(
        ClipJobRequest(
            source_file="/tmp/source.mp4",
            require_creative_commons=False,
            remove_running_text=True,
        )
    )

    assert "--remove-running-text" in command


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
