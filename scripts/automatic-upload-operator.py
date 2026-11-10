#!/usr/bin/env python3
"""Durable, explicitly enabled Private intake; the API retains every media gate.

This operator does not approve editorial QC or public publication. Persist an
unknown-outcome reservation before POST so timeouts cannot cause retransmission.
"""
from __future__ import annotations
import fcntl
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'backend/data'
POLICY = DATA / 'automatic_upload_policy.json'
STATE = DATA / 'automatic_upload_operator.json'
PUBLIC_STATE = ROOT / 'backend/outputs/_automation/upload-status.json'
BASE = 'http://127.0.0.1:8010'


def request(path, payload=None):
    kwargs = {} if payload is None else dict(data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(urllib.request.Request(BASE + path, **kwargs), timeout=900 if payload is not None else 20) as response:
        return json.load(response)


def save(state):
    temp = STATE.with_suffix('.json.tmp')
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
    temp.replace(STATE)
    # The existing static output server exposes only this minimal progress
    # snapshot. Keep rights evidence, model findings and errors in data/.
    PUBLIC_STATE.parent.mkdir(parents=True, exist_ok=True)
    public = dict(checked_epoch=state.get('checked_epoch'), enabled=state.get('enabled'),
        clips=[{k: row.get(k) for k in ('source_job_id', 'clip_url', 'status')}
            for row in state.get('clips', {}).values()])
    temporary = PUBLIC_STATE.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(public) + '\n')
    temporary.replace(PUBLIC_STATE)


def key(job_id, url):
    return hashlib.sha256((job_id + '\n' + url).encode()).hexdigest()


def tick():
    policy = json.loads(POLICY.read_text()) if POLICY.exists() else {}
    if policy.get('enabled') is not True:
        if STATE.exists():
            state = json.loads(STATE.read_text()); state['enabled'] = False; save(state)
        return 'disabled'
    # Visibility cannot be broadened by a typo or unrelated configuration.
    if policy.get('visibility') != 'private':
        raise ValueError('Only explicitly approved Private intake is supported')
    state = json.loads(STATE.read_text()) if STATE.exists() else {'clips': {}}
    uploads = request('/api/youtube/uploads')
    jobs = request('/api/jobs')
    pending = []
    for job in sorted(jobs, key=lambda row: row['created_at']):
        if (job.get('status') != 'completed'
                or job['request']['clip_mode'] not in {'short', 'highlight_5m', 'long_animate'}):
            continue
        if not policy.get('follow_completed_jobs') and job['id'] not in policy.get('job_ids', []):
            continue
        for clip in job.get('clips', []):
            identity = key(job['id'], clip['url'])
            row = state['clips'].setdefault(identity, dict(source_job_id=job['id'], clip_url=clip['url'], status='pending'))
            exact = [u for u in uploads if u.get('source_job_id') == job['id']
                and u.get('clip_url') == clip['url'] and not u.get('dry_run')]
            verified = next((u for u in exact if u.get('status') == 'completed'
                and u.get('upload_confirmed') is True and u.get('video_url')), None)
            active = next((u for u in exact if u.get('status') in {'queued', 'running'}), None)
            existing = verified or active
            if existing:
                row.update(status='verified' if verified else existing['status'], upload_id=existing['id'],
                    video_url=existing.get('video_url'), upload_outcome_unknown=False, error=None)
                continue
            if exact:
                # A failed record may already own a remote file. Reconciliation
                # belongs to the backend's same-ID verification path.
                row.update(status='needs_remote_verification', upload_id=exact[0]['id'],
                    video_url=exact[0].get('video_url'), error=exact[0].get('error'))
                recoverable = next((u for u in exact if u.get('status') == 'failed'
                    and u.get('video_url') and u.get('storage_state_verification_attempted') is False
                    and any(text in (u.get('error') or '').casefold() for text in (
                        'dialog-not-found', 'modal upload tidak ditemukan', 'studio gagal memuat aplikasi'))), None)
                # Older backends do not expose this capability. Once the tested
                # backend fix is active, request its same-ID verification once.
                # The backend owns saved-session fallback; never select a file.
                if (recoverable and not row.get('verification_requested')
                        and not row.get('upload_outcome_unknown')
                        and not any(str(line).startswith(('CLAIMED_UPLOAD_ABORTED:', 'CLAIM_ABORT:')) for u in exact for line in u.get('logs', []))):
                    pending.append((job, clip, row, recoverable['id']))
                continue
            if row.get('upload_outcome_unknown') or row.get('upload_id'):
                row['status'] = 'needs_remote_verification'
                continue
            if (job['request'].get('clip_mode') == 'highlight_5m'
                    and job['request'].get('publication_review_required')):
                # Native Long QC owns both platforms; do not bypass its hold.
                row.update(status='waiting_for_long_qc', error=None)
                continue
            if row.get('retry_after_epoch', 0) > time.time():
                continue
            if clip.get('youtube_upload_ready') is False:
                row.update(status='preflight_hold', error=clip.get('youtube_upload_issue') or 'Upload preflight not ready')
                continue
            pending.append((job, clip, row, None))
    state.update(checked_epoch=time.time(), enabled=True, visibility='private')
    save(state)
    if any(u.get('status') in {'queued', 'running'} and not u.get('dry_run') for u in uploads):
        return 'waiting_for_upload_queue'
    # One submission per tick: let the durable backend queue finish each file.
    if pending:
        job, clip, row, verification_id = pending[0]
        row.update(status='submitting', upload_outcome_unknown=True)
        if verification_id:
            row['verification_requested'] = True
        save(state)
        try:
            result = request('/api/jobs/' + job['id'] + '/youtube-uploads',
                {'clip_url': clip['url'], 'visibility': 'private'})
            if verification_id and result['id'] != verification_id:
                raise ValueError('Verification must preserve the existing upload ID')
            row.update(status=result['status'], upload_id=result['id'],
                video_url=result.get('video_url'), upload_outcome_unknown=False, error=None)
            print('PRIVATE_INTAKE_QUEUED', job['id'], result['id'], flush=True)
        except urllib.error.HTTPError as exc:
            # A 4xx preflight rejection did not accept the mutation. A 5xx may
            # have occurred after acceptance and must retain its reservation.
            definite = 400 <= exc.code < 500
            detail = exc.read(8192).decode(errors='replace')
            row.update(status='preflight_hold' if definite else 'needs_remote_verification',
                error=detail, upload_outcome_unknown=not definite, retry_after_epoch=time.time() + 900)
            print('PRIVATE_INTAKE_HELD', job['id'], exc.code, flush=True)
        except Exception as exc:
            row.update(status='needs_remote_verification', error=type(exc).__name__)
            print('PRIVATE_INTAKE_OUTCOME_UNKNOWN', job['id'], type(exc).__name__, flush=True)
        save(state)
        return 'processed'
    return 'watching_completed_jobs'


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    with (DATA / 'automatic-upload-operator.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while True:
            try:
                print('PRIVATE_INTAKE_STATUS', tick(), flush=True)
            except Exception as exc:
                print('PRIVATE_INTAKE_RETRY', type(exc).__name__, flush=True)
            if '--once' in __import__('sys').argv:
                return
            time.sleep(30)


if __name__ == '__main__':
    main()
