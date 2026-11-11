"""Chinese/Korean drama discovery under RYUUNDY's story-first cron contract."""
from __future__ import annotations

import re
import os
from typing import Any
from ryuundy_reference_learning import clean_topic_text


DRAMA_THEME_SIGNALS = {
    'chinese_drama_story': {'drama china', 'drama cina', 'drama tiongkok', 'drama mandarin',
                           'chinese drama', 'cdrama', 'c drama', 'dracin'},
    'korean_drama_story': {'drama korea', 'korean drama', 'kdrama', 'k drama', 'drakor'},
}
DRAMA_THEME_PROFILES = {
    'chinese_drama_story': {
        'label': 'Drama China: Pilihan, Keluarga & Plot Twist',
        'tone': 'story-first khas RYUUNDY: emosional, empatik, dan reflektif; perlakukan drama sebagai fiksi, dengan narasi Bahasa Indonesia yang didukung sumber',
        'short_role': 'pilih satu konflik, keputusan tokoh, dan konsekuensi/payoff yang tuntas; utamakan keluarga, kepercayaan, pengkhianatan, atau bangkit; jangan memotong ending tepat sebelum jawabannya',
        'long_role': 'lengkapi setup, motif tokoh, sebab-akibat, perubahan hubungan, dan akibat akhir dari sumber yang sama; tambahkan analisis karakter yang spesifik, tanpa mengulang Short atau mengarang dialog',
        'duration_filter': 'any',
        'queries': [
            'ulasan drama china konflik keluarga analisis karakter bahasa indonesia',
            'alur cerita drama china pengkhianatan dan konsekuensi narasi indonesia',
            'dracin pilihan tokoh plot twist pelajaran hidup ulasan indonesia',
            'analisis cerita drama mandarin jatuh bangkit keluarga indonesia',
        ],
    },
    'korean_drama_story': {
        'label': 'Drama Korea: Hubungan, Konsekuensi & Pelajaran Hidup',
        'tone': 'story-first khas RYUUNDY: hangat, emosional, dan tidak menghakimi; bedakan tokoh fiksi dari aktornya, dengan narasi Bahasa Indonesia yang didukung sumber',
        'short_role': 'angkat satu pilihan sulit atau perubahan kepercayaan dengan konteks singkat dan payoff utuh; prioritaskan hubungan, persahabatan, keluarga, atau comeback, bukan kompilasi adegan romantis acak',
        'long_role': 'susun konteks hubungan, keputusan, konsekuensi, dan perkembangan karakter; pertahankan kronologi serta penutup dari sumber yang sama, lalu jelaskan makna yang belum muat dalam Short',
        'duration_filter': 'any',
        'queries': [
            'ulasan drama korea konflik keluarga analisis karakter bahasa indonesia',
            'alur cerita drakor kepercayaan pengkhianatan konsekuensi narasi indonesia',
            'analisis drama korea persahabatan pilihan tokoh plot twist indonesia',
            'ulasan cerita drakor jatuh bangkit pelajaran hidup bahasa indonesia',
        ],
    },
}
STORY_SIGNALS = {'keluarga', 'hubungan', 'persahabatan', 'kepercayaan', 'pengkhianatan',
    'dikhianati', 'orang tua', 'ibu', 'ayah', 'cinta', 'pilihan', 'keputusan', 'konsekuensi',
    'penyesalan', 'bangkit', 'comeback', 'plot twist', 'pelajaran hidup', 'tanggung jawab',
    'family', 'friendship', 'betrayal', 'forgiveness', 'consequences'}
COMMENTARY_SIGNALS = {'ulasan', 'review', 'analisis', 'analysis', 'narasi', 'narration',
    'pembahasan', 'alur cerita', 'bedah cerita', 'bedah karakter'}
DRAMA_EDITOR_BRIEF = (
    'Cerita ini fiksi/dramatisasi: jangan melabelinya kisah nyata, berita, atau kajian agama. '
    'Pisahkan tokoh dari aktor; tindakan tokoh bukan pendapat pribadi pemerannya. '
    'Narasi Bahasa Indonesia harus mengikuti dialog atau terjemahan yang tersedia; '
    'jangan menebak terjemahan atau menambah adegan, identitas, motif, dan akhir cerita. '
    'Jaga siapa melakukan apa dan sebab-akibat tetap jelas. Efek mengikuti perubahan emosi '
    'yang benar-benar ada; adegan sedih tidak diberi efek lucu atau musik pesta.'
)


def drama_lane_enabled(theme: str) -> bool:
    # Korean drama is opt-in; Chinese drama joins the ordinary rotation.
    return theme != 'korean_drama_story' or os.environ.get(
        'AUTO_VIRAL_SCHEDULE_KOREAN_DRAMA_ENABLED', 'false'
    ).strip().casefold() in {'1', 'true', 'yes', 'on'}


def normalized(value: str) -> str:
    return ' ' + re.sub(r'[^a-z0-9]+', ' ', value.casefold()).strip() + ' '


def has_signal(text: str, signals: set[str]) -> bool:
    return any(normalized(signal) in text for signal in signals)


def drama_source_rejection_reason(info: dict[str, Any], theme: str) -> str:
    if theme not in DRAMA_THEME_PROFILES:
        return ''
    text = normalized('\n'.join(clean_topic_text(value) for value in [
        str(info.get('title') or ''), str(info.get('description') or ''),
        ' '.join(map(str, info.get('tags') or []))]))
    if not has_signal(text, DRAMA_THEME_SIGNALS[theme]):
        return 'sumber tidak mengidentifikasi asal drama yang sesuai dengan lane cron'
    if not has_signal(text, STORY_SIGNALS):
        return 'drama tidak menunjukkan konflik, pilihan, atau konsekuensi yang sesuai cerita RYUUNDY'
    if not has_signal(text, COMMENTARY_SIGNALS):
        return 'lane drama membutuhkan ulasan/analisis/narasi cerita; kompilasi adegan mentah dilewati'
    return ''


def drama_trend_query(value: str, theme: str) -> str:
    if theme not in DRAMA_THEME_PROFILES or not has_signal(normalized(value), DRAMA_THEME_SIGNALS[theme]):
        return ''
    origin = 'drama china' if theme == 'chinese_drama_story' else 'drama korea'
    return f'ulasan {origin} pilihan tokoh konflik keluarga narasi bahasa indonesia'


def drama_hashtags(theme: str, long_form: bool) -> list[str]:
    origin = 'DramaChina' if theme == 'chinese_drama_story' else 'DramaKorea'
    return [origin, 'CeritaFiksi', 'AnalisisKarakter', 'PilihanDanKonsekuensi',
            'CeritaRYUUNDY', 'VideoPanjang' if long_form else 'ShortsIndonesia']
