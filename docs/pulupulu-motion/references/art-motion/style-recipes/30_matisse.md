# 30_matisse · 1947 Matisse Jazz cut-outs

> Source: migration test C (independent agent working from the read-only skill, 2026-10-04). After consolidation the scene code was ported to `scripts/art-motion/engine/scenes/30_matisse.js`.

Filename at experiment time: `scenes/k4_matisse.js` (167 lines). About 25ms per frame, frame difference 9.3%.

**Composition**: wall = the Polynesia double-blue chequerboard (`#1d4fb8 / #4f95dc`, each cell a 240×236 cut-paper block), window = Icarus (cobalt ground, black figure, red heart, yellow star), floor = emerald `#1f9a5a` with a black skirting strip, tabletop is a black cut-out, chair is a yellow cut-out.

**Methods**
1. **Scissor polyline `cut(pts)`**: take a point every 14–24px along the contour, add ±2–2.5px seeded jitter, join the points with straight lines. Every self-generated shape is handled this way.
2. **Seaweed (key)**: one tapered stem plus 2×lobes **round-tipped capsule fingers** alternating left and right. Finger angle `±(1.05−0.55u)`, length `width·(1−0.45u)`, width `width·(0.34−0.12u)`. All sub-paths `addPath` into the same Path2D and are filled once with nonzero to get the union, so the shadow is also computed only once. **Do not use "modulate width along a spine"**: the first version did that and produced caterpillars and Z-shaped lightning bolts.
3. **RIG character hand-cut edge**: RIG gives no point list, so the whole character layer gets a per-pixel displacement. The static displacement field is `fbm(0.028x, 0.028y, 2)·9`, one set for dx and one for dy, processing only the bbox (330,470)-(1600,980), about 15ms.
4. **Paper shadow**: shadow offset (5,6), blur 4, `rgba(10,20,40,.3)`, to read as paper pinned to the wall.
5. **Gouache brush marks**: cache 2600 long streaks (60–300px, width 6–22, half black and half white, α .04–.13, slanted −0.25rad), applied over the whole picture with `overlay`.

**Motif animation**:
- The seaweed sways about its root like a sheet of paper, `sin(2.8t+φ)·0.13`, and the curled edge breathes with `scaleX 0.93–1.0`.
- Icarus: 7 irregular yellow stars, twinkling as they turn (scale `.82+.22sin(7t+1.9k)`); the black figure drifts up and down; the red heart beats (`1+.18·max(0,sin 9t)`).
- Two white birds beat their wings (scaleY `.55+.45cos 13t`).
- One sheet of pink paper tumbles and falls (scaleX=cos 6t).
- Steam is two small white cut-outs.

**Character**: Matisse's Romanian Blouse. White wide-sleeved blouse, a cobalt embroidery band down the placket (small red and yellow alternating triangles), red/blue embroidered cross-bands on the sleeves rotating with the arms (clipped inside upperArm), red long skirt + black belt, blonde hair as 5 cut-paper curls. Facial features use only cut-paper fragments: black almond eyes, a red lip triangle, pink cheek discs.
**Pitfalls**: the falling paper sheet's first trajectory crossed the girl's face; moved to the left wall. The counter is backed with a white cut-paper sheet, otherwise the black lettering is unreadable on cobalt.

---

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
