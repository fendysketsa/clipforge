# Long cron continuation — 2026-11-13

The automatic Long lane is enabled, including QC and automatic YouTube Private
admission after PASS_UPLOAD. The frontend proxy repair is now active: its served
release matches the expected proxy release and `/api/health` returns HTTP 200.

The old Lilang render is intact but has terminal DROP_SOURCE QC. Cron already
selected another source and started job `85fde21850f548b4af607f99edca5db5` without
a manual upload. It advanced from 80%, part 6, to 89%, part 10 of 10, during this
investigation. Rendering, QC, queue admission and confirmed remote upload remain
separate stages. The replacement has not yet finished or confirmed an upload.

## Changes ready for deployment

- Reconcile Long attempt checkpoints against actual jobs. A completed QC decision
  can settle a stale reservation after its job was cleaned up. An unknown missing
  job remains reserved, preserving duplicate protection and the daily attempt cap.
- Expose live Long progress and display it on the old result card. The rejected
  card explains DROP_SOURCE and disables repeated manual upload. It refreshes
  policy every ten seconds and uses actual active jobs rather than queued labels
  left in a checkpoint. Explicit PASS_UPLOAD and upload_allowed are required.
- Sample one frame per second before the costly layout in the optional watermark
  probe. Spatial transforms and output coordinates stay the same. In a real
  three-second source sample, the probe dropped from 16.091 to 1.330 seconds;
  both results contain three 640×360 frames. This is a probe benchmark, not a
  claim that whole-video rendering is twelve times faster.

## Evidence and activation

298 backend tests, 37 frontend test cases, TypeScript and the production frontend
build passed. A temporary browser preview verified the rejection reason, actual
replacement progress and disabled upload button using read-only backend requests.
See `verification.json`, `tests.xml`, `browser-ui-verification.json`,
`long-status-preview.png`, `probe-benchmark.json` and the runtime snapshots.

The new changes above are source/build verified, **not active in production**.
This session cannot access Docker and sudo requires a host administrator password.
The active renderer was left running. Once existing render/upload work finishes,
the repository's normal single update command activates the complete patch:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

After deployment, verify backend source manifests, frontend deployment release,
API health, the scheduler and Long progress. Do not equate passing tests or an
enabled policy with a completed remote upload. No rejected source was resubmitted
to a provider, manually approved, uploaded again or deleted during this repair.
