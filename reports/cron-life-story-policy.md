Cron life stories (version 1)

Scope: scheduler-owned RYUUNDY episodes only. Manual story generation, source
clipping, News, Facebook, Private Shorts and Long production retain their rules.

The existing scheduled-Short budget includes at most two original-story
attempts per Jakarta day. The second attempt becomes eligible after six slots
are occupied. Failed generation also consumes the experiment attempt budget.
There are no additional daily production slots.

`backend/data/cron_life_stories.json` is an atomic, private reservation ledger.
It preserves run and child job IDs, topic cooldowns and script identity across
restarts. Corrupt ledgers stop this experiment without resetting reservations.
The existing campaign uploader owns submission, duplicate checks and cleanup.

The six-scene fictional script has a concrete problem, decision, action,
consequence and resolved ending. Narration is validated before paid media work;
recent script similarity prevents recycling. Generated characters and images
are original. The visual recipe uses illustrated scenes and camera movement;
it does not claim character/body animation. Caption phrases retain native TTS
timing, and final render, narration, opening and provider-license gates remain
mandatory. Failed gates preserve the output instead of submitting it.

Configuration, passed by the normal Compose command:

- `AUTO_VIRAL_CRON_LIFE_STORY_ENABLED=true` (Compose default).
- `AUTO_VIRAL_CRON_LIFE_STORY_DAILY_LIMIT=2` (bounded to zero through two).
- `AUTO_VIRAL_CRON_LIFE_STORY_PROVIDER_RIGHTS_EVIDENCE`: operator-supplied
  reference covering the configured image, voice and other provider terms.
  Source-video permission is not substituted for this evidence. Until supplied,
  this experiment reports `waiting_for_provider_rights`; regular cron continues.

Read status at `/api/automation/viral-cc/life-stories` or the `cron_life_story`
field in the cron schedule. No credentials or proof text are exposed there.
The Docker build manifest includes the module, and backend readiness verifies
the cron-only contract. Deployment uses the repository's standard Compose
command; there is no separate activation script.
