# 46_pissarro · Pissarro: The Flow of Life and Figures in Their Environment

Status: research recipe; the demo was rebuilt on 2026-10-16 under protocol 16 (see "v2 Production Run" at the end); neither self-assessment nor independent review reached 80, so it is not registered as a production run.

## Check First

Read [Cross-Scene Style Extraction](../15-style-transfer.md) first, then this card. The works are used to compare visual language; figures, objects, composition, and camera are not lifted directly. The stable features below are research generalisations; the implementation and transfer plan are hypotheses awaiting verification; official parameters or already-measured capabilities must not be claimed falsely.

## Scope

Prefer his Impressionist urban and rural language; the Neo-Impressionist pointillist phase is labelled separately and not mixed with loose brushwork in the same shot.

## Transferable Visual Language

- Brushwork: small directional colour touches build roads, buildings, vegetation, and figures — not random noise.
- Colour and light: weather and time of day govern local colour; environmental reflection persists within light and shade.
- Space: anything from a higher vantage point down to eye level at ground works; pedestrians and activity sit inside a credible environment.
- Modelling: figures are usually participants in an event, with position, scale, and action, rather than scattered decorative dots.

## Content That Varies by Brief

Paris boulevards, bird's-eye views, carriages, peasants, or rain are not mandatory; each scene re-sets its viewing point.

## Distinction from Adjacent Styles

Distinct from Renoir's soft modelling of figures, and from Sisley's landscapes governed by the large sky / ground relationship; this card is about lived activity happening inside an environment.

## Production Starting Point (To Be Verified)

Let street / interior surface strokes vary with direction and depth; keep stable seeds and regional masks for figure motion; crowding comes from the story, not from adding people to hide an empty frame.

Action speed, frame rate, camera, and score are set by this narrative; a quiet mood in the image is not the same thing as slow motion. Engineering integration follows the [Style Author Spec](../08-style-author-spec.md); an engine id is registered only after a new renderer has actually been built.

## Cross-Scene Test Prompts (Not a Fixed Template)

- Several people packing luggage in a shared office area.
- Automated sorting in a winter warehouse: equipment activity replaces pedestrians.
- A temporary rural clinic opening its doors: change the street subject and the viewpoint.

Pick tests with different subjects / spatial scales / subject types; running the full set every time is not required. Record still-frame and motion acceptance separately; keep uncovered ranges marked as to be verified.

## References and Evidence Boundaries

- [*The Boulevard Montmartre at Night*: the city and serial observation](https://www.nationalgallery.org.uk/paintings/camille-pissarro-the-boulevard-montmartre-at-night)
- [*The Avenue, Sydenham*: a different urban space](https://www.nationalgallery.org.uk/paintings/camille-pissarro-the-avenue-sydenham)
- [*The Pork Butcher*: a close-range labour subject](https://www.nationalgallery.org.uk/paintings/camille-pissarro-the-pork-butcher)

Primary museum / production material is used to check works and methods; encyclopedia entries only help with locating. Starting work still requires actually looking side by side at several original works or clips of different scenes and recording stable features and exceptions; a work list does not mean a multi-image visual experiment has been completed.

## Feedback After Use

Check this section's latest verified conclusions before use; what exists now is a technical check of a 6-second single-scene output; style fidelity and cross-scene visual verification are unfinished. Afterwards record only findings that affect results: date, subject, route taken, reference and output paths / hashes, problem, fix, verification status, and scope. Rewrite an invalid conclusion in place; do not append contradictory rules. Upgrade a research hypothesis to a production recipe only after it reproduces across scenes; for repeatable engineering problems, fix the tool first and test it. User preferences go into the taste profile separately and do not widen authorisation.


### 2026-10-15 · Single-Scene Trial Feedback

- Scene: autumn orchard; event: seen from behind, pushing a cart, the figure entering the environmental colour touches; route: code-drawn and animated.
- Check: deterministic re-run, full MP4 decode, and independent frame-sampling review; the short-film fast-motion metric is turned yellow under the existing gate and cannot be extrapolated to feature-length compliance.
- Boundary: this only proves the project runs and is watchable; artist / studio style similarity is still limited, and geometry, palette, or texture parameters cannot be treated as the final standard.

## v2 Production Run (2026-10-16, self-score ~75, taste items pending author)

- Route: `scenes/46_pissarro.js`. Shape layer (sky / distant church and hills / patchwork fields / path / six trees) → `MEDIUM.broken` (horizontal long strokes for the sky, ground following the lie of the land, multi-directional short strokes for canopies, complementary jitter of warm-bright against cool-dark) → cache; motion = drifting cloud, drifting leaf strokes on the top of the canopies, pedestrians (small canvas → broken → pasted back) walking nearer along the path.
- Subject: a country lane on market day, two farm women carrying baskets and one person pushing a cart; the lane carries the eye into depth; tree shadows cross the path and the fields.
- Measured: qa determinism ✓, no popping, 18 ms/frame.
- Still improvable: figure faces are white blobs; the church is covered by the near tree; canopies lean towards "fur balls" with no branches showing through; the distinction from Sisley (47) rests mainly on short, multi-directional strokes and orange-pink flicker inside the greens, and still needs side-by-side verification.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
