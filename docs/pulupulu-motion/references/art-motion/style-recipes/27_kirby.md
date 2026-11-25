# 27_kirby · 1966 Marvel Silver Age (Jack Kirby + four-colour offset)

> Source: migration test C (independent agent working from the read-only skill, 2026-10-04). After consolidation the scene code was ported to `scripts/art-motion/engine/scenes/27_kirby.js`.

Filename at experiment time: `scenes/k1_kirby.js` (255 lines). About 20ms per frame, frame difference 7.5%.

**Pipeline: the same geometry drawn twice**
1. **Colour plate layer**: paper `#f4ecd6` + flat fills + Ben-Day dots. Light blue wall carries C dots (pitch 9, r 2.7, 15°), dark blue floor carries purple dots (pitch 9, r 3.2, 75°), skin is red dots (pitch 7, r 1.5, 75°). **The whole layer is `drawImage(color, 4, 3)` = misregistration**.
2. **Ink line layer**: white ground, each part "white fill → shadow → 6px black stroke". Composited with `multiply` over the colour plate, so white = transparent. Filling each part white covers the lines of the parts drawn before it, so only the visible lines remain and no visibleLines is needed.
3. **Kirby's spotted blacks + feathering**: light comes from the window (LIGHT=(-0.86,-0.5)).
   - Black crescent: `path ∩ ¬translate(path, LIGHT·d1)`, d1=14. Done by `clip(path)` first, then `clip(…,'evenodd')` with "full-screen rect + translated path", then fillRect black.
   - Feather band: same construction with d2=30 to get a band, inside which parallel lines along the light direction are drawn (spacing 9px, line width 2.6).
   - Parameters (d1/d2): skirt 16/34, torso 14/30, sleeve 10/22, hair 12/26, cat body 16/34, tabletop 10/18.
   - One function gives any Path2D a Kirby-style shadow.

**Motif animation**
- **Kirby krackle**: a cluster of 16–26 black circles. Distances distributed as `R·rnd^0.7`, larger toward the centre (`R·(0.05+0.2·(1-d/R))`), reseeded at 12fps, radius pulsing with `sin(18t+i)`. 6 clusters travel along an S-shaped energy stream outside the window (`(k/6+0.42t)%1`); the stream is a yellow core band with an orange edge and a jagged ink border. Steam also uses krackle (4 small clusters floating up).
- **Speed lines**: cup-raise speed `|sin(min(1,lt/0.9)π)|`, 9 black lines trailing down from the cup base, length 70–180·v, jittering at 12fps; two motion arcs behind the elbow.
- **Onomatopoeia SLURRP!**: from lt 0.52 it pops out with `outBack`, in `Bangers-400` 132px (×0.82); black extrusion of 7 layers (each offset (0.8d,d)) makes Kirby's blocky dimensional lettering; the red letters carry a 46px band clipped into yellow (two-tone lettering); the base is a 26-point yellow explosion frame; ±3px jitter at 12fps.
- **Panels**: main panel 24..1534; the right panel is a cat face close-up whose pupils move up with `cup` (`lerp(14,-18,cup)`) and look left. Background is magenta ground + yellow dots + 44 converging black triangles (reseeded at 12fps) + 6 krackle clusters around the head. Caption box at the bottom "BUT THE CAT IS WATCHING!", caption box at the top left "MEANWHILE, AT TEA TIME...". The counter is made as a caption box with yellow ground, black frame and a black misregistered drop shadow, placed in the gutter at the top right.

**Character**: 60s red A-line dress, white Peter Pan collar (two ellipses), three black buttons on the placket, black headband (an elliptical arc in the head's rotated coordinate system, line width 11), flared hair ends (drawn in the `skirt` hook, behind the torso). The chair is a Saarinen Tulip chair.

**Pitfalls**
- The onomatopoeia was first placed at (1000,300) at full size and covered the window and the girl's face. Moved to (990,318) and scaled to 0.82.
- A large black ellipse on the right of the cat close-up made the cat look like a tortoiseshell; changed to a narrow crescent hugging the edge.
- The planet ring has to be split into a back half arc (drawn first) and a front half arc (drawn later), or the ring passes through the planet.
- **Still improvable**: the picture reads as "clean pop comic" and still lacks Kirby's blocky fingers, more extreme perspective and muscular tension.

---

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
