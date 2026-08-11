import pytest

import youtube_uploader
from youtube_uploader import UploadError, ensure_supported_studio_browser


UNSUPPORTED_TEXT = "sempurnakanpengalamanandabrowseryangtidakdidukungversibrowserlama"


class CompatibilityPage:
    def __init__(self, url="https://studio.youtube.com/channel/demo"):
        self.url = url
        self.goto_calls = []
        self.wait_calls = []

    def evaluate(self, _script):
        return "https://studio.youtube.com/upload?approve_browser_access=true"

    def goto(self, url, **kwargs):
        self.goto_calls.append((url, kwargs))
        self.url = url

    def wait_for_load_state(self, state, **kwargs):
        self.wait_calls.append((state, kwargs))


def test_unsupported_browser_page_uses_youtube_official_continue_link(monkeypatch):
    page = CompatibilityPage()
    page_texts = iter((UNSUPPORTED_TEXT, "Konten channel Dashboard"))
    monkeypatch.setattr(youtube_uploader, "normalized_page_text", lambda _page: next(page_texts))

    ensure_supported_studio_browser(page)

    assert page.goto_calls == [
        (
            "https://studio.youtube.com/upload?approve_browser_access=true",
            {"wait_until": "domcontentloaded", "timeout": 30000},
        )
    ]
    assert page.wait_calls == [("domcontentloaded", {"timeout": 15000})]


def test_unsupported_browser_page_fails_after_official_continue_is_rejected(monkeypatch):
    page = CompatibilityPage(
        "https://studio.youtube.com/upload?approve_browser_access=true"
    )
    debug_labels = []
    monkeypatch.setattr(youtube_uploader, "normalized_page_text", lambda _page: UNSUPPORTED_TEXT)
    monkeypatch.setattr(
        youtube_uploader,
        "save_debug_artifacts",
        lambda _page, label: debug_labels.append(label),
    )

    with pytest.raises(UploadError, match="tetap menolak"):
        ensure_supported_studio_browser(page)

    assert page.goto_calls == []
    assert debug_labels == ["youtube-browser-unsupported"]


def test_supported_studio_page_does_not_navigate(monkeypatch):
    page = CompatibilityPage()
    monkeypatch.setattr(youtube_uploader, "normalized_page_text", lambda _page: "Dashboard channel")

    ensure_supported_studio_browser(page)

    assert page.goto_calls == []
