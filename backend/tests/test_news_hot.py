from datetime import datetime, timedelta, timezone
import pytest

import api
from news_hot import NEWS_HOT_THEME, news_hot_topic_rejection_reason


NOW = datetime(2026, 11, 5, 17, 5, tzinfo=timezone.utc)  # Nov 6, 00:05 WIB


def run(key, created=NOW, status="completed", theme=NEWS_HOT_THEME, trigger="schedule"):
    return api.AutoViralRun(
        id=key, created_at=created.isoformat(), updated_at=created.isoformat(),
        finished_at=created.isoformat(), status=status, trigger=trigger,
        request=api.AutoViralRequest(cron_theme_key=theme, video_count=1, clips_per_video=1),
    )


@pytest.fixture
def news(monkeypatch):
    monkeypatch.setenv("AUTO_VIRAL_SCHEDULE_NEWS_HOT_ENABLED", "true")
    monkeypatch.setenv("AUTO_VIRAL_SCHEDULE_NEWS_HOT_DAILY_LIMIT", "3")
    monkeypatch.setattr(api, "auto_viral_active_run_id", None)


def test_daily_reservations_use_wib_keep_failures_and_cross_midnight_inflight(news, monkeypatch):
    rows = [run("today-failed", status="failed"), run("today-cancelled", status="cancelled"),
            run("yesterday", NOW - timedelta(minutes=10)),
            run("inflight-yesterday", NOW - timedelta(minutes=10), status="running"),
            run("main", theme="gaming_story"), run("manual", trigger="manual")]
    monkeypatch.setattr(api, "auto_viral_runs", {r.id: r for r in rows})
    assert api.news_hot_daily_reserved(NOW) == 3
    assert not api.scheduled_news_hot_due(NOW)
    # This is the same primitive used inside the creation lock, without reacquiring it.
    with api.auto_viral_lock:
        assert api.news_hot_daily_reserved(NOW, runs=rows) == 3


def test_news_request_survives_reload_without_sermon_queries_or_publication(news):
    request = api.AutoViralRequest.model_validate(api.scheduled_news_hot_request().model_dump())
    assert request.cron_theme_key == NEWS_HOT_THEME
    assert request.video_count == request.clips_per_video == request.top == 1
    assert request.max_age_days == 2
    assert not request.auto_upload_youtube and not request.auto_upload_tiktok
    assert not request.create_paired_long_video and not request.auto_publish_paired_long_video
    assert api.auto_viral_youtube_playlist(request) == "News"
    perspective = api.auto_viral_format_perspective(request, long_form=False)
    assert "RYUUNDY" in perspective and "tuduhan" in perspective
    assert "Short dan Long" not in perspective
    assert all("islam" not in q.casefold() for q in request.queries)


def test_interleaves_main_campaign_and_can_render_with_full_studio(news, monkeypatch):
    latest = run("latest")
    monkeypatch.setattr(api, "latest_scheduled_auto_viral_run", lambda: latest)
    monkeypatch.setattr(api, "auto_viral_daily_mix_incomplete", lambda *_: True)
    assert not api.scheduled_news_hot_due(NOW)
    monkeypatch.setattr(api, "auto_viral_daily_mix_incomplete", lambda *_: False)
    assert api.scheduled_news_hot_due(NOW)
    monkeypatch.setattr(api, "youtube_cron_buffer_enabled", lambda: True)
    monkeypatch.setattr(api, "youtube_cron_capacity_room", lambda: 0)
    monkeypatch.setattr(api, "auto_viral_boot_not_before", lambda _: NOW)
    monkeypatch.setattr(api, "auto_viral_run_can_resume_upload", lambda _: False)
    assert api.auto_viral_next_run_at(NOW, None, None) == NOW
    assert api.auto_viral_next_run_at(NOW, None, "active") is None


@pytest.mark.parametrize("age", [None, 3, 30, 90])
def test_news_freshness_cannot_relax_to_old_sources(news, monkeypatch, age):
    monkeypatch.setenv("VIRAL_CC_ADAPTIVE_FILTERS", "true")
    monkeypatch.setenv("VIRAL_CC_REQUIRE_UPLOAD_DATE", "false")
    monkeypatch.setattr(api, "upload_age_days", lambda _: age)
    assert "News Hot" in api.viral_search_hard_filter_rejection_reason({}, api.scheduled_news_hot_request())


@pytest.mark.parametrize("title,accepted", [
    ("Berita politik Indonesia: penjelasan dampak kebijakan pemerintah", True),
    ("Wawancara DPR RI soal kebijakan publik", True),
    ("Berita politik Amerika hari ini", False),
    ("Berita sepak bola Indonesia terbaru", False),
    ("Politik Indonesia: dukung partai kami", False),
])
def test_news_topic_scope(title, accepted):
    assert (not news_hot_topic_rejection_reason({"title": title})) is accepted


def test_review_gate_applies_before_youtube_and_tiktok_preflight(news):
    job = api.ClipJob(
        id="news", status="completed", created_at=NOW.isoformat(), updated_at=NOW.isoformat(),
        request=api.ClipJobRequest(source_file="owned.mp4", scheduled_news_hot=True),
    )
    clip = api.ClipFile(name="news.mp4", url="/outputs/news/news.mp4", size_bytes=123)
    assert "News Hot ditahan" in api.youtube_monetization_preflight_issue(job, clip)
    assert api.automatic_youtube_playlist(job, clip, "Nasihat #Islam") == "News"


def test_disabled_news_preserves_regular_daily_quotas(monkeypatch):
    monkeypatch.setenv("AUTO_VIRAL_SCHEDULE_NEWS_HOT_ENABLED", "false")
    monkeypatch.setenv("AUTO_VIRAL_DAILY_UPLOAD_LIMIT", "23")
    monkeypatch.setenv("AUTO_VIRAL_DAILY_SHORT_UPLOAD_TARGET", "23")
    assert not api.scheduled_news_hot_due(NOW)
    assert api.auto_viral_daily_short_upload_target() == 23


def test_creation_enforces_daily_limit_before_spawning(news, monkeypatch):
    monkeypatch.setattr(api, "auto_viral_runs", {str(i): run(str(i), datetime.now(timezone.utc)) for i in range(3)})
    with pytest.raises(api.HTTPException, match="Slot News Hot") as exc:
        api.create_and_start_auto_viral_campaign(api.scheduled_news_hot_request(), trigger="schedule")
    assert exc.value.status_code == 409


def test_history_pruning_cannot_reset_news_reservations(news, monkeypatch):
    import json

    now = datetime.now(timezone.utc)
    rows = [run("news", now - timedelta(minutes=15))]
    rows.extend(run(f"main-{i}", now, theme="gaming_story") for i in range(12))
    monkeypatch.setenv("AUTO_VIRAL_HISTORY_LIMIT", "10")
    monkeypatch.setattr(api, "auto_viral_runs", {r.id: r for r in rows})
    api.save_auto_viral_runs_unlocked()
    payload = json.loads(api.AUTO_VIRAL_RUNS_PATH.read_text())
    assert any(r["id"] == "news" for r in payload)
    assert api.news_hot_daily_reserved(now, runs=list(api.load_auto_viral_runs().values())) == 1


def test_news_clip_keeps_series_marker_and_measured_audio(news, monkeypatch):
    monkeypatch.setattr(api, "viral_source_rejection_reason", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(api, "wait_for_no_active_clipping_job", lambda: None)
    monkeypatch.setattr(api, "normalize_job_request", lambda value: value)
    monkeypatch.setattr(api, "queue_auto_viral_clip_job", lambda value: value)
    request = api.create_auto_viral_clip_job(
        {"url": "https://youtube.com/watch?v=news12345", "title": "Berita politik Indonesia: dampak kebijakan", "upload_date": "20261105"},
        api.scheduled_news_hot_request(), scheduled=True,
    )
    assert request.scheduled_news_hot and request.scheduled_public_source_credit
    assert not request.scheduled_reaction_avatar_layout and not request.scheduled_contextual_audio
    assert "20261105" in request.creator_perspective
    assert "Tanggal kejadian" in request.creator_perspective


def test_news_ranking_measures_politics_rather_than_story_keyword_overlap():
    metadata = {"title": "Berita politik Indonesia penjelasan dampak kebijakan pemerintah"}
    ranked = api.apply_cron_trend_ranking(
        {"language_score": 100, "momentum_score": 80}, metadata, theme_key=NEWS_HOT_THEME,
    )
    assert ranked["niche_label"] == "News Hot Indonesia"
    assert ranked["cron_trend_score"] >= 80


def test_campaign_renders_one_news_source_and_retains_it_for_review(news, monkeypatch):
    from types import SimpleNamespace

    request = api.scheduled_news_hot_request()
    campaign = run("news-campaign", datetime.now(timezone.utc), status="queued")
    campaign.request = request
    finished_job = SimpleNamespace(
        id="news-job", status="completed", clips=[SimpleNamespace(url="/outputs/news.mp4")], error=None,
    )
    monkeypatch.setattr(api, "auto_viral_runs", {campaign.id: campaign})
    monkeypatch.setattr(api, "jobs", {finished_job.id: finished_job})
    monkeypatch.setattr(api, "recently_processed_job_source_urls", lambda *_: set())
    monkeypatch.setattr(api, "discover_auto_viral_campaign_sources", lambda *_: [
        {"url": "https://youtube.com/watch?v=news12345", "title": "Berita politik Indonesia"},
        {"url": "https://youtube.com/watch?v=another12", "title": "Berita lain"},
    ])
    rendered = []

    def render(source, *_):
        rendered.append(source["url"])
        return finished_job

    monkeypatch.setattr(api, "create_auto_viral_clip_job", render)
    monkeypatch.setattr(api, "run_clip_job_with_campaign_progress", lambda *_: None)
    monkeypatch.setattr(api, "send_telegram_alert", lambda *_: None)
    monkeypatch.setattr(api, "queue_youtube_private_buffer_promotions_once", lambda: 0)
    api.run_auto_viral_campaign(campaign.id)
    result = api.auto_viral_runs[campaign.id]
    assert result.status == "completed"
    assert len(rendered) == 1 and result.progress_current == 1
    assert result.processed[0]["status"] == "manual_review_required"
    assert finished_job.id in api.jobs
    assert not api.youtube_uploads and not api.tiktok_uploads


def test_reviewed_news_upload_does_not_consume_main_cron_quota(news, monkeypatch):
    from types import SimpleNamespace

    news_run = run("news")
    main_run = run("main", theme="gaming_story")
    news_run.processed = [{"job_id": "news-job"}]
    main_run.processed = [{"job_id": "main-job"}]
    monkeypatch.setattr(api, "auto_viral_runs", {r.id: r for r in [news_run, main_run]})
    monkeypatch.setattr(api, "youtube_uploads", {
        key: SimpleNamespace(source_job_id=key, clip_url=f"/outputs/{key}.mp4", dry_run=False, status="queued")
        for key in ["news-job", "main-job"]
    })
    assert api.auto_viral_daily_platform_upload_keys("youtube", NOW) == {("main-job", "/outputs/main-job.mp4")}
    assert api.auto_viral_daily_youtube_content_counts(NOW) == {"short": 1, "long": 0}
