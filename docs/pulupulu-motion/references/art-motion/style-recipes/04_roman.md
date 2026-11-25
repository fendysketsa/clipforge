# 04_roman · 79 AD Pompeii Mosaic — Technique Notes

File: `scenes/04_roman.js` (about 330 lines). Final self-check: warm max 17ms / mean 13ms (1920×1080), init 206ms (once, at boot), 17,871 tesserae, of which 13,067 are recolored every frame inside the dynamic region. Determinism passes.

## Core idea: lay out once, let color flow from tessera to tessera each frame

Mosaic animation should look like this: the tesserae themselves are fixed in the wall, and what moves is color flowing from one stone to the next. So the renderer is split in two halves.

1. **init (`build()`, 206ms)**: work out where every tessera is, how big, which way it faces, which pixels belong to it, and how its bevel is shaded; store that as `ID` (Int32, the tessera index per pixel, -1 = grout) and `SH` (Uint8, per-pixel shading, 128=1.0).
2. **Per frame**: repaint the flat underlay, `getImageData` once, then sample color at the center of each dynamic tessera (plus that tessera's fixed color jitter), then fill pixel by pixel inside the dynamic rectangle with `color×shade>>7`, and finally `putImageData` onto its own offscreen canvas and `drawImage` that onto `c`.
   - Pitfall: **never `putImageData` straight onto `c`**, because it ignores the engine's punch zoom and transition clipping. Write to an offscreen canvas first, then `drawImage`.
   - Each frame touches only about 1,000,000 pixels (4 border bands, inside the frame, the girl, the cat); a JS loop costs about 5ms. Every offscreen context uses `{willReadFrequently:true}` so `getImageData` stays fast.

## Tessera layout (andamento: contour-following rows)

Simplified from the approach in Hausner 2001, "Simulating Decorative Mosaics".

- **Structure map**: static underlay plus frame-0 cat and girl (without the moving near arm), downsampled to 960×540. Any pixel whose summed RGB difference to its neighbour exceeds 34 is marked as an edge, and the frame-band boundaries in the category map are marked as edges too.
- **Distance field**: exact Euclidean distance transform via Felzenszwalb–Huttenlocher (two passes of 1D lower envelope), about 20ms at half resolution.
- **Walk contours to place tesserae**: candidate pixels satisfy |d−(k+½)s|<1.5 and k < that class's ring count, i.e. the isoline bands of the distance field. Starting from an unvisited candidate, walk the 8-neighbourhood preferring the candidate "most aligned with the previous step" (direction smoothed 0.6/0.4), and drop a tessera once the distance from the last one is ≥s. Tessera orientation is the tangent of the distance-field gradient. A spatial hash guarantees any two tesserae are ≥0.8× the mean size apart.
- **Regular rows to fill holes**: lay a half-offset grid per class (row jitter ±5%, column jitter ±9%). Minimum-spacing test 0.86; place if it fits. This step closes the holes between contour rows and along the center line as well.
  - Pitfall: at first the grid was only placed where "distance ≥K×s", which left narrow shapes (the cat's tail, 26px wide) with no tessera at all and the whole tail showing grout. Restricting the test to minimum spacing alone fixed it.
- **Border bands laid separately**: each edge lays 11 rows in its own local coordinates, tesserae 7.6px, with width along the edge randomized 0.86–1.14; corners are 11×11 squares.

| Class | Tessera edge px | Contour rings | Color jitter |
|---|---|---|---|
| Wall | 12 | 1, then regular rows | ±8%, 7% of tesserae darkened an extra 12% |
| Halo (white rim outside people/cat/objects) | 11 | 9 (the whole halo follows contours) | ±5% |
| Girl's body / objects | 10 | all contour-following | ±5% |
| Girl's face, cat head | 6 | all | ±4% |
| Hair | 8 | all | ±5% |
| Inside volcano picture | 9 | 2 | ±6% |
| Outer border band | 7.6 | rows along the edge | ±5% |
| Lettering | 7 | all | ±5% |
| Ground band | 13 | 1 | ±6.5% |

Beyond the jitter in the table, every tessera also gets a ±7 additive grayscale jitter. 9% of tesserae skew warm (+12,+4,−8) and 7% skew cool (−6,0,+9).

## Tessera shape and grout: weighted L∞ Voronoi

- Each tessera is a rotated square. Its four half-edge lengths are drawn independently from `s/2×(1.08–1.28)`, and the rotation angle is jittered a further ±0.06rad. The distance from a pixel to tessera k is `D=max(|u|/h±, |v|/h±)`, where (u,v) is the pixel's position in that tessera's local frame.
- Rasterizing records, per pixel, the smallest D1, the second smallest D2 and the associated tessera index; cost is 1.5h over each tessera's bounding box.
- **Grout**: a pixel counts as grout if `D1>1`, or `(D2−D1)·h/2 < g` (g = clamp(0.1s, 0.75, 1.25)px) — that is, near the bisector between two tesserae. Seams therefore come out about 1.5–2.5px wide and the stones get irregular edges "cut" by their neighbours, like real chisel work.
  - Pitfall: half-edge lengths initially came from `s/2×(0.9–1.1)`, making tesserae smaller than their spacing; grout then covered about 40% of the area and everything looked sparse. Making each tessera 8–28% larger than the half-spacing and letting the bisectors cut them packs the stones tight. This one change is the key to the material feel.
- **Bevel shading**: within 2.2px of an edge, brighten or darken ±16% by the dot product of the outward normal and the light direction (−0.6,−0.8) (upper left lit, lower right dark). Add a dome term `−5%·D1²` and ±3% pixel grain.
- Grout color: `rgb(112,103,92)` ±8 noise.

## Flat underlay and palette

- Wall `#e4ddcd`, halo `#f5f1e8` (every person and object is outlined with a 44–50px halo, and tesserae align along it into a white rim), outline `#46322a`, 8px outline (face 8px so it lays in whole rows).
- Picture frame: red `#a8322a`, then inward a deep-red `#7c221d` line, a gold `#d0a23c` line, and a dark line.
- Volcano: its three faces light `#7c84b8`, mid `#4e5796`, dark `#2f3672`; sky `#9ec0d8`→`#d3e3e4`; slopes `#6f9341`/`#92b254`; ground `#cba344`; cypress `#2b5a2f`; lava `#d64a22`/`#f2952c`.
- Girl: stola `#efe7d5`, two red stripes at the hem `#a8322a`; red shawl in three pieces (draped diagonally across the back, one across the knees, one falling at the front opening), fold lines `#7c221d`, with a gold brooch; the short cuff is a circle of radius 62 centered on the shoulder cut into the upper arm, with a red edge; blond `#dcaa42`, layer lines `#9c6c1c`, spiral bun at the back of the head; the red hair ribbon is a cubic bezier rotated with the head tilt. Eyes are drawn as a 10×6 white plus a dark blob of radius 5.5, so they land exactly as "one white, one dark" 6px tesserae.
- Cat: orange `#dc8530`, shaded back `#c06a24`, stripes `#9c4818`, white `#f7f2e8`, big amber eyes `#e9c22c` (radius eyeR×1.65), red collar `#b02a22` with a gold pendant. The body is smoothed with `RIG.smooth(K.bodyPts)` into a pear shape, replacing the old polygon. Tail rings are drawn with a dashed line `setLineDash([9,13])`.
- "CAVE CATTVM": **hand-written monoline heavy-stroke letters** (C from an elliptical arc; A, V, E, T, M from polylines), stroke 14px, cap height 60px, tracking 16, horizontally scaled to 600px wide.
  - Pitfall: filling Cinzel-700 text directly breaks thin horizontal strokes at 7–9px tesserae (E becomes F, the A loses its crossbar), and tight tracking welds letters together. After three rounds the conclusion is "mosaic lettering = monoline heavy strokes, roughly 2 tesserae wide per stroke".

## Motif animation (this segment runs lt 0–0.94s, drawn through 1.29s during the T04 transition)

- **Four-edge wave pattern flowing clockwise**: each edge switches to local coordinates with `setTransform` (u clockwise along the edge, v inward from outside) and draws the same Vitruvian scroll: starting from the inner black band, the spiral closes from r 24 to 5 over 2.25 turns, line width 13, period 81px. Phase is `42·lt + 81·easeInOut((lt−0.485)/0.365)` — constant drift throughout plus one extra cycle over the source's frames 226–248. Tessera positions do not move, so black and white flow across the stones, which is exactly what a mosaic in motion looks like. Between 0.4 and 0.9s, 20% of the border-band pixels are changing.
- **Vesuvius smoking**: the crater is only 70px below the frame top, so smoke rising straight up is clipped almost immediately and never seen (the first version fell into this). Instead the whole ash-cloud band drifts right at 55px/s (period 380px), plus 9 puffs of smoke (dark `#3f3c3a`→light `#a29c94`) hugging the sky and drifting low to the right, plus 12 sparks (10px squares on parabolic paths) and crater lava pulsing. 4.4% of pixels inside the frame are changing.
- **Cup raise**: timing from `choreo.cup/sip`; the cup is a gold kantharos with white stone steam at the rim, opacity 1−0.85·cup. The path is a hand-written `armPose` (see "Review rework" at the end).
  - Pitfall: with 15px wall tesserae the hand and cup smeared into a blob inside the big stones. For a while the arm-swept area was given its own 8.5px tesserae, which turned into a pale patch when still; the final fix was a uniform 12px across the whole wall.
- **Cat**: tail uses `choreo.tail×1.6` (the native amplitude is too small to read at 9px tesserae); when blinking, the eyes become orange tesserae with one dark line.

## Performance and the dynamic rectangle

- The dynamic rectangle is computed at init from the bounding boxes of sampled poses (cup stepped 0.05 from 0 to 1, sip at 0/0.15, cat tail within ±0.75), expanded by 58px to cover the halo and the steam. Outside the rectangle is the static mosaic from frame 0.
  - Pitfall: the rectangle must be big enough, otherwise tesserae straddling the boundary show half new color and half old.
- Across the whole-film timeline, every frame in the Roman segment (including the two transitions in and out, drawing both old and new layers) stays under 40ms, apart from the one-time cold cache of other eras when first entering a transition.

## What to know when self-checking

- `selfcheck`'s "motion diff 0.2↔0.7" is contaminated by the engine's beat punch zoom. Below lt<0.37 the whole frame is scaling, and it reports 68% — that is not the painting moving. Measure 0.4↔0.9 (after the punch ends) instead: 6.2% of the whole frame, of which border bands 20.4%, girl 8.4%, picture frame 4.4%, cat 0.8%.

## Still could be better

- When the girl lifts the cup to her lips, hand, cup and face crowd together and blur slightly at the 6–8.5px tessera scale.

## Review rework (second round)

- **Cat**: anchored at the feet (540,905) and scaled to 0.85 with a canvas transform (category map and dynamic rectangle scaled in step); ear tips drop from y≈540 to about 590 and the halo no longer touches the frame. The head was redrawn as a front-facing Persian-style cat: two big R17 amber round eyes, black vertical pupils, 7px dark eye sockets, an 11px dark stroke around the head, and 6px detail tesserae in the category map too, so the contour lays in rows.
- **Cup-to-face smearing**: no longer uses the skeleton's original cup path; uses a hand-written `armPose`. The cup travels a quadratic bezier "tabletop → forward and up (1150,470) → in front of the lips", ending with the rim's right end against `G.lips[0]` at a tilt of 0.15rad (8.6°). The hand supports under the foot (offset interpolated from (28,34) to (3,44)), IK with the same 165/122 arm lengths and elbow direction. The forearm stands in front of the chin, so nose, lips, chin and eye all show. Face outline thickened to 10px.
- **Patch feel**: removed the "arm-swept area at 8.5px" class. Wall tesserae are uniform 12px (closer to the source's wall tessera scale too); the dynamic region's wall shares the surrounding layout and only recolors per frame, so no boundary is visible.
  - Lesson: never change tessera size just for detail in the dynamic region — when the shot is still, it reads as a patch.
- After the rework: warm max 17.1ms, mean 13.0ms, determinism passes.

## Shot-review rework (third round, report items 3 and 4)

- **The border does not look like it is scrolling**: across the whole-film timeline (renderFrame) it genuinely moves, but with "stones fixed, only colors change" the scroll shifts only 1–3px per frame, and after quantization to 7.6px tesserae it barely lights up on the motion heatmap.
  - Fix: turn the border into a "conveyor belt". At init, prebake a tessera strip 2106px long (26 periods). The pattern period is 81px and the tessera layout also loops on 81px: 11 tesserae per row, widths random but normalized to exactly 81px, and the jitter reused per period. So the whole strip can be shifted to any phase and still join seamlessly.
  - Each frame: once per edge, `c.transform(edge local coordinates)`, then clip and `drawImage(strip, BW−2·81+phase, 0)`; the stones travel clockwise with the pattern. Corner squares stay static.
  - Phase changed to `15·lt + 81·easeInOut((lt−0.485)/0.365)`, dropping constant drift from 42 to 15px/s and leaving the main motion to the single cycle over source frames 226–248.
  - Still-segment motion (motion.py, 480×270 mean frame diff, frames 222–253): the replica rises from 1.98 to 4.62, source 2.90. At 42px/s drift it was 5.5.
  - Rule: when slow pattern displacement is smaller than the tessera size, "color-only" change gets eaten by quantization — either move the stones too, or make the displacement far larger than a tessera.
- **The cup is unreadable**: the cup was removed from the underlay and replaced with a `cupSprite` patch of 4.4px tesserae. Contents: the kantharos at 1.3× scale — dark outline tesserae, gold body (shaded on the right), bright rim with dark interior, two handles, foot. Each frame it is laid over the mosaic as a whole, at `armPose`'s position and tilt. Steam became two columns of white square stones rising along a sine (`steamTiles`) with grout edges. Only the cup's white halo stays in the underlay.
  - Rule: props narrower than 3 tesserae do not read in a fixed layout; make them into movable "inlay pieces" (emblema-style patches).
- **The face does not read its features**: face tesserae changed from 6px to 5px. Eye white 13×7, dark 8×7 — about 3 dark stones plus white; lips changed to red `#a8282a`, an 8.5×6 ellipse, about 2 tesserae; brows 6px dark brown. Viewed at half size on 1080p, eyes and mouth read.
- After the rework: warm max 20.9ms, p90 17.4ms, mean 13.9ms, determinism passes.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
