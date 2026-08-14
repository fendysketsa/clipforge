import pytest

import youtube_uploader
from youtube_uploader import (
    UploadError,
    click_playlist_checkbox,
    playlist_dialog_open,
    playlist_is_selected,
    playlist_row_is_selected,
    select_playlist,
)


class CapturingPage:
    def __init__(self, result=True):
        self.result = result
        self.scripts = []

    def evaluate(self, script, *_args):
        self.scripts.append(script)
        return self.result


class FakeControl:
    def __init__(self, *, role=False, checked=False):
        self.role = role
        self.checked = checked
        self.clicks = 0

    def get_attribute(self, name):
        if name == "aria-checked" and self.role:
            return "true" if self.checked else "false"
        return None

    def is_checked(self, timeout=0):
        return self.checked

    def count(self):
        return 1

    def is_visible(self, timeout=0):
        return True

    def scroll_into_view_if_needed(self, timeout=0):
        return None

    def click(self, timeout=0):
        self.clicks += 1
        self.checked = True


class FakeControls:
    def __init__(self, controls):
        self.controls = controls

    def count(self):
        return len(self.controls)

    def nth(self, index):
        return self.controls[index]


class FakeFirst:
    def __init__(self, control=None):
        self.control = control

    @property
    def first(self):
        return self.control or FakeMissingControl()


class FakeMissingControl(FakeControl):
    def __init__(self):
        super().__init__()

    def count(self):
        return 0


class FakeRow:
    def __init__(self, checkbox):
        self.checkbox = checkbox

    def locator(self, selector):
        if selector.startswith('[role="checkbox"], input'):
            return FakeControls([self.checkbox])
        if selector in {'div#checkbox[role="checkbox"]', '[role="checkbox"]'}:
            return FakeFirst(self.checkbox)
        return FakeFirst()


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


def test_playlist_checkbox_targets_current_youtube_row_and_interactive_control(monkeypatch):
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda _seconds: None)
    page = CapturingPage()

    assert click_playlist_checkbox(page, "Islam", timeout_ms=100)

    script = page.scripts[0]
    assert "li.row" in script
    assert "label.ytcp-checkbox-label" in script
    assert "[role=\"checkbox\"]" in script
    assert "querySelectorAll('ytcp-playlist-dialog')" in script


def test_playlist_verification_is_scoped_to_matching_dialog_row(monkeypatch):
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda _seconds: None)
    page = CapturingPage()

    assert playlist_is_selected(page, "Islam", timeout_ms=100)

    script = page.scripts[0]
    assert "li.row" in script
    assert "checks.some(isChecked)" in script
    assert "querySelectorAll('ytcp-playlist-dialog')" in script


def test_closed_playlist_dialog_requires_visible_non_hidden_surface(monkeypatch):
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda _seconds: None)
    page = CapturingPage()

    assert playlist_dialog_open(page, timeout_ms=100)

    script = page.scripts[0]
    assert "surface.getAttribute?.('aria-hidden') !== 'true'" in script
    assert "label.includes('playlist baru')" not in script


def test_playlist_checkbox_uses_trusted_locator_click_and_verifies_state(monkeypatch):
    checkbox = FakeControl(role=True, checked=False)
    row = FakeRow(checkbox)
    monkeypatch.setattr(youtube_uploader, "playlist_row_locator", lambda *_args: row)
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(youtube_uploader, "log", lambda _message: None)

    assert click_playlist_checkbox(object(), "Islam", timeout_ms=100)
    assert checkbox.clicks == 1
    assert playlist_row_is_selected(row) is True


def test_playlist_selection_waits_for_real_checkbox_state_before_confirming(monkeypatch):
    calls = configure_playlist_happy_path(monkeypatch, summaries=[True])
    states = iter([False, True, True])
    monkeypatch.setattr(
        youtube_uploader,
        "playlist_is_selected",
        lambda *_args, **_kwargs: next(states),
    )
    monkeypatch.setattr(
        youtube_uploader,
        "click_playlist_checkbox",
        lambda *_args, **_kwargs: calls.append("trusted-click") or True,
    )

    select_playlist(object(), "Islam")

    assert "trusted-click" in calls
    assert calls.index("trusted-click") < calls.index("done")
    assert "PLAYLIST_CONFIRMED: Islam" in calls
