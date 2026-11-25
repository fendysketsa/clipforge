# 26_vaporwave · 2011 vaporwave / cyber neon

> Source: migration test B (independent agent working from the read-only skill, 2026-10-04). After consolidation the scene code was ported to `scripts/art-motion/engine/scenes/26_vaporwave.js`.

Filename at experiment time: `scenes/c5_vaporwave.js` (about 210 lines). Review red flag: the top was pink in the first version and blended into the pink-toned skin, so it read as if she were wearing nothing. Changed to a lavender-purple trench `#8f7cf6` + white triangle collar + teal zip line. Median 49ms per frame; frame difference 25% (the VHS post-processing keeps the whole screen moving).

**Pipeline**: the whole picture is drawn into an offscreen S first, then VHS post-processing outputs to c (the counter is drawn by the engine on the top layer and is unaffected by the chromatic aberration).
1. Wall: deep purple vertical gradient `#0d0322 → #4a0f6a` + magenta radial light at the window, teal radial light at the sign. A teal light strip along the base of the wall.
2. **`glowLine(c, col, w, blur)`**: the same path is first stroked thick with shadowBlur as the glow, then stroked as a 2–3px near-white core line — that is the neon tube.
3. Sunset in the window: the sun is a yellow → orange → magenta vertical gradient, cut with `destination-out` into 7 horizontal slits whose width grows with depth (2 + q²·16), moving up as a whole at 0.9/s. The horizon is a wireframe mountain (magenta glow); below it a teal perspective grid scrolls toward the viewer; palm silhouettes sway left and right.
4. Ground: a magenta perspective grid, vanishing point (960,600), horizontal lines `y = 600 + 520/d`, d = k + 1 − phase (phase = 1.3t mod 1), line width thickening toward the foreground.
5. **The neon sign "カフェ" draws its own tubes as polylines** (no font dependency): each kana is 1–3 strokes in (u,v) unit coordinates. Each character flickers by per-frame hash: off when `hash(floor(30t), k) < 0.07`; "フ" additionally goes off with 22% probability when `f mod 17 < 5`, and dark purple tubes are drawn while off.
6. Win95 dialog TEA.EXE: grey body, navy gradient title bar, progress blocks `3 + 14lt` cells, percentage `18 + 70lt`. On the table, a marble bust (22-point profile silhouette, purple-grey gradient + vein lines + pink rim light + sunglasses gag).
7. Character: pink sweater, teal pleated long skirt, blonde hair + pink scrunchie. Glow outline "pink on the window side, teal on the back": the same set of paths stroked twice, clipped to the left and right halves of the screen respectively.

**VHS post-processing `vhs(c, S, t, lt)`**
- RGB separation: for each channel, draw S into a temporary canvas, `multiply` by a solid `#ff0000/#00ff00/#0000ff` to extract that single channel, then composite onto black with `lighter` at an offset. Offset amount 3 + 1.5sin(7t), with occasional (hash<0.12) +6.
- Tracking noise band: 70px high, scrolling down at `(520lt + 200) mod (H+160)`. Inside the band a horizontal offset every 6px of `±30·sin(πy/bh)`, overlaid with 90 white-grey noise lines.
- Scanlines: 4×4 tile pattern (row 0 α 0.28, row 2 α 0.12). OSD: PressStart2P "PLAY" + a hand-drawn ▶ (the font has no such glyph), blinking every 16 frames; date at bottom left, timecode running off lt.

**Palette**: magenta `#ff4fd8`, hot pink `#ff2f8f`, teal `#3ff6ff`, deep purple `#12052a / #2a0b4a`, sun yellow `#ffd84a`, orange `#ff8a3a`.

**Pitfalls**
- Full-width "ＶＡＰＯＲＷＡＶＥ", ▶ and Japanese are all missing from `lib/fonts` and silently fall back to a system font. Labels were switched to half-width + letter-spacing 7, and ▶ and the kana are drawn by hand.
- The character outline uses part paths, so the waistline and the arms/torso junctions glow too. That's acceptable for a neon line drawing, but for a pure outer contour you have to draw the silhouette into an offscreen first and then stroke the offscreen's edge.

---

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
