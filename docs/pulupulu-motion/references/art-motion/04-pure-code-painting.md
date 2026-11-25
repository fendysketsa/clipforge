# 04 · Pure-code drawing: paint an artful picture with Canvas and make it live

This page takes pure-code drawing as its main line: scenes and objects are built by procedural and style renderers; people, anthropomorphic characters and robots are not drawn in code into the finished film — for the generated-frame route see 10, for the delivery line see `character-detail.md` (the character-detail spec). This page is the method summary written after the first pass through all 16 styles; the concrete parameters of each style live in `style-recipes/<id>.md` (the style recipe library).

## 1. Project skeleton (`scripts/art-motion/engine/` — copy it once and you can start a new film)

```
index.html      load order: lib/fonts → lib/util → lib/paint → lib/rig → eras → transitions → scenes/index → engine
eras.js         segment table: id, how many eighth notes (eighths) it occupies, transition{type,dur,delay,cx,cy}, year-plaque style
scenes/<id>.js  one file per segment: SCENES['<id>'] = { draw(c, lt, t) }   ← the bulk of the work is here
transitions.js  transition library: (c, A old, B new, p, o) → draw one frame
scripts/art-motion/engine/engine.js       beat grid → t0/t1 per segment; during a transition the old and new segments are each drawn offscreen and then handed to the transition; camera impact on the downbeat; year counter (value determined only by global t)
scripts/art-motion/engine/lib/paint.js    noise, texture, hand-drawn boiling lines, style renderers, region palette swatch, shared choreography choreo, steam, particles
scripts/art-motion/engine/lib/rig.js      character skeleton: RIG.girl / RIG.cat → Path2D per part + anchors; drawGirl/drawCat (mode: fill/line); ik2, smooth, taper
render.py       headless Chromium calls renderFrame(t) per frame → PNG pipe → ffmpeg 60fps, can mux an audio track; --solo <id> single-segment preview, --stills dumps still frames
compare.py      original | remake side-by-side contact sheet at the same timecode
```

Render speed: a 15-second 60fps film takes about 90 seconds (M-series Mac). Most single-segment frames take 5–40ms; the heaviest, Van Gogh, 110ms.

## 2. How to paint one style (five layers, reference implementation `scenes/09_postimp.js`)

> The five layers are the default order for oil-painting/printmaking styles, not a universal law: **ink wash** runs in reverse (paper is the base, ink only goes on top, large areas stay white — do not fill them first); **pattern styles** (Kusama, Bauhaus) are "sprinkle pattern over a flat fill", where the pattern itself is the renderer; **chiaroscuro** is "draw the lit version first, then multiply by a light map".

1. **Flat-fill underpainting**: block in the large areas (wall, floor, sky, beyond the window) with flat color/gradients, with position and value correct. This layer fixes the composition; the style has not appeared yet.
2. **The style renderer repaints it**: use the underpainting as the color source and repaint the whole frame in that style's stroke grammar — Van Gogh flow-field long strokes, Impressionist short dabs, mosaic tesserae, ukiyo-e misregistered color plates + pattern, Cubist facets, Pop halftone dots, 8-bit low-res pixel-by-pixel, ray-traced per-pixel reflections… The renderer decides "whose painting this is".
3. **Small objects get their own layer**: if small things like tables, chairs, vases and picture frames go through the renderer together with the large areas, they shatter into a mush. Draw them separately with finer parameters, using `source-atop` so they only paint onto themselves.
4. **Characters**: speedrun/time-travel films use the same skeleton (RIG) and the same choreography, and only the drawing method changes (other subject matter designs its characters per subject) — flat fill, then that style's fine texture on top, then crisp outline and facial features last. Characters are where the audience's eye lands; they must read as someone specific.
5. **Highlights that move**: small loops of the era motif (see 02). Continuous motion uses continuous time; hand-drawn lines swap seed at 8–12fps to "boil", which gives the handmade feel.

## 3. Style renderer quick reference (all in `scripts/art-motion/engine/lib/paint.js` or written per scene)

| Renderer | Good for | Key |
|---|---|---|
| `strokes` flow-field strokes | Van Gogh, Expressionism, oil painting | Write the direction field per region (walls vertical, floor along the perspective, starry sky along the swirl); the **region palette** matters more than color jitter; each stroke needs a dark edge to look thick |
| `dabs` color dabs | Impressionism | Short elliptical strokes with warm/cool offset; **this is not pointillism** (no pure palette, dabs are not equal-sized — what comes out is Impressionism) |
| Optical-mix pointillism (29_seurat) | Seurat, Neo-Impressionism | Pure palette juxtaposed in fixed proportions, equal-sized dots, complementary-color dots, light bleeding across the value boundary |
| Tessellation (04_roman, hand-written) | Mosaic, stained glass | Compute the layout once, let color flow across the tesserae each frame; lay tesserae along contours (distance-field isolines); make tesserae 8–28% larger than half the spacing so the bisectors cut visible grout |
| Color plates + pattern (07_ukiyoe) | Ukiyo-e, woodcut, screenprint | Offset the fill (3,2)px against the ink lines; build patterns as CanvasPattern; horizontal brush streaks for the wash |
| `facets` cut planes | Cubism, low-poly | Stack translucent gradient facets to build space; leave triangles unclipped so silhouettes become straight-edged |
| `halftone` dots | Pop, old print | A small tile with `createPattern` is 10× faster than drawing dot by dot; 45° grid |
| Low-res pixel-by-pixel (14_8bit) | Pixel art, retro games | Draw at 240×135 then nearest-neighbor upscale; clamp to a 14-color palette; 1px black outline per part |
| Per-pixel shading (15_raytrace) | Early CGI, plastic, metal | One unified plastic shading model (base color + radial dark edge + ambient reflection + hard specular); mirrored reflection on the ground |
| Gold leaf (05_gothic) | Illumination, icons, ornament | Per-pixel burnish grain + an embossed dark line offset 1px from the bright line; highlights only where the "goldness" mask allows |
| Sfumato | Classical oil painting | Whole-layer light blur + a semi-transparent sharp layer; craquelure + canvas weave + vignette + yellow glaze |
| Variable-width path (10_nouveau) | Art Nouveau, calligraphic lines, printmaking | Offset both sides of the point list by the width into a polygon; a dark, offset silhouette underneath = thick outside, thin inside |
| Grain stipple (16_2026) | Contemporary flat illustration | Scatter dots inside the shape with density as a function of position; cache everything static |
| Brush flying-white + ink bleed (17_ink) | Ink wash, calligraphy, Eastern freehand | Taper the brush at entry and exit, sample at equal arc length for flying white; `filter='blur()'` to bleed it (deterministic under Chromium); paper is the base, ink only goes on top |
| Long curved flow strokes + row warp (19_munch) | Expressionism, sense of flow | Long strokes that walk 20–30 steps along the flow field; displace the whole frame by a per-row sine (margin ≥ maximum displacement so no seam shows) |
| Watercolor wash (25_ghibli) | Ghibli backgrounds, watercolor | Transparent color stacking + tide-mark edges; the tide-mark stroke's alpha fades as it expands |
| Grayscale photo halftone (22_constructivism) | Constructivism, old newsprint, photo collage | Dot radius from luminance, 45° grid, batch into a single path and fill once |
| Two-version light/shadow clipping + sheared long shadows (24_hopper, 23_dali) | Hopper, Surrealism, hard-light scenes | Draw a lit version and a dark version, clip by light shape; shadows via a shear transform |
| VHS channel-split post pass (26_vaporwave) | Vaporwave, retro video | RGB misregistration, scanlines, tracking-noise bands, applied as a post layer |
| Whole-frame light-map multiply (32_rembrandt) | Chiaroscuro, night scenes, candlelight | Draw the lit version first, then multiply by a light map (window light + radial candlelight) |
| Cel hard-shadow bands (35_shinkai) | Japanese animation, Makoto Shinkai | Part minus its translated self = hard shadow band; a bright lit edge on the light side |
| Stepped frame rate `stepTime(t,fps)` (33_rubberhose, 34_shadowpuppet) | Old animation, shadow puppetry, stop motion | 12fps/10fps stepping is half the style, not stutter |

## 4. Characters: one skeleton, a dozen-plus drawing methods

- Do not invent skeleton coordinates off the top of your head: overlay a 20px grid on an AI character sheet (or any reference image), read the key points part by part, and smooth them into a Path2D with Catmull-Rom (`RIG.smooth`). The first hand-written version's girl read as a boy; after measuring the points, one round was enough for her to read as a 17-year-old blonde.
- For a seated pose, hiding the legs inside a long skirt looks most natural; holding a cup uses two-bone IK (upper arm 165 / forearm 122), with the elbow pole fixed pointing down.
- The anchors `G.A` (top of head, forehead, neck, chest, waist, knee, hand…) let each style add costume: Egyptian broad collar, Gothic halo, ukiyo-e shimada coiffure, Bauhaus joint discs, Pop big waves.
- Each style may stylize the skeleton (Egyptian profile head with frontal eye, black-figure silhouette, Cubist half-blue face, pixelation), but staging and motion timing must stay consistent with the skeleton — that is where "the same two characters travelling through time" comes from.
- Big closing performance moves (jump, sprawl, claw swipe, gasp) do not have to be crammed into the shared skeleton: 16_2026 builds its own pose library (one set of local key points per pose, interpolated value by value), with squash and stretch pivoting on the sole of the foot and the flip happening on the most compressed frame.

## 5. Making the painting "live": motion checklist and how to measure it

- Every segment needs at least: one continuous action for the protagonist (choreo.cup — raising the cup) + 2–4 motif loops. Short segments (<0.5s) must be fast enough to step at 15–30fps.
- Self-check the amount of motion: render two frames (**avoid the 0.35s camera impact after a transition**, or the whole screen counts as moving) and take the frame difference. The first pass measured (0.45↔0.9s, after the zoom settles): cave 2.8%, Egypt 3.4%, Rome 6.4%, Greece 9.9%; original film, same segments, heat map 6.9%, 6.2%, 17.3%, 11.6%. If it reads too still, add motif motion.
- Moving things must sit on the focal point (in the speedrun demo: the person, the cat, the window; for new subject matter, set the focus from your own composition).

## 6. Pitfalls hit

- **Composite modes**: applying `source-in` pattern by pattern wipes each other out (Klimt's gold robe vanishes entirely) — paint the pattern across a scratch canvas first, then `source-in` once against the silhouette; `destination-out` on the segment canvas punches transparent holes, which are black in the video — punch them offscreen, then composite; overlaying paper texture/grain on a character cannot use `source-atop` (the paper color washes the figure out pale) — cut the texture layer with `destination-in` against the silhouette, then multiply it back.
- Self-drawn letterforms: two strokes wound in opposite directions inside one path cancel into a hole under the nonzero rule — fill each part separately.
- "Melt" transitions: let the new image flow down as round-headed droplets (profile `(1-u²)^0.3`); dragging the old image downward produces spikes, which do not read as liquid.
- Set transition duration by the "visible part": inOut easing barely changes at either end, so a complex signature transition at 0.34s only reads for 0.2s and gets read as a plain wipe — give it 0.48–0.5s.
- For translucent stacked pieces like shadow puppetry/paper cut-outs, overlaps multiply and go black; tune stacking order and opacity to the material.

- Writing `putImageData` straight to the target canvas bypasses the engine's camera-impact scale and transition clipping — write it offscreen first, then `drawImage`.
- Give any offscreen context you read pixels from `{willReadFrequently:true}`; call `g.reset()` every frame, or the previous frame's lineJoin/state lingers and the first frame does not match the rest.
- `drawGirl(mode:'line')` composited on top draws occluded parts' outlines straight through (the far sleeve through the torso, the back half of the hat brim through the hair). Use `RIG.visibleLines(key, (g, lineColor) => draw the whole thing, realLineColor, box)`: draw the same way twice with the line color swapped to white as a sentinel; the pixels that differ between the two passes are the lines that are not occluded (facial-feature lines included). Work in the order "fill → style texture → visibleLines to restore lines".
- **The camera impact must hit both the old and the new layer**: punching only the new layer means that at the start of a transition the new layer has not appeared yet, so nothing moves on the downbeat frame, and it sounds like "the sound arrives before the picture" (v1 review measured 0.1–0.17s of lag).
- **Swapping seeds on whole-screen strokes at 8fps = flicker, not life**: review measured full-screen jump frame differences of 18–20, larger than a transition. Keep stroke positions fixed and let the direction field vary continuously over time (flickering like a flame); reserve boiling for the line art.
- Do not give the moving region its own parameters (tessera size, stroke density) — when it stops, it is a patch.
- In coarse-grain styles like mosaic/pixel, set type in bold monospaced strokes (each stroke ≥2 grains wide); thin typefaces break up.
- Make small things bigger than feels right: an ukiyo-e wave claw at 22–50px does not read; 44–74px is "The Great Wave off Kanagawa".
- Determinism: seed every random value; rendering the same t twice must be pixel-identical, or it flickers during render.

## 7. Division of labour (multiple agents drawing in parallel)

Write `era-author-spec.md` (the per-era author spec) first (interface, available libraries, reference implementation, hard requirements, reference files, self-check commands, delivery notes), then dispatch agents four eras at a time. State plainly in the spec: "do not modify lib/ or anyone else's files." Each group hands back in 30–35 minutes, and the notes settle straight into `style-recipes/` (the style recipe library). The first pass had all 16 segments accepted in one go — the spec plus the reference implementation did that work.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
