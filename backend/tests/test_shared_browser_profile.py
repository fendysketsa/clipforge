from types import SimpleNamespace

import pytest

import api
import youtube_uploader


@pytest.fixture
def shared(monkeypatch):
    monkeypatch.setenv("SOCIAL_BROWSER_SHARED", "true")
    monkeypatch.setattr(api, "YOUTUBE_CDP_URL", "http://127.0.0.1:9333")
    monkeypatch.setattr(api, "TIKTOK_CDP_URL", "http://127.0.0.1:9444")
    monkeypatch.setenv("YOUTUBE_UPLOAD_USE_CDP", "false")
    monkeypatch.setenv("YOUTUBE_ALLOW_CHROMIUM_PROFILE_UPLOAD", "true")
    monkeypatch.setenv("YOUTUBE_UPLOAD_STORAGE_STATE_FIRST", "true")


def test_shared_mode_handles_two_forwarding_ports(shared):
    assert api.social_browser_is_shared()
    assert api.youtube_upload_prefers_cdp()
    assert not api.youtube_profile_upload_allowed()
    assert not api.youtube_upload_storage_state_first()


@pytest.mark.parametrize("profile", [False, True])
def test_shared_login_and_check_attach_without_opening_profile(shared, profile):
    login = api.build_youtube_login_command()
    check = api.build_youtube_check_login_command(use_chromium_profile=profile)
    for command in [login, check]:
        assert command[2] == "capture-session"
        assert "--no-hydrate-storage-state" in command
        assert "--chromium-user-data-dir" not in command
        assert command[command.index("--cdp-url") + 1] == "http://127.0.0.1:9333"


def test_nonshared_mode_keeps_operator_selected_upload_mode(monkeypatch):
    monkeypatch.setenv("SOCIAL_BROWSER_SHARED", "false")
    monkeypatch.setenv("YOUTUBE_UPLOAD_USE_CDP", "false")
    monkeypatch.setenv("YOUTUBE_ALLOW_CHROMIUM_PROFILE_UPLOAD", "true")
    monkeypatch.setenv("YOUTUBE_UPLOAD_STORAGE_STATE_FIRST", "true")
    assert not api.youtube_upload_prefers_cdp()
    assert api.youtube_profile_upload_allowed()
    assert api.youtube_upload_storage_state_first()
    assert api.build_youtube_login_command()[2] == "login"


def test_repeated_login_click_before_popen_does_not_spawn_another_helper(shared, monkeypatch):
    status = api.YouTubeLoginStatus(active=True)
    monkeypatch.setattr(api, "youtube_login_status", status)
    monkeypatch.setattr(api, "youtube_login_process", None)
    monkeypatch.setattr(api.threading, "Thread", lambda **_: pytest.fail("Second helper was spawned"))
    assert api.start_youtube_login_if_needed() is status


def test_raw_cli_rejects_shared_persistent_profile_before_launch(shared):
    with pytest.raises(youtube_uploader.UploadError, match="Chrome CDP"):
        youtube_uploader.require_dedicated_profile_mode()


def test_shared_reconnect_does_not_restart_the_healthy_desktop_browser(shared, monkeypatch):
    process = SimpleNamespace(stdout=iter(["TARGET_ACCOUNT_CONFIRMED: ryuundyofficial\n"]), wait=lambda: 0)
    monkeypatch.setattr(api, "youtube_login_process", None)
    monkeypatch.setattr(api, "youtube_login_reconnect_cdp", True)
    monkeypatch.setattr(api, "youtube_login_status", api.YouTubeLoginStatus(active=True))
    monkeypatch.setattr(api, "youtube_graphical_process_env", lambda: {})
    monkeypatch.setattr(api.subprocess, "Popen", lambda *_, **__: process)
    monkeypatch.setattr(api, "start_youtube_cdp_refresh_process", lambda **_: pytest.fail("Shared browser restarted"))
    api.run_youtube_login_process()
    assert not api.youtube_login_status.active
    assert api.youtube_login_status.error is None


def test_capture_preserves_live_cookies_by_default():
    assert "--no-hydrate-storage-state" in api.build_youtube_capture_command()


def test_container_launcher_never_starts_shared_profile(tmp_path):
    import os
    from pathlib import Path
    import shutil
    import subprocess

    root = tmp_path / "repo"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    real_scripts = Path(api.__file__).resolve().parent.parent / "scripts"
    for name in ["open-youtube-login-chrome.sh", "load-dotenv.sh"]:
        shutil.copyfile(real_scripts / name, scripts / name)
    (root / ".env").write_text("")
    binaries = tmp_path / "bin"
    binaries.mkdir()
    curl = binaries / "curl"
    curl.write_text("#!/bin/sh\nexit 7\n")
    curl.chmod(0o755)
    profile = tmp_path / "shared-profile"
    env = os.environ.copy()
    env.update(IN_DOCKER="1", SOCIAL_BROWSER_SHARED="true",
               YOUTUBE_LOGIN_PROFILE_DIR=str(profile),
               PATH=str(binaries) + os.pathsep + env.get("PATH", ""))
    result = subprocess.run(["bash", str(scripts / "open-youtube-login-chrome.sh")],
                            env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 75
    assert "desktop service" in result.stderr
    assert not profile.exists()
