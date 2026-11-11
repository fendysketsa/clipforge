# TikTok Shorts recovery, 11 November 2026

Scope: existing TikTok failures excluding all Long media. The initial audit found 28 failed records grouped into 12 paths: 11 real Short files plus one synthetic `upload` / `job` / `clip.mp4` test record. Long records and visibility settings were not changed.

## Already completed

The reviewed political Short `864a5c5c78d04fc889306aab6f8c2996` reused its original ID and recovered through the live-session path. It is completed with upload confirmation and exact remote URL:

https://www.tiktok.com/@titikbalikislami/video/7706903370652585237

Visibility remains Only you. Its file was present before recovery and subsequently cleaned by the application's normal confirmed-upload lifecycle.

A read-only Studio inventory captured 60 recent posts. Eight other real Short files already have an exact full-caption match and stable remote ID. Several legacy local success records contained only a profile URL, and other matching attempts still say failed. These files must be reconciled, never uploaded again. Canonical records and remote URLs are listed in execution-plan.json. A live run of the new verifier confirmed one such exact ID, full caption hash and original privacy without local source files, new transfer or Post.

## Prepared next steps

The remaining local Short `a73ad80494d8444eb4ec2ecd4827e9d5` stopped at a backend restart before any Post intent. Its media digest still matches, current render QC passed, source-rights confirmation is present, publication review is not required, and retry count is 1/3. Its public visibility is the already approved original setting and will be preserved.

Latest source adds a guarded explicit Short retry endpoint. It requires no possible Post, remaining retry budget, live target-session validation, existing unchanged file, current review/QC and preflight, original account and duplicate guards. It does not change caption, privacy or upload ID, and rejects Long.

A separate exact-remote verification endpoint validates the target account, requested stable video ID, complete caption hash and original visibility through authenticated Studio. It can reconcile a cleaned job/media record without reading media, transferring a file or posting. The browser execution lock and optimistic record version check prevent concurrent uploader interference. Unknown/mismatched remote evidence leaves the local record unchanged. Session checks now use the existing background activity helper on their own temporary tab to avoid slow background hydration.

Validation: 301 backend tests plus 38 Chromium tests passed. See the XML artifacts. The source-matching expected backend release is in verification.json. These new batch endpoints have not been activated: Docker is denied and sudo requires the desktop password. Run the requested Compose rebuild, verify release and health, then execute the exact plan through the API.

## Held entries

Four failed attempts refer to the same missing file/job `b9f424ca5a364685b39c807d47d0b70d` (MOMON PANIK! ATUN jadi BUTA di MINECRAFT). An older attempt has durable Post acceptance but no exact current remote match was found in the inspected inventory. Its original media is gone. It remains held; absence from a partial list cannot authorize another upload.

The synthetic test record has neither a real source job nor media and is excluded from real upload work. Historical failed sibling attempts are retained as history; reconciliation updates the canonical matching record and its exact URL instead of deleting history or manufacturing another post.
