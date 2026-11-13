# RYUUNDY watermark redesign — 2026-11-13

The owner requested a refined translucent emblem inspired by the supplied
reference, using RYUUNDY's current channel logo. The avatar was fetched directly
from the public channel identified by UCAOZF9Qzj6DYoXKtLnP4UUQ. Its current
public owner URL is @ryuundy88. Download provenance and the original hash are
recorded in backend/assets/branding/ryuundy-brand.json.

The new seal preserves the original R, crescent and ring. It uses transparent
champagne ink, a serif RYUUNDY wordmark and KISAH · HIKMAH · MAKNA. There is no
rectangular backplate, blinking, rotating ornament or copied reference logo.
The SVG embeds the actual avatar; it does not redraw the monogram or contact
the network during rendering. The avatar itself remains unchanged.

A shared channel_branding.py module supplies the same asset and placement to
Shorts, Long compilations, FFmpeg Long Animate and all Remotion templates.
The seal is 208 px on 1080x1920 Shorts and 216 px on 1920x1080 Longs, centered
at approximately 46% frame height. Logo opacity is 24%, wordmark opacity 34%.
FFmpeg corrects librsvg's premultiplied alpha to avoid muddy dark ink.
The one still image repeats to the existing stream's end without looping or
extending its timeline. Branding assets participate in image/source integrity
verification, so a changed logo requires a matching rebuilt image.

Validation: 403 tests passed across channel branding, captions, Hypit,
Remotion manifests, Long Animate and Compose deployment. Encoded video tests
check complete frame counts/duration, stable opacity, transparent corners,
confined placement and correct light ink. Python compilation and whitespace
checks passed. These generated previews were decoded and inspected:

- preview-short.mp4: 5 seconds, 1080x1920, 60 fps, silent.
- preview-long.mp4: 5 seconds, 1920x1080, 60 fps, silent.
- preview-remotion.mp4: 1 second, 1080x1920, 30 fps, silent.
- seal-transparent.png and preview/encoded PNGs: design and representative frames.
- clipper-smoke/watermark-render-check.mp4: full export_clip execution,
  25 seconds, 1080x1920, original audio retained; sidecar confirms style v2.

These previews use a local source only to inspect the watermark and are not
publication candidates. Preview-only media and temporary manifests are ignored
by Git. No upload/publication or modification of previously published videos
was performed.

The code is implemented; production activation is NOT confirmed. Docker socket
access is denied, and the attempted noninteractive Compose build returned
"sudo: a password is required". Source and successful previews do not prove
that current cron workers execute this version. After current jobs finish,
activate with the project's normal command:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

Then verify healthy containers/source hashes and inspect a newly produced
output's channel_watermark style_version=2 plus its actual encoded frames.
