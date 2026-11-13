# Automatic cleanup of terminal cron outputs

Source implemented and verified; container activation remains blocked by `sudo: a password is required`.

- Cron-owned artifacts only (`scheduled_public_source_credit`). Manual jobs remain outside this cleanup rule.
- Long QC outages and worker/enqueue setup failures have a three-attempt budget, with a 60-second retry interval. Exhausted outputs are discarded without fabricating QC approval.
- `DROP_SOURCE` is terminal. A Long requiring an unsupported repair is discarded so another source can be selected. Provider safety refusals are never resubmitted or bypassed.
- YouTube browser recovery is capped at three attempts for cron. A failed subprocess explicitly certifies whether it failed before file selection; the parent persists file-selection evidence separately from its bounded log tail.
- Active workers, a possibly submitted file, an unconfirmed remote ID, or an accepted/uncertain TikTok Post prevent cleanup. TikTok pre-Post failures use the existing bounded retry budget.
- Cleanup removes exact local artifacts and their final job card/workspace. Successful remote posts and all platform upload records remain intact. Shared and nested workspaces referenced by other jobs are protected.
- Interrupted/failed filesystem cleanup has a durable checkpoint and is retried. Long reservations and parent cron checkpoints are settled as deleted, not counted as QC or upload success. The daily source-attempt cap remains intact.
- Cleanup runs inside the scheduler and background upload sweeper, without an open dashboard or email.
- `/api/automation/viral-cc/long-production` exposes cleanup enablement, the recovery limit, and recent outcomes. `AUTO_UPLOAD_TERMINAL_CLEANUP_ENABLED` defaults to true in Compose.

Validation: **389 tests passed** (see `tests.xml`), Python compilation and `git diff --check` passed. Fixtures verify physical file/card deletion, retained TikTok confirmation, unknown/active submission protection, partial deletion recovery, sibling/nested workspace preservation, bounded worker recovery, and continued source selection without resetting attempt limits.

Live pre-activation: backend healthy, initially no jobs or queued/running platform uploads. The final read found a newly running job `f73d7456928946a79f2b8b7a40667cd6`; it was left running. The backend still did not expose the new cleanup policy. See `runtime-before.json`, `runtime-after.json`, and `activation.json` for runtime evidence and the running/expected release IDs.

Activate from the repository directory:

```sh
sudo bash scripts/activate-terminal-output-cleanup.sh
```

The script builds first, pauses new cron launches, waits for active jobs/uploads and media subprocesses to finish, recreates backend/bot, verifies the new API policy and source release, then restores the previous cron switch. It writes `reports/terminal-output-cleanup-activation.json` only after runtime verification. A successful build alone does not prove activation.
