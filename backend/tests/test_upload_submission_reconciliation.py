"""A lost HTTP response must neither strand a clip nor create a second transfer."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from types import SimpleNamespace
import json

import pytest
import api


def row(**overrides):
    fields = dict(id='accepted', source_job_id='job', clip_url='/outputs/job/clip.mp4',
        dry_run=False, status='queued', upload_confirmed=False,
        created_at='2026-11-10T00:00:00+00:00', error=None)
    fields.update(overrides)
    return SimpleNamespace(**fields)


@pytest.fixture(params=['youtube', 'tiktok'])
def platform(request, monkeypatch):
    name = request.param
    records = {}
    monkeypatch.setattr(api, name + '_uploads', records)
    monkeypatch.setattr(api, name + '_upload_creation_lock', Lock())
    monkeypatch.setattr(api, 'require_' + name + '_ready', lambda: None)
    monkeypatch.setattr(api, 'tiktok_login_is_active', lambda: False)
    monkeypatch.setattr(api, 'get_youtube_upload', lambda identity: records[identity])
    monkeypatch.setattr(api, 'queue_' + name + '_upload_jobs',
        lambda items: records.update({item.id: item for item in items}))
    request_model = api.YouTubeUploadRequest if name == 'youtube' else api.TikTokUploadRequest
    return name, records, request_model(clip_url='/outputs/job/clip.mp4'), getattr(api, 'reconcile_' + name + '_upload_submission')


@pytest.mark.parametrize('status', ['queued', 'running', 'completed', 'failed', 'cancelled'])
def test_existing_attempt_is_returned_without_new_record_or_worker(platform, monkeypatch, status):
    name, records, request, reconcile = platform
    existing = row(status=status, upload_confirmed=status == 'completed')
    records[existing.id] = existing
    def forbidden(*args, **kwargs): raise AssertionError('May not resubmit an existing attempt')
    monkeypatch.setattr(api, 'create_' + name + '_upload_record', forbidden)
    monkeypatch.setattr(api, 'queue_' + name + '_upload_jobs', forbidden)
    assert reconcile('job', request) is existing


def test_pending_metadata_then_failed_transfer_cannot_be_replayed(platform, monkeypatch):
    name, records, request, reconcile = platform
    entered, release, recovery_started = Event(), Event(), Event()
    creates = []
    def create(*args):
        creates.append(True);entered.set();assert release.wait(3)
        return row(status='failed', error='Transfer outcome unknown')
    monkeypatch.setattr(api, 'create_' + name + '_upload_record', create)
    def original_request():
        with getattr(api, name + '_upload_creation_lock'):
            upload = create('job', request)
            getattr(api, 'queue_' + name + '_upload_jobs')([upload])
            return upload
    def recover():
        recovery_started.set()
        return reconcile('job', request)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(original_request)
        assert entered.wait(3)
        second = pool.submit(recover)
        assert recovery_started.wait(3)
        assert not second.done()
        release.set()
        assert first.result(timeout=3).id == second.result(timeout=3).id
    assert len(creates) == 1


def test_request_that_never_reached_a_worker_can_be_recovered_once(platform, monkeypatch):
    name, records, request, reconcile = platform
    creates = []
    def create(*args): creates.append(True);return row()
    monkeypatch.setattr(api, 'create_' + name + '_upload_record', create)
    assert reconcile('job', request).id == reconcile('job', request).id
    assert len(creates) == len(records) == 1


def test_all_original_preflight_rejections_are_preserved(platform, monkeypatch):
    name, records, request, reconcile = platform
    def reject(*args): raise api.HTTPException(status_code=409, detail='Capacity or QC hold')
    monkeypatch.setattr(api, 'create_' + name + '_upload_record', reject)
    with pytest.raises(api.HTTPException, match='Capacity or QC hold'):
        reconcile('job', request)
    assert not records


def test_scope_and_priority_exclude_dry_runs_and_other_clips():
    older = row(id='success', status='completed', upload_confirmed=True)
    latest = row(id='failure', status='failed', created_at='2026-11-10T01:00:00+00:00')
    unrelated = row(id='other', clip_url='/outputs/other.mp4', status='running')
    simulation = row(id='dry', dry_run=True, status='running')
    assert api.existing_submission_recovery_record([older, latest, unrelated, simulation], 'job', older.clip_url) is older


def test_capacity_wait_batch_survives_backend_restart(monkeypatch, tmp_path):
    saved = tmp_path / 'automation.json'
    run = api.AutoViralRun(id='waiting', status='running', trigger='schedule',
        request=api.AutoViralRequest(), created_at=api.now_iso(), updated_at=api.now_iso(),
        progress_stage='cron_capacity_wait', processed=[dict(job_id='job', job_status='completed', status='awaiting_upload')])
    saved.write_text(json.dumps([run.model_dump()]))
    monkeypatch.setattr(api, 'AUTO_VIRAL_RUNS_PATH', saved)
    restored = api.load_auto_viral_runs()['waiting']
    assert restored.status == 'queued' and restored.progress_stage == 'resume_pending_upload'
    assert restored.processed == run.processed
