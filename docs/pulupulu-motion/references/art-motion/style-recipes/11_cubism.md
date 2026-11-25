# 11_cubism · 1912 Analytic Cubism (Picasso / Braque)

File: `scenes/11_cubism.js` (about 280 lines). Performance: warm mean 13ms, max 19ms, first frame (cache build) ≈100ms; determinism passes; 6.9% of pixels moving in the lt 0.34→0.46 motion diff. The shot holds for 0.47s (T10 shard transition 0.24s).

## Pipeline
1. **Fully cached background plate `cb_bg` — "transparent overlaid planes"**: core function `plane(g, pts, col, alpha, r)`: each plane gets one linear gradient whose start is vertex 0 and whose end is another random vertex, with three stops = 25% cream mix → base color → 40% deep-brown mix, alpha 0.18–0.7. Assembly: 18 hand-placed large planes (following the source's composition positions) + 9 radiating fan planes under the table (emanating from (1000,1090), alternating light/dark at α0.3) + 70 random 3/4-gons (avoiding the year area at upper right). Layering multiple translucent gradients produces exactly the Analytic Cubist space — "transparent, interpenetrating, each plane light on one side and dark on the other".
   - Texture planes: 4 stippled (9px diamond grid, r1.6), 4 hatched (7px-spaced diagonals), one page of ruled paper at the left edge.
   - Braque's short-dash grain: 9000 little dashes of 3–8×1.5px, 55% cream at α0.28 / 45% deep brown at α0.16 — the source's "brick texture" comes entirely from this.
   - 46 fine straight lines running through the composition (1.3px α0.55) = passage.
   - Faux wood grain `wood()`: draw S/6 wavy lines along the long edge, add Gaussian bulges at knot positions `14·exp(-(u-k)²/0.01)`, with 4 concentric ellipses per knot. Used for the tabletop and the right-hand plank (Braque's combed faux wood). Cane chair back = 10px diamond holes + diagonals in both directions.
2. **Window-pane shard sliding**: the window view is cached separately as a 560×540 image (55 blue-gray facets + 3 diagonal light beams + Eiffel Tower + gull arcs); each of the four panes clips it and frames it at a different offset `dx = sin(9lt+1.7i)·18 + 10fps jitter ±3`, `dy = cos(7lt+i)·8` — the same view displaced across four panes = multi-viewpoint assembly; each pane also has a translucent triangle sliding sideways at 260px/s.
3. **CAFÉ stencil letters jumping and swapping**: `AlfaSlabOne-400` 104px drawn into a small offscreen layer, beat-locked at 12fps (`st=floor(lt·12)`), cycling through the order table `CAFÉ/ACFÉ/CAÉF/CFAÉ`, with each letter's y ±13 and rotation ±0.11rad per step (from a hash); then `destination-out` cuts horizontal and vertical breaks = stencil lettering (the breaks let the planes underneath show through, more convincing than painted paper-colored bars).
4. **Newspaper JOU**: cache a 300×190 image (LibreBaskerville-700 84px "JOU" + 12px headline "LA BATAILLE / S'EST ENGAGÉ UN CHAT" + three columns of gray greeked text), micro-trembling at 8fps each frame (rotation ±0.0125rad, x ±1.5px), with the top-right corner folding on `sin(20lt)`.
5. **Characters = hand-written facetizer `facetize`**: RIG flat fill (fill mode, no lines) into an offscreen layer → read back the pixels of that bounding box → jittered triangle mesh (random diagonal per cell) → each triangle samples color at its centroid, `×(0.8+0.38·rand)` for value, then a light→dark gradient from vertex 0 to vertex 2 → **drawn back without clipping the triangles** (skip those with centroid alpha<120). No clipping is the key: the silhouette edge becomes jagged straight cuts and some triangles stick out past the contour — that is the Cubist "planes spilling past the outline" feel.
   - Girl cell 58 (large planes); the hair region is then fine-cut again at cell 26, cutting only "colors that look blond" (`only: R>150 && B<130 && R-B>60`); cat cell 26.
   - Vertices jitter ±8% of cell at 8fps and 16–35% of triangles jump ±12% in value (boil) → the characters are "micro-moving", exactly like the cat region in source frames 548–562.
6. **After faceting, restore Picasso-style structure**: repave the face with two skin-tone value planes (faceting drags blond colors into the face) + a blue-gray plane over the front half of the face at α0.82 + a frontal almond eye (frontal eye on a profile face) + spiral ear + red lips; two value triangles on the white collar + three buttons; 8 radiating cut lines from the waist down the skirt + alternating light/dark wedge planes; the outer contour uses straight segments `segs()`, with each end extended 10–16px (lines drawn past the bounds). Cat: hexagonal straight-line head contour, straight-line body contour from `bodyPts`, yellow diamond eyes + vertical pupils, triangular nose in profile.
7. The top layer is 5 planes at α0.2 pressed over the human and the cat, offset by `sin(6lt)·8` — embedding the characters "into" the space so they do not look pasted onto the background.

## Palette
Paper `#d6c8ac`, cream `#ece3cf`, ochre `#b8975f`, brown `#6e5538`, deep brown `#3a2c1e`, gray `#a8a395`, blue-gray `#8e9eab`, dark gray `#5a5852`; window view `#c9d3da/#8fa3b3/#e4e6e2/#6f8597/#b4c1cb/#5f7385`; dress `#6a7a8b`, sleeve `#3c4857` (must be darker than the dress, otherwise the cup-holding arm melts entirely into the dress facets), skin `#e2cfae`, blond `#c9a256`; cat `#c8773a`/`#e8dfc9`.

## Pitfalls (important)
- **Non-determinism: the first frame differs from everything after.** Two causes stack up, both appearing only on the first frame: ① the first time the offscreen layer that needs `getImageData` is drawn it goes through the GPU, and after reading back Chrome converts it to a CPU raster, so antialiasing differs → centroid samples differ → triangle colors differ; ② more importantly, the offscreen layer's context state (`lineJoin='round'` set inside facetize, `lineCap='round'` from segs) persists into the next frame, while the first frame uses the default miter/butt. Fix: create the layer yourself with `getContext('2d',{willReadFrequently:true})` and **at the start of each frame call `g.reset()` (clears pixels + state) instead of `clearRect`**. This was only found by hashing "the same lt rendered three times in a row".
- Facet cell 34 covered everything in small triangles, looking like a low-poly 3D model rather than Cubism; 58 is what gives "large value planes".
- The second fine-cut pass over the hair region started with a circular clip, which turned half the face gold — fixed by adding the color filter `only`.

## Still improvable
- The girl's overall contour is still RIG's realistic curve; faceting only changed the edges. A more thorough approach is to replace shoulders, elbows and knees with a polyline skeleton before faceting.
- The source is darker with stronger value contrast (more large deep-brown planes); this version runs lighter.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
