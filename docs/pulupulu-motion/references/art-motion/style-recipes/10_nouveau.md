# 10_nouveau · 1896 Art Nouveau (Mucha poster)

File: `scenes/10_nouveau.js` (about 300 lines). Performance: warm mean 29ms, max 37ms, first frame (cache build) ≈80ms; determinism passes (same lt rendered twice is pixel-identical); 13.1% of pixels moving in the lt 0.35→0.65 motion diff. The shot holds for 0.70s (T09 organic-wave transition 0.24s, growing out of (1330,320) = the girl's halo).

## Pipeline
1. **Fully cached background plate `nv_bg`**: three-stage vertical gradient gray-green→sage→peach (`#b9cba0`→`#cfd3a6`→`#ecc9a2`, laid only inside the inner frame 34..1886×32..907); dot pattern = ring r10 + center dot r2.6, row pitch 54, column pitch 62, odd rows offset 31 (diamond stagger), color `rgba(120,140,100,.38)`; a 240×135 fbm tile upscaled at α0.5 for lithograph mottling (hundreds of times faster than full-screen noise); mosaic floor band with a 20×24 cell and a 9-color cycle `(k*7+(k>>2))%9` scattered; green banner `#8fac80`; title `Marcellus-400` 76px, letterSpacing 12, 7px dark-brown stroke first then cream fill; gold frame = outer 6px gold `#c9a24a` + two 2px dark-brown lines inside and outside.
2. **Variable-width path `ribbon(pts, w(q))`**: the point list is first densified with Catmull-Rom (4–10 points per segment), then each point is offset ±w/2 along the normal and the result filled as a closed polygon. Every "whiplash line" uses it: stems, leaves, wrought-iron table legs, banner scrollwork, hair, steam. `swellW(wmax)` = pointed at both ends, thick in the middle (sine envelope) — that is the weight breathing of Mucha's line. Spiral terminator `spiral(cx,cy,r0,a0,turns,dir)`: radius decays linearly to 15%.
3. **Mucha's "thick outer contour, thin inner lines" — the whole-silhouette offset method**: the characters (cat + girl + hair + drapery) are all drawn into an offscreen layer L (RIG's both mode, lw 2 → inner lines occlude correctly in part order); then copy L, tint it deep brown `#4e3320` with `source-in`, and lay it under L on the main canvas at three offsets (-1.5,-1.5), (3.5,4.5), (2,2.5). Result: a 1.5px ring around the silhouette edge, a 4–5px thick edge on the lower right; inner lines stay 2px. Costs only 3 extra full-screen `drawImage` calls.
4. Grain `P.grain('nv', .05, warm brown, .14)` on the top layer, like lithographic printing.

## Motif animation (all must read within 0.7s)
- **Sunrise**: measured off the source (frame 509 (583,400) → frame 530 (576,299), ≈-5px/frame) and written as `sy = 400 - (lt-0.267)·288`, `sx = 583 - (lt-0.267)·20`; at lt=0 it sits at 477 (hidden behind the hills), by lt=0.7 it reaches 275. The hill color bands are drawn over the sun = free occlusion for "rising from behind the hills".
- **Leaded rays turning**: 14 radial leaded rays from the sun center r92→r420, angle `+lt·0.9·0.25` slowly turning with ±0.04 sway; the rays travel with the sun, so the whole window's glass divisions keep changing — the most eye-catching motion inside the window.
- **Stained-glass border**: along the arch's inner edge (straight sides + elliptical arc rx219 ry130) place a 14×14 glass chip every 17px, rotated to the tangent, cycling through 6 colors.
- **Poppies/lilies swaying**: flower-head horizontal offset `sin(7.5t+φ)·13 + sin(3.1t+2φ)·5`, stems are three-control-point ribbon curves with only the upper section pushed; the left and right clumps are in opposite phase; leaves at 0.3× amplitude.
- **Halo rotation**: the girl's halo R172, 18 round studs turning `+0.9t`, inner ring of 32 rose-window petals counter-rotating at `-0.63t`; cat halo R106 with eight-petal orange flowers `-1.1t` + a gold dashed ring travelling via lineDashOffset.
- **Hair**: first one big hair mass (16-point smooth, outer edge rippling by `sin(6t+y·0.035)·9`), then 7 locks down the back + 2 locks over the shoulders: each lock is a 12-point S-curve `sin(7.4q+φ-7t)·(6+20q)` (travelling wave moving downward), ending in a 1.2-turn spiral, width tapering 14–18 → 2.5, cream highlight core + fine deep-gold lines. 6 small curls on the crown's outer edge give volume. All points follow `G.A.headC`'s offset (they move with the head as she tips back to drink, following less the further down they are).
- **S-shaped decorative steam**: 3 cream ribbons (width 26/20/14) + 1.8px brown stroke + center line, `sin(4q+φ-6t)·(18+70q)` travelling wave, horizontal spacing spreading with height ×(1+2.6q), 34px spiral at the tip; overall `lean = -90 - 160·cup` tilting left — **pitfall**: choreo brings the cup to the lips, so steam rising straight up cuts across the girl's face; it must lean toward the window with cup.
- choreo: cup raise, head tilt, blink, tail swing and breathing all use RIG; the saucer stays on the table (so the tabletop is not empty once the cup is taken).

## Palette
Line `#4e3320`; gold `#c9a24a`/`#9c7a2e`; cream `#f6eedb`; skin `#f6dcc4`; blond `#e8bf55`/highlight `#f6dc8a`/shadow `#b9862a`; dress `#f4ecda`; pink drapery `#e6aaa5`/folds `#d48e8c`; poppies `#d9706a`/`#b4504b`, centers `#3f6a4a` + gold dots; lilies `#f7f2e6`; wrought iron `#3d7763`; cat `#e39a4c`/`#fbf3e3`/stripes `#c0672c`, eyes `#e6c040`; halo pink `#ebb8b2`, teal ring `#5f9a8a`, cat halo red `#b8473a`.

## Pitfalls
- **`drawGirl(mode:'line')` on the top layer draws the contours of occluded parts (the far sleeve) straight through the torso** (the 09 benchmark has this too). Fix: draw the lines inside an offscreen layer in both mode, in part order, then build the thick outer contour over the whole thing.
- Hair started as 7 long 34px-wide bands, like sausages or noodles; Mucha hair = a base hair mass + fine S-curled locks + spiral terminators, width ≤18.
- When self-checking diffs do not use frames at lt<0.33: the engine applies a 1.03× beat punch zoom within 20 frames of a transition start, and the diff lights the whole screen red.

## Still improvable
- The cat is still RIG's seated pose (straight white legs); the design sheet has a lounging fluffy orange cat. The Mucha flavor is currently carried mainly by the halo and the thick/thin line work.
- The title uses Marcellus while the design sheet has a rounder hand-drawn Art Nouveau letterform; a hand-written set of letter paths is possible.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
