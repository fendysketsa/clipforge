"""Evidence-gated local history disposition; never approve or mutate a remote post."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Iterable
from urllib.parse import unquote

from source_download import redact, source_id
import upload_attention

VERSION = 1
_SELECTION_EXHAUSTED = 'Tidak ditemukan potongan dengan kalimat tuntas, alur utuh, retensi memadai, dan konteks aman.'
_REASONS = {
    'selection_recovery_exhausted': 'Seleksi dan pemulihan sumber sudah habis; kartu kosong diarsipkan otomatis.',
    'long_material_rejected': 'Bahan Long tidak memenuhi syarat; percobaan gagal kosong diarsipkan otomatis.',
    'long_anchor_context_rejected': 'Konteks dan batas kalimat Long tidak aman; percobaan gagal kosong diarsipkan otomatis.',
    'news_mandatory_review_unresolved': 'Bukti review fakta, konteks, dan hak berita belum lengkap; hasil ditolak dan dibersihkan otomatis.',
    'active_production': 'Worker sedang menjalankan atau mengantrekan produksi.',
    'active_upload': 'Upload yang sudah diantrekan sedang diselesaikan oleh worker platform.',
    'active_recovery_child': 'Percobaan pemulihan aktif diselesaikan sebelum pembersihan hasil lama.',
    'active_checkpoint_consumer': 'Pipeline masih membaca hasil ini; keputusan mengikuti checkpoint aktif.',
    'remote_or_submission_evidence': 'Status posting dicocokkan otomatis; identitas remote tetap dilindungi.',
    'upload_record_requires_own_recovery': 'Catatan upload ditangani oleh worker pemulihan platform.',
    'failed_job_has_artifacts': 'Bukti hasil masih tersedia; worker memeriksa pemulihan sebelum cleanup.',
    'failure_needs_recovery_evidence': 'Penyebab kegagalan diperiksa sebelum memilih pemulihan atau cleanup.',
    'owned_by_platform_worker': 'Pekerjaan dikelola oleh worker platform asal.',
    'manual_or_review_only': 'Setelan sumber dan review yang tersimpan tetap dipertahankan.',
    'evidence_incomplete': 'Bukti proses belum lengkap; pemeriksaan berikutnya mempertahankan hasil yang ada.',
    'invalid_artifact_identity': 'Identitas file belum valid; hasil dilindungi sampai pemeriksaan selesai.',
    'approved_or_no_news_artifact': 'Hasil yang sudah direview mengikuti jalur upload yang disetujui.',
    'not_terminal': 'Pekerjaan mengikuti pemeriksaan dan antrean otomatis yang berlaku.',
}


def revision(job: dict) -> str:
    """Approval, identity or artifact changes invalidate a previously planned cleanup."""
    request = job.get('request') or {}
    evidence = {key: job.get(key) for key in ('id', 'status', 'error', 'source_url', 'finished_at')}
    evidence['request'] = {key: request.get(key) for key in (
        'url', 'target_platform', 'clip_mode', 'review_only', 'publication_review_required',
        'scheduled_news_hot', 'scheduled_public_source_credit', 'cron_daily_lane')}
    evidence['clips'] = [{key: clip.get(key) for key in (
        'url', 'size_bytes', 'is_correct', 'render_qc_passed', 'render_qc_blocking', 'youtube_upload_ready')}
        for clip in job.get('clips') or []]
    evidence['candidate_count'] = len(job.get('candidates') or [])
    return hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()


def terminal_failure_reason(job: dict) -> str | None:
    """Only explicit exhausted selection/structural failures qualify, not transport errors."""
    error = str(job.get('error') or '')
    text = ' '.join([error, *[str(line) for line in job.get('logs') or []]])
    text = ' '.join(text.split()).casefold()
    if error.startswith(_SELECTION_EXHAUSTED):
        return 'selection_recovery_exhausted'
    if 'insufficient_or_excessive_compilation_material' in text:
        return 'long_material_rejected'
    if ('long story dibatalkan karena momen short wajib tidak dapat dipertahankan' in text
            and 'batas kalimat yang aman' in text):
        return 'long_anchor_context_rejected'
    return None


def decision(job: dict, *, jobs: Iterable[dict] = (), youtube: Iterable[dict] = (),
             tiktok: Iterable[dict] = (), process_active: bool = False,
             workspace_exists: bool = True, checkpoint_busy: bool = False,
             facebook_protected: bool = False, evidence_complete: bool = True) -> dict:
    """Plan local removal only after the adapter proves ownership and all consumers idle.

    The adapter must sample process/checkpoint/file state and recheck the returned
    revision under its admission locks before archiving and applying the plan.
    Existing publication-review flags are never changed or treated as approval.
    """
    request = job.get('request') or {}
    result = dict(version=VERSION, source_job_id=str(job.get('id') or ''), revision=revision(job),
                  action='retain', decision=None, reason='not_terminal', clip_urls=[],
                  delete_source=False, upload_allowed=False, urgent=False)

    def retain(reason):
        return {**result, 'reason': reason}

    if not evidence_complete:
        return retain('evidence_incomplete')
    if request.get('target_platform', 'standard') != 'standard' or facebook_protected:
        return retain('owned_by_platform_worker')
    if not request.get('scheduled_public_source_credit') or request.get('review_only'):
        return retain('manual_or_review_only')
    if job.get('status') in {'queued', 'running'} or process_active:
        return retain('active_production')
    if checkpoint_busy:
        return retain('active_checkpoint_consumer')
    if any(child.get('status') in {'queued', 'running'} and job.get('id') in {
            child.get('repair_source_job_id'), child.get('source_recovery_parent_job_id')}
            for child in jobs):
        return retain('active_recovery_child')
    yt = [row for row in youtube if row.get('source_job_id') == job.get('id') and not row.get('dry_run')]
    tt = [row for row in tiktok if row.get('source_job_id') == job.get('id') and not row.get('dry_run')]
    if any(row.get('status') in {'queued', 'running'} for row in [*yt, *tt]):
        return retain('active_upload')
    # These plans target unsubmitted history. Even confirmed remote success is
    # left to its existing platform cleanup owner, preserving all remote IDs.
    if yt or tt:
        if any(upload_attention.submitted(platform, row) or upload_attention.confirmed(platform, row)
               for platform, rows in (('youtube', yt), ('tiktok', tt)) for row in rows):
            return retain('remote_or_submission_evidence')
        return retain('upload_record_requires_own_recovery')

    clips = job.get('clips') or []
    if job.get('status') == 'failed':
        if clips or job.get('candidates') or workspace_exists:
            return retain('failed_job_has_artifacts')
        reason = terminal_failure_reason(job)
        if reason:
            return {**result, 'action': 'archive_empty_failure', 'decision': 'DROP_SOURCE', 'reason': reason}
        return retain('failure_needs_recovery_evidence')

    if job.get('status') == 'completed' and request.get('scheduled_news_hot'):
        unapproved = [clip for clip in clips if clip.get('is_correct') is not True]
        if unapproved:
            urls = [str(clip.get('url') or '') for clip in unapproved]
            if any(not url.startswith('/outputs/') or any(part in {'', '.', '..'} for part in
                    unquote(url.removeprefix('/outputs/')).split('/')) or '?' in url or '#' in url for url in urls):
                return retain('invalid_artifact_identity')
            return {**result, 'action': 'drop_source', 'decision': 'DROP_SOURCE',
                    'reason': 'news_mandatory_review_unresolved', 'clip_urls': urls, 'delete_source': True}
        return retain('approved_or_no_news_artifact')
    return result


def planning_snapshot(plan: dict, *, next_check_at: str | None = None, archived: bool = False) -> dict:
    """Small UI metadata; never a substitute for platform/QC confirmation."""
    reason = str(plan.get('reason') or 'not_terminal')
    urgent = plan.get('urgent') is True
    state = ('archived' if archived else 'urgent' if urgent else 'archiving'
             if plan.get('action') in {'archive_empty_failure', 'drop_source'} else 'processing'
             if reason in {'active_production', 'active_upload', 'active_recovery_child'} else 'waiting')
    return dict(state=state, action=str(plan.get('action') or 'retain'),
                reason=_REASONS.get(reason, 'Keputusan berikutnya mengikuti bukti dan setelan yang tersimpan.'),
                next_check_at=next_check_at, urgent=urgent)


def _safe(value, depth=0):
    if depth > 6:
        return '[bounded]'
    if isinstance(value, dict):
        return {str(key): _safe(item, depth + 1) for key, item in list(value.items())[:128]
                if not re.search(r'(?i)(?:api[_-]?key|cookie|authorization|password|secret|access[_-]?token)', str(key))}
    if isinstance(value, list):
        return [_safe(item, depth + 1) for item in value[:128]]
    if isinstance(value, str):
        identity = source_id(value)
        if identity:
            return 'https://www.youtube.com/watch?v=' + identity
        return redact(value)
    return value


def archive(folder: Path, job: dict, plan: dict, *, checkpoint_refs: list[dict], now: str) -> Path:
    """Store a small private receipt before local deletion; no state-file rewrite."""
    identity = str(job.get('id') or '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', identity):
        raise ValueError('Invalid autonomous history identity')
    if plan.get('source_job_id') != identity or plan.get('revision') != revision(job):
        raise ValueError('Autonomous history evidence changed')
    if plan.get('action') not in {'archive_empty_failure', 'drop_source'} or plan.get('decision') != 'DROP_SOURCE':
        raise ValueError('No terminal local cleanup decision')
    request = job.get('request') or {}
    receipt = dict(version=VERSION, job_id=identity, decision='DROP_SOURCE', action=plan['action'],
        reason=plan['reason'], revision=plan['revision'], archived_at=now, remote_action='none',
        source_id=source_id(job.get('source_url') or request.get('url') or ''),
        original_job={key: job.get(key) for key in (
            'status', 'source_title', 'source_url', 'error', 'created_at', 'finished_at',
            'repair_source_job_id', 'source_recovery_parent_job_id', 'download_diagnostics')},
        original_request={key: request.get(key) for key in (
            'url', 'target_platform', 'clip_mode', 'review_only', 'publication_review_required',
            'scheduled_news_hot', 'scheduled_public_source_credit', 'scheduled_theme_key',
            'cron_daily_lane', 'cron_production_day', 'paired_short_job_id', 'confirm_source_rights')},
        clips=[{key: clip.get(key) for key in (
            'name', 'url', 'is_correct', 'render_qc_passed', 'render_qc_blocking', 'youtube_upload_ready')}
            for clip in job.get('clips') or []],
        previous_logs=[str(line) for line in job.get('logs') or []][-30:],
        candidate_count=len(job.get('candidates') or []),
        checkpoint_refs=checkpoint_refs, local_clip_urls=plan.get('clip_urls') or [],
        upload_allowed=False, manual_hold_released=False)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (identity + '.json')
    descriptor, temporary = tempfile.mkstemp(prefix='.history-', dir=folder)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(_safe(receipt), stream, ensure_ascii=False, indent=2)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return target
