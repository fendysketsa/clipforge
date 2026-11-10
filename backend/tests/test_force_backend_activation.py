"""Forced activation preserves checkpoints and replaces files only while stopped."""
from contextlib import nullcontext
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('force_backend_activation', ROOT / 'scripts/force-backend-activation.py')
force = importlib.util.module_from_spec(spec)
spec.loader.exec_module(force)


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    (tmp_path / 'backend').mkdir()
    for name in ('api', 'clipper'):
        (tmp_path / 'backend' / (name + '.py')).write_text('new ' + name)
    monkeypatch.setattr(force, 'ROOT', tmp_path)
    snapshots = {key: [] for key in force.guard.ENDPOINTS}
    snapshots['jobs'] = [dict(id='render', status='running', request={'ai_api_key':'secret-key-must-not-leak'})]
    snapshots['automation/viral-cc'] = [dict(id='campaign', status='running')]
    snapshots['youtube/uploads'] = [dict(id='yt', status='running', video_url='https://youtu.be/abcdefghijk')]
    snapshots['tiktok/uploads'] = [dict(id='tt', status='running', submission_started=True)]
    monkeypatch.setattr(force.guard, 'read_snapshots', lambda _: snapshots)
    events = []
    monkeypatch.setattr(force.urllib.request, 'urlopen', lambda request, **kwargs:
        (events.append(('cancel', request.full_url)) or nullcontext()))
    state = dict(running=True, files={name: 'old ' + name for name in ('api', 'clipper')}, fail=None)
    def docker(*args):
        events.append(args)
        if args[0] == 'stop':
            state['running'] = False
        elif args[0] == 'start':
            state['running'] = True
        elif args[0] == 'cp':
            if args[1].startswith(force.CONTAINER + ':'):
                name = Path(args[1]).stem
                Path(args[2]).write_text(state['files'][name])
            else:
                assert not state['running'], 'Replaced live modules before stopping backend'
                name = Path(args[2]).stem
                contents = Path(args[1]).read_text()
                if state['fail'] == name and contents.startswith('new '):
                    raise subprocess.CalledProcessError(1, ['docker', *args])
                state['files'][name] = contents
        else:
            pytest.fail('Unexpected Docker mutation')
    monkeypatch.setattr(force, 'docker', docker)
    return tmp_path / 'state.json', state, events


def test_force_stops_before_replacement_and_retains_remote_identity(runtime):
    path, state, events = runtime
    force.force_activate(['api', 'clipper'], path)
    assert state['running'] and state['files'] == {'api': 'new api', 'clipper': 'new clipper'}
    saved = json.loads(path.read_text())
    assert saved['force_active'] and saved['stalled_run_ids'] == []
    assert saved['interrupted_work']['youtube/uploads'][0]['video_url'] == 'https://youtu.be/abcdefghijk'
    assert saved['interrupted_work']['tiktok/uploads'][0]['submission_started'] is True
    assert path.stat().st_mode & 0o777 == 0o600
    assert 'secret-key-must-not-leak' not in path.read_text()
    assert [event[1] for event in events if event[0] == 'cancel'] == [
        'http://127.0.0.1:8010/api/automation/viral-cc/campaign/cancel',
        'http://127.0.0.1:8010/api/jobs/render/cancel',
    ]
    assert ('stop', '--time', '10', force.CONTAINER) in events


def test_copy_failure_rolls_back_the_complete_old_set(runtime):
    path, state, _ = runtime
    state['fail'] = 'clipper'
    with pytest.raises(subprocess.CalledProcessError):
        force.force_activate(['api', 'clipper'], path)
    assert state['running'] and state['files'] == {'api': 'old api', 'clipper': 'old clipper'}


def test_unknown_api_state_prevents_force_mutations(runtime, monkeypatch):
    path, state, events = runtime
    def fail(_): raise ValueError('Unknown API state')
    monkeypatch.setattr(force.guard, 'read_snapshots', fail)
    with pytest.raises(ValueError): force.force_activate(['api'], path)
    assert state['running'] and not events and not path.exists()


@pytest.mark.parametrize('modules', [[], ['../api'], ['missing']])
def test_invalid_module_scope_cannot_stop_the_backend(runtime, modules):
    path, state, events = runtime
    with pytest.raises(ValueError): force.force_activate(modules, path)
    assert state['running'] and not events
