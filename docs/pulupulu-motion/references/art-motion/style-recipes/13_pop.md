# 13_pop · 1962 Pop (Lichtenstein comic panel + Warhol four-panel)

File: `scenes/13_pop.js` (~230 lines). Performance: warm average 6ms, max 9ms, first frame ≈45ms; determinism passes; lt 0.34→0.46 motion differential 11.6% of pixels. On-screen dwell 0.47s (T12 yellow lightning halftone transition 0.16s).

## Pipeline
1. **Ben-Day dots = `createPattern`, free**: one pitch×pitch tile drawing 4 corners + centre = 5 circles = a 45° grid (diagonal spacing pitch/√2). Wall: pitch 24, r5.6, blue `#2f5cc8` on white (diagonal 17px, matching the 17px period measured by FFT from the original); skin: pitch 13, r3.3, red `#e2483c` on skin tone `#fae0cc`; yellow field: pitch 14 r2.2 α0.18 faint print dots. Skin uses `fillStyle = pattern; fill(path)`, two orders of magnitude faster than `PAINT.halftone` (per-dot getImageData), and the pattern is aligned to screen coordinates so it doesn't "swim" as the character moves.
2. **Full background cached `pop_bg`**: comic panel border 6px black; white skirting 754–792 (6px black lines above and below); yellow field 796→990/1003 (horizon slightly slanted); red band; MEANWHILE... (`Bangers-400` 46px, black frame 5px on yellow); Warhol white frame + blue window-sill line; blue chair; paper grain.
3. **All characters are "thick 5px black outline + flat fill"**, one function `ink(c, path, fill, lw)` end to end; highlights are thick short white strokes; shading uses `hatch()`: inside an elliptical clip, black diagonal lines 10px apart, 3.5px wide.

## Motif animation
- **Warhol four panels swap palettes**: 4 palettes (bg/face/lower face/eyeshadow/lipstick), `step = floor(lt·11)` (≈ a swap every 5.5 frames; the original swaps at frames 601, 605/606, 612), panel i uses set `(i+step)%4`. Cat face = RIG.smooth's 9-point head shape + lower-face ellipse + black block on the right (misregistered silk-screen shadow) + eyeshadow/lipstick/nose/whiskers; two white glass reflections in the top-right panel.
- **Thought bubble's three dots flash in sequence**: the original's "dot1 frames 612–615, dot2 614–617, dot3 616–618" → one 12-frame loop, dot k is lit (r20, hops up 6px) when `((f-2k) mod 12) < 4`, otherwise r12. Bubble = 10 circles all stroked 11px black first, then all filled white (the cheapest way to write a union outline).
- **WIGGLE WIGGLE burst frame shakes**: 30fps-stepped hash jitter ±8px/±6px/±0.03rad; outer white burst (14 spikes, radius 128/178 with randomness) + inner yellow burst + two lines of `Bangers-400` 82px red text (12px black stroke + 4px black drop shadow); 10 black action-line triangles around it pulse in length `0.85+0.25·sin(40lt+2i)`.
- **Cat wiggles its rear, ready to pounce**: era-specific deformation from RIG.cat's anchors — crouch: body uses a custom 10-point outline (origin at `K.box`), head `K.headC + (22,104)` dropped low and tight to the body, white oval front paws stretched forward; wiggle: `wig = sin(lt·2π·6)·16` (6Hz, ~3 wiggles in 0.47s), point weight `clamp((560-x)/140)` → the closer to the rear the bigger the displacement, lifting by `|wig|·0.6` at the same time; stripes and tail follow the same deformation; three curved action lines beside the rear move with the wiggle.
- **Girl holds the cup**: RIG IK holds the cup; cup = white cup + blue diagonal stripes + coffee; steam as two black wavy lines jittering at 14Hz.

## The girl (Lichtenstein)
- Big golden waves: hair mass (19-point smooth, trailing edge bulges `sin(2.1i+4t)·14`) + 7 curl circles (r30–48, arranged along the trailing edge), **stroke all 10px black first, then fill all yellow = union outline**; inside each curl a 4.5px black C-shaped arc + a dark gold `#d9a514` arc = that sculptural Lichtenstein curl; 5 black S-shaped strands, 2 white highlights.
- Skin (face, neck, hands, legs) all red Ben-Day dots; red dress (cut at the knee, hem clipped with a curve, not a rectangle) + white highlight band; two dotted legs + red high heels (7-point polygon); big eyes (white sclera 12×8.5, blue iris r7, highlight dot) + 3 thick lashes + brows moved up 5px; lips enlarged.

## Palette
Black `#141414`; paper `#f3eedb`; blue `#2f5cc8`; yellow `#f7d52c`; red `#d8232a`/`#a8161c`; white `#fbf8ee`; skin `#fae0cc` + dots `#e2483c`; blonde `#f8d62c`/`#d9a514`; cat `#f39a2c`/`#c4561a`; Warhol backgrounds `#9ccf3a/#e0359a/#2fc0b0/#f08a2a`.

## Pitfalls
- Drawing the cat head at its RIG position leaves it hanging above the crouched body (a gap); in the crouch pose the head has to drop ~100px into the body.
- The first version of the hair was one sheet of yellow with a slight wave; from a distance it looked like a cloth draped over the head. Lichtenstein blonde is recognisable because of "curl circles + black C arcs".

## Still improvable
- The girl in the original has a tear and a white collar (the classic Lichtenstein crying girl); the design sheet dropped them and I didn't add them either; a speech balloon would make it more "comic" if wanted.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
