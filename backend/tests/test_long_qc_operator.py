import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def operator(monkeypatch, tmp_path):
    path = Path(__file__).resolve().parents[2] / 'scripts/long-qc-operator.py'
    spec = importlib.util.spec_from_file_location('long_qc_operator_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.setattr(module, 'DATA', tmp_path / 'data')
    module.DATA.mkdir()
    monkeypatch.setattr(module, 'REVIEWS', tmp_path / 'reviews')
    module.REVIEWS.mkdir()
    media = tmp_path / 'backend/outputs/job/video.mp4'
    media.parent.mkdir(parents=True)
    media.write_bytes(b'exact artifact')
    req = dict(clip_mode='highlight_5m', publication_review_required=True, url='https://youtu.be/source',
        confirm_source_rights=True, source_rights_evidence='Written permission for the source audio and video')
    job = dict(id='job', status='completed', request=req, clips=[dict(url='/outputs/job/video.mp4', fyp_score=95)])
    state = dict(uploads=[], queued=[], backend=False)
    def request(path, payload=None):
        if path.endswith('/long-production'): return {'auto_qc_enabled': state['backend']}
        if path == '/api/youtube/uploads': return state['uploads']
        if path == '/api/jobs': return [job]
        if path == '/api/jobs/job': return job
        if path == '/api/jobs/job/youtube-uploads':
            state['queued'].append(payload)
            result = dict(id='upload', source_job_id='job', clip_url=payload['clip_url'], visibility=payload['visibility'])
            state['uploads'].append(result)
            return result
        pytest.fail('Unexpected API call ' + path)
    monkeypatch.setattr(module, 'request', request)
    monkeypatch.setattr(module.qc, 'provider_config', lambda: dict(model='test', base_url='local', audio_review_mode='local_whisper'))
    monkeypatch.setattr(module.qc, 'audit_long', lambda *a: dict(status='reviewed',
        audit=dict(decision='PASS_UPLOAD', upload_allowed=True)))
    return module, state, media


def test_live_api_operator_queues_only_private_once(operator):
    module, state, _ = operator
    module.tick()
    module.tick()
    assert state['queued'] == [dict(clip_url='/outputs/job/video.mp4', visibility='private')]
    record = json.loads(next(module.REVIEWS.glob('*.json')).read_text())
    assert record['upload_id'] == 'upload' and record['upload_outcome_unknown'] is False


def test_operator_yields_to_deployed_backend(operator):
    module, state, _ = operator
    state['backend'] = True
    assert module.tick() == 'backend_owns_qc'
    assert state['queued'] == []


def test_rejected_long_backfill_is_reserved_once_and_daily_target_restored(operator, monkeypatch):
    module, _, _ = operator
    day = module.datetime.now(module.ZoneInfo('Asia/Jakarta')).date().isoformat()
    policy = dict(enabled=True, daily_target=1, attempts=[dict(day=day, job_id='rejected')])
    (module.REVIEWS / 'rejected.json').write_text(json.dumps(dict(source_job_id='rejected', audit=dict(decision='DROP_SOURCE'))))
    calls = []
    def request(path, payload=None):
        calls.append(payload)
        return {'production': {'status':'queued', 'job_id':'replacement'}}
    monkeypatch.setattr(module, 'request', request)
    assert module.replace_rejected_long(policy, []) == 'replacement_requested'
    assert calls == [dict(enabled=True, daily_target=2), dict(enabled=True, daily_target=1)]
    assert module.replace_rejected_long(policy, []) == 'replacement_reserved'
    assert len(calls) == 2
    policy['attempts'] *= 3
    module.replace_rejected_long(policy, [])
    assert len(calls) == 2


@pytest.mark.parametrize('reason', ['remote_unknown', 'drop', 'file_changed', 'post_timeout'])
def test_operator_holds_unknown_outcomes_and_changed_evidence(operator, monkeypatch, reason):
    module, state, media = operator
    if reason == 'remote_unknown':
        state['uploads'].append(dict(source_job_id='job', clip_url='/outputs/job/video.mp4', status='failed'))
    if reason == 'drop':
        monkeypatch.setattr(module.qc, 'audit_long', lambda *a: dict(status='reviewed', audit=dict(decision='DROP_SOURCE', upload_allowed=False)))
    if reason == 'file_changed':
        def audit(*args):
            media.write_bytes(media.read_bytes() + b'changed after AI inspection')
            return dict(status='reviewed', audit=dict(decision='PASS_UPLOAD', upload_allowed=True))
        monkeypatch.setattr(module.qc, 'audit_long', audit)
    if reason == 'post_timeout':
        request = module.request
        def uncertain(path, payload=None):
            if payload is not None: raise TimeoutError('Unknown acceptance')
            return request(path, payload)
        monkeypatch.setattr(module, 'request', uncertain)
    module.tick()
    module.tick()
    assert state['queued'] == []
