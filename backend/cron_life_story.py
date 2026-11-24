"""Owner-directed original life stories, admitted only by the scheduled campaign.

Reservations precede paid generation and survive restarts. Rendering and platform
submission retain their existing QC, license, identity and publication gates.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import fcntl
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
from zoneinfo import ZoneInfo

from failed_upload_cleanup import write_json

VERSION = 1
THEME = 'life_comeback'
SERIES = 'Langkah Kecil RYUUNDY'
REFERENCE = 'https://www.youtube.com/shorts/mTjyPANpdGw'
ROLES = ('hook', 'problem', 'decision', 'action', 'consequence', 'payoff')
TOPICS = (
    'Pekerja kehilangan pekerjaan, meminta informasi lowongan dan mendapat kesempatan kerja harian yang masuk akal',
    'Pedagang sepi pembeli, bertanya kebutuhan tetangga dan menguji pesanan kecil tanpa menambah utang',
    'Pekerja malu menerima pekerjaan sederhana, belajar menjaga kebutuhan pokok sambil mencari pekerjaan tetap',
    'Keluarga berselisih soal pengeluaran, mencatat kebutuhan bersama dan menyepakati satu perubahan kecil',
    'Sahabat merasa dilupakan, mengutarakan kebutuhan secara jelas tanpa menuduh semua teman meninggalkannya',
    'Anak dewasa lelah membandingkan pencapaian, memilih satu target realistis dan menyelesaikannya perlahan',
    'Pekerja kelelahan menerima semua permintaan, belajar menyampaikan batas waktu dengan sopan',
    'Usaha rumahan mendapat kritik, memeriksa satu keluhan nyata dan memperbaiki layanan tanpa janji berlebihan',
    'Orang tua dan anak salah paham lewat pesan singkat, memilih berbicara langsung dan saling mendengarkan',
    'Pekerja mendapat penghasilan pertama setelah masa sulit, memisahkan kebutuhan pokok dari belanja impulsif',
    'Tetangga sungkan meminta bantuan, menawarkan pertukaran keterampilan yang jelas dan saling menghargai',
    'Pelamar ditolak berkali-kali, memperbaiki satu contoh hasil kerja dan menerima masukan yang spesifik',
    'Pedagang mengambil terlalu banyak pesanan, menyampaikan batas kapasitas sebelum kualitas menurun',
    'Keluarga menghadapi rencana yang tertunda, membagi tugas kecil tanpa menyalahkan anggota keluarga',
    'Pekerja baru takut bertanya, mencatat instruksi dan mengonfirmasi tugas sebelum melakukan kesalahan',
    'Teman salah paham tentang pinjaman barang, mengembalikan barang dan menyepakati batas dengan jujur',
)
BRIEF = (
    'Arahan seri yang disetujui pemilik RYUUNDY: cerita kehidupan orisinal Indonesia, '
    'situasi konkret -> konflik -> keputusan -> tindakan -> konsekuensi -> penyelesaian. '
    'Tokoh dewasa konsisten, ilustrasi 2D orisinal, gerakan kamera lembut; '
    'caption frasa stabil tanpa kedipan. Empatik, tidak menghakimi. '
    'Tidak meniru tokoh, pakaian khas, dialog, suara, logo atau gambar referensi. '
    'Cerita merupakan ilustrasi fiksi, bukan kesaksian nyata atau nasihat profesional. '
    'Hindari klaim agama, diagnosis, investasi, janji sukses, tokoh publik dan penghinaan. '
    'Tindakan pertama muncul sebelum sepertiga durasi. Akhir menuntaskan masalah kecil, '
    'bukan menjanjikan semua kesulitan selesai. Maksimal satu pertanyaan pengalaman penonton.'
)


def read(path: Path) -> dict:
    if not path.exists():
        return {'version': VERSION, 'episodes': {}}
    state = json.loads(path.read_text())
    if (not isinstance(state, dict) or state.get('version') != VERSION
            or not isinstance(state.get('episodes'), dict)
            or any(not isinstance(row, dict) or not row.get('day') or not row.get('status')
                   for row in state['episodes'].values())):
        raise ValueError('Ledger cerita cron tidak valid; reservasi dipertahankan')
    return state


def today(now=None) -> str:
    return (now or datetime.now(ZoneInfo('Asia/Jakarta'))).astimezone(ZoneInfo('Asia/Jakarta')).date().isoformat()


def due(state: dict, plan: dict, limit: int, now=None) -> bool:
    lane = plan.get('lanes', {}).get('scheduled_short', {})
    day = today(now)
    attempts = sum(row.get('day') == day for row in state['episodes'].values())
    # Two experiments fit inside the existing 17; space the second after six
    # occupied slots. Failed attempts consume this feature's daily budget too.
    return bool(plan.get('enabled') and plan.get('day') == day and lane.get('remaining', 0) > 0
                and attempts < max(0, min(2, limit)) and (attempts == 0 or lane.get('used', 0) >= 6))


def reserve(path: Path, run_id: str, day: str, limit: int) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = read(path)
        if run_id in state['episodes']:
            return dict(state['episodes'][run_id])
        if sum(row.get('day') == day for row in state['episodes'].values()) >= min(2, max(0, limit)):
            raise ValueError('Jatah eksperimen cerita cron hari ini sudah terpakai')
        cutoff = (datetime.fromisoformat(day) - timedelta(days=7)).date().isoformat()
        recent = {row.get('topic') for row in state['episodes'].values() if row.get('day', '') >= cutoff}
        choices = [topic for topic in TOPICS if topic not in recent]
        if not choices:
            raise ValueError('Topik segar cerita cron belum tersedia')
        topic = choices[int(hashlib.sha256(run_id.encode()).hexdigest(), 16) % len(choices)]
        row = dict(day=day, topic=topic, status='reserved')
        state['episodes'][run_id] = row
        write_json(path, state)
        return dict(row)


def update(path: Path, run_id: str, **changes):
    with path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = read(path)
        state['episodes'][run_id].update(changes)
        write_json(path, state)


def tokens(text: str) -> set[str]:
    return set(re.findall(r'\w+', text.casefold()))


def validate(payload: dict, previous: list[str]) -> tuple[str, str]:
    if not isinstance(payload, dict):
        raise ValueError('Naskah cerita harus berupa objek')
    title, character = str(payload.get('title') or '').strip(), str(payload.get('character_bible') or '').strip()
    scenes = payload.get('scenes')
    if not 4 <= len(title.split()) <= 14 or len(character.split()) < 12:
        raise ValueError('Judul atau identitas karakter cerita belum lengkap')
    if not isinstance(scenes, list) or len(scenes) != len(ROLES):
        raise ValueError('Cerita wajib memiliki enam beat lengkap')
    paragraphs, narration, visuals = [], [], []
    for index, (scene, role) in enumerate(zip(scenes, ROLES), 1):
        if not isinstance(scene, dict) or scene.get('role') != role:
            raise ValueError('Urutan beat cerita tidak lengkap')
        voice, visual = str(scene.get('narration') or '').strip(), str(scene.get('visual') or '').strip()
        if '\n' in voice or '\n' in visual or not 12 <= len(voice.split()) <= 48 or len(visual.split()) < 10:
            raise ValueError('Narasi atau aksi visual cerita belum konkret')
        narration.append(voice); visuals.append(visual)
        paragraphs.append(f'## Adegan {index} — {role}\nNarasi: {voice}\nVisual: {character}. {visual}\n'
                          'Arahan sutradara: Ilustrasi 2D Indonesia orisinal, satu aksi yang terlihat; '
                          'kamera pelan, ekspresi sesuai narasi, tanpa tulisan di dalam gambar.')
    spoken = ' '.join(narration)
    if not 150 <= len(spoken.split()) <= 240 or len(set(narration)) != 6 or len(set(visuals)) != 6:
        raise ValueError('Durasi atau variasi adegan cerita belum layak')
    if re.search(r'(?i)https?://|pasti (?:kaya|sukses|sembuh)|dijamin|bunuh diri|investasi|azab|kisah nyata', title + ' ' + spoken):
        raise ValueError('Cerita memuat klaim atau topik yang perlu review terpisah')
    current = tokens(spoken)
    for old in previous:
        baseline = tokens(old)
        if current and len(current & baseline) / len(current | baseline) >= .58:
            raise ValueError('Naskah terlalu mirip episode sebelumnya')
    # Explicit scene blocks keep the TTS from reading production directions.
    return title, '\n\n'.join(paragraphs)


def disclose(value: str, limit: int) -> str:
    line = 'Cerita ilustrasi fiksi RYUUNDY; narasi dan visual dibuat dengan bantuan AI.'
    if line in value:
        return value[:limit]
    return value[:max(0, limit-len(line)-2)].rstrip() + '\n\n' + line


def preflight(sidecar: dict, expected_script: str | None = None) -> str | None:
    def section(key):
        value = sidecar.get(key)
        return value if isinstance(value, dict) else {}
    marker = section('cron_life_story')
    if marker.get('version') != VERSION or marker.get('series') != SERIES:
        return 'Bukti seri cerita cron belum tersedia.'
    if expected_script is not None and marker.get('script_sha256') != hashlib.sha256(expected_script.encode()).hexdigest():
        return 'Identitas naskah cerita cron tidak cocok dengan hasil render.'
    try:
        duration = float(sidecar.get('duration') or 0)
    except (TypeError, ValueError):
        duration = 0
    if (sidecar.get('aspect_ratio') != '9:16' or not math.isfinite(duration) or not 60 <= duration <= 180
            or section('final_qc').get('passed') is not True
            or section('narration_quality').get('passed') is not True
            or section('cold_open_contract').get('quality_gate_passed') is not True
            or section('dynamic_captions').get('presentation') != 'stable_phrase_no_active_word_flicker'):
        return 'Cerita cron tertahan QC durasi, narasi, visual, pembuka atau caption.'
    ledger = section('asset_license_ledger')
    if ledger.get('complete') is not True:
        return 'Bukti izin provider gambar, suara dan musik cerita cron belum lengkap.'
    return None


def mark_render(path: Path, sidecar: dict, script: str, title: str) -> Path:
    """Use a Short filename so legacy uploader and growth classifiers agree."""
    target = path.with_name('clip_01_cron_life_story.mp4')
    if path != target:
        if target.exists():
            raise ValueError('Output cerita cron sudah ada; identitas hasil dipertahankan')
        path.rename(target)
        for suffix in ('_thumb.jpg', '_thumb_b.jpg', '_thumb_c.jpg', '.srt', '.dynamic.ass'):
            source = path.with_name(path.stem + suffix)
            if source.is_file():
                shutil.copy2(source, target.with_name(target.stem + suffix))
    sidecar.update(title=title or sidecar.get('title'), output_format='portrait_short',
        cron_life_story=dict(version=VERSION, series=SERIES, fiction=True,
            owner_direction_sha256=hashlib.sha256(BRIEF.encode()).hexdigest(),
            script_sha256=hashlib.sha256(script.encode()).hexdigest(),
            source_media_reused=False, reference_used_for_structure_only=True,
            motion_recipe='original_illustrated_scenes_with_camera', subject_motion_claimed=False))
    return target


def illustrated_recipe_allowed(enabled, aspect, duration, scenes, camera_shots):
    return bool(enabled is True and aspect == '9:16' and math.isfinite(duration)
                and 60 <= duration <= 180 and len(scenes) >= 6 and camera_shots >= 6
                and len({scene.narration for scene in scenes}) >= 6)


def run(api, run_id: str, request):
    """Called inside the single campaign owner, before source discovery."""
    with api.auto_viral_lock:
        owner = api.auto_viral_runs[run_id]
    if owner.trigger != 'schedule' or not request.cron_original_story:
        raise ValueError('Seri cerita ini khusus cron')
    api.ensure_auto_viral_campaign_not_cancelled(run_id)
    path = api.JOBS_PATH.parent / 'cron_life_stories.json'
    episode = reserve(path, run_id, request.cron_production_day, api.env_int('AUTO_VIRAL_CRON_LIFE_STORY_DAILY_LIMIT', 2))
    # Never restart a render or invent a new child for an interrupted reservation.
    if episode.get('status') != 'reserved':
        raise ValueError('Episode sudah memiliki percobaan; gunakan checkpoint yang sama')
    update(path, run_id, status='generating')
    api.update_auto_viral_run(run_id, progress_stage='story_writing', message='Menyusun cerita kehidupan orisinal RYUUNDY')
    state = read(path)
    config = api.AIConfig(enabled=request.ai_enabled, base_url=request.ai_base_url,
        model=request.ai_model, api_key=request.ai_api_key, timeout=120)
    raw = api.chat_completion(config, [dict(role='system', content=BRIEF +
        ' Kembalikan JSON: title, character_bible (wajah, pakaian, warna, usia konsisten), '
        'scenes (tepat enam objek role, narration, visual). Role berurutan: ' + ', '.join(ROLES) +
        '. Total narasi 150–240 kata Indonesia, 12–48 kata per adegan. '
        'Visual minimal sepuluh kata, karakter sama melakukan aksi berbeda. '
        'Jangan memasukkan label arahan dalam narasi.'),
        dict(role='user', content='Topik: ' + episode['topic'] + '\nEpisode lama yang tidak boleh diulang: ' +
             json.dumps([r.get('title') for r in state['episodes'].values() if r.get('title')][-30:], ensure_ascii=False))], temperature=.7)
    payload = api.extract_json(raw)
    title, script = validate(payload, [r['narration'] for r in state['episodes'].values() if r.get('narration')])
    api.ensure_auto_viral_campaign_not_cancelled(run_id)
    narration = ' '.join(scene['narration'] for scene in payload['scenes'])
    update(path, run_id, status='script_ready', title=title, narration=narration,
           script_sha256=hashlib.sha256(script.encode()).hexdigest())
    proof = api.os.environ.get('AUTO_VIRAL_CRON_LIFE_STORY_PROVIDER_RIGHTS_EVIDENCE', '').strip()
    if len(proof.split()) < 3:
        raise ValueError('Bukti izin provider cerita cron belum dikonfigurasi')
    job_request = api.ClipJobRequest(clip_mode='long_animate', script_text=script, top=1,
        compilation_target_seconds=100, min_duration=60, max_duration=120, story_aspect_ratio='9:16',
        scheduled_original_story=True, scheduled_theme_key=THEME,
        scheduled_editorial_context={'series': SERIES, 'run_id': run_id, 'title': title},
        cron_daily_lane='scheduled_short', cron_production_day=request.cron_production_day,
        creator_perspective=BRIEF, provider_rights_evidence=proof, confirm_long_animate_rights=True,
        auto_upload_youtube=False, require_creative_commons=False, required_hashtags=['CeritaKehidupan', 'LangkahKecil', 'ShortsIndonesia'],
        ai_enabled=request.ai_enabled, ai_base_url=request.ai_base_url, ai_model=request.ai_model, ai_api_key=request.ai_api_key)
    job = api.queue_auto_viral_clip_job(job_request)
    update(path, run_id, status='rendering', job_id=job.id)
    item = dict(job_id=job.id, job_status='queued', status='clipping', title=title, original_story=True)
    api.update_auto_viral_run(run_id, processed=[item])
    api.run_clip_job_with_campaign_progress(job.id, run_id, 1, 1)
    with api.jobs_lock:
        finished = api.jobs.get(job.id)
    if finished is None or finished.status != 'completed' or not finished.clips:
        update(path, run_id, status='render_failed')
        raise ValueError('Produksi cerita gagal; percobaan disimpan tanpa render ulang otomatis')
    item.update(job_status='completed', clip_count=len(finished.clips), status='clipped')
    update(path, run_id, status='rendered')
    api.update_auto_viral_run(run_id, processed=[item], clipping_finished_at=api.now_iso())
    api.ensure_auto_viral_campaign_not_cancelled(run_id)
    if request.auto_upload_youtube or request.auto_upload_tiktok:
        processed = api.upload_auto_viral_processed_jobs(run_id, request, [item])
    else:
        processed = [item]
    update(path, run_id, status='processed')
    api.update_auto_viral_run(run_id, processed=processed, status='completed', finished_at=api.now_iso(),
        progress_percent=100, progress_stage='completed', message='Episode cerita cron selesai diproses; status upload mengikuti bukti platform')
