# 15_raytrace · 1993 early ray-traced CGI

No 3D engine — 2D Canvas "shading conventions" fake a renderer's output.

## Plastic shading (every part goes through it)
`plastic(c, path, base, hx, hy, R)`:
1. fill the base colour;
2. radial gradient centred on the highlight point (hx,hy) with radius R: 0→white .55, 0.28→white .06, 0.62→transparent, 1→deep purple `rgba(10,0,30,.42)` (edges darkened = volume);
3. environment reflection: a ring of `rgba(70,150,150,.28)` stroke composited with `lighter`, width 0.18R, offset 0.04R to the left — the wall is teal, so the reflection is teal;
4. one hard-edged white elliptical specular highlight (0.16R × 0.09R, opacity .85). This stroke is the most '90s-Phong thing of all.

Limbs use `cyl()`: gradient across the limb's normal direction (dark .25 → white .5 narrow band at 22% → dark .45), then a thin white highlight line along 20%–75%.
The girl uses RIG.girl's Path2D (long hair), with the skirt swapped for blue plastic cylindrical legs plus spherical knee joints, and ball joints added at the shoulders — the jointed look of a "toy figure".
RIG's cat body is a polyline and the plastic shading exposes the facets: `RIG.smooth(K.bodyPts)` before shading. Tabby markings drawn with `filter: blur(2px)` as soft stripes "printed under the plastic".

## Scene
- Wall: radial gradient `#7dbcb9 → #64a6a6 → #3f8285`, light source at the window's position; the window's cast shadow `blur(10px)`, offset down-right.
- Outside: pink-purple gradient sky (`#a24cc4 → #df62ae → #f5a08a → #f8c070`), two mountain layers, a pink 28×26 wireframe grid over the mountains (early-CG wireframe terrain), snow caps as jagged triangles.
- **Floor**: per-pixel perspective checkerboard, vanishing point (960,480), `X=(x-960)/dy, Z=1/dy`, cells TX=0.27, TZ=0.00029, 2×2 supersampled AA, plus 35% fog within 140px of the wall. Cached; cold start 53ms for the whole scene.
- **Reflection**: the object layer (chair/table/girl/cat) is drawn to an offscreen layer, mirrored with `translate(0, 2*906); scale(1,-1)` and drawn into the floor clip region at `globalAlpha .34`; each prop mirrors about its own ground line (cone 780, purple ring 846, chrome ball 800), and **must be drawn to a separate layer first, then composited semi-transparent as a whole** — otherwise the purple ring's 140 small balls each at .34 stack into opacity.
- Glass table: translucent green ellipse + thick edge + white stroke, with one diagonal highlight sliding 260px per second.

## Small loops (must be visible within 0.23s)
- Purple ring: 140 balls arranged along a torus, spinning about the vertical axis at 7 rad/s, tilted 0.35, drawn depth-sorted (first a dark purple base layer so the balls read as a tube, then per-ball radial highlights). In 0.23s it turns 1.6 rad, going from face-on to edge-on — very obvious.
- Chrome ball: per-frame per-pixel environment mapping (reflection vector pointing down → checkerboard, up → pink-purple sky + one window light streak); the checkerboard u coordinate shifts with `t*4.5` = it is turning; Fresnel rim brightening. Diameter 104px, <2ms per frame.
- Lens flare (`lighter`): sun-core glow 170px pulsing ±8% at 23 rad/s; 12 star spikes rotating at 1.6 rad/s; horizontal bar of light 960px; 5 ghosts (circles + hexagons) laid out along the "sun→frame centre" line, sliding with `sin(t*5)*0.03`.
- Cat's green eye glow: `lighter` radial gradient radius 46px, pulsing ±25% at 18 rad/s.
- Cup-holding (choreo.cup), tail flick, blinks, steam as usual.

## Pitfalls
- The transition wireframe computes edges from the frame where the new picture first appears and caches them (`once('edges')`), so the frame at lt≈0 must be complete — do not leave lt=0 blank or fading in.
- Performance: hot frame 23ms, cold start 53ms.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
