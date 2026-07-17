import pytest

import youtube_uploader
from youtube_uploader import UploadError, add_manual_subtitle


def configure_required_subtitle(monkeypatch):
    monkeypatch.setenv("YOUTUBE_ADD_MANUAL_SUBTITLE", "true")
    monkeypatch.setenv("YOUTUBE_MANUAL_SUBTITLE_REQUIRED", "true")
    monkeypatch.setenv("YOUTUBE_MANUAL_SUBTITLE_TEXT", "FCN")
    monkeypatch.setattr(youtube_uploader.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(youtube_uploader, "save_debug_artifacts", lambda *_args: None)
    monkeypatch.setattr(youtube_uploader, "click_add_subtitle", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(youtube_uploader, "click_manual_subtitle_mode", lambda *_args, **_kwargs: True)


def test_required_manual_subtitle_is_filled_and_saved(monkeypatch):
    configure_required_subtitle(monkeypatch)
    monkeypatch.setattr(youtube_uploader, "type_subtitle_text", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(youtube_uploader, "click_subtitle_done", lambda *_args, **_kwargs: True)

    assert add_manual_subtitle(object()) is True


def test_required_manual_subtitle_rejects_unverified_text(monkeypatch):
    configure_required_subtitle(monkeypatch)
    monkeypatch.setattr(youtube_uploader, "type_subtitle_text", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(youtube_uploader, "force_fill_subtitle_textarea", lambda *_args, **_kwargs: False)

    with pytest.raises(UploadError, match="belum berhasil diisi dan diverifikasi"):
        add_manual_subtitle(object())


def test_required_manual_subtitle_uses_verified_force_fill(monkeypatch):
    configure_required_subtitle(monkeypatch)
    filled_text = []
    monkeypatch.setattr(youtube_uploader, "type_subtitle_text", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        youtube_uploader,
        "force_fill_subtitle_textarea",
        lambda _page, text: filled_text.append(text) or True,
    )
    monkeypatch.setattr(youtube_uploader, "click_subtitle_done", lambda *_args, **_kwargs: True)

    assert add_manual_subtitle(object()) is True
    assert filled_text == ["FCN"]


def test_required_manual_subtitle_rejects_missing_done_button(monkeypatch):
    configure_required_subtitle(monkeypatch)
    monkeypatch.setattr(youtube_uploader, "type_subtitle_text", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(youtube_uploader, "click_subtitle_done", lambda *_args, **_kwargs: False)

    with pytest.raises(UploadError, match="Tombol Selesai subtitle tidak ditemukan"):
        add_manual_subtitle(object())
