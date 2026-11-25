# 25_ghibli · Ghibli visual family: overall language + existing background implementation


## 2026-10-15 · Overall-language study (still awaiting cross-scene validation)

Read [cross-scene style distillation](../15-style-transfer.md) first. The lower half of this card is engineering experience from one existing room scene; it proves that some watercolour/cel techniques run, but it does not represent the whole Ghibli system, and it is not a composition template for new films.

**Define the scope first.** My Neighbor Totoro, Kiki's Delivery Service and Spirited Away can be used to study characters, hand-painted backgrounds and everyday action in different environments; The Tale of the Princess Kaguya organizes line and negative space noticeably differently and must not be forced into the same watercolour background recipe. When producing, choose the film/author range that matches the content at hand, and compare shots of different locations, lighting and action rather than only picking forest long shots. The official [works and scene stills](https://www.ghibli.jp/works/) can be used to locate references; the [scene still release notice](https://www.ghibli.jp/info/013344/) does not mean unlimited use rights for all materials.

**Transferable research dimensions.** ① Character silhouettes, expressions and key actions are clear, and the background carries its own observation and material detail; ② character and environment agree in perspective, light direction, contact shadow and colour — they are not required to be painted with the same watercolour texture; ③ everyday action has body weight, a sequence of using objects, and reactions; ④ environmental motion has causes such as wind, gravity and contact; ⑤ a scene has both habitable structure and narrative use. These are initial research generalisations; whatever does not hold in a specific film means the scope must change.

**Content is variable.** Green forest, country house, girl, cat, broom, food and giant clouds are not mandatory. The subject can be a city repair shop, a night-shift transit station or a fictional equipment bay. "Sense of life" must not be equated with a fixed slow pace; tense passages also need accurate action.

**Production hypothesis.** Start from the space and light of this scene; design the character separately with independent checks of proportion, contour and expression; build to the no. 10 frame library or import assets; then composite and choreograph in code. The background wash is only an optional material means — multiplying a paper texture over a whole character image is not "finished". The existing `scenes/25_ghibli.js` can be consulted for local background technique, but the character and the new space must be redesigned; complex turns or interactions cannot be replaced by translating the same image.

**Transfer stress test (to do).** Recovering a lost item in a city launderette; an unmanned automatic irrigation installation starting up; two adult maintenance workers completing an emergency repair in a space capsule. These three are not new templates, only a check of transferability without forest, girl and slow motion.

**Feedback loop.** Each time record the film scope, scene, adopted route, image/animation evidence, character-environment consistency and contact problems; when an old conclusion fails, change the original sentence first. Passing one scene cannot rate the whole studio. Current status: the existing background implementation holds its original quality; overall visual and performance direction remains research.

## Existing watercolour background example (historical implementation, not a style definition)

> Source: migration test B (independent agent working from the read-only skill, 2026-10-04). After consolidation the scene code was ported to `scripts/art-motion/engine/scenes/25_ghibli.js`.

Filename at experiment time: `scenes/c4_ghibli.js` (about 270 lines). Median 17ms per frame, **first frame 619ms** (watercolour base plate caching); frame difference 5.1%.

**Watercolour renderer**
- `deform(pts, depth, amp, r)`: midpoint displacement. Each round pushes each edge midpoint along the normal by an approximate Gaussian amount (3 uniform numbers summed), amplitude proportional to edge length (min(1, len/80)), amp×0.6 per round.
- `wash(g, pts, color, {layers, alpha, amp, seed, edge, blend, fill})`: deform 3 rounds first to get the base shape; each layer deforms 2 more rounds and is filled at low α with `multiply` (transparent pigment layering), with a 1.6px stroke of the same colour at α=edge. The strokes accumulate layer by layer — that is the **water mark edge** where pigment settles. fill can take a gradient (sky, wall).
- Common parameters: large wall areas layers 5, α 0.4, amp 12; colour blooms layers 3, α 0.045, amp 40 (large deformation); wood planks layers 3, α 0.5, amp 3, edge 0.14; opaque whites (window frame, tablecloth, clouds) use `blend:'source-over'`, α 0.9–0.95.
- Wall = radial gradient wash (bright by the window `#fbf3e0` → corner `#dcc49a`) + 28 large-deformation transparent colour blooms (warm yellow, pink, blue-grey, pale green alternating) + dark blooms in two corners. Wainscot and floor are washed **block by block** with varied tone. Finally a high-frequency paper grain is layered over with `multiply` α 0.3.
- Clouds: opaque white round clumps (16 puffs, edges drawn with wash) + `source-atop` blue-grey gradient at the base, cached as a sprite. The big camphor tree is also a sprite, rotating ±0.025rad about its root.

**Cel character `cel(c, p, base, shade, dx, dy)`**: fill the whole shape with the shadow colour first, then inside clip(p) fill the base colour after translating the shape toward the light by (−dx, −dy), leaving only a crescent of shadow on the shaded side. Finally stroke 2.4px warm brown `#4a3428`. One function is the Ghibli-style two-tone cel.

**Motif animation**
- White gauze curtains: two panels, hem bulge `q²·(90 + 70·gust)`, gust = 0.55 + 0.45·sin(3.2lt + phase), plus a small `sin(7lt + 6q)` ripple; 3 semi-transparent wash layers with a fixed seed, so the edges don't boil.
- 360 blades of grass outside the window: the wind comes in gusts, `wind = 0.5 + 0.5·sin(3.1t − 0.018x)`, with the phase advancing along x, so a wave of wind can be seen sweeping across the grass slope.
- Clouds drift 22–30px/s; the canopy sways gently; 34 komorebi light spots on the wall (`screen` warm yellow radial gradient, positions drifting with noise, brightness flickering as `sin(5t + 1.7i)`); daisies on the table nod; the girl's long hair is blown to the right-rear (7-point smooth, pushed by wind); the red bow ribbon flutters; the tablecloth's hanging edge sways.

**Character**: long blonde hair + a big red bow (a nod to Kiki's Delivery Service, not copying the character), teal long dress + white apron + white cuffs; the cat is warm orange + off-white cel. The broom leaning against the wall in the background is an easter egg.
**Character's watercolour fill**: review said "the background looks right, the character doesn't (flat vector)". The character is drawn into an offscreen L first, and a separate texture layer M is built (paper grain α 0.8 + 40 transparent colour blooms `charBloom`, α 0.1, amp 16); M is cut to L's silhouette with `destination-in`, then composited back over the picture with `multiply`. The line colour was softened from `#4a3428` to `#6a4a38`.
**Curtains**: review said they don't flutter. gust frequency 3.2 → 5.4, bulge `q²·(60 + 150·gust)`.

**Pitfalls**
- With colour blooms at α 0.07×4 layers and grain multiply 0.5, the wall looked like mouldy old parchment. Ghibli rooms are bright: blooms dropped to α 0.045×3 layers, and the gradient lifted a full step overall.
- The first version built the wall from two rectangular washes (darker on the right) and a hard seam appeared at x≈1100. Dark areas must use large-deformation polygons (amp 60), not rectangles.

**Still improvable**: the character is still flat; Ghibli-style blocks of hair highlight could be added; flowing curtain shadows could be added inside the light spots on the floor.

---


### 2026-10-15 · New scene engineering trial

Added `54_ghibli_lab`, a street-corner repair shop, with a tram passing by and objects and environment moving subtly; run with `render.py --film style_studies --solo 54_ghibli_lab --from 0 --to 6`. The code is kept separate from the original 25 room. Determinism and decoding pass; independent review found no technical red items blocking this round's research showing; it still reads as procedural illustration, has not reached studio-film-level recognisability, and has not been cross-scene validated.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
