# Visual craft: why a flat scene looks cheap, and the rules that fix it

Distilled from research plus a rebuild that failed once in public. The first version of the Tetris film
was rejected as "all visuals weird and bad" while every technical gate passed — `om check` clean, no
pops, narration verified. The gap was craft, not code. This page is that gap, written down.

Sources at the bottom. Where a number is measured from the rebuild, it is marked **[this film]**.

---

## 1. The diagnosis: seven things that make flat vector look amateur

Check a still against this list before blaming the concept.

| Symptom | What is actually missing |
|---|---|
| Shapes read as clip-art | no shading: a single flat fill per object, no shade side, no highlight |
| Everything floats | no ground plane and no cast shadow — objects sit in a void |
| The frame is a void with a small object in it | no depth layers; subject occupies 20–30 % of the frame |
| Colours fight each other | every accent hue used at once, no hierarchy, no per-act palette |
| It looks "AI-made" | dark blue-purple gradient ground + neon cyan-purple glow. This skill's `palette.md` calls it off limits and `deliver.py` red-lights it above 30 % of the frame |
| Nothing breathes | one entrance per shot, then 4 s of dead hold; even timing across beats |
| Wrong-feeling type | one size everywhere, centred by reflex, caption and hero label competing |

**"Weird" is usually composition; "bad" is usually lighting.** Fix them separately.

---

## 2. Shading: four layers per object, one light direction

Draw every object bottom to top:

1. **Shade** — the full silhouette in a *hue-shifted* dark tone (shadows drift toward violet/blue).
2. **Lit base** — the same shape, offset a few px toward the light, in the base colour.
3. **Highlight** — a **rim on the two light-facing sides only** (an L-shaped stroke), 70–80 % opacity. A highlight bar stamped across the top of the block, or a uniform border on all four sides, reads as a glossy UI card rather than a lit object.
4. **Rim (optional)** — a lighter edge on the shadow side, or one smooth gradient glow behind light sources. One `slab()` macro that stamps the same inset border and top bar onto a CRT, an office door and a paper sheet makes three different objects look like one reusable component.

**One light direction for the whole film** (top-left is the safe default) — including every character and
every prop. Cast shadows are flat, hard-edged, offset along the light at ~28 % opacity. No blur: blur is
what makes a flat scene look muddy.

In code, derive the ramp instead of hand-picking colours:

```python
h, l, s = hls(base)
shade = hls_to_hex(h - 0.045, l * 0.58, s * 0.92)   # darker AND cooler
light = hls_to_hex(h + 0.055, min(0.94, l + (1 - l) * 0.34), s * 0.9)  # brighter AND warmer
```

A plain darker version of the base looks muddy; a hue shift is what reads as light. **[this film]**
Applying this one rule changed the blocks from "clip-art squares" to objects with a lit edge.

**Derive shades in HLS, but mix two colours in RGB.** Interpolating *hue* toward black is a trap: `#000000`
reports hue 0 (red), so lerping navy toward it drags the blue through green and leaves a green/taupe stain
across every sky, while a cream act turns muddy brown. `mix(a, b, t)` interpolates r/g/b channel-wise; only
the shade/light derivation of a *single* base colour belongs in HLS.

---

## 3. Depth: layer the frame, then move the layers at different speeds

Four planes, minimum:

1. **Ground** — a three-stop vertical gradient, top darkest, with slight hue drift. Depth with no detail.
2. **Far band** — desaturated, 10–20 % smaller, low contrast. Moves at ~30 % of the subject's speed.
3. **Mid band** — props the subject interacts with.
4. **Subject** — most saturated, highest contrast object in the frame.
5. **Front** — vignette and grain only. Never a third subject.

Desaturation is distance: the far band should be visibly greyer than the subject. Parallax without
desaturation reads as a mistake, not depth.

**Budget the ground above the caption scrim.** The scrim that backs the captions starts around `y = 1360`
of a 1920 frame; a floor drawn at `1400–1620` is painted out by it, so every object appears to float in a
void however good its shading is. Put `floor_y` at `1300–1340`, keep a 4–6 px horizon edge in a lighter
tone, and the cast shadows land somewhere the viewer can actually see.

---

## 4. Composition: asymmetric, on a grid, with bleed

- **Anchor to thirds or an edge.** Centred by default is the generated look.
- **Let one element leave the frame.** A visible edge on something that should be huge looks like a bug;
  a deliberate crop looks designed. **[this film]** the handheld in the trade-show beat bleeds off the
  left edge — the shot instantly stopped looking like a sticker on a background.
- **Reserve the caption band, and count the platform's own chrome.** Keep the subject inside y ≈ 300–1300
  of a 1080×1920 frame and anchor the caption from the bottom (`bottom: 420–480 px`, so a two-line cue
  still clears the ~400 px of player UI on Shorts/Reels/TikTok). An object behind the caption must be
  behind a scrim, and the scrim must start below the floor line (§3).
- **One subject per shot.** If two things compete, split the beat.

---

## 5. Colour: one palette per act, hierarchy inside it

- **Assign a palette to each act** so colour carries the arc: a dark warm palette for the origin, a cool
  device palette for the product act, a light paper palette for the resolution. **[this film]** three
  acts, three palettes (`ink` → `navy` → `paper` from `palette.md`), and the light act lands as relief.
- **Budget per shot:** one background family + at most two accent ramps + ink. Restraint is what reads as
  designed.
- **Warm = subject, cool = context** (or invert deliberately for a story reason).
- **Neutrals are tinted**, never pure grey or black: a dark version of the background hue is your "black".
- **Multicolour is an exception** for one hero object whose colour means something (the seven tetromino
  hues), never for furniture.
- **A colour that carries meaning is a film constant, never the act's accent role.** Per-act palettes
  re-point `accent` at whatever that act needs, so an object drawn with `palette.accent` changes colour
  between acts — a Soviet-era red box drawn that way renders **cyan** in a blue act, and the story stops
  making sense while the palette still looks tidy. Define `CONFLICT = "#c8402f"` (or whichever hue carries
  the meaning) once at module level and use it for every object that must stay that colour — the price
  stamp, the box, the court stamp, the zero — so the hue threads act two into act three instead of
  appearing from nowhere.

---

## 6. Type: one display face, three sizes, real contrast

- One committed display face for hero labels, one text face for captions. Anton/Inter Black is enough.
- Big size contrast between hero label (140–190 px at 1080 wide) and caption (60–66 px). "A few sizes,
  not ten" beats a subtle scale ramp.
- Hero labels on a thirds anchor, caption centred in its band.
- Caption on a light act needs **dark text with a light stroke** and a light scrim — white-with-black on
  cream is unreadable. Make the caption treatment palette-aware in the stylesheet, not per beat.
- Negative space is not unfinished space: give the hero line room.
- **A label helper must offset from the requested `x`, not drop it.** `align: "center"` implemented as
  `left: 0; width: 1080px; text-align: center` ignores the coordinate it was handed, so every centred
  label in the film lands on the same axis — three labels meant for three columns (`12`, `→`, `7`) stack
  into one glyph that reads as `1⁄2`. Keep the coordinate: `left: {x - 500}px; width: 1000px;
  text-align: center`, or drive the centring with `xPercent: -50` inside GSAP rather than in the style
  attribute, where a simultaneous `y` tween cannot fight it.
- **Tracking is per size, not per face.** `letter-spacing: -1px` suits a 160–240 px numeral and welds the
  letters of a 76–104 px word (`TETRIS` → `TE` fused). Use positive tracking (+0.5 to +1.5 px) on words
  and keep the negative value for all-digit labels.

---

## 7. Motion: springs, masks, overlap, holds

- **No fade-ins by default.** A masked rise, a scale that settles from a point, a line that draws
  itself. Overshoot (`back.out`) belongs to things that arrive *in air* or grow from a point — **a thing
  that lands on a surface accelerates and stops**: `power2.in` down to the surface, then a 4 px recoil
  (0.07 s) and settle. `back.out` on a falling block sends it bobbing back up through solid ground.
- **SVG groups need an origin.** A GSAP `scale` on an SVG `<g>` paints from the element origin `(0,0)`
  unless you pass `transformOrigin: "50% 50%"` (or set `transform-box: fill-box` in CSS), so a `pop`
  entrance flies in diagonally instead of growing in place.
- **Overlap**: the next move starts before the last settles. Even spacing is the generated rhythm.
- **Holds are allowed** — after a settle, hold; let the viewer read. Then move again. The pattern is
  fast, fast, hold — not constant motion and not a metronome.
- **Ambient layer**: keep one slow band drifting (a far band at ±10 px over 3 s) so a hold never looks
  frozen. Two limits: it must not be the *only* thing moving (at 1.1:1 contrast the QA's downscaled
  comparator scores it as nothing), and a full-frame **scale** is what stalls the renderer — a full-frame
  **translate** composites fine. So the camera move is `y` (150 px over the shot, `ease:'none'`), never
  `scale`, on the plate element (see `SKILL.md` render traps).
- **Causality**: something causes each change — a click, a drop, a stamp landing. Decoration
  (particles, random glow, an unexplained sweep) is what makes motion look cheap.

---

## 8. Texture: grain and vignette, cheaply

- **Grain**: one static `<feTurbulence>` layer at 6–8 % opacity, or a tiled noise PNG. Static, so it costs
  one raster, not one per frame. Grain reads as "crafted" and also masks gradient banding after H.264.
- **Vignette**: a single radial gradient at 35–40 % on the corners. More than that and the frame looks
  dirty, not cinematic.
- **Banding is the tell**: smooth gradients band after encoding. Either add grain or keep gradients subtle.

---

## 9. The verification pass you can actually run

1. **Contact sheet of every beat** at 110–270 px, in one image. Look for: is the subject the biggest,
   most contrasted thing; is there a ground; does anything bleed; is any caption fighting art.
2. **Greyscale pass.** If two objects become the same grey, the hierarchy is not working.
3. **Phone pass** at 40 % scale. Detail that dies here dies on a phone.
4. **First-frame pass.** Frame 0 is the poster. It must show the subject, not a blank or a lone mark.
5. **Numbers from `om qa`**: `hard cuts` and `average shot` expose the "it reads as slides" failure — a
   film with 2 cuts over 87 s is a slideshow whatever the stills look like. **[this film]** the rebuild
   went from 2 cuts / 29 s average to 22 cuts / 3.8 s average with no other structural change but
   composition and per-beat motion.

---


### Number and year captions

- **Years go on screen as digits**, even though the voice spells them: the caption is notation, not a
  transcript. A spelled year also breaks the chunker — `In nineteen eighty` reads as 1980, then `four,`
  flashes alone.
- **Small prose numbers stay spelled**: `twelve`, `seven`, `four` inside a sentence read better than
  digits and keep hierarchy against a giant hero numeral.
- **Large statistics compress to a readable unit** — `2 million`, not `2 000 000` (nobody counts zeroes in
  a 1 s caption); the zeroes belong on the hero label, not in the subtitle.
- **Weight cue duration by word length**, not equally: a one-word chunk given the same 0.9 s as a
  four-word chunk is what makes captions feel like they lag the voice.
- **Never split a year or a number+unit across two cues.**

## 10. Sources

- Kurzgesagt-style visual language (shading recipe, palette logic, colour script):
  <https://github.com/tugrulz/kurzgesagt-style> → `references/visual-language.md` (path inside that upstream repo, not in this skill)
- Motion principles, "escape the default look", springs and holds: <https://motionwritten.com/learn/docs/principles/>
- Depth through layered compositions (parallax by scaling duplicate plates):
  <https://trydemotion.com/blog/improve-motiongraphics-techniques>
- Texture and grain that survives compression:
  <https://mediascaleup.com/post/texture-and-grain-in-animation-what-actually-works-motion>
- Cinematic lighting fundamentals — depth, texture, motivation:
  <https://photography.tutsplus.com/articles/create-cinematic-lighting-in-after-effects--cms-93524>
- Typography decisions for motion (size contrast, negative space):
  <https://schoolofmotion.com/blog/tiny-typography-decisions-motion-graphics>
- The banned look (blue-purple gradient ground, neon glow) is defined in this skill's `palette.md`.


---

## 11. Get a second model to review the frames

Numbers and checkers will not tell you the frame looks amateur — another vision model will, if you ask
it properly. This works and it is cheap:

1. **Export six to eight stills** from the *delivered* MP4 (`ffmpeg -ss <t> -frames:v 1`) — not from the
   working tree — into one folder.
2. **Put the generator next to them** (`build2.py` or whichever file emits the page). A reviewer that can
   read the code can name the exact line that produced a bug.
3. **Write a brief** stating the format, the beats, the visual system as implemented, and demand ranked,
   numbered fixes ("sizes in px at 1080 wide, positions, colours, easing, timings"). Ask for composition,
   typography, colour, motion language, and what to cut.
4. **State "read only, do not modify files"** so the review cannot half-apply itself.

```sh
agy models                                              # note the exact id, e.g. gemini-4-hydrogen-high
agy --print "<the brief, plus: read only, do not modify files>" \
    --model gemini-4-hydrogen-high --add-dir "C:/project/review"
```

- `--print` is the one-shot form; `--add-dir` puts the stills **and the generator** in the workspace, so
  the reviewer can quote the line that produced a bug.
- **`--model` and `--effort` conflict** — the model ids already encode effort (`…-high`, `…-xhigh`), and
  passing both is rejected outright. Choose the model id only.
- Do not add `--dangerously-skip-permissions` for a review; the brief says read-only and the CLI can read
  without it.
- Ask for the critique in one response, ranked, with numbers. An unranked list of impressions is not
  actionable and will send you polishing the wrong layer.
- **Run a slow reviewer in the background.** A frontier model given ten images plus the generator can
  outlast a foreground tool call; launch it writing to a file (`… > review.md 2>&1`), then read the file
  when it exits, instead of losing the whole answer at the timeout.
- **Put the automated report and the timeline in the folder too** (`qa.txt`, `timeline.json`). The
  reviewer then reasons about holds, cut density and cue windows instead of guessing from stills.
- **Two rounds, two questions.** Round one is a look-only craft critique. Round two hands it the single
  question you actually care about (for example how a year should read in a caption) — and it surfaces a
  completely different bug class: round two on one film caught a black strobe between every beat and an
  HLS colour-mixing bug that round one had walked straight past.
- **Filter its advice through the render budget.** "Add a continuous slow push on the plate" is correct as
  design and fatal in this pipeline (see `SKILL.md` render traps). State that constraint inside the brief
  so the fixes that come back are implementable.

A second reviewer that runs a different stack is worth the wait — same brief, same folder, different
conclusions where it matters:

```sh
codex exec -m gpt-6.2-sol -c model_reasoning_effort="medium" \
  -i frame_1.png -i frame_2.png -i frame_8.png < prompt.txt > codex_review.md 2>&1
```

- `codex exec` attaches images explicitly with `-i` (one flag per file); it does not see a folder the way
  `agy --add-dir` does. Reasoning effort is a config key (`-c model_reasoning_effort="medium"`), **not** a
  model-id suffix, so it composes cleanly with `-m`.
- **`-i` is variadic — put the brief on stdin, not after the images.** A prompt passed as an argument
  following the last `-i` is consumed as another filename and the run dies with `No prompt provided via
  stdin`, after burning the model's time on nothing. Redirect the brief (`< prompt.txt`).
- **If a CLI answers with an auth error, stop.** `codex` in particular reports `Your access token could not
  be refreshed because your refresh token was already used` — the fix is the user running `codex login`
  themselves. Never paste a key into a command line to work around it, and never write up a review the tool
  never produced.
- Running two reviewers on the same brief is worth the wait when the subject is subjective: their overlap
  is the finding you can act on, and their disagreement is a judgement call, not a fact.

What that found on one film that had already passed every gate: a blind `scale(1.3)` cropping artwork and
pushing floors under the caption band · a caption scrim ending in a hard razor cut 240 px above the bottom
edge · labels 40–80 px off centre because an inline `translateX(-50%)` fought a GSAP `y` tween · a hero
label at 1.15:1 contrast · `ramp()`'s hue shift turning dark screens mint and navy panels purple · a
one-card `slab()` macro making a CRT, a door and a telex look like the same UI component · `back.out`
making falling pieces bounce through solid blocks · SVG `pop`/`scale` transforms painting from `(0,0)`
without `transformOrigin: "50% 50%"` · twelve *tetrominoes* drawn on the beat that says *pentominoes*.
None of that is caught by `om check`, `om qa` or a stills glance; all of it is obvious to a model shown
the frames and the generator.

## 12. Compositing a cut-out on a studio field: the defects a frame review finds

A real product cut-out (a turntable sprite, a manufacturer photograph) on a dark studio field is the strongest look
this pipeline can produce, and the way it fails is different from flat vector art. Every item below was found by
looking at sixteen finished stills at full size, and every one of them is invisible to `check`, `qa` and the
freeze/loudness gates.

| defect | what it looks like | do this instead |
|---|---|---|
| **outline traced as a rim light** | scribbles along every edge plus stray internal lines through the bodywork — an edge-detect filter, not light | derive the rim from the **alpha silhouette** (dilate, subtract, keep the light-facing side) with one light direction. Never stroke the object's outline |
| **a reflection built by stretching or duplicating the subject** | a large ghost smear, or duplicated mirrors/wheels offset below the object — reads as a corrupt file | a reflection is a **mirrored, low-opacity, softly blurred** copy with a defined floor line, or there is no reflection. Never a vertical stretch, never a second offset copy |
| **leftover construction guides** | a huge thin circle, a stray rule, an arc or a curve belonging to nothing | delete every geometric element that carries no meaning; a guide that survived into the render is the loudest "unfinished" tell |
| **fabricated props** | a licence plate, badge, fake UI, a number that exists nowhere | never. An invented plate is fabricated content and rejects the whole film regardless of everything else being right |
| **subject too small in the showcase shot** | the whole object at ~25 % of frame width floating in black | the shot that shows the object shows it **large**; recompose the layout rather than scaling it down. An empty field is not negative space |
| **two formats for one number** | `1.103` in a callout, `1,103` in the headline | one format film-wide: thousands with a comma, decimals with a point. Grep the rendered text for both patterns |
| **two spellings for one brand** | `ÖHLINS` on one card, `Ohlins` in a footer | one spelling across all shots, footers and small type included |
| **a derived figure the source does not state** | "4.5 kg lighter" when the manufacturer's table says 187 vs 191 = **4 kg** | subtract from the sourced table, never from memory, and print that result — or print nothing |
| **flat rectangles as light** | two grey bars behind the object meant to read as studio lights | light needs falloff and bloom: a gradient with a soft edge, or leave it out |

**Audit every still before you assemble.** Sixteen shots cost sixteen stills; a defect fixed before assembly is one
shot re-rendered, and the same defect after assembly is a film re-rendered. The order that works:

1. Render **all** shots as stills at full delivery resolution.
2. Sheet them four to an image and read **each** shot with vision, asking per shot: smeared or ghosted artifacts,
   stray lines or guides, muddy areas, unreadable or colliding type, dead space, invented content, and *does the
   picture show what its own title claims*.
3. Write the defects as a **numbered list per shot, each with what to do instead** — not "improve shot 03" but
   "delete the stretched ghost under the bike; a floor reflection must be mirrored and soft".
4. Hand that list back as the fix pass, restricted to re-rendering the affected shots.
5. Demand a **closure table** in the proof document: shot, what was wrong, what changed, and an explicit note on
   anything deliberately left unfixed.

A title/picture mismatch belongs on that list too: a card labelled `EXHAUST SYSTEM` whose headline states a rev
limiter is a defect even though each element is individually correct.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../SKILL.md) · [Art library index](art-motion/INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
