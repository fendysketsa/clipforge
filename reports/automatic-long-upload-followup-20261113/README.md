# Automatic Long upload follow-up — 2026-11-13

The user's frontend rebuild is verified: served release
`a51aab87c6aa42f39bc9db76c1276a0251a14c441d001d5336fc1e80906387ba`
matches the prepared frontend repair. It does not activate backend workers.
The running backend still lacks the pending cron patch; `/openapi.json` lacks
its durable cron playlist permission field.

Cron and Long production are ON. Both automatic QC and automatic YouTube Private
admission are ON. The replacement Long's QC record repeatedly returned
`waiting_for_ai_or_evidence`, reason `ValueError`, with a ten-minute retry.
The old record saved neither the message nor the failing stage. Its exact error
cannot now be reconstructed: both platform uploads completed and their normal
cleanup removed the artifact. Do not assert that this particular historical
ValueError was definitely an audio mismatch or an invalid AI response.

YouTube upload `2f546df2dfe545559f12fdd4fd1fc2eb` is now completed, with
`upload_confirmed=true`, remote video `2PRl4z8aSx4`, and the saved publication
slot 17 November 2026 at 20:30 WIB. TikTok also confirmed its exact post. These
were the already-existing upload requests; no new submission was made here.
The automatic production target is one Long/day.

## Repairs ready for backend activation

- Classify an actual local audio/caption contradiction as a source QC failure,
  keeping uploads disallowed and allowing the capped replacement lane to move
  on. It must not become an endless provider-outage retry. Unavailable local
  recognition, unavailable AI and invalid AI contracts remain held, not passed.
- Save the failed QC stage and a sanitized exception message, so the next
  failure identifies frames, thumbnail, audio extraction, local recognition,
  provider request or AI validation instead of only `ValueError`. Provider
  credentials and bearer tokens are redacted.
- Reconcile stale Long reservations against completed, confirmed non-simulated
  YouTube uploads with a valid remote ID. Cleanup of the render no longer leaves
  its attempt eternally `queued`. Remote confirmation counts the actual upload
  toward the daily production target; it never fabricates a QC PASS_UPLOAD.

132 related backend tests passed. The read-only computation in
`checkpoint-recovery-preview.json` applies the new reconciliation to the actual
stored records and correctly settles the cleaned replacement's checkpoint.
The live checkpoint was not directly overwritten. No refused source was
resubmitted, and no audit was manually changed to a pass.

## Activation

These backend repairs are **not active**. Noninteractive sudo still requests a
host administrator password. Once current jobs/uploads are idle, run the normal
complete update from `/www/wwwroot/clipper/clipforge`:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

Then verify backend deployment release against `verification.json`, API health,
the cron scheduler and the reconciled Long attempt. After a future eligible
render passes QC, the enabled worker should admit it automatically as Private.
Tests and an enabled policy do not prove a future automatic remote upload.
