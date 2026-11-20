# Facebook cron: niche, sound design, and verified execution

15 November 2026. This report separates source implementation, preview builds,
live Facebook outcomes, and remaining activation/QC blocks.

## Implemented in source

- Niche: **Digital sehari-hari untuk keluarga**, researched and explained in
  [RESEARCH.md](RESEARCH.md). It is an editorial hypothesis, not a measured
  Facebook winner or a views guarantee.
- Ten grounded animated demonstrations, weighted pillar exploration, and
  avoidance of the seven most recent topics when alternatives exist.
- A labelled result preview, context, operation, and complete result. Neural
  narration and stable phrase captions share the decoded speech clock.
- Four original procedural sound accents: two taps, a movement cue, and a
  confirmation. Quiet levels, narration ducking, and a final limiter; no
  third-party music. Existing RYUUNDY watermark is retained.
- Numeric filename order and different-folder examples have explicit object
  states. Sorting no longer animates rows through each other.
- QC examines transition timestamps and complete audio coverage; very short
  audio tails merge with the preceding sample to retain sentence context.
- Exact remote verification expands truncated captions and checks the full
  caption, account owner and video. Uploads persist a pre-Post Reel baseline
  and candidate remote URLs. Ambiguous submissions reconcile read-only with
  backoff; the worker never clicks Post again to recover them.
- Normal startup verifies the creative policy version and required FFmpeg
  filters. Dependencies remain in the standard Docker build path.

## Actual Facebook result

The existing upload was reconciled through the normal verification API after
expanding its caption. No new Post action was attempted during recovery.

- Upload: `d27a9dd3518b4f01a3a9cec3a41f3ac9`.
- Remote: https://www.facebook.com/reel/1844917023309992/
- Ledger: `completed`, `upload_confirmed=true`.
- Latest account snapshot: monetization active, policy clear, bonus **1/3**,
  estimated earnings **US$0**, qualified views **0**. The snapshot was collected
  at 14:48 WIB; the live API returned it again at 16:08 WIB.
- Bonus is not awarded. It still requires the remaining qualifying Reels and
  genuine qualified views confirmed by Facebook.

See [reconciled-existing-upload.json](reconciled-existing-upload.json) and
[deployment-verification.json](deployment-verification.json).

## Rendered media and QC limitation

Real approximately 29–31 second SFX examples were rendered and fully decoded.
An initial sparse-frame audit passed before a transition defect was discovered;
that earlier result does **not** approve the subsequently changed media.
The defect was fixed, and transition evidence was added to future audits.

Subsequent independent checks did not approve a final SFX example:

- Numeric-order example: provider HTTP 422, content safety screening refusal.
- Grouping example: audio/caption mismatch on an isolated sub-second tail.
  Future sampling was corrected; this rejected source was not retried.
- Size-order and copy examples: provider HTTP 422, content safety screening
  refusal. The copy audit preserves a sanitized provider diagnostic.

Rejected media and their generated assets were retired; concise audit records
remain. No rejected source was re-submitted, routed to another model, or posted.
There is **no final approved SFX MP4** in this report. The cause of the provider's
screening decisions is not established; this is not evidence of a Meta account
restriction. Current provider: OpenRouter / NVIDIA Nemotron 3.5 Super VL free,
with actual rendered audio checked by local Whisper.

## Validation and preview

- **477 tests passed**, with 24 FastAPI lifecycle deprecation warnings.
  [regressions.xml](regressions.xml) covers Facebook, QC, cron/Long compilation,
  captions, and deployment contracts. The final run completed in 27.83 seconds.
- Frontend production preview build: `ZRn6YMIKJRAWszTD0Rm_a`.
- Preview checked at 1440, 1280, 390 and 320 pixels, dark/light themes,
  pause/resume controls, and no horizontal overflow or JavaScript page errors.
  [ui-verification.json](ui-verification.json) records the checks.
- Screenshots use mocked production activity and real account-status fixtures;
  they demonstrate the new UI, not activation of the new backend policy.
- Python compilation and `git diff --check` pass.

## Deployment remains blocked

The required deployment command was attempted:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

It exited 1 because sudo requires a password and an interactive terminal.
The live backend is healthy and its legacy Facebook scheduler is running, but
`creative_policy_version` and `bonus_priority_version` are absent. Therefore
the new niche/SFX policy and bonus-priority update are **not activated**.
The last live check also found an unrelated running production job; preserve
its checkpoint before any later standard rebuild. No running service was
restarted or represented as newly deployed in this turn.
