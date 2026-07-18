# ClipForge

Local-first tool for turning long YouTube videos into ready-to-post vertical clips with transcription, burned-in subtitles, and smart crop options.

## Overview

![ClipForge overview](image.png)

## Features

- Download a single YouTube video with `yt-dlp`.
- Transcribe locally with `faster-whisper`.
- Score transcript windows for clip candidates.
- Export vertical 9:16 MP4 clips with SRT files.
- Burn subtitles into clips by default.
- Apply context-aware cinematic editing by default: theme color grading, animated hooks, varied camera motion, transcript-synced emphasis pulses, transitions, vignette, and progress bar.
- Add sparse conversation-aware reaction stickers for laughter, surprise, questions, prayer/gratitude, warnings, and emotional moments.
- Crop the source footer/running-text strip from vertical exports by default before adding fresh captions and graphics.
- Enhance voice clarity and generate safe, niche-aware social captions even when the AI service is unavailable.
- Keep captions compact with a soft gradient-blur background by default.
- Generate short clips and one chronological, FYP-focused compilation of about five minutes in the same job.
- Telegram's primary CTA always requests both outputs in one job and caps the compilation at 300 seconds.
- Search 70+ Creative Commons themes, including Islamic insight, mystery, myth/fact, history, and relevant horror; prioritize the last 30 days and expand to 180 days when needed.
- Permanently skip YouTube source URLs that have already completed clipping.
- Crop center or shift crop toward detected faces/people.
- Manage jobs and generated clips from a Next.js UI.
- Start jobs and receive complete results from a private Telegram bot.
- Queue completed clips for YouTube Studio upload through Playwright.
- Run locally with Python/Node or with Docker Compose.

## Requirements

- Python 3.12+
- Node.js 22+
- npm
- Network access for YouTube downloads and model downloads
- A full FFmpeg build with `drawtext`, `subtitles`/libass, and libx264 (included in the Docker image)
- Enough CPU, disk, and time for transcription and video encoding

Docker users only need Docker and Docker Compose.

## Quick Start With Docker

Copy the Docker env example:

```powershell
Copy-Item .env.docker.example .env
```

For web-only local usage, the first three values are enough. Fill the Telegram
values to enable the private bot:

```env
FRONTEND_PORT=3000
BACKEND_PORT=8010
NEXT_PUBLIC_API_BASE=http://localhost:8010
TELEGRAM_BOT_TOKEN=123456789:replace-with-botfather-token
TELEGRAM_OWNER_ID=123456789
```

Build and run:

```powershell
docker compose --env-file .env up -d --build
```

Open:

```text
frontend: http://localhost:3000
backend:  http://localhost:8010
```

The Telegram bot starts with the same Compose command. Open the bot, send
`/start`, then send a YouTube URL. Only the numeric ID configured in
`TELEGRAM_OWNER_ID` can use it.

Persistent local data:

```text
backend/outputs -> /app/outputs
backend/data -> /app/data
```

## Telegram Bot

The private bot provides clickable menus for clipping settings, live status,
cancellation, history, and resending completed jobs. A YouTube link is confirmed
before processing. When a job completes, the bot sends every clip followed by
its thumbnail, full title, social caption, and thumbnail prompt.

Required configuration:

```env
TELEGRAM_BOT_TOKEN=<token from BotFather>
TELEGRAM_OWNER_ID=<your numeric Telegram user ID>
```

Optional configuration:

```env
# Public backend URL used as a download fallback for files over Telegram's limit.
TELEGRAM_PUBLIC_BASE_URL=https://api.example.com
TELEGRAM_MAX_UPLOAD_MB=49
TELEGRAM_AI_BASE_URL=http://127.0.0.1:11434/v1
TELEGRAM_AI_MODEL=llama3.2-id:latest
OPENROUTER_API_KEY=
OPENROUTER_MODEL=openrouter/free
TELEGRAM_BATTERY_ALERT_ENABLED=true
TELEGRAM_BATTERY_ALERT_LEVELS=20,10,5
TELEGRAM_BATTERY_CHECK_INTERVAL_SECONDS=60
```

Bot state is persisted in `backend/data/telegram_bot_state.json`, so completed
jobs can continue being monitored after a bot container restart. Telegram's
hosted Bot API accepts uploads up to 50 MB; oversized clips remain available in
the web dashboard or through `TELEGRAM_PUBLIC_BASE_URL` when configured.

Gunakan `/battery` atau tombol **Baterai Device** untuk melihat sisa daya.
Pada Linux, bot juga mengirim satu alert saat baterai yang tidak sedang diisi
melewati ambang 20%, 10%, dan 5%. Docker Compose memasang `/sys` host secara
read-only agar container dapat membaca status baterai; ambang dan interval cek
dapat diubah melalui variabel di atas.

## YouTube Studio Upload

ClipForge can upload completed clips to YouTube Studio with Playwright. The
uploader uses a saved browser session, so you log in manually once and the
dashboard or Telegram bot can queue uploads afterwards.

Docker login:

```powershell
docker compose exec backend python youtube_uploader.py login
```

Alternatively, reuse a Chromium/Chrome profile that is already logged in to the
target YouTube channel by setting:

```env
YOUTUBE_CHROMIUM_USER_DATA_DIR=/path/inside/container/to/chromium-user-data
YOUTUBE_CHROMIUM_PROFILE_DIRECTORY=Default
YOUTUBE_ALLOW_CHROMIUM_PROFILE_UPLOAD=true
YOUTUBE_CDP_URL=http://127.0.0.1:9222
YOUTUBE_UPLOAD_USE_CDP=false
YOUTUBE_UPLOAD_FORCE_CDP=false
YOUTUBE_UPLOAD_STORAGE_STATE_FIRST=true
YOUTUBE_CDP_MAX_UPLOAD_MB=45
YOUTUBE_TARGET_CHANNEL=ryuundyofficial
YOUTUBE_TARGET_EMAIL=fendysketsa@gmail.com
YOUTUBE_TARGET_CHANNEL_ID=UCAOZF9Qzj6DYoXKtLnP4UUQ
YOUTUBE_STUDIO_URL=https://studio.youtube.com/channel/UCAOZF9Qzj6DYoXKtLnP4UUQ
```

The recommended flow is one-time login, then normal Playwright uploads:

1. Mount or point `YOUTUBE_CHROMIUM_USER_DATA_DIR` to a Chromium/Chrome profile
   that is already logged in, or run the login command once.
2. Click **Login Sekali** in the dashboard/Telegram. The backend validates the
   account/channel and saves `YOUTUBE_PLAYWRIGHT_STATE`.
3. Uploads run with Playwright storage-state first, without supervisor/CDP.

CDP is optional now. Use **Ambil Cookies CDP** only if you intentionally want to
copy cookies from an already-open Chrome remote debugging session. The legacy
`./scripts/recreate-compose-up.sh` and `./scripts/reset-youtube-cdp-profile.sh`
helpers remain available for CDP recovery, but normal uploads no longer depend
on them. Uploads are cancelled before file selection if the session does not
appear to belong to `ryuundyofficial` or `fendysketsa@gmail.com`.

Local login:

```powershell
cd backend
.\.venv\Scripts\python.exe youtube_uploader.py login
```

Enable **Auto Upload YouTube** before starting a clipping job to automatically
queue the highest-scored clips when processing finishes. After a job completes,
you can also use **Upload 3 terbaik** or the per-clip YouTube button in the
dashboard. In Telegram, use **Upload Clip Ini ke YouTube** or **Upload 3
Terbaik ke YouTube**. Batch uploads automatically pick the highest-scored clips,
select the configured playlist, and verify the saved session appears to be the
configured target channel before uploading. Uploads are processed one at a time
and persisted in `backend/data/youtube_uploads.json`.

For safer reuse, URL jobs require Creative Commons metadata by default before
download. During upload, Playwright waits for YouTube Studio Checks and cancels
before publish if copyright or restriction issues are detected. This reduces
risk but cannot guarantee a video will never receive a future claim.

Optional YouTube upload configuration:

```env
YOUTUBE_HEADLESS=true
YOUTUBE_CHROMIUM_USER_DATA_DIR=
YOUTUBE_CHROMIUM_PROFILE_DIRECTORY=Default
YOUTUBE_ALLOW_CHROMIUM_PROFILE_UPLOAD=true
YOUTUBE_CDP_URL=http://127.0.0.1:9222
YOUTUBE_UPLOAD_USE_CDP=false
YOUTUBE_UPLOAD_FORCE_CDP=false
YOUTUBE_UPLOAD_STORAGE_STATE_FIRST=true
YOUTUBE_CDP_MAX_UPLOAD_MB=45
YOUTUBE_DEFAULT_VISIBILITY=private
YOUTUBE_MADE_FOR_KIDS=false
YOUTUBE_DEFAULT_TAGS=shorts,clipforge
YOUTUBE_DEFAULT_PLAYLIST=Islam
YOUTUBE_TARGET_CHANNEL=ryuundyofficial
YOUTUBE_TARGET_EMAIL=fendysketsa@gmail.com
YOUTUBE_TARGET_CHANNEL_ID=UCAOZF9Qzj6DYoXKtLnP4UUQ
YOUTUBE_STUDIO_URL=https://studio.youtube.com/channel/UCAOZF9Qzj6DYoXKtLnP4UUQ
YOUTUBE_AUTO_UPLOAD_COUNT=3
YOUTUBE_REQUIRE_COPYRIGHT_CHECKS=true
YOUTUBE_CONTINUE_WHEN_CHECKS_STUCK=false
YOUTUBE_CHECKS_TIMEOUT_SECONDS=3600
YOUTUBE_CHECKS_LONG_RUNNING_EXTENSION_SECONDS=1800
YOUTUBE_CHECKS_PROGRESS_LOG_INTERVAL_SECONDS=60
YOUTUBE_PRE_PUBLISH_REVIEW_TIMEOUT_SECONDS=900
YOUTUBE_RELOAD_AFTER_PUBLISH=true
YOUTUBE_RELOAD_AFTER_PUBLISH_DELAY_SECONDS=10
YOUTUBE_MANUAL_SUBTITLE_TEXT=FCN
YOUTUBE_ADD_MANUAL_SUBTITLE=true
YOUTUBE_SUBTITLE_TYPE_DELAY_MS=120
YOUTUBE_SUBTITLE_EDITOR_READY_DELAY_MS=2500
YOUTUBE_SUBTITLE_SEGMENT_READY_DELAY_MS=30000
YOUTUBE_SUBTITLE_AFTER_TYPE_DELAY_MS=2000
YOUTUBE_UPLOAD_TIMEOUT_SECONDS=5400
YOUTUBE_STUDIO_NAV_TIMEOUT_MS=30000
YOUTUBE_DIRECT_UPLOAD_NAV_TIMEOUT_MS=18000
YOUTUBE_DIRECT_UPLOAD_INPUT_TIMEOUT_MS=15000
YOUTUBE_ALLOW_DIRECT_UPLOAD_PAGE_FALLBACK=true
YOUTUBE_DRY_RUN=false
```

Use `YOUTUBE_DRY_RUN=true` to test the Playwright flow without pressing the
final publish/save button.

## Local Development

Start backend:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8010
```

Start frontend in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:3000`.

## CLI Usage

The backend can also run without the UI:

```powershell
cd backend
.\.venv\Scripts\python.exe clipper.py "https://www.youtube.com/watch?v=..." --top 5 --min 35 --max 180
```

Quick test on the first 180 seconds:

```powershell
.\.venv\Scripts\python.exe clipper.py "https://www.youtube.com/watch?v=..." --model Systran/faster-whisper-base --analyze-seconds 180 --top 1
```

Create one non-Short highlight compilation targeting five minutes:

```powershell
.\.venv\Scripts\python.exe clipper.py "URL" --clip-mode highlight_5m --compilation-target 300 --min 30 --max 75 --ai-enabled
```

Outputs are written under `backend/outputs/`.

## API

```text
GET    /api/health
POST   /api/jobs
GET    /api/jobs
GET    /api/jobs/{job_id}
DELETE /api/jobs
GET    /api/youtube/config
GET    /api/youtube/uploads
POST   /api/jobs/{job_id}/youtube-uploads
POST   /api/jobs/{job_id}/youtube-uploads/batch
GET    /outputs/<generated-file>
```

## Configuration

For Docker/server deployments, `NEXT_PUBLIC_API_BASE` must be the browser-accessible backend URL:

```env
NEXT_PUBLIC_API_BASE=https://api.example.com
```

The frontend also uses `BACKEND_API_BASE` internally for proxying API requests in Docker:

```env
BACKEND_API_BASE=http://backend:8010
```

## Safety And Legal Notes

ClipForge is intended for local workflows and content you are allowed to process. Make sure you have rights or permission to download, transform, and republish source videos. Follow YouTube terms and applicable copyright law.

Do not expose the backend publicly without authentication, rate limits, request validation, quotas, and cleanup. The backend accepts URLs and runs expensive jobs.

## Project Structure

```text
backend/
  api.py                 FastAPI job API
  clipper.py             download/transcribe/score/export pipeline
  telegram_bot.py        owner-only Telegram bot and result delivery
  models/                optional crop detection model
  outputs/               generated local files, ignored by git
frontend/
  app/                   Next.js app router UI
  lib/apiClient.ts       API client helpers
  types/clip.type.ts     shared frontend types
docker-compose.yml       local app and Telegram bot stack
```

## License

MIT. See `LICENSE`.

Third-party notices live in `NOTICE`.

## Author

Created by [mallexibra](https://mallexibra.my.id/).
