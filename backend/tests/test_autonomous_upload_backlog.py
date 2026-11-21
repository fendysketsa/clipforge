"""Prompt local disposition without claiming an unknown remote publication."""
from datetime import datetime, timezone

import pytest

import api
import upload_attention as policy
import upload_attention_remote as remote
from upload_attention_runtime import AttentionService

NOW = datetime(2026, 11, 21, tzinfo=timezone.utc).timestamp()
VIDEO = 'https://www.youtube.com/watch?v=AbCdEfGh123'


def upload(**changes):
    values = dict(id='one', source_job_id='source', clip_url='/outputs/source/clip.mp4', clip_name='clip.mp4',
                  title='Original title', description='Original description', target_channel='ryuundyofficial',
                  status='failed', created_at='2026-10-01T00:00:00Z', updated_at='2026-11-20T00:00:00Z',
                  logs=['Video dipilih: clip.mp4'])
    return api.YouTubeUploadJob(**{**values, **changes})


def ledger(row, **changes):
    return dict(revision=policy.evidence_revision(row.model_dump()), state='waiting', attempts=4,
                checked_at=NOW - 60, next_check_at=NOW + 21600,
                message='Posting dengan metadata yang unik belum ditemukan; pemeriksaan diulang otomatis.', **changes)


def archive(row, state=None, **options):
    return policy.unknown_archive_evidence('youtube', row.model_dump(), state or ledger(row),
                                          media_exists=options.get('media_exists', False), now=NOW)


@pytest.fixture
def service(monkeypatch, tmp_path):
    monkeypatch.setenv('UPLOAD_ATTENTION_AUTOMATIC_ENABLED', 'true')
    monkeypatch.setenv('YOUTUBE_TARGET_CHANNEL_ID', api.DEFAULT_YOUTUBE_TARGET_CHANNEL_ID)
    monkeypatch.setattr(api, 'YOUTUBE_UPLOADS_PATH', tmp_path / 'youtube.json')
    monkeypatch.setattr(api, 'youtube_uploads', {})
    monkeypatch.setattr(api, 'tiktok_uploads', {})
    monkeypatch.setattr(api, 'save_youtube_uploads_unlocked', lambda: None)
    monkeypatch.setattr(api, 'save_tiktok_uploads_unlocked', lambda: None)
    monkeypatch.setattr(api, 'output_path_from_url', lambda _: None)
    monkeypatch.setattr(api, 'process_autonomous_history_once', lambda: 0, raising=False)
    monkeypatch.setattr(api, 'social_upload_waiting_turns', [])
    return AttentionService(api)


def test_missing_media_exhausted_unknown_becomes_local_archive_and_ignores_old_browser_backoff():
    row = upload()
    state = ledger(row)
    proof = archive(row, state)
    assert proof['decision'] == 'ARCHIVE_UNKNOWN' and proof['attempts'] == 4
    assert proof['upload_allowed'] is False and proof['remote_deleted'] is False
    item = policy.decision('youtube', row.model_dump(), [], media_exists=False, saved=state, now=NOW)
    assert item['action'] == 'archive_unknown' and not item['urgent']
    assert policy.status(item, state, NOW)['next_check_at'] == NOW


@pytest.mark.parametrize('guard', ['file', 'new', 'active', 'verified', 'few', 'login_error',
                                  'checking', 'revision', 'future_check', 'archived'])
def test_archive_requires_completed_current_bounded_evidence(guard):
    row = upload(); state = ledger(row); media = False
    if guard == 'file': media = True
    elif guard == 'new': row.created_at = '2026-11-20T23:59:00Z'
    elif guard == 'active': row.status = 'running'
    elif guard == 'verified': row.status = 'completed'; row.upload_confirmed = True; row.video_url = VIDEO
    elif guard == 'few': state['attempts'] = 2
    elif guard == 'login_error': state.update(message='Studio belum siap.', error_type='AuthenticationError')
    elif guard == 'checking': state['state'] = 'checking'
    elif guard == 'revision': state['revision'] = 'old'
    elif guard == 'future_check': state['checked_at'] = NOW + 20
    elif guard == 'archived': row = row.model_copy(update={'attention_archived_at': '2026-11-21T00:00:00Z'})
    assert archive(row, state, media_exists=media) is None


def test_known_id_receives_new_exact_filename_reader_before_archival():
    row = upload(video_url=VIDEO)
    state = ledger(row)
    assert archive(row, state) is None
    item = policy.decision('youtube', row.model_dump(), [], media_exists=False, saved=state, now=NOW)
    assert item['action'] == 'verify_remote'
    assert policy.status(item, state, NOW)['next_check_at'] == NOW
    state.update(reader_version=policy.READER_VERSION, verification_version=policy.READER_VERSION)
    assert archive(row, state)


def test_exhausted_missing_media_finishes_after_short_settlement_window_not_another_day():
    row=upload(created_at=datetime.fromtimestamp(NOW-policy.MIN_UNKNOWN_AGE_SECONDS-1,timezone.utc).isoformat())
    assert archive(row) is not None
    row.created_at=datetime.fromtimestamp(NOW-policy.MIN_UNKNOWN_AGE_SECONDS+1,timezone.utc).isoformat()
    assert archive(row) is None


def test_new_reader_network_failures_never_count_as_completed_unknown_observations(service, monkeypatch):
    row = upload(); api.youtube_uploads[row.id] = row
    service.store.update('youtube-one', revision=policy.evidence_revision(row.model_dump()), state='waiting',
        attempts=2, checked_at=NOW - 60, next_check_at=0, unknown_observations=0,
        message='Studio belum siap.', error_type='ConnectionError')
    monkeypatch.setattr(service, 'observe', lambda *_: {'confirmed':False,
        'message':'Posting dengan metadata yang unik belum ditemukan; pemeriksaan diulang otomatis.'})
    assert service.run_once() == 0
    saved = service.store.read()['items']['youtube-one']
    assert saved['attempts'] == 3 and saved['unknown_observations'] == 1
    assert archive(row, saved) is None


def test_legacy_completed_tiktok_profile_is_not_a_verified_post_and_can_close_locally():
    row = dict(id='tt', status='completed', upload_confirmed=True, dry_run=False,
        created_at='2026-10-01T00:00:00Z', profile_url='https://www.tiktok.com/@target',
        submission_started=True, submission_accepted=True)
    state = dict(revision=policy.evidence_revision(row), state='waiting', attempts=4, checked_at=NOW - 60,
        message='Posting dengan caption lengkap dan identitas unik belum terbukti; tidak ada Post ulang.')
    proof = policy.unknown_archive_evidence('tiktok', row, state, media_exists=False, now=NOW)
    assert proof and proof['decision'] == 'ARCHIVE_UNKNOWN'
    assert row['upload_confirmed'] is True  # Original historical evidence remains untouched.


def test_revision_is_compatible_with_legacy_rows_until_they_are_archived():
    row = upload().model_dump()
    original = policy.evidence_revision(row)
    row.update(attention_archived_at=None, attention_disposition='', attention_archive_reason='')
    assert policy.evidence_revision(row) == original
    row['attention_archived_at'] = '2026-11-21T00:00:00Z'
    assert policy.evidence_revision(row) != original
    assert policy.decision('youtube', row, [], media_exists=False) is None


def test_local_archive_finishes_during_unrelated_active_upload_and_busy_browser(service, monkeypatch):
    row = upload(); api.youtube_uploads[row.id] = row
    api.youtube_uploads['busy'] = upload(id='busy', status='running', clip_url='/outputs/busy.mp4')
    service.store.update('youtube-one', **ledger(row))
    calls = []
    monkeypatch.setattr(api, 'archive_unresolved_upload_record', lambda *args: calls.append(args) or True, raising=False)
    monkeypatch.setattr(service, 'observe', lambda *_: pytest.fail('Local archive must not use browser'))
    api.social_upload_execution_lock.acquire()
    try:
        assert service.run_once() == 1
    finally:
        api.social_upload_execution_lock.release()
    assert calls[0][:3] == ('youtube', row.id, policy.evidence_revision(row.model_dump()))
    assert calls[0][3]['upload_allowed'] is False


def test_duplicate_reconciliation_does_not_wait_for_an_unrelated_active_upload(service):
    source = upload(); api.youtube_uploads[source.id] = source
    api.youtube_uploads['done'] = upload(id='done', status='completed', upload_confirmed=True, video_url=VIDEO)
    api.youtube_uploads['busy'] = upload(id='busy', status='running', clip_url='/outputs/busy.mp4')
    assert service.run_once() == 1
    assert api.youtube_uploads[source.id].upload_confirmed
    assert api.youtube_uploads['busy'].status == 'running'


def test_history_failure_does_not_prevent_local_upload_disposition(service, monkeypatch):
    row = upload(); api.youtube_uploads[row.id] = row
    service.store.update('youtube-one', **ledger(row))
    def fail(): raise OSError('temporary history ledger failure')
    monkeypatch.setattr(api, 'process_autonomous_history_once', fail)
    monkeypatch.setattr(api, 'archive_unresolved_upload_record', lambda *_: True, raising=False)
    assert service.run_once() == 1


def test_changed_or_archived_row_rejects_late_reader_result(service):
    row = upload(video_url=VIDEO); api.youtube_uploads[row.id] = row
    item = service.snapshot()['items'][0]
    api.youtube_uploads[row.id] = row.model_copy(update={'attention_archived_at': '2026-11-21T00:00:00Z'})
    assert not service.unchanged(api.youtube_uploads[row.id], item)


def exact_proof(row, **changes):
    return dict(confirmed=True, video_url=VIDEO, title='Operator-edited title',
        description_sha256=policy.text_hash('Operator-edited description'),
        target_channel_id=api.DEFAULT_YOUTUBE_TARGET_CHANNEL_ID, visibility='public',
        source='authenticated_studio_exact_video', reader_version=policy.READER_VERSION,
        file_name_matched=True, original_filename=row.clip_name, remote_processing_complete=True, **changes)


def test_metadata_edit_is_verified_only_with_exact_id_filename_channel_and_completed_remote(service):
    row = upload(video_url=VIDEO,clip_name='clip_01_cerita_pembeli_dan_penjual_yang_lengkap.mp4')
    proof = exact_proof(row)
    assert service.proof_matches('youtube', row, proof)
    for field, invalid in [('video_url', 'https://youtu.be/ZyXwVuTs987'), ('original_filename', 'other.mp4'),
                           ('target_channel_id', 'other'), ('remote_processing_complete', False),
                           ('file_name_matched', False), ('reader_version', 1)]:
        assert not service.proof_matches('youtube', row, {**proof, field: invalid})
    assert not service.proof_matches('youtube', row.model_copy(update={'video_url': None}), proof)


def test_known_id_metadata_edit_does_not_erase_a_future_schedule(service):
    row = upload(video_url=VIDEO, publish_at='2099-01-01T00:00:00Z',
        clip_name='clip_01_cerita_pembeli_dan_penjual_yang_lengkap.mp4')
    proof = exact_proof(row); proof['visibility'] = 'private'
    assert not service.proof_matches('youtube', row, proof)


def test_generic_or_colliding_filename_cannot_release_metadata_mismatch(service):
    row=upload(video_url=VIDEO)
    assert not service.proof_matches('youtube',row,exact_proof(row))
    row=row.model_copy(update={'clip_name':'clip_01_cerita_pembeli_dan_penjual_yang_lengkap.mp4'})
    api.youtube_uploads['different']=row.model_copy(update={'id':'different','source_job_id':'other',
        'clip_url':'/outputs/other.mp4','clip_sha256':'different-bytes'})
    assert not service.proof_matches('youtube',row,exact_proof(row))


def test_exact_reader_uses_actual_metadata_and_never_changes_remote_controls(monkeypatch):
    import youtube_uploader as studio
    row = upload(video_url=VIDEO,clip_name='clip_01_cerita_pembeli_dan_penjual_yang_lengkap.mp4')
    class Field:
        def __init__(self, text): self.text = text; self.first = self
        def count(self): return 1
        def wait_for(self, **kwargs): pass
        def inner_text(self, **kwargs): return self.text
    class Page:
        url = 'https://studio.youtube.com/video/AbCdEfGh123/edit'
        def goto(self, *args, **kwargs): pass
        def locator(self, selector):
            return Field('Edited title' if 'title-textarea' in selector else 'Edited description'
                         if 'description-textarea' in selector else 'Publik')
        def get_by_text(self, text, **kwargs): assert text == row.clip_name; return Field(text)
    seen = []
    monkeypatch.setattr(studio, 'ensure_target_identity', lambda *_: None)
    monkeypatch.setattr(studio, 'saved_video_edit_snapshot', lambda page, title, visibility:
        seen.append(title) or {'uploading': 'False', 'uploadFailed': 'False'})
    proof = remote.read_youtube(Page(), row.model_dump(), api.DEFAULT_YOUTUBE_TARGET_CHANNEL_ID)
    assert seen == ['Edited title'] and proof['confirmed']
    assert proof['original_filename'] == row.clip_name and proof['remote_processing_complete']
    assert proof['description_sha256'] == policy.text_hash('Edited description')
