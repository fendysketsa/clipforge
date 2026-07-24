import pytest

import youtube_uploader
from youtube_uploader import (
    UploadError,
    click_final_upload_action,
    copyright_issue_detected,
    next_upload_step_timeout_ms,
    reload_after_publish,
    safe_upload_visibility,
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
