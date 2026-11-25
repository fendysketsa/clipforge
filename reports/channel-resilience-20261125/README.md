# Channel resilience — what is guaranteed, and what is not

Nothing can guarantee views, retention or a channel staying "jaya" forever.
What ClipForge can guarantee is that the studio does not damage the channel:
every automatic action is bounded, measured, and reversible through evidence.

## Invariants kept while increasing cron output

1. **No fabricated success.** Views, retention, QC approval, remote identity and
   publication are only recorded when measured/confirmed by the owning worker.
2. **Originality.** `RYUUNDY_ORIGINALITY_BRIEF` requires original characters,
   narration and meaning; no imitation of another creator's voice, style,
   character or scene, and no third-party footage/music.
3. **Single production owner.** The director publishes bounded directives and
   repairs only through existing guarded owners; it never renders or publishes.
4. **QC and rights gates.** Long output needs `PASS_UPLOAD`; if Long cannot be
   produced, the existing compilation fallback still requires Long QC. Facebook
   keeps `story_scene_sha256` / `manifest_sha256` evidence.
5. **Publication holds and identity.** Operator holds, retry budgets, daily
   limits and remote identity checks are preserved on every path.
6. **Measured loop.** Retention and performance are read from platform data and
   compared only against comparable topics/age; no prediction is claimed.
7. **Monetisation readiness, not income promises.** Original audio/visual assets,
   stable captions and the existing YouTube/Facebook monetisation preflight are
   preserved, so eligible videos can be considered for ads. Revenue depends on
   the platform and audience and is never fabricated or guaranteed.

## Output changes in this round

- Daily plan total **23 → 30** (`scheduled_short` 17 → 24, private 4, Long 2),
  with the daily upload cap raised to 30 and seven spaced public Short slots.
- Cron public Shorts raised to **7/day**, sourced only from candidates meeting
  the existing 1K-view floor; niche rotation uses `auto` with a 35% performance
  winner share so varied topics keep appearing.
- Long keeps a stronger intent than Short (motif → development → evidence →
  resolution) and uses the existing QC-preserving compilation fallback when a
  true Long is not possible. `format_fit` separates Long-worthy stories from
  Short-worthy moments.
- `RYUUNDY_ORIGINALITY_BRIEF` is part of the Long editorial brief: original
  characters, narration and meaning, no imitation, no third-party footage.

## Verification standard

Backend suite, focused cron/long/editorial tests, frontend checks, deployment
contract and live health are run before any change is claimed active.
