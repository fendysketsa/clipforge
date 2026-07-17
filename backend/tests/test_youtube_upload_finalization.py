import pytest

import youtube_uploader
from youtube_uploader import (
    UploadError,
    click_final_upload_action,
    reload_after_publish,
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
