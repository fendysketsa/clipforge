import ast
import pytest
from pathlib import Path
from types import SimpleNamespace

import youtube_uploader
from youtube_uploader import (
    UploadError,
    ensure_studio_page_healthy,
    ensure_supported_studio_browser,
    ensure_target_identity,
    goto_upload_page,
)


UNSUPPORTED_TEXT = "sempurnakanpengalamanandabrowseryangtidakdidukungversibrowserlama"


@pytest.mark.parametrize("relative", [
    "backend/youtube_uploader.py", "backend/tiktok_uploader.py",
    "backend/youtube_remote_status.py", "backend/youtube_blocked_cleanup.py",
    "scripts/delete-youtube-studio-video.py",
])
def test_shared_cdp_connections_never_override_user_media_preferences(relative):
    # Every attach changes all existing pages unless no_defaults is set,
    # including attaches used only to snapshot cookies in the background.
    root = Path(__file__).resolve().parents[2]
    tree = ast.parse((root / relative).read_text())
    connections = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Attribute) and node.func.attr == "connect_over_cdp"]
    assert connections
    for call in connections:
        assert any(kw.arg == "no_defaults" and isinstance(kw.value, ast.Constant)
                   and kw.value.value is True for kw in call.keywords), (relative, call.lineno)


def test_cdp_upload_does_not_overwrite_live_session_by_default(monkeypatch):
    monkeypatch.delenv("YOUTUBE_CDP_HYDRATE_STORAGE_STATE", raising=False)
    page = object()
    context = SimpleNamespace(new_page=lambda: page)
    monkeypatch.setattr(youtube_uploader, "hydrate_context_and_open_studio_page", lambda *_: pytest.fail("must not inject old cookies into live Chrome"))
    assert youtube_uploader.open_cdp_upload_page(context, Path("stale-state.json")) is page


def test_cdp_cookie_hydration_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("YOUTUBE_CDP_HYDRATE_STORAGE_STATE", "true")
    page = object()
    monkeypatch.setattr(youtube_uploader, "hydrate_context_and_open_studio_page", lambda *_: page)
    assert youtube_uploader.open_cdp_upload_page(object(), Path("state.json")) is page


def test_capture_session_reads_chrome_without_cookie_hydration_by_default():
    args = youtube_uploader.build_parser().parse_args(["capture-session"])
    assert args.hydrate_storage_state is False
    requested = youtube_uploader.build_parser().parse_args(["capture-session", "--hydrate-storage-state"])
    assert requested.hydrate_storage_state is True


class CompatibilityPage:
    def __init__(
        self,
        url="https://studio.youtube.com/channel/demo",
        active_channel_id="",
        body_text="Dashboard channel",
        body_html="",
    ):
        self.url = url
        self.active_channel_id = active_channel_id
        self.body_text = body_text
        self.body_html = body_html
        self.goto_calls = []
        self.wait_calls = []

    def evaluate(self, script):
        if "CHANNEL_ID" in script:
            return self.active_channel_id
        return "https://studio.youtube.com/upload?approve_browser_access=true"

    def goto(self, url, **kwargs):
        self.goto_calls.append((url, kwargs))
        self.url = url

    def wait_for_load_state(self, state, **kwargs):
        self.wait_calls.append((state, kwargs))

    def locator(self, selector):
        return CompatibilityLocator(self, selector)

    def content(self):
        return self.body_html


class CompatibilityLocator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    @property
    def first(self):
        return self

    def count(self):
        return int(self.selector == "body")

    def is_visible(self, **_kwargs):
        return bool(self.count())

    def inner_text(self, **_kwargs):
        return self.page.body_text


def test_unsupported_browser_page_uses_youtube_official_continue_link(monkeypatch):
    page = CompatibilityPage()
    page_texts = iter((UNSUPPORTED_TEXT, "Konten channel Dashboard", "Konten channel Dashboard"))
    monkeypatch.setattr(youtube_uploader, "normalized_page_text", lambda _page: next(page_texts))

    ensure_supported_studio_browser(page)

    assert page.goto_calls == [
        (
            "https://studio.youtube.com/upload?approve_browser_access=true",
            {"wait_until": "domcontentloaded", "timeout": 30000},
        ),
        (
            "https://studio.youtube.com/channel/demo?approve_browser_access=true",
            {"wait_until": "domcontentloaded", "timeout": 30000},
        ),
    ]
    assert page.wait_calls == [
        ("domcontentloaded", {"timeout": 15000}),
        ("domcontentloaded", {"timeout": 15000}),
    ]


def test_browser_approval_rejects_studio_app_load_error(monkeypatch):
    page = CompatibilityPage(body_text="Maaf, ada yang tidak beres")
    page_texts = iter((UNSUPPORTED_TEXT, "Konten channel Dashboard"))
    debug_labels = []
    monkeypatch.setattr(youtube_uploader, "normalized_page_text", lambda _page: next(page_texts))
    monkeypatch.setattr(
        youtube_uploader,
        "save_debug_artifacts",
        lambda _page, label: debug_labels.append(label),
    )

    with pytest.raises(UploadError, match="gagal memuat aplikasi"):
        ensure_supported_studio_browser(page)

    assert debug_labels == ["youtube-studio-app-load-error"]


def test_deleted_video_bootstrap_releases_stale_remote_checkpoint(monkeypatch):
    page = CompatibilityPage(
        url="https://studio.youtube.com/video/rfbqkjiyuc4/edit",
        body_text="Maaf, ada yang tidak beres",
        body_html='<script>resolve({"videoId":"rfbqkjiyuc4","status":"VIDEO_STATUS_DELETED"})</script>',
    )
    debug_labels = []
    monkeypatch.setattr(
        youtube_uploader,
        "save_debug_artifacts",
        lambda _page, label: debug_labels.append(label),
    )

    with pytest.raises(UploadError, match="belum ditemukan sebagai baris tersimpan"):
        ensure_studio_page_healthy(page)

    assert debug_labels == ["youtube-video-deleted"]


def test_browser_approval_preserves_restore_navigation_error(monkeypatch):
    page = CompatibilityPage()
    page_texts = iter((UNSUPPORTED_TEXT, "Konten channel Dashboard"))
    original_goto = page.goto

    def fail_restore(url, **kwargs):
        if url == "https://studio.youtube.com/channel/demo?approve_browser_access=true":
            raise TimeoutError("restore timeout")
        original_goto(url, **kwargs)

    page.goto = fail_restore
    monkeypatch.setattr(youtube_uploader, "normalized_page_text", lambda _page: next(page_texts))

    with pytest.raises(UploadError, match="gagal memulihkan halaman channel.*restore timeout"):
        ensure_supported_studio_browser(page)


def test_browser_approval_restore_error_never_has_blank_detail(monkeypatch):
    page = CompatibilityPage()
    page_texts = iter((UNSUPPORTED_TEXT, "Konten channel Dashboard"))
    original_goto = page.goto

    def fail_restore(url, **kwargs):
        if url == "https://studio.youtube.com/channel/demo?approve_browser_access=true":
            raise TimeoutError()
        original_goto(url, **kwargs)

    page.goto = fail_restore
    monkeypatch.setattr(youtube_uploader, "normalized_page_text", lambda _page: next(page_texts))

    with pytest.raises(UploadError, match="Detail: navigasi Studio berhenti tanpa detail"):
        ensure_supported_studio_browser(page)


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


def test_target_url_does_not_override_active_channel_mismatch(monkeypatch):
    page = CompatibilityPage(
        "https://studio.youtube.com/channel/target",
        active_channel_id="other-channel",
    )

    with pytest.raises(UploadError, match="bukan channel target"):
        ensure_target_identity(page, "Target", "target@example.com", "target")


def test_channel_id_comparison_is_case_sensitive():
    page = CompatibilityPage(
        "https://studio.youtube.com/channel/UCtarget",
        active_channel_id="uctarget",
    )

    with pytest.raises(UploadError, match="bukan channel target"):
        ensure_target_identity(page, "Target", "target@example.com", "UCtarget")


def test_target_channel_id_is_not_satisfied_by_google_email_alone(monkeypatch):
    target_channel_id = "UCtarget1234567890123456"
    page = CompatibilityPage(f"https://studio.youtube.com/channel/{target_channel_id}")
    monkeypatch.setattr(
        youtube_uploader,
        "normalized_page_text",
        lambda _page: "target@example.com",
    )

    with pytest.raises(UploadError, match="bukan channel atau akun target"):
        ensure_target_identity(page, "Target", "target@example.com", target_channel_id)


def test_upload_page_failure_always_includes_diagnostic(monkeypatch):
    page = CompatibilityPage()
    page.reload = lambda **_kwargs: None
    monkeypatch.setattr(youtube_uploader, "ensure_supported_studio_browser", lambda _page: None)
    monkeypatch.setattr(youtube_uploader, "ensure_studio_page_healthy", lambda _page: None)
    monkeypatch.setattr(youtube_uploader, "wait_for_upload_surface", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(youtube_uploader, "wait_for_file_input", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(youtube_uploader, "click_select_files_entry", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(youtube_uploader, "click_create_upload_by_topbar_position", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(youtube_uploader, "save_debug_artifacts", lambda *_args, **_kwargs: None)

    with pytest.raises(UploadError, match=r"Detail: URL https://studio\.youtube\.com/upload"):
        goto_upload_page(page, channel_id="target")
