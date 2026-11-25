# 08_impressionism · 1874 Impressionism (Monet)

65–76ms per frame (median 69ms). The main cost is two full-screen P.strokes passes plus one character-stroke pass.

## Pipeline (following the 09_postimp benchmark)
1. Flat underlay `impBase`, repainted every frame because the poppies, clouds, bouquet, potted plant and curtain all move:
   - Pink-lilac wall (#d8bede→#f0c8cc→#f2c4d4), with a warm-yellow sunlight radial gradient r=900 overlaid at the upper right.
   - Garden outside the window: sky, trees, red-roofed house, grass, 70 poppies (stem bases fixed, flower heads swaying `sin(t·3.2+ph+x·.02)·(6+r·.6)`), a woman with a parasol plus a child (a nod to "Poppy Field"), flower beds.
   - White window frame, pale lilac curtain, "Impression, Sunrise" on the wall, round table with a white-lilac cloth, vase, teapot, potted plant on the right (the whole leaf mass swaying on `sin(t·1.9)·8`).
2. Brushstroke repaint, **two passes**:
   - Main picture: cell 11, len 20, width 7, outline 0, jitterCol 26, with a mask excluding the window view and the small painting on the wall.
   - Window view and "Sunrise": cell 6, len 11, width 4.5, drawn only inside the mask.
   - The first version had a single coarse pass, which smeared the houses and parasol woman outside the window, and slashed "Sunrise" into a streak; splitting into two passes and giving "Sunrise" horizontal water-ripple strokes made everything legible.
   - Lay #f2e6ee on the canvas first so a pale ground shows through the gaps between strokes.
3. Direction field: wall diagonals up-right (sunlit area −0.95 rad, the rest −0.55, plus ±0.55 noise); ground nearly horizontal; curtain and tablecloth vertical; potted plant radiating outward from the pot rim; sky in the window horizontal.
4. Region palettes `P.swatch` (mixBase 0.3–0.45): wall 9 colors of pink/lilac/yellow; sunlit wall 7 colors of cream yellow; ground 7 colors of rose/orange/violet; separate sets for sky, grass green, lilac curtain, blue-violet tablecloth. The white window frame is detected with `col > (240,236,225)` and mixed back to white; otherwise it gets brushed into the wall color and the frame disappears. Poppy red returns null, keeping the underlay's original color.
5. Characters: first flat-fill with `RIG.drawCat` / `RIG.drawGirl` in fill mode, then run one P.strokes pass over the character layer with `source-atop` (cell 7, len 13) so strokes only appear inside the characters. The white dress samples four colors: white, pale lilac, cream. After that only the features are touched in, with fine lilac lines — Impressionism does not outline.
   - Straw hat, blue ribbon and sash ribbon all float.
   - `pal.line` must be set to the hair gold: drawGirl's locks and lid parts stroke with pal.line even when lw=0, and the default dark blue leaves a black streak beside the face. Same for the cat — set `line`/`whisker`.

## Motif animation
- **Sunlight patches flickering**: 26 patches (6 on the tabletop, 20 on the ground). Each patch's intensity is `0.5+0.5·sin(t·sp+ph)·sin(t·sp·0.53+2ph)`, clamped, so the on/off rhythm is irregular. Patches drift sideways slowly ±10px. Each is 40 short bright yellow-white strokes, boiling to a new seed at 8fps. The first version composited with screen at α0.75 and was nearly invisible on the pink ground; source-over at α0.95 was needed for brightness.
- The sunlit wall area has 60 diagonal bright strokes, flickering to new seeds at 6fps.
- Cat fur glints: 60 candidate points, restricted with `isPointInPath` to the cat body and the left half of the cat head (the lit side), blinking on `sin(t·7+h·30)`.
- The whole picture boils at 8fps; steam is white.

## Performance
Two full-screen stroke passes plus one character stroke pass cost about 69ms. During a transition the engine draws the outgoing and incoming eras at once; 08→09 totals about 69+110ms, exceeding 150ms, but only for the dozen or so frames of the transition.

## v2 rework (shot review: the whole screen re-rolled its strokes every 7–8 frames, frame diff 18)
- All stroke positions fixed: `boil: 0`. **Fixing the seed alone is not enough**: P.strokes' random numbers are one sequential stream, so when the palette returns null the jitter consumes 3 extra numbers; and whether it returns null depends on the underlay color, so one sway of the poppies or the potted plant re-rolls every subsequent cell's strokes. `stable(palette)` wraps it so each cell consumes exactly 1 number and never returns null.
- Character strokes no longer use alphaMask (when the cup-raise moves, the skipped cells change and the whole layer re-rolls); replaced with a hand-written loop using `U.hash(i,j)` per cell. This also brought the frame from 115ms back down to 72ms.
- "Aliveness" moved into local motion instead: light patches drift ±44px and switch at 5–11Hz; poppy sway increased to 10+; clouds traverse at 45px/s; curtain and potted plant sway; strokes in the garden foliage rotate ±0.22rad with the wind direction; cat tail swing (×2.2) and head turn (look).
- Still-segment frame diff (480×270, counter masked out, tail transition frames excluded): v1 mean 4.14, peak 20.5 — that is strobing; v2 mean 0.57, peak 1.9. Source 0.77.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
