# Voice-over whole films and lessons flowing back

This page collects the general method for making a whole voice-over film; it does not include the author's private feedback files. Segment interfaces are still in no. 09, characters in no. 10, the long-scroll demo in no. 11.

## From voice-over to picture

Confirm the script, the voice-over and the word-level timing first, then do the style table and the highlight list. Hang actions on keywords (like `TM.cue` in the reference code); do not hard-code every timestamp. The camera follows the content's bounding box; the subtitle band is a constraint in camera space, and must be cleared even when pushing in.

Whiteboard drawing accumulates on the same large canvas; the first stroke of a block is synchronised with the camera arriving, and within a block you write to the speech rate. After creating the board with `const B = DG.board(...)`, call rectangles as `B.line(points, {smooth:false})` so that the smoothing spline does not bulge them into ellipses. Reading time for a full list counts from the moment the last item finishes appearing; drawing time must not be counted as readable dwell.

Vox collage establishes objects, relations and camera first, then adds paper texture and ornaments. For explainer films, plan the different layouts and shot scales up front; moving the presenter around in post cannot rescue monotonous coverage.

## Acceptance and freezing

`qa.py` provides determinism, efficiency, motion, smoothness and text-framing hints. Framing detects text clipping, overlapping text, the subtitle band and near-blank areas; decorative large type and the like can trigger false positives, so look at the corresponding frame. For films on a light background, use `subzone_gate.py` to additionally check graphics entering the subtitle band; that dark-pixel threshold does not apply to textured backgrounds.

Before delivery, an agent that did not take part in production reviews the film independently — at least two for a long film. Record the timecode, root cause, change and re-verification for each issue; keep regressions of old issues separate from newly found ones. Accept against the specific issue; do not chase an overall score. If the same class of issue survives three consecutive rounds and both fixes have failed, go back to the asset or the engine capability; a problem originating upstream in the script goes back to the script.

Once the user has chosen, freeze code, timeline, mixing and subtitles together. Keep the candidate cut and the frozen version inside the project; do not overwrite them without confirmation.

## How lessons flow back into the skill

Each round records phenomenon → root cause → fix → verification → where it belongs. Style-specific problems go into the matching grammar card, cross-style methods into no. 09, character methods into no. 10, and anything machine-measurable into QA. Recurring traps are distilled into pre-flight checks; once a trap becomes an engine capability, the written rule shrinks. After a change, have an independent agent verify it and write it into the CHANGELOG.

A project's private feedback, personal image prompts and unreleased assets stay inside the project; the public skill takes only reusable method and the necessary evidence.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
