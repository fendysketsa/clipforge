# 49_chagall · Chagall: Memory Space and Emotional Colour

Status: research recipe + single-scene engineering trial; established and produced on 2026-10-15. Ships with `scenes/49_chagall.js`, run with `render.py --film style_studies --solo 49_chagall --from 0 --to 6`; it has not yet passed style fidelity or cross-scene verification, so it cannot be upgraded to a mature style on that basis.

## Check First

Read [Cross-Scene Style Extraction](../15-style-transfer.md) first, then this card. The works are used to compare visual language; figures, objects, composition, and camera are not lifted directly. The stable features below are research generalisations; the implementation and transfer plan are hypotheses awaiting verification; official parameters or already-measured capabilities must not be claimed falsely.

## Scope

Mainly the poetic space in the paintings; compare the early village work, the later religious paintings, and the stage / glass media separately, and do not flatten their differences.

## Transferable Visual Language

- Space: direction, scale, and adjacency may obey emotion, but the viewer still has to read the main action.
- Colour: colour fields and local forms express mood together; a particular set of high-saturation blues and reds is not required.
- Modelling: figures, animals, and objects keep a recognisable character; exaggeration and distortion stay connected.
- Narrative: real detail and memory images can coexist; the images come from the new story, not from a ready-made list of symbols.

## Content That Varies by Brief

Floating lovers, fiddlers, goats, and Russian villages are not mandatory; this spatial and colour relationship can be studied without flight.

## Distinction from Adjacent Styles

Distinct from Gauguin's large planes and contours; distinct from Dalí's realistic illusion — liquefying realistic objects alone does not make it Chagall.

## Production Starting Point (To Be Verified)

Establish the real relationship and the emotional relationship of this piece first, then decide where scale or direction changes; every distortion keeps character identity and object contact continuous. Motion rhythm is set by the narrative.

Action speed, frame rate, camera, and score are set by this narrative; a quiet mood in the image is not the same thing as slow motion. Engineering integration follows the [Style Author Spec](../08-style-author-spec.md); an engine id is registered only after a new renderer has actually been built.

## Cross-Scene Test Prompts (Not a Fixed Template)

- Two remote colleagues collaborating across time zones.
- Moving boxes and memory in an empty room.
- A hurried farewell at a train station: avoid automatically adding a floating couple.

Pick tests with different subjects / spatial scales / subject types; running the full set every time is not required. Record still-frame and motion acceptance separately; keep uncovered ranges marked as to be verified.

## References and Evidence Boundaries

- [MoMA, *I and the Village*](https://www.moma.org/collection/works/78984)
- [MoMA, *Birthday*](https://www.moma.org/collection/works/79360/)
- [Musée national Marc Chagall, France: the boundary of the religious-themed collection](https://www.culture.gouv.fr/rechercher-une-publication-du-ministere-de-la-culture/repertoire-des-informations-publiques/Musees-des-Beaux-arts/musee-national-marc-chagall)

Primary museum / production material is used to check works and methods; encyclopedia entries only help with locating. Starting work still requires actually looking side by side at several original works or clips of different scenes and recording stable features and exceptions; a work list does not mean a multi-image visual experiment has been completed.

## Feedback After Use

Check this section's latest verified conclusions before use; what exists now is a technical check of a 6-second single-scene output; style fidelity and cross-scene visual verification are unfinished. Afterwards record only findings that affect results: date, subject, route taken, reference and output paths / hashes, problem, fix, verification status, and scope. Rewrite an invalid conclusion in place; do not append contradictory rules. Upgrade a research hypothesis to a production recipe only after it reproduces across scenes; for repeatable engineering problems, fix the tool first and test it. User preferences go into the taste profile separately and do not widen authorisation.


### 2026-10-15 · Single-Scene Trial Feedback

- Scene: the memory of moving house; event: an old case opens and flowers and letters fly into an inverted space; route: code-drawn and animated.
- Check: deterministic re-run, full MP4 decode, and independent frame-sampling review; the short-film fast-motion metric is turned yellow under the existing gate and cannot be extrapolated to feature-length compliance.
- Boundary: this only proves the project runs and is watchable; artist / studio style similarity is still limited, and geometry, palette, or texture parameters cannot be treated as the final standard.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
