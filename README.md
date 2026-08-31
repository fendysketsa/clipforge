# Fendy Clipper

Local-first tool for turning long YouTube videos into ready-to-post vertical clips with transcription, burned-in subtitles, and smart crop options.

## Overview

![Fendy Clipper overview](image.png)

## Features

- Download a single YouTube video with `yt-dlp`.
- Transcribe locally with `faster-whisper`.
- Score transcript windows for clip candidates.
- End candidates on complete key-point/payoff boundaries and suppress near-duplicate ideas.
- Detect focused 20–32 second micro-theses that open on a relatable dilemma, add nuance, state a safety or ethical boundary, and close without stigmatizing the viewer. These use a restrained-authority edit with at most two meaningful reframes, no reaction stickers or cinematic smoke, and dialogue-first audio.
- Detect 18–32 second social anecdotes with first-person friction, chronological movement, a concrete comparison, and a self-directed punchline. These use a 1.9-second event card, faster face-safe reframes, authentic source reactions, and no synthetic ridicule, stickers, smoke, SFX, or background music.
- Export vertical 9:16 MP4 clips with SRT files.
- Burn subtitles into clips by default.
- Apply clean context-aware editing by default: a truthful opening hook, sparse transcript-synced camera cuts, two brief edge cues, and a thin progress line.
- Reframe a single speaker like a restrained virtual multi-camera edit, cutting between face-safe medium and close-up angles on meaningful speech beats.
- Record a monetization-readiness audit beside each render, require substantive editorial signals before YouTube upload, preserve verified CC BY attribution, and disclose realistic backdrop replacement.
- Build an **Original Rebuild** from a rights-cleared source: transcribe it as untrusted research input, require an AI-authored Indonesian editorial angle, reject scripts that copy more than the configured contiguous-word limit, delete downloaded working media/audio/transcript artifacts before Scene Cinema rendering, never pass a caller-owned local source to the renderer, and record hashes plus a no-source-media audit. This is an originality and provenance guard—not a Content ID bypass or a guarantee of YPP approval.
- Original Rebuild now requires a human-authored perspective plus source/provider license references. Every generated render records an asset-license ledger for research source, script, visuals, voice, and music. Before upload, a dynamic channel audit compares the narrative with up to 20 recent completed uploads and blocks near-duplicates at `YOUTUBE_GENERATED_CONTENT_MAX_SIMILARITY` (default `0.58`). Automated uploads are always forced Private-first; AI disclosure, Content ID Checks, factual review, attribution, and channel-wide YPP review still apply.
- Use one **Auto FYP Viral** visual system for Shorts and long-form: cinematic clean detail is the base, while 3D depth, archival-TV treatment, reframe, and speaker split are selected from the story instead of exposed as separate presets.
- Derive visual variation from the clip hook/POV/transcript so batches stay coherent without becoming near-identical mass-produced templates.
- Keep the original background by default; optional background cleaning remains available for text-heavy sources.
- Add at most one strong conversation-aware reaction sticker in Clean Detail mode, only for laughter, surprise, prayer, or warnings.
- Mix restrained transcript-synced sound effects under normalized dialogue.
- Automatically give Islamic clips a quiet, dialogue-ducked motivational music bed generated locally from the CC0 "Cahaya Hikmah" recipe, with no third-party recording or sample.
- Apply loop treatment only when the payoff semantically reconnects to the opening hook.
- Preserve the source footer and face pixels by default; footer cleanup is opt-in for sources where modifying the lower frame is acceptable.
- Enhance voice clarity and generate safe, niche-aware social captions even when the AI service is unavailable.
- Keep captions compact and readable with outline/shadow only, without a gradient band over the source image.
- Turn the fast-scanning reference-card pattern into a content-adaptive opening: the truthful hook stays prominent while the badge, accent color, and layout variation follow each story instead of repeating one fixed template.
- Detect compact question–answer clips with a late self-directed punchline; show a short transcript-quoted payoff teaser only after the opening context card, clear it before the spoken payoff, preserve authentic reactions, and suppress synthetic stickers/SFX or an intrusive end CTA.
- Turn long comparison/explainer Shorts into an adaptive three-beat evidence stage: keep the source video dominant, replace copied logos/patterns/photos with a content-derived context card and progress rail, remove duplicated cold-open excerpts, require a complete fair conclusion, and hold sensitive religious comparisons for manual claim/context review.
- Record a transparent growth experiment: Shorts target 20K views and 20 subscribers per upload, while long-form keeps a 5K/20-subscriber baseline. Stability means at least three of the latest five comparable uploads reach both targets, measured against the rolling median of the last ten uploads in the same format and series. Targets are experiments, not guaranteed distribution.
- Store post-publish performance snapshots on each YouTube upload and diagnose reach, retention, and subscriber conversion against comparable uploads in the same series. YouTube Analytics OAuth provides engaged views, watch metrics, shares, and subscribers; the YouTube Data API remains a public-statistics fallback.
- Auto-repair a broader shortlist before final selection, enforce a minimum FYP score of 78 for vertical exports, and block low-score legacy Shorts from YouTube upload instead of labeling them ready to post.
- Audit first-30-second editorial readiness across five beat windows (0–3, 3–8, 8–15, 15–22, and 22–30 seconds), including context-dependent openings, speech coverage, dead air, and fresh information. Timing-audited Shorts below 58 are held by the selection/upload gate; this score is a diagnostic, not a promise of actual audience retention.
- Place one value-led Subscribe invitation after the payoff: Shorts pair it with the contextual discussion prompt in a shorter 1.85-second window, suppress it for clips up to 40 seconds or earned loops, and long-form shows it once in the final chapter. The reason to subscribe follows the topic and never offers rewards or fake urgency.
- Produce adaptive 25–180 second Shorts: use the shortest complete promise–payoff cut, reserve longer windows for multi-beat stories with sustained information, and never add filler merely to reach three minutes.
- Build a separate 5–10 minute **Long Story** with a sentence-complete 10–22 second teaser, then restore source chronology across context, development, explanation, and payoff. The teaser is removed from its original position, and the renderer never adds filler merely to hit the selected duration.
- Produce **Long Animate** directly from an original script: Scene Cinema uses local Ollama for the storyboard and a local Apache-2.0 Z-Image-Turbo Q3 service for prompt-faithful scene images, then adds content-derived camera motion, Indonesian narration, scene-timed subtitles, procedural original music, thumbnail, and YouTube chapters before joining everything into one 16:9 video.
- Telegram's primary CTA requests short clips only for a faster turnaround.
- Search 70+ Creative Commons themes, including Islamic insight, mystery, myth/fact, history, and relevant horror. The current-viral niche defaults to the last seven days and rewards recent 20–120 minute conversations that can support genuinely different viewer questions; other themes keep their broader discovery windows.
- Package same-source Shorts as distinct editorial angles with concrete, truthful tension/outcome titles, while rejecting near-duplicate talking points. Freshness, face crops, captions, and titles are editorial signals only—not proof of reuse rights or monetization eligibility.
- Permanently skip YouTube source URLs that have already completed clipping.
- Crop center or shift crop toward detected faces/people.
- When a three-panel 9:16 layout is selected, keep the current clip in the large panel and feed both smaller panels from two other, timeline-spread clip candidates. Never build the three panels by cropping the same simultaneous source frame; skip the layout when two distinct companion clips are unavailable.
- Use an accuracy-first Indonesian transcription preset (`faster-whisper-medium`,
  beam search, VAD, and word timestamps) and invalidate stale lower-quality transcript caches.
- Manage jobs and generated clips from a Next.js UI.
- Generate a complete, readable description for every Short and long-form output: a content-specific summary, viewer benefits, discussion prompt, natural Like/Share/Subscribe support block, channel handle, editorial-context note, and deduplicated topical hashtags. Long-form keeps richer benefits and valid YouTube chapters while excluding `#Shorts`.
- Start jobs and receive complete results from a private Telegram bot.
- Queue completed clips for YouTube Studio upload through Playwright.
- Run locally with Python/Node or with Docker Compose.

## Requirements

- Python 3.12+
- Node.js 22+
- npm
- Network access for YouTube downloads and model downloads
- Docker builds include Deno and `yt-dlp-ejs` so current YouTube JavaScript challenges can be solved before media download; the downloader retries with the web-embedded client when a default signed URL returns 403.
- A full FFmpeg build with `drawtext`, `subtitles`/libass, and libx264 (included in the Docker image)
- Enough CPU, disk, and time for transcription and video encoding

Docker users only need Docker and Docker Compose.

The public Whisper model works without an account. Fendy Clipper stores the model
cache under `backend/data/huggingface`, so container rebuilds do not download it
again. For higher Hugging Face download limits, create a read-only access token
and set `HF_TOKEN=hf_...` in the untracked root `.env`; the backend forwards it
automatically and never writes the value to job logs.

Vertical Shorts end with a content-theme-derived question over the live payoff,
without a repeated Subscribe template. Optional Indonesian voice-over is disabled
by default; when explicitly enabled it speaks that contextual question. Configure it in `.env` with
`CTA_VOICEOVER_ENABLED`, `CTA_VOICEOVER_TEXT`, `CTA_VOICEOVER_VOICE`, and
`CTA_VOICEOVER_RATE`.

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

Fendy Clipper can upload completed clips to YouTube Studio with Playwright. The
uploader uses a saved browser session, so you log in manually once and the
dashboard or Telegram bot can queue uploads afterwards.

Docker login:

```powershell
docker compose exec backend python youtube_uploader.py login
```

On Linux, prepare the desktop bridge before starting/recreating Docker so the
headed login window can use the active `DISPLAY` and Xauthority:

```bash
./scripts/prepare-youtube-gui-runtime.sh
```

`recreate-compose-up.sh` and `run-youtube-cdp-cli.sh` run this preparation
automatically. Run it again after logging out of or restarting the desktop
session, because the Xauthority cookie can change.

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
YOUTUBE_CDP_MAX_UPLOAD_MB=256
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
you can also use **Upload 2 terbaik** or the per-clip YouTube button in the
dashboard. In Telegram, use **Upload Clip Ini ke YouTube** or **Upload 2
Terbaik ke YouTube**. Batch uploads automatically pick the highest-scored clips,
select the configured playlist, and verify the saved session appears to be the
configured target channel before uploading. Uploads are processed one at a time
and persisted in `backend/data/youtube_uploads.json`.

The dashboard's **Perbarui** action records a post-publish performance snapshot.
Set `YOUTUBE_DATA_API_KEY` for public views/likes/comments. For the complete
20K/20 feedback loop, create an OAuth grant with the read-only YouTube Analytics
scope and configure:

```env
YOUTUBE_ANALYTICS_CLIENT_ID=
YOUTUBE_ANALYTICS_CLIENT_SECRET=
YOUTUBE_ANALYTICS_REFRESH_TOKEN=
```

With OAuth configured, snapshots also include engaged views, average view
duration/percentage, shares, and video-attributed subscriber gains. Secrets are
read only by the backend and are never returned by the API.

For safer reuse, URL jobs require explicit Creative Commons metadata before
download and an explicit confirmation that the user owns or has provable
commercial permission for the complete audio and visual work. A CC label is
license metadata, not proof that the uploader owns every element in a recording.
Viral search also rejects live/upcoming, age-restricted, non-public, fan/support/
reupload/archive accounts, and sources that look like TV, film, music, broadcaster,
or known Content ID material. CC BY attribution is appended to the YouTube
description, while rendered MP4 files do not inherit source container metadata or
chapters. New renders also carry a monetization-readiness audit; upload is blocked
when source-rights confirmation or minimum substantive-edit evidence is absent.
This is a preflight, not a promise of YPP approval, because YouTube also reviews
the channel as a whole.

During upload, Playwright waits for YouTube Studio Checks and applies a zero-active-
claim policy: every detected Content ID/copyright claim cancels the workflow before
the final Save/Publish action, including claims currently described as having no
impact and claims on Shorts under one minute. A claimed upload is no longer saved
as a Private fallback. Private auto uploads do not hold the whole queue while
Studio still reports Checks as pending: the workflow checks for an explicit claim,
continues as Private, then checks once more immediately before Save. Public and
Unlisted uploads still require completed Checks. Because Content ID can apply a
later claim, review Private uploads before publishing. When Fendy Clipper replaces a realistic backdrop, it also
selects YouTube's altered-content disclosure before continuing. Review the
Restrictions and monetization columns before publishing.
This reduces risk but cannot guarantee a video will never receive a future claim.

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
YOUTUBE_CDP_MAX_UPLOAD_MB=256
YOUTUBE_DEFAULT_VISIBILITY=private
YOUTUBE_ALLOW_PUBLIC_AUTO_UPLOAD=false
YOUTUBE_MADE_FOR_KIDS=false
YOUTUBE_DEFAULT_TAGS=viralindonesia,trendingindonesia,kontenpilihan
YOUTUBE_DEFAULT_PLAYLIST=Islam
YOUTUBE_PLAYLIST_SELECT_ATTEMPTS=3
YOUTUBE_POLICY_REVIEW_DATE=2026-08-30
YOUTUBE_GENERATED_CONTENT_MAX_SIMILARITY=0.58
YOUTUBE_POLICY_REVIEW_INTERVAL_DAYS=180
YOUTUBE_TARGET_CHANNEL=ryuundyofficial
YOUTUBE_TARGET_EMAIL=fendysketsa@gmail.com
YOUTUBE_TARGET_CHANNEL_ID=UCAOZF9Qzj6DYoXKtLnP4UUQ
YOUTUBE_STUDIO_URL=https://studio.youtube.com/channel/UCAOZF9Qzj6DYoXKtLnP4UUQ
YOUTUBE_AUTO_UPLOAD_COUNT=2
YOUTUBE_PUBLIC_DAILY_LIMIT=2
YOUTUBE_PUBLIC_MIN_GAP_HOURS=6
YOUTUBE_PUBLISH_TIMEZONE=Asia/Jakarta
YOUTUBE_REQUIRE_COPYRIGHT_CHECKS=true
YOUTUBE_PRIVATE_FAST_CHECKS=true
YOUTUBE_PRIVATE_SKIP_PENDING_CHECKS=true
YOUTUBE_COPYRIGHT_HIGH_RISK_TERMS=islam itu indah,transcorp,trans tv,trans7
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

Output baru membawa identitas `FENDY AUDIT` pada video, ID audit di sidecar/deskripsi upload, dan blueprint pertumbuhan Codex untuk acquisition, retention, conversion, serta returning viewers. Blueprint adalah rencana eksperimen terukur, bukan jaminan view atau subscriber.

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
.\.venv\Scripts\python.exe clipper.py "https://www.youtube.com/watch?v=..." --top 5 --min 25 --max 180
```

Quick test on the first 180 seconds:

```powershell
.\.venv\Scripts\python.exe clipper.py "https://www.youtube.com/watch?v=..." --model Systran/faster-whisper-base --analyze-seconds 180 --top 1
```

Create one non-Short cinematic Long Story targeting 5–10 minutes (300–600 seconds):

```powershell
.\.venv\Scripts\python.exe clipper.py "URL" --clip-mode highlight_5m --compilation-target 600 --min 30 --max 90 --visual-mode auto_fyp --ai-enabled
```

Create a Long Animate video from a UTF-8 script:

```powershell
.\.venv\Scripts\python.exe clipper.py --clip-mode long_animate --script-file ".\naskah.txt" --output outputs --ai-enabled --ai-base-url http://localhost:11434/v1 --ai-model llama3.2-id:latest
```

For prompt-faithful visuals without a paid API, install and start the pinned local
Z-Image-Turbo Q3 runtime (about 5.8 GB):

```bash
./scripts/install-local-image-model.sh
./scripts/start-local-image-model.sh
```

It exposes `http://127.0.0.1:7860/v1/images/generations` through
stable-diffusion.cpp. The memory-safe default `1024x576`, 8-step render is designed for a
4 GB RTX 3050 and is normalized with a light detail pass to 1920x1080 by Long Animate. The runtime
uses memory-mapped model weights and retries a restarted service at a lower resolution. No Gemini/OpenAI
key is required. `LONG_ANIMATE_IMAGE_STRICT=true` stops the job when the local
service is unavailable instead of silently substituting procedural art. Use
`builtin://story-art` only when a geometric placeholder is explicitly desired.
The storyboard parser understands Markdown `Scene`/`Adegan` blocks, keeps a
shared character bible, and removes narration/on-screen-text labels from image
prompts. Long Animate conservatively
enables YouTube's altered/synthetic disclosure, starts uploads as Private, and
requires confirmation that the script and configured media providers permit
commercial YouTube use.

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

Fendy Clipper is intended for local workflows and content you are allowed to process. Make sure you have rights or permission to download, transform, and republish source videos. Follow YouTube terms and applicable copyright law.

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
