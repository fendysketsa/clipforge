#!/usr/bin/env python3
"""Run the approved Long reviewer through the live API without a backend restart."""
from __future__ import annotations

import fcntl
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.request
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import long_video_qc as qc
from source_rights import source_rights_risk_reasons

BASE = 'http://127.0.0.1:8010'
DATA = ROOT / 'backend/data'
REVIEWS = DATA / 'long_review_qc'


def request(path, payload=None):
    kwargs = {} if payload is None else dict(data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(urllib.request.Request(BASE + path, **kwargs), timeout=90) as response:
        return json.load(response)


def save(path, record):
    temp = path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def replace_rejected_long(policy, jobs):
    """Old backends count failed QC renders as successes; backfill once, capped at 3/day."""
    if not policy.get('enabled') or any(j.get('status') in {'queued', 'running'} for j in jobs):
        return 'waiting_for_completed_long'
    day = datetime.now(ZoneInfo('Asia/Jakarta')).date().isoformat()
    today = [row for row in policy.get('attempts', []) if row.get('day') == day]
    if not today or len(today) >= 3:
        return 'waiting_for_completed_long'
    reviews = [json.loads(path.read_text()) for path in REVIEWS.glob('*.json')]
    decisions = {row.get('source_job_id'): (row.get('audit') or {}).get('decision') for row in reviews}
    if not all(decisions.get(row.get('job_id')) in {'DROP_SOURCE', 'REPAIR_ONCE'} for row in today):
        return 'waiting_for_completed_long'
    marker = DATA / 'long_qc_replacement_reservation.json'
    previous = json.loads(marker.read_text()) if marker.exists() else {}
    if previous.get('day') == day and previous.get('attempt_count') == len(today):
        return 'replacement_reserved'
    save(marker, {'day': day, 'attempt_count': len(today), 'outcome': 'reserved'})
    path = '/api/automation/viral-cc/long-production'
    try:
        result = request(path, {'enabled': True, 'daily_target': min(3, len(today) + 1)})
        save(marker, {'day': day, 'attempt_count': len(today), 'production': result.get('production')})
        print('REJECTED_LONG_REPLACEMENT', result.get('production'), flush=True)
    finally:
        request(path, {'enabled': policy['enabled'], 'daily_target': policy['daily_target']})
    return 'replacement_requested'


def tick():
    # The host worker yields ownership once the deployed backend exposes its
    # own enabled QC worker. No two processes should operate the same lane.
    policy = request('/api/automation/viral-cc/long-production')
    if policy.get('auto_qc_enabled'):
        return 'backend_owns_qc'
    uploads = request('/api/youtube/uploads')
    jobs = request('/api/jobs')
    for job in jobs:
        if (job.get('status') != 'completed' or job['request']['clip_mode'] != 'highlight_5m'
                or not job['request'].get('publication_review_required')):
            continue
        for clip in job.get('clips', []):
            key = hashlib.sha256((job['id'] + '\n' + clip['url']).encode()).hexdigest()
            path = REVIEWS / (key + '.json')
            record = json.loads(path.read_text()) if path.exists() else {}
            if record.get('upload_id') or record.get('upload_outcome_unknown'):
                continue
            if record.get('next_retry_epoch', 0) > time.time():
                continue
            media = (ROOT / 'backend' / clip['url'].lstrip('/')).resolve()
            if ROOT / 'backend/outputs' not in media.parents:
                continue
            exact = [row for row in uploads if row.get('source_job_id') == job['id']
                     and row.get('clip_url') == clip['url'] and not row.get('dry_run')]
            # Any persisted upload outcome owns this exact clip; never create
            # an unattended replacement of an unknown/failed remote object.
            if exact:
                continue
            metadata_path = media.parent.parent / 'metadata.json'
            metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
            req = job['request']
            context = dict(source_job_id=job['id'], source_clip_url=clip['url'],
                source_url=job.get('source_url') or req['url'],
                rights_confirmed=req.get('confirm_source_rights') is True,
                rights_evidence=req.get('source_rights_evidence', ''),
                rights_risks=source_rights_risk_reasons(metadata), claim_block=None,
                news_hot=req.get('scheduled_news_hot', False),
                repair_attempted=bool(job.get('repair_source_job_id') or job.get('repair_source_clip_url')
                    or any(line.startswith('AUTO_REPAIR_ATTEMPTED:') for line in job.get('logs', []))),
                score_floor_met=(clip.get('fyp_score') or 0) >= 80 and clip.get('growth_quality_gate_passed') is not False)
            signature = qc.fingerprint(media, context)
            if record.get('fingerprint') != signature or record.get('status') != 'reviewed':
                print('QC_STARTED', job['id'], flush=True)
                result = qc.audit_long(media, context)
                record = dict(result, source_job_id=job['id'], source_clip_url=clip['url'],
                              fingerprint=signature, updated_epoch=time.time())
                if result['status'] != 'reviewed':
                    record['next_retry_epoch'] = time.time() + 600
                save(path, record)
                print('QC_RESULT', job['id'], result.get('status'),
                      (result.get('audit') or {}).get('decision'), flush=True)
            audit = record.get('audit') or {}
            if audit.get('decision') != 'PASS_UPLOAD' or audit.get('upload_allowed') is not True:
                continue
            if qc.fingerprint(media, context) != signature:
                continue
            # Read live state again immediately before the upload mutation.
            current = request('/api/jobs/' + job['id'])
            if current.get('status') != 'completed' or current['request'] != req:
                continue
            if any(row.get('source_job_id') == job['id'] and row.get('clip_url') == clip['url']
                   and not row.get('dry_run') for row in request('/api/youtube/uploads')):
                continue
            record['upload_outcome_unknown'] = True
            save(path, record)
            try:
                uploaded = request('/api/jobs/' + job['id'] + '/youtube-uploads',
                    {'clip_url': clip['url'], 'visibility': 'private'})
                record.update(upload_id=uploaded['id'], upload_visibility=uploaded['visibility'],
                              upload_outcome_unknown=False)
                save(path, record)
                print('PRIVATE_UPLOAD_QUEUED', job['id'], uploaded['id'], flush=True)
            except Exception as exc:
                # Even a timeout after acceptance must never trigger reupload.
                record['upload_error'] = type(exc).__name__
                save(path, record)
                print('UPLOAD_HELD_FOR_RECONCILIATION', job['id'], type(exc).__name__, flush=True)
            return 'reviewed'
    return replace_rejected_long(policy, jobs)


def main():
    REVIEWS.mkdir(parents=True, exist_ok=True)
    with (DATA / 'long-qc-operator.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while True:
            try:
                status = tick()
                save(DATA / 'long_qc_operator_state.json', {'status': status, 'checked_epoch': time.time()})
                if status == 'backend_owns_qc':
                    return
            except Exception as exc:
                print('QC_OPERATOR_RETRY', type(exc).__name__, flush=True)
            if '--once' in sys.argv:
                return
            time.sleep(30)


if __name__ == '__main__':
    main()
