# 44_cortona · Pietro da Cortona: Baroque Mass and Moving Groups

Status: research recipe + single-scene engineering trial; established and produced on 2026-10-15. Ships with `scenes/44_cortona.js`, run with `render.py --film style_studies --solo 44_cortona --from 0 --to 6`; it has not yet passed style fidelity or cross-scene verification, so it cannot be upgraded to a mature style on that basis.

## Check First

Read [Cross-Scene Style Extraction](../15-style-transfer.md) first, then this card. The works are used to compare visual language; figures, objects, composition, and camera are not lifted directly. The stable features below are research generalisations; the implementation and transfer plan are hypotheses awaiting verification; official parameters or already-measured capabilities must not be claimed falsely.

## Scope

Mainly the group organisation, colour-light, and space of large decorative and narrative paintings; the ceiling effect is one applied branch.

## Transferable Visual Language

- Form: full-bodied figures, drapery, and environmental mass push and pull against each other to form groups.
- Space: diagonal links, front-to-back interleaving, and local breaking of the frame create continuity; composition is regenerated for each new event.
- Colour and light: rich warm and cool colours support each other; light and dark break the complexity into readable levels.
- Material: architecture, painting, and ornament can continue into one another, but each keeps its own boundary and physical touch.

## Content That Varies by Brief

A full screen of angels, cloud masses, cartouches, gilded edges, upshots, or spirals is not mandatory; a domestic scene must also have something clear happening first.

## Distinction from Adjacent Styles

Distinct from Michelangelo's single-body tension; distinct from Pozzo's route, which is built mainly on architectural perspective illusion.

## Production Starting Point (To Be Verified)

Paint three large tiers of groups and their light relationships first, controlling density with occlusion and colour-light; add detail afterwards. If you use frame-breaking and a ceiling, test the viewing point; ornament must not cover the action.

Action speed, frame rate, camera, and score are set by this narrative; a quiet mood in the image is not the same thing as slow motion. Engineering integration follows the [Style Author Spec](../08-style-author-spec.md); an engine id is registered only after a new renderer has actually been built.

## Cross-Scene Test Prompts (Not a Fixed Template)

- Scene changes happening backstage in a large theatre at once: real activity forms the groups.
- Equipment being lifted in a repair shop: primary and secondary massing and diagonal relationships.
- A small two-person dining table: after scaling down, the organisation is still abundant but restrained.

Pick tests with different subjects / spatial scales / subject types; running the full set every time is not required. Record still-frame and motion acceptance separately; keep uncovered ranges marked as to be verified.

## References and Evidence Boundaries

- [Uffizi: the four ages frescoes in the Pitti Palace stove room, cross-checked against the ceiling works](https://www.uffizi.it/en/artworks/stove-room)
- [Museum With No Frontiers: collection entry for the Barberini ceiling](https://baroqueart.museumwnf.org/database_item.php?id=monument%3BBAR%3Bit%3BMon11%3B18%3Bit&pageT=N)
- [Painter and work list: keep checking non-ceiling works](https://en.wikipedia.org/wiki/Pietro_da_Cortona)

Primary museum / production material is used to check works and methods; encyclopedia entries only help with locating. Starting work still requires actually looking side by side at several original works or clips of different scenes and recording stable features and exceptions; a work list does not mean a multi-image visual experiment has been completed.

## Feedback After Use

Check this section's latest verified conclusions before use; what exists now is a technical check of a 6-second single-scene output; style fidelity and cross-scene visual verification are unfinished. Afterwards record only findings that affect results: date, subject, route taken, reference and output paths / hashes, problem, fix, verification status, and scope. Rewrite an invalid conclusion in place; do not append contradictory rules. Upgrade a research hypothesis to a production recipe only after it reproduces across scenes; for repeatable engineering problems, fix the tool first and test it. User preferences go into the taste profile separately and do not widen authorisation.


### 2026-10-15 · Single-Scene Trial Feedback

- Scene: theatre scene change; event: suspended props and layered drapes moving; route: code-drawn and animated.
- Check: deterministic re-run, full MP4 decode, and independent frame-sampling review; the short-film fast-motion metric is turned yellow under the existing gate and cannot be extrapolated to feature-length compliance.
- Boundary: this only proves the project runs and is watchable; artist / studio style similarity is still limited, and geometry, palette, or texture parameters cannot be treated as the final standard.

## v2 Production Run (2026-10-16, self-score ~70, not registered as a production run)

- Source anchoring: *Allegory of Divine Providence* (Barberini ceiling), *The Rape of the Sabine Women* (only two distinct works; the third entry was the same image as the first and was dropped as a duplicate). Signature: stucco frames plus gilded roundels, warm gold radial light at the centre, clouds piled into volume, a crowd rotating around the centre, ribbons and figures spilling past the frame.
- Route: `scenes/44_cortona.js`. Three stucco bands + egg-and-dart + gold roundels in the four corners → opening sky gradient with radial light → cloud mass (one bumpy silhouette overall, lit along the direction facing the centre, outer arcs outlining the lumps) → crowd (`M.figure` rotating around the centre) + red and blue silk ribbons flared along the ellipse normal → white-robed figure at the centre with breathing gold light → `MEDIUM.fresco`.
- Lesson: stacking clouds out of individual spherical radial gradients reads as soap bubbles; build the cloud as one bumpy mass first, then light it along the light direction. Ribbon width must be expanded along the path normal; a fixed angle turns them into hairs.
- Still improvable: figures are still bell-shaped robes; missing strong foreshortening and strong light-and-dark; the highlight arcs look cartoonish.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
