"""Long renders must not block Short discovery, and evergreen sources may age."""
from datetime import datetime, timedelta, timezone

import pytest

import api


def _job(mode, status="running"):
    return api.ClipJob(
        id="lane-test", status=status,
        created_at=api.now_iso(), updated_at=api.now_iso(),
        request=api.ClipJobRequest(clip_mode=mode),
    )


@pytest.mark.parametrize("mode", ["highlight_5m", "long_animate"])
def test_long_render_does_not_delay_short_wait(monkeypatch, mode):
    monkeypatch.setattr(api, "jobs", {"long": _job(mode)})
    monkeypatch.setattr(api.time, "sleep", lambda _seconds: None)
    api.wait_for_no_active_clipping_job(timeout_seconds=1)


@pytest.mark.parametrize("active_mode,incoming_mode,blocked", [
    ("highlight_5m", "short", False),
    ("long_animate", "short", False),
    ("short", "short", True),
    ("highlight_5m", "highlight_5m", True),
])
def test_queue_guard_separates_long_from_short(monkeypatch, active_mode, incoming_mode, blocked):
    monkeypatch.setattr(api, "jobs", {"active": _job(active_mode)})
    monkeypatch.setattr(api, "cron_source_process_limit_reached", lambda _url: False)
    monkeypatch.setattr(api, "save_jobs_unlocked", lambda: None)
    request = api.ClipJobRequest(clip_mode=incoming_mode, url="https://youtube.com/watch?v=abcdefghijk")
    if blocked:
        with pytest.raises(RuntimeError, match="clipping lain"):
            api.queue_auto_viral_clip_job(request)
    else:
        assert api.queue_auto_viral_clip_job(request).id


def test_active_short_job_still_blocks(monkeypatch):
    monkeypatch.setattr(api, "jobs", {"short": _job("short")})
    monkeypatch.setattr(api.time, "sleep", lambda _seconds: None)
    with pytest.raises(RuntimeError, match="Short"):
        api.wait_for_no_active_clipping_job(timeout_seconds=0)


@pytest.mark.parametrize("mode,expected", [("short", 1), ("highlight_5m", 0)])
def test_review_hold_only_suppresses_long_auto_upload(monkeypatch, mode, expected):
    job = api.ClipJob(
        id="review-lane", status="completed",
        created_at=api.now_iso(), updated_at=api.now_iso(),
        request=api.ClipJobRequest(clip_mode=mode, publication_review_required=True),
        clips=[api.ClipFile(name="a.mp4", url="/outputs/a.mp4", size_bytes=1)],
    )
    monkeypatch.setattr(api, "best_youtube_clip_urls", lambda j, n: [c.url for c in j.clips])
    monkeypatch.setattr(api, "youtube_monetization_preflight_issue", lambda j, c: None)
    assert len(api.best_automatic_upload_clip_urls(job, 1)) == expected


def test_evergreen_window_admits_older_source_but_news_hot_does_not():
    older = (datetime.now(timezone.utc) - timedelta(days=120)).strftime("%Y%m%d")
    info = {"upload_date": older, "duration": 1800, "definition": "hd"}
    evergreen = api.AutoViralRequest(cron_theme_key="lecture_wisdom", max_age_days=30)
    assert api.viral_search_hard_filter_rejection_reason(info, evergreen) == ""
    news = api.AutoViralRequest(cron_theme_key=api.NEWS_HOT_THEME, max_age_days=2)
    assert "News Hot" in api.viral_search_hard_filter_rejection_reason(info, news)
