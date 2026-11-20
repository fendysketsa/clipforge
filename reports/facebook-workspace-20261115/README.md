# Facebook workspace — 15 November 2026

Implemented in the existing ClipForge dashboard at `/#facebook`, with a Facebook connection card also available in `/#settings`.

## Editorial and production

- Starting niche: Indonesian everyday phone/technology tips; optional simple digital habits.
- One concrete problem, visible steps, and a complete result. Prefer 30 seconds, default maximum 38 seconds, selectable maximum 45 or 55 seconds. There is no automatic duration expansion in this lane.
- Up to three distinct clips per input. Existing sentence-boundary, context, editorial and render checks remain active. The uploaded source stays unchanged during rendering.
- Same RYUUNDY SVG watermark as existing Shorts. Separate stable white phrase captions, measured to the actual font width; no word animation. Facebook disables subscribe overlays, subscribe voiceovers, unrelated religious outros, large editorial cards and added third-party music. Tutorial steps stay visible.
- Separate posting copy: brief, conversational, grounded in the clip, with two niche hashtags. No public source line, URL, creator mention or engagement bait. Private source/rights evidence remains in the normal job metadata. Input must be owned or have permission that permits publication without credit.

## Browser and publication

- Facebook email verified live: `fendysketsa@gmail.com`.
- Professional dashboard indicator verified on the active personal profile.
- Facebook, YouTube Studio and TikTok Studio share the existing persistent Chrome on CDP port 9333. No profile migration, session reset or cookie export was performed.
- `clipforge-social-browser.service` is enabled and running. Its existing repo launcher now restores all three tabs and monitors an already-running Chrome instead of repeatedly exiting/restarting.
- Saved login survives normal profile reuse; the platforms retain control of session expiry and verification challenges. A single browser does not bypass each platform's initial login.
- Uploader form inspected with a synthetic 30-second fixture, reaching the public-audience screen and detecting `Posting`. **No Post/Posting button was pressed. No real production clip was published.**
- Upload records are persisted atomically in `backend/data/facebook_workspace.json`, bound to the verified profile and file SHA-256. Account/Page switches are rejected. The submission checkpoint is saved before Post. Restarted or uncertain submissions are held for exact remote reconciliation, without automatic re-upload. Explicit retries are limited to failures before Post, with the same file, refreshed identity and QC, and at most three total attempts.
- Upload execution and cooldown are shared with YouTube/TikTok. Pending and uncertain Facebook results are protected from normal explicit job/clip deletion. Facebook jobs are excluded from the other platforms' automatic publication lane.
- Before public upload: operator preview/review, completed production, preserved publication holds, valid rights, Facebook render metadata, current watermark, encoded H.264 1080×1920 with audio and no duration above 55 seconds, complete context, render QC and a verified target session.

## Validation and activation

- 315 focused/regression tests passed; see `regressions.xml`. API tests use temporary ledgers; no production scheduler was started by the tests.
- Frontend typecheck and production build passed. Frontend source/asset verification passed.
- UI checked at 1440, 1280, 390 and 320 CSS pixels, including a long title, running and failed states. No body overflow or page errors. Preview/QC/queue interaction exercised with mocked API data; see `ui-verification.json` and screenshots.
- The sample video and screenshots are test fixtures, not proof of a published clip.
- The full existing export pipeline was exercised with a synthetic input: exactly 30.000 seconds encoded, H.264 1080×1920 with audio, identical source SHA-256 before/after rendering, Facebook posting caption, current watermark, no extra outro/subscribe CTA, and seven-frame render QC passed. See `full-render-verification.json` and `full-render-frame.png`.
- Standard deployment was attempted using the required exact command:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

The command could not run because sudo requires the operator's password. Direct Docker access is also denied. The current production backend returns 404 for `/api/facebook/config`, so the Facebook workspace is **source-ready and preview-built, not activated in the running containers**. Existing service/database settings were preserved. Browser launcher changes are already picked up by the existing desktop service.

Facebook capability checks are integrated into normal Compose readiness and frontend asset verification. After the standard deployment can run, verify service health, the Facebook capability response, the served frontend build, and the live account before reporting activation. Actual first-source clipping and a confirmed remote Reel remain unverified.
