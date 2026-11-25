# 36_picasso_blue · 1903 Picasso's Blue Period

> Source: migration test D (an independent agent implementing straight from the read-only skill, 2026-10-04). After integration the scene code was ported to `scripts/art-motion/engine/scenes/36_picasso_blue.js`.

File name at experiment time: `scenes/r5_bluepicasso.js`, about 24ms per frame.

**Pipeline**: flat monochrome blue underpainting (wall, floor, night sea and moon outside the window) → repaint with wide dry strokes, then blur 7px and composite at 80% → very faint dry-brush filaments → copy the window frame back as-is, add small strokes → table on its own layer → coarse environment contours (no boil) → waves, broken moonlight, clouds → characters (elongated overall) → small strokes on the characters + cool-light gradient → coarse visibleLines contours → shawl folds → slow heat haze → canvas weave + cool vignette.

**Key parameters**
- Palette: #132240 / #1d3866 / #2d5a94 / #6b8fb6 / #b6c8d8 / blue-grey #3b6878, strictly monochrome.
- The orange-and-white cat is separated by value: orange = mid blue #4f719a, tabby #273f66, white = pale blue #b6c8d8. Blonde = the brightest blue-grey #cbd8e0, skin #90a9be; the hair has to sit one step lighter than the skin to read as "blonde".
- Wall strokes: cell34, len110, w34, jitter 4, vertical ±0.5·noise(0.003); palette mixBase 0.8; then blur 7px and composite at α0.8. Floor strokes use the same params, horizontal.
- Dry-brush filaments: 900 of them, α0.07, length 30–90.
- Elongation: the girl `DOMMatrix().translate(1240,932).scale(0.84,1.12)`, pivoted on the soles; the cat scale(0.82,1.14), pivoted on (540,905). The same matrix is used in three places: Path2D.addPath, the offscreen setTransform, and the setTransform inside the visibleLines callback.
- Shawl: draped from forehead/headTop, past nape and back, down to waist+70, colour #6b8fb6, fold lines rgba(20,40,80,.6) 4px. Long fingers: 3 slim ellipses 22×4.5 around the cup.
- Contours: Prussian blue #0c1830, 5px, no boil. The Blue Period contour line is certain of itself; it should not shake.
- Slow: breathing sin(1.8t)·0.026 (about 2× the amplitude and 0.45× the frequency of the shared choreography); the cup lifts over 1.25s (the shared choreography uses 0.9s); the heat haze rises at 0.5× time.

**Motif animation**: waves outside the window drifting sideways (faster the closer they are, speed 20 + 0.25·(y − 400)), 14 strips of broken moonlight flickering, one pale long cloud crossing the moon, slow breathing (person and cat), lifting the cup, heat haze. Motion area 3.2%.

**Pitfalls**
- The first version left a little ochre on the cat and the hair (a nod to The Old Guitarist); independent review judged that it broke the monochrome. The Blue Period should be all blue — separate by value.
- cell16, len40, w14 vertical strokes all over the wall read as "rain / blanket" — that is Impressionism, not the Blue Period. Go wide, long, low-contrast, then blur a layer over it.
- The round caps of packed wide strokes formed a "crowd of heads" (see ② item 11). The 7px blur suppressed it; the real fix is to add a cap parameter to strokes.
- If the table area is excluded from the big strokes with a rectangular mask, a flat rectangular patch is left on the floor. The table has to be its own layer drawn after the strokes; do not cut a hole in the strokes.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
