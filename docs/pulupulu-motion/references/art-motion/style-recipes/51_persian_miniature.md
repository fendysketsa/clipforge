# 51_persian_miniature · Persian Miniature: Layered Space and Precise Narrative

Status: research recipe; the demo was rebuilt on 2026-10-16 under protocol 16 (see "v2 Production Run" at the end); neither self-assessment nor independent review reached 80, so it is not registered as a production run.

## Check First

Read [Cross-Scene Style Extraction](../15-style-transfer.md) first, then this card. The works are used to compare visual language; figures, objects, composition, and camera are not lifted directly. The stable features below are research generalisations; the implementation and transfer plan are hypotheses awaiting verification; official parameters or already-measured capabilities must not be claimed falsely.

## Scope

Not a single artist or a single period. The initial focus is late Timurid Herat and early Safavid Tabriz book painting; choose one range before production and do not mix all Persian / Mughal painting indiscriminately.

## Transferable Visual Language

- Space: raise the viewpoint, unfold the buildings and layer the scenery so that several events can be read at once; do not force single-point perspective.
- Modelling: fine lines, clear gestures, and precise small objects carry the narrative together; figures are not pattern fill.
- Colour: mineral-saturated colour fields and fine ornament control each other; gold is used for the appropriate material layer.
- Composition: text areas, borders, and the picture can echo each other, and the organising logic can be kept in a new scene that has no text.

## Content That Varies by Brief

Gardens, palaces, carpets, Persian script, borders, or mounted figures are not mandatory; do not patch together patterns from different regions to stand in for historical accuracy.

## Distinction from Adjacent Styles

Distinct from the precise life studies of the Mughal natural-observation card, and equally distinct from Lorenzetti's continuous space of urban solids; do not call the three of them "refined Oriental painting".

## Production Starting Point (To Be Verified)

Rebuild a multi-level setting and action routes for the new subject, keeping subject layering separate from pattern layering; ornament follows the surface and must not drift during motion. Text needs real content and reliable letterforms — otherwise do not fabricate calligraphy.

Action speed, frame rate, camera, and score are set by this narrative; a quiet mood in the image is not the same thing as slow motion. Engineering integration follows the [Style Author Spec](../08-style-author-spec.md); an engine id is registered only after a new renderer has actually been built.

## Cross-Scene Test Prompts (Not a Fixed Template)

- The flow of books through a multi-level city library.
- The complete collaboration process in a modern food factory.
- Layered servicing of a single machine: testing the transfer without gardens or palaces.

Pick tests with different subjects / spatial scales / subject types; running the full set every time is not required. Record still-frame and motion acceptance separately; keep uncovered ranges marked as to be verified.

## References and Evidence Boundaries

- [Met: study of Shah Tahmasp's *Shahnama*](https://www.metmuseum.org/essays/the-shahnama-of-shah-tahmasp)
- [Met: collection notes on the *Shahnama* across periods](https://www.metmuseum.org/art/collection/search/446551)
- [Met teaching material on court art: comparing different album pages](https://www.metmuseum.org/learn/educators/curriculum-resources/~/media/Files/Learn/For%20Educators/Publications%20for%20Educators/Islamic%20Teacher%20Resource/Unit5.pdf)

Primary museum / production material is used to check works and methods; encyclopedia entries only help with locating. Starting work still requires actually looking side by side at several original works or clips of different scenes and recording stable features and exceptions; a work list does not mean a multi-image visual experiment has been completed.

## Feedback After Use

Check this section's latest verified conclusions before use; what exists now is a technical check of a 6-second single-scene output; style fidelity and cross-scene visual verification are unfinished. Afterwards record only findings that affect results: date, subject, route taken, reference and output paths / hashes, problem, fix, verification status, and scope. Rewrite an invalid conclusion in place; do not append contradictory rules. Upgrade a research hypothesis to a production recipe only after it reproduces across scenes; for repeatable engineering problems, fix the tool first and test it. User preferences go into the taste profile separately and do not widen authorisation.


### 2026-10-15 · Single-Scene Trial Feedback

- Scene: an irrigated courtyard; event: a water wheel and water flow inside layered space; route: code-drawn and animated.
- Check: deterministic re-run, full MP4 decode, and independent frame-sampling review; the short-film fast-motion metric is turned yellow under the existing gate and cannot be extrapolated to feature-length compliance.
- Boundary: this only proves the project runs and is watchable; artist / studio style similarity is still limited, and geometry, palette, or texture parameters cannot be treated as the final standard.

## v2 Production Run (2026-10-16, self-score ~80, taste items pending author)

- Source anchoring: Herat *Yusuf and Zulaykha*, the garden bathing-women page, and a page from Shah Tahmasp's *Shahnama*. Signature: the ground stood up like a hanging carpet (flat, seen from above), buildings cut open to reveal inner rooms, geometric tilework covering everything, gold edging + lapis blue borders, text blocks entering the picture, small figures in three-quarter view with large turbans.
- Route: `scenes/51_persian_miniature.js`, flat colour + dark brown contours throughout; star tiles tiled across by period modulo; octagonal pool, zigzag channels (gold edge + celadon), dotted leaves on the canopies; motion = water wheel turning, gold ripples running along the zigzag channels, goldfish circling the pool, falling petals, gardener working a lever, reader breathing.
- Measured: qa determinism ✓, no popping, 3 ms/frame.
- Still improvable: figures are too small and too plain; the text blocks are fake cursive; the ground lacks layering.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
