# yt-clip

CLI lokal untuk membuat clip vertical 9:16 dari YouTube video berdasarkan transcript dan scoring sederhana.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

```powershell
.\.venv\Scripts\python.exe clipper.py "https://youtu.be/RPTFTa8fgNs?si=TEDG1jDjGRgI9_Cz"
```

Opsi yang sering dipakai:

```powershell
.\.venv\Scripts\python.exe clipper.py "URL" --top 5 --min 35 --max 180
```

Test cepat tanpa transcribe full video:

```powershell
.\.venv\Scripts\python.exe clipper.py "URL" --model Systran/faster-whisper-base --analyze-seconds 180 --top 1
```

Output ada di:

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
- H.264 MP4, CRF 18
- source download mencoba HD sampai 1080p (`bestvideo+bestaudio`)
- subtitle burned-in
- transcript lokal via `Systran/faster-whisper-small`
- durasi clip dinamis, maksimal 3 menit secara default

Kalau laptop terasa berat, pakai model lebih kecil:

```powershell
.\.venv\Scripts\python.exe clipper.py "URL" --model Systran/faster-whisper-base
```
