# 01_cave · 40,000 BC Cave Painting (code-only)

File: `scenes/01_cave.js` (about 330 lines). Final performance: warm max 22ms / mean 21.1ms; cold (cache build) happens at engine boot; determinism passes; 3.9% of pixels differ between 0.2 and 0.7s in the motion diff.

## Pipeline
1. **Rock wall (fully cached, `cave_relief`/`cave_bg`)**
   - Compute the height field at half resolution, 960×540: `fbm(x·0.0022,4oct)·1.0 + fbm(x·0.011,3oct)·0.16 + noise(x·0.05)·0.03` (coordinates use full-resolution pixels).
   - Finite differences ×52 give the normal, light direction L=(-0.55,-0.62,0.56) (upper left), `shade = clamp(0.5+(dot-0.56)·0.9)`; the base color is mixed between `#ce925a` (light ochre)/`#6e4426` (dark)/`#b6643a` (red patch) with two low-frequency fbm layers, then multiplied by (0.72+shade·0.55). Upscale to full screen with smooth interpolation → soft undulation.
   - Layer two passes of `P.grain` (dark 0.22 density α0.32, light 0.10 α0.28) for the granularity; 10 random-walk cracks (turn ±0.45rad per step, step 14–40px, 12% chance to branch), with a bright line offset +1.6px laid under the dark line → incised look.
   - Vignette: radial gradient r 260→1180, outer ring α0.8; a static warm light at the center uses lighter (α0.36) to light only the rock wall.
   - **Pitfall: with a large mid-frequency coefficient in relief (0.35, ×60 on normals) the whole wall becomes camouflage/dunes, and once the texture is overlaid the figures look like they are in camo gear**. Only after dropping the mid-frequency term to 0.16 and normals to ×52 did it read as rock face.
2. **"Paint soaked into the rock"**
   - Every shape uses one drawing routine, `shape()`: first stroke once with the **fuzz pattern** (sparse charcoal dots, width 2lw+7) → then stroke with the **ink pattern** (charcoal black, 7% random holes plus large holes where noise >0.58, width 2lw) → finally a flat fill covering the inner half-ring. Effect = solid charcoal line + sprayed fuzzy edge, and painter order handles occlusion for free (the arm covering the garment's line).
   - Charcoal "boil": two 256 patterns are randomly translated every 1/9 s with `pattern.setTransform`; the geometry stays put while the grain jumps — cheaper than jittering paths and it does not deform.
   - After the whole paint layer is finished, `source-atop` one `cave_figtex` pass: rock shadow → black α(0.5-v)·150, lit areas → warm white α(v-0.5)·50, dark/light grain, low-frequency wet/dry patches α≤70. **The paint layer gets only one full-screen composite**, hence 19ms.
   - All fills are opaque flats; color is "dirtied" by the texture. Never stack paint with multiply — chalk white (the cat's white) disappears.
3. **Negative handprints/paw prints**: Gaussian spray on a 320² scratch canvas (σ46·s 3200 points α0.15–0.6 + σ28 1400 points), then `destination-out` a solid hand-shaped mask, finally fill the mask with `#f6e2bc` at α0.3. **The hand shape must be filled into the mask piece by piece**: putting the palm ellipse and finger capsules into one Path2D and filling once lets nonzero winding cancel where subpaths run opposite, producing gaps (hit at r4).
4. **Firelight**: one radial gradient per frame, center (1000+40·noise(t·3.1), 540+26·noise(t·2.3)), intensity `0.13+0.09·noise(t·8.5)+0.04·sin(21t)`, **composited with overlay** (α = intensity×2.6). Outside it, add another vignette that breathes inversely to the fire. Pitfall: starting with lighter washed the girl's blond hair and hide to pink-white and killed the ochre saturation; overlay brought the colors back.
5. **Embers**: three `P.particles` groups (left 0–360 ×11, right 1540–1920 ×12, middle ×5), y drifting from 1110 to 120, life 5.5s; bright core r 2.2–4.6 + 3.2× halo, `|sin(6t+1.9i)|` flicker, `sin(q·π)` fade in and out at both ends, composited with lighter.

## Motif animation
- **Bison/horse, two poses**: `ph = floor(t·60/7)%2` (changes every 7 frames), two coordinate sets for the leg endpoints (extended/tucked), head ±0.07rad about the neck point, whole-body y alternating -3/+1px; the horse runs in opposite phase to the bison. Legs use only charcoal lines (as in the source); the body is a filled silhouette plus a 22px dark wash along the spine (Lascaux-style modeling).
- **Cup raise**: RIG's cup track was not used (tabletop→mouth, with the tabletop point on the girl's chest, unlike the source's "arm extended, cup held in mid-air"). Custom: `hold=(1084,506)` → `mouth=HP(1224,380)`, progress `k = choreo(max(0,lt-0.95)).cup` (the choreo curve shifted as a whole by 0.95s, matching the source's frame 58 start of the lift), arm via `RIG.ik2(G.A.shoulder, cup+(34,10), 170,128,-1)`; `RIG.girl({cup:k})` still handles the head tipping back and the small sip tilt. k reaches 1 at lt≈1.85 (end of the T01 transition).
- **Steam**: three charcoal lines `x0 + sin(13q − 11t + 1.3j)·6`, 58px tall, following the cup.
- **Cat**: RIG.cat's head/eyes/nose/earInner/stripes/tailPts anchors plus a hand-drawn pear-shaped body, white chest, white forelegs, thigh arcs; tail = three-layer stroke in fuzz/ink/orange + one cross-band every 4 sample points; blinking comes from choreo.blink.
- **Cat size (review rework)**: at native size RIG.cat's ear tips sit at y≈535, poking into the bottom edge of the mural frame (550). The whole cat is scaled by 0.86 with a canvas transform anchored at the feet (540,905) (translate→scale→translate, with RIG.cat itself still s=1); the ear tips land at y≈582, leaving about 30px to the frame bottom, and the feet do not move. Line widths scale ×0.86 with it and the difference is invisible.
- **Title**: `Kalam-700` 78px letterSpacing 7, horizontally scaled to 930px wide, `#9b2a18`, drawn into the paint layer (so it takes the rock texture too). α = t<0.933 ? 1 : 1-(t-0.933)/0.2.

## Motion-amount rework (review metric: still segment frames 21–84, 480×270 per-frame mean frame difference)
The replica scored 0.62 vs the source's 0.86 — too still. Only local motion was added, with no reliance on full-screen flicker:
- Firelight: intensity `0.14+0.11·noise(9.5t)+0.04·sin23t+0.03·sin37t`, center drifting ±60/±36px (was ±40/±26). Larger values were tried (±0.16, ±90px) and shot to 1.22 with a wobbling image, so they were dialed back.
- Embers 28→49 (left 20, right 20, middle 9), bright core r 2.6–5.4, halo α0.32 at 3.6×, flicker `0.3+0.7|sin|`.
- Handprints pulsing: each print gets a r=105 warm radial gradient (lighter) on top, α=0.2·clamp(0.5+0.9·noise(7t+3.7k)), each with its own phase.
- Bison/horse bob ±3→ 9px vertical, ±3px horizontal, head sway ±0.12rad.
- Cat head micro-motion (matching source frames 65–81): over lt 1.08–1.35 with a `sin(πq)` envelope, lift and turn −0.16rad about the neck point (596,680), push RIG.cat look to 1.5, ears micro-tremble ±0.06rad at 60Hz.
- Result: **0.62 → 1.06** (source 0.86); max 22ms per frame.

## Period-styling the girl
Red ochre `#9c3520` silhouette (face/neck/arms/calves), with the profile keeping a single almond eye (cream sclera + black pupil + one lash, blinking turns into an arc) — that stroke is the key to the "girlish" read; hair filled in yellow ochre `#cf8f2c` plus 6 `#6e3c0e` wavy strands (amplitude growing with length), with a wavy outline as well; the lower half of the strands gradually stop rotating with the head (the HB function) so the whole mass of hair does not whip around when she tips her head back to drink. Knee-length hide garment = G.torso + a hand-drawn hem (a ±16px zigzag fur edge every 15px), `#b06a2c` + 26 "round spot + 7 small dots" leopard rosettes + 18 short fur lines; seams are hidden by stroking both pieces' edges first, then filling them together.

## Palette
Wall `#ce925a/#6e4426/#b6643a`; charcoal `#21150d`; red ochre `#9c3520`/dark `#74261a`; yellow ochre (cat) `#c9772f`; blond `#cf8f2c`/`#6e3c0e`; hide `#b06a2c`/spots `#4e2610`; chalk white `#f0dfbf`; bison `#8c3d22`/head `#76301a`; horse `#cf8236`; stone `#c98c50`/`#c08048`; tabletop `#d49a5a`; handprints `#8e2a1a`; embers `#ffe082`.

## Still improvable
- The girl's body uses RIG's realistic curves and reads "too smooth" for a true cave-painting figure; a more primitive approach is to downsample the contour to 12–16 points and add heavy hand-drawn jitter.
- The rock relief is static; the firelight changes brightness but not shadow direction. To actually get "relief shifting under a dancing fire" you need two shade maps with different light directions, interpolated by the firelight (+1 full-screen composite).

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
