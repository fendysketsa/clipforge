import json

import pytest

import api
from api import (
    ClipFile,
    ClipJob,
    ClipJobRequest,
    TikTokUploadRequest,
    build_tiktok_upload_command,
    create_tiktok_upload_record,
    delete_completed_youtube_upload_clip,
    tiktok_caption_for_clip,
)
from tiktok_uploader import clean_handle
from tiktok_strategy import build_tiktok_strategy, tiktok_caption_from_strategy


def make_job(clip: ClipFile) -> ClipJob:
    return ClipJob(
        id="job-tiktok",
        status="completed",
        request=ClipJobRequest(source_file="owned.mp4", confirm_source_rights=True),
        created_at="2026-09-06T00:00:00+00:00",
        updated_at="2026-09-06T00:00:00+00:00",
        clips=[clip],
    )


def test_tiktok_caption_removes_shorts_and_adds_relevant_islamic_tags():
    clip = ClipFile(
        name="clip_01.mp4",
        url="/outputs/demo/clip_01.mp4",
        size_bytes=10,
        title="Nasihat menjaga lisan #Shorts",
        is_correct=True,
    )
    caption = tiktok_caption_for_clip(make_job(clip), clip, 1)

    assert "#Shorts" not in caption
    assert "#Islam" in caption
    assert "#Dakwah" in caption
    assert len(caption) <= 2200


@pytest.mark.parametrize(
    ("title", "hook", "expected_series"),
    [
        ("Bolehkah doa setelah shalat?", "Bagaimana hukumnya?", "jawaban_ustadz_30_detik"),
        ("Kesalahan wudhu yang sering terjadi", "Periksa bagian ini", "kesalahan_ibadah_sehari_hari"),
        ("Makna sabar saat diuji", "Sabar bukan berarti diam", "nasihat_sering_disalahpahami"),
    ],
)
def test_tiktok_strategy_selects_a_stable_content_series(title, hook, expected_series):
    first = build_tiktok_strategy(title=title, hook=hook, text=title, stable_key="clip-01")
    second = build_tiktok_strategy(title=title, hook=hook, text=title, stable_key="clip-01")

    assert first["series_id"] == expected_series
    assert first["experiment_id"] == second["experiment_id"]
    assert first["visual_recipe"] == second["visual_recipe"]
    assert first["measure"] == [
        "views",
        "watched_full_percentage",
        "average_watch_time_seconds",
        "shares",
        "saves",
        "comments",
        "followers_gained",
    ]


def test_tiktok_strategy_caption_keeps_source_copy_and_adds_non_coercive_cta():
    strategy = build_tiktok_strategy(
        title="Makna ikhlas",
        hook="Ikhlas tidak menghapus ikhtiar",
        text="Nasihat tentang ikhlas dan ikhtiar.",
        stable_key="clip-ikhlas",
    )

    caption = tiktok_caption_from_strategy("Penjelasan ringkas dari kajian. #Shorts", strategy)

    assert "Penjelasan ringkas dari kajian." in caption
    assert strategy["series_label"] in caption
    assert "#Shorts" not in caption
    assert "share kalau Muslim" not in caption
    assert len(caption) <= 2200


def test_tiktok_upload_record_is_always_only_you(monkeypatch, tmp_path):
    output_root = tmp_path / "outputs"
    video = output_root / "demo" / "clip_01.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"owned-render")
    clip = ClipFile(
        name=video.name,
        url="/outputs/demo/clip_01.mp4",
        size_bytes=video.stat().st_size,
        title="Hikmah sabar",
        is_correct=True,
    )
    job = make_job(clip)
    monkeypatch.setattr(api, "OUTPUTS_DIR", output_root)
    monkeypatch.setattr(api, "jobs", {job.id: job})
    monkeypatch.setattr(api, "tiktok_uploads", {})
    monkeypatch.setattr(api, "youtube_monetization_preflight_issue", lambda *_args: None)

    upload = create_tiktok_upload_record(job.id, TikTokUploadRequest(clip_url=clip.url))

    assert upload.visibility == "only_you"
    assert upload.target_handle == "titikbalikislami"
    assert upload.upload_confirmed is False
    assert upload.series_label == "Nasihat yang Sering Disalahpahami"
    assert upload.opening_hook
    assert upload.visual_recipe
    assert upload.experiment_id
    assert any("Only you" in line for line in upload.logs)


def test_tiktok_upload_command_keeps_account_guard_before_subcommand(monkeypatch, tmp_path):
    output_root = tmp_path / "outputs"
    video = output_root / "demo" / "clip_01.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"video")
    clip = ClipFile(
        name=video.name,
        url="/outputs/demo/clip_01.mp4",
        size_bytes=5,
        title="Kajian singkat",
        is_correct=True,
    )
    job = make_job(clip)
    monkeypatch.setattr(api, "OUTPUTS_DIR", output_root)
    monkeypatch.setattr(api, "jobs", {job.id: job})
    monkeypatch.setattr(api, "tiktok_uploads", {})
    monkeypatch.setattr(api, "youtube_monetization_preflight_issue", lambda *_args: None)
    monkeypatch.setattr(api, "tiktok_auth_state_exists", lambda: True)
    upload = create_tiktok_upload_record(job.id, TikTokUploadRequest(clip_url=clip.url, dry_run=True))

    command = build_tiktok_upload_command(upload)
    upload_index = command.index("upload")

    assert command[command.index("--target-handle") + 1] == "titikbalikislami"
    assert command.index("--target-handle") < upload_index
    assert command[upload_index + 1] == str(video)
    assert "--dry-run" in command


def test_tiktok_state_requires_a_tiktok_cookie(monkeypatch, tmp_path):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"cookies": [{"domain": ".youtube.com"}]}), encoding="utf-8")
    monkeypatch.setattr(api, "TIKTOK_PLAYWRIGHT_STATE", state)
    assert api.tiktok_auth_state_exists() is False

    state.write_text(json.dumps({"cookies": [{"domain": ".tiktok.com"}]}), encoding="utf-8")
    assert api.tiktok_auth_state_exists() is True


def test_youtube_cleanup_is_blocked_until_same_clip_is_confirmed_on_tiktok(monkeypatch, tmp_path):
    output_root = tmp_path / "outputs"
    video = output_root / "demo" / "clip_01.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"keep-me")
    clip = ClipFile(
        name=video.name,
        url="/outputs/demo/clip_01.mp4",
        size_bytes=video.stat().st_size,
        is_correct=True,
    )
    job = make_job(clip)
    youtube_upload = api.YouTubeUploadJob(
        id="youtube-done",
        source_job_id=job.id,
        clip_url=clip.url,
        clip_name=clip.name,
        status="completed",
        created_at="2026-09-06T00:00:00+00:00",
        updated_at="2026-09-06T00:01:00+00:00",
        title="done",
        video_url="https://youtube.com/watch?v=abc12345678",
        upload_confirmed=True,
    )
    monkeypatch.setattr(api, "OUTPUTS_DIR", output_root)
    monkeypatch.setattr(api, "jobs", {job.id: job})
    monkeypatch.setattr(api, "youtube_uploads", {youtube_upload.id: youtube_upload})
    monkeypatch.setattr(api, "tiktok_uploads", {})

    with pytest.raises(RuntimeError, match="dipertahankan.*TikTok"):
        delete_completed_youtube_upload_clip(youtube_upload.id, steps=("video",))

    assert video.is_file()


@pytest.mark.parametrize(
    ("value", "expected"),
    [("@TitikBalikIslami", "titikbalikislami"), (" titik.balik_1 ", "titik.balik_1")],
)
def test_clean_handle(value, expected):
    assert clean_handle(value) == expected
