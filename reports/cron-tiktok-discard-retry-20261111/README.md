# Cron TikTok: Discard and automatic requeue

Prepared behavior for scheduler-owned TikTok uploads:

- The upload command receives `--cron-fresh-upload` only for a source with scheduler provenance.
- Each cron attempt owns a new automation tab. It never selects a user's or an audit tab, and closes only its own tab when finished.
- A Discard/Continue-editing draft prompt chooses Discard. The uploader requires a visibly empty picker and no blocking modal before declaring that discard complete. A second draft-discard confirmation is bounded to one action. Delete-published-post dialogs are not operated on.
- Cron skips the Continue-editing recovery path both at initial intake and after a transfer error. Transfer failures exit before Post and enter the existing bounded retry policy. Manual upload behavior remains separate.
- The retry operator may enqueue a failed file even while unrelated YouTube/TikTok work is waiting. The shared browser lock and existing upload spacing still serialize execution.
- Retries keep their durable upload ID, file hash, account, privacy and retry counter. A new `queued_at` moves the new execution attempt to the queue tail instead of retaining its original priority.
- Recoverable failures use delays of 60, 180 and 600 seconds, with three retries. The missing-privacy-option and failed-draft-discard cases are recognized. Existing Post intent/acceptance, remote IDs, changed files and failed rights/QC gates continue to block a fresh transfer.
- Results and History cards show the automatic retry time in WIB. An unrelated or uncertain attempt clears a stale retry reservation rather than promising a retry that cannot execute.

Verification:

- `focused.xml`: 151 passed.
- `regression.xml`: 1,360 passed; the same two unrelated storyboard-stream tests remain excluded.
- `browser.xml`: 25 passed using isolated Chromium documents with network blocked, including Discard versus Continue, confirmation, overlay interception and published-post deletion protection.
- Frontend typecheck and production build passed. `frontend-build.json` verifies the retry label, four-card layout marker and queue-position component in the staged bundle.
- `activation.xml`: additional deployment and source-rebuild tests.

No production draft, remote post or media source was discarded by these tests. The live check in `runtime-status.json` still reports the older backend (director policy 3), no `cron_draft_policy` marker, and cron OFF. Noninteractive sudo requires a password. The combined activation now verifies both `cron_draft_policy=discard` and the served retry UI:

```bash
sudo bash /www/wwwroot/clipper/clipforge/scripts/activate-director-source-recovery.sh --resume-cron
```

This command must finish runtime/hash/UI verification before these prepared changes can be described as active. An uncertain Post is held against duplicate transfer; it is not silently treated as a safely retryable failure.
