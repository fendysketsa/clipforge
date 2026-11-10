"""Exercise real commits and pushes against disposable local bare remotes."""
import importlib.util
import json
from pathlib import Path
import subprocess
import time

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('git_auto_sync', ROOT / 'scripts/git-auto-sync.py')
sync_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync_module)


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.PIPE).decode().strip()


@pytest.fixture
def repository(tmp_path):
    remote, repo = tmp_path / 'remote.git', tmp_path / 'repo'
    subprocess.run(['git', 'init', '--bare', '--initial-branch=master', str(remote)], check=True, capture_output=True)
    subprocess.run(['git', 'init', '--initial-branch=master', str(repo)], check=True, capture_output=True)
    git(repo, 'config', 'user.name', 'Test Author');git(repo, 'config', 'user.email', 'author@example.test')
    (repo / 'tracked.txt').write_text('original\n')
    (repo / 'delete.txt').write_text('remove me\n')
    git(repo, 'add', '.');git(repo, 'commit', '-m', 'seed')
    git(repo, 'remote', 'add', 'origin', str(remote));git(repo, 'push', '-u', 'origin', 'master')
    return repo, remote


def worker(repo, **kwargs):
    options = dict(remote='origin', branch='master', settle_seconds=0, max_bytes=sync_module.MAX_BYTES)
    options.update(kwargs)
    return sync_module.Sync(repo, **options)


def test_add_modify_delete_and_special_paths_reach_remote_once(repository):
    repo, remote = repository
    (repo / 'tracked.txt').write_text('updated\n');(repo / 'delete.txt').unlink()
    (repo / 'new [file].txt').write_text('new\n');(repo / ':odd.txt').write_text('literal\n')
    first = worker(repo).run();assert first['state'] == 'synced' and first['committed'] and first['pushed']
    assert git(remote, 'show', 'master:tracked.txt') == 'updated'
    assert git(remote, 'show', 'master:new [file].txt') == 'new'
    assert 'delete.txt' not in git(remote, 'ls-tree', '--name-only', 'master').splitlines()
    assert not git(repo, 'status', '--porcelain')
    second = worker(repo).run();assert second['state'] == 'synced'
    assert not second['committed'] and not second['pushed']
    assert git(repo, 'rev-list', '--count', 'HEAD') == '2'


def test_offline_push_retains_commit_then_retries_without_another_commit(repository):
    repo, remote = repository
    git(repo, 'remote', 'set-url', 'origin', str(remote.parent / 'offline.git'))
    (repo / 'new.txt').write_text('save locally\n')
    first = worker(repo).run();assert first['state'] == 'retry_later'
    saved_head = git(repo, 'rev-parse', 'HEAD')
    assert git(remote, 'rev-parse', 'master') != saved_head
    git(repo, 'remote', 'set-url', 'origin', str(remote))
    second = worker(repo).run();assert second['state'] == 'synced' and second['pushed']
    assert git(repo, 'rev-parse', 'HEAD') == git(remote, 'rev-parse', 'master') == saved_head


def test_remote_divergence_never_rebases_or_force_pushes(repository, tmp_path):
    repo, remote = repository;peer = tmp_path / 'peer'
    subprocess.run(['git', 'clone', str(remote), str(peer)], check=True, capture_output=True)
    git(peer, 'config', 'user.name', 'Peer');git(peer, 'config', 'user.email', 'peer@example.test')
    (peer / 'peer.txt').write_text('remote work\n');git(peer, 'add', '.');git(peer, 'commit', '-m', 'peer');git(peer, 'push')
    remote_head = git(remote, 'rev-parse', 'master')
    (repo / 'local.txt').write_text('local work\n')
    result = worker(repo).run();assert result['state'] == 'needs_sync'
    assert git(remote, 'rev-parse', 'master') == remote_head
    assert (repo / 'local.txt').read_text() == 'local work\n'
    assert not (repo / '.git/rebase-merge').exists()


def test_wrong_branch_and_manual_merge_leave_worktree_and_index_untouched(repository):
    repo, _ = repository;(repo / 'new.txt').write_text('unfinished\n')
    git(repo, 'checkout', '-b', 'feature')
    assert worker(repo).run()['state'] == 'wrong_branch'
    git(repo, 'checkout', 'master');(repo / '.git/MERGE_HEAD').write_text(git(repo, 'rev-parse', 'HEAD') + '\n')
    assert worker(repo).run()['state'] == 'git_operation_in_progress'
    assert not git(repo, 'diff', '--cached', '--name-only')


def test_quiet_period_and_dry_run_do_not_stage_or_commit(repository):
    repo, remote = repository;(repo / 'new.txt').write_text('editing\n')
    before = git(repo, 'rev-parse', 'HEAD')
    assert worker(repo, settle_seconds=60).run()['state'] == 'waiting_for_quiet'
    plan = worker(repo).run(dry_run=True);assert plan['state'] == 'dry_run'
    assert plan['eligible_files'] == ['new.txt']
    assert not git(repo, 'diff', '--cached', '--name-only')
    assert git(repo, 'rev-parse', 'HEAD') == git(remote, 'rev-parse', 'master') == before


@pytest.mark.parametrize('path', ['.env', 'backend/data/cookies.json', 'backend/uploads/source.mp4',
    'youtube_storage_state.json', '.ssh/id_ed25519', 'frontend/.next-queue/build.json'])
def test_runtime_credentials_and_build_files_are_not_added(repository, path):
    repo, _ = repository;file = repo / path;file.parent.mkdir(parents=True, exist_ok=True);file.write_text('private runtime\n')
    result = worker(repo).run()
    assert result['state'] == 'synced' and not result['committed']
    assert result['protected_files_skipped'] == 1
    assert path not in git(repo, 'ls-files').splitlines()


def test_credential_content_is_rejected_without_printing_value_or_staging(repository):
    repo, _ = repository;token = 'gh' + 'p_' + 'a' * 36
    (repo / 'settings.txt').write_text('token=' + token)
    result = worker(repo).run();assert result['state'] == 'held'
    assert token not in json.dumps(result)
    assert not git(repo, 'diff', '--cached', '--name-only')


def test_already_staged_secret_or_large_outgoing_blob_is_never_pushed(repository):
    repo, remote = repository;before = git(remote, 'rev-parse', 'master')
    (repo / '.env').write_text('private\n');git(repo, 'add', '.env')
    assert worker(repo).run()['state'] == 'held'
    git(repo, 'reset');(repo / '.env').unlink()
    (repo / 'large.bin').write_bytes(b'x' * 2000);git(repo, 'add', '.');git(repo, 'commit', '-m', 'large pending blob')
    assert worker(repo, max_bytes=1000).run()['state'] == 'held'
    assert git(remote, 'rev-parse', 'master') == before


def test_active_auto_sync_lock_prevents_parallel_commit(repository):
    repo, _ = repository;sync = worker(repo)
    with (repo / '.git/clipforge-auto-sync.lock').open('a') as lock:
        sync_module.fcntl.flock(lock, sync_module.fcntl.LOCK_EX | sync_module.fcntl.LOCK_NB)
        assert sync.run()['state'] == 'already_running'
