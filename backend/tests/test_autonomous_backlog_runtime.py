"""Integration of bounded local disposition, with real persisted models and no browser."""
from datetime import datetime, timedelta, timezone
import json

import pytest

import api
import upload_attention as policy
from upload_attention_runtime import AttentionService


@pytest.fixture
def runtime(monkeypatch, tmp_path):
    monkeypatch.setenv('UPLOAD_ATTENTION_AUTOMATIC_ENABLED', 'true')
    monkeypatch.setenv('AUTO_UPLOAD_TERMINAL_CLEANUP_ENABLED', 'true')
    monkeypatch.setattr(api, 'OUTPUTS_DIR', tmp_path / 'outputs')
    for key in ('job_processes', 'youtube_upload_processes', 'tiktok_upload_processes'):
        monkeypatch.setattr(api, key, {})
    monkeypatch.setattr(api, 'long_qc_active', set())
    monkeypatch.setattr(api, 'facebook_upload_protected', lambda *args: False)
    service = AttentionService(api)
    monkeypatch.setattr(api, 'upload_attention_service', service)
    return service


def exhausted(platform, service):
    now = datetime.now(timezone.utc)
    common = dict(id='old', source_job_id='missing', clip_url='/outputs/missing/clip.mp4', clip_name='clip.mp4',
        status='failed', created_at=(now-timedelta(days=2)).isoformat(), updated_at=(now-timedelta(days=2)).isoformat(),
        clip_sha256='a'*64)
    if platform == 'youtube':
        row = api.YouTubeUploadJob(**common, title='Original', file_selection_started=True,
                                  logs=['Video dipilih: clip.mp4'])
        api.youtube_uploads[row.id] = row
    else:
        common.update(status='completed')
        row = api.TikTokUploadJob(**common, target_handle='titikbalikislami', caption='Original',
            profile_url='https://www.tiktok.com/@titikbalikislami', upload_confirmed=True, submission_started=True)
        api.tiktok_uploads[row.id] = row
    saved = dict(revision=policy.evidence_revision(row.model_dump()), state='waiting', attempts=4,
        checked_at=now.timestamp()-60, message=policy.UNKNOWN_OBSERVATION_MESSAGES[0])
    service.store.update(platform+'-'+row.id, **saved)
    evidence = policy.unknown_archive_evidence(platform, row.model_dump(), saved, media_exists=False, now=now.timestamp())
    assert evidence
    return row, evidence


@pytest.mark.parametrize('platform', ['youtube', 'tiktok'])
def test_exhausted_record_closes_queue_but_keeps_original_remote_reservation(runtime, platform):
    row, evidence = exhausted(platform, runtime)
    assert api.archive_unresolved_upload_record(platform, row.id, evidence['revision'], evidence)
    records = api.youtube_uploads if platform == 'youtube' else api.tiktok_uploads
    result = records[row.id]
    assert result.attention_archived_at and result.attention_disposition == 'unresolved_remote_archived'
    assert result.status == row.status and result.upload_confirmed == row.upload_confirmed
    assert result.logs == row.logs and result.clip_sha256 == row.clip_sha256
    assert (result.video_url == row.video_url if platform == 'youtube' else result.profile_url == row.profile_url)
    full = api.list_youtube_uploads() if platform == 'youtube' else api.list_tiktok_uploads()
    dashboard = api.list_youtube_uploads(True) if platform == 'youtube' else api.list_tiktok_uploads(True)
    assert [item.id for item in full] == [row.id] and dashboard == []
    assert runtime.snapshot()['items'] == []
    receipt = json.loads((api.YOUTUBE_UPLOADS_PATH.parent/'attention_archive'/platform/'old.json').read_text())
    assert receipt['remote_action'] == 'none' and receipt['remote_outcome'] == 'unconfirmed'
    with pytest.raises(api.HTTPException) as error:
        api.ensure_no_archived_upload_resubmission(platform, 'new-source', '/outputs/new/file.mp4', row.clip_sha256)
    assert error.value.status_code == 409
    assert not api.completed_job_upload_retry_ready([result], row.source_job_id, row.clip_url)


def test_local_archive_does_not_wait_for_unrelated_upload_or_open_browser(runtime, monkeypatch):
    row, evidence = exhausted('youtube', runtime)
    api.youtube_uploads['active'] = row.model_copy(update=dict(id='active', status='running',
        source_job_id='other', clip_url='/outputs/other/file.mp4', clip_sha256='b'*64))
    monkeypatch.setattr(runtime, 'observe', lambda *args: pytest.fail('No browser for local archival'))
    assert runtime.run_once() == 1
    assert api.youtube_uploads[row.id].attention_archived_at
    assert api.youtube_uploads['active'].status == 'running'


@pytest.mark.parametrize('guard', ['file', 'process', 'active_related', 'changed', 'checking'])
def test_archive_rechecks_all_local_and_inflight_guards(runtime, guard):
    row, evidence = exhausted('youtube', runtime)
    if guard == 'file':
        path=api.output_path_from_url(row.clip_url); path.parent.mkdir(parents=True); path.write_bytes(b'keep')
    elif guard == 'process': api.youtube_upload_processes[row.id] = object()
    elif guard == 'active_related':
        api.youtube_uploads['related'] = row.model_copy(update=dict(id='related', status='queued'))
    elif guard == 'changed':
        api.youtube_uploads[row.id] = row.model_copy(update=dict(title='Changed identity'))
    else: runtime.store.update('youtube-old', state='checking')
    assert not api.archive_unresolved_upload_record('youtube', row.id, evidence['revision'], evidence)
    assert not api.youtube_uploads[row.id].attention_archived_at


def test_tombstone_write_failure_restores_original_record(runtime, monkeypatch):
    row, evidence = exhausted('youtube', runtime)
    def failed(): raise OSError('disk unavailable')
    monkeypatch.setattr(api, 'save_youtube_uploads_unlocked', failed)
    with pytest.raises(OSError):
        api.archive_unresolved_upload_record('youtube', row.id, evidence['revision'], evidence)
    assert api.youtube_uploads[row.id] is row


def history_job(identity='failed', news=False):
    job = api.ClipJob(id=identity, status='completed' if news else 'failed', created_at=api.now_iso(), updated_at=api.now_iso(),
        request=api.ClipJobRequest(url='https://www.youtube.com/watch?v=abcdefghijk',
            clip_mode='short' if news else 'highlight_5m', scheduled_public_source_credit=True,
            publication_review_required=not news, scheduled_news_hot=news),
        error=None if news else 'RuntimeError: insufficient_or_excessive_compilation_material')
    api.jobs[job.id] = job
    return job


def campaign(job):
    run = api.AutoViralRun(id='parent', status='failed', trigger='schedule', created_at=api.now_iso(), updated_at=api.now_iso(),
        request=api.AutoViralRequest(), processed=[dict(job_id=job.id, status='running', job_status='queued')])
    api.auto_viral_runs[run.id] = run
    return run


def test_empty_failed_review_job_archives_and_preserves_long_attempts(runtime):
    job=history_job(); run=campaign(job)
    api.save_long_production_state(dict(enabled=True, attempts=[dict(job_id=job.id, status='failed', day='2026-11-21')]))
    assert api.automatic_history_handling(job)['state'] == 'archiving'
    assert api.process_autonomous_history_once() == 1
    assert job.id not in api.jobs
    item=api.auto_viral_runs[run.id].processed[0]
    assert item['status'] == item['job_status'] == 'failed' and item['clip_count'] == 0
    attempt=api.long_production_state()['attempts'][0]
    assert attempt['status'] == 'failed' and attempt['day'] == '2026-11-21'
    assert attempt['disposition'] == 'deleted_terminal_output'
    receipt=json.loads((api.JOBS_PATH.parent/'autonomous_history/failed.json').read_text())
    assert receipt['original_request']['publication_review_required'] is True
    assert receipt['manual_hold_released'] is False and receipt['local_disposition'] == 'completed'


def test_failed_download_backlog_retires_without_touching_active_production(runtime):
    job = history_job()
    job.error = ('Koneksi jalur unduh YouTube terputus saat mengunduh video. '
                 'Workspace dan seluruh file sementara proses gagal telah dihapus.')
    job.progress_detail = 'Proses gagal; tidak ada hasil final yang dapat dipertahankan'
    campaign(job)
    active = job.model_copy(update=dict(id='active', status='running', error=None))
    api.jobs[active.id] = active
    assert api.process_autonomous_history_once() == 1
    assert job.id not in api.jobs and api.jobs[active.id].status == 'running'
    receipt = json.loads((api.JOBS_PATH.parent/'autonomous_history/failed.json').read_text())
    assert receipt['reason'] == 'source_download_failed_empty'
    assert receipt['original_job']['error'] == job.error
    assert receipt['remote_action'] == 'none' and receipt['local_disposition'] == 'completed'


@pytest.mark.parametrize('guard', ['active', 'recovery', 'live_campaign', 'upload', 'checkpoint_save'])
def test_history_never_discards_work_still_owned_by_another_worker(runtime, monkeypatch, guard):
    job=history_job(); run=campaign(job)
    if guard=='active': api.job_processes[job.id]=object()
    elif guard=='recovery': api.jobs['repair']=job.model_copy(update=dict(id='repair',status='queued',repair_source_job_id=job.id))
    elif guard=='live_campaign': run.status='running'
    elif guard=='upload':
        api.youtube_uploads['upload']=api.YouTubeUploadJob(id='upload',source_job_id=job.id,clip_url='/outputs/source.mp4',
            clip_name='source.mp4',title='Title',status='failed',created_at=api.now_iso(),updated_at=api.now_iso(),
            video_url='https://www.youtube.com/watch?v=abcdefghijk')
    else:
        def failed(): raise OSError('disk unavailable')
        monkeypatch.setattr(api,'save_auto_viral_runs_unlocked',failed)
    assert api.process_autonomous_history_once()==0
    assert job.id in api.jobs


def test_unsubmitted_news_drops_only_unapproved_clip_without_changing_approval(runtime):
    job=history_job('news',True);run=campaign(job)
    for name,approved in [('drop',False),('keep',True)]:
        path=api.OUTPUTS_DIR/'news/source/clips'/(name+'.mp4');path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'clip')
        job.clips.append(api.ClipFile(name=path.name,url='/outputs/news/source/clips/'+path.name,size_bytes=4,is_correct=approved))
    assert api.process_autonomous_history_once()==1
    remaining=api.jobs[job.id]
    assert len(remaining.clips)==1 and remaining.clips[0].is_correct
    assert api.output_path_from_url(remaining.clips[0].url).exists()
    item=api.auto_viral_runs[run.id].processed[0]
    assert item['automatic_disposition']=='PARTIAL_DROP_SOURCE' and item['clip_count']==1


def test_one_history_checkpoint_failure_does_not_block_unrelated_retirement(runtime, monkeypatch):
    blocked=history_job('blocked'); campaign(blocked)
    allowed=history_job('allowed')
    def failed(): raise OSError('checkpoint disk unavailable')
    monkeypatch.setattr(api,'save_auto_viral_runs_unlocked',failed)
    assert api.process_autonomous_history_once()==1
    assert blocked.id in api.jobs and allowed.id not in api.jobs


def test_news_cleanup_preserves_shared_media_used_by_another_job(runtime):
    job=history_job('news',True)
    path=api.OUTPUTS_DIR/'news/source/clips/shared.mp4';path.parent.mkdir(parents=True);path.write_bytes(b'keep')
    clip=api.ClipFile(name=path.name,url='/outputs/news/source/clips/shared.mp4',size_bytes=4)
    job.clips=[clip]
    api.jobs['other']=job.model_copy(update=dict(id='other',clips=[clip.model_copy(update={'is_correct':True})]))
    assert api.process_autonomous_history_once()==0
    assert path.read_bytes()==b'keep' and len(api.jobs[job.id].clips)==1
