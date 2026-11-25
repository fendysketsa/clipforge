# 24_hopper · 1942 Hopper American Realism (hard light planes)

> Source: migration test B (independent agent working from the read-only skill, 2026-10-04). After consolidation the scene code was ported to `scripts/art-motion/engine/scenes/24_hopper.js`.

Filename at experiment time: `scenes/c3_hopper.js` (about 150 lines). Median 13ms per frame (first frame 54ms); frame difference 6.0%.

**Core method: the two-version cutout**: the same `room(g, K)` function is drawn into two caches with two palettes — the shaded version `SH` (cool green wall `#5d8679`, dark floor `#5b3d2b`) and the lit version `LT` (warm yellow wall `#efcf8f`, bright floor `#c98b52`). Each frame draws the shaded version first, then clips the lit version into the moving light-patch polygon; the light and shadow boundaries are naturally hard, and the whole thing can translate. Characters and furniture work the same way: `girl(c, K, G)` is drawn once in shaded colours, then clipped into the slanted light band and drawn again in lit colours.

**Light patch geometry** (dx = 30 − 95·easeInOut(lt/1.25), moving left about 95px over 1.2s)
- Wall patch WP: (1420+dx, 250) → (1920, 470) → (1920, 730) → (1420+dx, 730)
- Floor patch FP: joins below the wall patch, spreading down and to the right
- Figure light band OP: left edge runs from (1345+dx, 0) to (1185+dx, 1080). The light edge sweeps across the girl's face over this stretch, from half the face shaded to the whole face lit
- Window mullion shadow: 24px vertical bars + one slanted bar parallel to the top edge of the patch
- **The figure's shadow on the wall** = the figure silhouette translated (+150, +18) drawn into an offscreen, `source-in` filled into the shaded base plate, then drawn back inside the light patch area. The effect is the shaded wall showing through the light patch, in sync with the figure's pose.

**Motif animation**: the light patch moves slowly (core); the barber pole on the red-brick building across the street (a nod to Early Sunday Morning), its red and blue diagonals travelling up at 60px/s; the roller-blind pull cord sways gently, `sin(4.2lt)·0.07rad`; 26 dust motes in the light band (shown only to the right of the light edge); steam.

**Texture**: the oil drag is mainly vertically stretched fbm (x·0.06, y·0.006) with diagonal as secondary, generated at 1/4 resolution then upscaled, `soft-light` α 0.2. Outside the window each opening has a 10px hard shadow on its right side, and the blinds are pulled to different heights (0.25–0.7) — that is Hopper's detail.

**Palette**: shaded wall `#5d8679`, wainscot `#4b6d63`, floor `#5b3d2b`; lit wall `#efcf8f`, wainscot `#d8ad68`, floor `#c98b52`; dress shaded `#7a2c2a` / lit `#cc4a3c`; blonde shaded `#a8893f` / lit `#f3d67e`; brick `#b4553a`.

**Pitfalls**
- The first brush marks used horizontal fbm at α 0.35 and the wall looked like watered marble. Hopper's walls are flat; brush marks may only be barely there.
- While editing the code a comment got inserted into the middle of a line and commented out the rest of that line (watch for this with Python bulk replacements).

**Character**: the first version was an updo + long red dress and review said "reads as an adult woman, not 17". Changed to long loose hair (`hair:'long'`) + a blue hairband and she got younger. The cat's white chest uses a smooth ellipse, shaded white `#dcd6c8` (the first version's `#c4bdac` read as a grey-and-white cat).

**Still improvable**: the cat stays in shadow the whole time and sits on the dark side (a deliberate trade for the sense of loneliness). It could be given a small patch of light coming in from the back window.

---

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
