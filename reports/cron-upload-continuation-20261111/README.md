# Cron and upload continuation — 11 November 2026

The latest source repairs TikTok caption/privacy readiness, YouTube upload-menu activation, and fairness between the two serialized upload workers. It includes the previously prepared cron director policy 4, whose rhythmic perspective inserts have their own encoded preview evidence in `../cron-rhythm-inserts-20261110/`.

## Verified fixes

- A TikTok privacy Select rendered as `role=dialog` is distinguished from a real blocking dialog. Changing Everyone to Only you no longer invalidates the locator used for readback. Caption clearing has a verified native keyboard fallback.
- Both CDP uploaders keep only their automated page active during the operation, then disable focus emulation and detach that session. They do not raise or close the user's Chrome window. This uses the [official Chrome page-focus protocol](https://chromedevtools.github.io/devtools-protocol/tot/Emulation/#method-setFocusEmulationEnabled).
- A live, separate YouTube audit reached the actual file input with the repaired helper. No file was selected. A successful click on a menu container alone is no longer treated as an opened upload form.
- A waiting platform receives its turn before the other worker can repeatedly reacquire the upload lock. Existing shared upload spacing remains in effect.
- TikTok waits for its Posts baseline before transfer. Existing-post reuse requires a complete caption, matching owner, unique video ID, and verified row privacy. New-post confirmation in the production upload path requires the corresponding new row, rather than any unrelated new ID. Inconclusive states do not authorize another transfer.
- Git still waits 1,800 seconds after code/staging/HEAD activity. Its message generator now prioritizes changed production behavior over incidental History layout markers; its installed timer reads the repository script directly. No manual repository commit or push was performed.

## Checks

- `regression.xml`: 1,332 passed; two previously excluded unrelated storyboard-stream tests remain excluded.
- `native-browser.xml`: 20 passed, using isolated Chromium documents with network requests blocked.
- `git.xml`: 25 passed, using temporary repositories and local bare remotes.
- Python compilation, Bash parsing, and whitespace checks passed.
- `youtube-live-form.json`: live YouTube file input ready, no file selected.
- `remote-post-evidence.json`: read-only matching of already present TikTok posts, with exact IDs and privacy. This audit does not change local upload records.
- `runtime-status.json`: running service evidence, kept separate from tested source evidence.

## Deployment boundary

The last verified backend is still director policy 3. Cron was OFF, although existing upload queues continued running. History already serves four desktop columns and queue positions. The independent Long configuration enables automatic QC and TikTok upload; that setting alone does not prove all three historical Long uploads completed.

Noninteractive sudo returned `sudo: a password is required`. No backend activation or all-uploads-completed outcome is claimed. The combined activation includes the new `browser_page_activity` dependency and verifies its hash with the uploader modules:

```bash
sudo bash /www/wwwroot/clipper/clipforge/scripts/activate-director-source-recovery.sh --resume-cron
```

It builds and verifies sources, waits up to ten minutes for actual active work, preserves browser/upload checkpoints, activates the backend and existing History build, and resumes cron after verification. A busy-worker timeout is an incomplete activation and must not be reported as success. Ambiguous old Post checkpoints remain protected; their absence from one Posts page is not deletion evidence.
