import sys

import pytest

import youtube_uploader
from youtube_uploader import (
    FENDY_CLIPPER_UPLOAD_PAGE_NAME,
    ThumbnailDailyLimitUploadError,
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
    normalize_youtube_video_url,
    open_advanced_upload_settings,
    private_review_check_options,
    reload_after_publish,
    safe_upload_visibility,
    set_altered_content_disclosure,
    set_upload_text_field,
    set_thumbnail,
    should_upload_custom_thumbnail,
    custom_thumbnail_daily_limit_detected,
    validate_thumbnail_file,
    verify_saved_video_in_studio,
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


class StaleUploadDialogsPage(TextPage):
    """Studio page with a hidden stale dialog plus one visible active dialog."""

    def evaluate(self, _script):
        return self.body

    def locator(self, selector):
        if selector == "ytcp-uploads-dialog":
            raise AssertionError("an unindexed multi-dialog locator must not be read")
        return super().locator(selector)


class PendingPublishPage:
    def locator(self, selector):
        if selector == "body":
            return TextPage("Video yang dipublikasikan")
        return TextPage("Visibilitas Publik Publikasikan")


class ClosedUploadStatusPage:
    def __init__(self, bodies):
        self.body = SequenceTextPage(bodies)

    def locator(self, selector):
        if selector == "ytcp-uploads-dialog":
            return type("ClosedDialogLocator", (), {"count": lambda _self: 0})()
        if selector == "body":
            return self.body
        return TextPage("")


class StudioVerificationPage:
    def __init__(self):
        self.goto_calls = []
        self.closed = False
        self.url = ""

    def goto(self, url, **kwargs):
        self.url = url
        self.goto_calls.append((url, kwargs))

    def close(self):
        self.closed = True


class StudioVerificationContext:
    def __init__(self):
        self.page = StudioVerificationPage()

    def new_page(self):
        return self.page


class StudioSourcePage:
    def __init__(self):
        self.context = StudioVerificationContext()
        self.url = "https://studio.youtube.com/channel/test-channel"


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
        return int(
            self.selector
            == 'ytcp-uploads-dialog input[type="file"][accept*="image"]'
        )

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


class MetadataKeyboard:
    def __init__(self, page):
        self.page = page
        self.presses = []
        self.inserted = []

    def press(self, key):
        self.presses.append(key)

    def insert_text(self, value):
        self.inserted.append(value)
        self.page.field_text = value

    def type(self, *_args, **_kwargs):
        raise AssertionError("metadata must not be typed character-by-character")


class MetadataFieldPage:
    def __init__(self):
        self.keyboard = MetadataKeyboard(self)
        self.field_text = ""
        self.scripts = []

    def evaluate(self, script, payload):
        self.scripts.append(script)
        if "target.scrollIntoView" in script:
            return True
        if "expectedText = normalizeText(expected)" in script:
            return self.field_text == payload["expected"]
        raise AssertionError("Unexpected metadata script")


def test_required_checks_do_not_continue_after_timeout_by_default(monkeypatch):
    monkeypatch.delenv("YOUTUBE_CONTINUE_WHEN_CHECKS_STUCK", raising=False)
    monkeypatch.setattr(youtube_uploader, "save_debug_artifacts", lambda *_args: None)

    with pytest.raises(UploadError, match="Step 3 Checks belum selesai"):
        wait_for_copyright_checks(object(), timeout_ms=0, require_checks=True)


def test_next_step_wait_defaults_to_fifteen_minutes(monkeypatch):
    monkeypatch.delenv("YOUTUBE_NEXT_STEP_TIMEOUT_SECONDS", raising=False)

    assert next_upload_step_timeout_ms(5_400_000) == 900_000


def test_long_form_next_step_wait_allows_slow_processing(monkeypatch):
    monkeypatch.delenv("YOUTUBE_LONG_FORM_NEXT_STEP_TIMEOUT_SECONDS", raising=False)

    assert next_upload_step_timeout_ms(5_400_000, "long-form") == 3_600_000


def test_metadata_description_uses_atomic_insert_and_normalized_verification(monkeypatch):
    page = MetadataFieldPage()
    description = "🔥 DUKUNG @RYUUNDYOFFICIAL\n👍 Like jika bermanfaat.\n\n⚠️ CATATAN KONTEN"
    monkeypatch.setattr(youtube_uploader, "log", lambda _message: None)

    set_upload_text_field(
        page,
        description,
        "deskripsi",
        (r"description|deskripsi", r"beri tahu penonton"),
    )

    assert page.keyboard.inserted == [description]
    assert page.keyboard.presses == ["Control+A", "Backspace", "Tab"]
    verification_script = page.scripts[-1]
    assert "normalize('NFKC')" in verification_script
    assert "\\u2066-\\u2069" in verification_script
    assert "normalizeText(text) !== expectedText" in verification_script
    assert "description-textarea" in verification_script
    assert "ytcp-uploads-dialog" in verification_script
    assert "isVisible(surface)" in verification_script


def test_metadata_title_and_description_use_their_exact_active_dialog_ids(monkeypatch):
    page = MetadataFieldPage()
    monkeypatch.setattr(youtube_uploader, "log", lambda _message: None)

    set_upload_text_field(
        page,
        "Judul yang benar #Shorts",
        "judul",
        (r"title|judul",),
        reject_patterns=(r"description|deskripsi",),
    )

    focus_script = page.scripts[0]
    verification_script = page.scripts[-1]
    assert "title-textarea" in focus_script
    assert "description-textarea" in focus_script
    assert "activeDialogs.reverse()" in focus_script
    assert "fieldKind === 'description'" in verification_script
    assert "dialog.querySelector" in verification_script


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


def test_private_review_does_not_wait_for_pending_community_check(monkeypatch):
    logs = []
    monkeypatch.setattr(youtube_uploader, "dismiss_reload_prompt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(youtube_uploader, "log", logs.append)
    page = TextPage("Hak cipta Tidak ditemukan masalah\nPedoman Komunitas Masih memeriksa")

    checks_pending = wait_for_copyright_checks(
        page,
        timeout_ms=100,
        require_checks=True,
        allow_private_review_while_community_pending=True,
    )

    assert checks_pending is True
    assert any("tanpa menahan antrean" in message for message in logs)


def test_private_review_skips_pending_copyright_check(monkeypatch):
    logs = []
    monkeypatch.setattr(youtube_uploader, "dismiss_reload_prompt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(youtube_uploader, "log", logs.append)
    page = TextPage(
        "Hak cipta Masih memeriksa\n"
        "Pedoman Komunitas Tidak ditemukan masalah\n"
        "Perlu waktu lebih lama untuk menyelesaikan pemeriksaan"
    )

    checks_pending = wait_for_copyright_checks(
        page,
        timeout_ms=100,
        require_checks=True,
        skip_pending_checks_for_private_review=True,
    )

    assert checks_pending is True
    assert any("dilanjutkan sekarang" in message for message in logs)


def test_private_review_fast_paths_are_enabled_by_default(monkeypatch):
    monkeypatch.delenv("YOUTUBE_PRIVATE_FAST_CHECKS", raising=False)
    monkeypatch.delenv("YOUTUBE_PRIVATE_SKIP_PENDING_CHECKS", raising=False)

    assert private_review_check_options("private") == (True, True)
    assert private_review_check_options("public") == (False, False)


def test_private_review_fast_paths_can_be_disabled_explicitly(monkeypatch):
    monkeypatch.setenv("YOUTUBE_PRIVATE_FAST_CHECKS", "false")
    monkeypatch.setenv("YOUTUBE_PRIVATE_SKIP_PENDING_CHECKS", "false")

    assert private_review_check_options("private") == (False, False)


def test_private_review_fast_path_never_bypasses_a_copyright_claim(monkeypatch):
    monkeypatch.setattr(youtube_uploader, "dismiss_reload_prompt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(youtube_uploader, "save_debug_artifacts", lambda *_args: None)
    page = TextPage(
        "Hak cipta Konten yang diklaim ditemukan di video ini\n"
        "Pedoman Komunitas Masih memeriksa"
    )

    with pytest.raises(UploadError, match="Content ID"):
        wait_for_copyright_checks(
            page,
            timeout_ms=100,
            require_checks=True,
            allow_private_review_while_community_pending=True,
            skip_pending_checks_for_private_review=True,
        )


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


def test_checks_read_visible_dialog_when_studio_keeps_stale_dialog(monkeypatch):
    monkeypatch.setattr(youtube_uploader, "dismiss_reload_prompt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(youtube_uploader, "save_debug_artifacts", lambda *_args: None)
    page = StaleUploadDialogsPage(
        "Pemeriksaan selesai. Konten yang diklaim ditemukan. "
        "Klaim ini tidak memengaruhi visibilitas atau fitur video Anda."
    )

    with pytest.raises(UploadError, match="Content ID"):
        wait_for_copyright_checks(page, timeout_ms=100, require_checks=True)


def test_checks_reject_exact_two_check_non_blocking_claim_from_studio(monkeypatch):
    monkeypatch.setattr(youtube_uploader, "dismiss_reload_prompt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(youtube_uploader, "save_debug_artifacts", lambda *_args: None)
    page = TextPage(
        "Konten yang dilindungi hak cipta ditemukan di video ini. "
        "Tidak ada dampak pada jangkauan video. Video ini dapat dilihat sesuai dengan setelan Anda. "
        "Tidak ada dampak pada channel. Hal ini bukan teguran hak cipta."
    )

    with pytest.raises(UploadError, match="Content ID"):
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


def test_checks_still_block_claimed_short_over_one_minute(monkeypatch):
    monkeypatch.setattr(youtube_uploader, "dismiss_reload_prompt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(youtube_uploader, "save_debug_artifacts", lambda *_args: None)
    page = TextPage(
        "Konten yang dilindungi hak cipta ditemukan di video ini. "
        "Tidak ada dampak pada jangkauan video. Video ini dapat dilihat sesuai dengan setelan Anda. "
        "Tidak ada dampak pada channel. Hal ini bukan teguran hak cipta."
    )

    with pytest.raises(UploadError, match="Content ID"):
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


def test_previously_non_blocking_claim_never_bypasses_zero_claim_policy():
    compact_body = "This video has a Content ID claim"

    assert copyright_issue_blocks_upload(
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

    with pytest.raises(UploadError, match="tidak masuk channel"):
        wait_for_review_checks_safe_before_publish(
            TextPage("Konten yang diklaim ditemukan di video ini"),
            100,
        )


def test_private_review_rechecks_claim_before_save(monkeypatch):
    selected_visibilities = []
    ready_visibilities = []
    monkeypatch.setattr(youtube_uploader, "dismiss_reload_prompt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(youtube_uploader, "get_upload_workflow_step", lambda _page: "REVIEW")
    monkeypatch.setattr(
        youtube_uploader,
        "visibility_is_selected",
        lambda _page, visibility: selected_visibilities.append(visibility) or True,
    )
    monkeypatch.setattr(
        youtube_uploader,
        "final_action_button_is_ready",
        lambda _page, visibility: ready_visibilities.append(visibility) or True,
    )
    monkeypatch.setattr(youtube_uploader, "save_debug_artifacts", lambda *_args: None)

    with pytest.raises(UploadError, match="tidak masuk channel"):
        wait_for_review_checks_safe_before_publish(
            TextPage(
                "Konten yang dilindungi hak cipta ditemukan di video ini. "
                "Video diblokir secara global."
            ),
            100,
            visibility="private",
        )

    assert selected_visibilities == []
    assert ready_visibilities == []


def test_exact_global_block_claim_copy_is_never_safe():
    body = (
        "Konten yang dilindungi hak cipta ditemukan di video ini. "
        "Video diblokir secara global. Tidak ada dampak pada channel. "
        "Hal ini bukan teguran hak cipta."
    )

    assert copyright_issue_detected(body)
    assert copyright_issue_blocks_upload(body)
    assert not copyright_claim_is_explicitly_non_blocking(body)


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


def test_custom_thumbnail_is_attempted_for_shorts_and_long_form(tmp_path):
    short = tmp_path / "clip_01.mp4"
    highlight = tmp_path / "highlight_5menit_hikmah.mp4"
    resume = tmp_path / "resume_cerita_5menit_hikmah.mp4"

    assert should_upload_custom_thumbnail(short, "shorts")
    assert should_upload_custom_thumbnail(highlight, "long-form")
    assert should_upload_custom_thumbnail(short, "auto")
    assert should_upload_custom_thumbnail(highlight, "auto")
    assert should_upload_custom_thumbnail(resume, "auto")


def test_thumbnail_file_is_submitted_once_while_studio_finishes_transfer(monkeypatch, tmp_path):
    thumbnail = tmp_path / "resume_cerita_thumb.jpg"
    thumbnail.write_bytes(b"thumbnail")
    page = ThumbnailUploadPage()
    logs = []
    monkeypatch.setattr(
        youtube_uploader,
        "validate_thumbnail_file",
        lambda _path, _content_type: (1280, 720),
    )
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(youtube_uploader, "log", logs.append)

    set_thumbnail(page, thumbnail, timeout_ms=5000)

    assert page.set_input_calls == [str(thumbnail)]
    assert any(message.startswith("THUMBNAIL_ATTACHED:") for message in logs)


def test_custom_thumbnail_daily_limit_is_detected_in_indonesian():
    page = TextPage(
        "Batas thumbnail kustom harian tercapai. "
        "Diperlukan waktu hingga 24 jam untuk dapat membuat thumbnail kustom baru."
    )

    assert custom_thumbnail_daily_limit_detected(page) is True


def test_thumbnail_daily_limit_stops_waiting_without_resubmitting(monkeypatch, tmp_path):
    thumbnail = tmp_path / "resume_cerita_thumb.jpg"
    thumbnail.write_bytes(b"thumbnail")
    page = ThumbnailUploadPage()
    monkeypatch.setattr(
        youtube_uploader,
        "validate_thumbnail_file",
        lambda _path, _content_type: (1280, 720),
    )
    monkeypatch.setattr(
        youtube_uploader,
        "custom_thumbnail_daily_limit_detected",
        lambda current_page: current_page.upload_started,
    )
    monkeypatch.setattr(youtube_uploader, "dismiss_custom_thumbnail_daily_limit", lambda _page: None)

    with pytest.raises(ThumbnailDailyLimitUploadError, match="Batas harian thumbnail"):
        set_thumbnail(page, thumbnail, timeout_ms=5000)

    assert page.set_input_calls == [str(thumbnail)]


def test_optional_shorts_thumbnail_skips_when_studio_has_no_upload_control(monkeypatch, tmp_path):
    thumbnail = tmp_path / "clip_01_thumb.jpg"
    thumbnail.write_bytes(b"thumbnail")
    page = ThumbnailUploadPage()
    page.frames = []
    logs = []
    monkeypatch.setattr(
        youtube_uploader,
        "validate_thumbnail_file",
        lambda _path, _content_type: (1080, 1920),
    )
    monkeypatch.setattr(youtube_uploader, "log", logs.append)

    attached = set_thumbnail(
        page,
        thumbnail,
        timeout_ms=0,
        content_type="shorts",
        required=False,
    )

    assert attached is False
    assert any(message.startswith("THUMBNAIL_SKIPPED:") for message in logs)


def test_thumbnail_validation_accepts_portrait_shorts(monkeypatch, tmp_path):
    thumbnail = tmp_path / "clip_01_thumb.jpg"
    thumbnail.write_bytes(b"thumbnail")
    fake_cv2 = type(
        "FakeCv2",
        (),
        {"imread": staticmethod(lambda _path: type("Image", (), {"shape": (1920, 1080, 3)})())},
    )()
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)

    assert validate_thumbnail_file(thumbnail, "shorts") == (1080, 1920)


def test_review_safe_text_does_not_trigger_false_issue(monkeypatch):
    monkeypatch.setattr(youtube_uploader, "dismiss_reload_prompt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(youtube_uploader, "get_upload_workflow_step", lambda _page: "REVIEW")
    monkeypatch.setattr(youtube_uploader, "visibility_is_selected", lambda *_args: True)
    monkeypatch.setattr(youtube_uploader, "final_action_button_is_ready", lambda *_args: True)
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda _seconds: None)

    wait_for_review_checks_safe_before_publish(TextPage("Pemeriksaan selesai. Tidak ditemukan masalah."), 100)


def test_final_confirmation_ignores_published_text_behind_open_dialog(monkeypatch):
    clock = iter((0.0, 0.0, 1.0))
    monkeypatch.setattr(youtube_uploader.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(youtube_uploader, "dismiss_reload_prompt", lambda *_args, **_kwargs: None)

    with pytest.raises(UploadError, match="belum terkonfirmasi selesai"):
        wait_for_final_upload_confirmation(PendingPublishPage(), timeout_ms=100)


def test_final_confirmation_waits_after_modal_closes_while_transfer_is_still_running(monkeypatch):
    clock = iter((0.0, 0.0, 0.1))
    logs = []
    page = ClosedUploadStatusPage(
        [
            "Video lama: Upload selesai. Video saat ini: Mengupload 16%",
            "Upload selesai. Pemrosesan akan segera dimulai",
        ]
    )
    monkeypatch.setattr(youtube_uploader.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(youtube_uploader, "dismiss_reload_prompt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(youtube_uploader, "log", logs.append)

    video_url = wait_for_final_upload_confirmation(
        page,
        timeout_ms=1000,
        video_url="https://www.youtube.com/watch?v=abcDEF12345",
    )

    assert video_url == "https://www.youtube.com/watch?v=abcDEF12345"
    assert any("16%" in message for message in logs)
    assert logs[-1] == "Konfirmasi final upload terdeteksi."


def test_final_confirmation_extends_timeout_while_large_file_progress_moves(monkeypatch):
    clock = iter((0.0, 0.0, 0.09, 0.11))
    page = ClosedUploadStatusPage(
        [
            "Mengupload 16%",
            "Mengupload 17%",
            "Upload selesai",
        ]
    )
    monkeypatch.setattr(youtube_uploader.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(youtube_uploader, "dismiss_reload_prompt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(youtube_uploader, "log", lambda _message: None)

    assert wait_for_final_upload_confirmation(
        page,
        timeout_ms=100,
        video_url="https://www.youtube.com/watch?v=abcDEF12345",
    )


def test_final_confirmation_recovers_from_exact_private_content_row(monkeypatch):
    page = ClosedUploadStatusPage([""])
    logs = []
    monkeypatch.setattr(youtube_uploader.time, "monotonic", lambda: 0.0)
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(youtube_uploader, "dismiss_reload_prompt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(youtube_uploader, "log", logs.append)
    monkeypatch.setattr(
        youtube_uploader,
        "verify_saved_video_in_studio",
        lambda *_args, **_kwargs: "https://www.youtube.com/watch?v=abcDEF12345",
    )

    assert wait_for_final_upload_confirmation(
        page,
        timeout_ms=1000,
        expected_title="Video baru #Shorts",
        visibility="private",
    ) == "https://www.youtube.com/watch?v=abcDEF12345"
    assert "halaman Content" in logs[-1]


def test_final_confirmation_passes_assigned_video_url_to_studio_verification(monkeypatch):
    page = ClosedUploadStatusPage([""])
    calls = []
    monkeypatch.setattr(youtube_uploader.time, "monotonic", lambda: 0.0)
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(youtube_uploader, "dismiss_reload_prompt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(youtube_uploader, "log", lambda _message: None)

    def verify(*_args, **kwargs):
        calls.append(kwargs)
        return kwargs["video_url"]

    monkeypatch.setattr(youtube_uploader, "verify_saved_video_in_studio", verify)

    video_url = "https://www.youtube.com/watch?v=abcDEF12345"
    assert wait_for_final_upload_confirmation(
        page,
        timeout_ms=1000,
        video_url=video_url,
        expected_title="Video baru #Shorts",
        visibility="private",
    ) == video_url
    assert calls == [{"video_url": video_url, "timeout_ms": 1000}]


def test_studio_verification_uses_exact_video_edit_page_before_content_list(monkeypatch):
    source_page = StudioSourcePage()
    video_url = "https://www.youtube.com/watch?v=abcDEF12345"
    monkeypatch.setattr(youtube_uploader, "install_browser_dialog_guard", lambda _page: None)
    monkeypatch.setattr(
        youtube_uploader,
        "saved_video_edit_snapshot",
        lambda *_args, **_kwargs: {
            "titleOk": "True",
            "visibilityOk": "True",
            "uploadFailed": "False",
            "uploading": "False",
        },
    )

    assert verify_saved_video_in_studio(
        source_page,
        "Video baru #Shorts",
        "private",
        video_url=video_url,
        timeout_ms=1000,
    ) == video_url
    assert source_page.context.page.goto_calls[0][0] == (
        "https://studio.youtube.com/video/abcDEF12345/edit"
    )
    assert source_page.context.page.closed is True


def test_studio_verification_rechecks_browser_compatibility_on_new_tab(monkeypatch):
    source_page = StudioSourcePage()
    compatibility_pages = []
    video_url = "https://www.youtube.com/watch?v=abcDEF12345"
    monkeypatch.setattr(youtube_uploader, "install_browser_dialog_guard", lambda _page: None)
    monkeypatch.setattr(
        youtube_uploader,
        "ensure_supported_studio_browser",
        compatibility_pages.append,
    )
    monkeypatch.setattr(youtube_uploader, "ensure_studio_page_healthy", lambda _page: None)
    monkeypatch.setattr(
        youtube_uploader,
        "saved_video_edit_snapshot",
        lambda *_args, **_kwargs: {
            "titleOk": "True",
            "visibilityOk": "True",
            "uploadFailed": "False",
            "uploading": "False",
        },
    )

    assert verify_saved_video_in_studio(
        source_page,
        "Video baru #Shorts",
        "private",
        video_url=video_url,
        timeout_ms=1000,
    ) == video_url
    assert compatibility_pages == [source_page.context.page]


def test_studio_verification_searches_shorts_content_tab_first(monkeypatch):
    source_page = StudioSourcePage()
    monkeypatch.setattr(youtube_uploader.time, "monotonic", lambda: 0.0)
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(youtube_uploader, "install_browser_dialog_guard", lambda _page: None)
    monkeypatch.setattr(youtube_uploader, "ensure_supported_studio_browser", lambda _page: None)
    monkeypatch.setattr(youtube_uploader, "ensure_studio_page_healthy", lambda _page: None)

    def row_snapshot(page, *_args, **_kwargs):
        if page.url.endswith("/videos/short"):
            return {
                "href": "https://studio.youtube.com/video/abcDEF12345/edit",
                "visibilityOk": "True",
                "uploadFailed": "False",
                "uploading": "False",
            }
        return {}

    monkeypatch.setattr(youtube_uploader, "saved_video_row_snapshot", row_snapshot)

    assert verify_saved_video_in_studio(
        source_page,
        "Video baru #Shorts",
        "private",
        timeout_ms=3000,
    ) == "https://www.youtube.com/watch?v=abcDEF12345"
    assert source_page.context.page.goto_calls[0][0].endswith("/videos/short")


def test_normalize_youtube_video_url_accepts_studio_edit_link():
    assert normalize_youtube_video_url(
        "https://studio.youtube.com/video/abcDEF12345/edit"
    ) == "https://www.youtube.com/watch?v=abcDEF12345"


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
