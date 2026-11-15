"""Isolated Facebook workspace, durable uploads, and shared-browser session routes."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import uuid
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field

import facebook_browser as browser
import facebook_strategy as strategy


class FacebookJobInput(BaseModel):
    url: str = Field(default='', max_length=2000)
    source_file: str = Field(default='', max_length=255)
    niche: Literal['tech_daily', 'digital_simple'] = 'tech_daily'
    max_duration: int = Field(default=38, ge=26, le=55)
    top: int = Field(default=1, ge=1, le=3)
    rights: Literal['owned', 'permission_no_credit']
    rights_evidence: str = Field(min_length=20, max_length=2000)
    creator_perspective: str = Field(default='', max_length=4000)
    allow_reprocess_source: bool = False


class FacebookUploadInput(BaseModel):
    job_id: str
    clip_url: str


class FacebookVerifyInput(BaseModel):
    video_url: str


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def start_background(target, *args):
    threading.Thread(target=target, args=args, daemon=True).start()


class Store:
    def __init__(self, path: Path):
        self.path, self.lock = path, threading.RLock()
        # Corrupt persisted records must never become an empty duplicate ledger.
        self.data = json.loads(path.read_text()) if path.exists() else {'schema': 1, 'uploads': {}, 'session': {}}
        if self.data.get('schema') != 1 or not isinstance(self.data.get('uploads'), dict):
            raise RuntimeError('Data Facebook tidak valid; ledger dipertahankan untuk pemeriksaan.')

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.facebook-', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(self.data, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def update(self, identifier: str, **changes):
        with self.lock:
            self.data['uploads'][identifier].update(**changes, updated_at=now())
            self.save()


def install(app, api):
    stores: dict[str, Store] = {}
    stores_lock = threading.Lock()

    def store() -> Store:
        path = api.JOBS_PATH.parent / 'facebook_workspace.json'
        with stores_lock:
            if str(path) not in stores:
                stores[str(path)] = Store(path)
            return stores[str(path)]

    def session_check(open_login=False):
        data = store()
        with api.social_upload_turn():
            previous = data.data.get('session') or {}
            result = browser.check_session(open_login=open_login,
                expected_profile=previous.get('verified_profile_id', ''))
        with data.lock:
            if result.get('account_verified'):
                result['verified_profile_id'] = result['profile_id']
            elif previous.get('verified_profile_id'):
                result['verified_profile_id'] = previous['verified_profile_id']
            data.data['session'] = result
            data.save()
        return result

    def qc(job, clip):
        issues = []
        if job.request.target_platform != 'facebook':
            issues.append('Hanya render khusus Facebook yang dapat diunggah di ruang ini.')
        if job.status != 'completed':
            issues.append('Produksi belum selesai.')
        if job.request.publication_review_required or job.request.review_only:
            issues.append('Publication hold masih aktif.')
        if (not job.request.confirm_source_rights or not job.request.facebook_source_rights
                or len(job.request.source_rights_evidence.split()) < 6):
            issues.append('Bukti kepemilikan/izin tanpa atribusi belum lengkap.')
        path = api.output_path_from_url(clip.url)
        if path is None or not path.is_file() or not path.resolve().is_relative_to(api.OUTPUTS_DIR.resolve()):
            return {'decision': 'HOLD', 'issues': [*issues, 'File hasil tidak ditemukan.']}
        try:
            probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams',
                '-show_format', '-of', 'json', str(path)], timeout=20))
            issues.extend(strategy.media_issues(probe))
        except Exception:
            issues.append('Media encoded belum dapat diverifikasi.')
        sidecar = api.clip_sidecar_payload(clip)
        facebook = sidecar.get('facebook') or {}
        if facebook.get('version') != strategy.VERSION:
            issues.append('Profil render Facebook belum terverifikasi.')
        if (facebook.get('watermark') or {}).get('style_version') != 2:
            issues.append('Watermark Short yang sama belum terverifikasi.')
        render = sidecar.get('render_quality_qc') or {}
        if render.get('quality_gate_passed') is not True or render.get('blocking') is True:
            issues.append('QC render belum lulus.')
        if job.request.facebook_source_rights == 'permission_no_credit':
            readiness = sidecar.get('monetization_readiness') or {}
            if not api.monetization_readiness_is_eligible(sidecar, readiness):
                issues.append('Transformasi editorial materi berizin belum cukup terverifikasi.')
        if clip.context_recut_required or clip.religious_review_required or clip.narrative_arc_complete is not True:
            issues.append('Konteks atau akhir ucapan belum aman.')
        if not clip.is_correct:
            issues.append('Tonton preview lalu tandai hasil sudah diperiksa.')
        caption = str(facebook.get('caption') or '')
        if not caption or not strategy.public_caption(caption):
            issues.append('Caption Facebook belum tersedia.')
        if any(marker in caption.lower() for marker in ['http://', 'https://', 'www.', 'sumber:', 'source:', 'credit:']):
            issues.append('Caption publik masih mengandung sumber atau tautan.')
        return {'decision': 'HOLD' if issues else 'PASS_UPLOAD', 'issues': issues,
                'caption': caption, 'sha256': api.file_sha256(path),
                'checked_at': now(), 'duration_target': 30, 'max_seconds': 55}

    def run_upload(identifier):
        data = store()
        with api.social_upload_turn():
            with data.lock:
                row = dict(data.data['uploads'][identifier])
                if row['status'] != 'queued' or row.get('submission_started'):
                    return
            try:
                # Share the cooldown with YouTube/TikTok; the durable Facebook
                # ledger additionally provides the same interval for all lanes.
                import time
                remaining = api.social_upload_cooldown_remaining()
                if remaining:
                    time.sleep(min(600, remaining))
                job, clip, _ = api.find_job_clip(row['job_id'], row['clip_url'])
                audit = qc(job, clip)
                if audit['issues'] or audit.get('sha256') != row['sha256']:
                    raise RuntimeError('; '.join(audit['issues']) or 'File berubah sejak masuk antrean.')
                data.update(identifier, status='running', started_at=now(), message='Memeriksa akun dan menyiapkan Reel.')
                result = browser.upload(api.output_path_from_url(clip.url), row['caption'], row['profile_id'],
                                        lambda **changes: data.update(identifier, **changes))
                data.update(identifier, **result, finished_at=now())
            except Exception as exc:
                with data.lock:
                    attempted = data.data['uploads'][identifier].get('submission_started')
                data.update(identifier, status='needs_review' if attempted else 'failed',
                            message=str(exc)[:500], finished_at=now())

    @app.get('/api/facebook/config')
    def config():
        data = store()
        with data.lock:
            status = dict(data.data.get('session') or {})
        return {'version': strategy.VERSION, 'target_email': browser.TARGET_EMAIL,
                'target_seconds': 30, 'max_seconds': 55,
                'shared_browser': api.social_browser_is_shared(),
                'session': status, 'niches': [{'key': key, **value} for key, value in strategy.NICHES.items()],
                'caption_style': 'Frasa putih stabil, dua baris; caption posting singkat dan kontekstual.',
                'login_note': 'Satu browser menyimpan sesi tiap platform. Facebook tetap memerlukan login awal '
                              'dan dapat meminta verifikasi ulang.',
                'publication_policy': 'Preview dan QC wajib; Post yang belum terkonfirmasi ditahan.'}

    @app.post('/api/facebook/session/check')
    def check():
        return session_check()

    @app.post('/api/social/login')
    def login():
        # Existing launcher adds tabs only when shared Chrome is alive; in
        # Docker it refuses to create a competing desktop profile.
        try:
            subprocess.run(api.build_youtube_cdp_refresh_command(), timeout=40,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except Exception:
            pass
        return session_check(open_login=True)

    @app.get('/api/facebook/jobs')
    def list_jobs():
        with api.jobs_lock:
            rows = [job for job in api.jobs.values() if job.request.target_platform == 'facebook']
        result = []
        for job in sorted(rows, key=lambda row: row.created_at, reverse=True)[:40]:
            enriched = api.enrich_job_for_display(job)
            result.append({'job': enriched, 'results': [
                {'clip_url': clip.url, 'caption': str((api.clip_sidecar_payload(clip).get('facebook') or {}).get('caption') or '')}
                for clip in enriched.clips]})
        return result

    @app.post('/api/facebook/jobs')
    def create(request: FacebookJobInput):
        if bool(request.url.strip()) == bool(request.source_file.strip()):
            raise HTTPException(400, 'Pilih satu video URL atau file yang sudah diunggah.')
        if len(request.rights_evidence.split()) < 6:
            raise HTTPException(400, 'Jelaskan bukti hak audio dan visual minimal enam kata.')
        if request.url:
            if not api.normalize_youtube_video_url(request.url):
                raise HTTPException(400, 'Gunakan URL YouTube yang valid atau unggah video sendiri.')
        return api.create_job(api.ClipJobRequest(
            target_platform='facebook', facebook_niche=request.niche,
            facebook_source_rights=request.rights, url=request.url.strip(), source_file=request.source_file,
            min_duration=25, max_duration=request.max_duration, top=request.top,
            confirm_source_rights=True, source_rights_evidence=request.rights_evidence,
            creator_perspective=request.creator_perspective, require_creative_commons=False,
            allow_reprocess_source=request.allow_reprocess_source,
            auto_upload_youtube=False, caption_font_size=11, caption_position='bottom',
        ))

    @app.post('/api/facebook/qc')
    def inspect(request: FacebookUploadInput):
        job, clip, _ = api.find_job_clip(request.job_id, request.clip_url)
        return qc(job, clip)

    @app.get('/api/facebook/uploads')
    def uploads():
        data = store()
        with data.lock:
            return sorted([dict(row) for row in data.data['uploads'].values()],
                          key=lambda row: row['created_at'], reverse=True)

    @app.post('/api/facebook/uploads')
    def enqueue(request: FacebookUploadInput):
        data = store()
        job, clip, _ = api.find_job_clip(request.job_id, request.clip_url)
        audit = qc(job, clip)
        if audit['issues']:
            raise HTTPException(409, '; '.join(audit['issues']))
        with data.lock:
            # Both exact source and hash are durable idempotency identities.
            for row in data.data['uploads'].values():
                if row['sha256'] == audit['sha256'] or (row['job_id'], row['clip_url']) == (job.id, clip.url):
                    return dict(row)
            status = data.data.get('session') or {}
            try:
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(status.get('checked_at', ''))).total_seconds()
                fresh = 0 <= age < 600
            except (ValueError, TypeError):
                fresh = False
            if not fresh or not status.get('account_verified') or not status.get('verified_profile_id'):
                raise HTTPException(409, 'Periksa sesi Facebook dan verifikasi email akun target terlebih dahulu.')
            identifier = uuid.uuid4().hex
            row = dict(id=identifier, job_id=job.id, clip_url=clip.url, clip_name=clip.name,
                       sha256=audit['sha256'], caption=audit['caption'], status='queued',
                       target_email=browser.TARGET_EMAIL, profile_id=status['verified_profile_id'],
                       submission_started=False, upload_confirmed=False, video_url=None,
                       created_at=now(), updated_at=now(), message='Menunggu browser bersama.')
            data.data['uploads'][identifier] = row
            data.save()
        start_background(run_upload, identifier)
        return dict(row)

    @app.post('/api/facebook/uploads/{identifier}/verify-remote')
    def reconcile(identifier: str, request: FacebookVerifyInput):
        data = store()
        with data.lock:
            row = dict(data.data['uploads'].get(identifier) or {})
        if not row:
            raise HTTPException(404, 'Upload tidak ditemukan.')
        url = browser.reel_url(request.video_url)
        if not url:
            raise HTTPException(400, 'Gunakan permalink https://www.facebook.com/reel/ID/.')
        with api.social_upload_turn(), browser.connection() as context:
            status = browser.session(context, expected_profile=row['profile_id'])
            verified = status.get('account_verified') and browser.verify_remote(context, url, row['caption'], row['profile_id'])
        if not verified:
            raise HTTPException(409, 'Akun, caption lengkap, dan identitas Reel belum cocok.')
        data.update(identifier, status='completed', upload_confirmed=True, video_url=url,
                    message='Identitas Reel berhasil direkonsiliasi.', finished_at=now())
        return dict(data.data['uploads'][identifier])

    @app.on_event('startup')
    def resume():
        data = store()
        pending = []
        with data.lock:
            for identifier, row in data.data['uploads'].items():
                if row['status'] == 'running' or (row['status'] == 'queued' and row.get('submission_started')):
                    row.update(status='needs_review', message='Runtime direstart; periksa remote sebelum tindakan berikutnya.')
                elif row['status'] == 'queued':
                    pending.append(identifier)
            data.save()
        for identifier in pending:
            start_background(run_upload, identifier)
        start_background(session_check)

    # Expose only the durable cooldown to the existing two upload lanes.
    def cooldown(current):
        data = store()
        with data.lock:
            rows = list(data.data['uploads'].values())
        remaining = 0.0
        for row in rows:
            if row.get('finished_at'):
                finished = datetime.fromisoformat(row['finished_at'])
                remaining = max(remaining, (finished - current).total_seconds() + 45)
        return max(0.0, min(600, remaining))
    api.facebook_upload_cooldown = cooldown
    def protected(job_id, clip_urls=None):
        data = store()
        with data.lock:
            return any(row['job_id'] == job_id and row['status'] in {'queued', 'running', 'needs_review'}
                       and (clip_urls is None or row['clip_url'] in clip_urls)
                       for row in data.data['uploads'].values())
    api.facebook_upload_protected = protected
