#!/usr/bin/env python3
"""Upgrade local Short covers before their thumbnail transfer starts."""
import fcntl
import json
from pathlib import Path
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from shorts_thumbnail import VERSION, install_pack

DATA = ROOT / 'backend/data'


def api(path):
    with urllib.request.urlopen('http://127.0.0.1:8010' + path, timeout=15) as response:
        return json.load(response)


def transfer_not_started(job_id, clip_url, rows):
    for row in rows:
        if row.get('source_job_id') != job_id or row.get('clip_url') != clip_url or row.get('dry_run'):
            continue
        if row.get('upload_confirmed') or row.get('status') == 'completed':
            return False
        if any(marker in line for line in row.get('logs', []) for marker in (
            'Mengatur thumbnail otomatis', 'Transfer thumbnail dimulai', 'THUMBNAIL_ATTACHED:',
            'Thumbnail otomatis terpasang')):
            return False
    return True


def tick():
    uploads = api('/api/youtube/uploads')
    for job in api('/api/jobs'):
        if job.get('status') != 'completed' or job['request']['clip_mode'] != 'short':
            continue
        for clip in job.get('clips', []):
            if not transfer_not_started(job['id'], clip['url'], uploads):
                continue
            video = (ROOT / 'backend' / clip['url'].lstrip('/')).resolve()
            if ROOT / 'backend/outputs' not in video.parents or not video.is_file():
                continue
            sidecar = json.loads(video.with_suffix('.json').read_text())
            if (sidecar.get('thumbnail_curiosity') or {}).get('policy_version') == VERSION:
                continue
            result = install_pack(video, sidecar, may_publish=lambda: transfer_not_started(
                job['id'], clip['url'], api('/api/youtube/uploads')))
            if result:
                print('SHORT_THUMBNAIL_READY', job['id'], result['winner'], result['headline'], flush=True)
                return {'status':'thumbnail_ready', 'job_id':job['id'], **result}
    return {'status':'waiting_for_untransferred_short'}


def main():
    with (DATA / 'shorts-thumbnail-operator.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while True:
            try:
                result = tick()
                temp = DATA / 'shorts_thumbnail_operator_state.json.tmp'
                temp.write_text(json.dumps({**result, 'checked_epoch':time.time()}, ensure_ascii=False)+'\n')
                temp.replace(DATA / 'shorts_thumbnail_operator_state.json')
            except Exception as exc:
                print('SHORT_THUMBNAIL_RETRY', type(exc).__name__, flush=True)
            if '--once' in sys.argv:
                return
            time.sleep(3)


if __name__ == '__main__':
    main()
