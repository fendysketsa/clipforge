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
- Queue completed clips for YouTube Studio upload through Playwright.
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
TELEGRAM_AI_BASE_URL=http://127.0.0.1:11434/v1
TELEGRAM_AI_MODEL=deepseek-v4-flash:cloud
```

Bot state is persisted in `backend/data/telegram_bot_state.json`, so completed
jobs can continue being monitored after a bot container restart. Telegram's
hosted Bot API accepts uploads up to 50 MB; oversized clips remain available in
the web dashboard or through `TELEGRAM_PUBLIC_BASE_URL` when configured.

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
YOUTUBE_CDP_URL=http://127.0.0.1:9222
YOUTUBE_UPLOAD_USE_CDP=true
YOUTUBE_UPLOAD_FORCE_CDP=true
YOUTUBE_CDP_MAX_UPLOAD_MB=45
YOUTUBE_TARGET_CHANNEL=ryuundy8812
YOUTUBE_TARGET_EMAIL=fendysketsa@gmail.com
YOUTUBE_TARGET_CHANNEL_ID=UCAOZF9Qzj6DYoXKtLnP4UUQ
YOUTUBE_STUDIO_URL=https://studio.youtube.com/channel/UCAOZF9Qzj6DYoXKtLnP4UUQ
```

When running with Docker, the browser profile must be mounted into the backend
container first. The safer recreate flow is:

```bash
./scripts/recreate-compose-up.sh
```

Use `./scripts/recreate-compose-up.sh --down-first` when you also want to run
`docker compose down` before recreating services. Use
`./scripts/recreate-compose-up.sh --reset-profile` only when the Chrome CDP
profile is broken and YouTube keeps asking for login; it deletes the saved CDP
profile and opens a fresh one. The wrapper starts
`scripts/open-youtube-login-chrome.sh` in the background, keeps
`http://127.0.0.1:9222` open with
`google-chrome --remote-debugging-address=127.0.0.1 --remote-debugging-port=9222 --user-data-dir=$HOME/.config/clipforge/youtube-chrome-profile https://studio.youtube.com`,
and sends Chrome GPU/Skia logs to `/tmp/clipforge-youtube-chrome.log`. The Chrome
profile is stored under `$HOME/.config/clipforge/youtube-chrome-profile`, so YouTube login
survives container recreate. By default, the wrapper syncs that profile from
`YOUTUBE_CHROMIUM_HOST_USER_DATA_DIR` in `.env` (`/home/fcn88/.config/google-chrome`)
so it can reuse the desktop Chrome session that is already logged in. To reuse
another existing Chrome session/profile, run the wrapper with
`YOUTUBE_LOGIN_SOURCE_PROFILE_DIR=/path/to/profile ./scripts/recreate-compose-up.sh`.
Keep that Chrome window open while uploads run. CDP upload is enabled by default;
clips above the CDP transfer limit are staged as compressed upload copies under
`backend/data/youtube_cdp_uploads` without modifying the original dashboard clips.
If you want the recreate command to keep watching Chrome instead of returning to
the prompt, use `./scripts/recreate-compose-up.sh --watch-chrome`.
For laptop startup/supervisor, use the example config at
`deploy/supervisor/clipforge-youtube.conf`; it runs
`./scripts/recreate-compose-up.sh --watch-chrome` and deliberately does not reset
the profile. The legacy `./scripts/reset-youtube-cdp-profile.sh` command now
delegates to `./scripts/recreate-compose-up.sh --reset-profile --watch-chrome`
and starts the Chrome CDP window minimized by default
(`YOUTUBE_CHROME_START_MINIMIZED=true`).
Uploads use Chrome CDP by default because YouTube Studio can reject the bundled
Playwright browser as old or unsupported. Keep `YOUTUBE_UPLOAD_FORCE_CDP=true`
when the backend must not fall back to Playwright storage state after a CDP
refresh.
The dashboard and Telegram **Run CDP** button calls the backend endpoint
`POST /api/youtube/cdp/refresh`. By default the backend looks for
`scripts/open-youtube-login-chrome.sh`; in Docker, `docker-compose.yml` mounts
that folder at `/app/scripts`. If Chrome is controlled by the host desktop
session instead of the backend container, keep the supervisor above running on
the host or start Chrome CDP from outside, then use **Sync CDP**. For custom
deployments, set `YOUTUBE_CDP_REFRESH_COMMAND` to the launcher command that is
valid from the backend process. The Docker backend also sets
`YOUTUBE_CHROME_HEADLESS=true`, `YOUTUBE_LOGIN_SOURCE_PROFILE_DIR=/app/data/chromium-youtube`,
and `YOUTUBE_LOGIN_PROFILE_DIR=/app/data/youtube-chrome-profile` so the Run CDP
button can start a Playwright Chromium CDP process without depending on an
unlocked desktop display. **Sync CDP** calls `POST /api/youtube/cdp/sync`; it
does not start or restart Chrome, and only hydrates/validates the session after
remote debugging is already active. When a queued upload starts and CDP is not
responding, the backend runs the refresh command automatically before invoking
the YouTube uploader, so Telegram retry can recover while the laptop is locked
or AFK. The Telegram Run CDP button waits for CDP readiness before sending the
success notification; increase `TELEGRAM_YOUTUBE_CDP_REFRESH_TIMEOUT_SECONDS` if
the launcher needs more time to open Chrome.
Direct upload from the mounted full profile is disabled unless
`YOUTUBE_ALLOW_CHROMIUM_PROFILE_UPLOAD=true` because full desktop profiles often
fail in headless Playwright. Uploads are cancelled before file selection if the
session does not appear to belong to `ryuundy8812` or `fendysketsa@gmail.com`.

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
YOUTUBE_ALLOW_CHROMIUM_PROFILE_UPLOAD=false
YOUTUBE_CDP_URL=http://127.0.0.1:9222
YOUTUBE_UPLOAD_USE_CDP=true
YOUTUBE_UPLOAD_FORCE_CDP=true
YOUTUBE_CDP_MAX_UPLOAD_MB=45
YOUTUBE_DEFAULT_VISIBILITY=private
YOUTUBE_MADE_FOR_KIDS=false
YOUTUBE_DEFAULT_TAGS=shorts,clipforge
YOUTUBE_DEFAULT_PLAYLIST=Islam
YOUTUBE_TARGET_CHANNEL=ryuundy8812
YOUTUBE_TARGET_EMAIL=fendysketsa@gmail.com
YOUTUBE_TARGET_CHANNEL_ID=UCAOZF9Qzj6DYoXKtLnP4UUQ
YOUTUBE_STUDIO_URL=https://studio.youtube.com/channel/UCAOZF9Qzj6DYoXKtLnP4UUQ
YOUTUBE_AUTO_UPLOAD_COUNT=3
YOUTUBE_REQUIRE_COPYRIGHT_CHECKS=true
YOUTUBE_CHECKS_TIMEOUT_SECONDS=600
YOUTUBE_MANUAL_SUBTITLE_TEXT=RYUUNDY
YOUTUBE_SUBTITLE_TYPE_DELAY_MS=120
YOUTUBE_SUBTITLE_EDITOR_READY_DELAY_MS=2500
YOUTUBE_SUBTITLE_SEGMENT_READY_DELAY_MS=30000
YOUTUBE_SUBTITLE_AFTER_TYPE_DELAY_MS=2000
YOUTUBE_UPLOAD_TIMEOUT_SECONDS=900
YOUTUBE_STUDIO_NAV_TIMEOUT_MS=60000
YOUTUBE_DIRECT_UPLOAD_NAV_TIMEOUT_MS=60000
YOUTUBE_DIRECT_UPLOAD_INPUT_TIMEOUT_MS=5000
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
