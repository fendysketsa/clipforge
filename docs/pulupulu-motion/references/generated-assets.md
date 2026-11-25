# Generated print assets — an image model draws the art, the film assembles it

Owner: image-model art, cropping and mounting

Use this route when the story needs objects, places, people or archival-feeling material that no icon
library carries and that hand-drawn SVG turns into a sticker: hardware, documents, magazines, consoles,
portraits, maps. It replaces "draw it with paths" with "brief it, generate it, crop it, mount it".

It is a **different** route from `references/asset-sourcing.md`: that one is for glyphs (silhouette or
line), this one is for pictorial panels. Never mix the two inside one shot.

---

## 1. Write `DESIGN.md` before generating anything

The image model has no memory of the film. Everything it must obey has to be on one page: register,
palette with one job per colour, texture substrate, and a hard-requirements block that repeats for every
asset. Without this the twelve images arrive in six different visual dialects.

```markdown
## Register, in one sentence
"Printed, not lit." — ink and halftone on cream paper, cut with a knife, dropped on a surface.
Never glow on black.

## Palette — every colour has ONE job
paper #F1E8D6 the canvas · ink #14120F structure and type · yellow #F2B33D the one emphasis marker
red #C8402F the old / cost / negation · cobalt #24406E the new · muted teal #3C6A61 the past

## Hard requirements for every image
- paper background, full bleed, no border, no vignette, no frame
- object centred, ≥ 90 px paper margin; NO text, letters, numbers or logos anywhere
- hard offset shadow down-right ~18 px, 100 % opacity, no blur, no glow
- halftone/print texture inside ink areas only (keep it off light faces)
- 1024x1024 PNG, sRGB

## Asset list
| # | file | what it shows |
|---|---|---|
| A1 | a1_well.png | top-down ink well, teal locked stack, one yellow piece above |
```

A register table from a real film, which works because each colour carries meaning instead of decoration:

| colour | job |
|---|---|
| paper | the canvas; every frame sits on it |
| ink | structure, type, the well, the rules |
| yellow | the ONE emphasis marker per shot — highlight, never a whole-scene fill |
| red | the old, the cost, the negation: rights, money, *pulled*, theft |
| cobalt | the new: rights secured, the company, the era that won |
| muted teal | locked blocks, secondary objects, "already happened" |

Two rules fall out of it: **red and cobalt never share a beat** except the turn, and **one yellow
emphasis per shot** — a second yellow kills the first.

## 2. Generate, four assets per call

A hosted image tool inside a coding CLI is the cheap path when the key is already installed. Ask the CLI
to use its own image tool, name the exact filenames, and demand a manifest — a claim of success is not a
file on disk.

```sh
codex exec --skip-git-repo-check -m <model> -c model_reasoning_effort="medium" "Read DESIGN.md here. Generate a1_well.png, a2_shapes.png, a3_ball.png, a4_terminal.png exactly as specified. One image-generation call per asset, 1024x1024. Save each with exactly that filename in this folder, resize if the tool returns another size, verify each file exists and is a PNG, then print a manifest: filename, bytes, pixel size, and one line on what the image actually contains." > gen_a1_a4.log 2>&1
```

- **Four per call, not twelve.** A batch of four finishes inside a background job; a batch of twelve
times out and saves nothing. Run batches sequentially — the same CLI writing the same folder in parallel
collides.
- **Run it as a background job with notify**, output to a log: image generation runs minutes per asset.
- **Ask for the manifest every time.** It is the only way to know the tool's real output size, and it
exposes deviations (margin too small, halftone bleeding onto light faces, wrong cell count) while the fix
is still one more generation instead of a re-cut film.
- **Look at the batch before generating the next one.** A four-up contact sheet (`PIL`) plus one look at
it catches a drifting palette in batch 1 instead of batch 4.
- Prompt the CLI on **stdin** (`< prompt.txt`) whenever the command also carries `-i image` flags — a
  prompt passed as an argument after them is swallowed as another filename.
- **Say what the frame is, not only what the object is.** "A background plate" is ambiguous and comes back
  as a small painted rectangle floating on cream, useless behind a cut-out. Brief a plate as **the image
  itself is the entire frame**: painted edge to edge in the delivery aspect, sky reaching the top edge,
  water reaching the bottom, no border, no card, no vignette — and state the horizon height as a
  percentage of frame height.
- **Forbid withholding for framing.** A careful model will refuse to save an asset because the tool
  returned 1254 px or the object touched an edge. Both are post-processing problems, not failures: say
  "do not withhold for size or margin, I crop and pad". If it still holds the files back, take the raw
  generations from the CLI's own `generated_images` cache and normalise them yourself rather than paying
  for a second generation round.
- **Check a cut-out twice.** The alpha histogram *and* a look at it composited on a mid-grey background: a
  figure can arrive drawn on a cream card at alpha 255, which no histogram can see and which reads as a
  panel in the next frame.

## 3. Crop every print to its content before mounting

Generated art arrives with the paper margin it was told to keep, so mounting the 1024 px file as-is gives
**a huge empty frame around a small object** — the "double frame" that reads as an unfinished panel. Crop
once, at build time, and cache the result next to the page.

```python
from PIL import Image
import numpy as np

src = Image.open(path).convert("RGB")
# the paper is the MOST COMMON colour in the image — never sample the corners: on some prints the ink
# touches a corner and the "paper" you sample is ink
quant = src.quantize(colors=24, method=Image.MEDIANCUT).convert("RGB")
counts = {}
for n, rgb in quant.getcolors(src.width * src.height):     # note: (count, rgb), in that order
    counts[rgb] = counts.get(rgb, 0) + n
paper_rgb = max(counts.items(), key=lambda kv: kv[1])[0]

delta = np.abs(np.asarray(src).astype(int) - np.array(paper_rgb)).sum(2)
mask = delta > 60
# a soft vignette or edge noise puts a few differing pixels on every row; require real coverage
rows = np.where(mask.sum(1) > max(3, int(src.height * 0.004)))[0]
cols = np.where(mask.sum(0) > max(3, int(src.width * 0.004)))[0]
box = (cols.min(), rows.min(), cols.max() + 1, rows.max() + 1)
```

Two PIL traps that cost time:

- **`ImageChops.difference(a, b)` silently crops to the overlap.** Comparing a 1024² print against an
  8×8 swatch of its own paper colour returns an 8×8 difference and a 26 px "bbox" — the script then
  "crops" the artwork to nothing and reports success. Build the paper image at `src.size`, or use numpy.
- **`getcolors()` returns `(count, rgb)`**, not `(rgb, count)`. Unpacking it the other way round raises
  `TypeError: unsupported operand type(s) for +: 'int' and 'tuple'`.

Pad the box by ~32 px (keep the drawn shadow inside the crop), then make the crop **square** about the
object's centre so mounted panels share one optical size. Keep the halftone — that is the material.

## 4. Assemble: mount, label, caption, move

- **The shadow is already in the art** — do not add a CSS `outline` + `box-shadow` on top of the panel;
  that is the second half of the double-frame bug. Standard shots get no keyline; only the two beats you
  deliberately bleed get a 2 px ink rule.
- **Size from the crop, not from the file:** fit the visible art inside ~`760×860` on a 1080-wide frame,
  centred below the label band. A small object (a ball, a single cartridge) needs its own number — a
  panel sized like the others leaves it looking lost.
- **Bleed is a choice, not an accident:** one or two hero beats may take a 1080 px panel past the paper
  edge (`left:-24px`), and the label moves *below* the panel on those beats rather than over it.
- **Paper texture and dots go BEHIND art and type**, at ~8 % (dots) and ~25 % (grain). A global overlay on
  top flattens every material into one surface — the same dot rhythm on a CRT screen and on the paper
  around it is what makes a generated print look pasted.
- **Labels and captions are added here, never baked into the image.** Text in a generated image is
  unusable: misshapen glyphs, invented words, unlocalisable. Keep the images textless and put every word
  in HTML where it can be corrected, translated and re-timed.
- **Motion vocabulary for a printed sheet:** paper slap-in (`scale 1.15 → 1`, `back.out(1.15)`, settle
  1–2° crooked), highlighter swipe behind a word (`scaleX 0 → 1`, `power2.out`, 0.18 s), sheet-wipe as
  the only transition, stamp (`scale 1.6 → 1`, `power4.in`), and a slow drift for the rest of the shot.
  Forbidden: glow, blur transitions, perfectly straight settles, gradients on objects.

## 4b. A recurring character across many poses

A person who has to be the same person in eight shots cannot be generated shot by shot: the model has no
memory of the sheet it drew yesterday, and each call invents a face. Build the character before the film.

1. **Approve the head before any pose.** One sheet, the same head in three views (front, three-quarter,
   profile), one age, no body, transparent background, equal spacing and one eye line. Lock eye spacing,
   nose profile, ear placement, jaw proportions. Regenerate until the three views are obviously one man —
   this sheet is the reference for everything that follows.
2. **Generate every pose against that sheet** (`-i face_sheet.png`) with one fixed template: keep the
   supplied face and its proportions, then vary only pose, wardrobe, age and camera angle. Never re-describe
   the face in words; the image reference is the specification.
3. **Age the face, do not redesign it.** Young and old versions are edits of the approved views — hairline,
   greying, wrinkles, soft tissue — not new characters.
4. **Write the pose set as a table before generating** (action, age, wardrobe, facing) so drift is visible on
   paper instead of in a render. A supporting character is a *different* person by design: say so, or the
   model quietly reuses the protagonist's face.
5. **Crop every pose identically.** Alpha bbox → same long side → same anchor point, or the character
   changes size against the background between shots and reads as a different person.

A character-led film also needs the character in most beats: the machines or documents are what he made, and
one or two beats of the object alone are enough to show it.

## 5. One critique round, then converge

When the art came from another model, one exchanged round is worth it — it catches assembly mistakes the
model can name because it knows what it drew. Then stop: this user pays per token for both sides.

Send the ten delivered frames plus a brief that lists **what you assembled and what you think is wrong**,
and demand numbers back (px, seconds, easing, colour). Prompts that get useful answers:

- "your prints carry a 90 px paper margin, so the keyline plus that margin reads as two frames — crop or
  keep the margin, and say why"
- "the highlighter sits only on the hero label; should the caption get one, and on which word"
- "what is the cheapest change with the most effect on the fact that the print never moves relative to
  the paper"

Apply what it returns in **one pass**, re-render once, and report which suggestions you took and which
you rejected. A second round is a new project, not a continuation.

## 6. Before the render

- Contact sheet of one frame per beat — a print that fills its panel in batch 3 can sit tiny in beat 12
  because two assets were cropped at different scales.
- Read the frames for the register you wrote down: is every colour doing its job, is there exactly one
  emphasis per shot, is the paper the same cream everywhere.
- A render that stalls after assets were added is almost always paint cost, not the images: an SVG
  `feTurbulence` used as a CSS `background-image` re-runs the filter on every repaint. Bake the grain to a
  PNG tile once, and keep that tile near-white (mean ≈ 247) if the layer uses
  `background-blend-mode: multiply`, or a grey tile turns the cream ground grey.
