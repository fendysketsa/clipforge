"""Facebook-only editorial policy. No credentials, publication, or shared state."""
from __future__ import annotations

import math
import re
from typing import Any

VERSION = 1
TARGET_SECONDS = 30
MAX_SECONDS = 55
NICHES = {
    'tech_daily': {
        'label': 'Tips teknologi & trik HP sehari-hari',
        'brief': 'Satu masalah nyata, satu langkah yang terlihat, satu hasil yang bisa dicoba. '
                 'Pilih tips HP, pengaturan aplikasi, dan kebiasaan digital; hindari klaim keamanan '
                 'mutlak, pembobolan akun, hoaks, promosi investasi, serta tutorial yang kedaluwarsa.',
        'queries': ['tips HP Android sehari hari bahasa Indonesia',
                    'trik pengaturan WhatsApp tutorial Indonesia',
                    'cara merapikan penyimpanan HP tutorial Indonesia'],
        'signals': ['hp', 'ponsel', 'android', 'iphone', 'whatsapp', 'aplikasi', 'pengaturan',
                    'penyimpanan', 'baterai', 'notifikasi', 'kamera', 'file', 'ponsel'],
        'hashtags': ['TipsHP', 'TeknologiSehariHari'],
    },
    'digital_simple': {
        'label': 'Kebiasaan digital yang memudahkan hidup',
        'brief': 'Tunjukkan langkah sederhana mengatur file, foto, pesan, dan pekerjaan digital. '
                 'Jangan memotong peringatan atau membuat hasil yang tidak terlihat di rekaman.',
        'queries': ['tips mengatur file foto HP tutorial Indonesia',
                    'tips produktivitas digital sederhana Indonesia'],
        'signals': ['file', 'foto', 'pesan', 'folder', 'dokumen', 'aplikasi', 'digital',
                    'notifikasi', 'pengaturan', 'ponsel', 'hp', 'komputer'],
        'hashtags': ['TipsDigital', 'TipsSehariHari'],
    },
}


def public_caption(value: str) -> str:
    """Keep public copy compact; provenance stays in private job metadata."""
    lines = []
    for line in str(value or '').splitlines():
        if re.search(r'(?:https?://|www\.|(?:youtube|youtu|tiktok|facebook)\.com|youtu\.be|@\w+)', line, re.I):
            continue
        if re.search(r'\b(?:sumber|source|credit|credits|kredit|diambil dari|cuplikan dari|courtesy)\s*[:：-]?', line, re.I):
            continue
        if re.search(r'\b(?:like|share|subscribe|follow|fyp|viral|tag teman|komen|komentar|bagikan|ikuti)\b', line, re.I):
            continue
        cleaned = re.sub(r'#\w+', '', line).strip(' \t"')
        if cleaned:
            lines.append(cleaned)
    text = re.sub(r'\s+', ' ', ' '.join(lines)).strip()
    if len(text) > 420:
        text = text[:420].rsplit(' ', 1)[0].rstrip(' ,;:') + '…'
    return text


def make_caption(clip: Any, config: Any, niche: str = 'tech_daily') -> str:
    from llm import chat_completion, extract_json
    title = public_caption(str(getattr(clip, 'title', '') or ''))
    evidence = str(getattr(clip, 'text', '') or '')[:2400]
    # The fallback quotes an existing complete title, without inventing a benefit.
    copy = title.rstrip('.!?') + '.' if title else ''
    if config.enabled and config.base_url and config.model:
        try:
            result = extract_json(chat_completion(config, [
                {'role': 'system', 'content': 'Tulis caption Facebook berbahasa Indonesia dari bukti klip. '
                 'Maksimal dua kalimat (25-55 kata): situasi yang akrab lalu manfaat/langkah yang benar-benar '
                 'terlihat atau terucap. Nada santai, hangat, spesifik. Jangan menambah fakta, janji hasil, '
                 'pertanyaan generik, emoji, atribusi, URL, akun, hashtag, ajakan engagement, atau clickbait. '
                 'Jika bukti tidak cukup, gunakan judul saja. Balas JSON {"caption":"..."}.'},
                {'role': 'user', 'content': f'Judul: {title}\nTranskrip: {evidence}'},
            ], temperature=0.4))
            candidate = public_caption(str(result.get('caption') or '')) if isinstance(result, dict) else ''
            if candidate:
                copy = candidate
        except Exception:
            pass
    if not copy:
        return ''
    return copy + '\n\n' + ' '.join('#' + tag for tag in NICHES[niche]['hashtags'])


def candidate_score(candidate: Any, niche: str) -> float:
    text = ' '.join(str(getattr(candidate, key, '') or '') for key in ('title', 'text', 'core_message')).casefold()
    relevance = sum(bool(re.search(r'\b' + re.escape(term) + r'\b', text)) for term in NICHES[niche]['signals'])
    duration = float(candidate.end) - float(candidate.start)
    if not math.isfinite(duration) or not 20 <= duration <= MAX_SECONDS or relevance == 0:
        return -1
    return min(30, relevance * 7) + max(0, 25 - abs(duration - TARGET_SECONDS)) + float(getattr(candidate, 'score', 0) or 0) * .45


def phrase_cues(segments: list, offset: float, duration: float) -> list[tuple[float, float, str]]:
    """Phrase timing; no karaoke, pop, fade, or word-at-a-time flashing."""
    from PIL import ImageFont
    try:
        font = ImageFont.truetype('DejaVuSans-Bold.ttf', 58)
        measure = font.getlength
    except OSError:
        measure = lambda value: len(value) * 35
    cues: list[tuple[float, float, str]] = []
    for segment in segments:
        start = max(0.0, float(segment.start) - offset, cues[-1][1] if cues else 0.0)
        end = min(duration, float(segment.end) - offset)
        words = str(segment.text).split()
        if not words or end - start < .8:
            continue
        chunks, lines, current = [], [], ''
        for word in words:
            proposal = (current + ' ' + word).strip()
            if current and measure(proposal) > 680:
                lines.append(current)
                current = word
                if len(lines) == 2:
                    chunks.append('\n'.join(lines))
                    lines = []
            else:
                current = proposal
        if current:
            lines.append(current)
        if lines:
            chunks.append('\n'.join(lines))
        # Equal phrase holds prevent a final one-word remainder from flashing
        # for only a few frames after a longer two-line cue.
        for position, phrase in enumerate(chunks):
            cue_start = start + (end - start) * position / len(chunks)
            cue_end = start + (end - start) * (position + 1) / len(chunks)
            cues.append((cue_start, cue_end, phrase))
    return cues


def media_issues(probe: dict) -> list[str]:
    issues = []
    try:
        duration = float(probe.get('format', {}).get('duration', 0))
    except (TypeError, ValueError):
        duration = 0
    if not math.isfinite(duration) or not 20 <= duration <= MAX_SECONDS:
        issues.append('Durasi encoded harus 20–55 detik; target 30 detik.')
    streams = probe.get('streams') or []
    video = next((row for row in streams if row.get('codec_type') == 'video'), {})
    if (video.get('width'), video.get('height')) != (1080, 1920):
        issues.append('Video harus portrait 1080×1920.')
    if video.get('codec_name') != 'h264':
        issues.append('Video harus memakai H.264.')
    if not any(row.get('codec_type') == 'audio' for row in streams):
        issues.append('Audio tidak ditemukan.')
    return issues
