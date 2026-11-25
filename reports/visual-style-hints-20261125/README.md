# Visual style hints from pulupulu-motion (25 Nov 2026)

## Decision

The vendored `docs/pulupulu-motion` skill is useful as **craft vocabulary**, not
as a renderer. Its HTML+GSAP/`om` pipeline was not installed: ClipForge keeps
Motlab/Remotion, their QC evidence chains, and the single production owner.

## What was adopted

`backend/visual_style_hints.py` — ten original, technique-only art-direction
profiles (flat geometry, paper cut-out, watercolour wash, ink line, sparse
halftone, soft flat, neon grid, pixel blocks, warm key light, simple mosaic).
Each carries a short prompt sentence, a suggested palette and one motion hint.

Boundaries, enforced in code and tests:

- no artist, franchise, named character, sample frame or composition is copied;
- `scope='prompt_hint_only'`, `renderer_neutral=True`, `rights_reference=False`;
- hints are bounded (≤240 characters) and deterministic per topic;
- no rights, QC, publication or measurement claim is made.

## Where it is wired

- `cron_long_strategy.VISUAL_DIRECTION_BRIEF` → appended to `LONG_EDITOR_BRIEF`
  (Long editorial/model prompts only).
- `ryuundy_reference_catalog.editorial_brief()` → prompt-only brief used by
  RYUUNDY cron perspectives and Long review.
- `facebook_stories._art_direction_hint()` → appended to the model system
  message in `author()`. **Not** added to `plan['story']`, so `plan_sha256`,
  `story_scene_sha256` and `manifest_sha256` are unchanged.
- `GET /api/runtime/visual-style` → exposes the catalogue for agents/UI.

## Why not deeper

Adding keys to Facebook `plan['story']`, changing `motlab/story-scene.mjs`, or
touching renderer palettes would alter QC/evidence hashes or renderer-owned
behaviour. That needs a separate, explicitly authorised change.

## Verification

Focused tests cover the catalogue, deterministic selection, prompt bounds,
forbidden artist names, brief containment and the endpoint; the full backend
suite is run before deployment.
