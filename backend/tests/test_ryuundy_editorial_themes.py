"""Requested topics enter cron with their own Long roles and review policy."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
import api
import ryuundy_editorial_themes as themes

TITLES = {
    "legend_folklore": "Cerita rakyat legenda Danau Toba dalam bahasa Indonesia",
    "domestic_politics": "Analisis politik Indonesia kronologi kebijakan pemerintah dan dampak masyarakat",
    "food_healthy_review": "Review makanan sehat Indonesia bahan porsi dan cara masak",
    "food_taste_review": "Review kuliner Indonesia rasa tekstur porsi dan harga makanan",
}


@pytest.mark.parametrize("key", themes.PROFILES)
def test_requested_topic_reaches_search_and_both_formats(key, monkeypatch):
    profile = themes.PROFILES[key]
    monkeypatch.setattr(api, "scheduled_news_hot_due", lambda: False)
    monkeypatch.setattr(api, "scheduled_ryuundy_theme_profile", lambda: (key, profile))
    monkeypatch.setenv("AUTO_VIRAL_SCHEDULE_PAIRED_LONG_ENABLED", "true")
    monkeypatch.setenv("AUTO_VIRAL_SCHEDULE_PAIRED_LONG_COUNT", "1")
    monkeypatch.setenv("AUTO_VIRAL_SCHEDULE_AUTO_UPLOAD_YOUTUBE", "false")
    request = api.scheduled_auto_viral_request()
    assert request.cron_theme_key == key and request.duration_filter == "any"
    assert request.theme_focus in profile["queries"]
    assert set(request.queries) <= set(profile["queries"])
    assert profile["long_role"] in api.auto_viral_format_perspective(request, long_form=True)
    assert profile["short_role"] in api.auto_viral_format_perspective(request, long_form=False)
    source = dict(url="https://www.youtube.com/watch?v=abcdefghijk", title=TITLES[key],
                  duration=1200, view_count=5000, license="Creative Commons Attribution license")
    captured = []
    monkeypatch.setattr(api, "wait_for_no_active_clipping_job", lambda: None)
    monkeypatch.setattr(api, "normalize_job_request", lambda request: request)
    monkeypatch.setattr(api, "queue_auto_viral_clip_job", lambda request:
        captured.append(request) or SimpleNamespace(id="short", request=request))
    short = api.create_auto_viral_clip_job(source, request, scheduled=True)
    short.candidates = [SimpleNamespace(start=10, end=45)]
    api.create_auto_viral_paired_long_job(source, request, short, wait_for_slot=False)
    assert [r.clip_mode for r in captured] == ["short", "highlight_5m"]
    assert captured[-1].cron_long_strategy and captured[-1].scheduled_theme_key == key
    for row in captured:
        assert not {"Islam", "KisahIslami", "KisahNyata"} & set(row.required_hashtags)
    if key == "domestic_politics":
        assert all(r.publication_review_required for r in captured)
        assert not request.auto_upload_youtube and not request.auto_upload_tiktok
        assert not request.auto_publish_paired_long_video


@pytest.mark.parametrize("key", themes.PROFILES)
def test_new_topics_participate_in_rotation(key, monkeypatch):
    for name in ("scheduled_islamic_animation_trial_profile", "scheduled_performance_winner_profile",
                 "scheduled_search_term_winner_profile"):
        monkeypatch.setattr(api, name, lambda: None)
    monkeypatch.setattr(api, "auto_viral_runs", {
        other: SimpleNamespace(trigger="schedule", created_at=datetime.now(timezone.utc).isoformat(),
                               request=SimpleNamespace(cron_theme_key=other))
        for other in api.RYUUNDY_CRON_THEME_PROFILES if other != key
    })
    assert api.scheduled_ryuundy_theme_profile()[0] == key


@pytest.mark.parametrize("key", themes.PROFILES)
def test_source_discovery_rejects_unrelated_theme(key, monkeypatch):
    monkeypatch.setattr(api, "cron_trend_score", lambda *a: (90, []))
    monkeypatch.setattr(api, "indonesian_language_score", lambda *a: 100)
    assert not api.cron_trend_candidate_rejection_reason({"title": TITLES[key]}, theme_key=key)
    assert api.cron_trend_candidate_rejection_reason(
        {"title": "Roblox mabar dan gameplay Indonesia"}, theme_key=key)


def test_political_upload_flags_cannot_bypass_review_after_persisted_reload():
    request = api.AutoViralRequest(cron_theme_key="domestic_politics",
        auto_upload_youtube=True, auto_upload_tiktok=True, auto_publish_paired_long_video=True,
        create_paired_long_video=True, paired_long_video_count=1)
    restored = api.AutoViralRequest.model_validate(request.model_dump())
    assert restored.create_paired_long_video
    assert not restored.auto_upload_youtube and not restored.auto_upload_tiktok
    assert not restored.auto_publish_paired_long_video


def test_mystery_does_not_invent_true_story_attribution():
    assert "KisahNyata" not in api.source_theme_hashtags(
        {"title": "Pengalaman misteri"}, theme_key="mystery_story", long_form=True)


def test_compose_capability_contract_reports_all_requested_topics():
    contract = api.get_cron_long_strategy()
    assert contract["version"] == 2 and contract["semantic_story_review_required"]
    profiles = {p["key"]: p for p in contract["themes"]}
    assert {"mystery_story", *themes.PROFILES} <= profiles.keys()
    assert profiles["domestic_politics"]["manual_review_required"]
    assert not contract["future_views_guaranteed"]
