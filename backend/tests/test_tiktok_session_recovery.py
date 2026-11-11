"""Recover the observed false logout without replaying an uncertain Post."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import api
import automatic_retry
import tiktok_uploader as uploader
from test_tiktok_caption_recovery import failed_caption
from test_tiktok_browser_outage import external_browser


LOGOUT = 'Sesi TikTok belum login. Klik Login TikTok lalu lanjutkan dengan Google di Chrome.'
LOGS = ['TARGET_ACCOUNT_CONFIRMED:@titikbalikislami', 'POST_BASELINE_MATCHES:0',
        'Storage-state TikTok ditolak; mencoba ulang memakai Chrome/profile login yang sama.',
        'Recovery Chrome TikTok belum tersedia: Chrome host TikTok tidak aktif.']


@pytest.fixture
def false_logout(failed_caption):
    path, upload, started = failed_caption
    upload.error = LOGOUT
    upload.logs = list(LOGS)
    upload.auto_retry_count = 1
    return path, upload, started


def test_false_logout_needs_fresh_verification_and_reuses_original_record(false_logout):
    _, upload, started = false_logout
    assert api.queue_retryable_tiktok_uploads_once() == 0
    original = (upload.id, upload.caption, upload.visibility, upload.clip_sha256, upload.target_handle)
    assert api.queue_retryable_tiktok_uploads_once(upload_ids={upload.id}, verified_session=True) == 1
    recovered = api.tiktok_uploads[upload.id]
    assert (recovered.id, recovered.caption, recovered.visibility, recovered.clip_sha256, recovered.target_handle) == original
    assert recovered.auto_retry_count == 2
    assert recovered.auto_retry_reason == 'live_session_revalidated_before_post'
    assert len(started) == 1
    assert api.queue_retryable_tiktok_uploads_once(upload_ids={upload.id}, verified_session=True) == 0


@pytest.mark.parametrize('risk', ['started', 'accepted', 'intent', 'url', 'confirmed',
                                  'budget', 'file', 'hash', 'gate', 'sibling', 'account', 'scope', 'actual_logout'])
def test_live_validation_never_overrides_other_guards(false_logout, monkeypatch, risk):
    path, upload, started = false_logout
    if risk == 'started': upload.submission_started = True
    if risk == 'accepted': upload.submission_accepted = True
    if risk == 'intent': upload.logs.append('POST_SUBMIT_INTENT: issued')
    if risk == 'url': upload.profile_url = 'https://www.tiktok.com/@target/video/123'
    if risk == 'confirmed': upload.upload_confirmed = True
    if risk == 'budget': upload.auto_retry_count = 3
    if risk == 'file': path.unlink()
    if risk == 'hash': path.write_bytes(b'changed')
    if risk == 'gate': monkeypatch.setattr(api, 'youtube_monetization_preflight_issue', lambda *_: 'held')
    if risk == 'sibling': api.tiktok_uploads['sibling'] = upload.model_copy(update={'id': 'sibling', 'submission_accepted': True})
    if risk == 'account': upload.target_handle = 'another_account'
    if risk == 'actual_logout': upload.logs = []
    scope = {'other'} if risk == 'scope' else {upload.id}
    assert api.queue_retryable_tiktok_uploads_once(upload_ids=scope, verified_session=True) == 0
    assert not started


def test_recovery_keeps_existing_backoff(false_logout):
    _, upload, started = false_logout
    now = datetime.now(timezone.utc)
    upload.auto_retry_at = (now + timedelta(minutes=5)).isoformat()
    assert api.queue_retryable_tiktok_uploads_once(now, upload_ids={upload.id}, verified_session=True) == 0
    assert not started


def test_explicit_retry_validates_live_session_then_reserves_same_upload(false_logout, monkeypatch):
    _, upload, started = false_logout
    monkeypatch.setattr(api, 'tiktok_login_is_active', lambda: False)
    monkeypatch.setattr(api, 'create_tiktok_upload_record', lambda *_: upload)
    monkeypatch.setattr(api, 'check_tiktok_session', lambda: SimpleNamespace(ok=True))
    result = api.create_tiktok_upload(upload.source_job_id, api.TikTokUploadRequest(clip_url=upload.clip_url))
    assert result.id == upload.id and result.status == 'queued'
    assert result.auto_retry_count == 2
    assert len(api.tiktok_uploads) == 1


def test_failed_live_validation_does_not_revive_record(false_logout, monkeypatch):
    _, upload, _ = false_logout
    monkeypatch.setattr(api, 'tiktok_login_is_active', lambda: False)
    monkeypatch.setattr(api, 'create_tiktok_upload_record', lambda *_: upload)
    monkeypatch.setattr(api, 'check_tiktok_session', lambda: SimpleNamespace(ok=False, error='Account unavailable', message=''))
    with pytest.raises(api.HTTPException, match='Account unavailable'):
        api.create_tiktok_upload(upload.source_job_id, api.TikTokUploadRequest(clip_url=upload.clip_url))
    assert api.tiktok_uploads[upload.id].status == 'failed'
    assert upload.auto_retry_count == 1


def test_session_check_alone_never_queues_media(monkeypatch):
    monkeypatch.setattr(api, 'check_tiktok_session_unlocked', lambda: 'validated')
    monkeypatch.setattr(api, 'queue_retryable_tiktok_uploads_once', lambda **_: pytest.fail('Check uploaded media'))
    assert api.check_tiktok_session() == 'validated'
    assert not api.social_upload_execution_lock.locked()


def test_session_check_never_navigates_while_upload_has_browser(monkeypatch):
    monkeypatch.setattr(api, 'check_tiktok_session_unlocked', lambda: pytest.fail('Concurrent navigation'))
    with api.social_upload_execution_lock:
        result = api.check_tiktok_session()
    assert not result.ok and 'upload' in result.error


def test_check_failure_releases_browser_lock(monkeypatch):
    def fail(): raise RuntimeError('test failure')
    monkeypatch.setattr(api, 'check_tiktok_session_unlocked', fail)
    with pytest.raises(RuntimeError): api.check_tiktok_session()
    assert not api.social_upload_execution_lock.locked()


def test_external_browser_check_never_uses_isolated_fallback(monkeypatch):
    monkeypatch.setenv('TIKTOK_CDP_EXTERNAL_BROWSER', 'true')
    monkeypatch.setenv('TIKTOK_UPLOAD_USE_CDP', 'true')
    monkeypatch.setattr(api, 'playwright_installed', lambda: True)
    monkeypatch.setattr(api, 'tiktok_cdp_ready', lambda: True)
    monkeypatch.setattr(api, 'tiktok_auth_state_exists', lambda: True)
    commands = []
    def check(command, **_):
        commands.append(command)
        return SimpleNamespace(returncode=2, stdout='USER_ERROR:BrowserType.connect_over_cdp: ECONNREFUSED', stderr='')
    monkeypatch.setattr(api.subprocess, 'run', check)
    monkeypatch.setattr(api, 'quarantine_tiktok_auth_state', lambda: pytest.fail('Session discarded'))
    assert not api.check_tiktok_session().ok
    assert len(commands) == 1 and '--cdp-url' in commands[0]


@pytest.mark.parametrize('error,attempts', [
    ('Transfer file CDP TikTok gagal sebelum posting; file belum dikirim.', 1),
    ('Sesi TikTok terdeteksi, tetapi identitas akun belum dapat diverifikasi karena halaman profil belum selesai dimuat.', 3),
    (LOGOUT, 1),
])
def test_upload_recovery_stays_in_external_browser(monkeypatch, external_browser, error, attempts):
    monkeypatch.setattr(api, 'tiktok_cdp_ready', lambda: True)
    monkeypatch.setattr(api, 'tiktok_source_is_cron', lambda _: False)
    monkeypatch.setattr(api.time, 'sleep', lambda _: None)
    monkeypatch.setattr(api, 'quarantine_tiktok_auth_state', lambda: None)
    commands = []
    def process(command, **_):
        commands.append(command)
        return SimpleNamespace(stdout=iter(['USER_ERROR:' + error]), wait=lambda: 2)
    monkeypatch.setattr(api.subprocess, 'Popen', process)
    api.run_tiktok_upload(external_browser.id)
    assert len(commands) == attempts
    assert all('--cdp-url' in command for command in commands)


@pytest.mark.parametrize('failure', [False, True])
def test_check_owns_temporary_tab_and_preserves_existing_upload(monkeypatch, tmp_path, failure):
    events = []
    page = SimpleNamespace(set_default_timeout=lambda _: None, close=lambda: events.append('closed'))
    context = SimpleNamespace(new_page=lambda: page)
    class Manager:
        def __enter__(self): return None
        def __exit__(self, *_): pass
    monkeypatch.setattr(uploader, 'import_playwright', lambda: (Manager, RuntimeError))
    monkeypatch.setattr(uploader, 'open_context', lambda *_: (context, None))
    monkeypatch.setattr(uploader, 'select_tiktok_page', lambda _: pytest.fail('Existing upload tab reused'))
    monkeypatch.setattr(uploader, 'minimize_cdp_browser', lambda *_: pytest.fail('User window minimized'))
    def validate(*_):
        if failure: raise uploader.UploadError('validation failed')
        events.append('validated')
    monkeypatch.setattr(uploader, 'validate_target_account', validate)
    monkeypatch.setattr(uploader, 'save_session_state', lambda *_: events.append('saved'))
    args = SimpleNamespace(command='check-login', cdp_url='http://127.0.0.1:9444',
        target_handle='titikbalikislami', target_email='', state=tmp_path / 'session.json')
    if failure:
        with pytest.raises(uploader.UploadError): uploader.run(args)
    else:
        assert uploader.run(args) == 0
    assert events == (['closed'] if failure else ['validated', 'saved', 'closed'])
