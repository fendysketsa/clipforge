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
- Crop center or shift crop toward detected faces/people.
- Manage jobs and generated clips from a Next.js UI.
- Start jobs and receive complete results from a private Telegram bot.
- Run locally with Python/Node or with Docker Compose.

## Requirements

- Python 3.12+
- Node.js 22+
- npm
- Network access for YouTube downloads and model downloads
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
```

Bot state is persisted in `backend/data/telegram_bot_state.json`, so completed
jobs can continue being monitored after a bot container restart. Telegram's
hosted Bot API accepts uploads up to 50 MB; oversized clips remain available in
the web dashboard or through `TELEGRAM_PUBLIC_BASE_URL` when configured.

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

Outputs are written under `backend/outputs/`.

## API

```text
GET    /api/health
POST   /api/jobs
GET    /api/jobs
GET    /api/jobs/{job_id}
DELETE /api/jobs
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
