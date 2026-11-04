# Cron investigation — 4 November 2026

## Observed runtime

Evidence snapshot: `cron-investigation-20261104.json`, checked at 12:34 WIB.

- The host backend is healthy. Cron is enabled and its scheduler is running.
- Campaign `e78910eb52d048bd8c1da3b4b945ca4a` is processing source 3/6. The source download was still growing at 12:31 WIB, then progressed to CUDA transcription by 12:34 WIB. It was not a stalled cron worker.
- The screenshot identifies job `10e4939544f1442eb64bcbebc9a4ab82`. Its campaign checkpoint was held for advertiser-suitability review. The render also had an exposure warning. Marking a clip reviewed does not erase its original render measurement.
- The screenshot clip subsequently completed YouTube upload at 12:25:01 WIB (`acvluAUrObI`) and TikTok upload at 12:25:12 WIB. Both application records have `upload_confirmed=true`. The YouTube publication is scheduled for 5 November at 16:00 WIB; upload completion is distinct from public release. No independent Studio verification was performed in this investigation.
- Scheduled YouTube backlog: 10/11; new Private reserves: 1/5. These are intentional capacity controls.
- Historical campaign logs also contain missing checkpoints after cleanup/restarts, a YouTube login failure, an upload timeout, and rejected partial media. These are separate historical failures, not proof that the current scheduler is stopped. Existing checkpoint recovery and upload tests cover those paths.

## Defects corrected

1. Scheduler status previously inferred missing permission from a disabled upload flag. That flag can also be disabled by capacity, daily targets, browser readiness, or paired-Long settings. Active campaigns could consequently show a false permission hold. Status now reports those conditions separately and prioritizes the active campaign.
2. The results panel treated every failed visual measurement as a blocking hold, even when its audit sidecar explicitly set `blocking=false`. The API now exposes that field, including rehydration of existing jobs, and the panel distinguishes visual notes from blocking decisions. Missing audit data remains conservative. Context and upload-preflight failures still hold the clip.
3. Reconciliation and schedule-calculation exceptions could escape the main scheduler loop and stop its thread. A guarded cycle now logs the error and retries after 30 seconds. Regression tests inject errors at four different steps and verify that a second cycle executes.
4. Forced-CDP readiness now checks the live CDP connection, including when the ordinary CDP preference is disabled.

## Validation

- 105 cron, scheduling, recovery, and regression tests passed.
- 281 YouTube/TikTok upload tests passed.
- Frontend TypeScript checking passed.
- Production frontend build passed from an isolated temporary copy using webpack. The workspace `.next` directory contains files owned by another account, so it was not overwritten.
- Python compilation, shell syntax, and `git diff --check` passed.
- The full unrelated API suite was not completed: the local environment lacks OpenCV. The relevant cron and upload suites above completed successfully.

## Deployment status

**Activated and independently verified on 4 November 2026 at 14:34-14:35 WIB.** Evidence: `cron-health-activation-20261104.json`.

- Backend health is `ok`; frontend HTTP response is 200.
- The live API exposes the new `render_qc_blocking` field. A deployed frontend JavaScript chunk also contains the corresponding logic.
- Cron is enabled and its scheduler is running. The false permission warning is gone.
- Current wait is intentional: 11/11 scheduled videos and 5/5 new Private reserves. Next scheduler check is **16:01 WIB**, after the next scheduled release frees capacity.
- The former campaign completed naturally at 14:34:04 WIB with **6 verified uploaded batches**, 1 manual-review hold, and 2 failed source attempts. No forced cancellation was performed.
- The host activation and waiting processes have exited. The previous temporary administrator-access blocker is resolved.
- Runtime flags, paired-Long settings, and upload limits match the pre-activation configuration. Public cadence remains 7 releases/day with a 2h15m minimum gap.

The user ran `sudo bash scripts/activate-cron-health-fix.sh` on the host. The script built images first, prevented new campaigns, drained existing work, recreated backend/frontend, and restored the original cron switch. No manual reupload was performed during verification.

## Progress-counter observation

The old campaign replaced rejected sources while pursuing its configured target of six successful batches. Its label clamps the source index to the target, so `6/6` can remain visible while replacement attempts continue. Nine source attempts were ultimately recorded. This counter behavior remains separate from the scheduler-liveness and QC-status changes in this deployment; it must not be interpreted as proof that the campaign has finished.
