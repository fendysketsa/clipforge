# 43_lorenzetti · Ambrogio Lorenzetti: A Readable Social Space

Status: research recipe + single-scene engineering trial; established and produced on 2026-10-15. Ships with `scenes/43_lorenzetti.js`, run with `render.py --film style_studies --solo 43_lorenzetti --from 0 --to 6`; it has not yet passed style fidelity or cross-scene verification, so it cannot be upgraded to a mature style on that basis.

## Check First

Read [Cross-Scene Style Extraction](../15-style-transfer.md) first, then this card. The works are used to compare visual language; figures, objects, composition, and camera are not lifted directly. The stable features below are research generalisations; the implementation and transfer plan are hypotheses awaiting verification; official parameters or already-measured capabilities must not be claimed falsely.

## Scope

Use it to compare city narrative with other spatial works; it is not about painting every subject as a Siena civic fresco.

## Transferable Visual Language

- Space: buildings, roads, doorways, and places connect many kinds of lived activity; a local viewpoint can serve readability.
- Modelling: figures are small but their actions and trades are clear; buildings have volume rather than being flat icons.
- Colour and light: earth colours, mineral colours, and detailed light and shade stay unified overall; avoid an old-paper filter that darkens all the information.
- Narrative: several events can coexist, but with primary and secondary weight, routes, and clear causal links.

## Content That Varies by Brief

A horizontal scroll, city walls, medieval dress, or a dense crowd are not mandatory; complexity comes from this brief's content.

## Distinction from Adjacent Styles

Distinct from Persian miniature: the space emphasises the continuity of town solids and lived activity; density is not built from all-over geometric pattern.

## Production Starting Point (To Be Verified)

Build the world canvas from the connection relationships of this place, give figure activity a visible route, then paint in layers. Eye guidance can use local action and camera; do not lay out a row of small cards that have nothing to do with each other.

Action speed, frame rate, camera, and score are set by this narrative; a quiet mood in the image is not the same thing as slow motion. Engineering integration follows the [Style Author Spec](../08-style-author-spec.md); an engine id is registered only after a new renderer has actually been built.

## Cross-Scene Test Prompts (Not a Fixed Template)

- A modern logistics park: unloading, sorting, and delivery linked to each other.
- A single-room clinic: readable collaboration inside a small space.
- Unmanned greenhouse pipework: with no figures, the actual installation carries the narrative.

Pick tests with different subjects / spatial scales / subject types; running the full set every time is not required. Record still-frame and motion acceptance separately; keep uncovered ranges marked as to be verified.

## References and Evidence Boundaries

- [Italian Ministry of Culture: the city and countryside of Good Government](https://catalogo.cultura.gov.it/approfondimento/l-allegoria-del-buon-governo-ambrogio-lorenzetti/il-buon-governo-citta-e-campagna)
- [Uffizi, *Presentation of Jesus at the Temple*: a different spatial subject](https://www.uffizi.it/opere/presentazione-al-tempio)
- [The complete fresco cycle: contrasting narrative moods](https://en.wikipedia.org/wiki/The_Allegory_of_Good_and_Bad_Government)

Primary museum / production material is used to check works and methods; encyclopedia entries only help with locating. Starting work still requires actually looking side by side at several original works or clips of different scenes and recording stable features and exceptions; a work list does not mean a multi-image visual experiment has been completed.

## Feedback After Use

Check this section's latest verified conclusions before use; what exists now is a technical check of a 6-second single-scene output; style fidelity and cross-scene visual verification are unfinished. Afterwards record only findings that affect results: date, subject, route taken, reference and output paths / hashes, problem, fix, verification status, and scope. Rewrite an invalid conclusion in place; do not append contradictory rules. Upgrade a research hypothesis to a production recipe only after it reproduces across scenes; for repeatable engineering problems, fix the tool first and test it. User preferences go into the taste profile separately and do not widen authorisation.


### 2026-10-15 · Single-Scene Trial Feedback

- Scene: cut-away library; event: a red book slides down, falls into a book cart, and rides away with it; route: code-drawn and animated.
- Check: deterministic re-run, full MP4 decode, and independent frame-sampling review; the short-film fast-motion metric is turned yellow under the existing gate and cannot be extrapolated to feature-length compliance.
- Boundary: this only proves the project runs and is watchable; artist / studio style similarity is still limited, and geometry, palette, or texture parameters cannot be treated as the final standard.
- Actual fix: removed the book's modulo reset; the cart stops first to receive the book, and the book only moves off once it is bound to the cart frame; review no longer shows it flying back to the entrance.

## v2 Production Run (2026-10-16, self-score ~72, not registered as a production run)

- Figures rebuilt (user feedback: "the figures still need crazy optimisation"): small head, long body, narrow shoulders over an outward-flaring robe, fold lines, light on the left and dark on the right, front foot showing beyond the hem, three-quarter view; 20 figures walking on a loop in the street, large near and small far.

- Source anchoring: *The Effects of Good Government in the City*, *Allegory of Good Government* (only two distinct works). Signature: buildings stacked one on another filling the upper half, rows of small arched windows in pink / grey / ochre walls, crenellated towers, ground-floor arcades cut open to reveal workshops, a band of small figures in the street each doing their own thing, a dark brown border band.
- Route: `scenes/43_lorenzetti.js`. Shape layer (sky → low mid-ground buildings → main buildings left and right → cut-open cobbler's workshop → street → steps) → `MEDIUM.fresco`; small figures painted last each frame (circle dance, pack mule, stone hoisted on scaffolding, cobbler, flag).
- Fixed in the second round: blank plaster showing through in the middle, figures with both arms out reading as cartoon, the mule crowding the circle dance.
- Still improvable: street foot traffic needs to multiply several times over; walls need a paint layer; small figures need more natural proportions and drapery; add a street receding in perspective.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
