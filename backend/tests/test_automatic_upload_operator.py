import importlib.util
import json
from pathlib import Path
import urllib.error
import pytest


@pytest.fixture
def intake(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location('private_intake_test', Path(__file__).resolve().parents[2] / 'scripts/automatic-upload-operator.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'POLICY', tmp_path / 'policy.json')
    monkeypatch.setattr(module, 'STATE', tmp_path / 'state.json')
    monkeypatch.setattr(module, 'PUBLIC_STATE', tmp_path / 'public/status.json')
    module.POLICY.write_text(json.dumps(dict(enabled=True, visibility='private', follow_completed_jobs=True)))
    state = dict(uploads=[], calls=[], jobs=[dict(id='long', created_at='2026-11-09', status='completed',
        request=dict(clip_mode='highlight_5m', publication_review_required=True),
        clips=[dict(url='/outputs/long.mp4', youtube_upload_ready=True)])])
    def request(path, payload=None):
        if path == '/api/jobs': return state['jobs']
        if path == '/api/youtube/uploads': return state['uploads']
        assert path == '/api/jobs/long/youtube-uploads'
        state['calls'].append(payload)
        result = dict(id='remote-upload', status='queued', source_job_id='long', clip_url=payload['clip_url'])
        state['uploads'].append(result)
        return result
    monkeypatch.setattr(module, 'request', request)
    return module, state


def test_long_private_intake_keeps_review_flag_and_is_idempotent(intake):
    module, state = intake
    module.tick(); module.tick()
    assert state['calls'] == [dict(clip_url='/outputs/long.mp4', visibility='private')]
    assert state['jobs'][0]['request']['publication_review_required'] is True


@pytest.mark.parametrize('status', ['failed', 'cancelled', 'queued', 'running', 'completed'])
def test_existing_remote_record_cannot_create_duplicate(intake, status):
    module, state = intake
    state['uploads'] = [dict(id='known', source_job_id='long', clip_url='/outputs/long.mp4',
        status=status, video_url='https://youtu.be/known', upload_confirmed=status=='completed')]
    module.tick()
    assert not state['calls']


def test_timeout_reservation_survives_restart(intake, monkeypatch):
    module, state = intake
    original = module.request
    def timeout(path, payload=None):
        if payload: raise TimeoutError('Accepted but response lost')
        return original(path, payload)
    monkeypatch.setattr(module, 'request', timeout)
    module.tick()
    monkeypatch.setattr(module, 'request', original)
    module.tick()
    assert not state['calls']
    assert next(iter(json.loads(module.STATE.read_text())['clips'].values()))['upload_outcome_unknown']


def test_api_preflight_rejection_is_held_without_falsifying_approval(intake, monkeypatch):
    import io
    module, state = intake
    original = module.request
    def reject(path, payload=None):
        if payload: raise urllib.error.HTTPError(path, 409, 'held', {}, io.BytesIO(b'Rights not verified'))
        return original(path, payload)
    monkeypatch.setattr(module, 'request', reject)
    module.tick(); module.tick()
    record = next(iter(json.loads(module.STATE.read_text())['clips'].values()))
    assert record['status'] == 'preflight_hold' and not record['upload_outcome_unknown']
    assert not state['calls']


def test_only_private_visibility_and_explicit_policy_can_submit(intake):
    module, state = intake
    module.POLICY.unlink()
    assert module.tick() == 'disabled'
    module.POLICY.write_text(json.dumps(dict(enabled=True, visibility='public')))
    with pytest.raises(ValueError): module.tick()
    assert not state['calls']


def test_rejected_media_and_active_render_do_not_submit(intake):
    module, state = intake
    state['jobs'][0]['clips'][0]['youtube_upload_ready'] = False
    module.tick()
    assert not state['calls']
    state['jobs'][0]['status'] = 'running'
    module.tick()
    assert not state['calls']


def test_scoped_policy_does_not_upload_future_unrelated_jobs(intake):
    module, state = intake
    module.POLICY.write_text(json.dumps(dict(enabled=True, visibility='private', follow_completed_jobs=False, job_ids=['requested-job'])))
    module.tick()
    assert not state['calls']
    policy = json.loads(module.POLICY.read_text()); policy['job_ids'].append('long')
    module.POLICY.write_text(json.dumps(policy))
    module.tick()
    assert len(state['calls']) == 1


def test_public_progress_snapshot_omits_private_evidence_and_errors(intake):
    module, state = intake
    module.tick()
    snapshot = json.loads(module.PUBLIC_STATE.read_text())
    assert snapshot['enabled'] is True
    assert set(snapshot['clips'][0]) == {'source_job_id', 'clip_url', 'status'}
    assert snapshot['clips'][0]['status'] == 'queued'


@pytest.mark.parametrize('condition', ['supported', 'old_backend', 'already_attempted', 'claim', 'timeout'])
def test_same_id_recovery_waits_for_backend_capability_and_is_reserved_once(intake, monkeypatch, condition):
    module, state = intake
    existing = dict(id='known', source_job_id='long', clip_url='/outputs/long.mp4', status='failed',
        video_url='https://youtu.be/known', error='Next modal upload tidak ditemukan; dialog-not-found',
        logs=[], storage_state_verification_attempted=False)
    if condition == 'old_backend': existing.pop('storage_state_verification_attempted')
    if condition == 'already_attempted': existing['storage_state_verification_attempted'] = True
    if condition == 'claim': existing['logs'] = ['CLAIMED_UPLOAD_ABORTED: explicit claim']
    state['uploads'] = [existing]
    original = module.request
    def request(path, payload=None):
        if payload:
            state['calls'].append(payload)
            if condition == 'timeout': raise TimeoutError('Unknown response')
            return dict(existing, status='queued')
        return original(path, payload)
    monkeypatch.setattr(module, 'request', request)
    module.tick(); module.tick()
    assert len(state['calls']) == (1 if condition in {'supported', 'timeout'} else 0)
    row = next(iter(json.loads(module.STATE.read_text())['clips'].values()))
    assert row['upload_id'] == 'known'
    if condition in {'supported', 'timeout'}: assert row['verification_requested'] is True
    if condition == 'timeout': assert row['upload_outcome_unknown'] is True
