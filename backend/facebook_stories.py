"""Topic-driven Facebook stories: any operator topic becomes a varied short video.

The visual language follows the familiar Indonesian "dulu vs sekarang",
"mitos vs fakta" and "three small steps" formats. No real person, footage,
third-party music, or unverified claim is used. An operator types one topic;
the style is chosen automatically so consecutive posts do not look identical.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re

from llm import AIConfig, chat_completion, extract_json

import facebook_motion as motion
import facebook_strategy as strategy

VERSION = 1
SERIES_KEY = 'topik'
MAX_TOPIC_CHARS = 140
ICONS = ('clock', 'chat', 'spark', 'alert', 'check', 'lightbulb', 'list', 'hand', 'star', 'heart', 'book', 'phone', 'people', 'question')

STYLES = {
    'dulu_sekarang': dict(
        label='Dulu vs Sekarang', layout='compare', title_prefix='Dulu vs Sekarang',
        concept='Membandingkan kebiasaan lama dan cara sekarang tanpa menghakimi.',
        hashtags=('#BedaZaman', '#CeritaSehariHari'), accent='#168F85', accent_soft='#E4EFE5',
        panels=(
            dict(label='Dulu', caption='Lebih sederhana, kadang serba cepat.', icon='clock'),
            dict(label='Sekarang', caption='Pilihan lebih banyak, perlu lebih sadar.', icon='spark'),
        )),
    'mitos_fakta': dict(
        label='Mitos vs Fakta', layout='compare', title_prefix='Mitos atau Fakta',
        concept='Memisahkan cerita yang beredar dari kebiasaan memeriksa sumber.',
        hashtags=('#MitosAtauFakta', '#CekDulu'), accent='#6DAEDD', accent_soft='#E6EEF7',
        panels=(
            dict(label='Anggapan', caption='Sering beredar dari mulut ke mulut.', icon='alert'),
            dict(label='Fakta', caption='Perlu dicek dengan sumber yang jelas.', icon='check'),
        )),
    'salah_benar': dict(
        label='Keliru vs Tepat', layout='compare', title_prefix='Keliru atau Tepat',
        concept='Menunjukkan urutan langkah yang lebih aman dan masuk akal.',
        hashtags=('#CaraTepat', '#TipsSehariHari'), accent='#E9947D', accent_soft='#F7E6DF',
        panels=(
            dict(label='Keliru', caption='Terburu-buru tanpa memeriksa.', icon='alert'),
            dict(label='Tepat', caption='Pelan, jelas, dan sesuai kebutuhan.', icon='check'),
        )),
    'masalah_solusi': dict(
        label='Masalah & Solusi', layout='compare', title_prefix='Masalah dan Solusi',
        concept='Mengenali masalah lalu mencoba satu langkah kecil yang aman.',
        hashtags=('#SolusiSederhana', '#CeritaSehariHari'), accent='#F8C262', accent_soft='#FAF0D9',
        panels=(
            dict(label='Masalah', caption='Terasa mengganggu dan berulang.', icon='alert'),
            dict(label='Solusi', caption='Satu langkah kecil yang bisa dicoba.', icon='lightbulb'),
        )),
    'tiga_langkah': dict(
        label='Tiga Langkah', layout='steps', title_prefix='Tiga Langkah',
        concept='Memecah topik menjadi tiga langkah yang mudah diikuti.',
        hashtags=('#TigaLangkah', '#TipsSehariHari'), accent='#168F85', accent_soft='#E4EFE5',
        panels=(
            dict(label='Satu', caption='Siapkan kebutuhan.', icon='list'),
            dict(label='Dua', caption='Lakukan satu langkah.', icon='hand'),
            dict(label='Tiga', caption='Periksa hasilnya.', icon='check'),
        )),
    'pilihan_a_b': dict(
        label='Pilihan A atau B', layout='compare', title_prefix='Pilihan A atau B',
        concept='Membandingkan dua pilihan dengan batasannya masing-masing.',
        hashtags=('#PilihSesuaiKebutuhan', '#CeritaSehariHari'), accent='#8F9CC3', accent_soft='#E9EBF4',
        panels=(
            dict(label='Pilihan A', caption='Cocok untuk situasi tertentu.', icon='star'),
            dict(label='Pilihan B', caption='Punya batasan yang berbeda.', icon='heart'),
        )),
    'moral_anak': dict(
        label='Cerita Moral Anak', layout='compare', title_prefix='Cerita Moral',
        concept='Satu kebiasaan baik ditunjukkan lewat kejadian sederhana di sekolah atau di rumah.',
        hashtags=('#CeritaMoral', '#AnakSekolah', '#KebiasaanBaik'), accent='#3E8E6F', accent_soft='#E6F1E8',
        panels=(
            dict(label='Keadaan', caption='Situasi sederhana yang mudah dikenali.', icon='people'),
            dict(label='Pilihan baik', caption='Satu langkah kecil yang bisa ditiru.', icon='heart'),
        )),
}
STYLE_KEYS = tuple(STYLES)
NARRATION_STAGE_TITLES = {
    'compare': ('Pertanyaan', 'Konteks', 'Bandingkan', 'Kesimpulan'),
    'steps': ('Pertanyaan', 'Konteks', 'Tiga langkah', 'Kesimpulan'),
}
STYLE_HINTS = (
    (('dulu', 'sekarang', 'zaman', 'dahulu', 'perubahan', 'berubah'), 'dulu_sekarang'),
    (('mitos', 'fakta', 'hoax', 'hoaks', 'anggapan', 'katanya'), 'mitos_fakta'),
    (('salah', 'keliru', 'kesalahan', 'benar', 'tepat'), 'salah_benar'),
    (('masalah', 'solusi', 'atasi', 'mengatasi', 'keluhan'), 'masalah_solusi'),
    (('cara', 'tips', 'trik', 'langkah', 'panduan', 'mulai'), 'tiga_langkah'),
    (('pilih', 'pilihan', 'atau', 'banding', 'beda'), 'pilihan_a_b'),
    (('moral', 'akhlak', 'jujur', 'sopan', 'sabar', 'berbagi', 'tolong', 'maaf',
      'terima kasih', 'sekolah', 'guru', 'teman', 'anak'), 'moral_anak'),
)
UNSAFE = re.compile(r'\b(?:bokep|porno|judi|slot|narkoba|senjata|bunuh|teroris|pinjol|crypto|investasi|obat terlarang)\b', re.I)
CLAIMS = re.compile(r'\b(?:dijamin|pasti sembuh|menyembuhkan|100\s*%|menghasilkan uang|password|otp|kode verifikasi|nomor rekening)\b', re.I)
FRAMING = re.compile(r'\b(?:contoh|cerita|pengalaman|kebiasaan|situasi|bandingkan|banding|langkah)\b', re.I)
URL_OR_HANDLE = re.compile(r'(?:https?://|www\.|@\w+|#\w+)', re.I)

# A rotating bank keeps scheduled production varied without an operator edit.
DEFAULT_TOPICS = (
    dict(text='beda zaman cara guru menangani murid lupa PR', style='dulu_sekarang'),
    dict(text='beda zaman cara belajar sebelum dan sesudah ada internet', style='dulu_sekarang'),
    dict(text='dulu dan sekarang cara orang berkirim kabar', style='dulu_sekarang'),
    dict(text='perubahan cara anak bermain dari zaman dulu ke sekarang', style='dulu_sekarang'),
    dict(text='beda cara orang tua mengajarkan sopan santun dulu dan sekarang', style='dulu_sekarang'),
    dict(text='mitos makan telur menyebabkan bisul', style='mitos_fakta'),
    dict(text='anggapan minum air dingin saat batuk', style='mitos_fakta'),
    dict(text='mitos membaca di tempat gelap merusak mata', style='mitos_fakta'),
    dict(text='anggapan keramas malam hari bikin sakit kepala', style='mitos_fakta'),
    dict(text='mitos anak kecil tidak boleh keluar malam', style='mitos_fakta'),
    dict(text='kesalahan menyimpan foto di HP yang bikin penuh', style='salah_benar'),
    dict(text='cara keliru mengatur notifikasi aplikasi', style='salah_benar'),
    dict(text='kesalahan kecil saat mengisi nama file', style='salah_benar'),
    dict(text='kesalahan memindahkan file tanpa memeriksa tujuan', style='salah_benar'),
    dict(text='cara mengatasi anak terlalu lama main HP', style='masalah_solusi'),
    dict(text='mengatasi file dan foto yang memenuhi penyimpanan', style='masalah_solusi'),
    dict(text='solusi notifikasi grup yang terlalu ramai', style='masalah_solusi'),
    dict(text='cara mengatasi meja belajar yang berantakan', style='masalah_solusi'),
    dict(text='tiga langkah merapikan foto di HP', style='tiga_langkah'),
    dict(text='tiga langkah mengatur pengingat harian', style='tiga_langkah'),
    dict(text='tips menyiapkan bekal sekolah pagi hari', style='tiga_langkah'),
    dict(text='tiga langkah memeriksa file sebelum menghapus', style='tiga_langkah'),
    dict(text='memilih menyimpan foto di HP atau cloud', style='pilihan_a_b'),
    dict(text='memilih belajar pagi atau malam', style='pilihan_a_b'),
    dict(text='memilih aplikasi catatan atau buku tulis', style='pilihan_a_b'),
    dict(text='memilih mengatur notifikasi atau mematikan semuanya', style='pilihan_a_b'),
    dict(text='anak jujur mengembalikan uang kembalian di kantin sekolah', style='moral_anak'),
    dict(text='meminta maaf setelah tidak sengaja menjatuhkan buku teman', style='moral_anak'),
    dict(text='berbagi alat tulis dengan teman yang lupa membawa', style='moral_anak'),
    dict(text='mengucap terima kasih setelah dibantu guru di kelas', style='moral_anak'),
    dict(text='antre rapi di kantin sekolah saat istirahat', style='moral_anak'),
    dict(text='menolong teman yang terjatuh di halaman sekolah', style='moral_anak'),
    dict(text='merapikan meja belajar setelah selesai digunakan', style='moral_anak'),
    dict(text='mendengarkan penjelasan guru tanpa menyela teman', style='moral_anak'),
    dict(text='mengakui kesalahan saat lupa mengerjakan PR', style='moral_anak'),
    dict(text='menyapa tetangga dengan sopan saat pulang sekolah', style='moral_anak'),
    dict(text='membantu merapikan meja makan di rumah setelah makan', style='moral_anak'),
)
_BANK_TEXT = {row['text'].casefold() for row in DEFAULT_TOPICS}


def _hash(value: str) -> int:
    return int(hashlib.sha256(value.encode()).hexdigest()[:12], 16)


def normalize_topic(value) -> str:
    if not isinstance(value, str):
        raise ValueError('Topik video wajib berupa teks.')
    text = re.sub(r'\s+', ' ', value).strip().strip('.,;:!?')
    text = re.sub(r'^(?:topik|ide|judul)\s*[:：-]\s*', '', text, flags=re.I)
    if len(text) < 4:
        raise ValueError('Topik terlalu pendek; tulis minimal empat karakter.')
    if len(text) > MAX_TOPIC_CHARS:
        raise ValueError(f'Topik maksimal {MAX_TOPIC_CHARS} karakter.')
    if not re.search(r'[A-Za-z]', text):
        raise ValueError('Topik harus memuat kata, bukan hanya angka atau simbol.')
    if URL_OR_HANDLE.search(text) or re.search(r'[\x00-\x1f]', text):
        raise ValueError('Topik tidak boleh memuat tautan, akun, tagar, atau karakter kontrol.')
    if UNSAFE.search(text):
        raise ValueError('Topik ini tidak dapat diproduksi karena batas keamanan konten.')
    return text


def resolve_style(topic: str, style=None, seed: str = '') -> str:
    if style is not None:
        if style not in STYLES:
            raise ValueError('Gaya cerita tidak tersedia.')
        return style
    folded = topic.casefold()
    best_key, best_score = None, 0
    for words, key in STYLE_HINTS:
        score = sum(1 for word in words if re.search(r'\b' + re.escape(word) + r'\b', folded))
        if score > best_score:
            best_key, best_score = key, score
    if best_key:
        return best_key
    return STYLE_KEYS[_hash(seed + ':' + topic + ':style') % len(STYLE_KEYS)]


def display_topic(topic: str, style: str) -> str:
    """Drop a redundant style prefix so titles and narration stay natural."""
    if style == 'dulu_sekarang':
        value = re.sub(r'^(?:beda\s+zaman|dulu\s+dan\s+sekarang|dulu\s+vs\s+sekarang|perubahan)\s+', '', topic, flags=re.I)
    elif style == 'mitos_fakta':
        value = re.sub(r'^(?:mitos|anggapan|katanya)\s+', '', topic, flags=re.I)
    else:
        return topic
    return value.strip() or topic


def choose_topic(seed: str, recent=(), recent_styles=()) -> dict:
    """Pick a bank topic that avoids recent text and repeats the same style last."""
    used = {str(value).casefold() for value in recent if value}
    pool = [row for row in DEFAULT_TOPICS if row['text'].casefold() not in used] or list(DEFAULT_TOPICS)
    banned = set(recent_styles[-3:])
    fresh = [row for row in pool if row['style'] not in banned]
    if fresh:
        pool = fresh
    bucket = _hash(seed + ':topic') % len(pool)
    return dict(pool[bucket])


def _safe_title(prefix: str, topic: str) -> str:
    title = f'{prefix}: {topic}'
    if len(title) > 80:
        room = max(12, 80 - len(prefix) - 2)
        title = f'{prefix}: {topic[:room].rsplit(" ", 1)[0].rstrip(" ,;:")}…'
    return strategy.public_caption(title) or prefix


def _fallback_narration(style: str, topic: str) -> list[str]:
    rows = {
        'dulu_sekarang': [
            'Dulu dan sekarang, apa yang benar-benar berubah?',
            f'Kita bahas {topic}. Pengalaman setiap orang bisa berbeda.',
            'Dulu, kebiasaan ini sering dijalani tanpa banyak pilihan. Sekarang, cara dan alatnya lebih beragam, '
            'tetapi tujuannya tetap sama: membuat hidup terasa lebih mudah.',
            'Tidak semua perubahan harus diikuti. Ambil yang masuk akal, tinggalkan yang tidak sesuai. '
            'Ini cerita ringan, bukan patokan mutlak untuk semua orang.',
        ],
        'mitos_fakta': [
            'Anggapan dan fakta, mana yang lebih masuk akal?',
            f'Kita bahas {topic}. Banyak cerita beredar, jadi perlu diperiksa.',
            'Anggapan lama sering terdengar meyakinkan karena diulang. Namun, cerita yang diulang belum tentu benar. '
            'Cek sumber yang jelas sebelum mempercayai atau membagikannya.',
            'Kalau masih ragu, tanyakan kepada orang yang paham. Jangan langsung percaya pada satu cerita. '
            'Ini contoh cara berpikir kritis, bukan vonis untuk semua situasi.',
        ],
        'salah_benar': [
            'Cara lama dan cara tepat, apa bedanya?',
            f'Kita bahas {topic}. Kesalahan kecil sering terasa biasa.',
            'Sering kali masalahnya bukan niat, tetapi urutan langkah. Mulai dari hal paling sederhana. '
            'Periksa hasilnya, lalu perbaiki tanpa menyalahkan diri sendiri.',
            'Tidak ada cara yang sempurna untuk semua orang. Pilih langkah yang paling aman dan sesuai kebutuhan. '
            'Ini cerita dan contoh, bukan aturan mutlak.',
        ],
        'masalah_solusi': [
            'Masalah ini sering terjadi. Apa solusinya?',
            f'Kita bahas {topic}. Setiap situasi punya batasannya sendiri.',
            'Kenali masalahnya dulu. Pilih satu langkah kecil yang paling masuk akal. '
            'Lakukan pelan-pelan, lalu periksa apakah ada perubahan.',
            'Kalau belum berhasil, coba cara lain tanpa memaksakan. '
            'Ini cerita ringan dan contoh, bukan jaminan hasil untuk semua orang.',
        ],
        'tiga_langkah': [
            'Tiga langkah sederhana untuk memulai.',
            f'Kita bahas {topic}. Tidak perlu langsung sempurna.',
            'Satu, siapkan kebutuhan yang paling dekat. Dua, lakukan satu langkah kecil. '
            'Tiga, periksa hasilnya sebelum lanjut ke langkah berikutnya.',
            'Mulai dari satu langkah hari ini. Ulangi sampai terasa nyaman. '
            'Ini contoh ringan, bukan patokan mutlak untuk semua orang.',
        ],
        'pilihan_a_b': [
            'Dua pilihan, satu kebutuhan. Mana yang pas?',
            f'Kita bahas {topic}. Keduanya punya sisi yang berbeda.',
            'Pilihan pertama bisa terasa cepat, tetapi punya batasan. Pilihan kedua mungkin lebih tenang, '
            'tetapi butuh waktu. Sesuaikan dengan kebutuhan, bukan dengan tekanan orang lain.',
            'Tidak ada pilihan yang sempurna untuk semua orang. Coba, perhatikan hasilnya, lalu sesuaikan. '
            'Ini cerita dan contoh, bukan keputusan mutlak.',
        ],
        'moral_anak': [
            'Apa yang bisa kita lakukan hari ini?',
            f'Kita bahas {topic}. Cerita ini bisa terjadi di sekolah atau di rumah.',
            'Situasinya sederhana. Ada pilihan yang terasa mudah, dan ada pilihan yang lebih baik. '
            'Kita lihat apa yang terjadi kalau satu langkah kecil dilakukan dengan sengaja.',
            'Satu kebiasaan baik tidak perlu besar untuk berarti. Coba di rumah atau di sekolah bersama teman. '
            'Ini cerita dan contoh, bukan aturan yang sama untuk semua orang.',
        ],
    }
    return rows[style]


def _fallback_caption(style: str, title: str) -> str:
    caption = strategy.public_caption(f'{title}. Pilih yang paling masuk akal untuk situasi masing-masing.')
    return caption + '\n\n' + ' '.join('#' + tag for tag in STYLES[style]['hashtags'])


def plan(seed: str, kind: str = 'reel', topic=None, style=None) -> dict:
    topic_text = normalize_topic(topic)
    style = resolve_style(topic_text, style, seed)
    spec = STYLES[style]
    panels = [dict(row) for row in spec['panels']]
    narration = _fallback_narration(style, display_topic(topic_text, style))
    title = _safe_title(spec['title_prefix'], display_topic(topic_text, style))
    story = dict(version=VERSION, style=style, layout=spec['layout'], topic_text=topic_text,
                 concept=spec['concept'], panels=panels, authored=False,
                 original_storyboard=True, claims='relatable_framing', cast='host')
    result = dict(version=1, seed=seed, kind=kind, topic='story', series=SERIES_KEY,
                  custom_topic=topic_text, title=title,
                  stages=[dict(title=name, text=text) for name, text in
                          zip(NARRATION_STAGE_TITLES[spec['layout']], narration)],
                  files=[], caption=_fallback_caption(style, title),
                  visual_type='authored_topic_motion', third_party_footage=False,
                  third_party_music=False, synthetic_voice=True,
                  narration_provider='edge_neural_id-ID-ArdiNeural', story=story,
                  creative_policy=dict(version=2, niche='Cerita sehari-hari', pillar=style,
                      pillar_label=spec['label'], basis='operator_topic',
                      format=style, captions_stable=True, first_result_preview=None,
                      source_clock_changed=False, views_guaranteed=False),
                  motion_version=motion.VERSION, render_engine='motlab')
    result['plan_sha256'] = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return result


def script_identity(source_plan) -> str:
    text = ' '.join(stage['text'] for stage in source_plan['stages']).casefold()
    return hashlib.sha256(re.sub(r'\W+', ' ', text).strip().encode()).hexdigest()


def _validated_ai(raw, style):
    if not isinstance(raw, dict):
        raise ValueError('Naskah AI bukan objek JSON.')
    lines = raw.get('narration')
    if not isinstance(lines, list) or len(lines) != 4 or not all(isinstance(row, str) and row.strip() for row in lines):
        raise ValueError('Empat tahap narasi wajib lengkap.')
    lines = [re.sub(r'\s+', ' ', row).strip() for row in lines]
    count = sum(len(row.split()) for row in lines)
    if not 50 <= count <= 110:
        raise ValueError('Panjang narasi cerita belum sesuai.')
    if len(lines[0].split()) > 10 or len(lines[1].split()) > 20 or any(len(row.split()) > 38 for row in lines[2:]):
        raise ValueError('Salah satu tahap narasi terlalu panjang.')
    joined = ' '.join(lines)
    if URL_OR_HANDLE.search(joined) or CLAIMS.search(joined) or not FRAMING.search(joined):
        raise ValueError('Narasi memuat klaim atau tautan yang tidak diizinkan.')
    panels = raw.get('panels')
    if not isinstance(panels, list) or not 2 <= len(panels) <= 3:
        raise ValueError('Panel cerita harus dua atau tiga.')
    clean = []
    for row in panels:
        if not isinstance(row, dict):
            raise ValueError('Panel cerita tidak valid.')
        label = re.sub(r'\s+', ' ', str(row.get('label') or '')).strip()
        caption = re.sub(r'\s+', ' ', str(row.get('caption') or '')).strip()
        icon = str(row.get('icon') or '').strip()
        if not 2 <= len(label) <= 26 or not 3 <= len(caption) <= 74 or icon not in ICONS:
            raise ValueError('Label, keterangan, atau ikon panel tidak sesuai.')
        if URL_OR_HANDLE.search(label + ' ' + caption) or CLAIMS.search(label + ' ' + caption):
            raise ValueError('Panel memuat tautan atau klaim terlarang.')
        clean.append(dict(label=label, caption=caption, icon=icon))
    title = re.sub(r'\s+', ' ', str(raw.get('title') or '')).strip()
    caption = re.sub(r'\s+', ' ', str(raw.get('caption') or '')).strip()
    if not 8 <= len(title) <= 80 or not 10 <= len(caption) <= 220:
        raise ValueError('Judul atau caption AI belum valid.')
    if URL_OR_HANDLE.search(title + ' ' + caption) or CLAIMS.search(title + ' ' + caption):
        raise ValueError('Judul atau caption memuat klaim terlarang.')
    return dict(title=title, narration=lines, panels=clean, caption=caption)


def author(source_plan, previous=(), config=None):
    """Author a fresh script from the operator topic, then keep a safe fallback."""
    previous = set(previous)
    plan = deepcopy(source_plan)
    config = config or {}
    if config.get('base_url') and config.get('model'):
        try:
            raw = extract_json(chat_completion(AIConfig(enabled=True, base_url=config['base_url'],
                model=config['model'], api_key=config.get('api_key', ''), timeout=90), [
                {'role': 'system', 'content':
                    'Anda penulis naskah video pendek Facebook berbahasa Indonesia yang hangat dan jujur. '
                    'Buat naskah orisinal untuk topik dari operator dengan gaya yang diminta. '
                    'Empat tahap: pertanyaan pemancing (maksimal 10 kata), konteks topik (maksimal 20 kata), '
                    'penjelasan panel (maksimal 38 kata), lalu kesimpulan dan batasan (maksimal 38 kata). '
                    'Gunakan bahasa sehari-hari dan akui bahwa pengalaman setiap orang bisa berbeda. '
                    'Jangan mengarang fakta, angka, nama orang nyata, sumber, tautan, tagar, emoji, atau ajakan engagement. '
                    'Jangan membuat klaim kesehatan, keamanan, keuangan, atau janji hasil. '
                    'Panel dua atau tiga buah; label 2-26 karakter, keterangan 3-74 karakter. '
                    'Ikon panel hanya dari daftar yang diberikan. '
                    'Judul 8-80 karakter tanpa tautan. Caption 10-220 karakter tanpa hashtag. '
                    'Wajib memuat kata contoh, cerita, pengalaman, kebiasaan, situasi, atau langkah. '
                    'Jika audiensnya anak sekolah, pakai kalimat pendek dan satu kebiasaan baik yang jelas, '
                    'beri contoh di sekolah atau di rumah, jangan menakut-nakuti, menghakimi, atau memaksakan '
                    'keyakinan; biarkan anak melihat akibat dari pilihannya. '
                    'Balas JSON {"title":"...","narration":["...","...","...","..."],'
                    '"panels":[{"label":"...","caption":"...","icon":"..."}],"caption":"..."}.'},
                {'role': 'user', 'content': json.dumps(dict(
                    topic=plan['story']['topic_text'], style=plan['story']['style'],
                    style_label=STYLES[plan['story']['style']]['label'],
                    audience=('Anak sekolah dan keluarga' if plan['story']['style'] == 'moral_anak'
                              else 'Keluarga umum'),
                    layout=plan['story']['layout'], allowed_icons=list(ICONS),
                    panel_count=len(plan['story']['panels'])), ensure_ascii=False)},
            ], temperature=0.7))
            value = _validated_ai(raw, plan['story']['style'])
            plan['title'] = strategy.public_caption(value['title']) or plan['title']
            for stage, text in zip(plan['stages'], value['narration']):
                stage['text'] = text
            plan['story']['panels'] = value['panels']
            plan['story']['layout'] = 'steps' if len(value['panels']) == 3 else 'compare'
            hashtags = STYLES[plan['story']['style']]['hashtags']
            plan['caption'] = strategy.public_caption(value['caption']) + '\n\n' + ' '.join('#' + tag for tag in hashtags)
            plan['story']['authored'] = True
            plan['authoring'] = 'fresh_topic_script_pending_independent_qc'
        except Exception:
            plan['authoring'] = 'template_storyboard'
    else:
        plan['authoring'] = 'template_storyboard'
    identity = script_identity(plan)
    if identity in previous:
        raise ValueError('Naskah cerita identik sudah pernah diproduksi; pilih topik lain.')
    plan['script_sha256'] = identity
    return plan


def verify_plan(value):
    story = value.get('story')
    if not isinstance(story, dict) or story.get('version') != VERSION:
        raise ValueError('Bukti cerita topik belum lengkap.')
    if story.get('original_storyboard') is not True or story.get('claims') != 'relatable_framing':
        raise ValueError('Kebijakan cerita topik berubah.')
    if value.get('render_engine') != 'motlab' or value.get('motion_version') != motion.VERSION:
        raise ValueError('Engine render cerita topik tidak sesuai.')
    if value.get('third_party_footage') is not False or value.get('third_party_music') is not False:
        raise ValueError('Cerita topik tidak boleh memakai footage atau musik pihak lain.')
    if normalize_topic(story.get('topic_text')) != story.get('topic_text') or value.get('custom_topic') != story.get('topic_text'):
        raise ValueError('Topik cerita berubah dari sumber.')
    if story.get('style') not in STYLES or story.get('layout') not in {'compare', 'steps'}:
        raise ValueError('Gaya cerita topik tidak dikenal.')
    panels = story.get('panels')
    want = 3 if story['layout'] == 'steps' else 2
    if not isinstance(panels, list) or len(panels) != want:
        raise ValueError('Jumlah panel cerita tidak sesuai.')
    for row in panels:
        if (not isinstance(row, dict) or not 2 <= len(str(row.get('label') or '')) <= 26
                or not 3 <= len(str(row.get('caption') or '')) <= 74
                or row.get('icon') not in ICONS):
            raise ValueError('Panel cerita tidak valid.')
        if URL_OR_HANDLE.search(str(row.get('label')) + ' ' + str(row.get('caption'))) or CLAIMS.search(str(row.get('caption'))):
            raise ValueError('Panel cerita memuat klaim atau tautan.')
    stages = value.get('stages')
    if not isinstance(stages, list) or len(stages) != 4:
        raise ValueError('Empat tahap cerita wajib lengkap.')
    texts = [str(stage.get('text') or '') for stage in stages]
    if not all(texts) or URL_OR_HANDLE.search(' '.join(texts)) or CLAIMS.search(' '.join(texts)):
        raise ValueError('Narasi cerita tidak valid.')
    if not 40 <= sum(len(text.split()) for text in texts) <= 120 or not FRAMING.search(' '.join(texts)):
        raise ValueError('Panjang atau kerangka narasi cerita belum sesuai.')
    if 'http://' in str(value.get('caption')).lower() or 'https://' in str(value.get('caption')).lower():
        raise ValueError('Caption cerita masih memuat tautan.')


def timeline(plan, segments=()):
    stages = plan['stages']
    if len(stages) != 4:
        raise ValueError('Empat tahap cerita wajib lengkap.')
    begin, end = stages[2]['start'], stages[2]['end']
    if end - begin < 2.1:
        raise ValueError('Narasi meninggalkan ruang gerak yang terlalu singkat.')
    story = plan['story']
    panels = story['panels']
    if story['layout'] == 'steps':
        span = max(.45, (end - begin) / max(1, len(panels) - 1))
        reveals = [round(min(end - .15, begin + index * span), 3) for index in range(len(panels))]
    else:
        reveals = [round(stages[1]['start'] + .35, 3), round(begin + .4, 3)]
    reveals[0] = max(round(stages[1]['start'] + .2, 3), min(reveals[0], begin))
    for index in range(1, len(reveals)):
        reveals[index] = max(reveals[index - 1] + .35, reveals[index])
    reveals[-1] = min(reveals[-1], end - .1)
    if not all(math.isfinite(value) for value in reveals) or reveals[-1] <= reveals[0]:
        raise ValueError('Waktu panel cerita tidak dapat dihitung.')
    select = round(stages[1]['start'] + .25, 3)
    departure = reveals[0]
    arrival = reveals[-1]
    return dict(version=VERSION, fps=motion.FPS,
                alignment='measured_tts_phrase_with_story_panel_clock',
                select=select, departure=departure, arrival=arrival,
                reveals=reveals, complete=round(stages[3]['start'] + .35, 3),
                search_reset=round(arrival, 3), compare=round(arrival, 3),
                inspect=round(stages[3]['start'] + .4, 3),
                phase_order=['kenali', 'bandingkan', 'simpulkan'],
                label='CERITA SEHARI-HARI', source_clock_changed=False)


def scene(plan, t):
    clock = plan.get('motion_timeline') or timeline(plan)
    stages = plan['stages']
    story = plan['story']
    reveals = clock['reveals']
    panels = []
    for index, row in enumerate(story['panels']):
        at = reveals[min(index, len(reveals) - 1)]
        progress = motion.ease((t - at) / .55)
        panels.append(dict(**row, id=f'panel-{index}', at=at,
                           reveal=round(progress, 4), active=t >= at))
    phase = 0 if t < stages[1]['start'] else 1 if t < stages[2]['start'] else 2 if t < stages[3]['start'] else 3
    return dict(version=VERSION, style=story['style'], layout=story['layout'], phase=phase,
                topic_text=story['topic_text'], panels=panels, complete=t >= clock['complete'],
                clock=clock)


def frame(plan, t, cues):
    """Pillow fallback used only by legacy paths; new plans render through Motlab."""
    from PIL import Image, ImageDraw, ImageFont
    model = scene(plan, t)
    image = Image.new('RGB', (1080, 1920), '#F6F4E9')
    draw = ImageDraw.Draw(image)
    accent = STYLES[model['style']]['accent']
    draw.ellipse((-260, 310, 670, 1240), fill='#E4EFE5')
    draw.ellipse((650, 400, 1420, 1150), fill='#F4E2CD')
    bold = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 56)
    small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 26)
    draw.text((85, 95), 'RYUUNDY  /  CERITA SEHARI-HARI', font=small, fill=accent)
    draw.text((85, 160), plan['title'][:48], font=bold, fill='#173B45')
    for index, panel in enumerate(model['panels']):
        x = 70 + index * 480
        y = 560 + round(60 * (1 - panel['reveal']))
        draw.rounded_rectangle((x, y, x + 450, y + 620), radius=40, fill='#FFFFFF', outline=accent, width=4)
        draw.text((x + 32, y + 36), panel['label'], font=bold, fill=accent)
        draw.multiline_text((x + 32, y + 130), panel['caption'], font=small, fill='#173B45')
    cue = next((row for row in cues if row[0] <= t < row[1]), None)
    if cue:
        for index, line in enumerate(cue[2].splitlines()):
            width = draw.textlength(line, font=bold)
            draw.text(((1080 - width) / 2, 1435 + index * 69), line, font=bold, fill='#173B45')
    return image
