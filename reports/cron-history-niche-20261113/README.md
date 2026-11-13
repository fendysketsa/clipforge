# Cron niche: Sejarah, Geografi & Budaya Nusantara

Reference: https://www.youtube.com/watch?v=75K0oO1M4UM, Javanese Stories.
Public metadata describes an educational documentary connecting southern Java,
colonial decisions, geography, maritime trade and cultural narratives. The
reference metadata is saved in `reference.json`; it is not evidence that its
historical claims or media rights were independently verified.

The new `history_geography_nusantara` profile enters the existing cron rotation
with documentary search queries, matching topic signals, complementary Short
and Long directions, and topic-specific hashtags. Both formats persist the
same niche and route to **Sejarah, Geografi & Budaya Nusantara**. The reference
is inspiration, not a forced download or unconditional upload. Manual discovery
retains its existing catalogue.

Playlist creation is now explicitly cron-only. New cron upload records persist
`cron_create_missing_playlist`; the worker receives `--create-missing-playlist`.
Older records can inherit permission from a still-present source job marked as
cron. Manual uploads default to no creation permission. A matching existing
playlist is reused. If an exact Studio search proves absence, the worker creates
the playlist once, verifies its exact row and saved selection, then continues
the usual audience, checks and visibility steps. An unknown response never
causes another Create click.

Validation: **260 tests passed**: 195 related backend tests, 58 selected cron/API
regressions and 7 Chromium tests with simulated Studio. They cover actual cron
rotation selection, source fit, format propagation, durable permissions after
source cleanup, existing-playlist reuse, one-time creation and manual isolation.
Python syntax and whitespace checks passed. A broader API run was interrupted
at an unrelated storyboard streaming test; its incomplete run is not counted.

## Activation status

The change is source/test verified, **not activated in the running backend**.
Read-only `/openapi.json` inspection still lacks the new cron permission field;
API health and the cron scheduler are healthy. The previous replacement Long
finished rendering and entered automatic QC, which is waiting for AI/evidence.
No remote playlist was created during tests and no upload was initiated.

The session's standard Docker deployment access remains unavailable because
sudo requires a host administrator password. After active render/upload work
finishes, the normal complete application update activates this with the other
pending fixes:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

Verify the backend release against `verification.json`, health and cron status.
Actual remote creation is confirmed only by a real worker's
`PLAYLIST_CREATED_CONFIRMED` and `PLAYLIST_CONFIRMED` events; simulated Chromium
tests do not establish that production outcome.
