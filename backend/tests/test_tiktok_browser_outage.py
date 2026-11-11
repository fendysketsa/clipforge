"""A missing external browser must not invalidate a reusable TikTok login."""
from types import SimpleNamespace

import pytest

import api
import automatic_retry


@pytest.fixture
def external_browser(monkeypatch, tmp_path):
    monkeypatch.setenv('TIKTOK_AUTOMATIC_RETRY_ENABLED', 'true')
    monkeypatch.setenv('TIKTOK_UPLOAD_USE_CDP', 'true')
    monkeypatch.setenv('TIKTOK_CDP_EXTERNAL_BROWSER', 'true')
    monkeypatch.setattr(api, 'tiktok_cdp_ready', lambda: False)
    monkeypatch.setattr(api, 'tiktok_auth_state_exists', lambda: True)
    monkeypatch.setattr(api, 'playwright_installed', lambda: True)
    monkeypatch.setattr(api, 'quarantine_tiktok_auth_state',
                        lambda: pytest.fail('Browser outage invalidated login'))
    media = tmp_path / 'clip.mp4'
    media.write_bytes(b'validated media')
    monkeypatch.setattr(api, 'output_path_from_url', lambda _: media)
    upload = api.TikTokUploadJob(
        id='browser-outage', source_job_id='source', clip_url='/outputs/clip.mp4',
        clip_name='clip.mp4', status='queued', caption='caption', target_handle='titikbalikislami',
        created_at=api.now_iso(), updated_at=api.now_iso())
    monkeypatch.setattr(api, 'tiktok_uploads', {upload.id: upload})
    monkeypatch.setattr(api, 'save_tiktok_uploads_unlocked', lambda: None)
    monkeypatch.setattr(api, 'upload_media_duration_issue', lambda _: None)
    monkeypatch.setattr(api, 'reusable_tiktok_upload', lambda *_: None)
    return upload


def test_outage_never_launches_isolated_uploader_or_invalidates_login(monkeypatch, external_browser):
    monkeypatch.setattr(api.subprocess, 'Popen',
                        lambda *_a, **_k: pytest.fail('Isolated uploader launched'))
    api.run_tiktok_upload(external_browser.id)
    failed = api.tiktok_uploads[external_browser.id]
    assert failed.status == 'failed'
    assert failed.error == automatic_retry.TIKTOK_BROWSER_UNAVAILABLE
    assert not failed.submission_started and not failed.submission_accepted
    assert failed.auto_retry_reason == 'browser_connection_before_post'
    assert failed.auto_retry_at


def test_session_check_preserves_login_when_external_browser_is_unreachable(monkeypatch, external_browser):
    monkeypatch.setattr(api.subprocess, 'run',
                        lambda *_a, **_k: pytest.fail('Isolated session check launched'))
    status = api.check_tiktok_session()
    assert not status.ok
    assert status.error == automatic_retry.TIKTOK_BROWSER_UNAVAILABLE
    assert 'status login belum dapat diperiksa' in status.message


def test_recovered_browser_reuses_live_session(monkeypatch, external_browser):
    monkeypatch.setattr(api, 'tiktok_cdp_ready', lambda: True)
    monkeypatch.setattr(api, 'tiktok_source_is_cron', lambda _: False)
    command = api.build_tiktok_upload_command(external_browser)
    assert command[command.index('--cdp-url') + 1] == api.TIKTOK_CDP_URL
    monkeypatch.setattr(api.subprocess, 'run', lambda *_a, **_k: SimpleNamespace(
        returncode=0, stdout='TARGET_ACCOUNT_CONFIRMED:@titikbalikislami', stderr=''))
    assert api.check_tiktok_session().ok


def test_connection_loss_after_readiness_does_not_fall_back_to_isolated_browser(monkeypatch, external_browser):
    monkeypatch.setattr(api, 'tiktok_cdp_ready', lambda: True)
    monkeypatch.setattr(api, 'tiktok_source_is_cron', lambda _: False)
    monkeypatch.setattr(api, 'restart_tiktok_login_browser',
                        lambda _: (_ for _ in ()).throw(RuntimeError('Host browser unavailable')))
    commands = []

    def process(command, **_kwargs):
        commands.append(command)
        return SimpleNamespace(stdout=iter([
            'USER_ERROR:BrowserType.connect_over_cdp: ECONNREFUSED']), wait=lambda: 2)

    monkeypatch.setattr(api.subprocess, 'Popen', process)
    api.run_tiktok_upload(external_browser.id)
    assert len(commands) == 1 and '--cdp-url' in commands[0]
    assert api.tiktok_uploads[external_browser.id].error == automatic_retry.TIKTOK_BROWSER_UNAVAILABLE


@pytest.mark.parametrize('evidence', [
    {'started': True}, {'accepted': True},
    {'logs': ['POST_SUBMIT_INTENT: issued']},
    {'logs': ['POST_API_ACCEPTED: accepted']},
    {'logs': ['VIDEO_URL:https://www.tiktok.com/@target/video/123']},
])
def test_outage_never_retries_a_possible_post(evidence):
    logs = evidence.get('logs', [])
    flags = {key: value for key, value in evidence.items() if key != 'logs'}
    assert automatic_retry.tiktok_retry_reason(
        automatic_retry.TIKTOK_BROWSER_UNAVAILABLE, logs, **flags) == ''
