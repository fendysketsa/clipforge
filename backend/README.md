# ClipForge Backend

FastAPI service and CLI for generating vertical 9:16 clips from YouTube videos.

Pipeline:

1. Fetch metadata and download source video with `yt-dlp`.
2. Extract mono 16 kHz audio with FFmpeg.
3. Transcribe audio locally with `faster-whisper`.
4. Score transcript windows into clip candidates.
5. Export MP4 clips, SRT subtitles, and JSON metadata.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## CLI

```powershell
.\.venv\Scripts\python.exe clipper.py "https://youtu.be/RPTFTa8fgNs?si=TEDG1jDjGRgI9_Cz"
```

## API

```powershell
.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8010
```

Main API:

```text
GET  /api/health
POST /api/jobs
GET  /api/jobs
GET  /api/jobs/{job_id}
DELETE /api/jobs
GET  /outputs/<generated-file>
```

## Telegram Bot

Run the bot after the API is available:

```powershell
$env:TELEGRAM_BOT_TOKEN="<token>"
$env:TELEGRAM_OWNER_ID="<numeric-user-id>"
$env:BACKEND_API_BASE="http://127.0.0.1:8010"
.\.venv\Scripts\python.exe telegram_bot.py
```

The Docker Compose setup starts this process automatically. Access is checked
against `TELEGRAM_OWNER_ID` for every message and button callback.

Common CLI options:

```powershell
.\.venv\Scripts\python.exe clipper.py "URL" --top 5 --min 15 --max 60
```

Test cepat tanpa transcribe full video:

```powershell
.\.venv\Scripts\python.exe clipper.py "URL" --model Systran/faster-whisper-base --analyze-seconds 180 --top 1
```

Output:

```text
outputs/
  <judul-video>/
    metadata.json
    audio.wav
    transcript.json
    candidates.json
    clips/
      clip_01_*.mp4
      clip_01_*.srt
      clip_01_*.json
```

Default output video:

- vertical `1080x1920`
- H.264 MP4, CRF 16 untuk preset Jernih dan CRF 14 untuk Maksimal
- source download mencoba sampai 2160p pada preset Jernih/Maksimal (`bestvideo+bestaudio`)
- subtitle burned-in
- caption dinamis menyorot kata penting dari ucapan asli, dengan timing berbobot jumlah kata dan margin aman agar tidak tertutup action rail/judul UI Shorts; file SRT bersih tetap dibuat untuk accessibility
- caption ringkas dengan outline/shadow tanpa gradient band agar wajah dan piksel sumber tetap bersih
- hook visual/audio, reaction kontekstual, dan pattern interrupt
- klip berkonteks Islami otomatis mendapat backsong motivasional instrumental "Cahaya Hikmah" yang disintesis lokal, berlisensi CC0, dan di-duck agar dialog tetap jelas
- mode visual `auto_fyp` aktif secara default dengan pipeline clean-detail: koreksi warna ringan, adaptive clarity pada tahap akhir, reframe hanya di beat penting, tanpa blurred frame/gradient/kartu besar di atas wajah
- mode `animated_3d` tetap tersedia bila memang menginginkan denoise temporal, warna film animasi, depth contrast, dan outline halus
- background asli dipertahankan secara default; pembersihan backdrop dan panel speaker-split tetap tersedia sebagai pilihan khusus
- intisari ucapan asli disimpan di metadata; mode clean-detail tidak menutup wajah dengan kartu intisari besar
- kandidat wajib punya point utama, batas kalimat tuntas, dan payoff dekat ending
- treatment loop hanya aktif saat payoff benar-benar terhubung ke hook
- variasi motion dipilih deterministik dari isi cerita (bukan nomor urut export) agar rangkaian upload tidak terlihat seperti template massal yang identik
- audit monetisasi v2 hanya meloloskan upload Private bila alur hook–pesan inti–payoff utuh dan edit kamera/emphasis/audio benar-benar mengikuti transcript; hasil audit bukan jaminan diterima YPP
- metadata/chapter container sumber tidak diwariskan ke MP4 hasil; bukti lisensi tetap disimpan lokal
- transcript lokal accuracy-first via `Systran/faster-whisper-medium`, beam search,
  VAD, word timestamps, dan cache yang terikat model/bahasa
- nama orang/brand/istilah khusus dapat diprioritaskan melalui
  `CLIPFORGE_TRANSCRIPTION_HOTWORDS` (pisahkan dengan koma)
- durasi clip pendek dinamis, maksimal 60 detik
- mode `short` tidak merender kompilasi tambahan

Untuk membuat satu clip resume sinematik 5–10 menit (bukan Short), pilih target 300–600 detik:

```powershell
.\.venv\Scripts\python.exe clipper.py "URL" --clip-mode highlight_5m --compilation-target 600 --min 30 --max 90 --visual-mode cinematic --ai-enabled
```

If CPU feels too slow, use a smaller model:

```powershell
.\.venv\Scripts\python.exe clipper.py "URL" --model Systran/faster-whisper-base
```

## Notes

- This service is local-first. Add auth, rate limiting, and quotas before public deployment.
- Do not commit `outputs/`, `.env`, or `jobs.json`.
- Process only videos you have rights or permission to use.
