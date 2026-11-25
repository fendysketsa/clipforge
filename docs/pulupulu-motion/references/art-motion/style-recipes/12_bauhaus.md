# 12_bauhaus · 1923 Bauhaus poster

File: `scenes/12_bauhaus.js` (~210 lines). Performance: warm average 5ms, max 9.5ms, first frame ≈85ms; determinism passes; lt 0.34→0.46 motion differential 4.9% of pixels (black bar, grid window, concentric arcs, cat, ball, doll all moving). On-screen dwell 0.47s (T11 blue square/red circle/yellow triangle/round hole transition 0.20s, origin (1330,590) ≈ centre of the red circle).

## Pipeline
1. **Full background cached `bh_bg`**: off-white aged paper `#ebe3cf` + 320×180 fbm thumbnail upscaled at α0.5 (aged mottling) + a thin diagonal line running (40,170)→(1900,840) (behind the window) + black horizontal bar top-left (60,61,256,13), red vertical bar (292,105,24,468) + vertical "bauhaus" (`Poppins-800` 210px, `rotate(-π/2)` then horizontally scaled to exactly 820px long, origin (262,1000), read bottom to top) + small grey square + ground line (345,898)-(1860,915) + yellow right triangle + katze (Poppins-800 150px, red `#d3262b`) + two lines of Poppins-600 31px bottom-right + black-faced table with chrome tube legs (three-colour linear gradient) + Breuer cantilever chair (same path stroked 15px dark grey / 10px chrome / 3px highlight offset 2px) + two grain layers (dark specks 0.02 density α0.35, old-print black blotches).
2. Red circle cached separately at 520²: base colour + `source-atop` fbm light patches α0.55, imitating the uneven ink of screen print / lithography.
3. Characters and composition are all geometric solids: no curved strokes anywhere, only circles, squares, triangles, thick bars.

## Motif animation
- **Long diagonal black bar turns like a clock hand**: angles measured frame by frame from the original (frames 575–579 28°, 581 33°, 583 37°, 585 42°, 587 46°, 591 49.5°) written as `deg = 28 + 21.5·easeOut(clamp((lt-0.26)/0.22))`. Pivot = hub centre (1125,195) (confirmed by comparing frames 576/590 in the original: the hub stays put, the lower end sweeps down), bar 27px from -432 to +150, thin parallel line offset 30px, short red bar offset -30px, the hub's inner arc turns with it.
- **Mondrian grid window rotation**: 4×4 grid (inner frame 366..794 × 126..561, cells 100×101, gap 9.5), 6 cells take part in the rotation, 13fps stepping `step=floor(lt·13)`, each cell on a different phase, swapping only when `(step+2·sw)%9 < 6` (not on every beat, so the rhythm isn't mechanical); rotation colours use only red yellow blue cream light blue grey. Pattern cells (9px graph paper) and quarter-circle cells preserved.
- **Concentric arcs**: 6 arcs right of the red circle, start phase wobbling `sin(9lt-0.7i)·0.05`, radius breathing `±3`, arc length sweeping from 55% to 100% within 0.4s — like sound waves pushing outward.
- **Steam over the cup**: one 2.2px sine hairline (26 cycles/170px, `-18t` travelling wave), linear-gradient fade-out.
- **Cat bats the ball for a roll**: right front paw `tap = sin(clamp((lt-0.05)/0.16)·π)` extends 36px forward then retracts; blue ball r31 rolls from x712 to x816 over `lt 0.13→0.47` with easeOut, **rotation = displacement/radius** (white diameter line + white dot show it rolling), with two speed lines behind it while rolling. Tail = 26px thick orange arc + dashed dark-orange stripes of the same width, angle following `choreo.tail·0.5`.

## Geometricisation of the characters (all anchors from RIG)
- **Schlemmer doll**: head = circle r70 (`G.A.headC + (14,-18)`), golden geometric hair piece = sector of the rear half of the head (-1.95→1.15rad) + forehead triangle + bun circle r34 + rear half-circle hair piece (`G.A.back`); face = black vertical-bar eyes (become horizontal bars when blinking), red square cheeks, short black mouth. The whole head group rotates about `G.A.neck` per `G.tilt` (tilts up when drinking). Torso = blue trapezoid + rear black trapezoid (undulating with breathe); skirt = black sector r178 + blue trapezoid; limbs = thick black rod with round ends, joints = cream disc + 5px black ring + black centre dot. The near arm uses `G.A.shoulder/elbow/hand` directly (the RIG IK arm holding the cup), the far arm lies flat on the table (reproducing the hand reaching toward the tabletop in the original).
- **Cat**: body circle r100 (derived from `K.box` as (536,805), scaled with breathe) + 4 dark orange horizontal bands on the left (clipped inside the circle) + cream sector lower-right (orange/white blocks); head = 104 square (`K.headC + (14,48)`, turning slightly ±0.08rad with the tail phase) + yellow triangle ears + cream lower face + dark orange forehead band; eyes = white circles + black vertical-bar pupils.

## Palette
Paper `#ebe3cf`; black `#161514`; red `#d3262b`; blue `#2a58b4`; yellow `#efc12f`; light blue `#b9cee0`/`#a6c0da`; grey `#c6c3bb`; cream `#f2ecdf`; orange `#ee8a2a`/`#c25a14`; chrome `#c9c9c6`.

## Pitfalls
- The first version computed cells at 107px and overflowed the black frame by 16px on the right — the window size has to be derived backwards from "inner frame width - 3 gaps".
- I put black into the rotation colours; when it landed on a black cell the whole window suddenly got heavy, like a broken cell — removed.
- The doll's mouth was first drawn as a long black bar sticking out past the head, as in the original; on the girl's face it read as a cigarette, so it became a short horizontal bar inside the head.

## Still improvable
- The cat's head/body were moved down relative to the RIG skeleton (so the square head sits on the round body); during the transition the cat head sits ~50px off from the neighbouring eras.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
