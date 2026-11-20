"""A completed rejection must leave the queue without losing its evidence."""
import json
import stat

import pytest

import api
import upload_attention as policy
from upload_attention_runtime import AttentionService


@pytest.fixture
def rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(api, 'OUTPUTS_DIR', tmp_path / 'outputs')
    monkeypatch.setattr(api, 'job_processes', {})
    monkeypatch.setattr(api, 'youtube_upload_processes', {})
    monkeypatch.setattr(api, 'tiktok_upload_processes', {})
    monkeypatch.setattr(api, 'claimed_clip_cleanup_scheduled', set())
    upload = api.YouTubeUploadJob(id='rejected', source_job_id='source',
        clip_url='/outputs/source/clips/clip.mp4', clip_name='clip.mp4', title='Rejected clip',
        status='failed', created_at=api.now_iso(), updated_at=api.now_iso(),
        clip_sha256='a' * 64, clip_deleted_at=api.now_iso(),
        logs=['CLAIMED_UPLOAD_ABORTED: zero_active_claim_policy', 'CLAIMED_CLIP_DELETED: file removed'])
    api.youtube_uploads[upload.id] = upload
    api.save_youtube_uploads_unlocked()
    return upload


def receipt(upload):
    path = policy.rejection_folder(api.YOUTUBE_UPLOADS_PATH) / (upload.id + '.json')
    return path, json.loads(path.read_text())


def test_already_deleted_claim_is_archived_and_removed_without_touching_siblings(rejected):
    done = rejected.model_copy(update=dict(id='done', clip_url='/outputs/other.mp4', status='completed',
        upload_confirmed=True, video_url='https://www.youtube.com/watch?v=abcdefghijk', logs=[]))
    api.youtube_uploads[done.id] = done
    assert api.delete_claimed_youtube_upload_record(rejected.id)
    assert rejected.id not in api.youtube_uploads and api.youtube_uploads[done.id] is done
    path, audit = receipt(rejected)
    assert audit['decision'] == 'DROP_SOURCE' and audit['local_media_removed']
    assert audit['remote_action'] == 'none' and audit['upload']['id'] == rejected.id
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert api.youtube_clip_claim_block('another-source', '/outputs/other.mp4', 'a' * 64).id == rejected.id
    assert api.youtube_clip_claim_block('another-source', '/outputs/other.mp4', 'b' * 64) is None
    assert not api.delete_claimed_youtube_upload_record(rejected.id)


@pytest.mark.parametrize('guard', ['completed', 'active', 'dry_run', 'unconfirmed_claim',
                                   'file', 'job_clip', 'youtube_process', 'tiktok_active'])
def test_unfinished_or_unproven_work_is_retained(rejected, guard):
    if guard == 'completed':
        rejected.status = 'completed'; rejected.upload_confirmed = True
    elif guard == 'active':
        rejected.status = 'running'
    elif guard == 'dry_run':
        rejected.dry_run = True
    elif guard == 'unconfirmed_claim':
        rejected.logs = ['Tidak ada klaim copyright.']; rejected.error = 'copyright help page'
    elif guard == 'file':
        path = api.output_path_from_url(rejected.clip_url); path.parent.mkdir(parents=True); path.write_bytes(b'keep')
    elif guard == 'job_clip':
        api.jobs['source'] = api.ClipJob(id='source', status='completed', request=api.ClipJobRequest(),
            created_at=api.now_iso(), updated_at=api.now_iso(),
            clips=[api.ClipFile(name='clip.mp4', url=rejected.clip_url, size_bytes=1)])
    elif guard == 'youtube_process':
        api.youtube_upload_processes[rejected.id] = object()
    elif guard == 'tiktok_active':
        api.tiktok_uploads['tt'] = api.TikTokUploadJob(id='tt', source_job_id='other',
            clip_url=rejected.clip_url, clip_name='clip.mp4', status='running', caption='Caption', target_handle='fixture',
            created_at=api.now_iso(), updated_at=api.now_iso())
    assert not api.delete_claimed_youtube_upload_record(rejected.id)
    assert api.youtube_uploads[rejected.id] is rejected


def test_missing_job_does_not_mean_existing_file_was_removed(rejected):
    path = api.output_path_from_url(rejected.clip_url); path.parent.mkdir(parents=True); path.write_bytes(b'keep')
    api.claimed_clip_cleanup_worker(rejected.id)
    assert path.read_bytes() == b'keep' and rejected.id in api.youtube_uploads
    assert 'File yatim' in api.youtube_uploads[rejected.id].clip_delete_error


@pytest.mark.parametrize('failed_write', ['archive', 'queue'])
def test_write_failure_retains_rejected_record(rejected, monkeypatch, failed_write):
    def unavailable(*args, **kwargs):
        raise OSError('disk unavailable')
    monkeypatch.setattr(policy if failed_write == 'archive' else api,
        'archive_rejection' if failed_write == 'archive' else 'save_youtube_uploads_unlocked', unavailable)
    with pytest.raises(OSError):
        api.delete_claimed_youtube_upload_record(rejected.id)
    assert api.youtube_uploads[rejected.id] is rejected


def test_startup_retries_cleanup_even_after_media_deleted_timestamp(rejected, monkeypatch):
    scheduled = []
    for name in ('enable_ready_youtube_cdp_for_automation', 'cleanup_orphan_output_roots',
                 'start_youtube_performance_collector_if_needed', 'start_runtime_data_cleanup_if_needed'):
        monkeypatch.setattr(api, name, lambda: None)
    monkeypatch.setenv('AUTO_UPLOAD_COMPLETED_JOBS', 'false')
    monkeypatch.setattr(api, 'schedule_claimed_clip_cleanup', scheduled.append)
    api.resume_queued_youtube_uploads()
    assert scheduled == [rejected.id]


def test_attention_finishes_rejections_while_unrelated_upload_and_browser_are_busy(rejected, monkeypatch):
    monkeypatch.setenv('UPLOAD_ATTENTION_AUTOMATIC_ENABLED', 'true')
    api.youtube_uploads['busy'] = rejected.model_copy(update=dict(id='busy', status='running',
        clip_url='/outputs/busy.mp4', logs=[]))
    scheduled = []
    monkeypatch.setattr(api, 'schedule_claimed_clip_cleanup', lambda key: scheduled.append(key) or True)
    service = AttentionService(api)
    monkeypatch.setattr(service, 'observe', lambda *_: pytest.fail('No browser for local rejection cleanup'))
    api.social_upload_execution_lock.acquire()
    try:
        snapshot = service.snapshot()
        assert snapshot['terminal_claim_action'] == 'DROP_SOURCE'
        assert snapshot['items'][0]['state'] == 'waiting'
        assert service.run_once() == 1
    finally:
        api.social_upload_execution_lock.release()
    assert scheduled == [rejected.id]
    assert not service.store.path.exists()  # Cleanup does not consume remote retry budget.


def test_archive_removes_credentials_from_downloader_logs(rejected):
    rejected.logs += ['Cookie: SID=secret', 'failed https://user:pass@cdn.test/media?token=signature']
    assert api.delete_claimed_youtube_upload_record(rejected.id)
    path, _ = receipt(rejected)
    text = path.read_text()
    assert 'secret' not in text and 'signature' not in text and 'user:pass' not in text


def test_corrupt_claim_fingerprint_evidence_blocks_instead_of_allowing_upload(rejected):
    assert api.delete_claimed_youtube_upload_record(rejected.id)
    index = policy.rejection_folder(api.YOUTUBE_UPLOADS_PATH) / 'by-sha256' / ('a' * 64 + '.json')
    index.write_text('{')
    with pytest.raises(api.HTTPException) as error:
        api.youtube_clip_claim_block('another', '/outputs/another.mp4', 'a' * 64)
    assert error.value.status_code == 409
