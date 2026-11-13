from datetime import datetime, timedelta, timezone

import pytest

import api
import ryuundy_growth_learning as growth

NOW = datetime(2026, 11, 13, 10, tzinfo=timezone.utc)


def upload(index, title, views, *, days=4, **updates):
    stamp = (NOW - timedelta(days=days)).isoformat()
    return api.YouTubeUploadJob(id=str(index), source_job_id=f"job-{index}",
        clip_url=f"/outputs/{index}/clip.mp4", clip_name=f"clip_{index}.mp4",
        status="completed", created_at=stamp, finished_at=stamp, updated_at=NOW.isoformat(),
        title=title, visibility="public", target_channel="ryuundyofficial", upload_confirmed=True,
        video_url=f"https://www.youtube.com/watch?v={index:011d}",
        performance_snapshots=[api.YouTubePerformanceSnapshot(captured_at=NOW.isoformat(),
            source="youtube_public", views=views)]).model_copy(update=updates)


def report(rows, **kwargs):
    return growth.performance_report(rows, signals=api.RYUUNDY_CRON_THEME_SIGNALS,
        enabled_themes=set(api.RYUUNDY_CRON_THEME_PROFILES) - {"korean_drama_story"}, now=NOW, **kwargs)


def examples():
    return [upload(1, "Kak Yuta selamatkan Mio", 5000),
            upload(2, "Mio terjebak labirin", 1900),
            upload(3, "Baby Selin membuka pintu", 1600),
            *[upload(i, "Percakapan di kantor", 100) for i in range(4, 8)]]


def test_recurring_character_series_has_replicated_age_matched_evidence():
    data = report(examples())
    assert data["winner"] == "gaming_story"
    cohort = data["cohorts"]["gaming_story"]
    assert cohort["samples"] == 3 and cohort["median_views"] == 1900
    assert cohort["median_age_matched_lift"] == 19
    assert cohort["character_series_samples"] == 3
    assert not data["causal_claim"] and not data["actual_retention_verified"]
    assert cohort["retention_samples"] == 0


@pytest.mark.parametrize("updates,reason", [
    ({"visibility": "private"}, "not_public"),
    ({"dry_run": True}, "unconfirmed_or_dry_run"),
    ({"upload_confirmed": False}, "unconfirmed_or_dry_run"),
    ({"target_channel": "other"}, "other_channel"),
    ({"clip_name": "resume_cerita_demo.mp4"}, "long_format"),
    ({"video_url": None}, "missing_or_duplicate_remote_id"),
    ({"video_url": "https://example.com/watch?v=00000000001"}, "missing_or_duplicate_remote_id"),
    ({"publish_at": (NOW + timedelta(days=1)).isoformat()}, "outside_mature_publication_window"),
    ({"finished_at": (NOW - timedelta(hours=2)).isoformat()}, "outside_mature_publication_window"),
    ({"performance_snapshots": []}, "unmeasured"),
    ({"playlist": "News"}, "independent_news_lane"),
])
def test_unpublished_unknown_other_format_or_unmeasured_upload_cannot_vote(updates, reason):
    row = upload(9, "Mio mengambil kunci", 100000, **updates)
    data = report([row])
    assert data["eligible_samples"] == 0 and data["winner"] is None
    assert data["excluded"][reason] == 1


def test_private_zero_view_uploads_cannot_depress_the_baseline():
    rows = examples()[:3] + [upload(i, "Pembicaraan lain", 0, visibility="private") for i in range(10, 50)]
    data = report(rows)
    assert data["winner"] is None
    assert data["excluded"]["not_public"] == 40


def test_same_remote_video_only_casts_one_vote():
    first = examples()[0]
    data = report([first, first.model_copy(update={"id": "retry"}), *examples()[3:]])
    assert data["winner"] is None
    assert data["cohorts"]["gaming_story"]["samples"] == 1


def test_newer_private_checkpoint_cannot_be_counted_through_older_public_retry():
    public = examples()[0]
    private = public.model_copy(update={"id": "private", "visibility": "private",
        "updated_at": (NOW + timedelta(seconds=1)).isoformat()})
    data = report([public, private])
    assert data["eligible_samples"] == 0


def test_weak_character_subseries_does_not_inherit_other_gaming_success():
    rows = [upload(i, "Roblox roleplay obby survival", 5000) for i in range(10, 17)]
    rows += [row.model_copy(update={"performance_snapshots": [api.YouTubePerformanceSnapshot(
        captured_at=NOW.isoformat(), source="youtube_public", views=10)]}) for row in examples()[:3]]
    data = report(rows + examples()[3:])
    assert data["winner"] == "gaming_story"
    assert data["cohorts"]["gaming_story"]["character_series_qualified"] is False


def test_old_outlier_and_younger_cohort_cannot_manufacture_a_winner():
    rows = [upload(i, "Mio dan Yuta di Roblox", 10000, days=20) for i in range(1, 4)]
    rows += [upload(i, "Percakapan biasa", 10, days=2) for i in range(4, 8)]
    assert report(rows)["winner"] is None


def test_single_viral_outlier_does_not_pass_median_gate():
    rows = [upload(1, "Mio Roblox", 1000000), upload(2, "Yuta Roblox", 10), upload(3, "Selin Roblox", 15)]
    assert report(rows + examples()[3:])["winner"] is None


@pytest.mark.parametrize("age_days", [4, 40])
def test_measurement_must_be_fresh_and_taken_after_maturity(age_days):
    row = upload(1, "Mio Roblox", 10000, days=10)
    row.performance_snapshots[0].captured_at = (NOW - timedelta(days=age_days)).isoformat()
    assert report([row])["eligible_samples"] == 0


def test_non_gaming_cohort_can_win_without_enabling_korean_drama():
    rows = [upload(i, "Drama China pengkhianatan keluarga analisis", 3000) for i in range(1, 4)]
    data = report(rows + examples()[3:])
    assert data["winner"] == "chinese_drama_story"


def test_old_wrong_hashtag_cannot_relabel_character_fiction_as_religion():
    theme, series = growth.content_theme("Kak Yuta menyelamatkan Mio #Islam",
        api.RYUUNDY_CRON_THEME_SIGNALS, set(api.RYUUNDY_CRON_THEME_PROFILES))
    assert theme == "gaming_story" and series == "character_roleplay"


def test_scheduler_focuses_proven_series_but_retains_exploration(monkeypatch):
    data = report(examples())
    monkeypatch.setattr(api, "ryuundy_channel_growth_report", lambda: data)
    monkeypatch.setenv("AUTO_VIRAL_SCHEDULE_PERFORMANCE_WINNER_ENABLED", "true")
    monkeypatch.setenv("AUTO_VIRAL_SCHEDULE_PERFORMANCE_WINNER_SHARE_PERCENT", "75")
    key, profile = api.scheduled_performance_winner_profile()
    assert key == "gaming_story" and profile["queries"][0] == growth.CHARACTER_QUERIES[0]
    assert "dua detik" in profile["short_role"] and len(profile["short_role"]) <= 800
    assert profile["performance_evidence"]["series"] == "character_roleplay"
    assert api.RYUUNDY_CRON_THEME_PROFILES[key]["queries"][0] != growth.CHARACTER_QUERIES[0]
    # This turn falls in the configured exploration share.
    from types import SimpleNamespace
    monkeypatch.setattr(api, "auto_viral_runs", {str(i): SimpleNamespace(trigger="schedule") for i in range(8)})
    assert api.scheduled_performance_winner_profile() is None


def test_character_editor_brief_stays_in_relevant_cron_lanes():
    manual = api.AutoViralRequest(creator_perspective="My review")
    assert growth.CHARACTER_EDITOR_BRIEF not in api.auto_viral_format_perspective(manual, long_form=False)
    story = manual.model_copy(update={"cron_theme_key": "gaming_story"})
    assert growth.CHARACTER_EDITOR_BRIEF in api.auto_viral_format_perspective(story, long_form=False)
    news = manual.model_copy(update={"cron_theme_key": api.NEWS_HOT_THEME})
    assert growth.CHARACTER_EDITOR_BRIEF not in api.auto_viral_format_perspective(news, long_form=False)


def test_scheduled_request_preserves_proven_series_queries_instead_of_generic_catalogue(monkeypatch):
    data = report(examples())
    monkeypatch.setattr(api, "ryuundy_channel_growth_report", lambda: data)
    monkeypatch.setattr(api, "scheduled_news_hot_due", lambda: False)
    monkeypatch.setattr(api, "scheduled_auto_viral_youtube_browser_ready", lambda: False)
    monkeypatch.setattr(api, "scheduled_auto_viral_rights_profile_ready", lambda: False)
    key, profile = api.scheduled_performance_winner_profile()
    monkeypatch.setattr(api, "scheduled_ryuundy_theme_profile", lambda: (key, profile))
    request = api.scheduled_auto_viral_request()
    assert request.cron_theme_key == "gaming_story"
    assert request.theme_focus in growth.CHARACTER_QUERIES
    assert set(request.queries) == set(growth.CHARACTER_QUERIES)
