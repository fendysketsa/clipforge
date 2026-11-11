"""Exercise real commits and pushes against disposable local bare remotes."""
import importlib.util
import json
from pathlib import Path
import subprocess
import time
import os

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


def clock(monkeypatch):
    now = [1_000_000.0]
    monkeypatch.setattr(sync_module.time, 'time', lambda: now[0])
    return now


def test_thirty_minute_deadline_resets_on_new_edit_and_survives_worker_restart(repository, monkeypatch):
    repo, remote = repository;now = clock(monkeypatch)
    before = git(remote, 'rev-parse', 'master')
    (repo / 'tracked.txt').write_text('first edit\n')
    first = worker(repo, settle_seconds=1800).run()
    assert first['state'] == 'waiting_for_quiet' and first['remaining_seconds'] == 1800
    now[0] += 1799
    assert worker(repo, settle_seconds=1800).run()['remaining_seconds'] == 1
    (repo / 'tracked.txt').write_text('second edit\n')
    assert worker(repo, settle_seconds=1800).run()['remaining_seconds'] == 1800
    assert not git(repo, 'diff', '--cached', '--name-only')
    assert git(repo, 'rev-parse', 'HEAD') == git(remote, 'rev-parse', 'master') == before
    now[0] += 1799
    assert worker(repo, settle_seconds=1800).run()['remaining_seconds'] == 1
    now[0] += 1
    done = worker(repo, settle_seconds=1800).run()
    assert done['state'] == 'synced' and done['committed'] and done['pushed']
    assert git(remote, 'show', 'master:tracked.txt') == 'second edit'


def test_deletion_waits_thirty_minutes_even_without_an_mtime(repository, monkeypatch):
    repo, remote = repository;now = clock(monkeypatch)
    worker(repo, settle_seconds=1800).run()
    now[0] += 2000
    (repo / 'delete.txt').unlink()
    assert worker(repo, settle_seconds=1800).run()['remaining_seconds'] == 1800
    now[0] += 1800
    done = worker(repo, settle_seconds=1800).run()
    assert done['state'] == 'synced' and done['committed']
    assert 'delete.txt' not in git(remote, 'ls-tree', '--name-only', 'master').splitlines()


def test_preserved_mtime_and_staging_activity_still_reset_countdown(repository, monkeypatch):
    repo, _ = repository;now = clock(monkeypatch);file = repo / 'tracked.txt'
    file.write_text('first edit\n');original = file.stat()
    worker(repo, settle_seconds=1800).run()
    now[0] += 1700
    file.write_text('second edit\n');os.utime(file, ns=(original.st_atime_ns, original.st_mtime_ns))
    assert worker(repo, settle_seconds=1800).run()['remaining_seconds'] == 1800
    now[0] += 1700
    git(repo, 'add', 'tracked.txt')
    assert worker(repo, settle_seconds=1800).run()['remaining_seconds'] == 1800


def test_report_churn_neither_resets_code_deadline_nor_creates_report_only_commits(repository, monkeypatch):
    repo, remote = repository;now = clock(monkeypatch)
    (repo / 'tracked.txt').write_text('code edit\n')
    report = repo / 'reports/status.json';report.parent.mkdir()
    worker(repo, settle_seconds=1800).run()
    now[0] += 1700;report.write_text('{"progress": 40}\n')
    assert worker(repo, settle_seconds=1800).run()['remaining_seconds'] == 100
    now[0] += 100
    assert worker(repo, settle_seconds=1800).run()['committed']
    assert git(remote, 'show', 'master:reports/status.json') == '{"progress": 40}'
    head = git(repo, 'rev-parse', 'HEAD')
    now[0] += 60;report.write_text('{"progress": 90}\n')
    done = worker(repo, settle_seconds=1800).run()
    assert done['state'] == 'synced' and not done['committed'] and not done['pushed']
    assert git(repo, 'rev-parse', 'HEAD') == git(remote, 'rev-parse', 'master') == head


def test_network_retry_keeps_completed_quiet_period_but_another_edit_holds_push(repository, monkeypatch):
    repo, remote = repository;now = clock(monkeypatch)
    (repo / 'tracked.txt').write_text('code edit\n')
    worker(repo, settle_seconds=1800).run()
    git(repo, 'remote', 'set-url', 'origin', str(remote.parent / 'offline.git'))
    now[0] += 1800
    assert worker(repo, settle_seconds=1800).run()['state'] == 'retry_later'
    saved_head = git(repo, 'rev-parse', 'HEAD')
    git(repo, 'remote', 'set-url', 'origin', str(remote));now[0] += 60
    done = worker(repo, settle_seconds=1800).run()
    assert done['pushed'] and not done['committed']
    assert git(remote, 'rev-parse', 'master') == saved_head
    (repo / 'tracked.txt').write_text('new editing session\n')
    assert worker(repo, settle_seconds=1800).run()['remaining_seconds'] == 1800


@pytest.mark.parametrize('during', ['add', 'fetch'])
def test_new_edit_during_git_preparation_prevents_premature_push(repository, monkeypatch, during):
    repo, remote = repository;now = clock(monkeypatch)
    (repo / 'tracked.txt').write_text('finished edit\n')
    instance = worker(repo, settle_seconds=1800);instance.run()
    now[0] += 1800;original_git = instance.git;before = git(remote, 'rev-parse', 'master')
    def changing_git(*args, **kwargs):
        output = original_git(*args, **kwargs)
        if args[0] == during: (repo / 'tracked.txt').write_text('editing resumed during preparation\n')
        return output
    monkeypatch.setattr(instance, 'git', changing_git)
    held = instance.run()
    assert held['state'] == 'waiting_for_quiet' and held['remaining_seconds'] == 1800
    assert git(remote, 'rev-parse', 'master') == before


def test_commit_message_describes_staged_code_and_actual_line_counts(repository):
    repo, remote = repository;file = repo / 'scripts/git-auto-sync.py';file.parent.mkdir()
    file.write_text('QUIET_SECONDS = 1800\ndef quiet_gate():\n    return 1800\n\ndef commit_message():\n    return "summary"\n')
    assert worker(repo).run()['committed']
    message = git(remote, 'log', '-1', '--format=%B')
    assert message.startswith('chore(git): perbarui jeda auto-sync 30 menit dan ringkasan pesan commit')
    assert 'A scripts/git-auto-sync.py (+6/-0 baris)' in message
    assert 'quiet_gate, commit_message' in message
    assert 'auto-sync 2026-' not in message


def test_history_commit_subject_comes_from_layout_diff(repository):
    repo, remote = repository;folder = repo / 'frontend';folder.mkdir()
    (folder / 'HistorySection.tsx').write_text('export function HistorySection() { return null; }\n')
    (folder / 'globals.css').write_text('.jobList { grid-template-columns: repeat(4, minmax(0, 1fr)); }\n')
    assert worker(repo).run()['committed']
    message = git(remote, 'log', '-1', '--format=%B')
    assert message.startswith('style(history): atur 4 kartu per baris')
    assert 'A frontend/HistorySection.tsx' in message and 'A frontend/globals.css' in message


def test_mixed_commit_describes_upload_behavior_before_incidental_history_marker(repository):
    repo,remote=repository
    folder=repo/'backend';folder.mkdir()
    (folder/'browser_page_activity.py').write_text('def start_background_page_activity(page):\n    return page\n')
    (folder/'api.py').write_text('def social_upload_turn():\n    return True\n')
    script=repo/'scripts';script.mkdir()
    (script/'activate-ui.sh').write_text('# history-four-columns\n')
    assert worker(repo).run()['committed']
    message=git(remote,'log','-1','--format=%B')
    assert message.startswith('fix(automation): fokus browser upload dan giliran antrean upload')
    assert 'Perilaku yang diperbarui:' in message


def test_upload_symbols_in_test_fixtures_do_not_claim_a_production_fix(repository):
    repo,remote=repository
    tests=repo/'backend/tests';tests.mkdir(parents=True)
    (tests/'test_fixture.py').write_text('def social_upload_turn():\n    return True\n')
    assert worker(repo).run()['committed']
    message=git(remote,'log','-1','--format=%B')
    assert message.startswith('test(tests):') and 'fix(automation)' not in message


@pytest.mark.parametrize('recreated', [False, True])
def test_staged_deletion_newly_ignored_does_not_block_commit_and_push(repository,recreated):
    repo,remote=repository
    # Initial tracked report is now deliberately removed from version control.
    report=repo/'old-report.json';report.write_text('{"old":true}')
    git(repo,'add','old-report.json');git(repo,'commit','-m','old report');git(repo,'push')
    git(repo,'rm','old-report.json')
    (repo/'.gitignore').write_text('old-report.json\n')
    if recreated:report.write_text('private local runtime record')
    (repo/'tracked.txt').write_text('actual code update\n')
    result=worker(repo).run()
    assert result['state']=='synced' and result['pushed']
    assert 'old-report.json' not in git(remote,'ls-tree','--name-only','master').splitlines()
    assert git(remote,'show','master:tracked.txt')=='actual code update'
    if recreated:assert report.read_text()=='private local runtime record'


def test_already_staged_missing_source_deletion_can_be_the_only_change(repository):
    repo,remote=repository
    git(repo,'rm','delete.txt')
    result=worker(repo).run()
    assert result['state']=='synced' and result['pushed']
    assert 'delete.txt' not in git(remote,'ls-tree','--name-only','master').splitlines()
