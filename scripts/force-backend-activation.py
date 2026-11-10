#!/usr/bin/env python3
"""Explicit operator force: stop the existing backend before replacing modules.

The guarded activator verifies image hashes and holds the deployment lock.
This helper never edits checkpoint files, deletes media, or submits uploads.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
CONTAINER = 'fendy-clipper-backend'
spec = importlib.util.spec_from_file_location('idle_guard', ROOT / 'scripts/wait-for-backend-idle.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def docker(*args):
    subprocess.run(['docker', *args], check=True)


def force_activate(modules, state_file):
    if not modules or any(not name.isidentifier() or not (ROOT / 'backend' / (name + '.py')).is_file() for name in modules):
        raise ValueError('Invalid backend module list')
    snapshots = guard.read_snapshots('http://127.0.0.1:8010/api/')
    for run in snapshots['automation/viral-cc']:
        if run['status'] in {'queued', 'running'}:
            request = urllib.request.Request(
                'http://127.0.0.1:8010/api/automation/viral-cc/' + run['id'] + '/cancel',
                data=b'{}', headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(request, timeout=30):
                pass
    for job in snapshots['jobs']:
        if job['status'] in {'queued', 'running'}:
            request = urllib.request.Request('http://127.0.0.1:8010/api/jobs/' + job['id'] + '/cancel',
                data=b'{}', headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(request, timeout=30):
                pass
    state = json.loads(state_file.read_text()) if state_file.exists() and state_file.stat().st_size else {}
    fields = ('id', 'status', 'source_job_id', 'clip_url', 'video_url', 'profile_url',
              'upload_confirmed', 'submission_started', 'submission_accepted',
              'clip_sha256', 'visibility', 'publish_at', 'progress_stage', 'updated_at')
    state.update(stalled_run_ids=state.get('stalled_run_ids', []), force_active=True,
        interrupted_work={key: [{field: row[field] for field in fields if field in row}
                                for row in rows if row.get('status') in {'queued', 'running'}]
                          for key, rows in snapshots.items()})
    state_file.write_text(json.dumps(state, indent=2) + '\n')
    state_file.chmod(0o600)
    with tempfile.TemporaryDirectory(prefix='clipforge-force-backup-') as folder:
        backup = Path(folder)
        # Back up every old module before stopping anything. If copying the
        # replacement fails, restore the complete old set while still stopped.
        for name in modules:
            docker('cp', f'{CONTAINER}:/app/{name}.py', str(backup / (name + '.py')))
        print('Force requested: stopping backend; persisted upload checkpoints are retained.', flush=True)
        docker('stop', '--time', '10', CONTAINER)
        starting = False
        try:
            for name in modules:
                docker('cp', str(ROOT / 'backend' / (name + '.py')), f'{CONTAINER}:/app/{name}.py')
            starting = True
            docker('start', CONTAINER)
        except BaseException:
            if starting:
                docker('stop', '--time', '10', CONTAINER)
            for name in modules:
                docker('cp', str(backup / (name + '.py')), f'{CONTAINER}:/app/{name}.py')
            docker('start', CONTAINER)
            raise
    print('Forced restart complete; the caller must verify backend health and runtime hashes.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-file', type=Path, required=True)
    parser.add_argument('modules', nargs='+')
    args = parser.parse_args()
    force_activate(args.modules, args.state_file)
