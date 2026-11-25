# Voice-cloning model check

`selection` in the platform record holds the model the user chose by ear, the speech rate, the voice-registry reference and the upgrade preference. Before calling that platform, run `voice_review.py --provider <platform>` to read the listening selection; a model specified explicitly for this call overrides the stored choice. Periodic updates preserve `selection`; official candidates must not overwrite a personal choice. Without a general vendor adapter, keep using the verified project call path that the record points to, and do not describe a query tool as a synthesis tool.

Used for the pre-cloning check and for the periodic inspection the user has authorised. The record lives in `voice-model-review.json` in the same directory as the actual user configuration of `capabilities.py`; do not commit private configuration.

Each platform is stored separately:
```json
{"providers":{"qwen":{"checked_at":"2026-10-15T12:00:00+08:00","models":[],"sources":[],"findings":"official list and account-level callability recorded separately"}}}
```

`checked_at` is updated only after this run successfully read and checked the official material. On failure, record `last_attempt_at` and `last_error`, keeping the old success time. `sources` keeps the source URL, the access date and the relevant fact; `models` records the exact ID, the purpose, the official support status and the measured status, and does not lump ordinary TTS, voice design or real-time conversation in with voice cloning.

For Doubao, check the Volcengine Doubao Speech voice-cloning and synthesis docs first; for Qwen, check the Bailian speech-synthesis model list, the voice-cloning guide and the API docs first. Leaderboards serve as candidate leads, not as evidence of a public API ID or of account availability. Confirm whether old and new endpoints have migrated, the reference-audio requirements, the pricing and the model deprecations; a search that finds nothing does not mean nothing has changed.

The weekly check reads official material and local configuration only, updates the record, and reports additions, deprecations or changed limits. Never top up credit, retrain, switch defaults or repeat paid tests on your own initiative. After the user authorises a test, separately record the requested model, the receipt, the audio acceptance and the listening feedback; recommend changing the default only when actual listening and reliable call evidence are sufficient.

Source: on 2026-10-15 the user asked for a weekly check of Doubao/Qwen updates, and for the current model and the last check time to be reported at every cloning. If official material conflicts with an old record, correct the old conclusion and keep the basis for the correction; keep personal listening choices separate from public capability.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
