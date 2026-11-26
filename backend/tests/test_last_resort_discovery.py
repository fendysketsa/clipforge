"""When on-theme sources are exhausted, widen search without weakening gates."""
import api
from api import AutoViralRequest


EXCLUDED = "https://www.youtube.com/watch?v=aaaaaaaaaaa"
FRESH = "https://www.youtube.com/watch?v=bbbbbbbbbbb"


def test_last_resort_widens_duration_but_keeps_exclusion(monkeypatch):
    monkeypatch.setenv("VIRAL_CC_REQUIRE_YOUTUBE_DATA_API", "false")
    monkeypatch.setattr(api, "search_youtube_data_api_viral_sources", lambda *a, **k: [])
    monkeypatch.setattr(api, "sort_viral_source_payloads", lambda *a, **k: None)
    monkeypatch.setattr(api, "preflight_scheduled_sources", lambda sources, *a: sources)
    monkeypatch.setattr(api, "diverse_viral_source_payloads", lambda sources, *a, **k: sources[:1])
    monkeypatch.setattr(api, "update_auto_viral_run", lambda *a, **k: None)
    monkeypatch.setattr(api, "append_auto_viral_log", lambda *a, **k: None)
    monkeypatch.setattr(api, "append_auto_viral_error", lambda *a, **k: None)

    calls = []

    def fake_search(request, run_id, *, exclude_urls=None, stop_after=None, max_metadata_checks=None):
        calls.append((list(request.queries), request.duration_filter, set(exclude_urls or ())))
        if len(calls) == 1:
            return []
        return [{"url": FRESH, "title": "Fresh"}]

    monkeypatch.setattr(api, "search_auto_viral_sources", fake_search)
    request = AutoViralRequest(video_count=1, queries=["kueri tema sempit"])
    result = api.discover_auto_viral_campaign_sources(request, "run", {EXCLUDED}, 3)

    assert len(calls) == 2
    assert calls[0][1] == "over_20"
    assert calls[1][1] == "any"
    assert EXCLUDED in calls[1][2]
    assert any(row["url"] == FRESH for row in result)
