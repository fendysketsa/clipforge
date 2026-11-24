"""Read-only projection of actual queues. Never dispatch, infer QC approval or publish."""
from __future__ import annotations

from datetime import datetime, timezone
import math
import re

from source_download import redact

VERSION = 1
DEPARTMENTS = ('production', 'quality', 'distribution', 'recovery', 'cleanup', 'facebook')
STAGES = {
    'queued': 'Menunggu giliran', 'source': 'Menyiapkan sumber', 'download': 'Mengunduh sumber',
    'transcribe': 'Mentranskripsi', 'transcription': 'Mentranskripsi', 'analysis': 'Menganalisis sumber',
    'analyze': 'Menganalisis sumber', 'selection': 'Memilih klip', 'render': 'Merender video',
    'rendering': 'Merender video', 'qc': 'Memeriksa kualitas', 'quality_control': 'Memeriksa kualitas',
    'quality_repair': 'Memperbaiki hasil', 'upload': 'Mengirim video', 'youtube_upload': 'Mengirim ke YouTube',
    'social_upload': 'Distribusi platform', 'waiting_upload': 'Menunggu distribusi',
    'resume_pending_upload': 'Menunggu pemulihan distribusi', 'cron_capacity_wait': 'Menunggu kapasitas',
    'daily_upload_limit': 'Menunggu kuota harian', 'youtube_platform_daily_limit': 'Menunggu kuota YouTube',
    'retry_upload': 'Menunggu retry distribusi', 'preflight': 'Memeriksa kelayakan sumber',
    'trend_discovery': 'Mencari sumber', 'fallback_discovery': 'Mencari sumber cadangan',
}
WAIT_STAGES = {'waiting_upload', 'resume_pending_upload', 'cron_capacity_wait', 'daily_upload_limit',
               'youtube_platform_daily_limit', 'retry_upload'}
QC_STAGES = {'qc', 'quality_control', 'quality_repair', 'audit', 'clip_qc', 'clip_quality_control'}


def title(value, fallback):
    return re.sub(r'\s+', ' ', redact(str(value or fallback))).strip()[:160]


def percent(value):
    return min(100, max(0, value)) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def observe(api, context):
    rows = {key: [] for key in DEPARTMENTS}
    with api.jobs_lock:
        jobs = {key: dict(id=key, status=getattr(job, 'status', ''),
            title=title(getattr(job, 'source_title', ''), 'Video ' + key[:8]),
            stage=getattr(job, 'progress_stage', '') or '', progress=percent(getattr(job, 'progress_percent', None)),
            repair=bool(getattr(job, 'repair_source_job_id', None)),
            facebook=getattr(getattr(job, 'request', None), 'target_platform', '') == 'facebook',
            updated_at=getattr(job, 'updated_at', None)) for key, job in api.jobs.items()}
    with api.long_qc_lock:
        long_qc = {str(key).split('\n', 1)[0] for key in api.long_qc_active}

    def item(identity, state, text, stage, *, job_id=None, upload_id=None, platform=None, progress=None, kind='production'):
        return dict(id=identity, state=state, title=text, stage=stage, progress_percent=progress,
                    job_id=job_id, upload_id=upload_id, platform=platform, kind=kind,
                    destination='facebook' if platform == 'facebook' else 'history')

    for key, job in jobs.items():
        if job['status'] not in {'queued', 'running'} and key not in long_qc:
            continue
        quality = key in long_qc or job['repair'] or job['stage'] in QC_STAGES
        department = 'quality' if quality else 'facebook' if job['facebook'] else 'production'
        state = 'running' if key in long_qc else 'queued' if job['status'] == 'queued' or job['stage'] in WAIT_STAGES else 'running'
        # The pipeline may own a parent cron job while it waits for an upload.
        if job['stage'] in WAIT_STAGES:
            department = 'distribution'
        stage = 'Memeriksa kualitas Long' if key in long_qc else STAGES.get(job['stage'], 'Memperbaiki hasil' if job['repair'] else 'Memproses video')
        rows[department].append(item('job:' + key, state, job['title'], stage, job_id=key,
            platform='facebook' if job['facebook'] else None, progress=job['progress'] if state == 'running' else None,
            kind='qc' if quality else 'production'))

    for platform in ('youtube', 'tiktok'):
        with getattr(api, platform + '_uploads_lock'):
            for key, upload in getattr(api, platform + '_uploads').items():
                if getattr(upload, 'dry_run', False) or getattr(upload, 'attention_archived_at', None):
                    continue
                state = getattr(upload, 'status', '')
                if state not in {'queued', 'running'} or getattr(upload, 'upload_confirmed', False):
                    continue
                job_id = getattr(upload, 'source_job_id', None)
                text = title(getattr(upload, 'title', None) or getattr(upload, 'clip_name', None), platform.title() + ' ' + key[:8])
                rows['distribution'].append(item(platform + ':' + key, state, text,
                    ('Mengirim ke ' if state == 'running' else 'Antrean ') + platform.title(),
                    job_id=job_id, upload_id=key, platform=platform, kind='upload'))
    # Long QC may be active for a record that disappeared between two snapshots.
    for key in long_qc - jobs.keys():
        rows['quality'].append(item('qc:' + key, 'running', 'Audit Long ' + key[:8], 'Memeriksa kualitas Long', job_id=key, kind='qc'))

    fb = context['facebook']
    for row in fb.get('activity_work', []):
        # The main jobs dictionary already owns production and QC status.
        if row['kind'] == 'production' and (jobs.get(row.get('job_id'), {}).get('status') in {'queued', 'running'} or row.get('job_id') in long_qc):
            continue
        rows['facebook'].append(item(row['id'], row['state'], title(row.get('title'), 'Facebook'),
            row['stage'], job_id=row.get('job_id'), upload_id=row.get('upload_id'), platform='facebook', kind=row['kind']))

    # A scheduled cleanup is pending, not evidence that a deletion is executing.
    with api.claimed_clip_cleanup_lock:
        cleanups = list(api.claimed_clip_cleanup_scheduled)
    for key in sorted(cleanups):
        rows['cleanup'].append(item('cleanup:' + key, 'queued', 'Aset ' + key[:8], 'Menunggu file bebas dari transfer', upload_id=key, kind='cleanup'))
    if api.terminal_output_cleanup_lock.locked():
        rows['cleanup'].append(item('cleanup:terminal', 'running', 'Pemeliharaan aset', 'Membersihkan hasil terminal', kind='cleanup'))
    if api.upload_attention_service.execution.locked():
        rows['recovery'].append(item('recovery:inspection', 'running', 'Verifikasi pengiriman', 'Memeriksa bukti platform', kind='verification'))

    upload_jobs = {row['job_id'] for row in rows['distribution'] if row['kind'] == 'upload' and row['job_id']}
    rows['distribution'] = [row for row in rows['distribution'] if row['kind'] == 'upload' or row['job_id'] not in upload_jobs]

    represented = {row['job_id'] for work in rows.values() for row in work if row['job_id']}
    represented.update(row['upload_id'] for work in rows.values() for row in work if row['upload_id'])
    for incident in context['incidents']:
        if incident.get('action') == 'worker_supervision':
            continue
        if incident.get('severity') == 'info' and not incident.get('job_id') and not incident.get('upload_id'):
            continue
        if incident.get('job_id') in represented or incident.get('upload_id') in represented:
            continue
        department = incident['department']
        if department in rows:
            rows[department].append(item('incident:' + incident['id'], 'blocked',
                title(incident.get('title'), 'Pekerjaan tertahan'),
                'Perlu keputusan Anda' if incident['state'] == 'needs_operator' else 'Menunggu pemulihan',
                job_id=incident.get('job_id'), upload_id=incident.get('upload_id'),
                platform='facebook' if department == 'facebook' else None, kind='verification'))

    enabled = dict(production=context['cron_enabled'], quality=context['cron_enabled'] or context['generic_enabled'] or fb['enabled'],
        distribution=context['cron_enabled'] or context['generic_enabled'], recovery=context['attention_enabled'] or context['retry_enabled'],
        cleanup=context['attention_enabled'] or context['cron_enabled'] or context['generic_enabled'], facebook=fb['enabled'])
    departments = []
    for key, work in rows.items():
        running, queued, blocked = (sum(row['state'] == state for row in work) for state in ('running', 'queued', 'blocked'))
        available = key != 'facebook' or fb.get('activity_available') is True
        state = 'unavailable' if not available else 'running' if running else 'queued' if queued else 'blocked' if blocked else 'idle' if enabled[key] else 'paused'
        detail = f'{running} berjalan · {queued} mengantre' if running or queued else f'{blocked} pekerjaan tertahan' if blocked else 'Tidak ada pekerjaan aktif' if state == 'idle' else 'Otomasi dijeda' if state == 'paused' else 'Menunggu data aktivitas'
        work.sort(key=lambda row: ({'running': 0, 'queued': 1, 'blocked': 2}[row['state']], row['id']))
        departments.append(dict(id=key, state=state, available=available, running_count=running,
            queued_count=queued, blocked_count=blocked, detail=detail, work=work[:8], total_count=len(work)))
    return dict(version=VERSION, available=True, observed_at=datetime.now(timezone.utc).isoformat(), departments=departments)
