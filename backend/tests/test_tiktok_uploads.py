import json
import re
from types import SimpleNamespace

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
from tiktok_uploader import (
    UploadError,
    _launch_with_retry,
    clean_handle,
    login_and_capture,
    save_session_state,
    upload_video,
)
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
    assert strategy["series_label"] not in caption
    assert "#Shorts" not in caption
    assert "share kalau Muslim" not in caption
    assert len(caption) <= 600


def test_tiktok_caption_removes_template_noise_and_duplicate_ctas():
    strategy = build_tiktok_strategy(
        title="Kalau orang Islam seperti ini",
        hook="Kalau orang Islam seperti ini, apa yang terjadi dengan mereka?",
        text="Jawaban singkat dari kajian.",
        stable_key="caption-cleanup",
    )
    caption = tiktok_caption_from_strategy(
        """Kalau orang Islam seperti ini, apa yang terjadi dengan mereka?

Untuk direnungkan:
Hikmah mana yang paling ngena?

Bagikan pembahasan ini kepada orang yang mungkin membutuhkannya.

#viralindonesia #trendingindonesia #kontenpilihan #KesehatanReligius #Shorts""",
        strategy,
    )

    assert caption.startswith(
        "Apa yang terjadi ketika seorang Muslim berada dalam kondisi seperti ini?"
    )
    assert "Seri:" not in caption
    assert "Untuk direnungkan" not in caption
    assert "Bagikan pembahasan" not in caption
    assert "#viralindonesia" not in caption
    assert "#KesehatanReligius" not in caption
    assert "#MuslimIndonesia" in caption
    assert caption.count("Simpan") == 1
    assert len(re.findall(r"#[\w\d_]+", caption)) <= 5


def test_tiktok_caption_normalizes_the_full_legacy_caption():
    strategy = build_tiktok_strategy(
        title="Kalau orang Islam seperti ini",
        hook="Kalau orang Islam seperti ini, apa yang terjadi dengan mereka?",
        text="Jawaban singkat dari kajian.",
        stable_key="legacy-caption-cleanup",
    )
    strategy["cta"] = (
        "Simpan untuk dipelajari lagi. Tulis pertanyaan lanjutan dengan santun."
    )
    caption = tiktok_caption_from_strategy(
        """Seri: Jawaban Ustadz 30 Detik

Poin penting dari penjelasan ini: Kalau orang islam seperti ini. wah, udah lama

Kalau orang Islam seperti ini, apa yang terjadi dengan mereka?

Untuk direnungkan:
Hikmah mana yang paling ngena?

Bagikan pembahasan ini kepada orang yang mungkin membutuhkannya.

#viralindonesia #trendingindonesia #kontenpilihan #KesehatanReligius

Simpan untuk dipelajari lagi. Tulis pertanyaan lanjutan dengan santun.

#JawabanUstadz #KajianIslam #BelajarIslam #Islam #Dakwah""",
        strategy,
    )

    assert caption == """Apa yang terjadi ketika seorang Muslim berada dalam kondisi seperti ini?

Penjelasan lengkapnya penting agar pertanyaan dan jawaban tidak dipahami di luar konteks.

Simpan video ini sebagai bahan belajar.

#JawabanUstadz #KajianIslam #BelajarIslam #Islam #MuslimIndonesia"""


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


def test_tiktok_gui_login_command_uses_cdp_without_locking_profile(monkeypatch):
    monkeypatch.setattr(api, "tiktok_auth_state_exists", lambda: False)
    monkeypatch.setattr(api, "tiktok_chromium_profile_ready", lambda: True)

    command = api.build_tiktok_base_command(
        force_profile=True,
        cdp_url="http://127.0.0.1:9444",
    )

    assert command[command.index("--cdp-url") + 1] == "http://127.0.0.1:9444"
    assert "--chromium-user-data-dir" not in command


def test_tiktok_cdp_capture_uses_uploader_identity_validation(monkeypatch):
    monkeypatch.setattr(api, "TIKTOK_CDP_URL", "http://127.0.0.1:9444")

    command = api.build_tiktok_cdp_capture_command()

    assert command[:2] == [api.sys.executable, "tiktok_uploader.py"]
    assert command[command.index("--cdp-url") + 1] == "http://127.0.0.1:9444"
    assert command[command.index("--target-handle") + 1] == "titikbalikislami"
    assert command[-3] == "login"
    assert "capture-tiktok-cdp-session.py" not in " ".join(command)


def test_tiktok_cdp_launcher_keeps_chrome_supervised(monkeypatch, tmp_path):
    launcher_log = tmp_path / "launcher.log"
    chrome_log = tmp_path / "chrome.log"
    chrome_log.write_text("DevTools listening\n", encoding="utf-8")
    monkeypatch.setattr(api, "TIKTOK_CDP_REFRESH_LOG", launcher_log)
    monkeypatch.setattr(api, "TIKTOK_CHROME_LOG", chrome_log)
    monkeypatch.setattr(api, "TIKTOK_CDP_URL", "http://127.0.0.1:9444")
    monkeypatch.setattr(api, "YOUTUBE_CDP_URL", "http://127.0.0.1:9333")
    monkeypatch.setattr(api, "tiktok_cdp_process", None)
    monkeypatch.setattr(api, "build_tiktok_cdp_launcher_command", lambda: ["launcher"])
    monkeypatch.setattr(api, "youtube_graphical_process_env", lambda: {"DISPLAY": ":1"})
    readiness = iter([False, True])
    monkeypatch.setattr(api, "tiktok_cdp_ready", lambda: next(readiness))
    calls = []

    class Process:
        def poll(self):
            return None

    def popen(command, **kwargs):
        calls.append((command, kwargs))
        return Process()

    monkeypatch.setattr(api.subprocess, "Popen", popen)
    logs = []

    api.open_tiktok_login_browser(logs)

    assert calls[0][0] == ["launcher"]
    assert calls[0][1]["env"]["TIKTOK_CHROME_BACKGROUND"] == "false"
    assert calls[0][1]["start_new_session"] is True
    assert api.tiktok_cdp_process is not None
    assert any("Chrome GUI TikTok siap" in line for line in logs)


def test_tiktok_upload_prefers_the_live_persistent_cdp_browser(monkeypatch, tmp_path):
    output_root = tmp_path / "outputs"
    video = output_root / "demo" / "clip_01.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"video")
    monkeypatch.setattr(api, "OUTPUTS_DIR", output_root)
    monkeypatch.setattr(api, "TIKTOK_CDP_URL", "http://127.0.0.1:9444")
    monkeypatch.setattr(api, "tiktok_cdp_ready", lambda: True)
    upload = api.TikTokUploadJob(
        id="upload-cdp",
        source_job_id="job-tiktok",
        clip_url="/outputs/demo/clip_01.mp4",
        clip_name=video.name,
        status="queued",
        created_at="2026-09-06T00:00:00+00:00",
        updated_at="2026-09-06T00:00:00+00:00",
        caption="caption",
        target_handle="titikbalikislami",
    )

    command = api.build_tiktok_upload_command(upload)

    assert command[command.index("--cdp-url") + 1] == "http://127.0.0.1:9444"
    assert "--chromium-user-data-dir" not in command


def test_tiktok_session_check_uses_live_cdp_without_saved_state(monkeypatch):
    monkeypatch.setattr(api, "playwright_installed", lambda: True)
    monkeypatch.setattr(api, "tiktok_cdp_ready", lambda: True)
    monkeypatch.setattr(api, "tiktok_auth_state_exists", lambda: False)
    monkeypatch.setattr(api, "TIKTOK_CDP_URL", "http://127.0.0.1:9444")
    monkeypatch.setattr(api, "tiktok_login_status", api.YouTubeLoginStatus(active=False))
    commands = []

    def run(command, **_kwargs):
        commands.append(command)
        return SimpleNamespace(
            returncode=0,
            stdout="TARGET_ACCOUNT_CONFIRMED:@titikbalikislami\nSESSION_SAVED:/tmp/state.json\n",
            stderr="",
        )

    monkeypatch.setattr(api.subprocess, "run", run)

    status = api.check_tiktok_session()

    assert status.ok is True
    assert commands[0][commands[0].index("--cdp-url") + 1] == "http://127.0.0.1:9444"


def test_tiktok_state_requires_a_tiktok_cookie(monkeypatch, tmp_path):
    state = tmp_path / "state.json"
    state.write_text(
        json.dumps({"cookies": [{"name": "sessionid", "domain": ".youtube.com"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(api, "TIKTOK_PLAYWRIGHT_STATE", state)
    assert api.tiktok_auth_state_exists() is False

    state.write_text(
        json.dumps({"cookies": [{"name": "sessionid", "domain": ".tiktok.com", "expires": -1}]}),
        encoding="utf-8",
    )
    assert api.tiktok_auth_state_exists() is True


def test_tiktok_state_rejects_anonymous_and_expired_cookies(monkeypatch, tmp_path):
    state = tmp_path / "state.json"
    monkeypatch.setattr(api, "TIKTOK_PLAYWRIGHT_STATE", state)

    state.write_text(
        json.dumps({"cookies": [{"name": "ttwid", "domain": ".tiktok.com", "expires": -1}]}),
        encoding="utf-8",
    )
    assert api.tiktok_auth_state_exists() is False

    state.write_text(
        json.dumps({"cookies": [{"name": "sessionid", "domain": ".tiktok.com", "expires": 1}]}),
        encoding="utf-8",
    )
    assert api.tiktok_auth_state_exists() is False


def test_rejected_tiktok_state_is_quarantined_and_no_longer_ready(monkeypatch, tmp_path):
    state = tmp_path / "state.json"
    state.write_text(
        json.dumps({"cookies": [{"name": "sessionid", "domain": ".tiktok.com", "expires": -1}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(api, "TIKTOK_PLAYWRIGHT_STATE", state)

    rejected = api.quarantine_tiktok_auth_state()

    assert rejected == tmp_path / "state.json.invalid"
    assert rejected.is_file()
    assert not state.exists()
    assert api.tiktok_auth_state_exists() is False


def test_tiktok_profile_without_saved_auth_is_not_upload_ready(monkeypatch):
    monkeypatch.setattr(api, "playwright_installed", lambda: True)
    monkeypatch.setattr(api, "tiktok_auth_state_exists", lambda: False)
    monkeypatch.setattr(api, "tiktok_chromium_profile_ready", lambda: True)

    config = api.tiktok_config_payload()

    assert config.enabled is False
    assert config.auth_state_exists is False
    assert "Login TikTok" in config.auth_status_message


def test_tiktok_session_state_is_complete_and_atomically_replaced(tmp_path):
    class Context:
        def storage_state(self, **kwargs):
            assert kwargs == {}
            return {
                "cookies": [{"name": "sessionid", "domain": ".tiktok.com"}],
                "origins": [
                    {
                        "origin": "https://www.tiktok.com",
                        "localStorage": [{"name": "user", "value": "active"}],
                    }
                ],
            }

    state = tmp_path / "session.json"
    save_session_state(Context(), state)

    payload = json.loads(state.read_text(encoding="utf-8"))
    assert payload["origins"][0]["localStorage"] == [{"name": "user", "value": "active"}]
    assert list(tmp_path.glob("*.tmp")) == []


def test_tiktok_login_does_not_leave_login_page_for_stale_auth_cookie(monkeypatch, tmp_path):
    class Page:
        url = "https://www.tiktok.com/login"

        def wait_for_timeout(self, _milliseconds):
            pass

    timeline = iter([0.0, 1.0, 1.0, 6.0, 6.0, 6.0, 31.0])
    validation_calls = []
    monkeypatch.setattr("tiktok_uploader.time.monotonic", lambda: next(timeline))
    monkeypatch.setattr("tiktok_uploader.has_authenticated_tiktok_cookie", lambda _context: True)
    monkeypatch.setattr(
        "tiktok_uploader.validate_target_account",
        lambda *_args: validation_calls.append(True),
    )

    with pytest.raises(UploadError, match="Login belum terverifikasi"):
        login_and_capture(
            Page(),
            object(),
            tmp_path / "state.json",
            "titikbalikislami",
            "owner@example.com",
            30,
        )

    assert validation_calls == []
    assert not (tmp_path / "state.json").exists()


def test_tiktok_browser_launch_retries_closed_browser(monkeypatch):
    attempts = 0
    monkeypatch.setenv("TIKTOK_BROWSER_LAUNCH_ATTEMPTS", "3")
    monkeypatch.setattr("tiktok_uploader.time.sleep", lambda _seconds: None)

    def launch():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("BrowserType.launch: Target page, context or browser has been closed")
        return "browser"

    assert _launch_with_retry(launch, "test") == "browser"
    assert attempts == 3


def test_tiktok_cdp_upload_sends_bytes_instead_of_container_path(monkeypatch, tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video-payload")
    selected = []

    class FileInput:
        def wait_for(self, **_kwargs):
            pass

        def set_input_files(self, value, **kwargs):
            selected.append((value, kwargs))

    class Locator:
        first = FileInput()

    class Page:
        url = "https://www.tiktok.com/tiktokstudio/upload"

        def wait_for_timeout(self, _milliseconds):
            pass

        def locator(self, selector):
            assert selector == 'input[type="file"]'
            return Locator()

    monkeypatch.setattr("tiktok_uploader.goto", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("tiktok_uploader.dismiss_upload_overlays", lambda *_args: None)
    monkeypatch.setattr("tiktok_uploader.set_caption", lambda *_args: None)
    monkeypatch.setattr("tiktok_uploader.set_only_you", lambda *_args: None)

    upload_video(
        Page(),
        video,
        "caption",
        True,
        "titikbalikislami",
        remote_browser=True,
    )

    payload, kwargs = selected[0]
    assert payload["name"] == "clip.mp4"
    assert payload["mimeType"] == "video/mp4"
    assert payload["buffer"] == b"video-payload"
    assert kwargs["timeout"] == 300_000


def test_explicit_tiktok_login_refreshes_even_while_saved_session_exists(monkeypatch):
    monkeypatch.setattr(api, "tiktok_login_process", None)
    monkeypatch.setattr(api, "tiktok_login_status", api.YouTubeLoginStatus(active=False))
    monkeypatch.setattr(api, "tiktok_auth_state_exists", lambda: True)

    class Thread:
        def __init__(self, *, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            pass

    monkeypatch.setattr(api.threading, "Thread", Thread)

    status = api.start_tiktok_login_if_needed()

    assert status.active is True
    assert status.error is None
    assert "Membuka TikTok" in status.logs[-1]


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
