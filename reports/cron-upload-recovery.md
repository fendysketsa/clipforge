# Cron upload recovery and quiet YouTube status checks

Status: source changes validated; production activation is pending Docker/root access.

The production API reported scheduled run `9c52d940a4fa42cb81bf70c1e9325478`
still running in `social_upload`, last updated at 16:03 WIB on 5 November 2026.
Its source job `051bf76060fb467c943795155a3f2dbc` and local outputs no longer
exist. Both upload queues are idle. TikTok record
`08a5812983e64132add4e55de33de57d` is confirmed; no YouTube upload record for
that job was found. The parent run still occupied the scheduler's active slot.
The precise blocked operation in the old worker could not be inspected because
the running container requires root access.

The repair:

- Retires upload-phase cron runs after 15 minutes only when all child jobs,
  active upload records, live subprocesses, and ongoing upload creation are absent.
- Retires missing upload checkpoints loaded after a restart before capacity
  calculations, preserving authoritative remote successes in the parent snapshot.
- Prevents retired workers from reviving the run or queueing further uploads.
- Stops waiting immediately if an expected upload record disappears; holds the
  unknown remote outcome instead of retrying it automatically.
- Keeps scheduler maintenance responsive while the YouTube creation lock is busy.
- Allows fresh discovery after an expired checkpoint even with upload retries
  disabled and the normal cycle set to 24 hours. Capacity and daily caps still apply.
- Reads YouTube deletion evidence through HTTP with an independent cookie jar,
  without opening a Chrome tab. Only exact-ID, explicit uploader-deletion evidence
  can release a remote reserve.

Validation: 147 focused tests passed; Python compilation, embedded activation
script Python compilation, shell syntax checks, and `git diff --check` passed.
An offline replay of the observed persisted records released the stale active
slot, retained the confirmed TikTok record, and left the production state files
unchanged. See `cron-upload-recovery-check.json`. No production render or
post-deployment scheduler recovery has been verified yet.

Activate both fixes:

```bash
sudo bash /www/wwwroot/clipper/clipforge/scripts/activate-cron-upload-recovery.sh
```

The script builds the durable backend image, pauses future cron launches,
requires idle render/upload queues, permits restart recovery only for old upload
runs whose jobs are absent, and checks container subprocesses before restarting.
It stages the two changed modules in the existing container, retaining its exact
environment and mounts. It then restores the previous cron switch and verifies
runtime hashes, retirement of the stale run, and a new active run or next run time.
Successful activation writes `cron-upload-recovery-activation.json`.

The activation attempt from this session stopped before any changes because
`sudo -n` returned `sudo: a password is required`.

## Activation guard follow-up, 6 November 2026 WIB

The screenshot's image build succeeded. The old activation script then exited
immediately on the first queued/running row, restored cron, and required another
manual attempt. A live read confirmed running source job
`95bae767ceae44fa87aa97289ea7a2bc` and campaign
`5057808348684055836f08bddfc91cdf`; neither was safe to interrupt.

Activation now pauses future cron launches and waits up to six hours, reporting
blocking job IDs, stages, and update times every 15 seconds. It checks queues,
campaigns, and media/downloader/uploader subprocesses before staging and checks
again before replacing modules and restarting. Orphan recovery remains limited
to the existing scheduled upload-checkpoint conditions. A timeout, error, or
interruption restores the original cron switch.

The recovery wrapper forwards options. After a successful image build, use:

```bash
sudo bash /www/wwwroot/clipper/clipforge/scripts/activate-cron-upload-recovery.sh --skip-build
```

`--skip-build` verifies both patched module hashes in the built image before
pausing cron, and again after waiting. If the image differs from current source,
activation stops and asks for a normal build. `--wait-seconds N` changes the
six-hour limit; `--no-wait` performs the previous immediate safety check.

Validation: 38 deployment-guard tests passed, including real shell exit-trap
tests for both enabled and disabled cron states. Shell syntax, embedded Python
compilation, and whitespace checks passed. A read-only live guard check correctly
blocked on the running source job without changing cron or container state.
The additional application test run could not collect because this local Python
environment lacks `fastapi`; the earlier 147-test result above belongs to the
previous validation session. Runtime activation remains pending: direct Docker
access was denied and `sudo -n` required a password.

The subsequent idle-queue attempt exposed a Docker compatibility bug in the
guard: `docker top ... -eo args` omitted the PID column required by the daemon,
which returned `Couldn't find PID field in ps output`. The guard now requests
`-eo pid,args`. An executable-boundary regression reproduces the PID requirement
and verifies that renderer, uploader, and downloader rows are still detected.
All 39 deployment-guard tests passed. A live API check after the failed attempt
confirmed `enabled=true`, `scheduler_running=true`, and a next-run timestamp;
the error did not leave cron paused. Live execution of the corrected Docker
command still requires a sudo password. Only the host-side guard and its test
changed for this fix, so the built backend image can be reused.
