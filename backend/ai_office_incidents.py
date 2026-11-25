"""Observe studio blockers without approving media, replaying Post or editing settings."""
from __future__ import annotations

import hashlib
import re

from automatic_retry import MAX_RETRIES, tiktok_retry_reason, tiktok_submission_possible
from autonomous_history import terminal_failure_reason

VERSION = 2
LIMIT = 100


def detect(api, context):
    incidents = []

    def add(identity, department, title, reason, action, *, automatic=False,
            state='waiting', severity='warning', job_id=None, upload_id=None):
        row = dict(id=identity, department=department, title=title[:180], reason=reason,
            action=action, automatic=automatic, state=state, severity=severity,
            job_id=job_id, upload_id=upload_id,
            destination='settings' if state == 'needs_operator' and action == 'restore_access' else 'history')
        row['revision'] = hashlib.sha256(repr(sorted(row.items())).encode()).hexdigest()[:20]
        incidents.append(row)

    with api.jobs_lock:
        jobs = list(api.jobs.items())
    records = {}
    for platform in ('youtube', 'tiktok'):
        with getattr(api, platform + '_uploads_lock'):
            records[platform] = list(getattr(api, platform + '_uploads').items())
    owned = {getattr(row, 'source_job_id', '') for rows in records.values() for _, row in rows
             if not getattr(row, 'dry_run', False)}
    for identity, job in jobs:
        status = getattr(job, 'status', '')
        request = getattr(job, 'request', None)
        if getattr(request, 'target_platform', 'standard') == 'facebook':
            continue
        clips = getattr(job, 'clips', []) or []
        title = re.sub(r'\s+', ' ', str(getattr(job, 'source_title', '') or 'Produksi ' + identity[:8]))
        if status == 'failed':
            message = str(getattr(job, 'error', '') or '').casefold()
            if any(word in message for word in ('login', 'verifikasi dan sesi', 'captcha')):
                add('job:' + identity, 'production', title,
                    'Sumber belum dapat diakses dengan sesi tersimpan. Akses perlu dipulihkan sebelum produksi diulang.',
                    'restore_access', state='needs_operator', job_id=identity)
            else:
                cleanup = bool(not clips and not getattr(job, 'candidates', [])
                    and getattr(request, 'scheduled_public_source_credit', False)
                    and not getattr(request, 'review_only', False)
                    and terminal_failure_reason(dict(error=getattr(job, 'error', ''),
                        progress_detail=getattr(job, 'progress_detail', ''), logs=getattr(job, 'logs', []))))
                add('job:' + identity, 'cleanup' if cleanup else 'production', title,
                    'Produksi gagal sebelum ada hasil video; worker memeriksa apakah percobaan kosong dapat diarsipkan.'
                    if cleanup else 'Produksi gagal. Hasil dan bukti yang tersisa dipertahankan untuk pemeriksaan penyebab.',
                    'cleanup_history' if cleanup else 'inspect_production',
                    automatic=bool(cleanup and api.env_bool('AUTO_UPLOAD_TERMINAL_CLEANUP_ENABLED', True)), job_id=identity)
        elif status == 'completed' and clips:
            if getattr(request, 'publication_review_required', False) or any(getattr(c, 'render_qc_blocking', False) for c in clips):
                long_review = (getattr(request, 'clip_mode', '') == 'highlight_5m'
                               and callable(getattr(api, 'queue_review_long_qc_once', None)))
                quarantine = callable(getattr(api, 'defer_job_for_manual_review', None))
                add('job:' + identity, 'quality', title,
                    ('Worker QC diminta mengaudit ulang hasil ini; kelulusan tetap harus dibuktikan dan upload tetap ditahan.'
                     if long_review else
                     'Hasil ditahan untuk review manusia dan dikeluarkan dari unggah otomatis; QC tidak disetujui otomatis.'
                     if quarantine else
                     'Hasil tersedia, tetapi pemeriksaan kualitas atau review publikasi belum selesai. Upload tetap ditahan.'),
                    'review_quality' if long_review else 'defer_manual_review' if quarantine else 'review_quality',
                    automatic=bool(long_review or quarantine), job_id=identity)
            elif (identity not in owned and getattr(request, 'scheduled_public_source_credit', False)
                  and not getattr(request, 'review_only', False)):
                add('job:' + identity, 'distribution', title,
                    'Hasil cron belum memiliki catatan upload. Worker distribusi akan memeriksa seluruh syarat sebelum mengantrekan.',
                    'recover_scheduled_uploads', automatic=bool(context['cron_enabled']), severity='info', job_id=identity)
    for platform, rows in records.items():
        for identity, row in rows:
            if (getattr(row, 'dry_run', False) or getattr(row, 'attention_archived_at', None)
                    or getattr(row, 'status', '') not in {'failed', 'cancelled'}):
                continue
            logs = getattr(row, 'logs', []) or []
            error = str(getattr(row, 'error', '') or '')
            if getattr(row, 'upload_confirmed', False):
                continue
            possible = (tiktok_submission_possible(logs,
                started=getattr(row, 'submission_started', False), accepted=getattr(row, 'submission_accepted', False))
                or bool(getattr(row, 'profile_url', None))) if platform == 'tiktok' else bool(
                    getattr(row, 'file_selection_started', False) or getattr(row, 'video_url', None)
                    or any(str(line).startswith(('Video dipilih:', 'REMOTE_UPLOAD_CHECKPOINT')) for line in logs))
            exhausted = getattr(row, 'auto_retry_count', 0) >= MAX_RETRIES or getattr(row, 'resume_existing_draft_only', False)
            retry = platform == 'tiktok' and not exhausted and tiktok_retry_reason(error, logs,
                started=getattr(row, 'submission_started', False), accepted=getattr(row, 'submission_accepted', False))
            access = any(word in error.casefold() for word in ('login', 'captcha', 'session tidak valid'))
            # An unconfirmed upload is never assumed published. The attention
            # owner may still reconcile remote identity locally; it does not
            # replay a Post or change the upload record.
            reconcile = not access and bool(context['attention_enabled'])
            add(platform + ':' + identity, 'recovery', platform.title() + ' · ' + str(getattr(row, 'clip_name', '') or identity[:8]),
                'Posting mungkin sudah dikirim. Worker mencocokkan identitas remote sebelum memutuskan langkah berikutnya.' if possible else
                'Koneksi atau form upload terhenti sebelum Post. Percobaan yang sama mengikuti batas retry dan pemeriksaan file.' if retry else
                'Akses akun perlu dipulihkan. Sesi dan catatan upload tetap dipertahankan.' if access else
                'Batas retry transfer tercapai atau draf yang sama harus dipulihkan. Percobaan baru tidak dibuat otomatis.' if exhausted else
                'Upload belum terkonfirmasi. Bukti percobaan diperiksa; pengiriman baru tidak diasumsikan aman.',
                'retry_tiktok' if retry else 'verify_upload' if possible or reconcile else 'restore_access' if access else 'inspect_upload',
                automatic=bool(context['retry_enabled'] if retry else context['attention_enabled'] if possible or reconcile else False),
                state='needs_operator' if access and not possible else 'waiting',
                job_id=getattr(row, 'source_job_id', None), upload_id=identity)
    for key, department, enabled, running in (
        ('cron', 'production', context['cron_enabled'], context['cron_alive']),
        ('attention', 'recovery', context['attention_enabled'], context['attention_alive']),
        ('retry', 'recovery', context['retry_enabled'], context['retry_alive'])):
        if enabled and not running:
            add('worker:' + key, department, 'Worker ' + key + ' belum berjalan',
                'Direktur meminta pemulihan worker pemilik tugas. Pengaturan operator tetap dipertahankan.',
                'worker_supervision', automatic=True, severity='critical')
    if hasattr(api, 'cron_life_story_status'):
        story = api.cron_life_story_status()
        if story.get('enabled') and story.get('state') == 'waiting_for_provider_rights':
            add('policy:story-rights', 'quality', 'Cerita memakai jalur cron cadangan',
                'Bukti izin provider cerita belum tersedia. Eksperimen ini dilewati; slot tetap diisi sumber cron yang memenuhi syarat. Izin provider tidak diasumsikan.',
                'use_supported_cron', automatic=bool(context['cron_enabled']),severity='info')
    facebook = context['facebook']
    if facebook.get('qc_wait_count', 0):
        add('facebook:quality', 'facebook', f"{facebook['qc_wait_count']} hasil Facebook menunggu QC",
            'Worker memulihkan audit dengan model proyek yang sudah dikonfigurasi dan jeda retry bertingkat. Upload menunggu bukti QC yang lulus.',
            'recover_facebook',automatic=bool(facebook.get('enabled')))
        incidents[-1]['destination'] = 'facebook'
    if facebook.get('failed_upload_count', 0):
        add('facebook:uploads', 'facebook', f"{facebook['failed_upload_count']} pengiriman Facebook belum selesai",
            'Sebagian posting mungkin sudah dikirim; identitas remote perlu dicocokkan sebelum pengiriman berikutnya.'
            if facebook.get('unknown_post_count', 0) else 'Worker memeriksa audiens, mengulang gangguan sementara sesuai batas, dan melewati Story kedaluwarsa yang belum pernah dikirim.',
            'recover_facebook',automatic=bool(facebook.get('enabled')))
        incidents[-1]['destination'] = 'facebook'
    priority = {'critical': 0, 'warning': 1, 'info': 2}
    return sorted(incidents, key=lambda row: (priority[row['severity']], not row['automatic'], row['id']))
