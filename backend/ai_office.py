"""Lightweight supervisor: delegate to existing owners, preserve their safety gates."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import tempfile
import threading
import time
import uuid
import ai_office_director
import ai_office_incidents
import ai_office_learning
import ai_office_activity
import yt_skills

VERSION = 1
INTERVAL = 30
HISTORY_LIMIT = 60
BACKOFF = (60, 300, 900, 3600)


def stamp(value: float | None = None) -> str:
    return datetime.fromtimestamp(time.time() if value is None else value, timezone.utc).isoformat()


def alive(thread) -> bool:
    return bool(thread is not None and thread.is_alive())


class OfficeService:
    """One manager thread; workers alone own media, QC, remote IDs and publishing."""
    def __init__(self, api):
        self.api = api
        self.path = api.JOBS_PATH.parent / 'ai_office.json'
        self.lock = threading.RLock()
        self.execution = threading.Lock()
        self.start_lock = threading.Lock()
        self.wakeup = threading.Event()
        self.stop = threading.Event()
        self.thread = None
        self.loaded = False
        self.tasks = []
        self.assignments = {}
        self.incidents = {}
        self.last_tick_at = None
        self.next_tick_at = None
        self.error = None
        self.force_requested = False
        self.dirty = False
        self.strategy = dict(ai_office_director.DEFAULT_STRATEGY)
        self.directives = []
        self.directive_at = None

    def enabled(self):
        return self.api.env_bool('AI_OFFICE_ENABLED', True)

    def _learning_root(self):
        return self.api.JOBS_PATH.parent.parent

    def _load(self):
        with self.lock:
            if self.loaded:
                return
            data = {'version': VERSION, 'tasks': [], 'assignments': {}}
            if self.path.exists():
                if self.path.stat().st_size > 256_000:
                    raise ValueError('Office journal exceeds limit')
                data = json.loads(self.path.read_text())
                if (not isinstance(data, dict) or data.get('version') != VERSION
                        or not isinstance(data.get('tasks'), list) or not isinstance(data.get('assignments'), dict)):
                    raise ValueError('Invalid office journal')
                if not all(isinstance(row, dict) and all(isinstance(row.get(key), str) for key in
                           ('id', 'department', 'action', 'started_at', 'summary'))
                           and row.get('status') in {'running', 'completed', 'deferred', 'failed'}
                           for row in data['tasks']):
                    raise ValueError('Invalid office task')
                if not all(isinstance(row, dict) and isinstance(row.get('attempts', 0), int)
                           and row.get('attempts', 0) >= 0
                           and isinstance(row.get('next_retry', 0), (int, float))
                           and math.isfinite(row.get('next_retry', 0)) and row.get('next_retry', 0) >= 0
                           and isinstance(row.get('last_dispatch', 0), (int, float))
                           and math.isfinite(row.get('last_dispatch', 0)) and row.get('last_dispatch', 0) >= 0
                           for row in data['assignments'].values()):
                    raise ValueError('Invalid office retry state')
            self.tasks = data['tasks'][-HISTORY_LIMIT:]
            self.assignments = data['assignments']
            incidents = data.get('incidents', {})
            if (not isinstance(incidents, dict) or any(not isinstance(row, dict) or not isinstance(row.get('id'), str)
                    or row.get('state') not in {'waiting', 'needs_operator', 'resolved'} for row in incidents.values())):
                raise ValueError('Invalid office incident journal')
            self.incidents = incidents
            self.strategy = (ai_office_director.validate_strategy(data['strategy'])
                             if isinstance(data.get('strategy'), dict)
                             else dict(ai_office_director.DEFAULT_STRATEGY))
            directives = data.get('directives', [])
            if (not isinstance(directives, list) or len(directives) > ai_office_director.HISTORY_LIMIT
                    or any(not isinstance(row, dict) or not isinstance(row.get('id'), str)
                           or not isinstance(row.get('department'), str)
                           or row.get('status') not in {'active', 'blocked'}
                           for row in directives)):
                directives = []
            self.directives = directives
            self.directive_at = data.get('directive_at')
            if self.directive_at is not None and not isinstance(self.directive_at, str):
                self.directive_at = None
            for task in self.tasks:
                if task['status'] == 'running':
                    task.update(status='deferred', finished_at=stamp(),
                                summary='Koordinator direstart; keadaan worker diperiksa kembali sebelum penugasan.')
                    self.dirty = True
            self.loaded = True

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix='.ai-office-', dir=self.path.parent)
        try:
            with os.fdopen(descriptor, 'w') as stream:
                os.fchmod(stream.fileno(), 0o600)
                json.dump(dict(version=VERSION, tasks=self.tasks[-HISTORY_LIMIT:],
                               assignments=self.assignments, incidents=self.incidents,
                               strategy=self.strategy, directives=self.directives,
                               directive_at=self.directive_at), stream, ensure_ascii=False)
            os.replace(temporary, self.path)
            self.dirty = False
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def context(self):
        a = self.api
        with a.jobs_lock:
            active_jobs = [row for row in a.jobs.values() if row.status in {'queued', 'running'}]
            quality_jobs = sum(bool(row.repair_source_job_id) or row.progress_stage in {'qc', 'quality_control'}
                               or str(getattr(row, 'progress_detail', '') or '').casefold().startswith(('audit ', 'qc '))
                               for row in active_jobs)
        with a.youtube_uploads_lock:
            youtube = [(row.status, bool(row.upload_confirmed)) for row in a.youtube_uploads.values()
                       if not row.dry_run and not getattr(row, 'attention_archived_at', None)]
        with a.tiktok_uploads_lock:
            tiktok = [(row.status, bool(row.upload_confirmed)) for row in a.tiktok_uploads.values()
                      if not row.dry_run and not getattr(row, 'attention_archived_at', None)]
        with a.long_qc_lock:
            quality_jobs += len(a.long_qc_active)
        with a.claimed_clip_cleanup_lock:
            cleanups = len(a.claimed_clip_cleanup_scheduled)
        if a.terminal_output_cleanup_lock.locked():
            cleanups += 1
        facebook = {
            'enabled': False, 'worker_running': False, 'active_count': 0,
            'state': 'disabled', 'detail': 'Otomasi Facebook belum tersedia.'}
        if hasattr(a, 'facebook_office_snapshot'):
            try:
                facebook = a.facebook_office_snapshot()
            except Exception as error:
                facebook.update(state='degraded',
                    detail=f'Status Facebook mengalami {type(error).__name__}; departemen lain tetap dipantau.')
        context = dict(cron_enabled=a.auto_viral_schedule_enabled(),
            generic_enabled=a.env_bool('AUTO_UPLOAD_COMPLETED_JOBS', False),
            retry_enabled=a.env_bool('TIKTOK_AUTOMATIC_RETRY_ENABLED', True),
            attention_enabled=a.upload_attention_service.enabled(),
            jobs=len(active_jobs), quality=quality_jobs, cleanups=cleanups,
            youtube_queued=sum(status == 'queued' for status, _ in youtube),
            tiktok_queued=sum(status == 'queued' for status, _ in tiktok),
            uploads=sum(status in {'queued', 'running'} for status, _ in youtube + tiktok),
            unverified=sum(status in {'failed', 'cancelled'} and not confirmed for status, confirmed in youtube + tiktok),
            cron_alive=alive(a.auto_viral_scheduler_thread),
            generic_alive=alive(a.completed_job_upload_sweeper_thread),
            retry_alive=alive(a.tiktok_retry_sweeper_thread),
            attention_alive=alive(a.upload_attention_service.thread), facebook=facebook)
        context['incidents'] = ai_office_incidents.detect(a, context)
        context['activity'] = ai_office_activity.observe(a, context)
        return context

    def _sync_incidents(self, rows):
        """A blocker closes only after it disappears from a successful observation."""
        now = stamp()
        with self.lock:
            current = {row['id'] for row in rows}
            for row in rows[:ai_office_incidents.LIMIT]:
                previous = self.incidents.get(row['id'], {})
                self.incidents[row['id']] = {**row, 'first_seen_at': previous.get('first_seen_at', now),
                    'last_seen_at': now, 'resolved_at': None}
            for identity, row in self.incidents.items():
                if identity not in current and row['state'] != 'resolved':
                    row.update(state='resolved', resolved_at=now)
            # Keep current blockers plus bounded, most recent resolved receipts.
            active = {r['id']:self.incidents[r['id']] for r in rows[:ai_office_incidents.LIMIT]}
            resolved = sorted((r for r in self.incidents.values() if r['state'] == 'resolved'),
                              key=lambda r:r.get('resolved_at') or '', reverse=True)
            self.incidents = {**{r['id']:r for r in resolved[:30]}, **active}
            incident_keys = sorted((k for k in self.assignments if k.startswith('incident:')),
                key=lambda k:self.assignments[k].get('last_dispatch', 0), reverse=True)
            for key in incident_keys[200:]:
                self.assignments.pop(key, None)
            self.dirty = True
            self._save()

    def _plan_directives(self, state):
        """Publish the digital leader's assignments; execution stays with owners.

        Directives are derived from the current observation, so they are not
        written to the journal on their own. Strategy changes are persisted
        explicitly by the strategy endpoint and by normal coordinator writes.
        """
        rows = ai_office_director.build_directives(self.strategy, state, state['incidents'])
        with self.lock:
            self.directives = rows
            self.directive_at = stamp()

    def _dispatch_incident(self, incident):
        a = self.api
        action = incident['action']
        if action == 'cleanup_history' and a.env_bool('AUTO_UPLOAD_TERMINAL_CLEANUP_ENABLED', True):
            callback = getattr(a, 'process_autonomous_history_once', None)
        elif action == 'recover_scheduled_uploads' and a.auto_viral_schedule_enabled():
            callback = getattr(a, 'queue_missing_scheduled_uploads_once', None)
        elif action == 'verify_upload' and a.upload_attention_service.enabled():
            callback = a.upload_attention_service.wakeup.set
        elif action == 'retry_tiktok' and a.env_bool('TIKTOK_AUTOMATIC_RETRY_ENABLED', True):
            callback = a.tiktok_retry_sweeper_wakeup.set
        elif action == 'recover_facebook':
            callback = getattr(a, 'request_facebook_recovery', None)
        elif action == 'use_supported_cron' and a.auto_viral_schedule_enabled():
            callback = a.auto_viral_scheduler_wakeup.set
        else:
            return False
        if not callable(callback):
            return False
        # These owners inspect their full backlog. One signal covers all
        # matching incidents and keeps retries bounded across source changes.
        key = 'incident:' + action
        if time.time() - self.assignments.get(key, {}).get('last_dispatch', 0) < 300:
            return False
        return self._assign(key, incident['department'], 'Koordinasi: ' + incident['title'], callback)

    def _assign(self, key, department, action, callback, *, force=False):
        """Persist intent before dispatch; failures back off across manager restarts."""
        now = time.time()
        with self.lock:
            previous = dict(self.assignments.get(key, {}))
            # A manual wake does not erase failure backoff or make a failed QC pass.
            if float(previous.get('next_retry', 0)) > now:
                return False
            if not force and now - float(previous.get('last_dispatch', 0)) < INTERVAL:
                return False
            task = dict(id=uuid.uuid4().hex, department=department, action=action,
                        status='running', started_at=stamp(now), finished_at=None,
                        summary='Arahan dicatat; memeriksa worker pemilik pekerjaan.', next_retry_at=None)
            old_tasks = self.tasks[:]
            was_dirty = self.dirty
            self.tasks = [*self.tasks, task][-HISTORY_LIMIT:]
            self.dirty = True
            try:
                self._save()
            except OSError:
                self.tasks = old_tasks
                self.dirty = was_dirty
                raise  # No side effect without durable intent.
        try:
            result = callback()
            status = 'deferred' if result is False else 'completed'
            summary = ('Penugasan ditunda karena setelan atau antrean berubah.' if result is False else
                       'Worker pemilik menerima arahan. Hasil video tetap menunggu QC dan konfirmasi platform.')
            attempts = 0
            next_retry = 0
        except Exception as error:
            status = 'failed'
            summary = f'Penugasan mengalami {type(error).__name__}; departemen lain tetap berjalan.'
            attempts = int(previous.get('attempts', 0)) + 1
            next_retry = time.time() + BACKOFF[min(attempts - 1, len(BACKOFF) - 1)]
        with self.lock:
            task.update(status=status, summary=summary, finished_at=stamp(),
                        next_retry_at=stamp(next_retry) if next_retry else None)
            self.assignments[key] = dict(attempts=attempts, next_retry=next_retry, last_dispatch=now,
                                         department=department, status=status)
            self.dirty = True
            self._save()
        return status == 'completed'

    def _start_owner(self, key):
        a = self.api
        if key == 'cron':
            if not a.auto_viral_schedule_enabled():
                return False
            a.start_auto_viral_scheduler_if_enabled()
            return alive(a.auto_viral_scheduler_thread)
        elif key == 'generic':
            if not a.env_bool('AUTO_UPLOAD_COMPLETED_JOBS', False):
                return False
            a.start_completed_job_upload_sweeper_if_needed()
            return alive(a.completed_job_upload_sweeper_thread)
        elif key == 'retry':
            if not a.env_bool('TIKTOK_AUTOMATIC_RETRY_ENABLED', True):
                return False
            a.start_tiktok_retry_sweeper_if_needed()
            return alive(a.tiktok_retry_sweeper_thread)
        elif key == 'attention':
            if not a.upload_attention_service.enabled():
                return False
            a.upload_attention_service.start()
            return alive(a.upload_attention_service.thread)
        elif key == 'facebook':
            return a.ensure_facebook_office_worker()
        elif key in {'youtube', 'tiktok'}:
            lock = a.youtube_uploads_lock if key == 'youtube' else a.tiktok_uploads_lock
            records = a.youtube_uploads if key == 'youtube' else a.tiktok_uploads
            with lock:
                queued = any(row.status == 'queued' and not row.dry_run for row in records.values())
            if not queued:
                return False
            (a.start_youtube_worker_if_needed if key == 'youtube' else a.start_tiktok_worker_if_needed)()
            with lock:
                remaining = any(row.status == 'queued' and not row.dry_run for row in records.values())
            return alive(getattr(a, key + '_worker_thread')) or not remaining
        return True

    def _acknowledge_recovered(self, key, running):
        if not running:
            return
        with self.lock:
            assignment = self.assignments.get('start_' + key)
            if assignment and assignment.get('status') == 'failed':
                assignment.update(status='completed', attempts=0, next_retry=0)
                self.dirty = True
                self._save()

    def run_once(self, *, force=False):
        if not self.enabled() or not self.execution.acquire(blocking=False):
            return 0
        changed = 0
        try:
            self._load()
            with self.lock:
                if self.dirty:
                    self._save()
            state = self.context()
            self._plan_directives(state)
            owners = [('cron', 'production', state['cron_enabled'], state['cron_alive']),
                      ('generic', 'distribution', state['generic_enabled'], state['generic_alive']),
                      ('retry', 'recovery', state['retry_enabled'], state['retry_alive']),
                      ('attention', 'recovery', state['attention_enabled'], state['attention_alive']),
                      ('facebook', 'facebook', state['facebook']['enabled'], state['facebook']['worker_running'])]
            for key, department, enabled, running in owners:
                self._acknowledge_recovered(key, running)
                if enabled and not running:
                    changed += self._assign('start_' + key, department, 'Memulihkan worker ' + key,
                                            lambda key=key: self._start_owner(key))
            for platform in ('youtube', 'tiktok'):
                thread = getattr(self.api, platform + '_worker_thread')
                if state[platform + '_queued'] and not alive(thread):
                    changed += self._assign('start_' + platform, 'distribution', 'Melanjutkan antrean ' + platform,
                                            lambda platform=platform: self._start_owner(platform))
            if force:
                for key, department, enabled, _ in owners:
                    if not enabled:
                        continue
                    def wake(key=key):
                        a = self.api
                        if key == 'cron' and a.auto_viral_schedule_enabled():
                            a.auto_viral_scheduler_wakeup.set()
                        elif key == 'generic' and a.env_bool('AUTO_UPLOAD_COMPLETED_JOBS', False):
                            a.completed_job_upload_sweeper_wakeup.set()
                        elif key == 'retry' and a.env_bool('TIKTOK_AUTOMATIC_RETRY_ENABLED', True):
                            a.tiktok_retry_sweeper_wakeup.set()
                        elif key == 'attention' and a.upload_attention_service.enabled():
                            a.upload_attention_service.wakeup.set()
                        else:
                            return False
                        return True
                    if key != 'facebook':
                        changed += self._assign('wake_' + key, department, 'Meminta pemeriksaan ' + key, wake)
            dispatched_actions = set()
            for incident in state['incidents']:
                if incident['automatic'] and incident['action'] not in dispatched_actions:
                    dispatched_actions.add(incident['action'])
                    changed += self._dispatch_incident(incident)
            observed = [row for row in self.context()['incidents'] if row['action'] != 'worker_supervision']
            if observed or self.incidents:
                self._sync_incidents(observed)
            with self.lock:
                self.error = None
        except Exception as error:
            with self.lock:
                self.error = type(error).__name__
        finally:
            with self.lock:
                self.last_tick_at = stamp()
                self.next_tick_at = stamp(time.time() + INTERVAL) if self.enabled() else None
            self.execution.release()
        return changed

    def snapshot(self):
        try:
            self._load()
            context = self.context()
        except Exception as error:
            with self.lock:
                self.error = type(error).__name__
            context = None
        with self.lock:
            tasks = [dict(task) for task in self.tasks]
            saved_incidents = {k:dict(v) for k,v in self.incidents.items()}
            failed_departments = {row.get('department') for row in self.assignments.values()
                                  if row.get('status') == 'failed' and row.get('next_retry', 0) > time.time()}
            last, next_tick, error = self.last_tick_at, self.next_tick_at, self.error
        enabled = self.enabled()
        worker_running = alive(self.thread)
        skills = yt_skills.snapshot()
        learning = ai_office_learning.snapshot(self._learning_root())
        departments = []
        def department(key, name, role, enabled, working, running, detail):
            state = ('working' if working else 'disabled' if not enabled else
                     'degraded' if not running or key in failed_departments else 'waiting')
            departments.append(dict(id=key, name=name, role=role, state=state,
                                    detail=detail, active_count=working))
        if context is not None:
            c = context
            department('production', 'Produksi & riset', 'Memilih sumber dan memproduksi Short serta Long.',
                       c['cron_enabled'], c['jobs'], c['cron_alive'],
                       f"{c['jobs']} pekerjaan video aktif atau mengantre." if c['jobs'] else
                       'Menunggu jadwal, kapasitas, atau sumber yang memenuhi syarat.' if c['cron_enabled'] else
                       'Produksi otomatis dijeda sesuai setelan operator.')
            quality_enabled = c['cron_enabled'] or c['generic_enabled'] or c['facebook']['enabled']
            quality_running = c['cron_alive'] or c['generic_alive'] or c['facebook']['worker_running']
            department('quality', 'QC & perbaikan', 'Memeriksa hasil; perbaikan sekali, lalu lolos atau dibuang.',
                       quality_enabled, c['quality'], quality_running,
                       f"{c['quality']} audit atau perbaikan aktif; kelulusan wajib dibuktikan.")
            distribution_enabled = c['cron_enabled'] or c['generic_enabled'] or bool(c['uploads'])
            department('distribution', 'Distribusi', 'Menjalankan antrean yang disetujui dan memverifikasi posting.',
                       distribution_enabled, c['uploads'], True,
                       f"{c['uploads']} upload aktif atau mengantre; ID posting tetap dipertahankan.")
            recovery_enabled = c['attention_enabled'] or c['retry_enabled']
            recovery_running = ((not c['attention_enabled'] or c['attention_alive'])
                                and (not c['retry_enabled'] or c['retry_alive']))
            checking = int(self.api.upload_attention_service.execution.locked())
            department('recovery', 'Pemulihan', 'Mencocokkan bukti dan mengulang kegagalan yang aman.',
                       recovery_enabled, checking, recovery_running,
                       f"{c['unverified']} catatan belum terkonfirmasi; jadwal retry dan bukti tetap diperiksa.")
            department('cleanup', 'Kebersihan', 'Mengarsipkan penolakan dan membersihkan hasil terminal.',
                       c['attention_enabled'] or c['cron_enabled'] or c['generic_enabled'], c['cleanups'],
                       c['attention_alive'] or c['cron_alive'] or c['generic_alive'],
                       'Cleanup mengikuti keputusan penolakan; file pekerjaan aktif tetap dilindungi.')
            fb = c['facebook']
            departments.append(dict(id='facebook', name='Facebook Studio',
                role='Mengelola produksi, QC, dan antrean Facebook.', state=fb['state'],
                detail=fb['detail'], active_count=fb['active_count']))
            activity_by_id = {row['id']: row for row in c['activity']['departments']}
            for row in departments:
                observed = activity_by_id[row['id']]
                row.update(active_count=observed['running_count'], queued_count=observed['queued_count'],
                           blocked_count=observed['blocked_count'], detail=observed['detail'])
                if observed['available']:
                    row['state'] = ('working' if observed['running_count'] else 'disabled' if observed['state'] == 'paused'
                                    else 'degraded' if row['state'] == 'degraded' else 'waiting')
        degraded = bool(error or (enabled and not worker_running)
                        or any(row['state'] == 'degraded' for row in departments))
        state = ('disabled' if not enabled else 'starting' if last is None and not error else
                 'degraded' if degraded else 'working' if any(row['state'] == 'working' for row in departments) else 'waiting')
        labels = dict(disabled='Koordinator dijeda', starting='Menyiapkan Kantor AI', degraded='Koordinator perlu pemulihan',
                      working='Kantor AI sedang bekerja', waiting='Kantor AI memantau')
        live_incidents = context['incidents'] if context is not None else []
        incident_rows = [{**row, 'first_seen_at': saved_incidents.get(row['id'], {}).get('first_seen_at'),
                         'last_seen_at': saved_incidents.get(row['id'], {}).get('last_seen_at')} for row in live_incidents[:ai_office_incidents.LIMIT]]
        return dict(version=VERSION, control_version=2, enabled=enabled, worker_running=worker_running, state=state, label=labels[state],
                    detail=('Koordinator dijeda; worker mengikuti jadwal dan setelan masing-masing.' if not enabled else
                            f'Pemeriksaan koordinator mengalami {error}; state dan pengaman tetap dipertahankan.' if error else
                            'Koordinator membagi arahan ke worker yang ada. QC, jadwal, dan konfirmasi platform tetap menentukan hasil.'),
                    last_tick_at=last, next_tick_at=next_tick if enabled else None,
                    departments=departments, tasks=tasks,
                    activity=context['activity'] if context is not None else dict(version=ai_office_activity.VERSION,
                        available=False, observed_at=stamp(), departments=[]),
                    incidents=incident_rows, incident_observation_available=context is not None,
                    resolved_incidents=[r for r in saved_incidents.values() if r['state'] == 'resolved'][-12:],
                    director=dict(version=ai_office_director.VERSION, name=self.strategy['name'],
                        role=self.strategy['role'], model='digital_leader',
                        supervision='supervised_existing_workers',
                        strategy=self.strategy, directives=list(self.directives),
                        strategy_revision=ai_office_director.revision(self.strategy),
                        directives_at=self.directive_at,
                        skills_version=yt_skills.VERSION,
                        skills_applied=skills['applied'],
                        skills_total=skills['total'],
                        learning=learning,
                        active_jobs=(context or {}).get('jobs', 0),
                        active_uploads=(context or {}).get('uploads', 0),
                        open_incidents=len(live_incidents), needs_operator=sum(r['state'] == 'needs_operator' for r in live_incidents)),
                    journal_ready=self.loaded and error is None,
                    capabilities=dict(supervised_workers=True, persisted_decisions=True, operator_settings_preserved=True,
                                      publication_gates_preserved=True, no_parallel_production_owner=True,
                                      incident_ownership=True, observed_resolution=True, safe_delegate_only=True,
                                      autonomous_recovery=True, configured_qc_fallback=True,
                                      digital_director=True, strategic_directives=True,
                                      organizational_learning=True, observed_queue_activity=True))

    def request_check(self):
        if not self.enabled():
            return False
        with self.lock:
            self.force_requested = True
        self.start()
        self.wakeup.set()
        return True

    def loop(self):
        while not self.stop.is_set() and self.enabled():
            self.wakeup.clear()
            with self.lock:
                force = self.force_requested
                self.force_requested = False
            self.run_once(force=force)
            self.wakeup.wait(INTERVAL)

    def start(self):
        if not self.enabled():
            return
        ai_office_learning.ensure_seed(self._learning_root())
        with self.start_lock:
            if alive(self.thread):
                return
            self.stop.clear()
            self.thread = threading.Thread(target=self.loop, daemon=True, name='ai-office-coordinator')
            self.thread.start()

    def shutdown(self):
        self.stop.set()
        self.wakeup.set()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=5)


def install(app, api):
    service = OfficeService(api)
    api.ai_office_service = service

    @app.get('/api/ai-office')
    def get_office():
        return service.snapshot()

    @app.post('/api/ai-office/run')
    def check_office():
        accepted = service.request_check()
        return dict(accepted=accepted, message='Arahan pemeriksaan dikirim ke koordinator.' if accepted else
                    'Koordinator dijeda sesuai setelan server.')

    @app.get('/api/ai-office/learning')
    def office_learning():
        ai_office_learning.ensure_seed(service._learning_root())
        return ai_office_learning.snapshot(service._learning_root())

    @app.post('/api/ai-office/learning')
    def record_learning(payload: dict):
        try:
            entry = ai_office_learning.record(payload, service._learning_root())
        except ValueError as exc:
            from fastapi import HTTPException
            raise HTTPException(422, str(exc)) from exc
        return dict(accepted=True, entry=entry)

    @app.get('/api/ai-office/yt-skills')
    def youtube_skills():
        return yt_skills.snapshot()

    @app.post('/api/ai-office/yt-skills/{skill_id}/run')
    def run_youtube_skill(skill_id: str, payload: dict | None = None):
        try:
            result = yt_skills.run(skill_id, payload)
        except ValueError as exc:
            from fastapi import HTTPException
            raise HTTPException(422, str(exc)) from exc
        return dict(id=skill_id, result=result)

    @app.post('/api/ai-office/strategy')
    def set_strategy(payload: dict):
        """The operator may refine the leader's focus; it cannot bypass worker gates."""
        try:
            strategy = ai_office_director.validate_strategy(payload)
        except ValueError as exc:
            from fastapi import HTTPException
            raise HTTPException(422, str(exc)) from exc
        with service.lock:
            service.strategy = strategy
            service.directives = []
            service.directive_at = None
            service.dirty = True
            service._save()
        service.wakeup.set()
        return dict(accepted=True, strategy=strategy, revision=ai_office_director.revision(strategy))

    app.add_event_handler('startup', service.start)
    app.add_event_handler('shutdown', service.shutdown)
    return service
