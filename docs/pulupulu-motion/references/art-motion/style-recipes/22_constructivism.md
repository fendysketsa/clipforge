# 22_constructivism · 1924 Russian Constructivist poster (Rodchenko / Lissitzky)

> Source: migration test B (independent agent working from the read-only skill, 2026-10-04). After consolidation the scene code was ported to `scripts/art-motion/engine/scenes/22_constructivism.js`.

Filename at experiment time: `scenes/c1_constructivism.js` (about 175 lines). Median 5ms per frame; frame difference 3.6%.

**Pipeline**
1. Fully cached base plate `cs_bg`: off-white aged paper (`P.texture` `#e9dfc4`, dark `#d9c9a4`) → black slanted bar on the left (rotate −0.5), red square (rotate 0.26), 5 rows of black "body text" bars → fine slanted lines on the right, red dot, vertical geometric letters "ЧАЙ" inside a black vertical bar → large black circle behind the character's head (center (1330,395), r 215) → slanted red ground (0,905)→(1920,856) with a 12px black line along its top edge → window → black table (red edge, diagonal brace) → black block stool.
2. **Window = photo collage**: first draw a grayscale "photo" offscreen (sky gradient `#5e5e5e→#e8e8e8`, radial white clouds, dark factory silhouettes, chimneys), then convert it to a halftone dot screen with `halftone()` (cell 7, gain 0.8); the Shukhov tower is drawn over the halftone in crisp black lines (five hyperbolic sections, each with two sets of 18 straight generatrices, phase offset ±1.1rad, back faces with sin<−0.2 omitted) — this is precisely the "photo + hand drawing" collage.
3. **Skin = halftone photo**: face, neck and hands are first drawn as grayscale gradients (bright in front, dark behind, `#fafafa→#9c9c9c`) into an offscreen, then screened (cell 4.6, gain 0.74, 45°). Off-white is laid under the dots, and a 7px `#fbf7ea` stroke is drawn around the outside first — that ring is the white border of a photograph cut out with scissors. Facial features are added with crisp black strokes, the lips painted red by hand. All clothing is cut-paper flat fill plus 3px black lines; shadows use `shadeDots()`, which lays dots inside a path according to a function.

**Key functions**
- `halftone(c, src, bx,by,bw,bh, cell, col, gain, ang=π/4)`: samples src grayscale on a rotated grid, dot radius = cell·gain·√(1−L), drawn only where alpha>128. **All dots are merged into a single path and filled once**. About 3000 dots on the face, under 2ms.
- Geometric Cyrillic letters: 5×7 modules, each letter is a set of rectangles or polygons (Й's diagonal stroke is a quadrilateral, the breve is a small rectangle above). **Each part is filled separately**.

**Motif animation**
- Lissitzky's red wedge stabbing into the black circle: the apex travels back and forth along a 0.34rad axis, `70·(0.5−0.5cos(2π·1.6·lt))`.
- Red dashed ring outside the black circle: dash [46,22], `lineDashOffset = −260·lt`.
- Radio waves at the tower top: 4 red arcs, `r = 18 + ((1.4lt + k/4) mod 1)·230`, α and line width decaying with phase.
- Ground slogan "ПЕЙТЕ ЧАЙ!": stamped letter by letter (letter k starts at 0.045k seconds and scales back from 1.5× to 1 within 0.12s), then the whole row does a wave jump of `−10·max(0, sin(11lt − 0.8k))`; every 4th letter is black.
- The two tails of the headscarf sway gently, `sin(9lt)·6`; the steam over the cup is three black zigzag lines rising.

**Character**: Komsomol girl — red headscarf (13 points local to the head, front edge pulled back so the golden bangs show, knotted at the nape into two triangular tails), white shirt + red neckerchief triangle + red cuffs, dark grey long skirt (halftone shadow). The cat uses cut-paper orange `#e2741c` + off-white, 10px black stripes, tabby markings made with dashed outline on the tail, eyes are vertical bars with square pupils.

**Palette**: paper `#e9dfc4`; red `#c8231c`/`#8f1711`; black `#151311`; off-white `#f4ecd6`; blonde `#e3b03e`/`#a87a1c`; cat orange `#e2741c`.

**Pitfalls**
- The breve of "Й" was first drawn above the letter box (y=−1.7u): in vertical setting it was covered by the preceding letter, and in the ground slogan by the skirt hem, so review read it as "ЧАИ". Fixed by drawing the whole letter inside the 7 cells (the И portion shifted down 1.7 cells), and by drawing the slogan above the character (poster lettering over the figure).
- The first "А" built two opposed diagonal legs plus a crossbar into one path; the overlaps cancelled out under nonzero, so in vertical setting it read as "В". Fixed by filling part by part.
- The first ground slogan had its baseline at y=1060 and the lower half of the letters fell out of frame. Now positioned by letter center with `translate(x, 990)`.
- The under-cheek shadow was too heavy at first and looked like a beard once screened. The shadow α in the grayscale source has to be half of what it would be in flat fill.

**Still improvable**: Rodchenko's more characteristic device is "photo of a figure + horn-shaped cone of type". The steam could become a red-and-black wedge-shaped cone of letters radiating from the cup mouth.

---

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
