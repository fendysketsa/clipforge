# TikTok browser outage and false logout

The affected Long is upload `6a0c263d509749d3ab61e02f67cace3a`, source job `2a08735031e3425faa863fd198665238`, visibility `only_you`. Its persisted log first confirms the intended account and saves the session. A cancel-upload dialog then blocks the form. A later retry uses an isolated context while the external Chrome browser is unavailable; that context reports logged out. The final card consequently shows a login error, despite the earlier authenticated browser evidence.

Current live validation through `POST /api/tiktok/session/check` returned `ok: true`, `TARGET_ACCOUNT_CONFIRMED:@titikbalikislami` and `SESSION_SAVED`. This turn performed no file transfer, Post or upload retry. The affected Long remains failed; no new remote post is claimed.

The current backend deployment report has release `7646145fd517a92fead41e5cc6f124f46d1c36cda5c9c19c3f750e5d9b653293`, which includes the previous cancel-dialog repair. The older report claiming that repair had not been activated is superseded by this current deployment evidence. This turn adds separate outage handling; it is not active yet.

Changes:

- When configured to use external Chrome, a failed readiness probe prevents silently launching an isolated uploader or session check. The existing login state is preserved.
- A connection failure after the readiness probe also stops before isolated-context fallback when external-browser mode is enabled.
- Only the exact pre-Post outage message permits the existing bounded retry policy. Existing Post intent, API acceptance, remote URL, confirmation, retry budget, account, file and privacy guards remain in force. A genuine login rejection still follows the existing login recovery path.

Validation: 178 tests passed across browser-outage handling, TikTok uploads, cancellation, upload spacing, caption recovery, cron fresh-upload behavior and deployment. See `tests.xml`. Test dependencies were installed under `/tmp/clipforge-test-deps`; application dependencies and credentials were not changed.

Activation was attempted only as a read-only Docker inspection: ordinary Docker access was denied, and `sudo -n docker ... exec` returned `sudo: a password is required`. The new changes have not been rebuilt or activated. The standard Compose update command must run from the user's terminal:

```sh
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

After rebuilding, check the deployment release against `verification.json`, validate the live TikTok session, and inspect the affected record before any retry. A valid session does not prove the failed Long has uploaded.
