"""Evidence-based handling of historical uploads; unknown posts never authorize retry."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import threading
import os
import tempfile
from urllib.parse import parse_qs, urlparse

from source_download import redact

VERSION = 1
REJECTION_CLEANUP_VERSION = 1
BACKOFF = (60, 300, 1800, 21600)


def youtube_id(value: str | None) -> str:
    try:
        parsed = urlparse(value or '')
        if parsed.scheme != 'https' or parsed.username or parsed.password:
            return ''
        if parsed.hostname in {'youtube.com', 'www.youtube.com', 'm.youtube.com'}:
            candidate = parse_qs(parsed.query).get('v', [''])[0] if parsed.path == '/watch' else ''
            match = re.fullmatch(r'/(?:shorts|live|embed)/([\w-]{11})/?', parsed.path)
            candidate = candidate or (match[1] if match else '')
        elif parsed.hostname == 'youtu.be':
            candidate = parsed.path.strip('/')
        else:
            return ''
        return candidate if re.fullmatch(r'[A-Za-z0-9_-]{11}', candidate) else ''
    except ValueError:
        return ''


def tiktok_url(value: str | None, handle: str = '') -> str:
    match = re.fullmatch(r'https://www\.tiktok\.com/@([\w.]+)/video/(\d{10,25})(?:[?#].*)?', value or '')
    if not match or (handle and match[1].casefold() != handle.casefold().lstrip('@')):
        return ''
    return f'https://www.tiktok.com/@{match[1]}/video/{match[2]}'


def normalized_text(value: str) -> str:
    return ' '.join(str(value or '').replace('\u200b', '').replace('\xa0', ' ').split())


def text_hash(value: str) -> str:
    return hashlib.sha256(normalized_text(value).encode()).hexdigest()


def caption_hash(value: str) -> str:
    return text_hash(value[:2200])


def confirmed(platform: str, row: dict) -> bool:
    return bool(not row.get('dry_run') and row.get('status') == 'completed' and row.get('upload_confirmed')
                and (youtube_id(row.get('video_url')) if platform == 'youtube'
                     else tiktok_url(row.get('profile_url'), row.get('target_handle', ''))))


def submitted(platform: str, row: dict) -> bool:
    logs = [str(line) for line in row.get('logs', [])]
    if platform == 'youtube':
        return bool(youtube_id(row.get('video_url')) or row.get('file_selection_started') or any(
            line.startswith(('Video dipilih:', 'Menyerahkan file ke YouTube Studio:', 'REMOTE_UPLOAD_CHECKPOINT',
                             'Tombol final diklik', 'UPLOAD_CONFIRMED:', 'FINAL_VISIBILITY:')) for line in logs))
    return bool(row.get('submission_started') or row.get('submission_accepted') or row.get('profile_url')
                or any(line.startswith(('POST_SUBMIT_INTENT:', 'POST_API_ACCEPTED:', 'POST_CONFIRMED',
                                        'UPLOAD_CONFIRMED:', 'VIDEO_URL:')) for line in logs))


def evidence_revision(row: dict) -> str:
    """Retry history survives restarts and UI-only timestamp changes."""
    fields = {key: row.get(key) for key in ('id', 'source_job_id', 'clip_url', 'clip_sha256', 'title', 'description',
              'caption', 'video_url', 'profile_url', 'visibility', 'publish_at', 'upload_confirmed', 'status', 'error',
              'clip_name', 'target_channel', 'target_handle', 'file_selection_started', 'submission_started',
              'submission_accepted', 'resume_existing_draft_only')}
    fields['safety_markers'] = [line for line in row.get('logs', []) if str(line).startswith(
        ('CLAIMED_UPLOAD_ABORTED:', 'REMOTE_UPLOAD_CHECKPOINT', 'POST_SUBMIT_INTENT:', 'POST_API_ACCEPTED:'))]
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def same_media(left: dict, right: dict) -> bool:
    if left.get('clip_sha256') and right.get('clip_sha256'):
        return left['clip_sha256'] == right['clip_sha256']
    return bool((left.get('clip_sha256') and left.get('clip_sha256') == right.get('clip_sha256')) or (
        left.get('source_job_id') and left.get('source_job_id') == right.get('source_job_id')
        and left.get('clip_url') and left.get('clip_url') == right.get('clip_url')))


def duplicate_for(platform: str, row: dict, rows: list[dict]) -> dict | None:
    account = 'target_channel' if platform == 'youtube' else 'target_handle'
    expected = str(row.get(account) or '').casefold().lstrip('@')
    if not expected:
        return None
    for other in rows:
        if other['id'] == row['id'] or not confirmed(platform, other) or not same_media(row, other):
            continue
        if str(other.get(account) or '').casefold().lstrip('@') != expected:
            continue
        return other
    return None


def decision(platform: str, row: dict, rows: list[dict], *, media_exists: bool, retry_allowed: bool = False,
             claim_confirmed: bool = False) -> dict | None:
    if row.get('dry_run') or row.get('status') in {'queued', 'running'} or confirmed(platform, row):
        return None
    logs = [str(line) for line in row.get('logs', [])]
    message = str(row.get('error') or '').casefold()
    base = {'id': f'{platform}-{row["id"]}', 'upload_id': row['id'], 'platform': platform,
            'revision': evidence_revision(row), 'remote_id': youtube_id(row.get('video_url')) if platform == 'youtube' else tiktok_url(row.get('profile_url'))}
    if platform == 'youtube' and (claim_confirmed or any(line.startswith('CLAIMED_UPLOAD_ABORTED:') for line in logs)):
        return {**base, 'action': 'drop_source',
                'reason': 'Klip ditolak pemeriksaan hak; file dan catatan antrean dibersihkan otomatis.'}
    if any(word in message for word in (
            'kebijakan nol-klaim', 'copyright', 'content id', 'community guideline', 'pelanggaran', 'content safety')):
        return {**base, 'action': 'hold', 'reason': 'Sumber diblokir oleh pemeriksaan hak atau kebijakan; dilewati otomatis.'}
    duplicate = duplicate_for(platform, row, rows)
    if duplicate:
        return {**base, 'action': 'reconcile_duplicate', 'duplicate_id': duplicate['id'],
                'reason': 'File yang sama sudah memiliki posting terverifikasi; catatan akan diselaraskan.'}
    possible = submitted(platform, row)
    if row.get('status') == 'cancelled' and not possible:
        return None
    if possible:
        return {**base, 'action': 'verify_remote',
                'reason': 'Mencocokkan posting yang sudah ada; sistem tidak mengirim file ulang.'}
    if retry_allowed and media_exists and row.get('status') == 'failed':
        return {**base, 'action': 'retry_upload',
                'reason': 'Kegagalan terbukti sebelum pengiriman; file yang lolos QC akan diantrekan ulang.'}
    if not media_exists:
        return {**base, 'action': 'hold',
                'reason': 'File lokal sudah tidak tersedia dan belum ada bukti posting yang tepat. Catatan disimpan.'}
    return {**base, 'action': 'hold', 'reason': 'Menunggu bukti QC atau sumber yang memenuhi syarat; tidak diterbitkan otomatis.'}


def rejection_folder(uploads_path: Path) -> Path:
    return uploads_path.parent / 'rejected_uploads' / 'youtube'


def archive_rejection(uploads_path: Path, row: dict, now: str) -> Path:
    """Persist the terminal decision before removing a local queue record."""
    identity = str(row.get('id') or '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', identity):
        raise ValueError('Invalid rejected upload identity')
    clean = {**row, 'logs': [redact(str(line)) for line in row.get('logs', [])],
             'error': redact(row.get('error') or '')}
    payload = dict(version=REJECTION_CLEANUP_VERSION, decision='DROP_SOURCE',
                   reason='confirmed_content_id_claim', archived_at=now,
                   local_media_removed=True, remote_action='none', upload=clean)
    folder = rejection_folder(uploads_path)
    target = folder / (identity + '.json')
    targets = [target]
    digest = str(row.get('clip_sha256') or '')
    if re.fullmatch(r'[a-fA-F0-9]{64}', digest):
        targets.append(folder / 'by-sha256' / (digest.lower() + '.json'))
    for destination in targets:
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix='.rejected-', dir=destination.parent)
        try:
            with os.fdopen(descriptor, 'w') as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return target


class StateStore:
    """Small atomic ledger independent of original upload IDs, holds and logs."""
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.RLock()

    def read(self) -> dict:
        with self.lock:
            if not self.path.exists():
                return {'version': VERSION, 'items': {}}
            data = json.loads(self.path.read_text())
            if not isinstance(data, dict) or not isinstance(data.get('items'), dict):
                raise ValueError('Ledger penanganan upload tidak valid; perubahan ditunda.')
            return data

    def update(self, key: str, **changes) -> dict:
        with self.lock:
            data = self.read()
            item = {**data['items'].get(key, {}), **changes}
            data['items'][key] = item
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            temporary.replace(self.path)
            return item


def status(item: dict, saved: dict, now: float) -> dict:
    attempt = int(saved.get('attempts', 0))
    saved = saved if saved.get('revision') == item['revision'] else {}
    running = saved.get('state') == 'checking' and now - float(saved.get('checked_at', 0)) < 150
    exhausted = item['action'] == 'retry_upload' and attempt >= 3
    held = item['action'] == 'hold' or exhausted
    next_at = float(saved.get('next_check_at') or 0)
    return {**item, 'state': 'held' if held else 'checking' if running else 'waiting', 'attempts': attempt,
            'reason': 'Batas tiga percobaan aman tercapai; catatan dan bukti disimpan.' if exhausted else item['reason'] if held else saved.get('message') or item['reason'],
            'checked_at': saved.get('checked_at'),
            'next_check_at': None if held or running else max(now, next_at)}


def due(items: list[dict], now: float) -> list[dict]:
    ready = [item for item in items if item['state'] == 'waiting' and (item.get('next_check_at') or 0) <= now]
    # Round-robin by check time prevents a stubborn first row starving older work.
    return sorted(ready, key=lambda item: (item.get('checked_at') or 0,
                  item['action'] != 'reconcile_duplicate', not bool(item.get('remote_id')), item['id']))
