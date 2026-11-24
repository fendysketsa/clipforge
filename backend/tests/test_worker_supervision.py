"""A supervisor can revive a dead owner without duplicating a live worker."""
import json
import threading
from types import SimpleNamespace

from fastapi import FastAPI
import pytest

import api
import facebook_api
from facebook_runner import Runner

RealThread = threading.Thread
WORKERS = [
    ('start_youtube_worker_if_needed', 'youtube_upload_worker_loop', 'youtube_worker_running', 'youtube_worker_thread'),
    ('start_tiktok_worker_if_needed', 'tiktok_worker_loop', 'tiktok_worker_running', 'tiktok_worker_thread'),
    ('start_completed_job_upload_sweeper_if_needed', 'completed_job_upload_sweeper_loop',
     'completed_job_upload_sweeper_running', 'completed_job_upload_sweeper_thread'),
    ('start_auto_viral_scheduler_if_enabled', 'auto_viral_scheduler_loop',
     'auto_viral_scheduler_running', 'auto_viral_scheduler_thread'),
    ('start_tiktok_retry_sweeper_if_needed', 'tiktok_retry_sweeper_loop',
     'tiktok_retry_sweeper_running', 'tiktok_retry_sweeper_thread'),
]


@pytest.fixture
def owner(monkeypatch, request):
    start, target, flag, reference = request.param
    monkeypatch.setenv('AUTO_UPLOAD_COMPLETED_JOBS', 'true')
    monkeypatch.setenv('AUTO_VIRAL_SCHEDULE_ENABLED', 'true')
    monkeypatch.setenv('TIKTOK_AUTOMATIC_RETRY_ENABLED', 'true')
    monkeypatch.setattr(api, 'youtube_upload_processes', {})
    monkeypatch.setattr(api, 'tiktok_upload_processes', {})
    monkeypatch.setattr(api, flag, False)
    monkeypatch.setattr(api, reference, None)
    monkeypatch.setattr(api, 'save_auto_viral_runs_unlocked', lambda: None)
    entered = threading.Event(); release = threading.Event(); calls = []

    def wait_for_release():
        calls.append(threading.current_thread())
        entered.set()
        assert release.wait(5), 'Test did not release its worker'

    monkeypatch.setattr(api, target, wait_for_release)
    yield SimpleNamespace(start=getattr(api, start), flag=flag, reference=reference,
                          entered=entered, release=release, calls=calls)
    release.set()
    worker = getattr(api, reference)
    if worker is not None and worker is not threading.current_thread():
        worker.join(timeout=2)


@pytest.mark.parametrize('owner', WORKERS, indirect=True)
def test_concurrent_supervisors_create_one_owner(owner):
    callers = [RealThread(target=owner.start) for _ in range(12)]
    for caller in callers:
        caller.start()
    for caller in callers:
        caller.join(timeout=2)
        assert not caller.is_alive()
    assert owner.entered.wait(2)
    assert len(owner.calls) == 1
    assert getattr(api, owner.reference) is owner.calls[0]
    assert getattr(api, owner.flag) is True


@pytest.mark.parametrize('owner', WORKERS, indirect=True)
def test_dead_thread_with_stale_running_flag_is_restarted(owner, monkeypatch):
    dead = RealThread(target=lambda: None); dead.start(); dead.join(timeout=2)
    monkeypatch.setattr(api, owner.reference, dead)
    monkeypatch.setattr(api, owner.flag, True)
    owner.start()
    assert owner.entered.wait(2)
    assert len(owner.calls) == 1 and getattr(api, owner.reference) is not dead


@pytest.mark.parametrize('owner', WORKERS, indirect=True)
def test_start_failure_does_not_leave_false_running_owner(owner, monkeypatch):
    class CannotStart:
        def __init__(self, **kwargs): pass
        def start(self): raise RuntimeError('thread unavailable')
        def is_alive(self): return False
    monkeypatch.setattr(api.threading, 'Thread', CannotStart)
    with pytest.raises(RuntimeError, match='thread unavailable'):
        owner.start()
    assert getattr(api, owner.reference) is None
    assert getattr(api, owner.flag) is False
    assert not owner.calls


@pytest.mark.parametrize('owner', WORKERS[:2], indirect=True)
def test_surviving_upload_subprocess_prevents_second_queue_owner(owner, monkeypatch):
    processes = 'youtube_upload_processes' if owner.reference == 'youtube_worker_thread' else 'tiktok_upload_processes'
    monkeypatch.setattr(api, processes, {'active': SimpleNamespace(poll=lambda: None)})
    owner.start()
    assert not owner.entered.is_set() and not owner.calls
    assert getattr(api, owner.reference) is None


@pytest.mark.parametrize('owner', WORKERS[2:], indirect=True)
def test_disabled_owner_is_not_enabled_by_supervision(owner, monkeypatch):
    monkeypatch.setenv('AUTO_UPLOAD_COMPLETED_JOBS', 'false')
    monkeypatch.setenv('TIKTOK_AUTOMATIC_RETRY_ENABLED', 'false')
    # The persisted cron override takes precedence over the enabled environment.
    monkeypatch.setattr(api, 'auto_viral_schedule_enabled_override', False)
    owner.start()
    assert not owner.calls and getattr(api, owner.reference) is None
    assert getattr(api, owner.flag) is False


def test_facebook_start_is_serialized_and_dead_owner_can_restart(monkeypatch):
    store = SimpleNamespace(lock=threading.RLock(), data={'uploads': {}}, save=lambda: None)
    runner = Runner(api, lambda: store, lambda: None, lambda *args: None, lambda *args: None, lambda: None)
    release = threading.Event(); entered = threading.Event(); calls = []
    def work():
        calls.append(threading.current_thread()); entered.set(); release.wait(5)
    monkeypatch.setattr(runner, 'loop', work)
    try:
        callers = [RealThread(target=runner.start) for _ in range(12)]
        for caller in callers: caller.start()
        for caller in callers:
            caller.join(timeout=2); assert not caller.is_alive()
        assert entered.wait(2) and len(calls) == 1
        release.set(); runner.thread.join(timeout=2)
        assert not runner.thread.is_alive()
        entered.clear(); release.clear()
        assert runner.start() is True
        assert entered.wait(2) and len(calls) == 2
    finally:
        release.set()
        if runner.thread: runner.thread.join(timeout=2)


@pytest.mark.parametrize('enabled', [True, False])
def test_facebook_office_adapter_respects_persisted_settings_and_hides_plans(tmp_path, monkeypatch, enabled):
    payload = dict(schema=1, uploads={'upload': dict(job_id='same-job', status='running')},
        autopilot=dict(enabled=enabled), autopilot_message='Fixture progress',
        autopilot_runs={'run': dict(job_id='same-job', status='rendering', authored_plan={'private': 'plan'})})
    (tmp_path / 'facebook_workspace.json').write_text(json.dumps(payload))
    adapter = SimpleNamespace(JOBS_PATH=tmp_path / 'jobs.json')
    facebook_api.install(FastAPI(), adapter)
    calls = []
    monkeypatch.setattr(Runner, 'start', lambda self: calls.append(True) or True)
    snapshot = adapter.facebook_office_snapshot()
    assert set(snapshot) == {'enabled', 'worker_running', 'active_count', 'state', 'detail',
        'qc_wait_count', 'failed_upload_count', 'unknown_post_count', 'skipped_upload_count',
        'autonomous_recovery_version'}
    assert snapshot['autonomous_recovery_version'] == 1
    assert all(snapshot[key] == 0 for key in ('qc_wait_count', 'failed_upload_count',
        'unknown_post_count', 'skipped_upload_count'))
    assert snapshot['enabled'] is enabled and snapshot['active_count'] == 1
    assert snapshot['state'] == ('degraded' if enabled else 'disabled')
    assert adapter.ensure_facebook_office_worker() is enabled
    assert calls == ([True] if enabled else [])
