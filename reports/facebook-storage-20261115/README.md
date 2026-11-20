# Facebook: compact results and confirmed-upload local cleanup

15 November 2026. The user authorized removing unnecessary material from the
Facebook results page and deleting local video files after confirmed upload.

## Completed on the running system

- Rechecked the existing Reel in the shared browser: matching account owner,
  full expanded caption, and video. No publishing action was performed.
- Verified its local SHA-256 matched the upload ledger, its job was completed
  and unheld, and no other job, repair, YouTube or TikTok upload depended on it.
- Deleted the exact local clip through the running system's existing guarded
  local-delete API. This also removed the old local job card and its generated
  workspace. The Facebook upload/autopilot history was retained.
- **17 files / 3,755,558 bytes** removed (approximately 3.58 MiB): MP4, neural
  narration, subtitle and generated intermediate artifacts.
- Verified the workspace no longer exists and the upload still has
  `status=completed`, `upload_confirmed=true`, and its exact remote URL:
  https://www.facebook.com/reel/1844917023309992/
- No remote deletion or new Post action was attempted. Other production jobs
  were not deleted or restarted.

Evidence: [cleanup-plan.json](cleanup-plan.json),
[remote-proof.json](remote-proof.json), [cleanup-intent.json](cleanup-intent.json),
[cleanup-applied.json](cleanup-applied.json), and
[runtime-verification.json](runtime-verification.json).

## Prepared source behavior

`backend/facebook_cleanup.py` owns the FB-only policy. It runs immediately
after remote confirmation/reconciliation and on normal scheduler ticks,
including ticks while production is paused. Startup starts that same worker;
there is no extra activation script. A guarded maintenance endpoint is also
available at `POST /api/facebook/storage/cleanup`.

Deletion requires completed/submitted/confirmed state, the expected target
email, an account ID, a canonical remote Reel URL or exact created Story URL,
and a matching local media hash. It preserves active processes, active QC,
repair dependencies, publication holds, ambiguous submissions, sibling assets,
cross-platform references and symlinks. It never deletes uploaded source inputs.
Only an exact single-output generated workspace owns its intermediate files;
manual or multi-output work is cleaned per clip.

The ledger records deletion intent before unlinking, completion after success,
file/byte counts and remote identity. Partial failures can resume after restart.
Cleanup failure does not demote remote success or cause another Post. Repeated
upload requests return the existing upload identity even after media deletion.
Legacy history without a local job remains visible and is marked locally absent
without inventing a reclaimed-byte count.

The Facebook results UI now uses the full available width. Published results
become compact title/status/link rows with optional caption expansion. Preview,
download, manual QC and permalink fields are removed for confirmed posts.
Unconfirmed results retain the necessary preview and recovery controls. Duplicate
titles and routine worker explanations were removed; errors use expandable detail.

## Verification

- **179 regression tests passed**, covering FB cleanup, uploads, automation,
  creative/QC policy, monetization, shared cleanup and Compose readiness.
  Existing FastAPI lifecycle deprecations remain warnings (24).
- A focused rerun verified cleanup still occurs while production is paused.
- Python compilation and `git diff --check` passed.
- Production frontend preview build: `BkANroL-crMq7xRhOmIi9`; normal build
  readiness checks include the new published-results UI.
- Browser checks at 1440, 1280, 390 and 320 pixels, plus light theme. No page
  JavaScript errors or horizontal overflow. Confirmed posts make no local video
  or thumbnail requests. Caption expansion, retained orphan history, pending
  remote reconciliation, and active production progress were checked.
- Screenshots and [ui-verification.json](ui-verification.json) are **preview
  evidence with mocked API responses**, not proof of deployed UI behavior.

## Activation remains blocked

The required standard command was attempted:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

It exited 1 because sudo requires a password and this process has no interactive
authentication terminal. The live backend remains healthy and the previous
Facebook scheduler runs, but `local_cleanup_version` is absent. The new automatic
cleanup policy and compact UI are therefore **not activated**. The one-time
cleanup of the 17 confirmed-upload files above **is completed**.
