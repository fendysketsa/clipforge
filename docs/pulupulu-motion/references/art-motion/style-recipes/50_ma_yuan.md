# 50_ma_yuan · Ma Yuan: Off-Centre Gravity, Blank Space, and Spare Brushwork

Status: research recipe; the demo was rebuilt on 2026-10-16 under protocol 16 (see "v2 Production Run" at the end); neither self-assessment nor independent review reached 80, so it is not registered as a production run.

## Check First

Read [Cross-Scene Style Extraction](../15-style-transfer.md) first, then this card. The works are used to compare visual language; figures, objects, composition, and camera are not lifted directly. The stable features below are research generalisations; the implementation and transfer plan are hypotheses awaiting verification; official parameters or already-measured capabilities must not be claimed falsely.

## Scope

The scope is Southern Song Ma Yuan's landscapes and small poetic scenes; "Ma's corner" is an organising tendency, not a fixed lower-left template, and it is not equivalent to all Chinese ink painting.

## Transferable Visual Language

- Space: solid forms and unpainted space establish scale, direction, and situation for each other; blank space is not background waiting to be filled.
- Brushwork: structurally forceful contours, texture strokes, and tonal variation build the near-ground texture; distance is more economical.
- Composition: an off-centre centre of gravity, and branches / rocks extending past the frame, create the lead-in; direction, proportion, and subject can all be changed.
- Colour and light: ink and restrained colour work together; this is not desaturating the whole picture, blurring it, or adding rice-paper grain.

## Content That Varies by Brief

Ancient figures, landscape, one particular corner, a lone boat, plum blossom, or a large empty screen are not mandatory; blank space in a modern scene must also express space and event.

## Distinction from Adjacent Styles

Distinct from Fan Kuan's monumental massing and dense texture dots; distinct from generic ink-and-wash freehand — ink diffusion cannot be the sole identifying feature.

## Production Starting Point (To Be Verified)

Arrange the new event with solids and negative shapes first, then explain the structure with directional brush tips, wet and dry, and tonal depth near and far. Motion inside blank space may only reveal what the story needs; particles must not be added to "fill in the blanks".

Action speed, frame rate, camera, and score are set by this narrative; a quiet mood in the image is not the same thing as slow motion. Engineering integration follows the [Style Author Spec](../08-style-author-spec.md); an engine id is registered only after a new renderer has actually been built.

## Cross-Scene Test Prompts (Not a Fixed Template)

- One person waiting for a train on a winter-night platform.
- A folding tool opened on an empty workbench.
- Two people quickly passing an umbrella at a doorway: tests the relationship between motion change and blank space.

Pick tests with different subjects / spatial scales / subject types; running the full set every time is not required. Record still-frame and motion acceptance separately; keep uncovered ranges marked as to be verified.

## References and Evidence Boundaries

- [Met, *Viewing Plum Blossoms by Moonlight*: visual poetry and situation](https://www.metmuseum.org/art/collection/search/44638)
- [National Palace Museum display of *Spring Walk on a Mountain Path*](https://south.npm.gov.tw/SelectionsDetailC004100.aspx?Cond=c693cd84-df8f-4e6f-8724-d7025ac43c20)
- [Met, *Peach Blossom Spring* catalogue: keep checking different flower-and-bird and landscape works](https://resources.metmuseum.org/resources/metpublications/pdf/Peach_Blossom_Spring_Gardens_and_Flowers_in_Chinese_Painting.pdf)

Primary museum / production material is used to check works and methods; encyclopedia entries only help with locating. Starting work still requires actually looking side by side at several original works or clips of different scenes and recording stable features and exceptions; a work list does not mean a multi-image visual experiment has been completed.

## Feedback After Use

Check this section's latest verified conclusions before use; what exists now is a technical check of a 6-second single-scene output; style fidelity and cross-scene visual verification are unfinished. Afterwards record only findings that affect results: date, subject, route taken, reference and output paths / hashes, problem, fix, verification status, and scope. Rewrite an invalid conclusion in place; do not append contradictory rules. Upgrade a research hypothesis to a production recipe only after it reproduces across scenes; for repeatable engineering problems, fix the tool first and test it. User preferences go into the taste profile separately and do not widen authorisation.


### 2026-10-15 · Single-Scene Trial Feedback

- Scene: rain shelter at a cliff edge; event: a paper umbrella crosses the blank space on the wind; route: code-drawn and animated.
- Check: deterministic re-run, full MP4 decode, and independent frame-sampling review; the short-film fast-motion metric is turned yellow under the existing gate and cannot be extrapolated to feature-length compliance.
- Boundary: this only proves the project runs and is watchable; artist / studio style similarity is still limited, and geometry, palette, or texture parameters cannot be treated as the final standard.

## v2 Production Run (2026-10-16, second-round self-score ~78, first-round independent review 74, taste items pending author)

- Source anchoring: *Songs of Treading on Green*, *Plum, Rock and Stream Ducks*, *Spring Walk on a Mountain Path*. Signature: silk ground turning golden-brown, corner composition, axe-cut texture strokes with a broad flat side-brush, long weeping-willow branches, a tiny figure looking into emptiness, pale ink washing distant mountains with no contour.
- Route: `scenes/50_ma_yuan.js`. `MEDIUM.silk` ground (warp and weft lines + bleeding edges) → distant mountains rendered with blur → rocks (polygon clipping + broad flat `P.brush` axe-cuts + fine hard texture strokes + broken contours) → old willow trunks (thick lines with pauses and jabs) → motion: hanging strands (clustered, curved, of varied length, each drawn with `P.brush`, swaying in the wind), scholar (back view, robe folds in one stroke, silk left unpainted, sleeve raised pointing into the distance), boat, birds, water ripples → silk-weave multiply overlay.
- Measured: qa determinism ✓, no popping, 8 ms/frame.
- Lesson: hanging strands drawn as evenly spaced vertical lines read as a fence; leaving the figure unfilled with a back view + robe folds is the most reliable; use radial gradients for mist bands, because rectangular gradients show seams at the edges.
- Second-round experiments: trunks that widen in segments read as bamboo joints, and axe-cuts changed to polygonal wedges read as arrows; both were reverted. The current version uses one continuous thick line plus short bark strokes, and short broad brush axe-cuts.
- Still improvable: the rock axe-cuts are still too dense; trunk stroke endings are too blunt; the signature has only a seal and no characters.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
