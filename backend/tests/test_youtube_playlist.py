import pytest

import youtube_uploader
from youtube_uploader import UploadError, select_playlist


def configure_playlist_happy_path(monkeypatch, *, summaries):
    calls = []
    summary_results = iter(summaries)
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(youtube_uploader, "dismiss_reload_prompt", lambda _page: None)
    monkeypatch.setattr(youtube_uploader, "playlist_dialog_open", lambda _page, timeout_ms=0: False)
    monkeypatch.setattr(
        youtube_uploader,
        "open_playlist_dropdown",
        lambda _page, timeout_ms=0: calls.append("open") or True,
    )
    monkeypatch.setattr(
        youtube_uploader,
        "search_playlist",
        lambda _page, name: calls.append(f"search:{name}") or True,
    )
    monkeypatch.setattr(youtube_uploader, "playlist_is_selected", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        youtube_uploader,
        "click_playlist_done",
        lambda _page, timeout_ms=0: calls.append("done") or True,
    )
    monkeypatch.setattr(
        youtube_uploader,
        "playlist_dropdown_value_matches",
        lambda *_args, **_kwargs: next(summary_results),
    )
    monkeypatch.setattr(youtube_uploader, "save_debug_artifacts", lambda *_args: calls.append("debug"))
    monkeypatch.setattr(youtube_uploader, "log", calls.append)
    return calls


def test_playlist_summary_does_not_skip_explicit_search_and_checkbox_verification(monkeypatch):
    calls = configure_playlist_happy_path(monkeypatch, summaries=[True])

    select_playlist(object(), "Islam")

    assert "open" in calls
    assert "search:Islam" in calls
    assert "done" in calls
    assert "PLAYLIST_CONFIRMED: Islam" in calls


def test_playlist_selection_retries_when_collapsed_summary_is_not_confirmed(monkeypatch):
    calls = configure_playlist_happy_path(monkeypatch, summaries=[False, True])

    select_playlist(object(), "Islam")

    assert calls.count("open") == 2
    assert calls.count("search:Islam") == 2
    assert calls.count("done") == 2


def test_playlist_selection_fails_closed_instead_of_silently_skipping(monkeypatch):
    monkeypatch.setenv("YOUTUBE_PLAYLIST_SELECT_ATTEMPTS", "2")
    calls = configure_playlist_happy_path(monkeypatch, summaries=[False, False])

    with pytest.raises(UploadError, match="playlist tidak terlewati"):
        select_playlist(object(), "Islam")

    assert calls.count("open") == 2
    assert calls[-1] == "debug"
