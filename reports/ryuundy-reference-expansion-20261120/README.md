# RYUUNDY reference expansion — 20 November 2026

## Applied source changes

| Owner reference | Verified identity / available evidence | RYUUNDY use |
| --- | --- | --- |
| [lJ7iSTmoAdc](https://www.youtube.com/watch?v=lJ7iSTmoAdc) | Kartun Acing, `@petualanganacing`, channel `UCRsbWgKYa7WyhgogHzfZwTw`; 1,297 seconds | New `moral_animation_story` rotation: fictional decisions, consequences and a complete moral payoff. Playlist: **Animasi Cerita Moral**. |
| [rzABQCp9YY4](https://www.youtube.com/shorts/rzABQCp9YY4) | Ngaji Quran, `@ngajialquran37`, channel `UC11EU3mqj375wJXNE4rCntw`; 35 seconds | Extend existing `lecture_wisdom` with complete Ustadz Adi Hidayat sermon queries and contextual Short packaging. This Short is a format reference, not Long material or a verified quote. |
| [-v5mR_d0XGM](https://www.youtube.com/watch?v=-v5mR_d0XGM) | ZamanEmas, `@ZamanEmasID`, channel `UCtou1nUKZ-hNxXK4HIhp-6w`; 2,186 seconds | New `nostalgia_indonesia` rotation: everyday life, houses, school, food, games and social change. Playlist: **Nostalgia & Indonesia Tempo Dulu**. |
| `@dunia.sjr` | Owner-supplied history handle; matching external search context, but the exact YouTube handle returned HTTP 404 | Included in the nostalgia/history reference brief and topic searches. No invented channel ID, platform attribution or exact-channel search. |

Three video identities were cross-checked using official YouTube oEmbed and
yt-dlp metadata, and their public thumbnails were inspected. Caption requests
returned empty responses. No full audiovisual review, spoken quotation,
historical claim, source license or retention measurement is certified by this
reference analysis. Public metadata snapshots and thumbnail evidence are in
this directory; signed caption/media URLs and credentials are excluded.

`source-fit.json` records actual metadata through the source-fit checks. The
animation and nostalgia references pass topic/language checks and the existing
Long demand/duration prefilter. The sermon Short is ineligible for Long, and its
sparse metadata does not satisfy the language check; that check is preserved.
It supplies an editorial format idea while new searches seek full sermons.

## Discovery and editorial propagation

- Two new profiles participate in the existing rotation. Search queries,
  Short/Long roles, tone, truthful hashtags and durable playlist mapping are
  installed together.
- Verified animation/nostalgia channels are optional additional API search
  lanes inside the existing query budget. At least one general search remains;
  a one-query budget retains general discovery. Manual requests and director
  replacement briefs do not inherit these channel preferences.
- References are not enqueued as unconditional source URLs and do not grant
  source rights. Existing source processing limits, QC, daily allocation,
  publication review and upload identity safeguards remain in place.
- The moral animation lane requires animation/cartoon context. Fiction is not
  relabeled as a real incident, religious proof or divine punishment. Incomplete
  episodes cannot receive invented endings. Animation alone does not set the
  child-audience flag.
- Nostalgia distinguishes dated archives, personal memory, interpretation,
  illustrations and reconstruction. It does not generalize one family's past
  experience to all Indonesia or invent dates, locations, prices or provenance.
- The public capability contract now exposes reference catalog version 1 and
  four references. `GET /api/automation/viral-cc/references` exposes the catalog.
  Normal startup checks require both new profiles and the catalog capability;
  the existing Docker manifest fingerprints the new Python module.

## Verification

**358 focused tests passed**:

- 260 tests covering the catalog, editorial profiles, reference learning,
  growth learning, history, Long strategy, drama, Compose/readiness, director
  recovery and playlist routing (`focused-results.xml`).
- 98 API budget tests selected for cron, trends, schedules, gaming and source
  discovery (`discovery-results.xml`). Three existing flag tests were made
  deterministic by selecting a non-review theme, so a live search-term cache
  cannot randomly choose politics and invalidate their unrelated assertions.
- Changed Python modules compile; `git diff --check` passes.

An earlier broader test attempt was stopped after it entered unrelated
storyboard tests: this host test environment lacks OpenCV (`cv2`), and a stream
test did not terminate on SIGINT. Only the specifically tagged pytest process
was terminated. The focused successful runs above are not a full project suite.
Tests used temporary Python dependencies under `/tmp`; no production dependency
or service setting was installed or changed by that setup.

## Activation status

The required deployment command was attempted:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

It stopped before building because sudo needs a password. The live API remains
healthy, but `/api/automation/viral-cc/references` still returns 404 and the live
Long capability contract does not expose the new profiles/catalog. Therefore
source implementation is complete but runtime activation is **not verified**.
No video was uploaded or published as part of adding these references. See
`runtime-status.json` for the current API evidence.
