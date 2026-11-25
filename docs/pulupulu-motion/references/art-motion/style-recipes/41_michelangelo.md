# 41_michelangelo · Michelangelo: sculptural quality and tension of pose

Status: research recipe + single-scene engineering trial; established and implemented on 2026-10-15. `scenes/41_michelangelo.js` is included, run with `render.py --film style_studies --solo 41_michelangelo --from 0 --to 6`; it has not passed style fidelity or cross-scene verification, so it cannot be upgraded to a mature style on that basis.

## First checks before you start

Read [cross-scene style distillation](../15-style-transfer.md) first, then this card. The works are for comparing visual language; characters, objects, composition and camera are not carried over directly. The stable features below are research generalisations, and the implementation and migration plans are hypotheses awaiting verification; do not pass them off as official parameters or as capability already tested.

## Scope

The core is the sculptural modelling shared by painting and drawing; the Sistine ceiling is one reference, and the materials of sculpture, fresco and the late works are not lumped together.

## Transferable visual language

- Form: skeleton, load, torsion and compression build the mass; force comes from the pose, not from giving every character muscles.
- Contour: overlap and foreshortening are clear, and the subject reads as a solid occupying real space.
- Colour and light: build the large volumes with light and shade; the ceiling can supply clear colour blocks, drawing studies are for structure and are not to be used directly as an overall palette.
- Space: a forceful subject and the negative shape pull on each other; this can hold at an ordinary viewing angle, with no forced up-shot of a dome.

## What changes with the brief

Nudity, classical deities, the touching fingers or a fixed muscle proportion are not defaults; modern clothing and non-human subjects must hold up just as well.

## How it differs from neighbouring styles

Differs from Cortona: the force of mass and pose is the point, not teeming groups, ceiling illusion and decorative density.

## Starting point for a build (to be verified)

Verify the load-bearing silhouette and the foreshortening first, then handle volume, clothing and light. Design the performance from the cause of the action; code handles the layers and the transforms, and a few ellipses cannot pass as a body that has been through anatomical design.

Action speed, frame rate, camera and score are decided by this narrative; do not equate a quiet mood with slow motion. Engineering integration follows the [style author spec](../08-style-author-spec.md), and the engine id is registered only once the new renderer actually exists.

## Cross-scene verification prompts (not a fixed template)

- Rescuers forcing a deformed door open: the load reads even through the uniform.
- A folding robotic arm extending and retracting: checks non-human mass.
- One person quietly tying a shoelace: a small action can still carry structural tension.

Pick tests across different subject matter / spatial scale / subject type; running the whole set every time is not required. Record still-frame and motion acceptance separately, and keep marking anything not covered as to be verified.

## References and the limits of the evidence

- [The Met's Michelangelo galleries: drawings, sculpture and design](https://www.metmuseum.org/exhibitions/listings/2017/michelangelo/exhibition-galleries)
- [Official material on the Sistine ceiling](https://www.museivaticani.va/content/museivaticani/en/collezioni/musei/cappella-sistina/volta.html)

Primary collection / production material is for checking the works and the method; encyclopaedia entries only help you locate things. Starting work still means actually looking at several originals or clips of different scenes and recording the stable features and the exceptions; a list of works is not the same as having done a multi-image visual experiment.

## Feeding back after use

Before use, look at the latest verified conclusions in this section; there is currently a technical check of a 6-second single-scene output, while style fidelity and cross-scene visual verification are unfinished. Afterwards record only findings that affect the result: date, subject matter, route taken, references and output path/hash, problem, fix, verification status and scope. Revise an expired conclusion in its original sentence; do not append contradictory rules. A research hypothesis is promoted to an implemented recipe only after cross-scene reproduction; for repeatable engineering problems, fix the tool first and test. User preferences go into the taste profile separately and do not widen the authorisation.


### 2026-10-15 · Feedback from a single-scene trial

- Scene: a stone crane arm; event: mechanical joints turning with a sculptural load; route: drawn and animated in code.
- Checks: determinism re-test, full MP4 decode, and an independent frame-grab review; the short's fast-motion metric was flagged amber under the existing gate and cannot be used to infer that a longer film passes.
- Boundary: this only proves that the build runs and can be watched; artist/studio style similarity is still limited, and the geometry, palette or texture parameters must not be taken as the final standard.

## v2 implementation (2026-10-16, self-assessed ~65, not registered as an implementation)

- Anchored in the originals: the Atlas Slave (unfinished, the figure still trapped in the rough stone), the study for the Libyan Sibyl (red chalk, seen from behind), and The Creation of Adam. The old version was a robotic arm plus a ball, unrelated to the spirit of Michelangelo, and has been dropped.
- Route: `scenes/41_michelangelo.js`. A greyscale form map (ellipses of light and dark stacking the shoulder blades, the spinal groove and the latissimus dorsi; light from the upper left) → deterministic hatching generated from value + gradient (mainly 50° diagonals, cross-hatched in the darks) → a chalk-grain contour taken from the overall silhouette boundary pixels, thickened on the backlit side and broken up → cached; at runtime it is revealed from top to bottom by y, with the chalk sweeping along. On the right is an older study of the same figure, flipped and reduced; the paper has torn edges, foxing, fibres and a few lines of notation that do not form words.
- Key point: do not draw contours at the seams between parts (use the overall silhouette, otherwise the "assembled doll" shows); the lower edge fading out stands for "unfinished".
- Still improvable: the head is too round, the upper arm slightly short, and there is no real torsion in the torso; leaving the paper completely bare in the lights could be pushed for more contrast.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
