# Y2 · Vox-style collage explainer: video animation grammar card

In one sentence: put the argument on a desk that holds real material — clippings, photographs, documents — and move the camera across that desk like an investigative reporter's eye; lines and pen strokes are drawn on in stops and starts, and the sense of evidence comes from "these things really were placed here".

Demo film: `scripts/art-motion/engine/demos/y2_vox/` (render with `render.py --film demos/y2_vox`) (8s, 3 shots, 2 transitions), overview: `assets/animation-grammar/y2_vox_overview.jpg`
Basis: research into this style (the original research text and the per-frame data stay in the experiment archive and were not taken into the skill; the numbers used are excerpted into this card). Five sample films: Missing Chapter (2022), the psychedelic-poster film (2019), Vox Borders (2018), Johnny Harris (2026), plus a Vox 2026 live-action film as a control. 13 camera moves were fitted for easing, and colours were sampled.

## Check before you start

1. **Real material is the main picture.** Screenshots, source text and photographs fill the frame or nearly fill it; push in on the sentence that has to be read. The desk is a world the camera travels through, not a background colour behind small images. Measure it: if more than 2 shots in a row have material narrower than 60% of the frame width, that is "picture-frame layout".
2. **"Slide in → typed label → red circle" has to rotate.** When storyboarding, write out a table of reveal actions: appear directly on the cut, push in, glide to the next one, highlighter sweep, red line connect, stamp, tear off… Never use the same reveal sequence more than 3 times in a row. Evidence: in one long film, 36 of 37 labels were slide-ins; by the middle the audience could predict the next step.
3. **Text that has to be read goes on the top layer and is drawn last,** not following the layer of the object it belongs to. Photographs, clips and later-added cards covering the text is the most frequently recurring giveaway in this grammar.
4. **Solve the camera's landing point backwards from what has to be read at that moment** (frame the target, then leave margin); don't type coordinates by hand. A neighbouring card label cut in half at the frame edge gets pushed out of frame.
5. **On an accumulating desk, every time a new card is placed, read the on-screen words through in reading order as one string.** Two cards' words sitting side by side can spell a wrong sentence ("exceed" next to "acquisition"); pull the card or write the qualifier out in full.
6. **A given event's formal action is performed only once.** An action already performed in the wide establishing shot is not repeated after the push-in, otherwise it reads as "it happened again".

---

## ① When to use it

**Use it:**
- Content with real archives, news, history, maps or people: "how this happened", "who said what, and when".
- When the voice-over is a reporter's argument: quotation, evidence, cause and effect. When the narration says "look at this sentence" or "note this number", the picture goes and highlights that sentence.
- When quoting a line, a set of numbers or a year, and the audience has to "see the source with their own eyes".
- The demo film uses the real numbers from the 2012 Google "cat recognition" paper: 1,000 machines, 16,000 CPU cores, 10 million YouTube screenshots, no labelling. Sources are arXiv:1112.6209 and the official Google blog.

**Don't use it:**
- Pure mechanism, pure concept, no real material to stick down. Forced, it becomes a "fake archive"; use Y1.
- Derivations and steps: use Y3.
- Content that needs a lot of character performance: cut-paper characters can only move in stops and starts.

## ② Frame composition

- **Three-colour system** (measured on Missing Chapter):
  - near-black ground `#171716`
  - paper white `#E0DCDA`–`#EEEDED`
  - one red in two steps: bright red `#B65255` for lines, dark red `#93403C` for fills
  - fluorescent yellow `#DACF08` (darker and more olive than the Vox logo's `#FFF200`; the logo yellow is rarely used over large areas in the films)
  - old map paper `#E4DCCF`, parchment `#CFB195`
  - no pure white, no pure black.
- **[This film]:**
  - desk `#e4ddcf`, tiled paper texture, with fibres and low-frequency light and dark.
  - clue red `#b8433f`, slightly brighter than measured, because it has to stay legible at 1080p.
  - fluorescent `rgba(218,207,8,.9)`, composite mode multiply.
  - shot 3 is a large black card-stock sheet `#1b1b1a` on the desk, with desk showing on all four edges.
- **Materials:**
  - Photographs are always greyscale halftone (45°), with a white border and two strips of translucent tape.
  - Clippings have torn edges, are yellowed, and carry a Song-style headline face.
  - Labels are Borders-style black bars with white bold type ("2012 · Google").
  - Index cards are ruled paper.
  - The paper texture is **static**. Measured frame delta in hold segments is 0.0–0.1; there is no per-frame grain — that is Johnny Harris 2026's film-stock look, not Vox.
- **Shadows are very weak.** Black-ground cards show almost no shadow at 360p [measured]. [This film] uses blur 10, offset (3,6), α 0.28 throughout.
- **Deliberately imperfect**: the Vox art director's own words are "You don't want it to look perfect because that might make it look more like an ad than an editorial piece" [first-hand].
- **Characters**: real people cut out of photographs as stickers, with a white border and a shadow. [This film] the author uses `the author.draw`, offsetting the silhouette 12px in 16 directions and laying a layer of paper white underneath as the sticker border.

## ③ Motion paths

- **Two frame rates (the core)** [measured]:
  - The camera layer is smooth 24fps motion.
  - The element layer (map blocks growing, red lines tracing a route, typing, hand-drawn rings, pop-ins) steps at 12fps, "on twos". In the psychedelic-poster film 52% of motion frames show the move–stop–move fingerprint.
  - [This film] the camera is computed continuously at 60fps; every element is quantised with `MO.step(t, 12)` before its progress is computed. QA measured 16.9% static frame pairs in shot 1 — those are the hold frames of on twos, not stutter.
- **Camera easing** [measured, 13 moves]:
  - Median duration 1.29s, range 0.71–1.96s, **not one of them linear**.
  - 7 are symmetric easeInOutSine, equivalent to AE's default Easy Ease, used for long-distance "find the next card".
  - 6 start fast and settle on a long tail, close to `cubic-bezier(.33,0,.2,1)`, used for "pull out to reveal" and "chase along the clue".
- **[This film] camera**:
  - Shot 1: after the highlighter sweep, a 1.5s sineInOut push into that line (1.14→1.28). Measured in BD, a sweep is often followed by one push.
  - Transition A: 1.1s long-tail bezier.
  - Transition B: push 0.6s sineInOut.
  - Shot 3: pull out 0.85s long-tail bezier.
  - Those measured durations (push 0.6–1.5s, pull out about 1s, chasing a line 1.3–1.8s) are the defaults for new films. The demo's shot 1 opening 0.9s slow push (1.14→1.165, 2% and bringing nothing on) and shot 3's 1%/s constant drift after the pull-out are the old way; new films don't copy them.
- **Entrances** [measured]:
  - Archive photographs and clippings **appear directly on the cut**, no bounce, no drop.
  - Only when tracking along a timeline does the next card slide in from off-frame, tilted 5–15°, straightening as it lands, about 0.8s.
  - [This film] small photographs and the author sticker use `slideIn`: 0.55s quartOut, from a 12° tilt to flat, stepped at 12fps.
- **Lines and pen** [measured]:
  - A red underline draws in 0.5–1s.
  - A red ellipse ring takes about 1s, one stroke, ends not closed, slightly crossing over.
  - A highlighter strip takes 1.5–3s per line, sweeping with the words as the narration says them.
  - Typing is about 13 characters/second, on twos.
  - [This film] red ring 0.65s, highlighter 0.9s (compressed for the demo), typing 13 chars/s, each red line 0.5s staggered by 0.15s, the counter rolls to 10,000,000 in 1.4s cubicOut.
- **The camera stops during holds**: measured frame delta in hold segments is 0.0–0.1 — when Vox's desk stops, it stops. While a card has internal animation (tracing, highlighting, typing) the camera doesn't move; if a purely static image holds for a long time, push in at the moment the narration reaches the part that has to be read (finding the card 0.5–0.9s, push 1.0–1.5s, ease in and out; only the reveal itself gets a 0.28s fast push), or glide to the next one — no constant drift.

## ④ Transitions (6 in common use)

1. **Hard cut**: the overwhelming majority, with cut points sitting on narration punctuation [measured].
2. **Glide along the red line (timeline tracking)**: the camera moves horizontally along a red line, 1.3–1.8s, long-tail easing; the next card slides in from the right at an angle and straightens.
   - [This film] Transition A: a red line runs from the highlighted line in the clipping to the counter label on the investigation wall, the camera chases it in 1.1s, with short motion blur along the direction of travel (7 samples, factor 0.6).
3. **Push into paper or a photograph → hard cut to a high-resolution scan of the same image**: 1.0–1.4s, S-curve easing.
   - [This film] Transition B: push all the way into the small photograph on the wall (log interpolation to z≈9.6); hard cut to a large scan of the same image (the halftone dots go from fine to coarse, reading as "swapped in a clearer one"); then cut to 3.
4. **Pull back from a single photograph → reveal the whole collage**: about 1.0s, fast start, long tail (measured at MC 2:30).
5. **Map blocks growing, route tracing**: 2.5–3.5s, on twos, with a solid red dot at the head of the line.
6. **A real hand turning pages, pulling paper** (Missing Chapter's signature): in code this can be approximated as "paper sliding in along an arc with a change of shadow".

**Note**: the "torn-paper transition" does not appear once in the five sample films. It is a template-site convention, not Vox grammar. The first version of this film used a torn-paper transition; after reading the research it was replaced.

## ⑤ Pacing and text

- **Shot length** [measured, collage sections]:
  - Two settings: slow (Missing Chapter) median 3.3s, about 12 cuts/minute, one card held 3–7s, carried by the tracing and highlighting inside the card.
  - Fast (psychedelic poster 1.8s, Johnny Harris 1.4s) about 25–33 cuts/minute, the image barely moves, the rhythm comes from the cutting.
- **Aligned with the voice-over**:
  - Highlighter, typing and tracing are locked to the speed of the spoken words, not to musical beats.
  - Johnny Harris's formulation is "Each word must correspond to a movement or action within the animation"; he writes his scripts in two columns [first-hand].
  - Joss Fong changes the music roughly every 20s [first-hand].
- **Text**:
  - Names and places in small serif type, white on the lower part of the photograph.
  - Black-ground timeline titles type on character by character, 13 chars/s, with a red line running across the frame.
  - Quotations surface in a handwriting face in an "ink spreading" way, about 2s, then a red bar follows along line by line [measured].
  - [This film] clippings and cards use Songti SC, large labels use PuHui-Heavy, numbers use Anton.

## ⑥ Implementation notes

> After being taken into the skill (2026-10-04 v0.4): the general-purpose functions in this card's "newly written" list have been consolidated into `scripts/art-motion/engine/lib/` (renamed to the unified MO / CAM / DG / TY / CH / UI / CL / TOON), and the demo's own code lives in `scripts/art-motion/engine/demos/y2_vox/`. For the library quick reference and "how to choose a grammar for a stretch of voice-over", see `references/art-motion/09-animation-grammar.md`.

- Reused from the skill:
  - `PAINT.cached`, `PAINT.scratch`: every paper piece, photograph and clipping is drawn once into a sprite
  - `PAINT.grain`: static grain
  - `PAINT.noise/fbm`
  - `KIT.densify/resample`: hand-drawn rings
  - `the author.build/pose/draw`
  - the engine transition interface
- Newly written, now consolidated into the library (`scripts/art-motion/engine/lib/collage.js` / `camera.js` / `diagram.js` / `motion.js`):
  - `MO.step(t,12)`: on twos.
  - `CL.paperTile`: tileable paper texture, sampled on a torus so it is seamless, with fibres.
  - `CL.halftone`: converts to greyscale 45° dots, batched into one path and filled in a single pass.
  - `CL.tornEdge`: torn edge.
  - `DG.hand / DG.drawPartial / DG.cum`: hand-drawn lines, traced out by length.
  - `CAM.motionBlur`: stacks frames along the direction of velocity.
  - Real-material pieces for new films: `MD.print` (a print: white border, aged paper colour, shadow, tape, croppable to a focus point), `MD.label` (black torn-edge label, 12fps typing), `MD.cover` (full-bleed layout + focus + push-in, for hard-cutting to live footage); shots use `CAM.track`'s glide and push, with punch reserved for accents. The y2 parametric clip has already moved to this set: photographs occupy 80–90% of the frame, the camera moves to the next item in 0.7s by default, and highlight slow-pushes for 0.9s (writing `"camera": "snap"` in the spec's top-level `data` switches it to a 0.30s lateral move and a 0.28s fast push) — no constant slow push.
  - `MO.bezier`: long-tail easing `(.33,0,.2,1)`.
- The demo's own (`demos/y2_vox/vox.js`; `slideIn / highlight / stringPts` have since gone into the library as `CL.slideIn / CL.highlight / CL.stringPts`):
  - `slideIn`: tilted slide-in to flat.
  - `highlight`: highlighter strip with rough edges, multiply.
  - `stringPts`: red line with sag.
  - `deskCam`: desk camera keyframes, plus a push at the end.
- **Key architecture**:
  - Shots 1 and 2 are the same desk world and the same camera. Transition A uses `same` (A and B were already the same picture), and the movement is done entirely by the camera.
  - Shot 3 is the large black card stock on the desk. Transition B uses `cut`, cutting on the fully pushed-in frame.
- **Performance**: shot 3 costs 73/89ms per frame (mean/peak); the author sticker needs 16 offsets per frame to pad its border. The sticker border can be cached and only recomputed when the pose changes at 12fps.

## ⑦ Reference films and first-hand sources

- Sample films:
  - Missing Chapter, "The case to rename this famous Christmas plant" https://www.youtube.com/watch?v=lLSUjl4WatY
  - "Where the 1960s \"psychedelic\" look came from" https://www.youtube.com/watch?v=9vuqI2v2IRs
  - Vox Borders, "China is erasing its border with Hong Kong" https://www.youtube.com/watch?v=MQyxG4vTyZ8
  - Johnny Harris, "The Internet Didn't Fail. It Was Taken." https://www.youtube.com/watch?v=0rKDo3hKbVk
- First-hand:
  - Interview with Vox art director Joey Sendaydiego https://www.storybench.org/how-vox-uses-animation-to-make-complicated-topics-digestible-for-everyone/
  - Joss Fong interview https://www.theopennotebook.com/2020/01/07/videogram-how-a-vox-video-explains-the-science-behind-the-first-photo-of-a-black-hole/
  - Johnny Harris, "How I Make My Maps" https://www.youtube.com/watch?v=GsojLuJpe_0
- Second-hand: PremiumBeat, "Replicating Vox motion graphic" https://www.premiumbeat.com/blog/replicating-vox-motion-graphic/
- Demo film facts:
  - Le et al., ICML 2012, arXiv:1112.6209 https://arxiv.org/abs/1112.6209
  - Official Google blog, 2012-06-26 https://blog.google/innovation-and-ai/products/using-large-scale-brain-simulations-for/

## ⑧ The three easiest things to get wrong

1. **Everything moving smoothly together at 60fps.** Half of the collage's handmade feel comes from the two frame rates: "the camera glides, the elements stutter". All smooth looks like a corporate promo; all 12fps makes the camera sickening.
2. **Passing template grammar off as Vox**: torn paper, every image bouncing and dropping in, paper texture jittering frame by frame. None of these appear in the measurements: Vox's photographs are simply there on the cut, the paper texture is dead, and the transitions are mostly hard cuts and pushes. The more showy the entrances, the less it looks like editorial work.
3. **Using Vox logo yellow as a large-area ground and spreading too much colour.** The yellow in the films is the `#DACF08`-step highlighter, used only to mark emphasis. The body is the three colours "black, paper white, one red", and one accent colour on top is enough.

**Don't eyeball a parametric clip's `highlight.rect` off the preview image.** rect is 0..1 coordinates relative to that image; estimating from a downscaled screenshot is typically 0.05–0.1 off overall, and the highlighter and red ring land on the neighbouring word. Measure pixels on the full-size image and divide by width and height; when the material is a web screenshot, read the target text's bounding box straight from the DOM and convert it into fractions of the screenshot element (a community-contributed method, see issue #6):

```js
const box = document.querySelector('#abs').getBoundingClientRect();   // the element that was screenshotted
// find the text node holding the target text and the offset i
const r = document.createRange(); r.setStart(node, i); r.setEnd(node, i + 'cat faces'.length);
const q = r.getBoundingClientRect();
[(q.x - box.x) / box.width, (q.y - box.y) / box.height, q.width / box.width, q.height / box.height];
// → write it into data.rect; then grab a frame after highlight's `at` with render.py --stills and check it
```

---

## Review and revision (an independent agent sees only the finished film, 8/10)

Review comments and what was done this round:
- "Shot 3 turns pure black, the one big desk breaks": changed to a large black card stock laid on the same desk, with desk texture showing on all four edges. Still Missing Chapter's black-card grammar, but the desk is unbroken.
- "0–0.9s completely static": the demo at the time added an opening slow push (1.14→1.165). The current rule: put the first event inside 0.3s (photograph already there on the cut, highlighter or red line starting immediately), or open with a single 0.17s slam.
- "Halftone mush filling the screen for too long": the push shortened from 0.7s to 0.6s, the pull-out from 1.0s to 0.85s. The pull-out starts at z=3.68 so the photograph has the same screen width either side of the hard cut, and tape is added at the same position on the large image, so the cut reads as "swapped for a high-res scan".
- "The blank paper strip appears first": the strip now slides in at a tilt, typing moved up to 0.4s.
- "The character cuts in from the right, half-body, in one frame": start point moved to 1100px off-screen; the first step at 12fps is still off-frame.
- "The film ends before the highlighter finishes": typing, red ring and highlighter all moved earlier; the highlighter finishes at 1.8s, then holds 0.3s.
- "The word 'cat' inside its head is too small": raised to 40px.
- "The camera is smooth throughout, not enough on twos": not changed. The research measured Vox as "camera 24fps smooth, elements 12fps stepped"; changing the camera to steps as well would depart from the measurement.

## QA (`scripts/art-motion/qa.py` in the skill, final version after revision)

| Shot | Measurement window (s within shot) | Motion area % mean/peak | Static frame pairs % | Jump frames | Per-frame cost mean/peak ms | Determinism |
|---|---|---|---|---|---|---|
| y2_s1 | 0.35–2.58 | 11.02 / 16.71 | 3.1 | 0 | 17.4 / 20.3 | ✓ pixel-identical |
| y2_s2 | 1.1–3.28 | 16.09 / 76.76 | 3.1 | 16 (continuous 2.77–3.28s) | 23.4 / 52.2 | ✓ pixel-identical |
| y2_s3 | 0.35–2.08 | 7.77 / 37.41 | 0.0 | 14 (continuous 0.39–0.83s) | 73.3 / 88.5 | ✓ pixel-identical |

Transition smoke test (each transition rendered once, slowest frame): y2_s2 (same) 55.2ms; y2_s3 (hardcut) 43.8ms

How to read it:
- **Shot 2's jump frames** run continuously from 2.77–3.28s — that is the 0.6s push into the small photograph on the wall, pushing to 9.6×.
- **Shot 3's jump frames** run continuously from 0.39–0.83s — that is the 0.85s pull-out reveal after the hard cut.
- Both are full-screen scaling, camera motion by design. The hard cut itself lands on frame 0 of shot 3, outside the measurement window.
- **3.1% static frame pairs**: comes from on twos on the element layer (12fps hold frames). The first version had a static opening camera and this number was 16.9%; after the review flagged "0–0.9s completely static", an opening slow push was added and it dropped to 3.1%. A lower number here does not mean better: a constant slow push can press static frame pairs very low and it still reads like flipping through slides; the right fix for a static opening is to make the first event happen earlier.
- **Shot 3 at 73/89ms per frame** is the heaviest of the three: the author sticker does 16 offsets per frame to pad the white border, and the black card texture still has to be drawn. To speed it up, recompute the sticker only when the pose changes at 12fps and reuse it on the other frames.

Rerun: `uv run scripts/art-motion/qa.py --project scripts/engine --film demos/y2_vox --out <dir>` (the table above holds the numbers from the experiment; for reruns after being taken into the skill, see the regression table in 09).

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
