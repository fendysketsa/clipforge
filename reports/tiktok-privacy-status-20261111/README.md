# TikTok privacy selection and upload outcome repair

The affected source b9f424ca5a364685b39c807d47d0b70d has a latest pre-Post failure requesting Only you. Runtime logs show the old worker dismissed its own Everyone/Friends/Only you privacy Select dialog. The default Everyone displayed in Studio did not satisfy this private request.

The older attempt aee89716f6b040ccab195408c1fa65d2 requested public and has both Post intent and API acceptance, but lacks an exact confirmed post ID. It must not be transferred again merely because the newest attempt failed before Post. A read-only isolated Studio search found an older different 47-second clip; it does not confirm this approximately 29-second clip and does not prove absence.

Source repairs preserve the controlled privacy Select, re-acquire its changed trigger, normalize whitespace, and recheck requested privacy after processing immediately before Post. Errors report target and observation while retaining terminal safety causes. Safe pre-Post failures retain bounded retry; any previous possible Post blocks a fresh transfer through the existing backend duplicate guard.

Results and History cards now retain prior same-account uncertain Post evidence, prefer an older same-hash confirmed result, show actual requested privacy, and avoid a misleading Retry action or hardcoded private-success label. Offline SSR tests execute both real components. Native Chromium tests use isolated pages with all network requests aborted.

See verification.json and test XML files. The production frontend build is staged in frontend/.next-director-recovery. The running backend remains policy 3, cron disabled, and missing the new duplicate/draft policy fields. Activation was not performed because sudo requires the user terminal password. No live uploads, posts, or remote deletions were performed during this audit.

Activate with:

```sh
sudo bash /www/wwwroot/clipper/clipforge/scripts/activate-director-source-recovery.sh --resume-cron
```

This command verifies image/source hashes, installs the staged UI, preserves checkpoints, and resumes cron after checks. It does not establish that the affected clip was remotely posted; that still needs its exact remote ID. The public versus private cron preference remains pending user clarification; no blanket visibility change was made.
