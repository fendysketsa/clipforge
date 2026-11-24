"""Digital leader for the AI Office: sets strategy and publishes assignments.

The leader never renders, uploads, edits operator settings or fakes QC. It
observes the existing coordinator context, decides what the studio should
prioritise, and writes bounded, durable directives that the existing worker
owners execute. This preserves the single-owner rule.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

VERSION = 1
HISTORY_LIMIT = 12
FOCUS_LIMIT = 8
TEXT_LIMIT = 240
PLATFORMS = ('facebook', 'youtube', 'tiktok')

DEFAULT_STRATEGY = {
    'version': VERSION,
    'name': 'Pimpinan Digital RYUUNDY',
    'role': 'Penentu arah studio dan pembagi arahan Kantor AI',
    'mission': ('Menumbuhkan literasi dan kebiasaan baik anak sekolah lewat cerita edukasi '
                'yang aman, orisinal, dan dekat dengan kehidupan sehari-hari.'),
    'focus': ['pendidikan_moral', 'kehidupan_sehari_hari', 'anak_sekolah'],
    'priority_platforms': list(PLATFORMS),
    'content_standard': [
        'Satu pesan moral yang jelas per video',
        'Tokoh dan naskah orisinal; tanpa footage atau musik pihak ketiga',
        'Bahasa ramah anak, contoh konkret, tanpa klaim atau janji hasil',
        'QC independen wajib lolos sebelum apa pun dikirim',
        'Identitas remote dicocokkan; Post tidak dikirim ulang',
        'Setelan operator, publication hold, dan jeda retry tetap dipertahankan',
    ],
    'audience': 'Anak sekolah dan keluarga',
    'model': 'supervised_existing_workers',
}


def validate_strategy(value):
    """Accept only bounded, explicitly known fields; fall back never invents evidence."""
    if not isinstance(value, dict):
        raise ValueError('Strategi pimpinan wajib berupa objek.')
    strategy = deepcopy(DEFAULT_STRATEGY)
    for key in ('name', 'role', 'mission', 'audience'):
        if key in value:
            text = value[key]
            if not isinstance(text, str) or not 3 <= len(text.strip()) <= TEXT_LIMIT:
                raise ValueError('Teks strategi tidak valid.')
            strategy[key] = text.strip()
    if 'focus' in value:
        focus = value['focus']
        if (not isinstance(focus, list) or not 1 <= len(focus) <= FOCUS_LIMIT
                or any(not isinstance(row, str) or not 2 <= len(row.strip()) <= 48 for row in focus)):
            raise ValueError('Fokus strategi tidak valid.')
        strategy['focus'] = [row.strip() for row in focus]
    if 'priority_platforms' in value:
        platforms = value['priority_platforms']
        if (not isinstance(platforms, list) or not 1 <= len(platforms) <= len(PLATFORMS)
                or any(row not in PLATFORMS for row in platforms) or len(set(platforms)) != len(platforms)):
            raise ValueError('Platform prioritas tidak valid.')
        strategy['priority_platforms'] = list(platforms)
    if 'content_standard' in value:
        standard = value['content_standard']
        if (not isinstance(standard, list) or not 1 <= len(standard) <= 12
                or any(not isinstance(row, str) or not 4 <= len(row.strip()) <= 160 for row in standard)):
            raise ValueError('Standar konten tidak valid.')
        strategy['content_standard'] = [row.strip() for row in standard]
    strategy['version'] = VERSION
    strategy['model'] = 'supervised_existing_workers'
    return strategy


def revision(strategy) -> str:
    payload = json.dumps(strategy, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def build_directives(strategy, state, incidents=()):
    """Turn observation + strategy into bounded, explainable assignments.

    Each directive is a durable instruction to an existing department. It
    carries evidence from the same observation so the UI can distinguish an
    active assignment from one that is blocked by operator settings.
    """
    strategy = validate_strategy(strategy)
    rev = revision(strategy)
    facebook = state.get('facebook') or {}
    incident_actions = {row.get('action') for row in (incidents or ())}
    signals = dict(
        jobs=int(state.get('jobs') or 0),
        quality=int(state.get('quality') or 0),
        uploads=int(state.get('uploads') or 0),
        queued=int(state.get('youtube_queued') or 0) + int(state.get('tiktok_queued') or 0),
        unverified=int(state.get('unverified') or 0),
        facebook_active=int(facebook.get('active_count') or 0),
        facebook_qc_wait=int(facebook.get('qc_wait_count') or 0),
        facebook_failed=int(facebook.get('failed_upload_count') or 0),
        open_incidents=len(incidents or ()),
    )
    definitions = (
        dict(key='education_first', department='production', priority='high',
             title='Utamakan cerita moral dan kebiasaan baik anak sekolah',
             reason=('Bank topik edukasi dipakai lebih dulu untuk slot produksi. Sumber cron yang '
                     'memenuhi syarat tetap menjadi pemilik produksi; arahan ini tidak membuat job baru.'),
             destination='history', action='use_supported_cron',
             skills=['yt-plan', 'yt-script', 'yt-viral'],
             enabled=bool(state.get('cron_enabled')),
             when=lambda s: s['jobs'] == 0),
        dict(key='facebook_education', department='facebook', priority='high',
             title='Produksi Original Facebook bertema edukasi dan moral anak',
             reason=('Departemen Facebook mengutamakan naskah orisinal anak sekolah dan kehidupan '
                     'sehari-hari. QC independen dan konfirmasi platform tetap menentukan hasil.'),
             destination='facebook', action='recover_facebook',
             skills=['yt-script', 'yt-shorts', 'yt-package'],
             enabled=bool(facebook.get('enabled')),
             when=lambda s: s['facebook_qc_wait'] == 0),
        dict(key='all_platforms', department='distribution', priority='high',
             title='Salurkan hasil yang lolos QC ke semua platform aktif',
             reason=('Setiap klip yang disetujui diperiksa untuk YouTube, TikTok, dan Facebook sesuai '
                     'setelan masing-masing. Publication hold dan identitas remote tidak ditimpa.'),
             destination='history', action='recover_scheduled_uploads',
             skills=['yt-package', 'yt-seo', 'yt-chapters'],
             enabled=bool(state.get('cron_enabled') or state.get('generic_enabled')),
             when=lambda s: s['queued'] == 0 or s['uploads'] > 0),
        dict(key='education_qc', department='quality', priority='high',
             title='Buktikan QC naskah dan video edukasi sebelum publikasi',
             reason=('Naskah ramah anak, satu pesan moral, dan bebas klaim harus dibuktikan. '
                     'Tidak ada kelulusan atau bukti QC yang dibuat-buat oleh koordinator.'),
             destination='history', action='review_quality',
             skills=['yt-audit', 'yt-retention', 'yt-edit'],
             enabled=bool(state.get('cron_enabled') or facebook.get('enabled')),
             when=lambda s: s['quality'] == 0),
        dict(key='delivery_proof', department='recovery', priority='normal',
             title='Tutup bukti pengiriman yang belum terkonfirmasi',
             reason=('Catatan yang belum terkonfirmasi dicocokkan dengan identitas remote. '
                     'Post tidak dikirim ulang hanya karena statusnya belum jelas.'),
             destination='history', action='verify_upload',
             skills=['yt-comment', 'yt-audit'],
             enabled=bool(state.get('attention_enabled')),
             when=lambda s: s['unverified'] > 0),
        dict(key='terminal_hygiene', department='cleanup', priority='normal',
             title='Arsipkan hasil terminal tanpa menghapus bukti',
             reason=('Penolakan dan Story kedaluwarsa yang belum pernah dikirim diarsipkan sesuai '
                     'kebijakan; file pekerjaan aktif tetap dilindungi.'),
             destination='history', action='cleanup_history',
             skills=['yt-audit'],
             enabled=bool(state.get('attention_enabled') or state.get('cron_enabled')),
             when=lambda s: 'cleanup_history' in incident_actions),
    )
    directives = []
    for item in definitions:
        item = dict(item)
        ready = bool(item.pop('enabled')) and bool(item.pop('when')(signals))
        status = 'active' if ready else 'blocked'
        directives.append(dict(
            id=rev[:8] + ':' + item['key'], key=item['key'], department=item['department'],
            title=item['title'], reason=item['reason'], action=item['action'],
            priority=item['priority'], automatic=ready, status=status,
            destination=item['destination'], evidence=signals,
            skills=list(item.get('skills') or ()),
        ))
    return directives
