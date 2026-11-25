# 42_guardi · Guardi: Air, Broken Light, and Loose Edges

Status: research recipe; the demo was rebuilt on 2026-10-16 under protocol 16 (see "v2 Production Run" at the end); neither self-assessment nor independent review reached 80, so it is not registered as a production run.

## Check First

Read [Cross-Scene Style Extraction](../15-style-transfer.md) first, then this card. The works are used to compare visual language; figures, objects, composition, and camera are not lifted directly. The stable features below are research generalisations; the implementation and transfer plan are hypotheses awaiting verification; official parameters or already-measured capabilities must not be claimed falsely.

## Scope

Mainly the air and the brushwork in city views and fantasy architecture paintings; avoid summarising all of his periods from a single Venice picture.

## Transferable Visual Language

- Brushwork: short, loose, dabbed bright strokes; contours break and resume, yet key structure stays legible.
- Colour and light: local bright accents held inside silver-grey or warm grey; air connects buildings, figures, and the distance.
- Space: near-to-far layering and small-scale figures establish the environmental volume; accurate surveying is not the only goal.
- Material: architecture, water, and sky each take a different stroke direction; the whole screen cannot be covered with a single kind of grain.

## Content That Varies by Brief

Venice, gondolas, canals, and ruins are not conditions of the style; water in every scene is not mandatory.

## Distinction from Adjacent Styles

Distinct from Canaletto's clear surveying; distinct from Sisley — it cannot be reduced to a generic Impressionism in bright blue-green.

## Production Starting Point (To Be Verified)

Build a legible urban / interior / industrial space first, then let edges and bright strokes loosen with depth. Bind texture to world or object coordinates; a moving shot must not re-roll random numbers across the whole screen.

Action speed, frame rate, camera, and score are set by this narrative; a quiet mood in the image is not the same thing as slow motion. Engineering integration follows the [Style Author Spec](../08-style-author-spec.md); an engine id is registered only after a new renderer has actually been built.

## Cross-Scene Test Prompts (Not a Fixed Template)

- Foot traffic at an elevated station after rain.
- Opening an inspection hatch in a dry hangar: no water, still air.
- A market on a neighbourhood square in winter: change season and subject scale.

Pick tests with different subjects / spatial scales / subject types; running the full set every time is not required. Record still-frame and motion acceptance separately; keep uncovered ranges marked as to be verified.

## References and Evidence Boundaries

- [*A Caprice with a Ruined Arch*](https://www.nationalgallery.org.uk/paintings/francesco-guardi-a-caprice-with-a-ruined-arch)
- [Francesco Guardi works at the National Gallery of Art](https://www.nga.gov/artists/1363-francesco-guardi/artworks)
- [*Lagoon Capriccio*](https://www.nationalgalleries.org/art-and-artists/13736/lagoon-capriccio)

Primary museum / production material is used to check works and methods; encyclopedia entries only help with locating. Starting work still requires actually looking side by side at several original works or clips of different scenes and recording stable features and exceptions; a work list does not mean a multi-image visual experiment has been completed.

## Feedback After Use

Check this section's latest verified conclusions before use; what exists now is a technical check of a 6-second single-scene output; style fidelity and cross-scene visual verification are unfinished. Afterwards record only findings that affect results: date, subject, route taken, reference and output paths / hashes, problem, fix, verification status, and scope. Rewrite an invalid conclusion in place; do not append contradictory rules. Upgrade a research hypothesis to a production recipe only after it reproduces across scenes; for repeatable engineering problems, fix the tool first and test it. User preferences go into the taste profile separately and do not widen authorisation.


### 2026-10-15 · Single-Scene Trial Feedback

- Scene: sailboat in the old harbour; event: the boat passes through broken light and loose building edges; route: code-drawn and animated.
- Check: deterministic re-run, full MP4 decode, and independent frame-sampling review; the short-film fast-motion metric is turned yellow under the existing gate and cannot be extrapolated to feature-length compliance.
- Boundary: this only proves the project runs and is watchable; artist / studio style similarity is still limited, and geometry, palette, or texture parameters cannot be treated as the final standard.

## v2 Production Run (2026-10-16, self-score ~78, taste items pending author)

- Source anchoring: *Venetian Lagoon*, *The Grand Canal and the Rialto Bridge*. Note that modern photographs (the Salute church) had got into the search results and were discarded. Signature: low horizon, a vast silver-grey-green air, slender gondolas, people reduced to a black body plus one or two dots of white and red, dry fast strokes, loose edges.
- Route: `scenes/42_guardi.js`. Sky (broad cumulus, warm bright over cool dark) / island tower / water (long bars of sky light + tower reflection) each pass through `MEDIUM.broken` (slender dry strokes, low saturation); the gondola and the punting figure are repainted on a small canvas with their reflections stretched and darkened; row-by-row water displacement; drifting cloud; birds.
- Still improvable: the tower's strokes lean towards stacked brick; figures are silhouettes only; missing Guardi's characteristic flickering white dots.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
