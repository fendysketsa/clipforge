import sys
import api
import pytest


@pytest.mark.parametrize('outcome', ['confirmed', 'unconfirmed', 'failed', 'claim', 'wrong_id', 'no_saved_session', 'already_attempted', 'legacy_log_marker', 'metadata_field_not_ready', 'empty_metadata', 'filename_title'])
def test_verification_fallback_keeps_exact_id_without_file_selection(monkeypatch, tmp_path, outcome):
    url = 'https://www.youtube.com/watch?v=abcDEF12345'
    upload = api.YouTubeUploadJob(id='verify-existing', source_job_id='job',
        clip_url='/outputs/job/clip_01.mp4', clip_name='clip_01.mp4', status='queued',
        created_at=api.now_iso(), updated_at=api.now_iso(), title='Saved video', video_url=url,
        storage_state_verification_attempted=outcome == 'already_attempted',
        logs=['STORAGE_STATE_VERIFY_ONCE: previous safe retry'] if outcome == 'legacy_log_marker' else [])
    monkeypatch.setattr(api, 'youtube_uploads', {upload.id: upload})
    monkeypatch.setattr(api, 'YOUTUBE_UPLOADS_PATH', tmp_path / 'uploads.json')
    monkeypatch.setattr(api, 'youtube_auth_state_exists', lambda: outcome != 'no_saved_session')
    commands = []
    monkeypatch.setattr(api, 'build_youtube_restart_verification_command', lambda u:
        [sys.executable, 'youtube_uploader.py', 'verify-upload', '--video-url', u.video_url,
         '--state', '/saved-state.json', '--use-cdp', '--cdp-url', 'http://127.0.0.1:9333'])
    def popen(command, **kwargs):
        commands.append(command)
        return object()
    monkeypatch.setattr(api.subprocess, 'Popen', popen)
    attempts = []
    def monitor(process, on_line, **kwargs):
        attempts.append(True)
        if len(attempts) == 1:
            if outcome == 'claim': on_line(api.YOUTUBE_CLAIM_ABORT_PREFIX + ' explicit copyright block')
            messages = {
                'metadata_field_not_ready':'Gagal mengisi judul dengan benar di tab Detail YouTube Studio.',
                'empty_metadata':'Metadata ditahan: deskripsi tersimpan masih kosong; finalisasi tidak dijalankan.',
                'filename_title':'Metadata ditahan: judul kosong atau masih memakai nama file internal clip/klip.',
            }
            on_line('USER_ERROR: ' + messages.get(outcome,'Tombol Berikutnya/Next modal upload tidak ditemukan; dialog-not-found'))
            return 1, False
        assert '--use-cdp' not in commands[-1] and '--cdp-url' not in commands[-1]
        assert commands[-1][commands[-1].index('--video-url') + 1] == url
        assert 'verify-upload' in commands[-1] and 'upload' not in commands[-1]
        assert api.youtube_uploads[upload.id].upload_confirmed is False
        if outcome in {'confirmed', 'wrong_id'}:
            on_line('VIDEO_URL: ' + (url if outcome == 'confirmed' else 'https://www.youtube.com/watch?v=Other123456'))
            on_line('UPLOAD_CONFIRMED: verified same exact video')
        elif outcome == 'failed':
            on_line('USER_ERROR: Saved session still unavailable')
            return 1, False
        return 0, False
    monkeypatch.setattr(api, 'monitor_youtube_upload_process', monitor)
    monkeypatch.setattr(api, 'cross_platform_cleanup_after', lambda *a: None)
    monkeypatch.setattr(api, 'schedule_completed_upload_cleanup', lambda *a: None)
    monkeypatch.setattr(api, 'schedule_claimed_clip_cleanup', lambda *a: None)
    api.run_youtube_restart_verification(upload.id)
    result = api.youtube_uploads[upload.id]
    assert result.video_url == url
    expected_attempts = 1 if outcome in {'claim', 'no_saved_session', 'already_attempted', 'legacy_log_marker', 'empty_metadata', 'filename_title'} else 2
    assert len(commands) == expected_attempts
    if expected_attempts == 2: assert result.storage_state_verification_attempted is True
    assert result.status == ('completed' if outcome == 'confirmed' else 'failed')
    assert result.upload_confirmed is (outcome == 'confirmed')
    if outcome == 'confirmed': assert result.error is None
