# 39_piero · Piero: geometric order and clear volume

Status: research recipe + single-scene engineering trial; established and implemented on 2026-10-15. `scenes/39_piero.js` is included, run with `render.py --film style_studies --solo 39_piero --from 0 --to 6`; it has not passed style fidelity or cross-scene verification, so it cannot be upgraded to a mature style on that basis.

## First checks before you start

Read [cross-scene style distillation](../15-style-transfer.md) first, then this card. The works are for comparing visual language; characters, objects, composition and camera are not carried over directly. The stable features below are research generalisations, and the implementation and migration plans are hypotheses awaiting verification; do not pass them off as official parameters or as capability already tested.

## Scope

Primarily Piero della Francesca's proportions, volumes and light relationships; the material difference between tempera and oil painting is kept.

## Transferable visual language

- Form: the large shape is established first; head-and-body, drapery and any new prop all have a concise and complete volume.
- Space: proportion, interval, perspective and negative shape constrain one another; order does not mean forced centred symmetry.
- Colour and light: clear, even light and restrained warm-cool; saturation varies with the work and the medium, with no fixed cream filter.
- Edges: the junctions of the main forms are clear, detail submits to the overall measure, and aimless broken strokes are rare.

## What changes with the brief

Colonnades, biblical figures and static poses are not mandatory; "stillness" must not force the action to slow down.

## How it differs from neighbouring styles

Unlike Raphael's supple groupings and sightline connections: here you look first at the intervals between forms, the geometric proportion and the even light.

## Starting point for a build (to be verified)

Block out the proportions and negative shapes of the new scene first with low-detail masses, check the perspective, then model and colour. Characters moving fast must still keep their form from falling apart and their occlusion readable; pure code starts from geometry and lighting, and characters still follow the character rules.

Action speed, frame rate, camera and score are decided by this narrative; do not equate a quiet mood with slow motion. Engineering integration follows the [style author spec](../08-style-author-spec.md), and the engine id is registered only once the new renderer actually exists.

## Cross-scene verification prompts (not a fixed template)

- One person chasing a train in a metro station: fast action does not mean breaking the order of proportion.
- Household appliances of different shapes on a dining table: check the volumetric relationships without relying on classical subject matter to be recognised.
- Maintenance work in a space greenhouse: no reuse of the original's colonnade; check the light and the space.

Pick tests across different subject matter / spatial scale / subject type; running the whole set every time is not required. Record still-frame and motion acceptance separately, and keep marking anything not covered as to be verified.

## References and the limits of the evidence

- [The Baptism of Christ: tempera and geometric relationships](https://www.nationalgallery.org.uk/paintings/piero-della-francesca-the-baptism-of-christ)
- [The Nativity: oil colour and narrative](https://www.nationalgallery.org.uk/paintings/piero-della-francesca-the-nativity)
- [The Flagellation of Christ: foreground and background space for comparison](https://en.wikipedia.org/wiki/The_Flagellation_of_Christ_(Piero_della_Francesca))

Primary collection / production material is for checking the works and the method; encyclopaedia entries only help you locate things. Starting work still means actually looking at several originals or clips of different scenes and recording the stable features and the exceptions; a list of works is not the same as having done a multi-image visual experiment.

## Feeding back after use

Before use, look at the latest verified conclusions in this section; there is currently a technical check of a 6-second single-scene output, while style fidelity and cross-scene visual verification are unfinished. Afterwards record only findings that affect the result: date, subject matter, route taken, references and output path/hash, problem, fix, verification status and scope. Revise an expired conclusion in its original sentence; do not append contradictory rules. A research hypothesis is promoted to an implemented recipe only after cross-scene reproduction; for repeatable engineering problems, fix the tool first and test. User preferences go into the taste profile separately and do not widen the authorisation.


### 2026-10-15 · Feedback from a single-scene trial

- Scene: an astronomy workshop; event: instrument rings turning with geometric order; route: drawn and animated in code.
- Checks: determinism re-test, full MP4 decode, and an independent frame-grab review; the short's fast-motion metric was flagged amber under the existing gate and cannot be used to infer that a longer film passes.
- Boundary: this only proves that the build runs and can be watched; artist/studio style similarity is still limited, and the geometry, palette or texture parameters must not be taken as the final standard.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
