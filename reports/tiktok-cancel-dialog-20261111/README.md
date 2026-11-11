# TikTok cancel-upload modal recovery

Root cause: dismiss_upload_overlays searched the whole page for Cancel/Batal after selecting a file. It clicked the real upload Cancel control and opened Studio's "Sure you want to cancel your upload? Any edits to your current upload will not be saved. No Yes" dialog. Generic modal handling had no No action, and the automatic retry classifier did not recognize this pre-Post failure.

Fix: no document-wide Cancel/Batal lookup remains in overlay cleanup. The observed cancellation prompt is matched strictly; only its scoped No control can be clicked. Keyboard recovery requires an enabled, visible, focused, uncovered No. A late click acknowledgement does not cause a second action, and any new/different modal stays blocking. Yes and Post are never activated by cancellation recovery. The earlier cron Continue-editing/Discard prompt still follows Discard and empty-picker verification, then a new file transfer.

Only this exact legacy pre-Post error gains bounded automatic retry (existing maximum three, backoff, same upload ID, same account, unchanged file hash, original privacy and review gates). Own/sibling Post intent, acceptance, remote ID or confirmed result still blocks blind retry. Unknown dialogs, safety restrictions and consent prompts gain no retry permission.

Read-only audit found four matching failed records with unchanged local files and no own/sibling possible-Post records in the inspected snapshot. This is not a claim of remote absence or successful posting. Raw browser/session/API data was kept in a private /tmp file; reports contain only IDs and audit booleans. No live upload, retry, publication, session change, deletion or restart was performed during this repair.

Offline native Chromium tests reproduce the actual form Cancel button and No/Yes dialogs, preserving the transferred file and checking covered controls/late acknowledgements. Source syntax and standard Compose image inputs include the new pure tiktok_dialogs.py helper. See focused.xml, browser.xml, regression.xml and verification.json.

Activation is pending because sudo requires an interactive password. Use the standard update command, with no separate TikTok activation script:

```sh
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

After activation, the existing sweeper can recover the four legacy errors if their current account, media, duplicate and review gates still pass. Persisted queueing or test success is not remote posting proof; the exact TikTok post ID and upload_confirmed must still be verified.
