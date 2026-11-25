# Pixel art — a documentary look with hard pixel edges

Path: graphics
Owner: pixel-art rendering discipline — grid, palette, outline, type, motion

For a film that must read as **pixel art** rather than as vector art with a retro filter over it. The rules
below are what makes the difference; every one of them was exercised on an 8-minute documentary that rendered
15,400 frames with zero freeze holds.

Pixel art is a *grid discipline*, not a palette and not a font. If a single draw call uses a fractional
coordinate or the footage is scaled by a non-integer factor, the result is mush at any zoom and the whole
look collapses.

---

## 1. The canvas is small, and the scale is integer

| layer | size | rule |
|---|---|---|
| logical canvas | **360×640** for 9:16 (270×480 for a 4:5, 640×360 for 16:9) | every coordinate is a whole number in this space |
| delivery | 1080×1920 | **exactly ×3 nearest-neighbour** — `np.repeat(a, 3, 0)` / `np.repeat(…, 3, 1)`, or ffmpeg `scale=…:flags=neighbor` |
| 1080×1920 at ×3 | 360×640 → 1080×1920 | 360·3 = 1080, 640·3 = 1920, so nothing is resampled unevenly |

- **Pick a logical size that divides the delivery size exactly.** ×2 or ×3 only. ×2.5 or a fit-to-width resize
  destroys the grid, and no amount of drawing care survives it.
- **Never anti-alias.** No `ImageDraw` line smoothing, no SVG, no CSS transforms, no `scale` in a browser
  renderer. A pixel-art frame is a hard-indexed bitmap, so render into a buffer and upscale once at the end.
- **Round at the draw call, not at the end.** Keep a single helper (`px(x) = int(round(x)))`) and use it for
  every coordinate so a moving object lands on the grid even when its motion is computed in floats.
- **Verify the grid mechanically**, not by eye: assert the encoded frame is an integer multiple of the logical
  canvas and count the distinct palette values used per frame.

## 2. Palette: fixed, indexed, and every colour has one job

- **≤ 24 colours**, declared once in `DESIGN.md` as `index → hex → job`. Store frames as a `uint8` buffer of
  palette indices (`shape=(640, 360)`, values `0..N-1`) — not RGB — so a stray shade cannot sneak in.
- **The white theme is a ground, not an absence.** A warm off-white (`#F7F5EF`) ground with a near-black ink
  (`#18161A`) leaves 3–4 accent hues free to carry every object. A pale paper ground plus saturated objects is
  what reads as “coloured assets on white”; grey objects on white read as an unfinished diagram.
- **No gradients.** A ramp is 2–3 stepped palette entries, or a real 1-px checkerboard dither. A smooth blend
  is the tell that the look is vector underneath.
- **Palette count is a gate.** If a frame uses an index outside the declared range, the renderer, not the
  artist, is wrong — assert `max(index) <= N-1` every frame.

## 3. Outline and shading

- **1-px hard ink outline** on every object, card, icon and sprite: at logical size, one pixel; after ×3 it is
  a crisp 3-px border.
- Shade with one darker step of the object's own hue, placed on the side away from the light. Two steps for a
  large mass, one for a small one; no soft shadow.
- **Contact shadows are still needed** — a dithered ellipse or a flat dark step under a figure — or objects
  float on the paper.

## 4. Type is drawn, not set

- Use a **bitmap font rendered into the buffer** at integer sizes (8, 12, 16, 24, 32 logical px), or a
  pixel-styled face at a size that is a multiple of its pixel grid. A scaled system font reintroduces
  anti-aliasing and is instantly wrong next to the art.
- Floor for captions: **20–24 logical px** (60–72 px delivered) — pixel type is chunkier than vector type, so
  the usual 36–40 px delivered figure is too small here.
- Keep one accent colour for emphasis inside a caption line, and put captions on a bordered plate on the paper
  ground rather than over the art.

## 5. Motion: animate properties, not sub-pixel positions

A pixel object cannot slide smoothly — a fractional translation either snaps (juddering) or gets resampled
(blurring). So:

- **Move in whole logical pixels**, at a speed that suits the beat; a 1-px-per-2-frames drift is a legitimate
  “slow”.
- **Animate the property instead of the position**: a lamp swings, smoke puffs rise and fade, a wheel rotates
  about its axis, a cursor blinks, dust motes wander, a bar fills in whole-pixel steps, a paper slides one
  pixel at a time on a fixed cadence.
- **A static plate needs ambient life** or the freeze gate fails: a 1-px dust mote, a blinking status light, a
  slowly filling gauge. Every scene carries its own motion; the cut is what changes the view.
- **Paper texture is a static pattern**, drawn once into the ground (a single-colour dot grid at one pixel per
  4–8 px), never a per-frame filter.

## 6. Scenes that survive 8 minutes

- **Vary the register, not just the layout**: RAM-grid diagrams, a period machine, a room with a desk, a
  temple of pillars, a gear, a timeline strip, a two-column compare, an end card. A chapter title card between
  registers buys rhythm cheaply.
- **Keep a persistent frame**: chapter number and name, a progress bar, and a caption plate in the same place
  every scene. The frame is what makes 90 unrelated scenes read as one film.
- **Draw the artefact, not a symbol for it.** A 1972 machine is a box with a fan grille, a tape reel, and a
  terminal; a generic rounded rectangle with a label is the failure mode.

## 7. Gates specific to this look

Check on the encoded file, in addition to the standing gates in `verification.md`:

1. **Integer scale:** delivery width and height are exact multiples of the logical canvas.
2. **Palette:** the frame's distinct colour count is ≤ the declared N, and no colour is outside the list.
3. **No fractional draw:** state the mechanism (rounding helper / index buffer) that guarantees it.
4. **Freeze:** `freezedetect=n=0.004:d=1.5` on a graphics film — a pixel frame that holds longer than that is
   a still, because nothing about hard edges reads as “waiting”.
5. **Legibility:** extract a caption at full size and read it at phone distance; pixel type at 20 logical px
   is the floor, and a caption that collides with art is a re-render, not a note.
