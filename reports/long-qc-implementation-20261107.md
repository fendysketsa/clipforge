# Automatic Long QC, 7 November 2026

The user-level Long QC operator is enabled and running in production. Backend-integrated activation remains pending Docker/sudo access.

The existing `clipforge-ai-qc` skill targets Shorts. The Long adaptation now checks rendered media and sidecar identity, rights and claims, editorial/context holds, exact output subtitles, full media decoding, audio level, representative frames around cuts, thumbnail, and opening/middle/payoff/ending audio excerpts. The model receives the evidence and returns PASS_UPLOAD, REPAIR_ONCE or DROP_SOURCE. Unavailable or incompatible AI, insufficient evidence, and contradictory responses retain a hold.

The scheduled Long review lane can opt in with `auto_qc_enabled`. Decisions persist under `backend/data/long_review_qc/` and bind to media, sidecar, subtitle, source gates, policy version and model configuration. Terminal decisions are cached; unavailable AI retries after ten minutes. At most one audit worker runs at a time. This does not audit every historical/manual Long or replace the Short QC path.

With `auto_qc_private_upload` enabled, a passing result may enter the existing YouTube queue as Private after the existing preflight passes. The upload record is persisted before worker startup. Existing/unknown remote checkpoints prevent duplicate submissions. This does not mark human signoff, enable Public publication, alter rights evidence, or delete local files. DROP_SOURCE is a rejection disposition; its `delete_source` field is a recommendation in the audit contract, not proof of deletion.

REPAIR_ONCE persists bounded edit instructions. Automatic Long recut execution is not implemented: the existing repair endpoint accepts Shorts only. A Long needing repair stays held instead of entering that endpoint or claiming a repair happened.

The initial rights-only DROP for `d14fe9c4666a441799a4033509e93df3` was superseded. The reviewer now uses the same persisted documented operator permission accepted by the upload preflight; unverified license metadata alone is not a missing-permission verdict. Explicit claims, source risks and absent permission still veto upload. The original output remains preserved for a full image/audio audit; no pass or publication is inferred from the permission correction.

Validation includes generated-media decoding/frame/audio tests, durable Private upload and duplicate protection, host-operator handoff, and targeted TikTok caption recovery. The expanded relevant suite passed 442 tests. Live local Whisper recognized the rendered Nisa opening with caption overlap F1=0.875 and mean log probability -0.423.

`clipforge-long-qc-operator.service` was enabled and started through the user's systemd manager. It reviews completed held Longs and queues a passing file through the existing live API as Private; it does not need Docker access. It yields automatically when the backend's QC policy becomes active. Request timeouts retain an unknown-outcome checkpoint and cannot cause retransmission. The user manager must be running for this host service to run.

When all today's attempts have terminal QC rejections, the host operator can request one replacement through the existing production API and immediately restore the original daily target. A durable reservation prevents duplicate requests after restart; production remains capped at three source attempts per Jakarta day. Explicit provider safety refusals become a terminal rejection, with no resubmission or alternate-provider bypass. The first legacy Long received this refusal (HTTP 422); its rejection is cached and its file is preserved. The active worker now waits for replacement `60da3eb153194ef9ac443c184bdbd8c9`, verified at 75%, rendering part 3 of 9.

Provider configuration is stored with mode 0600 in the ignored mounted file `backend/data/long_qc_provider.json`. Existing OpenRouter credentials were reused without printing them. The user explicitly approved exporting QC samples on 7 November 2026 after automatic approval review rejected the initial external-media transfer. Audio requests to the nominally free Omni model required a $0.50 account balance (HTTP 402), so the pipeline now performs audio recognition locally using the cached Whisper Medium model on CPU and sends images plus transcript evidence to a free visual model. No credits were purchased. Missing provider or local evidence keeps a hold.

One replacement Long was started using the live scheduled lane: `60da3eb153194ef9ac443c184bdbd8c9`, paired to Short `e09f658360544a76a5d8ac5e6859f69c`. Its source analysis is full-length (`analyze_seconds=null`). The daily target was restored to 1 immediately after queuing. Progress was verified at 73%, rendering story part 2 of 9. Earlier manual attempts failed because the live manual endpoint forced Creative Commons despite stored permission; this source bug is repaired but requires backend activation.

The TikTok Nisa draft caption was repaired live in the existing browser, with read-back verification and no Post click or retransmission. Click stability on background Chromium caused the failure even after transfer completed. The source fix uses verified native fill after modal dismissal and includes a single guarded pre-Post retry of the same persisted upload record. Its automatic retry hook still requires backend activation.

To move ownership into the backend and activate the durable TikTok retry/Long production fixes after existing work drains:

```sh
sudo bash /www/wwwroot/clipper/clipforge/scripts/activate-long-qc.sh
```

The deployment script waits for active work before restarting, restores the existing cron switch, verifies module hashes, and opts the Long lane into QC and Private upload. Inspect the live `GET /api/automation/viral-cc/long-production` response for `qc_vision_configured` and `qc_reviews`; an enabled policy is not evidence that a particular video passed.
