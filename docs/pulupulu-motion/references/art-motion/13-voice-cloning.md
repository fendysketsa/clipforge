# 13 · Voice-over and voice cloning

For the unified entry point and configuration see the [optional voice guide](capabilities.md); for interface details see the [voice-over API spec](voice-api.md).

An existing recording is reused first; when new voice-over is needed, pick a system voice or an already-bound cloned voice according to the user's configuration. `scripts/art-motion/koubo.py say/train/voices` keeps the old call entry point and shares the same configuration outside the install directory with `scripts/art-motion/capabilities.py`.

Each `say` produces exactly one take and does not automatically run three candidates or ASR. Re-records keep `--fit/--match`, and once done you still verify the lines, proper nouns, joins and subtitles. The specific model, speaking rate, voice and licensing are not hard-coded in this document.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
