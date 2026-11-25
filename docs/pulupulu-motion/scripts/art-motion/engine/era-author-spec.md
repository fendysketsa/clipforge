# Era Authoring Spec (pure code drawing)

> This is the author spec for the art-history speedrun reproduction film: the composition coordinates and character settings below apply only to that film and to similar speedrun / time-travel films. The general version is `references/art-motion/08-style-author-spec.md`; a new subject needs its composition rebuilt for that subject.

Each era you own = one file `scenes/<id>.js`, registering:

```js
SCENES['<id>'] = { draw(c, lt, t) { /* fill the whole 1920x1080 */ } };
```

- `c`: target 2D context; `lt`: this segment's local time (seconds, counted from this era's transition start, may run slightly past the segment length); `t`: film-wide time.
- **Do not draw the year plate** (top right 1500–1890 × 40–210 is drawn by the engine); leave that area as background, don't put important elements there.
- **Do not modify `lib/`, `scripts/art-motion/engine/engine.js`, `eras.js`, `transitions.js`, or anyone else's scene file**. Helper functions you need go in your own file.

## Available libraries (read the source first)
- `scripts/art-motion/engine/lib/paint.js` → `PAINT`: noise noise/fbm, textures texture/grain/craquelure, hand-drawn lines roughPath/boilSeed,
  style renderers strokes (flow-field strokes, with palette-region support)/dabs/mosaic/halftone/pixelate/facets, `swatch` colour groups, `choreo` shared choreography, steam, particles, `scratch(key)` offscreen canvas.
- `scripts/art-motion/engine/lib/rig.js` → `RIG`: `RIG.girl(opt)` girl skeleton (seated in profile facing left, returns a Path2D per part plus the anchors `G.A`), `RIG.drawGirl(c,G,pal)` (pal.mode can be fill/line),
  `RIG.cat(opt)` ginger-and-white cat skeleton (seated facing right), `RIG.drawCat(c,K,pal)`, `RIG.drawCup`, `RIG.smooth(points)` smooth curve, `RIG.taper` tapered limb, `RIG.ik2`.
- **Benchmark implementation: `scenes/09_postimp.js` (Van Gogh)** — study its structure: flat underpainting → repaint with the style renderer (region palette) → flat character plus fine strokes → added line work → moving highlights.

## Hard requirements
1. **The same scene skeleton**: standard composition — window (350,120)-(810,560), cat sitting on the floor (390,610)-(690,905), table (810,620)-(1200,905), person (1120,200)-(1500,910). The original film aligns every era to these positions, and the transitions depend on it.
2. **Characters**: the person is a 17-year-old European blonde girl wearing **that era's girl's clothing** (modest dress); the cat is a **ginger-and-white cat** (orange tabby on the top of the head / back / tail, white muzzle / chest / belly / paws).
   This must build on the `RIG.girl` / `RIG.cat` skeleton and choreography (one skeleton, one set of motions), but the drawing method changes to that era's: you may take only the Path2D and fill / stroke / silhouette it yourself, add costume at the anchors, or deform the skeleton points in period style (e.g. the Egyptian frontal eye, a black-figure silhouette).
3. **What is in the picture must live**: the main action uses `PAINT.choreo(lt,t)` (raising the cup, tail swish, blink, breathe),
   plus 2–4 **small loops taken from that era's visual motifs** — the list is under "in-frame action" for each era in `../breakdown/shot-list.md` (e.g. a rock-art animal running in two alternating poses, a scarab pushing the sun disc, a meander band scrolling, Vesuvius smoking, a gold-leaf highlight sweeping across, an ornithopter flying past, cherry petals falling, dappled light flickering…).
   The era is on screen for only 0.25–1.4 seconds, so the motion has to be **readable inside that window**.
4. **The style is made by code**: use the renderers / textures / lines to paint it as an artwork of that era, not as clip art. Lines may use 8–12fps "boil" (boilSeed) to add a hand-drawn feel.
5. **Performance**: ≤ 150ms per frame (1920×1080). Cache the static parts with `PAINT.cached`. Every random value is seeded; the same t must draw the same frame.

## References
- Reference-film frame for that era: `../generated-images/ref/<id>.png` (composition, motifs, colour, everything except the counter; you pull these frames from the reference film yourself, they do not ship with the skill)
- AI design plate (same composition, already swapped to the blonde girl + ginger-and-white cat): `../generated-images/plates/<id>.png` — use it as art-direction reference, **never paste the image into the frame**, draw with code only.
- In-frame action, transition origin: `../breakdown/shot-list.md`
- Reference film at 60fps: `../原片/<reference-film>.mp4` (bring your own)

## Self-check (at least 3 rounds per era)
```sh
cd <your project directory>   # contains code-project/ (copied from scripts/engine)
uv run --with playwright python code-project/render.py --solo <id> --stills 0,0.3,0.6,0.9 --out render/<id>
uv run --with playwright python code-project/render.py --solo <id> --from 0 --to 1.2 --out render/<id>/clip.mp4
```
Lay your frames beside the reference-film frames and the design plate (PIL) and ask yourself: (1) can you tell at a glance which era / artist it is? (2) does the girl read as a 17-year-old blonde girl and the cat as a ginger-and-white cat? (3) can you see the picture moving within one second? (4) any glitches (misalignment, broken lines, wrong occlusion, empty patches)?
Fix whatever fails, until you are satisfied.

## Delivery
- `scenes/<id>.js`
- `notes/<id>.md`: which techniques you used (renderer parameters, palettes, how the motif animations were built, the pitfalls you hit), **this is the experience that gets distilled into the skill**, so be concrete and give numbers.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../../../references/art-motion/INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
