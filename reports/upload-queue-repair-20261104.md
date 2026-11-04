# Upload queue repair — 4 November 2026

The changes are active and the target upload is **completed and confirmed**. YouTube upload `c9e987c2ade94f08b351fb0fd2eda6c8` finished at **15:53:33 WIB**, with Private visibility: https://www.youtube.com/watch?v=X51zOpHOhnM. YouTube Studio confirmed the transfer and the new video's title and visibility. TikTok was also confirmed. The temporary login helper opened during investigation was stopped after success; no further login is required for this target.

## Findings and changes

- The browser only polled uploads already known to be active. Work started or finished by cron could therefore leave its queue view stale. It now refreshes server state every 15 seconds while visible and immediately on focus/visibility changes. A production-browser test verified idle → queued → completed without reloading.
- The remaining clip, job `12becc7cd0a14d929072e571caa1512a`, was incorrectly classified as a religious ruling because it ended with a general wish about working anywhere and staying healthy/halal. A narrow shared rule now distinguishes that phrase from specific rulings or quotations. Legacy reassessment requires matching transcript hashes and intact context. Original audit evidence is retained; `is_correct` remains false. The source video bytes were not edited.
- An old failed Private reserve, `c3491accb5a84921abc14e246ebf5671`, still consumed capacity although video `wGJD-V4ae_0` had been deleted by its uploader. YouTube's player response explicitly confirmed that deletion. The reserve was marked cancelled locally; the historical record and remote ID remain. The removed video was not uploaded again.
- A background reconciler now checks failed Private reserves while the uploader is idle. It releases a reservation only on an explicit uploader-deletion response for that exact ID. Private/unavailable videos, claims, login failures, timeouts, and mismatched IDs keep their reservation. Checks have a 15-minute cooldown. The upload operator also survives a transient cycle exception.
- Once capacity was released, YouTube upload `6e9f0883897b4c42bb340d523f3ee789` was created. It failed before file selection because the Google session was signed out. No remote video ID was created. TikTok upload `9ea54af4b95c42b19dc04fa403aa0394` completed and was confirmed.
- The later YouTube attempt `c9e987c2ade94f08b351fb0fd2eda6c8` succeeded. Its SHA-256 matches both the original clip and the confirmed TikTok upload: `533c89bab226d1cdee7aaf120b91b9a640e88ce047a7998a1b9495219546fb03`. The completed-upload logs then confirm automatic cleanup of 14 local items and the source job, after both platforms were confirmed. The earlier failed attempt remains historical evidence, not an active upload.
- CDP uploads previously injected saved cookies before validating the live Chrome session. They now preserve that session by default; cookie hydration requires explicit opt-in. Capture-session reads Chrome without injecting stored cookies by default. The uploader module was replaced atomically and the backend image rebuilt while active renders continued.

## Validation and deployment

- 356 focused backend tests passed, including strict deletion proof, retained holds, cooldown, borrowed-browser preservation, cookie hydration defaults, and upload-operator recovery.
- TypeScript and the production frontend build passed.
- A headless browser against production verified queue transitions without reload and successfully read the actual backend (HTTP 200). No real upload was created by the browser test.
- Current network remains `clipforge_default`; client JSON requests use the existing direct backend URL.
- The proposed frontend host-network change was rejected by automatic approval review because it would broaden container network exposure. That change was fully reverted and was not applied. The safer existing network configuration was retained.
- The scheduler is enabled and running; the next campaign remains active without overlapping cron runs. No YouTube uploads remained queued or running at the final verification.
- Evidence and final login/upload state are saved in `upload-queue-repair-20261104.json`.

This target is resolved. The deletion reconciler, narrow classification correction, session-preserving uploader, and periodic browser refresh are deployed. Future authentication expiry still requires the account owner to authenticate; the code does not bypass Google authentication or content review.
