# 45_renoir · Renoir: Interwoven Warm and Cool, Figures with Warmth

Status: research recipe; the demo was rebuilt on 2026-10-16 under protocol 16 (see "v2 Production Run" at the end); self-score ~58 with no independent review, so it is not registered as a production run.

## Check First

Read [Cross-Scene Style Extraction](../15-style-transfer.md) first, then this card. The works are used to compare visual language; figures, objects, composition, and camera are not lifted directly. The stable features below are research generalisations; the implementation and transfer plan are hypotheses awaiting verification; official parameters or already-measured capabilities must not be claimed falsely.

## Scope

Prefer the Impressionist language from the 1870s to the early 1880s; the more linear turn of the 1880s and the different modelling of the late work must be noted separately, and a unified style across the whole career must not be asserted.

## Transferable Visual Language

- Brushwork: soft and hard edges convert into each other; colour touches stay visible but do not shatter faces and hands.
- Colour and light: warm flesh tones and cool reflected light act on each other; shadows keep their colour; do not lay one uniform orange over the whole picture.
- Modelling: rounded, tactile bodies and fabric; intimacy comes from the relationship between figures, not one uniform smiling face.
- Space: subject and environment share light and colour while near-to-far difference stays clear; interior and exterior are re-configured to the actual lighting.

## Content That Varies by Brief

A luncheon, straw hats, dappled tree shade, a French garden, pink skin, or a particular crowd are not mandatory; night scenes can also be studied for transfer.

## Distinction from Adjacent Styles

Compared with Pissarro it stresses figures, skin, and soft modelling more; compared with Sisley, landscape air is not the sole organising centre.

## Production Starting Point (To Be Verified)

Build structure from reliable character assets first, then work region by region with finer skin / hand strokes and looser environment strokes; unify colour and light while keeping material differences. Use light patches only where the light source and occlusion hold up.

Action speed, frame rate, camera, and score are set by this narrative; a quiet mood in the image is not the same thing as slow motion. Engineering integration follows the [Style Author Spec](../08-style-author-spec.md); an engine id is registered only after a new renderer has actually been built.

## Cross-Scene Test Prompts (Not a Fixed Template)

- Colleagues of different skin tones sorting equipment in an office.
- An empty breakfast table: recognised through colour and touch rather than through pretty figures.
- A rushed handover in a small shop at night: avoid warm light meaning slow motion.

Pick tests with different subjects / spatial scales / subject types; running the full set every time is not required. Record still-frame and motion acceptance separately; keep uncovered ranges marked as to be verified.

## References and Evidence Boundaries

- [Phillips, *Luncheon of the Boating Party*](https://www.phillipscollection.org/collection/luncheon-boating-party)
- [Art Institute of Chicago study of *Two Sisters*](https://publications.artic.edu/api/epub/paintingsanddrawings/135639/print_view)
- [Art Institute of Chicago, *Acrobats at the Cirque Fernando*](https://publications.artic.edu/api/epub/paintingsanddrawings/135637/print_view)

Primary museum / production material is used to check works and methods; encyclopedia entries only help with locating. Starting work still requires actually looking side by side at several original works or clips of different scenes and recording stable features and exceptions; a work list does not mean a multi-image visual experiment has been completed.

## Feedback After Use

Check this section's latest verified conclusions before use; what exists now is a technical check of a 6-second single-scene output; style fidelity and cross-scene visual verification are unfinished. Afterwards record only findings that affect results: date, subject, route taken, reference and output paths / hashes, problem, fix, verification status, and scope. Rewrite an invalid conclusion in place; do not append contradictory rules. Upgrade a research hypothesis to a production recipe only after it reproduces across scenes; for repeatable engineering problems, fix the tool first and test it. User preferences go into the taste profile separately and do not widen authorisation.


### 2026-10-15 · Single-Scene Trial Feedback

- Scene: space capsule repair; event: arms on the generated underlay, local deformation of pipes, and a leak fading; route: generated underlay + local code deformation.
- Check: deterministic re-run, full MP4 decode, and independent frame-sampling review; the short-film fast-motion metric is turned yellow under the existing gate and cannot be extrapolated to feature-length compliance.
- Boundary: this only proves the project runs and is watchable; artist / studio style similarity is still limited, and geometry, palette, or texture parameters cannot be treated as the final standard.
- Clear shortfall: local mesh displacement is not a full grip / hand-over / valve-turning performance; complex character interaction needs pose frames or hierarchical rigging, and a good-looking underlay must not mask weak motion.

## v2 Production Run (2026-10-16, self-score ~58, no independent review)

- Route: `scenes/45_renoir.js`. The old version was an external bitmap + mesh warp; it has been swapped for a code-drawn approach and the old version backed up. Shape layer = canopy / sky light through the leaves / trunks / sandy ground / table / distant crowd; redrawn with `MEDIUM.broken`: diagonal short strokes for canopy and ground, a separate layer of vertical fine strokes for the crowd (if the crowd shares the ground's horizontal strokes it gets smeared into lying-down shapes); the light-patch layer (warm yellow highlights / blue-violet shadow) is redrawn and cached separately, two offset copies cross-fade to sway, and it is dropped onto the figures again at low opacity; the foreground pair of dancers is redrawn on a small canvas each frame.
- Lesson: figures and background must be redrawn on separate layers, each with its own stroke direction; the light-patch layer over figures must be lowered in opacity, or the figures get covered to half height.
- Still improvable: the figures lean towards dolls; missing warm pink skin and fabric highlights; the mid-ground crowd is too orderly.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
