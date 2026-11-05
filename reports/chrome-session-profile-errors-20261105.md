# Chrome login profile error diagnosis — 5 November 2026

## Verified cause

- X11 exposed six windows titled `Profile error occurred`, all belonging to
  Chromium PID 10063 inside the backend container (host PID 108300), plus its
  parent YouTube window. These were error dialogs from one helper, not six
  independently authenticated accounts.
- The helper was `youtube_uploader.py login --auto-close --timeout 600
  --chromium-user-data-dir /app/data/youtube-playwright-profile`. It ran as root.
- Desktop Chrome was already using the corresponding host directory
  `backend/data/youtube-playwright-profile` as the desktop user. The helper
  opened the same profile using backend Chromium and a different user/keyring.
- A metadata-only scan at depth two found 106 root-owned profile files and 360
  owned by desktop UID 1000. `Local State`, `Default/Preferences`, and Singleton
  links were among the root-owned paths. Cookie values were not read or copied
  during this diagnosis. No database corruption verdict was made.
- CDP ports 9333 and 9444 returned the identical browser debugger ID. Source
  code had treated shared mode as true only when the two endpoint URL strings
  were equal. Thus two forwarding ports to the same browser bypassed the
  shared-browser protection. The YouTube login path could launch another
  persistent-profile browser rather than attach to the existing session.

## Live action and verification

- Both platform upload queues were idle before intervention.
- Stopped only the backend YouTube login helper through
  `POST /api/youtube/login/stop`.
- The desktop browser debugger ID was unchanged afterward.
- A fresh X11 inspection found **zero** `Profile error occurred` windows.
- Both existing pages responded to read-only CDP evaluation: YouTube Studio
  dashboard at the configured channel URL, and TikTok Studio content page.
  This checks page health; it is not evidence of a new completed upload or a
  complete TikTok account-identity audit.
- No browser profile, stored session, or cookie was deleted; the desktop
  browser and active rendering campaign were not stopped.

## Prepared source fix (not deployed)

- Explicit shared-browser mode now supports different forwarding endpoint URLs.
- Shared mode selects CDP for YouTube and disables direct persistent-profile
  upload and storage-state-first precedence.
- Login and profile-check commands attach through capture-session with
  `--no-hydrate-storage-state`, preserving the active browser session.
- Shared-mode reconnect does not restart the healthy desktop browser.
- Repeated login clicks cannot start another helper during the gap before
  `Popen` becomes available.
- Raw YouTube CLI persistent-profile login/check/upload also rejects shared
  mode before launching Chromium.

Validation: 288 tests passed across `test_shared_browser_profile.py`,
`test_tiktok_uploads.py`, and `test_youtube_uploads.py`; Python compilation and
`git diff --check` passed.

## Remaining runtime work

Backend source changes need a safe rebuild/deployment. Root-owned files in the
desktop profile still need their ownership restored to the profile directory's
desktop owner. Docker/root access is unavailable to this session, so neither
deployment nor ownership repair is claimed complete. Until deployment, the old
login path can reproduce the problem if invoked again.

An operator can restore only root-owned entries without following symlink
targets, after ensuring no backend persistent-profile helper is running:

```bash
sudo chown -R -h --from=0 "$(stat -c '%u:%g' backend/data/youtube-playwright-profile)" backend/data/youtube-playwright-profile
```

The existing `scripts/activate-cron-health-fix.sh` provides build-first,
drain-before-recreate activation while preserving current container settings.
It requires root. It does not itself verify the profile ownership repair.

## Subsequent live uploader recovery

The initial page-health check above did not establish that the uploader used
that authenticated browser. A subsequent failed upload exposed this gap.

- Switched the running backend through `/api/youtube/upload-mode/live-chrome`
  to the existing Chrome at port 9333. This runtime change did not need Docker
  access or stop an active render.
- `/api/youtube/login/once` then used the real capture/identity-validation path
  and returned `ok=true`, `session_ready=true`, `login_required=false`, with
  channel `UCAOZF9Qzj6DYoXKtLnP4UUQ` explicitly verified. Cookies were exported
  from the live browser without hydrating old cookies into it.
- Saved matching CDP-first/force settings in local `.env`, disabling direct
  persistent-profile preference and permission for future deployments.
- Retried the failed YouTube clip from job
  `8e63a32073204cdebb6b6a0ae4bffd67`; original failed record
  `eff332b486b349859e26a20afd544784` had no remote video checkpoint.
- New upload `05ecaab9c0a74e53b0e6304bd9967775` received remote video ID
  `mN0TG4O9Puw`. Studio accepted the final Schedule action, but an additional
  post-save visibility-control wait timed out and incorrectly left the local
  record failed. No file was selected or transferred a second time.
- Opened the existing video's edit page and verified its saved native schedule
  model: year 2026, zero-based month 10, day 6, time-of-day 49500 seconds,
  timezone index 0, browser timezone Asia/Jakarta. This is **6 November 2026,
  13:45 WIB**, matching the original requested schedule.
- Requeued verification of the **same** record and remote ID. It finished
  `status=completed`, `upload_confirmed=true`, `error=null`, URL
  `https://www.youtube.com/watch?v=mN0TG4O9Puw`.
- TikTok record `230d92dba32b4eeba62056da56a8dea5` remained the sole record for
  the clip and was not re-uploaded. Existing cross-platform cleanup applies
  only after both platforms are verified.

The runtime login/upload path is recovered. The prepared code guards and
root-owned profile-file repair still have the deployment/access limitations
described above; a runtime mode switch is not a code deployment. The post-save
30-second visibility-control timeout is a separate remaining robustness issue.

## Restart persistence repair

The next desktop browser start again showed sign-in pages. The old shared
profile still contained root-owned `Local State` and `Default/Preferences`;
its cookie database mixed `v10` and `v11` encrypted entries. The desktop
keyring was running and unlocked. This is stronger evidence of a mixed-writer
profile problem than of an ordinary expired-cookie-only incident.

Changes actually applied without Docker/root access:

- Created the separate `backend/data/social-chrome-profile` for desktop Chrome
  only. All 1,036 files found in the first ownership scan belonged to desktop
  UID 1000, including Local State, Preferences, and Cookies. Its persisted
  cookie database contained 69 `v11` entries and no `v10` entries at that check.
- Updated local `.env` so the desktop service uses that new profile and future
  backend persistent-profile fallback uses a different directory. Disabled
  automatic cookie hydration for both platforms in the deployment settings.
- Restarted only the desktop browser service while both upload queues were
  idle; active rendering was not stopped. The cron switch was restored to its
  observed pre-migration value (`false`).
- Retained the last verified exported session in a private recovery directory
  and attempted controlled recovery into the new profile. Google required
  owner identity verification; this requirement is not bypassed.
- Retained the complete legacy mixed-user profile at
  `backend/data/session-recovery-20261105/legacy-mixed-user-profile` and replaced
  the obsolete shared profile path with a private explanatory marker file.
  The old backend therefore cannot create another persistent browser at that
  path. No old browser profile was deleted.
- Added a guard to the bind-mounted launcher: Docker must attach to the host
  CDP browser and cannot launch the shared profile. The host launcher rejects
  critical profile files owned by another user and no longer deletes live
  Singleton locks. These launcher changes are already used by the host service.

Additional defects found and prepared for deployment:

- TikTok authenticated app-context identified the viewer as `titikbalikislami`,
  although its icon-only navigation/profile panel had not rendered a matching
  profile link. The CLI now reads only the authenticated `webapp.app-context`
  viewer identity, never the public `webapp.user-detail` identity.
- The API session checker must not fall through from a live authenticated but
  still-loading page to an unauthenticated isolated context and quarantine the
  previously valid state. That transient path now keeps the session.
- YouTube API capture defaults now explicitly preserve live cookies, matching
  the CLI default.

Validation after these changes: **306 tests passed**. Shell syntax, Python
compilation, Compose configuration, and whitespace checks passed. The reviewed
root command `scripts/activate-shared-browser-session-fix.sh` activates both CLI
modules atomically and rebuilds the image without stopping active render
workers. It requires Docker/root access; it has not been executed by this
session. API-module changes load on the next safe backend recreation.

Completion still requires the owner's Google flow to reach the Studio
dashboard, then a real browser-restart persistence check and uploader identity
validation. An owner response saying login is finished is not sufficient while
the observed automation tab remains on Google's password challenge. No claim
of restart-persistent Google login is made before that check succeeds.

## Final verified result

The remaining steps above have now completed:

- Desktop authentication authorized activation with `pkexec`. Both uploader
  CLI modules were atomically installed and SHA-256 verified in the running
  backend. `api.py`, `news_hot.py`, and `youtube_playlists.py` were also staged
  and hash-verified for its next safe restart. The running API process and
  active render were not restarted.
- The backend image build completed. The final image manifest list is
  `sha256:d08e01efcfe860db0d60a12e032547cd42a20d7d67252d1f7f2e0c92a8f0ec70`.
- The TikTok CLI now ignores the legacy hydration flag in shared-browser mode,
  so a stale deployment setting cannot overwrite the live login. Dedicated,
  non-shared mode retains its explicit opt-in restore behavior.
- The owner completed Google's Next step directly. Studio then reported the
  expected channel, and the uploader returned `ok=true`, `session_ready=true`,
  `login_required=false`.
- With both upload queues idle, restarted the desktop Chrome service. Observed
  a new browser debugger ID. No cookies were imported after this restart.
- The expected YouTube channel loaded from the persisted profile. The real
  uploader session check again returned success without requesting login.
- TikTok's real production session check also returned `ok=true` for the
  configured account after the same browser restart.

**Both platform logins survived a real browser restart.** Evidence is saved in
`browser-session-restart-verification-20261105.json`; installed-module hash
proof is in the private runtime-data directory. The activation log is
`shared-browser-session-activation.log`. Final relevant validation passed
**308 tests**, with shell syntax, Python compilation, Compose configuration,
and whitespace checks also passing. No new video was uploaded for the session
test and the active render was preserved.

An earlier agent attempt to press Google's Next button was rejected by automatic
approval review because auth-form submission lacked explicit permission. It
was not executed. The owner chose to press Next personally; that safer path
completed authentication before the restart test.
