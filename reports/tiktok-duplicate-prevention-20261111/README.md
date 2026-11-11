# TikTok duplicate prevention — 11 November 2026

## Root causes and repairs

The running backend was still director policy 3 during this investigation. Prepared source changes from the previous turn had not been activated; noninteractive sudo still required a password.

Two additional code paths allowed the same media to be selected again:

1. Manual upload creation reused successful records but could mint a new ID after a failed record that had already started or received an accepted Post response. The new API reservation checks target account and media SHA-256 across jobs, captions and filenames. Failed attempts retain their existing retry budget for manual requests as well as cron. The worker repeats the check before opening a browser, so legacy queued duplicates are also held.
2. Draft recovery accepted a ready editor even without the requested filename. It now requires the actual file identity. Transfers use a temporary copy named with the complete source SHA-256, so two jobs named `clip_01.mp4` cannot claim each other's draft. The original media remains unchanged. Identity is checked after transfer and again before Post.

`TikTokConfig.duplicate_guard_version=2` identifies this release. The combined activation verifies that marker plus runtime module hashes. It does not authorize an existing uncertain Post to be retransferred.

## Remote inventory

The account header reported 443 posts. The read-only virtual-list audit collected 383 distinct video IDs and found 10 groups with identical complete captions. This is a partial inventory and these groups are candidates, not proven duplicate videos. Several generic template captions recur. One matching-caption pair has different durations (37 and 29 seconds), so automatic deletion by caption would remove potentially different clips.

The two `Aku pikul ibu saya 500 km ...` candidates have the same caption and displayed duration of 45 seconds:

- https://www.tiktok.com/@titikbalikislami/video/7694665474407238964
- https://www.tiktok.com/@titikbalikislami/video/7694664778416950580

The public video route did not load in the audit browser. Studio search confirmed both records, but media equivalence was not established. No remote videos, drafts, or upload-history records were deleted, and no new upload was submitted by the audit.

## Verification and activation

- `focused.xml`: 169 tests passed.
- `regression.xml`: 1,344 passed; the same two unrelated storyboard-stream tests remain excluded.
- `activation.xml`: 31 passed.
- `browser.xml`: isolated Chromium checks; see XML for final count.
- Source compilation and whitespace checks passed.
- `runtime-status.json` distinguishes live code from prepared source and records repeated local media hashes.
- `remote-audit.json` contains the candidate ID groups without signed media URLs.

Production activation remains privileged:

```bash
sudo bash /www/wwwroot/clipper/clipforge/scripts/activate-director-source-recovery.sh --resume-cron
```

The activation waits for active work and preserves browser/upload checkpoints. A successful test suite is not evidence that this command ran, that old duplicate posts were removed, or that all queued uploads completed.
