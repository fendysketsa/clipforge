# Failed production and upload audit — 14 November 2026

Live cleanup completed through the running backend API:

- Removed 5 failed render jobs with no clips, no local final media, and no related upload identity.
- Removed 47 failed/cancelled YouTube records with missing local media and no remote, file-selection, or final-save checkpoint.
- Public read-only checks of 25 exact YouTube IDs found 14 available videos and 11 videos explicitly removed by their uploader. Removed those 11 unusable local records after another status/file check and a persistent backup.
- Total removed: 5 render jobs and 58 YouTube records. No remote videos were deleted by this cleanup. Completed uploads and active work were preserved.
- Prepared 21 exact TikTok record IDs for cleanup during normal backend startup. Each is rechecked against its original update timestamp, missing media, terminal status, and absence of any Post/remote identity. This cleanup has not run in production yet. An isolated simulation removed the expected 21 and preserved remote outcomes.
- Retained ambiguous submissions and file-selection checkpoints. A missing local render is insufficient evidence that a remote upload does not exist.

Backups are in the persisted `backend/data/failed-cleanup-audit/` directory. The pending operator request is `backend/data/failed_cleanup_requests.json`. Neither contains a request to publish, retry, or delete a remote post.

## Root cause and validation

Long cron source validation was losing `view_count`, `is_live`, and `live_status` in `sanitize_metadata()`. The fresh-metadata check therefore rejected valid Long demand as missing. These fields are now preserved; unknown demand and live sources remain rejected. Regression coverage exercises the sanitized metadata, not only a hand-built source profile.

Validation: 154 backend tests passed; all 6 frontend test files passed; production Next.js build and preview asset/manifest readiness passed. Browser verification covered 24 responsive view captures and 24 interaction assertions, including review holds and unknown submissions. No browser runtime errors or horizontal overflow were found.

## Activation status

The final UI preview build is `vVVGdJMPveqTWHKZ37bKz` on port 3037. Production frontend still served build `ryx7nsd9xiQf3kjsabon0` at the final check. Backend health returned HTTP 200; live production continued, including a new YouTube upload. `sudo -n true` returned `sudo: a password is required`.

The UI changes, Long metadata fix, and 21 TikTok cleanup requests require the repository's standard deployment, after active uploads finish:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

No separate activation script or cleanup command is required. Running services must be verified after that deployment before claiming activation.
