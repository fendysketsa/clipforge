"""Eleven YouTube content skills, applied as pure callable capabilities.

Each skill returns a deterministic artifact. None of them publishes, edits
operator settings, invents analytics or fabricates QC evidence.
"""
from __future__ import annotations

import re

VERSION = 1
SKILL_IDS = (
    'yt-script', 'yt-package', 'yt-edit', 'yt-comment', 'yt-plan', 'yt-viral',
    'yt-retention', 'yt-shorts', 'yt-seo', 'yt-chapters', 'yt-audit',
)

LABELS = {
    'yt-script': 'Naskah video',
    'yt-package': 'Paket metadata',
    'yt-edit': 'Rencana penyuntingan',
    'yt-comment': 'Balasan komentar aman',
    'yt-plan': 'Rencana konten mingguan',
    'yt-viral': 'Sudut konten & hook',
    'yt-retention': 'Pemeriksaan retensi',
    'yt-shorts': 'Format Shorts',
    'yt-seo': 'Kata kunci & judul',
    'yt-chapters': 'Bab bertanda waktu',
    'yt-audit': 'Audit hasil akhir',
}


def _text(payload, key, *, minimum=3, maximum=200):
    value = payload.get(key)
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise ValueError(f'{key} wajib berupa teks {minimum}–{maximum} karakter.')
    return re.sub(r'\s+', ' ', value).strip()


def yt_script(payload):
    topic = _text(payload, 'topic', maximum=140)
    style = payload.get('style') or 'tiga_langkah'
    import facebook_stories as stories
    plan = stories.plan('yt-script:' + topic[:16], 'short', topic, style=style)
    return dict(topic=topic, style=plan['story']['style'], title=plan['title'],
                stages=[dict(title=row['title'], text=row['text']) for row in plan['stages']],
                source='template_storyboard')


def yt_package(payload):
    title = _text(payload, 'title', maximum=120)
    description = _text(payload, 'description', minimum=10, maximum=1200)
    tags = payload.get('tags') or []
    if not isinstance(tags, list) or len(tags) > 15 or any(not isinstance(tag, str) or not 2 <= len(tag) <= 40 for tag in tags):
        raise ValueError('Tag tidak valid.')
    import facebook_strategy as strategy
    clean = strategy.public_caption(description)
    return dict(title=strategy.public_caption(title), description=clean, tags=[tag.strip() for tag in tags],
                hashtags=re.findall(r'#\w+', clean))


def yt_edit(payload):
    stages = payload.get('stages') or []
    if not isinstance(stages, list) or not 2 <= len(stages) <= 8 or any(not isinstance(row, dict) or not str(row.get('text') or '').strip() for row in stages):
        raise ValueError('Tahap naskah tidak valid.')
    words = [len(str(row['text']).split()) for row in stages]
    total = sum(words)
    if total < 20:
        raise ValueError('Naskah terlalu pendek untuk direncanakan.')
    weights = [round(60 * value / total, 1) for value in words]
    return dict(stage_seconds=weights, total_seconds=60, holds=[i for i, value in enumerate(weights) if value > 20],
                captions='stabil', transitions='seluruh_klip', note='Rencana biru; bukan bukti render atau QC.')


def yt_comment(payload):
    question = _text(payload, 'question', maximum=240)
    if re.search(r'(https?://|www\.|@\w+)', question, re.I):
        raise ValueError('Tautan atau akun tidak diterima dalam balasan.')
    return dict(reply=('Terima kasih sudah menonton dan bertanya. Jawaban singkatnya: ' + question[:160] +
                       '. Detailnya ada di video; kami tidak menjanjikan hasil yang sama untuk semua orang.'),
                tone='ramah', engagement_bait=False, remote_action='draft_only')


def yt_plan(payload):
    import facebook_autopilot as policy
    settings = policy.config(payload.get('settings'))
    start, end = policy.week()
    slots = policy.slots(None, settings)
    return dict(week_start=start, week_end=end, enabled=settings['enabled'],
                slots=[dict(key=row['key'], kind=row.get('kind', 'reel'), at=row.get('at')) for row in slots[:20]],
                quota=dict(weekly_posts=settings['weekly_posts'], weekly_stories=settings['weekly_stories']),
                catch_up=False)


def yt_viral(payload):
    topic = _text(payload, 'topic', maximum=140)
    words = [word for word in re.findall(r'[a-z]+', topic.casefold()) if len(word) > 3]
    angle = words[0] if words else 'cerita'
    return dict(hook=f'{angle.capitalize()} — apa yang sebenarnya terjadi?',
                angles=[f'{angle} dari sudut pengalaman', f'{angle} langkah kecil', f'{angle} kebiasaan baik'],
                evidence='sudut narasi, bukan janji penonton atau angka views', views_guaranteed=False)


def yt_retention(payload):
    stages = payload.get('stages') or []
    if not isinstance(stages, list) or not 2 <= len(stages) <= 8:
        raise ValueError('Tahap tidak valid.')
    lengths = [len(str(row.get('text') or '').split()) for row in stages]
    if not any(lengths):
        raise ValueError('Tahap tidak memuat narasi.')
    longest = max(range(len(lengths)), key=lambda index: lengths[index])
    return dict(stage_words=lengths, longest_stage=longest,
                suggestion='Pangkas bagian terpanjang menjadi satu ide per tahap.' if lengths[longest] > 38 else 'Pacing sudah seimbang.',
                measured=False, note='Heuristik naskah; bukan analitik retensi dari platform.')


def yt_shorts(payload):
    topic = _text(payload, 'topic', maximum=140)
    import facebook_stories as stories
    plan = stories.plan('yt-shorts:' + topic[:16], 'short', topic)
    return dict(format='short', max_seconds=55, title=plan['title'],
                stages=[row['text'] for row in plan['stages']],
                vertical=True, source='template_storyboard', publication_review=plan['creative_policy']['version'])


def yt_seo(payload):
    topic = _text(payload, 'topic', maximum=140)
    words = [word for word in re.findall(r'[a-z]{3,}', topic.casefold())]
    unique = list(dict.fromkeys(words))[:8]
    if not unique:
        raise ValueError('Topik tidak memuat kata kunci.')
    import facebook_strategy as strategy
    return dict(keywords=unique, title=strategy.public_caption(unique[0].capitalize() + ': ' + topic[:60]),
                description=topic + '. Contoh dan penjelasan ada di video.',
                note='Tanpa klaim peringkat atau jaminan penemuan.')


def yt_chapters(payload):
    seconds = payload.get('stage_seconds') or []
    titles = payload.get('titles') or []
    if (not isinstance(seconds, list) or not isinstance(titles, list) or not seconds
            or len(seconds) != len(titles) or any(not isinstance(value, (int, float)) or value < 0 for value in seconds)):
        raise ValueError('Waktu dan judul bab tidak cocok.')
    cursor = 0.0
    rows = []
    for value, title in zip(seconds, titles):
        rows.append(dict(start=round(cursor, 1), label=str(title)[:60]))
        cursor += float(value)
    return dict(chapters=rows, total_seconds=round(cursor, 1), format='00:00 Judul')


def yt_audit(payload):
    checks = payload.get('checks') or {}
    if not isinstance(checks, dict):
        raise ValueError('Bukti audit wajib berupa objek.')
    required = ('qc_pass', 'media_integrity', 'rights', 'context_safe', 'remote_identity_confirmed')
    missing = [key for key in required if checks.get(key) is not True]
    return dict(verdict='hold' if missing else 'ready', missing=missing,
                note='Audit hanya membaca bukti yang diberikan; tidak membuat kelulusan.',
                publication_allowed=not missing)


SKILLS = {
    'yt-script': yt_script, 'yt-package': yt_package, 'yt-edit': yt_edit,
    'yt-comment': yt_comment, 'yt-plan': yt_plan, 'yt-viral': yt_viral,
    'yt-retention': yt_retention, 'yt-shorts': yt_shorts, 'yt-seo': yt_seo,
    'yt-chapters': yt_chapters, 'yt-audit': yt_audit,
}


def snapshot():
    rows = [dict(id=identity, name=LABELS[identity], applied=callable(SKILLS.get(identity)))
            for identity in SKILL_IDS]
    return dict(version=VERSION, total=len(rows), applied=sum(row['applied'] for row in rows), skills=rows)


def run(skill_id, payload=None):
    if skill_id not in SKILLS:
        raise ValueError('Skill tidak dikenal.')
    return SKILLS[skill_id](payload or {})
