# Niche playlist and upload submission recovery repair — 2026-11-13

The red toast is emitted when the browser cannot reach the serialized upload
recovery endpoint. The green TikTok toast confirms queue admission, not upload
completion. Both recovery routes and the production health endpoint responded
at inspection time; the historical connection failure could not be reproduced.

Previously Studio playlist selection stopped if the requested row did not
exist. The repair searches the exact name, creates a missing playlist once,
requires the matching row to appear, and uses the existing checkbox/save
verification before the uploader advances to audience, checks and visibility.
Existing playlists and unknown/loading results cannot trigger creation.
An uncertain Create response stops without repeating Create.

Cron jobs now persist their niche through Shorts and paired Long creation,
so a generic dialogue title can still route to Drama China, Drama Korea,
Gaming, Podcast, Sepak Bola, and the other configured niche playlists.
The frontend retries guarded recovery up to three times, checking durable
records between requests and retaining its duplicate guard on uncertainty.

Validation: 112 backend tests, 5 native Chromium integration tests, frontend
queue tests (15 cases), TypeScript, frontend production build, Python compile,
and git diff whitespace checks passed. Studio's playlist list, new-playlist
submenu and creation form were inspected on a separate tab without saving.
A later read-only CDP search check could not reopen the dialog, so actual
remote creation and end-to-end upload with this change remain unverified.

Production activation is blocked: Docker socket access is denied and
`sudo -n docker-compose --env-file .env build backend frontend` requires a
password. The prepared local frontend build is `.next-niche-playlist`; no
Docker image build or new runtime activation was confirmed. Existing cron
processes were left running. See runtime-status.json and verification.json.

After current work finishes, the repository's standard activation command is:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

Verify healthy containers, source hashes, scheduler state and an actual
PLAYLIST_CREATED_CONFIRMED / PLAYLIST_CONFIRMED upload before claiming live
playlist creation success. Do not replay ambiguous previous uploads.
