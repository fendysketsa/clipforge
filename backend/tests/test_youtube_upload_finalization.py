import pytest

import youtube_uploader
from youtube_uploader import (
    FENDY_CLIPPER_UPLOAD_PAGE_NAME,
    UploadError,
    click_final_upload_action,
    close_duplicate_target_studio_tabs,
    close_idle_fendy_clipper_upload_tabs,
    close_upload_tab,
    copyright_claim_is_explicitly_non_blocking,
    copyright_issue_detected,
    copyright_issue_blocks_upload,
    mark_fendy_clipper_upload_tab,
    next_upload_step_timeout_ms,
    open_advanced_upload_settings,
    reload_after_publish,
    safe_upload_visibility,
    save_claimed_upload_as_private,
    set_altered_content_disclosure,
    set_thumbnail,
    should_upload_custom_thumbnail,
    wait_for_copyright_checks,
    wait_for_final_upload_confirmation,
    wait_for_review_checks_safe_before_publish,
)


class TextPage:
    def __init__(self, body):
        self.body = body

    def locator(self, _selector):
        return self

    def count(self):
        return 1

    def inner_text(self, **_kwargs):
        return self.body


class SequenceTextPage(TextPage):
    def __init__(self, bodies):
        super().__init__(bodies[-1])
        self.bodies = list(bodies)

    def inner_text(self, **_kwargs):
        if len(self.bodies) > 1:
            return self.bodies.pop(0)
        return self.bodies[0]


class PendingPublishPage:
    def locator(self, selector):
        if selector == "body":
            return TextPage("Video yang dipublikasikan")
        return TextPage("Visibilitas Publik Publikasikan")


class ReloadPage:
    def __init__(self):
        self.reload_calls = []

    def once(self, *_args):
        return None

    def reload(self, **kwargs):
        self.reload_calls.append(kwargs)


class BrowserPage:
    def __init__(self, url="", window_name=""):
        self.url = url
        self.window_name = window_name
        self.closed = False

    def evaluate(self, script):
        if script == "window.name":
            return self.window_name
        if script.startswith("window.name = "):
            self.window_name = FENDY_CLIPPER_UPLOAD_PAGE_NAME
            return None
        raise AssertionError(f"Unexpected script: {script}")

    def is_closed(self):
        return self.closed

    def close(self):
        self.closed = True


class ClickableLocator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    @property
    def first(self):
        return self

    def count(self):
        return int(self.selector == "ytcp-video-metadata-editor ytcp-button#toggle-button button")

    def is_visible(self, **_kwargs):
        return bool(self.count())

    def click(self, **_kwargs):
        self.page.clicked_selectors.append(self.selector)


class AdvancedSettingsPage:
    def __init__(self):
        self.clicked_selectors = []

    def locator(self, selector):
        return ClickableLocator(self, selector)


class DisclosurePage(AdvancedSettingsPage):
    def __init__(self, results):
        super().__init__()
        self.results = list(results)
        self.scripts = []

    def evaluate(self, script):
        self.scripts.append(script)
        return self.results.pop(0) if len(self.results) > 1 else self.results[0]


class ThumbnailInputLocator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    @property
    def first(self):
        return self

    def count(self):
        return int(self.selector == 'input[type="file"][accept*="image"]')

    def set_input_files(self, path, **_kwargs):
        self.page.set_input_calls.append(path)
        self.page.upload_started = True


class ThumbnailFrame:
    def __init__(self, page):
        self.page = page

    def locator(self, selector):
        return ThumbnailInputLocator(self.page, selector)

    def evaluate(self, _script):
        if not self.page.upload_started:
            return {"found": True, "selected": False, "uploading": False, "error": ""}
        if self.page.state_reads == 0:
            self.page.state_reads += 1
            return {"found": True, "selected": True, "uploading": True, "error": ""}
        return {"found": True, "selected": True, "uploading": False, "error": ""}


class ThumbnailUploadPage:
    def __init__(self):
        self.upload_started = False
        self.state_reads = 0
        self.set_input_calls = []
        self.frames = [ThumbnailFrame(self)]

    def locator(self, selector):
        if selector == "body":
            return TextPage("")
        return ThumbnailInputLocator(self, selector)


def test_required_checks_do_not_continue_after_timeout_by_default(monkeypatch):
    monkeypatch.delenv("YOUTUBE_CONTINUE_WHEN_CHECKS_STUCK", raising=False)
    monkeypatch.setattr(youtube_uploader, "save_debug_artifacts", lambda *_args: None)

    with pytest.raises(UploadError, match="Step 3 Checks belum selesai"):
        wait_for_copyright_checks(object(), timeout_ms=0, require_checks=True)


def test_next_step_wait_defaults_to_fifteen_minutes(monkeypatch):
    monkeypatch.delenv("YOUTUBE_NEXT_STEP_TIMEOUT_SECONDS", raising=False)

    assert next_upload_step_timeout_ms(5_400_000) == 900_000


def test_next_step_wait_never_exceeds_total_upload_timeout(monkeypatch):
    monkeypatch.setenv("YOUTUBE_NEXT_STEP_TIMEOUT_SECONDS", "1800")

    assert next_upload_step_timeout_ms(600_000) == 600_000


def test_advanced_settings_uses_current_indonesian_studio_toggle():
    page = AdvancedSettingsPage()

    assert open_advanced_upload_settings(page)
    assert page.clicked_selectors == [
        "ytcp-video-metadata-editor ytcp-button#toggle-button button"
    ]


def test_altered_content_disclosure_is_verified_after_selection(monkeypatch):
    page = DisclosurePage(
        [
            {"found": True, "clicked": True, "selected": False},
            {"found": True, "clicked": False, "selected": True},
        ]
    )
    logs = []
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(youtube_uploader, "log", logs.append)

    set_altered_content_disclosure(page, required=True)

    assert len(page.scripts) == 2
    assert "'ai use'" in page.scripts[0]
    assert "'penggunaan ai'" in page.scripts[0]
    assert any("terverifikasi" in message for message in logs)


def test_altered_content_disclosure_is_skipped_when_not_required():
    page = DisclosurePage([{"found": False, "clicked": False, "selected": False}])

    set_altered_content_disclosure(page, required=False)

    assert page.clicked_selectors == []
    assert page.scripts == []


def test_checks_wait_when_one_item_is_safe_but_another_is_checking(monkeypatch):
    clock = iter((0.0, 0.0, 1.0))
    monkeypatch.delenv("YOUTUBE_CONTINUE_WHEN_CHECKS_STUCK", raising=False)
    monkeypatch.setattr(youtube_uploader.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(youtube_uploader, "dismiss_reload_prompt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(youtube_uploader, "save_debug_artifacts", lambda *_args: None)
    page = TextPage("Copyright: No issues found\nCommunity Guidelines: Checking")

    with pytest.raises(UploadError, match="Step 3 Checks belum selesai"):
        wait_for_copyright_checks(page, timeout_ms=100, require_checks=True)


def test_checks_extend_wait_when_youtube_says_it_needs_longer(monkeypatch):
    clock = iter((0.0, 0.0, 1.0))
    logs = []
    monkeypatch.setenv("YOUTUBE_CHECKS_LONG_RUNNING_EXTENSION_SECONDS", "10")
    monkeypatch.setenv("YOUTUBE_CHECKS_PROGRESS_LOG_INTERVAL_SECONDS", "60")
    monkeypatch.setattr(youtube_uploader.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(youtube_uploader, "dismiss_reload_prompt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(youtube_uploader, "log", logs.append)
    page = SequenceTextPage(
        [
            (
                "Hak cipta Tidak ditemukan masalah\n"
                "Pedoman Komunitas Masih memeriksa\n"
                "Perlu waktu lebih lama untuk menyelesaikan pemeriksaan"
            ),
            (
                "Hak cipta Tidak ditemukan masalah\n"
                "Pedoman Komunitas Tidak ditemukan masalah"
            ),
        ]
    )

    wait_for_copyright_checks(page, timeout_ms=100, require_checks=True)

    assert any("ditambah" in message for message in logs)
    assert any("sudah centang" in message for message in logs)


def test_checks_block_exact_indonesian_claim_notice_from_studio(monkeypatch):
    monkeypatch.setattr(youtube_uploader, "dismiss_reload_prompt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(youtube_uploader, "save_debug_artifacts", lambda *_args: None)
    page = TextPage(
        "Konten yang diklaim ditemukan di video ini. "
        "Klaim ini tidak memengaruhi visibilitas atau fitur video Anda."
    )

    with pytest.raises(UploadError, match="Content ID"):
        wait_for_copyright_checks(page, timeout_ms=100, require_checks=True)


def test_checks_accept_exact_two_check_non_blocking_claim_from_studio(monkeypatch):
    logs = []
    monkeypatch.setattr(youtube_uploader, "dismiss_reload_prompt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(youtube_uploader, "save_debug_artifacts", lambda *_args: None)
    monkeypatch.setattr(youtube_uploader, "log", logs.append)
    page = TextPage(
        "Konten yang dilindungi hak cipta ditemukan di video ini. "
        "Tidak ada dampak pada jangkauan video. Video ini dapat dilihat sesuai dengan setelan Anda. "
        "Tidak ada dampak pada channel. Hal ini bukan teguran hak cipta."
    )

    wait_for_copyright_checks(
        page,
        timeout_ms=100,
        require_checks=True,
        content_type="shorts",
        media_duration_seconds=59.8,
    )

    assert copyright_claim_is_explicitly_non_blocking(page.body)
    assert copyright_issue_blocks_upload(
        page.body,
        content_type="shorts",
        media_duration_seconds=0,
    )
    assert any("aman untuk dilanjutkan" in message for message in logs)


def test_checks_still_block_claimed_short_over_one_minute(monkeypatch):
    monkeypatch.setattr(youtube_uploader, "dismiss_reload_prompt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(youtube_uploader, "save_debug_artifacts", lambda *_args: None)
    page = TextPage(
        "Konten yang dilindungi hak cipta ditemukan di video ini. "
        "Tidak ada dampak pada jangkauan video. Video ini dapat dilihat sesuai dengan setelan Anda. "
        "Tidak ada dampak pada channel. Hal ini bukan teguran hak cipta."
    )

    with pytest.raises(UploadError, match="Short berdurasi lebih dari 1 menit"):
        wait_for_copyright_checks(
            page,
            timeout_ms=100,
            require_checks=True,
            content_type="shorts",
            media_duration_seconds=61.0,
        )


def test_non_blocking_copy_never_overrides_explicit_video_block():
    body = (
        "This video has a Content ID claim. No impact on your video. "
        "No impact on your channel. This is not a copyright strike. "
        "The video is blocked globally."
    )

    assert not copyright_claim_is_explicitly_non_blocking(body)
    assert copyright_issue_blocks_upload(body, content_type="long-form", media_duration_seconds=300)


def test_verified_safe_claim_carries_to_compact_final_review_copy():
    compact_body = "This video has a Content ID claim"

    assert not copyright_issue_blocks_upload(
        compact_body,
        content_type="shorts",
        media_duration_seconds=59.8,
        previously_verified_non_blocking_claim=True,
    )
    assert copyright_issue_blocks_upload(
        f"{compact_body}. Restrictions found",
        content_type="shorts",
        media_duration_seconds=59.8,
        previously_verified_non_blocking_claim=True,
    )
    assert copyright_issue_blocks_upload(
        compact_body,
        content_type="shorts",
        media_duration_seconds=61.0,
        previously_verified_non_blocking_claim=True,
    )


def test_generic_checks_complete_is_not_treated_as_explicitly_safe(monkeypatch):
    clock = iter((0.0, 0.0, 1.0))
    monkeypatch.delenv("YOUTUBE_CONTINUE_WHEN_CHECKS_STUCK", raising=False)
    monkeypatch.setattr(youtube_uploader.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(youtube_uploader, "dismiss_reload_prompt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(youtube_uploader, "save_debug_artifacts", lambda *_args: None)

    with pytest.raises(UploadError, match="Step 3 Checks belum selesai"):
        wait_for_copyright_checks(TextPage("Pemeriksaan selesai."), timeout_ms=100, require_checks=True)


def test_review_blocks_claim_before_publication(monkeypatch):
    monkeypatch.setattr(youtube_uploader, "dismiss_reload_prompt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(youtube_uploader, "get_upload_workflow_step", lambda _page: "REVIEW")
    monkeypatch.setattr(youtube_uploader, "visibility_is_selected", lambda *_args: True)
    monkeypatch.setattr(youtube_uploader, "final_action_button_is_ready", lambda *_args: True)
    monkeypatch.setattr(youtube_uploader, "save_debug_artifacts", lambda *_args: None)

    with pytest.raises(UploadError, match="tidak dipublikasikan"):
        wait_for_review_checks_safe_before_publish(
            TextPage("Konten yang diklaim ditemukan di video ini"),
            100,
        )


def test_claim_detector_accepts_common_english_content_id_copy():
    assert copyright_issue_detected("Copyright-protected content found during checks")
    assert copyright_issue_detected("This video has a Content ID claim")
    assert not copyright_issue_detected("Copyright: No issues found")


def test_uploader_forces_public_request_to_private_by_default(monkeypatch):
    monkeypatch.delenv("YOUTUBE_ALLOW_PUBLIC_AUTO_UPLOAD", raising=False)
    assert safe_upload_visibility("public") == "private"
    assert safe_upload_visibility("unlisted") == "unlisted"

    monkeypatch.setenv("YOUTUBE_ALLOW_PUBLIC_AUTO_UPLOAD", "true")
    assert safe_upload_visibility("public") == "public"


def test_custom_thumbnail_is_only_uploaded_for_long_form(tmp_path):
    short = tmp_path / "clip_01.mp4"
    highlight = tmp_path / "highlight_5menit_hikmah.mp4"
    resume = tmp_path / "resume_cerita_5menit_hikmah.mp4"

    assert not should_upload_custom_thumbnail(short, "shorts")
    assert should_upload_custom_thumbnail(highlight, "long-form")
    assert not should_upload_custom_thumbnail(short, "auto")
    assert should_upload_custom_thumbnail(highlight, "auto")
    assert should_upload_custom_thumbnail(resume, "auto")


def test_thumbnail_file_is_submitted_once_while_studio_finishes_transfer(monkeypatch, tmp_path):
    thumbnail = tmp_path / "resume_cerita_thumb.jpg"
    thumbnail.write_bytes(b"thumbnail")
    page = ThumbnailUploadPage()
    logs = []
    monkeypatch.setattr(youtube_uploader, "validate_thumbnail_file", lambda _path: (1280, 720))
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(youtube_uploader, "log", logs.append)

    set_thumbnail(page, thumbnail, timeout_ms=5000)

    assert page.set_input_calls == [str(thumbnail)]
    assert any(message.startswith("THUMBNAIL_ATTACHED:") for message in logs)


def test_review_safe_text_does_not_trigger_false_issue(monkeypatch):
    monkeypatch.setattr(youtube_uploader, "dismiss_reload_prompt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(youtube_uploader, "get_upload_workflow_step", lambda _page: "REVIEW")
    monkeypatch.setattr(youtube_uploader, "visibility_is_selected", lambda *_args: True)
    monkeypatch.setattr(youtube_uploader, "final_action_button_is_ready", lambda *_args: True)

    wait_for_review_checks_safe_before_publish(TextPage("Pemeriksaan selesai. Tidak ditemukan masalah."), 100)


def test_final_confirmation_ignores_published_text_behind_open_dialog(monkeypatch):
    clock = iter((0.0, 0.0, 1.0))
    monkeypatch.setattr(youtube_uploader.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(youtube_uploader, "dismiss_reload_prompt", lambda *_args, **_kwargs: None)

    with pytest.raises(UploadError, match="belum terkonfirmasi selesai"):
        wait_for_final_upload_confirmation(PendingPublishPage(), timeout_ms=100)


def test_reload_runs_once_after_ten_second_publish_delay(monkeypatch):
    delays = []
    page = ReloadPage()
    monkeypatch.setenv("YOUTUBE_RELOAD_AFTER_PUBLISH", "true")
    monkeypatch.setenv("YOUTUBE_RELOAD_AFTER_PUBLISH_DELAY_SECONDS", "10")
    monkeypatch.setattr(youtube_uploader.time, "sleep", delays.append)

    reload_after_publish(page)

    assert delays == [10]
    assert page.reload_calls == [{"wait_until": "domcontentloaded", "timeout": 30000}]


def test_owned_upload_tab_is_marked_and_force_closed_even_when_setting_is_disabled(monkeypatch):
    page = BrowserPage("https://studio.youtube.com/channel/target")
    monkeypatch.setenv("YOUTUBE_CLOSE_UPLOAD_TAB", "false")

    mark_fendy_clipper_upload_tab(page)
    close_upload_tab(page, force=True)

    assert page.window_name == FENDY_CLIPPER_UPLOAD_PAGE_NAME
    assert page.closed is True


def test_idle_cleanup_only_closes_marked_fendy_clipper_tabs():
    idle_upload = BrowserPage(window_name=FENDY_CLIPPER_UPLOAD_PAGE_NAME)
    user_tab = BrowserPage("https://studio.youtube.com/channel/target")

    closed = close_idle_fendy_clipper_upload_tabs([idle_upload, user_tab])

    assert closed == 1
    assert idle_upload.closed is True
    assert user_tab.closed is False


def test_duplicate_cleanup_preserves_primary_and_unrelated_tabs():
    primary = BrowserPage("https://studio.youtube.com/channel/target")
    duplicate = BrowserPage("https://studio.youtube.com/channel/target/videos")
    other_channel = BrowserPage("https://studio.youtube.com/channel/other")
    unrelated = BrowserPage("https://www.youtube.com/watch?v=demo")

    closed = close_duplicate_target_studio_tabs(
        [primary, duplicate, other_channel, unrelated],
        primary,
        "target",
    )

    assert closed == 1
    assert primary.closed is False
    assert duplicate.closed is True
    assert other_channel.closed is False
    assert unrelated.closed is False


def test_final_action_requires_visibility_step(monkeypatch):
    monkeypatch.setattr(youtube_uploader, "get_upload_workflow_step", lambda _page: "CHECKS")
    monkeypatch.setattr(youtube_uploader, "save_debug_artifacts", lambda *_args: None)

    with pytest.raises(UploadError, match="step Visibilitas benar-benar aktif"):
        click_final_upload_action(object(), "public")


def test_final_action_requires_selected_visibility(monkeypatch):
    monkeypatch.setattr(youtube_uploader, "get_upload_workflow_step", lambda _page: "REVIEW")
    monkeypatch.setattr(youtube_uploader, "visibility_is_selected", lambda *_args: False)
    monkeypatch.setattr(youtube_uploader, "save_debug_artifacts", lambda *_args: None)

    with pytest.raises(UploadError, match="belum benar-benar tercentang"):
        click_final_upload_action(object(), "public")


def test_final_action_rechecks_claim_notice_immediately_before_click(monkeypatch):
    monkeypatch.setattr(youtube_uploader, "get_upload_workflow_step", lambda _page: "REVIEW")
    monkeypatch.setattr(youtube_uploader, "visibility_is_selected", lambda *_args: True)
    monkeypatch.setattr(youtube_uploader, "save_debug_artifacts", lambda *_args: None)

    with pytest.raises(UploadError, match="tepat sebelum aksi final"):
        click_final_upload_action(
            TextPage("Konten yang diklaim ditemukan di video ini"),
            "public",
        )


def test_claimed_upload_is_finalized_as_private(monkeypatch):
    page = object()
    calls = []
    logs = []
    monkeypatch.setattr(youtube_uploader, "get_upload_workflow_step", lambda _page: "CHECKS")
    monkeypatch.setattr(
        youtube_uploader,
        "click_next_upload_step",
        lambda *_args, **kwargs: calls.append(("next", kwargs["expected_step"])),
    )
    monkeypatch.setattr(youtube_uploader, "wait_for_visibility_step", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        youtube_uploader,
        "set_visibility",
        lambda _page, visibility: calls.append(("visibility", visibility)),
    )
    monkeypatch.setattr(youtube_uploader, "visibility_is_selected", lambda *_args: True)
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        youtube_uploader,
        "extract_video_url",
        lambda _page: "https://www.youtube.com/watch?v=abcDEF12345",
    )

    def fake_final_action(_page, visibility, **kwargs):
        calls.append(("final", visibility, kwargs["allow_claimed_private_save"]))

    monkeypatch.setattr(youtube_uploader, "click_final_upload_action", fake_final_action)
    monkeypatch.setattr(youtube_uploader, "reload_after_publish", lambda _page: calls.append(("reload",)))
    monkeypatch.setattr(youtube_uploader, "log", logs.append)

    result = save_claimed_upload_as_private(page, content_type="long-form", media_duration_seconds=300)

    assert result == "https://www.youtube.com/watch?v=abcDEF12345"
    assert calls == [
        ("next", "REVIEW"),
        ("visibility", "private"),
        ("final", "private", True),
        ("reload",),
    ]
    assert "FINAL_VISIBILITY: private" in logs
    assert "PRIVATE_FALLBACK_SAVED: content_id_claim" in logs
