# 29_seurat · 1884 Seurat A Sunday on La Grande Jatte (pointillism: a visual colour-mixing renderer)

> Source: migration test C (independent agent working from the read-only skill, 2026-10-04). After consolidation the scene code was ported to `scripts/art-motion/engine/scenes/29_seurat.js`.

Filename at experiment time: `scenes/k3_seurat.js` (136 lines). About 100ms per frame, frame difference 7.4% (still and solemn, mean adjacent-frame difference 0.45).

**Renderer (the important part, could be extracted into paint.js)**
1. A full flat-fill base plate, character included (~3ms per frame). Underneath, a `blur(4px) saturate(.85) brightness(1.06)` copy of the base plate is laid as underpainting, so the gaps between dots reveal it.
2. **Fixed hexagonal grid, equal dot size**: pitch 10, row spacing 8.66, r 4.5, each dot with ±1.2px static jitter. About 24,000 dots. Dots are accumulated into 21 Path2Ds by colour and each colour is filled once.
3. **Visual colour mixing colour selection**: a 21-colour pure palette.
   - 14 saturated colours: `#1a2058 #2a3a9a #3f6fd0 #6aaee6 #1f6a52 #2f9a5a #a8c83a #f2cf3a #f08a2a #e0432a #c0306a #7a4aa8 #f8f4e8 #e8b48a`
   - 7 pale colours (Seurat's "colours mixed with white"): `#f6e49a #f6c48a #cfe08a #b0cff0 #f2b8c8 #c99a4a #9a7ac8`
   - For every pair (i,j), **project** the target colour onto the segment Pj→Pi to get a continuous ratio w, clamped to [.2,.8]. `0.004·|Pi−Pj|²` is added to the distance, penalising pairs that are too far apart, so that black and white dots are not used to mix grey. Take the pair with the smallest distance; each dot picks Pi or Pj by `hash(i,j) < w`.
   - Results are cached in a Map keyed by the 15-bit quantised colour.
4. **Before sampling, add ±20 hash jitter to the target colour** (R+dj, G+0.8dj, B−0.6dj). The switch boundaries between paired colours therefore become interleaved dots, and no vertical colour bands appear.
5. **Complementary dots**: 8% of the dots are swapped for the complementary colour (blue↔orange, green↔red-purple, yellow↔purple…, 21 mappings in all). **Irradiation**: compare with the point 14px to the lower right; when the brightness difference >45, with 45% probability place a white dot on the bright side and a dark blue dot on the dark side.
6. **Seurat's own painted border**: a 28px dark blue band on all four sides, also run through the pointillist renderer, so orange complement dots appear in the band.

**Motif animation**:
- The Seine inside the window: sailboats drifting (40px/s), a steamboat trailing smoke, the profile of a lady with a parasol + a small monkey.
- The water dots re-hash at 6fps = glinting water.
- Indoors an orange-red butterfly flies above the table (`sin(2.6t)·120`), wings beating `|sin(20t)|`.
- 6fps makes 7% of the dots switch to their paired colour, showing light trembling between the dots. The first version used 4fps/3% and independent review judged it "basically a still" (mean adjacent-frame difference 0.1–0.2); at 6fps/7% it rose to 0.45.

**Character**: 1880s deep blue-purple long dress + a bustle at the back of the waist (an arc in the `back` hook) + white high collar + orange buttons + a small round hat with a red feather. A closed red parasol leans against the chair back.
**Pitfalls** (both at the renderer level)
- Preferring a single pure colour (with the penalty term) cut a gradient wall into several vertical bands.
- Once the ratio became continuous, paired colours still switched for whole columns at boundaries and still banded. Fixed by the target-colour jitter in step 4.
- The first palette had no pale colours, so a bright wall decomposed into white + skin tone + scattered blue dots and looked like snow noise.

---

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
