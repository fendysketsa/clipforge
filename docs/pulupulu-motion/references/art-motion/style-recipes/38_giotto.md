# 38_giotto · Giotto: mass and narrative relationships

Status: research recipe; the demo was redone on 2026-10-16 under protocol 16 (see "v2 implementation" at the end of the card), and neither the self-assessment nor the independent review reached 80, so it is not registered as an implementation.

## First checks before you start

Read [cross-scene style distillation](../15-style-transfer.md) first, then this card. The works are for comparing visual language; characters, objects, composition and camera are not carried over directly. The stable features below are research generalisations, and the implementation and migration plans are hypotheses awaiting verification; do not pass them off as official parameters or as capability already tested.

## Scope

Primarily the narrative fresco language of Giotto's maturity, with panel paintings used to check the mass of the figures; not every work is to be called a fresco.

## Transferable visual language

- Form: bodies as simple blocks with weight; drapery states the load and the volume; faces and hands can carry a relationship.
- Space: figures can stand and can touch; architecture and rock masses organise the event; no pursuit of the photographic perspective of later centuries.
- Colour and light: fairly complete local colour planes with graded modelling, light and shade serving volume, background and subject belonging to the same world.
- Material: the fresco direction uses matte surfaces, fine grain and soft colour layers; the gold-ground panel is another medium — do not lay gold over a whole layer.

## What changes with the brief

Saints and mourning gestures are not required; gold haloes, ultramarine sky and decorative borders are the shared signature of the three Scrovegni originals, and the v2 demo keeps them (the halo went to the porter — a joke, and also recognition value); cracking and fading are condition, not the core of the style.

## How it differs from neighbouring styles

Differs from Piero: the readability of gesture and of relationships between figures comes first, and geometric order does not become the protagonist. Differs from Raphael: it keeps a plainer, heavier block.

## Starting point for a build (to be verified)

First draw the new scene as readable silhouettes and blocks, layer it by contact relationship, then do the matte colour planes and the drapery; do not let surface craquelure stand in for modelling. Characters follow route 10, and the material treatment must cover the characters as well.

Action speed, frame rate, camera and score are decided by this narrative; do not equate a quiet mood with slow motion. Engineering integration follows the [style author spec](../08-style-author-spec.md), and the engine id is registered only once the new renderer actually exists.

## Cross-scene verification prompts (not a fixed template)

- Two people handing a large box over to each other at a courier depot: check gesture and weight.
- A dismantled machine in a repair room: it should still have a sense of mass with no classical figure present.
- A night-shift waiting room: after changing the lighting and the number of people, check whether the space and the colour planes still hold together.

Pick tests across different subject matter / spatial scale / subject type; running the whole set every time is not required. Record still-frame and motion acceptance separately, and keep marking anything not covered as to be verified.

## References and the limits of the evidence

- [Giotto, Adoration of the Magi: mass and architecture seen from below](https://www.metmuseum.org/art/collection/search/436504)
- [Giotto, Madonna Enthroned: the panel medium for comparison](https://www.uffizi.it/en/artworks/virgin-and-child-enthroned-surrounded-by-angels-and-saints-ognissanti-maesta)
- [The Lamentation: narrative fresco for comparison](https://en.wikipedia.org/wiki/Lamentation_(The_Mourning_of_Christ))

Primary collection / production material is for checking the works and the method; encyclopaedia entries only help you locate things. Starting work still means actually looking at several originals or clips of different scenes and recording the stable features and the exceptions; a list of works is not the same as having done a multi-image visual experiment.

## Feeding back after use

Before use, look at the latest verified conclusions in this section; there is currently a technical check of a 6-second single-scene output, while style fidelity and cross-scene visual verification are unfinished. Afterwards record only findings that affect the result: date, subject matter, route taken, references and output path/hash, problem, fix, verification status and scope. Revise an expired conclusion in its original sentence; do not append contradictory rules. A research hypothesis is promoted to an implemented recipe only after cross-scene reproduction; for repeatable engineering problems, fix the tool first and test. User preferences go into the taste profile separately and do not widen the authorisation.


### 2026-10-15 · Feedback from a single-scene trial

- Scene: a watermill courtyard; event: the waterwheel catches the water and turns, the clay jars and the courtyard showing heavy volume; route: drawn and animated in code.
- Checks: determinism re-test, full MP4 decode, and an independent frame-grab review; the short's fast-motion metric was flagged amber under the existing gate and cannot be used to infer that a longer film passes.
- Boundary: this only proves that the build runs and can be watched; artist/studio style similarity is still limited, and the geometry, palette or texture parameters must not be taken as the final standard.

## v2 implementation (2026-10-16, self-assessed ~65, taste items pending the author)

- Anchored in the originals: the Scrovegni Chapel's Lamentation, Meeting at the Golden Gate and Flight into Egypt (`fetch_reference.py`). Stable signatures: an ultramarine sky with gold stars, earth-red / ochre / olive robes, weighty bell-shaped robes, sightlines locking into one another between the figures, tilted grey-pink architectural blocks, a red-gold decorative band inside the frame.
- Route: `scenes/38_giotto.js`. Shape layer = sky (soft ultramarine blotches) → rock slopes → buildings (merlons + red-and-white diamond band under the eaves + arches) → ground → three figures via `MEDIUM.figure` (robes, half-cloaks, coarse sleeves, big heads, almond eyes + sightlines) → wooden crate; medium layer = `MEDIUM.fresco` (light blur + lime wash + plaster multiply + pinhole seams) + decorative border.
- Subject: two porters handing over a wooden crate at a dockside warehouse door, with a third person looking down at the corner of the crate; motion = the arc of the handover, hems swaying slightly, dust on landing, a bird crossing the sky.
- Measured: qa determinism ✓, no pops, 36ms/frame; still-frame match 27% (a fresco is quiet by nature; the motion is concentrated in the handover).
- Still improvable: faces and hands are still simple; haloes, angels and crowd density are missing; the light and shade in the drapery does not reach the layered glazing of the originals; the grass tufts are too even.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
