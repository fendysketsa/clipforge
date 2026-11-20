# Automatic upload attention — 20 November 2026

The screenshot's 71 attention rows were reproduced from the live API: 57 YouTube rows and 14 TikTok rows. Nine TikTok rows were historically marked completed but retained only a profile URL, which is insufficient to identify a particular post. All inspected failed records lacked a local media file; resubmitting them is not a viable repair.

The policy derived from the snapshot identifies 12 records with a verified same-media sibling, 56 requiring remote observation, and 3 explicit claim holds. This is a handling plan, not a claim that those records have already been repaired.

## Confirmed cause

Read-only authenticated Studio inspection of YouTube ID `V_SitOyPadM` matched the complete title, description and original filename. Its real visibility is Public, while its local failed record expects Private. The new reader verified it without uploading, saving metadata or changing visibility. The evidence is in `observed-youtube-proof.json`; the running local record has not yet been reconciled.

## Implementation

- A normal API startup hook starts one bounded worker. No separate activation script is needed.
- A small atomic ledger preserves attempts, backoff and proof across restarts. It does not replace upload records, QC decisions, operator settings or remote IDs.
- Verified same-media siblings reconcile historical attempts without transferring media. A conflicting file hash is never treated as the same file.
- Ambiguous submissions are observed in owned authenticated Studio tabs. Exact IDs, account, full metadata and actual visibility are checked. Discovery without a YouTube checkpoint additionally requires the original filename. TikTok requires an exact post ID and full caption; duplicate captions remain uncertain.
- Actual visibility can update the local record without changing the remote post. Observing a Private/Unlisted video cannot erase an intended YouTube publication schedule.
- Fresh retries are bounded, require proof of a failure before submission, unchanged local media hash and the original preflight/QC checks. Missing media, claims, review holds and unknown submissions never authorize a retry.
- Browser work yields to active upload queues and shares their execution mutex. One browser read runs per cycle, with backoff up to six hours. A reader timeout gets a cleanup grace period before being killed; the operator's browser and other tabs remain intact.
- The panel separates automatic handling from holds, shows reasons and the next check, and offers a nonblocking “Periksa sekarang” request. It polls only while visible. Reconciled TikTok attempts for the same exact post appear once.
- Docker startup readiness checks require the attention API and worker, and frontend verification includes the new panel assets.

## Verification

Production build, TypeScript and frontend regression checks passed. Backend regression covers identity mismatches, claims, changed records, hashes, pending schedules, actual visibility, mutex contention, persisted backoff, unknown outcomes and reader timeout cleanup, together with the existing upload/deployment suites. Final result: 476 backend tests passed (26 warnings), 9 frontend test files passed, and the production frontend build plus source/served-asset verification passed. Verified frontend build: `MSF_bQJ_3jSSiHNGpqLUH`.

Browser checks used the actual upload snapshot with a policy-derived status fixture because production has not yet activated the new API. Search and hold/automatic filters passed. Light/dark views were checked at 1440, 1280, 390 and 320 pixels, with no page overflow or uncaught JavaScript errors. Non-GET backend requests were blocked during UI checks. Screenshots are previews, not evidence of an active production worker.

## Deployment

The required standard deployment was attempted after confirming there were no active job or upload queues:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

It failed before Docker ran because sudo requires a terminal password. The new worker and panel are source/build-ready, not activated in the main services. Run the same command from an authenticated server terminal. Readiness checks are integrated into normal startup.

A final live check returned HTTP 404 for `/api/uploads/attention`, confirming that the production backend has not activated this feature. No claim is made that the 71 records have already been resolved.

The user-requested skill names “intrograsi” and “wartawan profesional” were not found in the available catalog or local skill folders. This work used direct repository, API and authenticated Studio evidence; those unavailable skills were not invoked.
