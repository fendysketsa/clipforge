# 40_raphael · Raphael: harmonious arrangement and natural connection

Status: research recipe + single-scene engineering trial; established and implemented on 2026-10-15. `scenes/40_raphael.js` is included, run with `render.py --film style_studies --solo 40_raphael --from 0 --to 6`; it has not passed style fidelity or cross-scene verification, so it cannot be upgraded to a mature style on that basis.

## First checks before you start

Read [cross-scene style distillation](../15-style-transfer.md) first, then this card. The works are for comparing visual language; characters, objects, composition and camera are not carried over directly. The stable features below are research generalisations, and the implementation and migration plans are hypotheses awaiting verification; do not pass them off as official parameters or as capability already tested.

## Scope

Weighted toward the forms, the connections between figures and the clear space of the mature period; the early Perugino influence and the stronger drama of the later work are not forced together into one averaged style.

## Transferable visual language

- Form: continuous contours, rounded modelling of body and drapery; idealised figures that still have a definite action.
- Space: primary and secondary groups, sightlines and gestures connect to one another; a triangular arrangement is one option, not a fixed layout.
- Colour and light: layered relationships of red, blue and neutrals, readable skin and soft volume; set the key colour afresh for each new scene.
- Detail: the information in the frame has a priority order, and architecture, props and figures all support the main event.

## What changes with the brief

The School of Athens arches, the two central figures, the Madonna holding the child or period costume are not compulsory; do not arrange every shot as a central triangle.

## How it differs from neighbouring styles

Differs from Piero's sense of measure: organic connection counts for more here. Differs from Michelangelo: not every body is hardened into a taut sculpture.

## Starting point for a build (to be verified)

Draw a diagram of the relationships between people and objects first, then choose the composition for this action; unify the characters and the environment through colour blocks, light direction and soft/hard edges. With none of the original's subject matter in sight it should still look clear, rounded and organised.

Action speed, frame rate, camera and score are decided by this narrative; do not equate a quiet mood with slow motion. Engineering integration follows the [style author spec](../08-style-author-spec.md), and the engine id is registered only once the new renderer actually exists.

## Cross-scene verification prompts (not a fixed template)

- A community repair class: several people each doing one related thing.
- A product workbench: a shot with nobody in it still needs hierarchy and connections between forms.
- Two people working together in a narrow kitchen: tests a non-monumental architectural scene.

Pick tests across different subject matter / spatial scale / subject type; running the whole set every time is not required. Record still-frame and motion acceptance separately, and keep marking anything not covered as to be verified.

## References and the limits of the evidence

- [Raphael at the National Gallery: different phases and subject matter](https://www.nationalgallery.org.uk/artists/raphael)
- [The Madonna of the Pinks: intimate gesture](https://www.nationalgallery.org.uk/paintings/raphael-the-madonna-of-the-pinks-la-madonna-dei-garofani)
- [The School of Athens: group comparison](https://en.wikipedia.org/wiki/The_School_of_Athens)

Primary collection / production material is for checking the works and the method; encyclopaedia entries only help you locate things. Starting work still means actually looking at several originals or clips of different scenes and recording the stable features and the exceptions; a list of works is not the same as having done a multi-image visual experiment.

## Feeding back after use

Before use, look at the latest verified conclusions in this section; there is currently a technical check of a 6-second single-scene output, while style fidelity and cross-scene visual verification are unfinished. Afterwards record only findings that affect the result: date, subject matter, route taken, references and output path/hash, problem, fix, verification status and scope. Revise an expired conclusion in its original sentence; do not append contradictory rules. A research hypothesis is promoted to an implemented recipe only after cross-scene reproduction; for repeatable engineering problems, fix the tool first and test. User preferences go into the taste profile separately and do not widen the authorisation.


### 2026-10-15 · Feedback from a single-scene trial

- Scene: a gardening workbench; event: a watering can pouring, and red and blue cloth organising the composition; route: drawn and animated in code.
- Checks: determinism re-test, full MP4 decode, and an independent frame-grab review; the short's fast-motion metric was flagged amber under the existing gate and cannot be used to infer that a longer film passes.
- Boundary: this only proves that the build runs and can be watched; artist/studio style similarity is still limited, and the geometry, palette or texture parameters must not be taken as the final standard.

## v2 implementation (2026-10-16, self-assessed ~70, not registered as an implementation)

- Anchored in the originals: The School of Athens, the Disputation of the Holy Sacrament, The Parnassus. Signatures: semicircular lunette + gold-brown／red／ultramarine decorative bands, a one-point-perspective barrel vault with coffers, a patch of sky at the far end, a chequered floor, statues in the niches, saturated robe colours in conversing groups.
- Route: `scenes/40_raphael.js`. The vault recedes to the vanishing point in a geometric series over N=9 courses, each course being cut into coffers by angle; the side walls alternate pilasters／niches; the floor is chequered by course and column; figures use `MEDIUM.figure` and point hand-to-eye at one another (book, astrolabe, scroll); three small figures walk along the ground in the distance.
- Still improvable: bell-shaped robes on the figures and near-identical faces; the niche statues look like candles; missing the sheen of skin and cloth.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
