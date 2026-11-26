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


def test_active_short_job_still_blocks(monkeypatch):
    monkeypatch.setattr(api, "jobs", {"short": _job("short")})
    monkeypatch.setattr(api.time, "sleep", lambda _seconds: None)
    with pytest.raises(RuntimeError, match="Short"):
        api.wait_for_no_active_clipping_job(timeout_seconds=0)


def test_evergreen_window_admits_older_source_but_news_hot_does_not():
    older = (datetime.now(timezone.utc) - timedelta(days=120)).strftime("%Y%m%d")
    info = {"upload_date": older, "duration": 1800, "definition": "hd"}
    evergreen = api.AutoViralRequest(cron_theme_key="lecture_wisdom", max_age_days=30)
    assert api.viral_search_hard_filter_rejection_reason(info, evergreen) == ""
    news = api.AutoViralRequest(cron_theme_key=api.NEWS_HOT_THEME, max_age_days=2)
    assert "News Hot" in api.viral_search_hard_filter_rejection_reason(info, news)
