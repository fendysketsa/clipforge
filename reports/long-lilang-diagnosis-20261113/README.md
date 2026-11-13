# Long “Lilang” diagnosis — 2026-11-13

The render is completed: 293.121875 seconds, 1920x1080, video and audio streams,
252284147 bytes. The file still exists. No matching YouTube upload record was
found. TikTok is already confirmed Only you at its exact persisted remote URL.

The red toast in the screenshot is a separate HTTP 502 from the frontend API
proxy: “Backend API is not reachable: All promises were rejected”. The backend
health endpoint itself responds normally. The request did not establish a
YouTube upload record for this Long.

The persisted Long QC audit also matters: status=reviewed,
decision=DROP_SOURCE, upload_allowed=false, context_safe=false. Its evidence
records an explicit provider content-safety refusal, so semantic/visual
approval is unavailable. This does not identify a particular defective scene
or prove a technical encoding failure. The existing provider refusal was not
retried, its decision was not overridden, and no new upload was submitted.
The existing TikTok upload was left unchanged.

The API previously displayed youtube_upload_ready=true while independently
reporting the Long QC refusal only for TikTok. Consequently the UI could show
“QC otomatis menunggu” and offer YouTube upload despite the recorded decision.
The repair shares the persisted Long review hold across both platform
preflights, uses the actual reason in production_qc_brief, and prevents the
ordinary correctness checkbox from erasing a terminal QC hold. Non-review
Longs and Shorts retain their existing preflights. Existing confirmed remote
records and source files are preserved.

Validation: 317 tests passed across Long QC, YouTube uploads, serialized
submission reconciliation and playlist routing. New regression tests cover a
terminal rejection with is_correct=true and the formerly misleading readiness
fields. Python compilation and whitespace checks passed.

These source changes are not confirmed active in the backend container.
Noninteractive sudo still requires a password; frontend proxy 502 is also
still observed. See diagnosis.json for the exact media/QC evidence. No
production success or upload for this Long is claimed.
