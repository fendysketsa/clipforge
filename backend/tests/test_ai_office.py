"""Supervision delegates only to existing owners and preserves durable decisions."""
from copy import deepcopy
import json
from types import SimpleNamespace
import threading

import pytest

import ai_office
from ai_office import OfficeService


class Worker:
    def __init__(self, running=True):
        self.running = running

    def is_alive(self):
        return self.running


@pytest.fixture
def office(tmp_path):
    """A complete local adapter, with no production state or worker targets."""
    flags = dict(AI_OFFICE_ENABLED=True, AUTO_UPLOAD_COMPLETED_JOBS=False,
                 TIKTOK_AUTOMATIC_RETRY_ENABLED=False, UPLOAD_ATTENTION_AUTOMATIC_ENABLED=False,
                 AUTO_VIRAL_SCHEDULE_ENABLED=True)
    api = SimpleNamespace(JOBS_PATH=tmp_path / 'jobs.json', flags=flags, calls=[], cron_enabled=False,
        jobs={}, youtube_uploads={}, tiktok_uploads={}, long_qc_active=set(),
        claimed_clip_cleanup_scheduled=set(), auto_viral_scheduler_thread=None,
        completed_job_upload_sweeper_thread=None, tiktok_retry_sweeper_thread=None,
        youtube_worker_thread=None, tiktok_worker_thread=None,
        api_key='private-provider-secret')
    for name in ('jobs_lock', 'youtube_uploads_lock', 'tiktok_uploads_lock', 'long_qc_lock',
                 'claimed_clip_cleanup_lock', 'terminal_output_cleanup_lock'):
        setattr(api, name, threading.Lock())
    for name in ('auto_viral_scheduler_wakeup', 'completed_job_upload_sweeper_wakeup',
                 'tiktok_retry_sweeper_wakeup'):
        setattr(api, name, threading.Event())
    api.env_bool = lambda key, default=False: flags.get(key, default)
    api.auto_viral_schedule_enabled = lambda: api.cron_enabled
    api.facebook = dict(enabled=False, worker_running=False, active_count=0,
                        state='disabled', detail='Paused by operator')
    api.facebook_office_snapshot = lambda: dict(api.facebook)

    def start(key, thread_name):
        def run():
            api.calls.append(key)
            setattr(api, thread_name, Worker())
        return run

    api.start_auto_viral_scheduler_if_enabled = start('cron', 'auto_viral_scheduler_thread')
    api.start_completed_job_upload_sweeper_if_needed = start('generic', 'completed_job_upload_sweeper_thread')
    api.start_tiktok_retry_sweeper_if_needed = start('retry', 'tiktok_retry_sweeper_thread')
    api.start_youtube_worker_if_needed = start('youtube', 'youtube_worker_thread')
    api.start_tiktok_worker_if_needed = start('tiktok', 'tiktok_worker_thread')
    attention = SimpleNamespace(thread=None, execution=threading.Lock(), wakeup=threading.Event(),
        retry_ledger={'existing-post': {'attempts': 3, 'next_check_at': 1_999_999_999}})
    attention.enabled = lambda: flags['UPLOAD_ATTENTION_AUTOMATIC_ENABLED']
    def start_attention():
        api.calls.append('attention')
        attention.thread = Worker()
    attention.start = start_attention
    attention.request_check = lambda: pytest.fail('Manager must preserve remote verification backoff')
    api.upload_attention_service = attention
    def start_facebook():
        api.calls.append('facebook')
        api.facebook.update(worker_running=True, state='waiting')
        return True
    api.ensure_facebook_office_worker = start_facebook
    return OfficeService(api), api


def upload(*, status='queued', confirmed=False, dry_run=False):
    return SimpleNamespace(status=status, upload_confirmed=confirmed, dry_run=dry_run)


def test_unreadable_facebook_settings_do_not_block_other_departments(office):
    service, api = office
    api.cron_enabled = True
    def broken():
        raise ValueError('private-provider-secret')
    api.facebook_office_snapshot = broken
    assert service.run_once() == 1
    assert api.calls == ['cron']
    snapshot = service.snapshot()
    facebook = next(row for row in snapshot['departments'] if row['id'] == 'facebook')
    assert facebook['state'] == 'degraded'
    assert 'private-provider-secret' not in json.dumps(snapshot)


def test_persisted_cron_pause_is_respected_even_when_environment_requests_cron(office):
    service, api = office
    assert api.flags['AUTO_VIRAL_SCHEDULE_ENABLED'] is True
    assert service.run_once(force=True) == 0
    assert not api.calls and not api.auto_viral_scheduler_wakeup.is_set()
    assert api.cron_enabled is False
    assert not service.path.exists()


def test_existing_manual_upload_queues_can_drain_with_cron_paused(office):
    service, api = office
    api.youtube_uploads['manual-yt'] = upload()
    api.tiktok_uploads['manual-tt'] = upload()
    original_youtube = dict(api.youtube_uploads)
    original_tiktok = dict(api.tiktok_uploads)
    assert service.run_once() == 2
    assert api.calls == ['youtube', 'tiktok']
    assert api.youtube_uploads == original_youtube and api.tiktok_uploads == original_tiktok
    assert api.cron_enabled is False
    assert all(task['status'] == 'completed' for task in service.tasks)
    assert all('konfirmasi platform' in task['summary'] for task in service.tasks)


def test_only_enabled_dead_owners_restart_and_alive_workers_are_not_duplicated(office):
    service, api = office
    api.cron_enabled = True
    api.flags.update(AUTO_UPLOAD_COMPLETED_JOBS=True, TIKTOK_AUTOMATIC_RETRY_ENABLED=True,
                     UPLOAD_ATTENTION_AUTOMATIC_ENABLED=True)
    api.facebook.update(enabled=True, state='degraded')
    api.auto_viral_scheduler_thread = Worker(False)
    assert service.run_once() == 5
    assert api.calls == ['cron', 'generic', 'retry', 'attention', 'facebook']
    assert service.run_once() == 0
    assert len(api.calls) == 5
    assert len(json.loads(service.path.read_text())['tasks']) == 5


@pytest.mark.parametrize('owner', ['cron', 'generic', 'retry', 'attention', 'youtube', 'tiktok'])
def test_starter_declining_without_live_owner_cannot_report_completed(office, monkeypatch, owner):
    service, api = office
    starters = dict(cron='start_auto_viral_scheduler_if_enabled',
        generic='start_completed_job_upload_sweeper_if_needed', retry='start_tiktok_retry_sweeper_if_needed',
        youtube='start_youtube_worker_if_needed', tiktok='start_tiktok_worker_if_needed')
    if owner == 'cron':
        api.cron_enabled = True
    elif owner == 'generic':
        api.flags['AUTO_UPLOAD_COMPLETED_JOBS'] = True
    elif owner == 'retry':
        api.flags['TIKTOK_AUTOMATIC_RETRY_ENABLED'] = True
    elif owner == 'attention':
        api.flags['UPLOAD_ATTENTION_AUTOMATIC_ENABLED'] = True
    else:
        getattr(api, owner + '_uploads')['queued'] = upload()
    def decline():
        api.calls.append(owner + '-declined')
        # For upload owners this models a surviving transfer subprocess:
        # start() returns without creating another thread or draining the queue.
    monkeypatch.setattr(api.upload_attention_service if owner == 'attention' else api,
                        'start' if owner == 'attention' else starters[owner], decline)
    assert service.run_once() == 0
    assert api.calls == [owner + '-declined']
    assert len(service.tasks) == 1 and service.tasks[0]['status'] == 'deferred'
    assert 'konfirmasi platform' not in service.tasks[0]['summary']
    if owner in ('youtube', 'tiktok'):
        assert getattr(api, owner + '_uploads')['queued'].status == 'queued'


@pytest.mark.parametrize('owner', ['cron', 'generic', 'retry', 'attention'])
def test_operator_setting_changed_after_observation_prevents_start_and_wake(office, monkeypatch, owner):
    service, api = office
    flag = dict(generic='AUTO_UPLOAD_COMPLETED_JOBS', retry='TIKTOK_AUTOMATIC_RETRY_ENABLED',
                attention='UPLOAD_ATTENTION_AUTOMATIC_ENABLED').get(owner)
    if owner == 'cron':
        api.cron_enabled = True
    else:
        api.flags[flag] = True
    observe = service.context
    def observe_then_pause():
        state = observe()
        if owner == 'cron':
            api.cron_enabled = False
        else:
            api.flags[flag] = False
        return state
    monkeypatch.setattr(service, 'context', observe_then_pause)
    assert service.run_once(force=True) == 0
    assert not api.calls and len(service.tasks) == 2
    assert all(task['status'] == 'deferred' for task in service.tasks)
    event = {'cron': api.auto_viral_scheduler_wakeup,
             'generic': api.completed_job_upload_sweeper_wakeup,
             'retry': api.tiktok_retry_sweeper_wakeup,
             'attention': api.upload_attention_service.wakeup}[owner]
    assert not event.is_set()


@pytest.mark.parametrize('platform', ['youtube', 'tiktok'])
def test_fast_queue_consumption_is_accepted_without_claiming_remote_confirmation(office, monkeypatch, platform):
    service, api = office
    queued = upload()
    getattr(api, platform + '_uploads')['queued'] = queued
    def consume():
        queued.status = 'running'
    monkeypatch.setattr(api, 'start_' + platform + '_worker_if_needed', consume)
    assert service.run_once() == 1
    assert service.tasks[-1]['status'] == 'completed'
    assert 'konfirmasi platform' in service.tasks[-1]['summary']
    assert queued.upload_confirmed is False


def test_disabled_manager_cannot_dispatch_or_resume_itself(office):
    service, api = office
    api.flags['AI_OFFICE_ENABLED'] = False
    api.cron_enabled = True
    api.youtube_uploads['queued'] = upload()
    assert service.run_once(force=True) == 0
    assert service.request_check() is False
    assert not api.calls and service.thread is None
    assert service.snapshot()['state'] == 'disabled'


def test_verified_and_dry_run_records_cannot_manufacture_upload_work(office):
    service, api = office
    api.youtube_uploads['verified'] = upload(status='completed', confirmed=True)
    api.youtube_uploads['simulated'] = upload(dry_run=True)
    api.tiktok_uploads['failed'] = upload(status='failed')
    assert service.run_once() == 0
    assert not api.calls


def test_force_wakes_attention_without_resetting_its_existing_remote_backoff(office):
    service, api = office
    api.flags['UPLOAD_ATTENTION_AUTOMATIC_ENABLED'] = True
    api.upload_attention_service.thread = Worker()
    before = deepcopy(api.upload_attention_service.retry_ledger)
    assert service.run_once(force=True) == 1
    assert api.upload_attention_service.wakeup.is_set()
    assert api.upload_attention_service.retry_ledger == before
    assert not api.calls
    assert service.tasks[-1]['action'] == 'Meminta pemeriksaan attention'


def test_failure_in_one_department_is_isolated_and_backoff_survives_restart(office, monkeypatch):
    service, api = office
    clock = [1_800_000_000.0]
    monkeypatch.setattr(ai_office.time, 'time', lambda: clock[0])
    api.cron_enabled = True
    api.flags['TIKTOK_AUTOMATIC_RETRY_ENABLED'] = True
    def fail_cron():
        api.calls.append('cron-failed')
        raise OSError('authorization=private-provider-secret')
    api.start_auto_viral_scheduler_if_enabled = fail_cron
    assert service.run_once() == 1
    assert api.calls == ['cron-failed', 'retry']
    first = json.loads(service.path.read_text())
    assert first['assignments']['start_cron']['attempts'] == 1
    assert first['assignments']['start_cron']['next_retry'] == clock[0] + ai_office.BACKOFF[0]
    assert 'private-provider-secret' not in service.path.read_text()
    restored = OfficeService(api)
    assert restored.run_once() == 0
    assert api.calls == ['cron-failed', 'retry']
    clock[0] += ai_office.BACKOFF[0] + 1
    assert restored.run_once() == 0
    assert api.calls == ['cron-failed', 'retry', 'cron-failed']
    assert restored.assignments['start_cron']['attempts'] == 2


@pytest.mark.parametrize('contents', ['{', '{"version":1,"tasks":{},"assignments":{}}',
                                     '{"version":1,"tasks":[{"id":"partial","status":"running"}],"assignments":{}}'])
def test_corrupt_journal_is_preserved_and_cannot_dispatch(office, contents):
    service, api = office
    service.path.write_text(contents)
    api.cron_enabled = True
    assert service.run_once() == 0
    assert service.path.read_text() == contents and not api.calls
    snapshot = service.snapshot()
    assert snapshot['state'] == 'degraded' and not snapshot['tasks']


def test_intent_write_failure_blocks_actuator(office, monkeypatch):
    service, api = office
    api.cron_enabled = True
    def fail_save():
        raise OSError('disk unavailable')
    monkeypatch.setattr(service, '_save', fail_save)
    assert service.run_once() == 0
    assert not api.calls and not service.tasks and not service.path.exists()
    assert service.error == 'OSError'


def test_completion_write_failure_recovers_without_dispatching_again(office, monkeypatch):
    service, api = office
    api.cron_enabled = True
    save = service._save
    writes = []
    def fail_second_write():
        writes.append(1)
        if len(writes) == 2:
            raise OSError('disk unavailable')
        save()
    monkeypatch.setattr(service, '_save', fail_second_write)
    assert service.run_once() == 0
    assert api.calls == ['cron']
    assert json.loads(service.path.read_text())['tasks'][0]['status'] == 'running'
    assert service.dirty and service.error == 'OSError'
    service.run_once()
    assert api.calls == ['cron']
    assert json.loads(service.path.read_text())['tasks'][0]['status'] == 'completed'
    assert not service.dirty and service.error is None


def test_history_is_bounded_without_reordering_recent_decisions(office, monkeypatch):
    service, api = office
    clock = [1_800_000_000.0]
    monkeypatch.setattr(ai_office.time, 'time', lambda: clock[0])
    for index in range(ai_office.HISTORY_LIMIT + 4):
        clock[0] += ai_office.INTERVAL + 1
        assert service._assign('check', 'production', f'Inspection {index}', lambda: True)
    stored = json.loads(service.path.read_text())
    assert len(stored['tasks']) == ai_office.HISTORY_LIMIT
    assert stored['tasks'][0]['action'] == 'Inspection 4'
    assert stored['tasks'][-1]['action'] == f'Inspection {ai_office.HISTORY_LIMIT + 3}'


def test_snapshot_is_read_only_compact_and_does_not_serialize_provider_secrets(office):
    service, api = office
    api.cron_enabled = True
    api.jobs['rendering'] = SimpleNamespace(status='running', repair_source_job_id=None,
        progress_stage='render', transcript='private full transcript', api_key=api.api_key)
    api.youtube_uploads['old'] = upload(status='failed')
    snapshot = service.snapshot()
    text = json.dumps(snapshot)
    assert not api.calls and not service.path.exists()
    assert 'private-provider-secret' not in text and 'private full transcript' not in text
    assert len(snapshot['departments']) == 6
    production = next(row for row in snapshot['departments'] if row['id'] == 'production')
    assert production['active_count'] == 1
    assert snapshot['capabilities']['no_parallel_production_owner'] is True


def test_interrupted_intent_becomes_deferred_until_live_owner_is_checked(office):
    service, api = office
    task = dict(id='in-flight', department='production', action='Resume worker', status='running',
        started_at=ai_office.stamp(), finished_at=None, summary='Intent was persisted', next_retry_at=None)
    service.path.write_text(json.dumps(dict(version=1, tasks=[task], assignments={})))
    before = service.path.read_bytes()
    snapshot = service.snapshot()
    assert snapshot['tasks'][0]['status'] == 'deferred'
    assert service.path.read_bytes() == before and not api.calls
    service.run_once()
    assert json.loads(service.path.read_text())['tasks'][0]['status'] == 'deferred'
    assert not api.calls


def test_active_manager_tick_prevents_competing_dispatch(office):
    service, api = office
    api.cron_enabled = True
    service.execution.acquire()
    try:
        assert service.run_once(force=True) == 0
    finally:
        service.execution.release()
    assert not api.calls


def test_concurrent_manager_starts_create_one_thread_and_shutdown_is_bounded(office, monkeypatch):
    service, _ = office
    entered = threading.Event()
    ticks = []
    def tick(**_):
        ticks.append(1)
        entered.set()
        return 0
    monkeypatch.setattr(service, 'run_once', tick)
    starts = [threading.Thread(target=service.start) for _ in range(5)]
    for thread in starts:
        thread.start()
    for thread in starts:
        thread.join(timeout=1)
    assert entered.wait(1)
    current = service.thread
    assert current is not None and current.is_alive()
    service.shutdown()
    assert not current.is_alive() and len(ticks) == 1


def test_installed_get_reads_only_and_post_requests_manager_inspection(office, monkeypatch):
    _, api = office
    routes = {}; handlers = {}
    class App:
        def get(self, path):
            return lambda callback: routes.setdefault(('GET', path), callback)
        def post(self, path):
            return lambda callback: routes.setdefault(('POST', path), callback)
        def add_event_handler(self, event, callback):
            handlers[event] = callback
    service = ai_office.install(App(), api)
    starts = []
    monkeypatch.setattr(service, 'start', lambda: starts.append(1))
    snapshot = routes['GET', '/api/ai-office']()
    assert snapshot['version'] == 1 and not api.calls and not starts
    assert not service.path.exists()
    assert routes['POST', '/api/ai-office/run']()['accepted'] is True
    assert service.force_requested and service.wakeup.is_set() and starts == [1]
    assert not api.calls  # HTTP dispatch never invokes media or upload work.
    assert set(handlers) == {'startup', 'shutdown'}
    api.flags['AI_OFFICE_ENABLED'] = False
    assert routes['POST', '/api/ai-office/run']()['accepted'] is False
    assert starts == [1]
