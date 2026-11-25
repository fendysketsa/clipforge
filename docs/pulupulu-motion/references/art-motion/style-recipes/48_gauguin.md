# 48_gauguin · Gauguin: Flat Planes, Contours, and Symbolic Colour

Status: research recipe; the demo was rebuilt on 2026-10-16 under protocol 16 (see "v2 Production Run" at the end); neither self-assessment nor independent review reached 80, so it is not registered as a production run.

## Check First

Read [Cross-Scene Style Extraction](../15-style-transfer.md) first, then this card. The works are used to compare visual language; figures, objects, composition, and camera are not lifted directly. The stable features below are research generalisations; the implementation and transfer plan are hypotheses awaiting verification; official parameters or already-measured capabilities must not be claimed falsely.

## Scope

Focus on the language of Synthetism and flat symbolic colour; do not treat Brittany, Tahiti, and the different media as one fixed set of subject matter.

## Transferable Visual Language

- Colour: large colour fields carry mood and structure; do not mechanically copy natural colour; colour needs a thematic basis.
- Modelling: simplified forms and clearer contours support each other, and a new subject is still identifiable.
- Space: depth can be compressed, the ground viewpoint raised, or stacking used to organise — but not every object is entirely flat.
- Surface: large colour areas keep subtle internal variation and must not degrade into uniform black-outlined vector fills.

## Content That Varies by Brief

Tropical plants, brown skin, particular costume, or "exotic" ornament are not mandatory; cultural subject matter comes from the user's brief and is not a shortcut to the style.

## Distinction from Adjacent Styles

Distinct from ordinary flat illustration: the colour fields carry emotional and symbolic relationships; distinct from Chagall: no need to invert, float, or shatter the spatial logic.

## Production Starting Point (To Be Verified)

Use a small number of large colour fields to place the psychological centre of gravity of the new scene first, then refine contours, stacking, and material. Motion may be fast or slow; colour fields stay consistent per object, and random recolouring across the frame is forbidden.

Action speed, frame rate, camera, and score are set by this narrative; a quiet mood in the image is not the same thing as slow motion. Engineering integration follows the [Style Author Spec](../08-style-author-spec.md); an engine id is registered only after a new renderer has actually been built.

## Cross-Scene Test Prompts (Not a Fixed Template)

- A modern convenience store on the night shift.
- A set of maintenance tools with no figures.
- A handover gesture during an office argument: identification must not rely on tropical subject matter.

Pick tests with different subjects / spatial scales / subject types; running the full set every time is not required. Record still-frame and motion acceptance separately; keep uncovered ranges marked as to be verified.

## References and Evidence Boundaries

- [Met essay on Gauguin: across media and Symbolism](https://www.metmuseum.org/essays/paul-gauguin-1848-1903)
- [*The Siesta*: figures and flat space](https://www.metmuseum.org/art/collection/search/436449)
- [Gauguin exhibition in New York: the difference between paintings, sculpture, and prints](https://www.metmuseum.org/exhibitions/listings/2002/gauguin)

Primary museum / production material is used to check works and methods; encyclopedia entries only help with locating. Starting work still requires actually looking side by side at several original works or clips of different scenes and recording stable features and exceptions; a work list does not mean a multi-image visual experiment has been completed.

## Feedback After Use

Check this section's latest verified conclusions before use; what exists now is a technical check of a 6-second single-scene output; style fidelity and cross-scene visual verification are unfinished. Afterwards record only findings that affect results: date, subject, route taken, reference and output paths / hashes, problem, fix, verification status, and scope. Rewrite an invalid conclusion in place; do not append contradictory rules. Upgrade a research hypothesis to a production recipe only after it reproduces across scenes; for repeatable engineering problems, fix the tool first and test it. User preferences go into the taste profile separately and do not widen authorisation.


### 2026-10-15 · Single-Scene Trial Feedback

- Scene: dye-yard at dusk; event: wind fills the fabric, symbolic colour fields support each other; route: code-drawn and animated.
- Check: deterministic re-run, full MP4 decode, and independent frame-sampling review; the short-film fast-motion metric is turned yellow under the existing gate and cannot be extrapolated to feature-length compliance.
- Boundary: this only proves the project runs and is watchable; artist / studio style similarity is still limited, and geometry, palette, or texture parameters cannot be treated as the final standard.

## v2 Production Run (2026-10-16, self-score ~65, taste items pending author)

- Route: `scenes/48_gauguin.js`. Every form goes through `MEDIUM.flat` (short bars inside the same colour block following the stroke direction + deep ultramarine contours, 5–8 px wide); a vermilion field, a yellow-ochre slope, and violet-brown diagonal trunks split the picture; three white-hatted women in the foreground are cropped by the frame; a boy leading a goat shrinks into the distance (scaled down so the naive modelling is not magnified).
- Measured: qa determinism ✓, no popping, 8 ms/frame.
- Key lesson: figures built from polylines read as emoji, so always use smooth closed curves (`smooth()` within the scene); hat brims must be drawn behind the face, and the face must not be covered.
- Still improvable: the boy and the goat are still naive; the trunks are too straight; missing Gauguin's large violet-brown shadow areas and symbolic animals.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
