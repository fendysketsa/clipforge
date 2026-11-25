# 47_sisley · Sisley: Air, Weather, and Continuous Landscape

Status: research recipe; the demo was rebuilt on 2026-10-16 under protocol 16 (see "v2 Production Run" at the end); neither self-assessment nor independent review reached 80, so it is not registered as a production run.

## Check First

Read [Cross-Scene Style Extraction](../15-style-transfer.md) first, then this card. The works are used to compare visual language; figures, objects, composition, and camera are not lifted directly. The stable features below are research generalisations; the implementation and transfer plan are hypotheses awaiting verification; official parameters or already-measured capabilities must not be claimed falsely.

## Scope

His landscape language is the main established basis; interiors, close-up figures, and science fiction are transfer experiments — do not claim the artist already has mature examples of these.

## Transferable Visual Language

- Colour and light: sky and weather affect the ground, buildings, and water; not every image is sunny blue-green.
- Brushwork: lighter, broken colour touches follow the surface direction; distance simplifies while the near ground stays legible.
- Space: the aerial layers are continuous; structures such as the horizon and roads guide the viewing — not just a water backdrop.
- Modelling: small figures and buildings keep landscape scale; large figure close-ups need separate verification.

## Content That Varies by Brief

Rivers, bridges, clear weather, and the French countryside are not mandatory; snow, flood, or overcast can serve as variation controls.

## Distinction from Adjacent Styles

Distinct from the close-range colour-light field of Monet's water lilies; it also does not default to Pissarro-style dense activity or to Guardi's looser urban silhouettes.

## Production Starting Point (To Be Verified)

Unify ambient light and depth first, then handle the brushwork of sky, hard surfaces, and organic matter separately. When a new figure is enlarged, rebuild its structure and local stroke density; a small dotted figure cannot simply be scaled up.

Action speed, frame rate, camera, and score are set by this narrative; a quiet mood in the image is not the same thing as slow motion. Engineering integration follows the [Style Author Spec](../08-style-author-spec.md); an engine id is registered only after a new renderer has actually been built.

## Cross-Scene Test Prompts (Not a Fixed Template)

- A winter industrial park with no river.
- One boarding at a suburban bus stop after rain.
- Greenhouse maintenance indoors: a transfer stress test beyond the original landscape range.

Pick tests with different subjects / spatial scales / subject types; running the full set every time is not required. Record still-frame and motion acceptance separately; keep uncovered ranges marked as to be verified.

## References and Evidence Boundaries

- [National Gallery, Sisley collection and biography](https://www.nationalgallery.org.uk/artists/alfred-sisley)
- [*The Watering Place at Marly-le-Roi* and the snow series](https://www.nationalgallery.org.uk/paintings/alfred-sisley-the-watering-place-at-marly-le-roi)
- [National Galleries of Scotland: snow-scene comparison](https://www.nationalgalleries.org/art-and-artists/artists/alfred-sisley)

Primary museum / production material is used to check works and methods; encyclopedia entries only help with locating. Starting work still requires actually looking side by side at several original works or clips of different scenes and recording stable features and exceptions; a work list does not mean a multi-image visual experiment has been completed.

## Feedback After Use

Check this section's latest verified conclusions before use; what exists now is a technical check of a 6-second single-scene output; style fidelity and cross-scene visual verification are unfinished. Afterwards record only findings that affect results: date, subject, route taken, reference and output paths / hashes, problem, fix, verification status, and scope. Rewrite an invalid conclusion in place; do not append contradictory rules. Upgrade a research hypothesis to a production recipe only after it reproduces across scenes; for repeatable engineering problems, fix the tool first and test it. User preferences go into the taste profile separately and do not widen authorisation.


### 2026-10-15 · Single-Scene Trial Feedback

- Scene: train in a snowy field; event: the train passes through continuous snow and sky; route: code-drawn and animated.
- Check: deterministic re-run, full MP4 decode, and independent frame-sampling review; the short-film fast-motion metric is turned yellow under the existing gate and cannot be extrapolated to feature-length compliance.
- Boundary: this only proves the project runs and is watchable; artist / studio style similarity is still limited, and geometry, palette, or texture parameters cannot be treated as the final standard.

## v2 Production Run (2026-10-16, self-score ~80, taste items pending author)

- Route: `scenes/47_sisley.js`. Three layers each redrawn and cached: sky (cumulus 2600 wide: warm white body + pale violet-grey shadow side + warm yellow lit face, `MEDIUM.broken` horizontal long strokes), water (reflected sky light + mirrored, darkened reflections of houses / trees / poles, horizontal long strokes), and the scene above the water (half-submerged inn, poplars, utility poles, far bank). Motion = slow cloud drift, row-by-row water displacement growing larger nearer the viewer, the ferry (small canvas → broken → pasted back), wake ripples.
- Subject: a village landing after the water rose; a ferryman poles a boat loaded with wooden crates.
- Measured: qa determinism ✓, no popping, 14 ms/frame.
- Fixed: `broken` expanded outward by 14 px before blurring, and the target width of the row-by-row water displacement widened, removing a row of notched dots along the left edge.
- Still improvable: roofs read as one flat slab; the boat's reflection is too dark; figures are silhouettes only.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
