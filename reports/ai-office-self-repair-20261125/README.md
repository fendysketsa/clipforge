# AI Office: self-repairing director (25 Nov 2026)

## Goal

Make the studio's "Pimpinan" an active brain: notice a blocker, send the
existing owner to fix it, keep a durable receipt, and show the repair on the
3D floor — without creating a second production owner or bypassing QC.

## Pipeline verified end to end (wiring, not forced publication)

| Path | Zero → upload chain |
| --- | --- |
| Short | `POST /api/jobs` / Telegram `/clip` / cron → `run_job()` → `clipper.py`: source → download → transcript → candidate selection → MP4 + sidecar → `completed` → YouTube/TikTok upload record → browser uploader → `UPLOAD_CONFIRMED` + remote identity. |
| Long | Same front half with `highlight_5m` → `export_compilation()` 16:9 → Long QC (`long_video_qc.audit_long()`) must return `PASS_UPLOAD` → Private/TikTok upload; `REPAIR_ONCE` and holds stay local. |
| Facebook | `POST /api/facebook/jobs` or autopilot originals → 25–55 s render → `facebook_api.qc()` gate → `enqueue_media()` → `facebook_browser.upload()` → `upload_confirmed` + remote verify; ambiguous Post ⇒ `needs_review`, never a blind repost. |

All ledgers and browser identity live under `backend/data` (bind-mounted), so
they survive `docker-compose --force-recreate`.

## What the director brain now does

- Observes incidents (`ai_office_incidents.detect`) every 30 s.
- Delegates only to existing guarded owners: cleanup, missing scheduled
  uploads, upload verification, bounded TikTok pre-Post retry, Facebook
  recovery, supported cron, and worker supervision.
- New: an unconfirmed upload with no remote identity is reconciled by the
  existing read-only attention owner instead of being left manual. It does
  **not** replay a Post or mutate the upload record.
- Access/login failures remain `needs_operator`; exhaustion, rights, QC,
  publication holds, and retry budgets are never overridden.
- Writes a bounded, durable `repairs` ledger (24 entries) with the delegated
  action and the owner's real summary. Snapshot exposes `active_repair`,
  `repair_count`, and capability `autonomous_repair`.
- In the 3D office, a live blocker overrides the routine patrol: the director
  walks to the affected department and his bubble shows the real repair
  summary. When the blocker clears, the normal round resumes.
- Every colleague's position now follows their **real worker state and stage**
  (`officeMotionFromWork`): transcription → reading at the desk, QC/discovery →
  task board, upload/distribution → coordination, repair → notebook, queued →
  task queue, blocked → meeting room, idle → lounge. The time-based routine is
  only a fallback when a department has no live work yet.
- The backend now publishes a machine-readable `stage_key` for each work item,
  so the UI maps the worker's own stage instead of guessing from a translated
  label.
- Fresh UI: a live work board with per-department cards, real progress meters,
  state chips and a director-focus line; a live 3D scene caption, pulsing active
  avatars, and animated meters. The 3D stage now has a glass control layer
  (live hero, activity bars, room dock), a subtle grid, and a floor glow under
  the colleague whose real worker stage is active. Every value comes from the
  observed snapshot; stale or unavailable data is labelled honestly.

## Safety boundaries

`no_parallel_production_owner`, `publication_gates_preserved`,
`safe_delegate_only`, and `operator_settings_preserved` remain true and are
checked by `deployment_runtime.backend_contract`. No QC approval, remote
identity, rights evidence, or publication success is inferred by the director.

## Verification

- Backend focused: `test_ai_office_incidents.py`, `test_ai_office_director.py`,
  `test_ai_office.py`, `test_activation_snapshot.py`, `test_compose_deployment.py`.
- Frontend: typecheck, all Node tests, production build, deployment health.
- Deployed with the exact standard Compose command; `/api/health`, `/api/ai-office`
  and `deployment.json` verified after recreation.

Note: this verifies that every stage is wired and guarded. It does not force a
real clip to be published — publication still depends on source rights, QC,
operator holds, and the platform's own confirmation.
