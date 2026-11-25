# 06_renaissance · 1503 High Renaissance (Leonardo-style)

16–37ms per frame (median 16ms).

## Pipeline
1. Static layer `ren_static`: paint the whole room onto the raw canvas first, then draw that entire layer into the cache with `filter: blur(1.3px)` — equivalent to one full-frame pass of sfumato. The room contains:
   - Walls: P.texture #43321f→#22180e, plus a radial gradient for the window glow, darkened toward the top.
   - Window: round-arched window, stone frame lit on the left, distant view in the opening.
   - Floor tiles: perspective checkerboard. Computed by true projection: `y = 420 + f·h/Z`, `x = 960 + f·X/Z`, f=1029, h=5.75, Z starting at 16 and stepping 1.4 per tile going forward. The first row lands at y=790, then 825/868/922/989 — matching the source's row spacing. Tile colors #a88c64 and #5c2418, with a soft-light pool of light on top plus a radial gradient darkening the periphery (centered at 760,960).
   - Square table with white cloth, ladder-back chair.
2. Distance (aerial perspective): three layers of mountains, bluer and paler with distance (#9fb4b8 → #7d9294), contours generated with fbm. Then lake, valley (gray-green shading into warm ochre), a winding silver-white river (width growing from 3 to 16px with distance), cypresses and round trees, stone bridge.
3. Each frame, in order: river glints (24 points of light moving downstream, twinkling) → birds → ornithopter (all three clipped to the window opening) → character layer → light shaft and dust → glaze layer.
4. Glaze layer `ren_over` (one `drawImage` after caching):
   - Vignette: α0.3 at 0.55, α0.8 at the edge.
   - Yellow varnish: α0.07.
   - Canvas weave: one line every 3px.
   - Oil-paint brush texture: 9000 strokes, α0.022/0.028, line width 5–10, random direction.
   - Craquelure: P.craquelure at α0.32; then turn it into white lines with `brightness(0) invert(1)`, offset 1px at α0.16 and composite with `lighter` — imitating the bright edges of lifted paint film.

## Sfumato
Characters are drawn into an offscreen layer `renChars`, processing only the region (320,180,1200,780). They are drawn back to the main frame in two passes: first `blur(2.6px)` fully opaque, then a sharp layer at α0.38 on top. Edges stay soft while features remain legible. Characters have no line work; all volume comes from gradients:
- Skirt folds: bright folds rgba(200,70,60,.3), dark folds rgba(40,0,0,.45).
- Velvet sleeve: a light band rgba(170,200,140,.45) along the bone direction.
- Face: lit from the left with a gradient, plus eye-socket shadow.

## Motif animation
- Ornithopter: flies from x=470 to 740 over 0–1.35s while bobbing and pitching slightly. The two bat wings flap on `up = 0.5+0.5·sin(t·12+phase)`, with the wingtip between −118 and +24px. The far wing is scaled to 0.78, darkened, and phase-shifted 0.5. Wing construction: leading-edge spar + 6 radiating ribs + scalloped trailing membrane, with the tail fin also swinging. The first version was a flat "paper plane" that did not read as Leonardo's ornithopter; only after redrawing the current ribbed fan wing did it read.
- Light shaft: the wedge is drawn into the cache once with `blur(28px)` and composited each frame in screen mode. The first version filled a polygon directly each frame and its two hard edges looked fake. Dust is 46 particles drifting slowly up along the shaft and twinkling.
- The girl sips from a silver cup on the choreography, eyes closing when cup>0.7. The cat keeps its eyes narrowed in a smile, tail swinging.

## Pitfalls
- The first version's oil texture used 26000 strokes at α0.05 with direction driven by noise, which turned the wall into Van Gogh swirls (Post-Impressionist). Dropping to 9000 strokes at α0.025 with random direction restored the classical oil feel.
- The inner darkening on the cat's body outline first used 26px at α0.45, which made the cream body look like it was under a glass dome. Changed to 14px at α0.22, with the white chest blending the orange fur in through a radial gradient and no hard boundary.
- The floor tiles were too bright and too contrasty at first, like vector illustration. The periphery must be darkened, leaving only the pool of light where the window light falls.

## v2 rework (shot review: too static, 0.20 vs 0.46; the subject was blurred while the view outside the window stayed sharp — depth of field inverted)
- Sfumato changed to: blur layer 1.6px (was 2.6), sharp layer α0.82 (was 0.38). Soft edges kept, features and contours now clear.
- Ornithopter scaled 1.6×, flight path 440→790, pitch amplitude ±0.07; birds increased to 14 and scaled 1–1.8×.
- Cat: head tilts and rubs about the neck ±0.16rad, squint alternating tight and loose, tail ×2.2, breathing ×3, look turning left and right. Girl: hair tips swing ±11px, sip ×1.6.
- Cloud shadows sweep the valley outside the window; light-shaft brightness varies with "cloud passing the sun" at 0.75±0.35; dust 70 particles.
- Still-segment frame diff: 0.20 (review metric) / 0.30 (my measurement) → 0.37. Source 0.43.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
