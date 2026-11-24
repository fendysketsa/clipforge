# Kantor AI — observed queue activity, 24 November 2026

The main UI now contains the office scene, compact department selectors, actual current work, operational links, and expandable incident actions. Strategy instructions, capability counts, learning counts, static director explanations and the manager-intent journal are removed from the rendered page. Existing strategy, callable skills, learning, persisted settings and worker safeguards stay in the backend.

## Source of activity

`OfficeService.context()` calls `ai_office_activity.observe()`. This read-only projection observes ClipJob status/stage/progress, independent Long QC IDs, YouTube/TikTok upload records, Facebook runner/upload observations, the upload-attention execution lock, the terminal-cleanup execution lock, pending claimed-file cleanup, and actual blockers. It separates running, queued, blocked, idle, paused and unavailable. Counts remain exact when the per-department work list is capped at eight. A parent job waiting for an upload is not counted a second time once that upload record exists. Completed and confirmed uploads do not remain active. Informational fallback policies are not fictitious blocked jobs.

The client polls every five seconds. Bubble text, job identity, owner, stage and available progress come from this projection. Missing, failed or stale observations cannot claim work. Coordinator pause does not conceal a manual job still running under its original owner. Agents travel through real doorways only after an observed destination changes. Queued agents do not type; completed work returns the agent to idle. No timed roaming loop or generated office chatter remains.

## Validation

- 108 backend, deployment and callable-skill tests passed; all eleven existing skills remain available.
- Frontend office-state and route tests passed; production build and TypeScript checks passed.
- Production preview readiness verified the served asset hashes and build manifest.
- Browser integration uses the actual `OfficeService.snapshot()` and new observer with isolated test records. It covers queued to running, same-ID transfer to QC, completion, queued/running/confirmed upload, employee filtering, pause, bubble control, zoom, lighting, stale data, missing telemetry and reduced motion. No mutating requests, worker dispatches or journal writes occurred.
- Screenshots and pixel checks passed at 1440, 1280, 900, 390 and 320 CSS pixels in both themes, with no horizontal overflow or JavaScript errors.
- A separate read-only capture projected live local API records through the new module and confirmed that the actual active job ID and progress appeared on the correct 3D employee and work list. See `live-projection-check.json`. This preview is distinct from deployment; private process locks and Facebook runner state were not asserted by the old endpoint capture.

## Deployment

Readiness for the normal startup now requires the observed-queue capability and versioned activity contract, alongside the existing internal skills and learning checks. No separate activation script was added.

The required command was attempted:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

Sudo required a password, so container build/recreation did not run. The deployed services have not activated these changes. Persisted operator settings, publication holds and remote upload identities were not edited.
