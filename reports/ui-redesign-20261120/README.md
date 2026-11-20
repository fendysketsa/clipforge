# ClipForge UI redesign — 20 November 2026

Implemented a shared studio design with a new operational overview, grouped desktop navigation, accessible mobile drawer, consistent light/dark themes, clearer creation/review/automation/platform workspaces, and a matching favicon.

The overview uses backend job/upload/schedule records. Unknown data stays unknown, failures display a retry notice, and existing settings, QC holds, upload identity and publication behavior are preserved. Existing Facebook/backend workspace edits were retained.

## Frontend optimization

- Removed roughly 600 unused CSS rules/selector branches and obsolete decorative layers. The detailed component stylesheet fell from 275,446 to 181,798 bytes (34%). Theme tokens are centralized.
- Split results, history, connections, Facebook, control and analysis panels into dynamic imports. Results/history mount only when viewed. The composer loads on first visit and remains mounted to preserve drafts when navigating.
- Preview videos use `preload="none"` and `playsInline`.
- Removed the continuous title/favicon animation loop. Tab status changes only when job progress changes.
- Cold initial-page JS transfer: 217,010 → 193,257 bytes (10.9% smaller). CSS transfer: 53,687 → 42,610 bytes (20.6% smaller).
- Added no dependencies or external fonts.
- Deployment readiness now verifies dynamic panel assets as well as the initial page. The normal Dockerfile/Compose startup still performs source and asset verification.

## Validation

- Production build and TypeScript/lint: passed.
- Frontend tests: 9 test files passed, including the existing queue/upload/theme/proxy tests and navigation deep-link tests.
- Deployment and Facebook integration suite: 137 tests passed. The initial restricted-sandbox run stalled in TestClient; the completed run outside the sandbox passed. Deployment tests also cover a tampered dynamically loaded chunk.
- Browser: all workspace sections plus source archive checked; light/dark at 1440px, and responsive layouts at 1280px, 390px and 320px. No horizontal page overflow or uncaught JavaScript errors in the checked states.
- Browser fixtures cover long titles, queued/running/completed/failed/cancelled cards, result videos, history filters/search, draft preservation, and mobile Escape/focus return. Four desktop history tracks and one mobile track were measured.
- Live backend data was read without uploads/publication. Because port 3100 is outside the production CORS allowlist, the review script mirrored live GET responses through Playwright's API context. It did not change the backend CORS configuration. Fixture interactions blocked non-GET backend actions.
- Before/after initial browser JS/CSS transfer measurements are in `state-review.json`; screenshots and computed layout checks are in this directory. These are cold initial-page resource measurements, not a benchmark of rendering or backend throughput.

## Deployment status

Source, production artifact and preview fingerprint verification passed. Verified preview build: vkwBczNuCvQciHsU4eB3e.

Attempted the required command after confirming no active production/upload jobs:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

It exited before Docker ran because sudo requires a terminal password:

```
sudo: a terminal is required to read the password
sudo: a password is required
```

The main services on port 3000 remain on the previous release. No production activation is claimed. Run the same standard command in an authenticated server terminal; readiness checks are integrated into normal startup. No separate activation command is required.
