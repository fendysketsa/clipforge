"""Background adapter for safe upload reconciliation in the normal API startup."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

import automatic_retry
import upload_attention as policy


class AttentionService:
    def __init__(self, api):
        self.api = api
        self.store = policy.StateStore(api.YOUTUBE_UPLOADS_PATH.with_name('upload_attention.json'))
        self.wakeup = threading.Event()
        self.execution = threading.Lock()
        self.start_lock = threading.Lock()
        self.thread = None

    def enabled(self):
        return self.api.env_bool('UPLOAD_ATTENTION_AUTOMATIC_ENABLED', True)

    def records(self):
        a = self.api
        with a.youtube_uploads_lock:
            youtube = [item.model_dump(exclude={'performance_snapshots', 'clip_cleanup_step_details'}) for item in a.youtube_uploads.values()]
        with a.tiktok_uploads_lock:
            tiktok = [item.model_dump(exclude={'performance_snapshots'}) for item in a.tiktok_uploads.values()]
        return {'youtube': youtube, 'tiktok': tiktok}

    def retry_allowed(self, platform, row):
        if platform == 'tiktok':
            return bool(automatic_retry.tiktok_retry_reason(row.get('error'), row.get('logs', []),
                started=row.get('submission_started'), accepted=row.get('submission_accepted')))
        return bool(not policy.submitted(platform, row) and any(str(line).startswith('UPLOAD_FAILED_BEFORE_FILE_SELECTION:')
                    for line in row.get('logs', [])))

    def snapshot(self):
        now = time.time()
        records = self.records()
        saved = self.store.read()['items']
        items = []
        for platform, rows in records.items():
            for row in rows:
                if row.get('status') in {'running', 'queued'} or policy.confirmed(platform, row):
                    continue
                path = self.api.output_path_from_url(row['clip_url'])
                item = policy.decision(platform, row, rows, media_exists=bool(path and path.is_file()),
                                       retry_allowed=self.retry_allowed(platform, row),
                                       claim_confirmed=(platform == 'youtube' and self.api.youtube_upload_was_claimed(
                                           self.api.YouTubeUploadJob.model_validate(row))))
                if item:
                    items.append(policy.status(item, saved.get(item['id'], {}), now))
        return {'version': policy.VERSION, 'rejected_upload_cleanup_version': policy.REJECTION_CLEANUP_VERSION,
                'terminal_claim_action': 'DROP_SOURCE', 'rejected_upload_archive': True, 'enabled': self.enabled(),
                'worker_running': bool(self.thread and self.thread.is_alive()), 'items': items}

    def current(self, platform, key):
        a = self.api
        lock = a.youtube_uploads_lock if platform == 'youtube' else a.tiktok_uploads_lock
        records = a.youtube_uploads if platform == 'youtube' else a.tiktok_uploads
        with lock:
            return records.get(key)

    def unchanged(self, row, item):
        return bool(row and policy.evidence_revision(row.model_dump()) == item['revision']
                    and row.status not in {'queued', 'running'} and not row.dry_run)

    def reconcile_duplicate(self, item):
        a = self.api; platform = item['platform']
        creation = a.youtube_upload_creation_lock if platform == 'youtube' else a.tiktok_upload_creation_lock
        lock = a.youtube_uploads_lock if platform == 'youtube' else a.tiktok_uploads_lock
        records = a.youtube_uploads if platform == 'youtube' else a.tiktok_uploads
        with creation:
            with lock:
                live = records.get(item['upload_id'])
                duplicate = records.get(item['duplicate_id'])
                if (not self.unchanged(live, item) or not duplicate
                        or not policy.duplicate_for(platform, live.model_dump(), [duplicate.model_dump()])):
                    return False
                changes = dict(status='completed', upload_confirmed=True, error=None,
                    updated_at=a.now_iso(), finished_at=live.finished_at or a.now_iso(),
                    visibility=duplicate.visibility, logs=[*live.logs,
                    f'ATTENTION_DUPLICATE_RECONCILED:{duplicate.id}',
                    'Posting file yang sama sudah terverifikasi; tidak ada transfer atau publikasi ulang.'][-160:])
                if platform == 'youtube':
                    changes.update(video_url=duplicate.video_url, publish_at=duplicate.publish_at)
                else:
                    changes.update(profile_url=duplicate.profile_url, auto_retry_at=None, auto_retry_reason='')
                records[live.id] = live.model_copy(update=changes)
                (a.save_youtube_uploads_unlocked if platform == 'youtube' else a.save_tiktok_uploads_unlocked)()
        return True

    def observe(self, platform, upload):
        a = self.api
        payload = {'platform': platform, 'upload': upload.model_dump(),
                   'target_channel_id': a.os.environ.get('YOUTUBE_TARGET_CHANNEL_ID', a.DEFAULT_YOUTUBE_TARGET_CHANNEL_ID),
                   'target_handle': a.tiktok_target_handle()}
        with tempfile.TemporaryDirectory(prefix='clipforge-attention-') as temporary:
            path = Path(temporary) / 'input.json'
            path.write_text(json.dumps(payload))
            cdp = a.YOUTUBE_CDP_URL if platform == 'youtube' else a.TIKTOK_CDP_URL
            process = subprocess.Popen([sys.executable, str(a.BASE_DIR / 'upload_attention_remote.py'),
                '--input', str(path), '--cdp-url', cdp], cwd=a.BASE_DIR, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
            try:
                stdout, _ = process.communicate(timeout=115)
            except subprocess.TimeoutExpired:
                process.terminate()  # Give the reader time to close its owned tab.
                try:
                    process.communicate(timeout=7)
                except subprocess.TimeoutExpired:
                    process.kill(); process.communicate()
                return {'confirmed': False, 'message': 'Studio belum merespons; pemeriksaan akan diulang otomatis.'}
        lines = [line.partition(':')[2] for line in stdout.splitlines() if line.startswith('ATTENTION_PROOF:')]
        try:
            return json.loads(lines[-1]) if process.returncode == 0 and lines else {'confirmed': False}
        except (ValueError, TypeError):
            return {'confirmed': False}

    def proof_matches(self, platform, live, proof):
        a = self.api
        if not proof.get('confirmed'):
            return False
        if platform == 'youtube':
            actual = policy.youtube_id(proof.get('video_url'))
            checkpoint = policy.youtube_id(live.video_url)
            channel = a.os.environ.get('YOUTUBE_TARGET_CHANNEL_ID', a.DEFAULT_YOUTUBE_TARGET_CHANNEL_ID)
            return bool(actual and (not checkpoint or actual == checkpoint)
                and (checkpoint or proof.get('file_name_matched'))
                and proof.get('target_channel_id') == channel
                and proof.get('source') == 'authenticated_studio_exact_video'
                and policy.normalized_text(proof.get('title')) == policy.normalized_text(live.title)
                and proof.get('description_sha256') == policy.text_hash(live.description)
                and proof.get('visibility') in {'public', 'private', 'unlisted'}
                and (not live.publish_at or proof.get('visibility') == 'public'))
        expected_handle = a.tiktok_target_handle()
        exact = policy.tiktok_url(proof.get('video_url'), expected_handle)
        original = policy.tiktok_url(live.profile_url, expected_handle)
        return bool(exact and (not original or exact == original)
            and live.target_handle.casefold().lstrip('@') == expected_handle.casefold().lstrip('@')
            and proof.get('source') == 'authenticated_studio_exact_post'
            and proof.get('visibility') in {'public', 'only_you'}
            and proof.get('caption_sha256') == policy.caption_hash(live.caption))

    def apply_proof(self, item, proof):
        a = self.api; platform = item['platform']
        creation = a.youtube_upload_creation_lock if platform == 'youtube' else a.tiktok_upload_creation_lock
        lock = a.youtube_uploads_lock if platform == 'youtube' else a.tiktok_uploads_lock
        records = a.youtube_uploads if platform == 'youtube' else a.tiktok_uploads
        with creation:
            with lock:
                live = records.get(item['upload_id'])
                if not self.unchanged(live, item) or not self.proof_matches(platform, live, proof):
                    return False
                changes = dict(status='completed', upload_confirmed=True, error=None,
                    updated_at=a.now_iso(), finished_at=live.finished_at or a.now_iso(),
                    logs=[*live.logs, 'ATTENTION_REMOTE_CONFIRMED:'+proof['video_url'],
                        'ID dan metadata posting terverifikasi baca-saja; tidak ada upload atau perubahan privasi.'][-160:])
                if platform == 'youtube':
                    changes.update(video_url=proof['video_url'], visibility=proof['visibility'], publish_at=None)
                else:
                    changes.update(profile_url=proof['video_url'], visibility=proof['visibility'], auto_retry_at=None, auto_retry_reason='')
                records[live.id] = live.model_copy(update=changes)
                (a.save_youtube_uploads_unlocked if platform == 'youtube' else a.save_tiktok_uploads_unlocked)()
        return True

    def retry(self, item):
        a = self.api; platform = item['platform']
        live = self.current(platform, item['upload_id'])
        if not self.unchanged(live, item) or policy.submitted(platform, live.model_dump()):
            return False
        if platform == 'tiktok':
            return bool(a.queue_retryable_tiktok_uploads_once(upload_ids={live.id}))
        with a.youtube_upload_creation_lock:
            live = self.current(platform, item['upload_id'])
            if not self.unchanged(live, item):
                return False
            job, clip, _ = a.find_job_clip(live.source_job_id, live.clip_url)
            path = a.output_path_from_url(clip.url)
            if (not path or not path.is_file() or not live.clip_sha256
                    or a.file_sha256(path) != live.clip_sha256 or job.request.publication_review_required
                    or not (clip.is_correct or clip.render_qc_passed is True)
                    or a.youtube_monetization_preflight_issue(job, clip) or a.upload_media_duration_issue(path)):
                return False
            with a.youtube_uploads_lock:
                siblings = [row.model_dump() for row in a.youtube_uploads.values() if row.id != live.id and not row.dry_run]
            if any(policy.same_media(live.model_dump(), other) and (other['status'] in {'queued','running'}
                   or policy.submitted(platform, other) or policy.confirmed(platform, other)) for other in siblings):
                return False
            a.require_youtube_ready()
            a.set_youtube_upload(live.id, status='queued', error=None, started_at=None, finished_at=None,
                logs=[*live.logs, 'ATTENTION_SAFE_RETRY: file, hash dan QC cocok; pengiriman sebelumnya belum dimulai.'][-160:])
            a.queue_youtube_upload_jobs([self.current(platform, live.id)])
        return True

    def run_once(self):
        if not self.enabled() or not self.execution.acquire(blocking=False):
            return 0
        changed = 0
        try:
            snapshot = self.snapshot()
            records = self.records()
            # Local rejection cleanup needs no browser and cannot be starved by
            # old remote verification rows or a busy social upload session.
            for item in snapshot['items']:
                if item['action'] != 'drop_source':
                    continue
                live = self.current(item['platform'], item['upload_id'])
                if self.unchanged(live, item) and self.api.youtube_upload_was_claimed(live):
                    changed += int(self.api.schedule_claimed_clip_cleanup(live.id))
            if any(row['status'] in {'queued', 'running'} for rows in records.values() for row in rows):
                return changed
            for item in policy.due([item for item in snapshot['items'] if item['action'] != 'drop_source'], time.time())[:12]:
                platform = item['platform']; key = item['id']
                if item['action'] == 'reconcile_duplicate':
                    success = self.reconcile_duplicate(item)
                    if success:
                        self.store.update(key, revision=item['revision'], state='resolved', checked_at=time.time(),
                                          message='Diselaraskan dengan posting file yang sama yang sudah terverifikasi.')
                        changed += 1
                    continue
                if not self.api.social_upload_execution_lock.acquire(blocking=False):
                    break
                try:
                    live = self.current(platform, item['upload_id'])
                    if not self.unchanged(live, item):
                        continue
                    attempts = item['attempts'] + 1
                    now = time.time()
                    self.store.update(key, revision=item['revision'], state='checking', checked_at=now,
                                      attempts=attempts, next_check_at=now + 180,
                                      message='Sedang mencocokkan bukti di Studio secara otomatis.')
                    proof = {}
                    if item['action'] == 'verify_remote':
                        proof = self.observe(platform, live)
                        success = self.apply_proof(item, proof)
                    else:
                        success = self.retry(item)
                    changed += int(success)
                    self.store.update(key, revision=item['revision'], state='resolved' if success else 'waiting',
                        checked_at=time.time(), attempts=attempts, proof=proof if success else {},
                        next_check_at=time.time()+policy.BACKOFF[min(attempts-1,len(policy.BACKOFF)-1)],
                        message='Selesai ditangani otomatis.' if success else proof.get('message') or
                            'Bukti belum lengkap; pemeriksaan berikutnya dijadwalkan otomatis.')
                except Exception as error:
                    self.store.update(key, revision=item['revision'], state='waiting', checked_at=time.time(),
                        next_check_at=time.time()+300, message='Penanganan belum selesai; sistem mencoba lagi otomatis.',
                        error_type=type(error).__name__)
                finally:
                    self.api.social_upload_execution_lock.release()
                break  # At most one browser read/retry per cycle; production work has priority.
            return changed
        finally:
            self.execution.release()

    def request_check(self):
        if not self.enabled():
            return 0
        now = time.time()
        requested = 0
        for item in self.snapshot()['items']:
            if item['state'] != 'waiting':
                continue
            with self.store.lock:
                saved = self.store.read()['items'].get(item['id'], {})
                if saved.get('state') == 'checking' and now-float(saved.get('checked_at',0)) < 150:
                    continue
                self.store.update(item['id'], revision=item['revision'], state='waiting', next_check_at=now)
            requested += 1
        self.start()
        self.wakeup.set()
        return requested

    def loop(self):
        while self.enabled():
            try:
                self.run_once()
            except Exception as error:
                print('Penanganan upload ditunda: '+type(error).__name__, flush=True)
            self.wakeup.wait(timeout=30)
            self.wakeup.clear()

    def start(self):
        with self.start_lock:
            if not self.enabled() or (self.thread and self.thread.is_alive()):
                return
            self.thread = threading.Thread(target=self.loop, daemon=True, name='upload-attention')
            self.thread.start()
