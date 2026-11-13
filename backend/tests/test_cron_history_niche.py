"""Cron reference discovery, format propagation and manual isolation."""
from datetime import datetime, timezone
from types import SimpleNamespace

import api


THEME = "history_geography_nusantara"


def history_source():
    return {
        "url": "https://www.youtube.com/watch?v=75K0oO1M4UM",
        "title": "Mengapa Belanda Takut dengan Selatan Jawa, dan Membiarkannya Kosong dan Sepi?",
        "description": "Dokumenter sejarah dan geografi Nusantara dalam bahasa Indonesia. "
                       "Membahas VOC, pesisir selatan Jawa, Daendels dan jalur perdagangan.",
        "tags": ["sejarah Indonesia", "geografi", "VOC"], "language": "id",
        "duration": 1368, "view_count": 5000,
        # Synthetic gate evidence for this test, not the reference's license.
        "license": "Creative Commons Attribution license",
    }


def test_reference_fits_history_lane_without_misclassifying_gameplay():
    assert api.cron_trend_candidate_rejection_reason(history_source(), theme_key=THEME) == ""
    assert "tema tidak cocok" in api.cron_trend_candidate_rejection_reason(
        {"title": "Roblox mabar lucu dan comeback", "language": "id"}, theme_key=THEME,
    )


def test_rotation_can_select_new_history_lane(monkeypatch):
    for name in ("scheduled_islamic_animation_trial_profile", "scheduled_performance_winner_profile",
                 "scheduled_search_term_winner_profile"):
        monkeypatch.setattr(api, name, lambda: None)
    monkeypatch.setattr(api, "auto_viral_runs", {
        key: SimpleNamespace(trigger="schedule", created_at=datetime.now(timezone.utc).isoformat(),
                             request=SimpleNamespace(cron_theme_key=key))
        for key in api.RYUUNDY_CRON_THEME_PROFILES if key != THEME
    })
    assert api.scheduled_ryuundy_theme_profile()[0] == THEME


def test_scheduler_carries_history_queries_and_editorial_context(monkeypatch):
    profile = api.RYUUNDY_CRON_THEME_PROFILES[THEME]
    monkeypatch.setattr(api, "scheduled_news_hot_due", lambda: False)
    monkeypatch.setattr(api, "scheduled_ryuundy_theme_profile", lambda: (THEME, profile))
    monkeypatch.setenv("AUTO_VIRAL_SCHEDULE_AUTO_UPLOAD_YOUTUBE", "false")
    request = api.scheduled_auto_viral_request()
    assert request.cron_theme_key == THEME
    assert request.theme_focus in profile["queries"]
    assert request.queries[0] == request.theme_focus
    assert request.source_urls == []  # reference is not an unconditional upload
    assert "mitos" in request.cron_editorial_tone
    assert "ketidakpastian" in request.cron_long_role


def test_both_formats_persist_niche_and_avoid_unrelated_hashtags(monkeypatch):
    captured = []
    monkeypatch.setattr(api, "wait_for_no_active_clipping_job", lambda: None)
    monkeypatch.setattr(api, "normalize_job_request", lambda request: request)
    monkeypatch.setattr(api, "queue_auto_viral_clip_job", lambda request:
                        captured.append(request) or SimpleNamespace(id="history-short", request=request))
    profile = api.RYUUNDY_CRON_THEME_PROFILES[THEME]
    request = api.AutoViralRequest(cron_theme_key=THEME, cron_editorial_tone=profile["tone"],
        cron_short_role=profile["short_role"], cron_long_role=profile["long_role"],
        create_paired_long_video=True, paired_long_video_count=1)
    short = api.create_auto_viral_clip_job(history_source(), request, scheduled=True)
    short.candidates = [SimpleNamespace(start=20, end=55)]
    api.create_auto_viral_paired_long_job(history_source(), request, short, wait_for_slot=False)
    assert [row.clip_mode for row in captured] == ["short", "highlight_5m"]
    for row in captured:
        restored = api.ClipJobRequest.model_validate(row.model_dump())
        assert restored.scheduled_theme_key == THEME and restored.scheduled_public_source_credit
        assert "SejarahNusantara" in restored.required_hashtags
        assert not set(restored.required_hashtags) & {"KisahNyata", "KisahIslami", "HororIndonesia"}


def test_manual_request_does_not_enter_new_cron_lane(monkeypatch):
    monkeypatch.setattr(api, "auto_viral_runs", {"manual": SimpleNamespace(trigger="manual")})
    assert not api.cron_trend_discovery_active("manual", api.AutoViralRequest(cron_trend_lane=True))
    assert api.AutoViralRequest().cron_theme_key == ""
