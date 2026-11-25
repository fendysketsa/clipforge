# 32_rembrandt · 1642 Rembrandt chiaroscuro

> Source: migration test D (an independent agent implementing straight from the read-only skill, 2026-10-04). After integration the scene code was ported to `scripts/art-motion/engine/scenes/32_rembrandt.js`.

File name at experiment time: `scenes/r1_rembrandt.js`, about 47ms per frame.

**Pipeline**: full-light underpainting (draw the room, the leaded diamond-pane window and the Turkish table rug in the colours they have when "everything is lit") → repaint the background with big brown strokes, then blur 2.2px and composite at 75% (a scumbled ground) → the table rug on its own layer, fine strokes → characters in flat fill + volumetric gradients + fine strokes → the characters' "lost edge" treatment → **light map multiply** → window glass screen highlight + cloud shadow sweeping across → bristle impasto → candle flame, dust motes in the light shaft, heat haze → craquelure, grain, a cached vignette layer + soft-light golden-brown glaze.

**Key parameters**
- Light map: base colour rgb(30,21,13), equivalent to ambient 0.13. Composited with lighter:
  - Light shaft: wedge polygon, blur 40px, cached, α 0.8–0.95.
  - The window itself: r330.
  - Face pool: r250 α0.95. Chest: r230 α0.55. Cat: r240 α0.8. Tabletop: r280 α0.6.
  - Candlelight: r190+40·fc, α 0.6+0.4·fc.
  - The "separation light" on the wall behind the girl: r300 α0.35. Rembrandt often brightens the wall behind a figure's shadow side, to separate the figure from the background.
  - Composite the whole frame multiply.
- Flicker: `flick(t) = 0.5·noise(2.2t) + 0.25·noise(6.5t)`; the light-pool centre drifts ±14px with noise(0.9t); cloud shadow `cloud = 0.5 + 0.5·sin(2.2t − 0.6)` scales the window light by ×(1 − 0.35·cloud), while a dark radial blot crosses the glass at 260px/s.
- Background strokes: cell18, len54, w16, jitter 6, angle −0.9 + 1.6·noise(0.003); palette mixBase 0.7.
- Lost edges: draw the character layer once fully opaque with blur(2.4px), then composite a sharp layer at α0.62. The shadow side melts into the background and the features are still recognisable.
- Impasto (bristle brush): one stroke = round(w/1.3) parallel fine bristles, each with brightness ±17, both ends randomly shortened 0–25%, line width 1.4–2.6; one α0.28 cast shadow underneath; sprinkle 2+w/3 highlights on top. Only used where the light lands: blonde hair, collar, china cup, pearl, the cat's white chest, the top of the cat's head.
- Overlay layers: craquelure α0.28×0.28; grain density 0.05 α0.12; vignette 0.75; soft-light rgba(200,140,60,.35).

**Motif animation**: candle flame (noise-driven side-to-side tilt, height jumps), window light dimmed by the cloud shadow and then recovering, 70 dust motes in the light shaft (drawn only inside the shaft, flickering on a 24-frame cycle), lifting the cup, heat haze. Motion area 8.0% (0.45↔1.0s).

**Pitfalls**
- The first version of the impasto was three tidy lines — offset shadow + main stroke + bright ridge — and read as a white sticker or a band-aid. Only the bristle brush made it read as paint.
- Copying a region of the source image back (`drawImage(b, x,y,w,h…)`) brings the unbrushed background with it and leaves a rectangular patch. Props should go on their own layer drawn after the strokes; do not copy regions.
- Grain at density 0.12 / α0.22 covers the face in dirty specks; 0.05 / 0.12 is just right.
- The hand has to be drawn before the cup, otherwise the hand's ellipse covers the china cup. The order inside drawGirl is "hand → cup → thumb"; follow that order if you redraw it yourself.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
