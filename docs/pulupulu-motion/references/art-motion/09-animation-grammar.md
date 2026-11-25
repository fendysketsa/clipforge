# 09 · Video Animation Grammar: 8 Ways to Draw YouTube Explainer / Tech / AI / Finance Films

Read this when you are making the "animation segments" of a narrated explainer film. It is the master index for the 8 grammar cards (`references/animation-grammar/`), the selection table, the rules that hold across grammars, the library quick reference, and the clip contract the narration pipeline works against.

All 8 grammars ship a directly renderable demo film (`scripts/art-motion/engine/demos/<grammar>/`, pixel-identical to the experiment originals when imported; after the `TY.charsIn` opacity fix on 2026-10-05 the y1 demo title fades out over 0.55s as originally intended, so those 0.55s of frames differ from the original) and a parameterised clip (`scripts/art-motion/engine/clips/<grammar>.js`, fed one JSON and producing a clip of exact duration).

---

## I. Overview

| Grammar | Fits | One-line core grammar | Typical shot length | Primary easing | Primary transition | Card | Demo |
|---|---|---|---|---|---|---|---|
| **y1 Kurzgesagt flat explainer** | Scale, "what's inside", mechanism systems; a calm, unhurried explainer voice | Draw the abstract concept as one concrete object, put it in a glowing world that scales without limit, and fly the camera between scales; the environment drifts gently, the subject changes on narration cues | Hard-cut shots 7–9s, the visual unit changes every 4.6–6.7s | `MO.k75` = bezier(.75,0,.25,1); for loops `MO.easyEase` | Dive-in `lensReveal`, fill-then-pull-out `matchCut` (logarithmic camera push/pull) | `animation-grammar/y1_kurzgesagt.md` | `--film demos/y1_kurzgesagt` |
| **y2 Vox collage** | Arguments that have real archives, news, screenshots, people; "look at this sentence", "watch this number" | Lay the argument out on a desk of real material; the camera moves across the desk like an investigative reporter's eye, and lines and pen strokes land in stops and starts | Slow gear median 3.3s (one card 3–7s); fast gear 1.4–1.8s | Camera `MO.sineInOut` / long tail `MO.longTail`; elements stepped at 12fps | Hard cut, truck along the red line `same`, push to fill the photo → hard cut `cut` | `animation-grammar/y2_vox.md` | `--film demos/y2_vox` |
| **y3 Whiteboard hand-drawn (RSA)** | Chains of reasoning, steps, "why"; deriving as you speak | Say one sentence, write one sentence; the camera follows the argument across a large whiteboard and pulls back at the end to show the whole map | Median 6.6s held per block | Truck across the board `MO.sineInOut` 1.2–2.4s; long jump 0.8s whip + motion blur | Same board `same` (the camera move is the transition), pull back to close | `animation-grammar/y3_whiteboard.md` | `--film demos/y3_whiteboard` |
| **y4 Story-driven stick character** | First-person experience, failures, punchlines; the audience wants "this person" | The narration is the lead and the picture is its reaction track: poses hard-cut in 0.1s and then hold, and a punchline lands by cutting to a reaction close-up that shuts its mouth on the beat | ASL 2.43s (median 1.87s) | Pose change `MO.expoOut` 0.1s + `MO.settle` squash-and-settle; character at 24fps | Hard cut `cut`, slam `smash`, whip `whip`, jump closer | `animation-grammar/y4_storytime.md` | `--film demos/y4_storytime` |
| **y5 Kinetic type** | Lists, "X stages", quotable lines, number opens, chapter cards | The words are the cast: keywords slam in on the downbeat, the main word is big enough to read at a glance, and the frame only ever has one focus | One shot per bar (about 2s at 120BPM) | `MO.expoOut` entrances, `MO.springHz` slams, `MO.expoIn` exits (faster) | Rush into a colour block `fillZoom`, colour bands `bands`, page push `push` | `animation-grammar/y5_kinetic_type.md` | `--film demos/y5_kinetic_type` |
| **t1 3Blue1Brown** | How one mechanism turns into another step by step: networks, matrices, gradients, probability | On black, only the one thing being discussed; Transform turns the previous concept straight into the next, colour = concept name, almost no cuts | One animation 1–3s + a 1s hold; one concept 8–20s | `MO.smooth` (6t⁵−15t⁴+10t³), used almost exclusively | Transform continuity (no cut), camera fly-through `zoomThrough`, `fadeShift` | `animation-grammar/t1_3b1b.md` | `--film demos/t1_3b1b` |
| **t2 Keynote UI** | Product/feature launches, version updates, tutorial steps, spec announcements | One thing per screen; a product screenshot or the real object is the lead and gets pushed into, and nouns and numbers land when the narration says them; the glow-field ground and glass cards are optional packaging, use them sparingly | Talk screen 5–8s; product fast cuts 1.5–3s | `MO.spring` bounce 0–0.15, `MO.appleOut` | Blur push `blurPush`, card expand `expandRect` | `animation-grammar/t2_keynote_ui.md` | `--film demos/t2_keynote_ui` |
| **t3 Finance chart** | Revenue, share price, market share, turning points; numbers the audience will screenshot and check | Build the axes first, then let the data grow, then annotate exactly one thing; the values are always honest, the animation only decides how they appear | One chart 2.5–6s | `MO.quintOut`; for lines `MO.smooth` | Panel truck `slidePush`, push into a region `zoomThrough` (live + bScale0), hard cut with the layout held still | `animation-grammar/t3_finance_chart.md` | `--film demos/t3_finance_chart` |

Overview stills: `assets/animation-grammar/<grammar>_overview.jpg` (one frame per shot).

Demo commands (run under `scripts/`):

```sh
uv run --with playwright python engine/render.py --film demos/y1_kurzgesagt --out y1.mp4            # render the demo film
uv run scripts/art-motion/qa.py --project scripts/engine --film demos/y1_kurzgesagt --out <dir>               # acceptance (run from the skill root)
# preview: start a local server and open scripts/art-motion/engine/index.html?film=demos/y1_kurzgesagt to scrub the timeline
```

The demo films are all compressed to about 8 seconds, 2.5–3× the density of a real film's rhythm, only so a demo can show every grammar. When you actually use one, slow down to the shot lengths in the table above.

---

## II. How to pick a grammar for a passage of narration

First look at what this passage of narration is doing, then pick the drawing method. A film can switch grammars between segments, but never mixes them inside one segment.

| This passage is… | Pick | Don't pick | Why |
|---|---|---|---|
| Explaining a concept or a mechanism ("how a neural network…") | **t1 3b1b** (needs derivation, has formulas) or **y1 Kurzgesagt** (needs scale, needs charm) | y2 (no real material to paste, it becomes a fake archive) | A mechanism is clearest through transformation and scale |
| News, events, history, with screenshots and direct quotes | **y2 Vox** | y1 (flat cartoon dilutes credibility) | The audience wants to see the source with their own eyes |
| Your own experience, a failure, a punchline | **y4 storytime** | t2 (carries a good-news mood by default) | The laugh lives in the pause of a reaction shot |
| A list, a few points, a few stages, one quotable line | **y5 kinetic type** | t1 (nothing to transform) | The information is structure, not picture |
| Product, tutorial steps, features, specs | **t2 keynote UI** (screenshot full-bleed and pushed into; glass cards optional) | t1 (glass and glow carry no logic, and neither does the reverse) | One thing per screen; nouns and numbers are the leads |
| Numbers, growth, trend, comparison | **t3 finance chart** | t2's big number (only when there is a single number) | It needs axes and units, and it has to survive being checked |
| Deriving as you speak, arguing step by step | **y3 whiteboard** | One full-screen switch | Say one sentence, write one sentence; the final pull-back is the landing |

Two fallbacks:
- Real screenshots to show → t2 (tutorial, clean) or y2 (argument, evidential). Make the screenshot the main picture and as full-bleed as possible; always scale proportionally and never crop key UI.
- Only one number in the passage → no chart; use t2/y5's big-number count, landing on the moment the narration says the value.

---

## III. Rules that hold across grammars

Rules distilled from the 8 cards that still hold when you switch grammar. Each one is followed by its source.

1. **The camera is a function of time only; the scene is redrawn from the camera vector.** Push, truck and fly-through are all the same world canvas redrawn under a different camera, so a 60× zoom is still sharp, and during a transition the previous shot keeps driving its camera by time (`live:true` on `zoomThrough`). (y1 ⑥ "key architecture"; y3 ⑥; t1 ④-2)
2. **Scale with logarithmic interpolation, and carry enough magnification to pass through a circular opening.** `CAM.zlerp` multiplies by the same factor every frame, where linear interpolation starts slow and ends violent; to fly into an opening of radius r the factor must be ≥ the distance from the opening's centre to the farthest screen corner / r (about 1100/r when centred, `CAM.coverZoom`). (y1 ⑧-2; t1 ④-2)
3. **Land the reveal frame on the beat or on the spoken word.** A transition is measured from the start of the new segment, so the frame where the new picture is revealed falls on the bar line: segment start = bar line − reveal point × transition length (`MO.onBeat`). A number settles when the narration says it: count start = the moment the number is spoken − count duration. Whiteboard writing starts about 0.5s after the matching phrase. (y5 ④ "alignment technique"; t2 ⑤; t3 ⑤; y3 ⑤)
4. **Structure first, then data, then annotation.** The axes appear, then the data grows, then the annotation — one thing annotated per shot; 3b1b Writes the question before any demonstration; keynote goes eyebrow → product name → subtitle. (t3 ③; t1 ⑤; t2 ③)
5. **One focus per screen.** Only one thing enters at a time, everything else holds still; main word to secondary line at least 3:1; the background sits one step lower than the lead in saturation, contrast and stroke weight. (y5 ⑧-1; t2 ⑤; y4 ⑧-2)
6. **Entrances slow, exits fast, and hold after the landing.** Entrance 0.3–0.4s, exit about 0.18s; a number holds at least 0.5s after it lands, a punchline holds ≥0.9s, and 3b1b waits about 1s after every animation. (y5 ⑤; t3 ⑧-3; y4 ⑤; t1 ⑤)
7. **Move on events, and let the camera go there and back.** The camera moves only when the audience's eye needs to go somewhere new: transitions use slow push, truck or pull-back (0.6–1.5 seconds, ease in and out, measured off Vox and 3b1b); fast push (0.28 seconds in by 18–32%) and slam (0.17 seconds, 1.55→0.94→1.0) are reserved for reveals, reversals and key numbers; after pushing in you must pull out or truck away, never three push-ins in a row. The same move on every shot is a slide deck, whether it is a constant slow push (the Nobel literature film r2, "it completely feels like playing a PPT") or one quick push per shot (the Nobel economics short, about 48 push-ins in 102 seconds, "too many, and the rhythm is too fast, not smooth at all"). Numbers and big words slam onto objects inside the film's world (screens, battery bars, price tags, blackboards), never onto a standalone solid-colour type card — in blind review those cards read as "a PPT page inserted", the same as a white-background chart insert. The engine has this ready: `CAM.track` (a camera-move table; write no move and you get a slow push), `MO.slam` (element slam), with the duration constants in `MO.PULSE`; the highlight in clips t2, y1 and y2 is a slow push by default, and only `"camera": "snap"` in the spec-level `data` makes it a fast push; there is no built-in constant slow push and no breathing. The environment layer (Kurzgesagt's glints, particles) may keep drifting gently; storytime is completely still in seven frames out of ten, and its life comes from the fast cuts plus the holds. The art-style speedrun is a different matter — there the picture has to stay alive the whole time (see 04). For the move table, each grammar's camera register, and when the count has to be policed, see `camera-language.md`. (y1 ③, ⑧-1; y4 ⑧-1; t2 ③)
8. **Two frame rates: the camera is smooth, the elements step.** In Vox the camera is smooth while paper, highlighter and typing run at 12fps on twos; in storytime the character is 24fps and the camera 60fps. All-smooth looks like a corporate promo, all-stepped judders. (y2 ③, ⑧-1; y4 ③)
9. **Colour = concept, and few accent colours.** One colour carries one concept (W in the formula and the connector line are both blue); past 3–4 semantic colours nobody remembers them; Vox is black, paper white and one red; whiteboard is black plus one orange. (t1 ⑧-3; t3 ⑧-2; y2 ⑧-3; y3 ⑧-3)
10. **Put transitions at the breath and the topic change, never mid-sentence.** Whip cuts land between two sentences, reaction shots sit inside silence; the whiteboard truck lands on a new argument; Vox hard cuts land on punctuation. (y4 ⑤; y3 ⑤; y2 ④)
11. **Review checks logic and what the numbers actually mean, not only whether it looks good.** Caught in practice: "rose 8.7×" where it should have been "rose to 8.7× the original"; a chart that recounted from 0 after expanding to full screen; a segment about hidden layers that drew a connection to the pixels; a multiple that has to be computable from the numbers on screen. (t3 revision table; t2 revision table; t1 ⑥)
12. **Real material is the main picture and stays as it is.** If you have a screenshot, photo, recording or original text, give it full-bleed or near full-bleed and push into the part you are talking about; code only explains, annotates and moves the camera (`MD.cover` for full-bleed + focus + push-in, `MD.print` for a print, `MD.label` for a black torn-edge label; the screenshot card in clip t2 and the photo in y2 are full-bleed or eight or nine tenths of frame by default); scale screenshots proportionally and never crop key UI; change only *how* the data appears, never *what* it is; bars always start at 0, and an axis that does not start at 0 must say so; every shot of fabricated data carries "illustrative data", and real data may never show that badge. (t3 ②, ⑧-1; clip contract)

---

## IV. Library quick reference (`scripts/art-motion/engine/lib/`, already loaded by index.html and clip.html)

| File | Namespace | What's in it |
|---|---|---|
| `motion.js` | `MO` | Camera-move durations `PULSE` (transitions push/glide/pull, accents punch/pan/slam) / `slamK/slam` (slam 1.55→0.94→1.0) / `pulse` (move progress), `seg/at/anim/step` (12fps stepping), manim `smooth/thereAndBack/rushInto/rushFrom/doubleSmooth/wiggle/lagged`, `sineInOut/cubic*/quart/quint/expo*/backOut/elasticOut`, `bezier` and `appleOut/emphasized/k75/easyEase/longTail`, SwiftUI `spring/smoothSpring/snappy/bouncy`, `springHz/settle`, `float`, `invert` (easing reverse lookup), `beat/onBeat` (beat-grid alignment). Canvas sizing `U.setStage/onStage` lives in `util.js` |
| `camera.js` | `CAM` | `apply/with`, `toScreen/toWorld`, `zlerp` (logarithmic scaling), `coverZoom`, `anchor`, `pushTo` (push to a point, moving it smoothly to centre or scaling in place), `at` (keyframes, trucking along a path), **`track` (camera-move table: `push` slow push (default) / `pull` pull back / `glide` find the next thing / `to` go to a given camera / `punch` fast push / `pan` fast pan / `slam` whole-frame slam / `shake` camera shake / `cut` hard cut; the camera is computed from t alone)**, `layer` (parallax), `velocity/motionBlur` (whip blur), `drift` (handheld micro-drift, only for art styles and pure-atmosphere shots) |
| `diagram.js` | `DG` | Point lists `cum/len/pointAt/drawPartial` (stroke by stroke) / `xform/arcPts/ellipsePts/hand` (hand-drawn jitter) / `revealMask/zigzag` (Reveal wipe), Transform `rectPts/circlePts/morph/shape`, colour `mix/mixA/rgba`, the 3b1b palette `MANIM` (already saturated ×1.5) / `saturate`, `math/write` (manim Write, outline first then fill), `neuron/edgeEnds/edge/flash`, `indicate/circumscribe/brace`, whiteboard `board` (stroke timeline + travel between strokes), `pen` (marker) |
| `typo.js` | `TY` | `text/width/font`, `wrap/fit` (line breaking; `fit` shrinks the type until it really fits: line count ≤ maxLines with every line measured, and no box overflow even for one long English word; `soft:true` returns `ok:false` when it will not fit so you can change the approach, `balance:true` evens several lines to equal length), `charsIn` (character-by-character rise), `rise` (mask rise), `pop`, `blurIn` (blur in), `typed/typedCount` (type-on), `marker/underline`, `slam` (main-word slam), `keyword/keywordMarker` (keyword emphasis), `fmt/count/tabular` (number roll and tabular figures) |
| `chart.js` | `CH` | `lin/ticks`, `grid/xLabels` (axes first), `bars` (grow from 0 + synchronised count + dim-to-grey highlight), `line/yAt`, `candles`, `callout` (point → leader → text), `tag/demoBadge/frame` (Economist layout) |
| `ui.js` | `UI` | `mesh` (glow-field ground), `grainTex`, `backdrop`, `shadow`, `glass` (frosted card), `sheen` (light sweep), `persp` (pseudo-3D), `icon`, `rr/rrPath/scratch` |
| `collage.js` | `CL` | `paperTile/fillPaper` (paper grain), `tornEdge/tornRect` (torn edges), `halftone/photo` (halftone photo), `placed/shadowed/slideIn` (slide in tilted, settle flat), `tape/pin`, `stringPts/string` (red string), `highlight` (rough highlighter), `stickerEdge` (cut-paper white edge) |
| `media.js` | `MD` | Real material as the subject: `cover` (full-bleed, with focus `fx/fy`, push-in `z`, crop, and `fit:'contain'` to keep the whole image uncropped), `toScreen` (points/boxes on the media → screen coordinates), `focusFor/zoomFor` (how much magnification a given region needs), `print` (print / Polaroid: white border, aged paper, drop shadow, tape), `label` (black torn-edge label, 12fps typing), `frameAt` (pull a frame from a sequence), `size`. A missing asset always errors — it never draws a blank frame |
| `toon.js` | `TOON` | `flat` (two-tone faceting), `glow/vgrad/circle/ellipse`, `bean` (the bean character, only for demo films and white-model previz, never in the final film; clip y4 no longer calls it) plus `LOOKS/look`, `POSES`, `poseAt` (pose-to-pose + settle), `blinkAt`, `alive`, `env/mouth` (lip-sync driven by the envelope), `sweat/mark` |

Transitions live at the end of `transitions.js`, in the "YouTube explainer grammar transitions" section: `same / lensReveal / matchCut / whip / smash / fillZoom / bands / push / zoomThrough / blurPush / expandRect / slidePush / fadeShift`, each with a one-line description and its parameters. Hard cuts use the existing `cut`.

Small engine-side changes: a whole vertical film with `render.py --film <name> --width 1080 --height 1920` (or `window.FILM_SIZE = [1080, 1920]` in eras.js) — the engine, transitions, camera and every library compute against the current canvas, though the 35 art-style scenes have still only been drawn landscape; a segment's `clip` (video frame sequence) fills proportionally by default, and `clipDraw(c, frame, lt, t)` places it yourself (push-in, focus, print), with a missing frame or image erroring out and refusing to render; a segment may write `dur` (seconds) instead of `eighths`; `window.BPM` changes the tempo; an explainer writes `window.PUNCH = 0` to turn off beat impacts (or `punch` on a single transition); `window.SCENE_LIBS / SCENE_DIR` let a film keep its code in its own directory (that is how demos are organised).

**Old experiment names → current names** (for reading the archived experiment code): `YT.camAt→CAM.at`, `YT.camForAnchor→CAM.anchor`, `YT.apply/camera→CAM.apply/with` (camera fields `zoom/rot` became `z/r`), `YT.ease.*→MO.*`, `YT.spring(t,f,d)→MO.springHz`, `YT.textIn→TY.charsIn`, `YT.type→TY.typed`, `YT.partial→DG.drawPartial`, `YT.at→DG.pointAt`, `YT.circlePts→DG.ellipsePts`, `YT.paperTile/halftone/tornEdge→CL.*`, `YT.bean/POSES/mouth→TOON.*`, `MN.*→DG.*` (`lerpPts→morph`, `C→MANIM`, `FONT_RM→FONT.rm`), `GL.*→UI.*`, `MO.textIn→TY.blurIn`, `MO.count/fmt/tabular→TY.*`, `easeOutQuint/easeOutExpo→quintOut/expoOut`, transitions `k_lens→lensReveal`, `k_fill→matchCut`, `hardcut→cut`, and y5's `zoomThrough→fillZoom` (it collided with 3b1b's camera fly-through).

Fonts: Chinese sans is uniformly `PuHui-Medium/Bold/Heavy/Black` (the open-source build is actually Source Han Sans, Noto Sans SC 500/700/800/900, keeping the original family names; see `scripts/art-motion/engine/lib/fonts.js`); whiteboard uses `LXGWWenKai-500`; both are subsets covering all 6763 hanzi of GB2312, so a new subject usually needs no additional glyphs. Formulas `CMU-rm/it`, keynote `Inter`, finance figures `RobotoCondensed`. Source Han Sans/Serif `NotoSansSC/NotoSerifSC` contain only the characters the three demo films use — do not use them for new content.

---

## V. Clip contract (the "animation segment" for a narration pipeline)

A narrated-video pipeline (whichever one you use) calls these 8 grammars at the right passages to make animation segments, with the pipeline acting as director: it chooses the grammar and computes cues from word-level timestamps in the narration. This section is the agreement between the two sides.

### Entry point

**Wrap a script around these in the narration pipeline; don't type them by hand**: draft sets the length from the final-cut timeline and emits the word table and a spec draft → render parses the words, calls this section's render.py, counts frames, drops the result into the edit project and freezes it → verify checks synchronisation frame by frame against the chapters. The author's own pipeline is wired exactly this way (that part is not open-sourced with this repository). Below is the engine's own interface.

```sh
cd <skill>/scripts
uv run --with playwright python engine/render.py --spec clip.json --out clip.mp4            # silent H.264 yuv420p
uv run --with playwright python engine/render.py --spec clip.json --alpha --out clip.mov    # ProRes 4444 with alpha (no background drawn, for pipeline compositing)
uv run --with playwright python engine/render.py --spec clip.json --stills 0.5,2,4 --out stills/   # extract frames to check
# preview: local server, open scripts/art-motion/engine/clip.html?spec=examples/t3_finance_chart.json and scrub the timeline
```

- Duration is exactly `duration`: frame count = round(duration × fps), and frame i is at i / fps. H.264 gets one keyframe per second (GOP = fps), so the pipeline's renderer can seek per second without freezing frames.
- **A single clip should carry at most 8 seconds.** When `duration` passes 8 seconds render.py prints a prominent warning at the start and at the end, and does not error (long clips are legitimate inside a narration pipeline). A clip that carries on too long reads as one PPT page: one layout to the end, bullets piling up longer and longer, the background dead from first frame to last. Split a film into many shots, one spec per shot (or one `scenes` block), changing composition between shots but not the look (same theme, at most 2 grammars), then join them (SKILL.md track sheet, steps 3–4; `references/art-motion/storyboard-template.md`). Some sample specs run 8.5–10 seconds — that is a demonstration of how to write one segment, not the length of a film.
- **One palette for the whole film: `theme`.** Every spec in a film writes the same `"theme"`: a palette name `paper`, `poster`, `ink`, `navy`, `bauhaus`, `snow`, `wood`, `chalk` (values in `references/art-motion/palette.md`), or an object `{"name": "wood", "accent": "#B8452A"}` overriding one or two keys, or a full 6-key object `{bg, surface, ink, sub, accent, accent2}`. A misspelled name, an object missing keys (with no `name`), or a colour that is not #hex → startup fails. A grammar given a theme does not paint large gradient grounds or neon glow, and every secondary colour derives from those 6. With no theme each grammar uses its own default (y1 defaults to flat dark ink, no longer a deep-purple starfield). t3 additionally accepts the old `"light"` and `"dark"` and its own theme object; `"paper"` now means the paper palette.
- Width, height and fps are read from the spec, default 1920×1080@30; for vertical write `width: 1080, height: 1920` (or override the spec on the command line with `--width 1080 --height 1920`). Every grammar has a vertical layout.
- Asset paths in a spec are relative to the spec file (absolute paths also work); render.py only serves the files the spec names. It accepts these fields: `cues[].image`, `cues[].frames` (video frame sequence: a directory or an array of paths), `data.image`, `data.character` (y4 frame-library directory). For how paths resolve see `engine/spec_assets.py`.
- Measure the segment: `uv run qa.py --spec <clip.json>` (run from `scripts/`; treats the whole clip as one segment and measures determinism, motion, still-frame pairs, isolated pops and cost, scaled for vertical; a monotonic, smooth push, truck or slam under 2 seconds counts as a camera event, not a pop).
- Delivery: `uv run deliver.py clip.mp4 --spec <clip.json> --out output/`. It first passes the `film_gate.py` gate (fast-motion frame share < 0.035 is a red light; a run of blank picture lasting 0.3 seconds or more in the middle is a red light and blocks even the shortest clip; no copy, non-zero exit), and only then copies the file and writes `delivery-note.md`, whose facts section the script generates. The gate was calibrated on 1–2 minute films and the numbers are noisy on clips of 10 seconds or less; if a clip is going into a film, run deliver.py on the film.
- A page error (broken grammar file, missing image or video frame) → non-zero exit, no clip. `qa.py --spec` and render.py share one asset resolver (`engine/spec_assets.py`), which understands both `frames` and the character frame library. A hanzi in the spec that the font subset lacks only warns (it falls back to a system font, which will look different on another machine); the common characters are all in the subset.

### spec

```json
{
  "grammar": "t3_finance_chart",          // 1 of 8: t1_3b1b | t2_keynote_ui | t3_finance_chart | y1_kurzgesagt | y2_vox | y3_whiteboard | y4_storytime | y5_kinetic_type
  "duration": 7, "fps": 30, "width": 1920, "height": 1080,
  "safe": { "top": 0, "bottom": 520 },     // optional: edges to clear (px), see below
  "alpha": false,                          // optional: true = no background drawn (render.py --alpha sets it automatically)
  "theme": "wood",                         // every spec in a film writes the same one: palette name or object, see "one palette for the whole film" above
  "data": { ... },                        // grammar-level parameters; see each section's "data" line for the fields a grammar accepts. Unknown fields are ignored
  "cues": [ { "at": 1.2, "kind": "bar", "text": "...", "sub": "...", "data": { ... }, "image": "screenshot.png", "dur": 1.0 } ]
}
```

**Common cue fields** (which each grammar accepts is covered in the sections below):

| Field | Meaning |
|---|---|
| `at` | Seconds, required. The "reveal frame": the element is first visible at t = at (internally the animation starts one frame before at). Exception: for `number`, at is the moment the number **settles**. Cues need not be sorted by time, clip.js sorts them; a cue whose at exceeds duration warns and is dropped (it would never be seen and takes no layout space). |
| `kind` | Required. **A kind the grammar does not accept does not error and draws nothing** — write against the table below. |
| `text` | Main text: title, point, label, the verbatim speech bubble, the big words in an insert shot. |
| `sub` | Secondary text: the t2 card caption, y5's secondary line, the short line actually shown in a y4 bubble, the line they type in a y4 insert shot. |
| `image` | Image path, relative to the spec file (absolute paths, `data:` and `http(s):` also work). Missing file → refuses to render. |
| `frames` / `fps` / `loop` | Video frame sequence (t2's screenshot card and y2's photo accept it): a directory (png/jpg/webp, sorted by filename) or an array of paths; plays from at at `fps` (default 30), holds on the last frame when done, `loop: true` loops. The layout is set from the first frame. Missing frames → refuses to render. |
| `data` | This cue's own parameters (`index`, `rect`, `icon`, …), see each section. |
| `dur` | Only a few kinds read it: t1's title/point/equation/line, t3's bar/line/candle, y1's enter, y4's react/insert. Other kinds ignore it. |

**`safe`**: `{top, bottom, left, right, fill?}` (px, default 0). clip.js passes it to the grammar along with the content box left after clearing, `ctx.box = {x, y, w, h}`; `fill` is an optional colour used to paint the cleared edges after the render (in a vertical film it makes a chart read as a card in the same position and on the same ground as the neighbouring contain screenshot; it is not painted under `--alpha`). **All 8 grammars already honour `top` / `bottom`** (each grammar object sets `safe: true`, and content is laid out only between top..H−bottom: t3's axes and source line, y2's camera zoom and frame centre, the layouts of t1/t2/y1/y3/y5, y4's bubbles and insert big words); **`left` / `right` are not laid out against by any grammar yet** — writing them only gets those edges painted by `fill`, while content still runs to the edge. On a vertical 1080×1920 narrated film the subtitle band sits around 1400–1520, so take `bottom` 490–570; landscape normally takes `bottom` 160–220. To wire safe into a new grammar, follow t3: add `safe.top` to the layout's vertical datum and subtract `safe.bottom` from the bottom elements, or lay out against `ctx.box` directly, then write `safe: true` in the grammar object (if it is missing while the spec gives safe, clip.js will console.warn).

**What `number` (big number) means** — only t2, t3 and y5 accept it; the other 5 draw nothing if you write one:

| Field | Rule |
|---|---|
| Value | `data.value` (a number, may be negative; omitted means 0). Rolls from 0 to value (expoOut, fast then slow); negatives use a true minus sign "−"; the integer part gets thousands separators automatically. |
| Format | `data.prefix` (e.g. `"¥"`), `data.suffix` (e.g. `"%"`, `" ×"`; write your own space), `data.decimals` (default **0**; t3's `spec.data.decimals` only affects bar labels and **number does not inherit it** — write decimals again on the cue if you want them). |
| Caption | `text`, `sub` or `data.text` all work; clip.js normalises all three. |
| Small label | `data.label`: above the number in t2, top-left of the page in y5; not drawn in t3. |
| Timing | `at` = the moment the number settles. t2 and t3 start rolling at at−0.9s; y5 changes page and starts rolling at at−0.7s. So a number's at must be at least 0.9 (0.7 for y5), or the roll is already well past halfway on frame 0. |
| Position | t2: its own screen, with the previous screen starting to exit at at−0.9s, never overlaid on a card; t3: a reserved strip above the plot area, right-aligned, with the caption to the left of the number; y5: its own page. |

### Cues each grammar accepts

In each section below the first line gives the spec-level `data`; the table gives the cues. The "minimal spec" is the least markup that renders a presentable segment — copy the structure and swap the content for your subject; the first cue is always a picture event, never a title.

#### t1_3b1b (3b1b / manim explanation: formulas, curves, points)

spec-level data: none.

| kind | Fields | Notes | Example |
|---|---|---|---|
| `title` | `text`, `data.color`, `dur` | Written from at; a further title moves the old one up and fades it out; if too long it shrinks the type first, then breaks to two lines. Never used as an opener — frame 0 shows the object first | `{"at":4,"kind":"title","text":"attention is a weighted average"}` |
| `equation` | `data.tokens` or `text`, `dur` (1.2s for the first, 1.5s after) | token: `{s, it?, col?, gap?, sub?, sup?, size?}`, where `col` takes a manim colour name (`BLUE_C` `YELLOW` `GREEN_C` `TEAL_C` `RED_C`…) or #hex. Given only text it splits automatically: single letters italic, runs of letters (softmax) upright. From the second one on it Transforms in from the previous | `{"at":1,"kind":"equation","text":"softmax(QK)V"}` |
| `point` | `text`, `dur` | One sentence to a line, Written; older lines grey out as new ones arrive. When it will not fit, the curve gives way first (vertical 50%→30%), then the type shrinks (≥0.6×), and if that is still not enough the whole block scrolls up as a new point writes and the oldest fades out (with a warning) | `{"at":3,"kind":"point","text":"compute similarity first"}` |
| `line` | `data.values` (evenly spaced y) or `data.points` (`[[x,y],…]`), `text` = the curve label, `data.color`, `dur` | The axes are Created before the curve is drawn; from the second line on it morphs from the previous one. With a line, landscape is text left / chart right, vertical is chart above / text below | `{"at":2,"kind":"line","text":"loss","data":{"values":[9,5,3,2,1.5]}}` |
| `highlight` | `data.index` (which point, from 0, default the latest) or `data.target:"equation"` | Indicate plus a yellow box that stays | `{"at":5,"kind":"highlight","data":{"index":0}}` |

Minimal spec:
```json
{"grammar":"t1_3b1b","duration":6,"cues":[
  {"at":0,"kind":"line","text":"weight of each word","data":{"values":[1,2,7,2,1]}},
  {"at":1.6,"kind":"equation","text":"softmax(QK)V"},
  {"at":3.4,"kind":"point","text":"the more alike, the larger the weight"},
  {"at":4.6,"kind":"highlight","data":{"target":"equation"}}]}
```

#### t2_keynote_ui (keynote UI: feature cards, screenshot cards, big numbers)

spec-level data: `eyebrow` (small type above the title), `title`, `subtitle`, `accent` (accent colour, default `#3d6bff`), `frame` (screenshot-card packaging: default `"full"` for full-bleed; `"glass"` is the old frosted-glass card, optional and to be used sparingly).

| kind | Fields | Notes | Example |
|---|---|---|---|
| `title` | `text`/`sub` override data.title/subtitle | Floats out of blur from at. Never used as an opener — put a screenshot or a number up first | `{"at":5,"kind":"title"}` |
| `card` / `step` / `image` (synonyms) | `text` card title, `sub` caption, `image` screenshot; `data.step` sets the number; an image-less card may add `data.icon` (`wave memory agent clock phone layers chart code check play bolt lock`) and `data.value/prefix/suffix/decimals/label` (a count on the card) | With an image (default `frame:"full"`): one per screen, the screenshot full-bleed (proportional, uncropped; `data.fit:"cover"` crops to fill around `data.focus:[fx,fy]`), padded around with a darkened, blurred copy of the same image; `text`/`sub` are a black torn-edge label bottom-left; it hard-cuts in on the at frame (a 0.17s light slam), and when the previous screen was also a full-bleed screenshot it trucks over at the same magnification for 0.30s. `data.frame:"glass"` uses the old glass card. It also accepts `frames` (screen-recording frames). Without an image: up to 3 consecutive cards side by side on one screen | `{"at":2,"kind":"card","text":"one sentence, one image","sub":"no prompt to write","data":{"icon":"bolt"}}` |
| `highlight` | `data.rect=[x,y,w,h]` (relative to the screenshot, 0..1), `text` optional label, `data.fill` (share of frame the box takes after the push, default 0.42) | Boxes a region of the current screenshot and dims the rest; in full-bleed mode the camera pushes in at the same time (at least 18% closer, at most 2.6×; slow push 0.9s by default, `data.camera:"snap"` at spec level makes it a 0.28s fast push), and the next highlight on the same image moves over (0.7s by default, 0.30s with snap) | `{"at":5,"kind":"highlight","data":{"rect":[0.6,0.2,0.2,0.1]}}` |
| `number` | See the number rules above; `data.over: true` | Its own screen. With `data.over: true` and a full-bleed screenshot on the previous screen: no new screen — the camera pulls back to the whole screenshot, the screenshot dims, and the number slams on top and counts. Use it when the number is about what is in that screenshot; do not cut to the glow ground | `{"at":4,"kind":"number","text":"monthly active users","data":{"value":1.2,"decimals":1,"suffix":" ×100M"}}` |

Minimal spec:
```json
{"grammar":"t2_keynote_ui","duration":6,"cues":[
  {"at":0.9,"kind":"number","text":"monthly active users","data":{"value":1.2,"decimals":1,"suffix":" ×100M"}},
  {"at":2.4,"kind":"card","text":"voice input","sub":"speak, and it becomes text","data":{"icon":"wave"}},
  {"at":3.6,"kind":"card","text":"long-term memory","sub":"remembers what you said last time","data":{"icon":"memory"}}]}
```
That is the shape without screenshots. With a product screenshot, open on a screenshot card (`{"at":0,"kind":"card","image":"screenshot.png","text":"…"}`, see `examples/t2_keynote_ui.json`; two real screenshots full-bleed + push-in + truck, see `examples/t2_fullbleed_pulse.json`).

#### t3_finance_chart (Economist-style data chart)

spec-level data: `title`, `unit` (the subtitle: metric and unit; when it will not fit it shrinks first, then breaks to two lines), `source` (source line bottom-left; same behaviour, and it clears the bottom-right badge), `badge?` (the bottom-right badge is only drawn if you write one, e.g. "illustrative data"; never write it on real data), `chart: "bar"|"line"|"candle"`, `series: [{label, value, color?}]` or for candles `[{label, o, h, l, c}]`, `decimals` (bar/point labels, default 1), `prefix`, `suffix`, `highlight: {index, text, sub}`, `colors: {main, accent, dim}`, `upDown: "cn"` (red up, green down, the default) `|"us"`, `xAxis: "category"|"time"` (bars name every category by default; lines and candles thin the labels by time), `theme` (may also be written at spec level `theme`): `"light"` (white ground, default) `|"dark"` (dark ground, light type), the eight palette names (`"paper"` now means the paper palette), or `{bg, ink, sub, grid, bar, dim, red…}`; with no theme but `safe.fill` set to the film's ground colour, the chart uses that as its ground, and a dark ground switches to light type automatically.

**Keep the chart shot inside the film's world**: the chart's ground stays in the same colour family as the shots around it (a dark film uses `theme:"dark"`, or writes the film's ground into `safe.fill`); never cut to a white-background report in the middle of a night scene or a dark film. Better still, draw the chart onto an object inside the film's world — `--alpha` gives a transparent clip that you paste onto a screen, a blackboard or a sheet of paper in the film.

| kind | Fields | Notes | Example |
|---|---|---|---|
| `title` | — | The moment the layout (title, subtitle, source) appears. May be omitted: without it the layout appears with the axes at 0 seconds | `{"at":0,"kind":"title"}` |
| `bar` / `line` / `candle` | `dur` (defaults by bar count); a bar chart may write several bar cues, each with `data.index` (a number or an array) = these bars grow at this moment | Axes → data grows. Bars always start at 0; when a line or candle's y-axis does not start at 0 the subtitle automatically adds "y-axis does not start at 0"; a negative bar's value goes below the bar and the annotation moves down with it; category names shrink before they break to two staggered lines, and the annotated bar always keeps its name; tick decimals follow the step size | `{"at":1.2,"kind":"bar"}` |
| `highlight` | `text`/`sub` override data.highlight; `data.index` which bar | The annotation dot pops on the at frame, leader line + text; when a diagonal placement would cover another bar or value it moves directly above this bar, and if there is no room at the top it adds one more tick step automatically | `{"at":4,"kind":"highlight","data":{"index":2},"text":"highest"}` |
| `number` | See the number rules above | A reserved strip above the plot area, never covering the line's leading end | `{"at":5,"kind":"number","text":"latest close","data":{"value":259.97,"prefix":"¥","decimals":2}}` |

Minimal spec:
```json
{"grammar":"t3_finance_chart","duration":6,"data":{"title":"R&D spend at three companies","unit":"2024, RMB 100M","source":"Source: illustrative data","badge":"Illustrative data","chart":"bar",
  "series":[{"label":"A","value":120},{"label":"B","value":86},{"label":"C","value":43}]},"cues":[
  {"at":0.3,"kind":"bar"},{"at":3.5,"kind":"highlight","data":{"index":0},"text":"most"}]}
```

#### y1_kurzgesagt (flat explainer: centre object + satellite nodes + scale traversal)

spec-level data: `center` (the name of the first layer's centre object), `center_style: {color, shape: "circle"|"rounded"|"hex"|"diamond", ring: true}` (omitted, a neutral style is generated from the name: colour and shape determined by the text, same name gives the same style, no orbit ring), `image` (crops an image into the centre object and moves the name into a capsule below), `flow: true` (nodes strung into a chain with signals passing in order and indices, for talking about "first, then"). The environment layer (glints, particles, signal pulses) drifts gently throughout; centre objects, nodes and labels hold once they land, and the camera does not slow-push.

| kind | Fields | Notes | Example |
|---|---|---|---|
| `title` | `text` | The title at the top rises character by character; it fades out over 0.5s starting at the first highlight's or enter's at. Never used as an opener — frame 0 shows a node first | `{"at":1,"kind":"title","text":"what one search goes through"}` |
| `point` | `text`, `data.color` | One satellite node plus label capsule for the current layer. ≤3 sit in the upper semicircle, ≥4 go all the way round. Labels are clamped inside frame for the current shot, and long ones shrink first | `{"at":1.4,"kind":"point","text":"tokenise"}` |
| `highlight` | `data.index` (counts only the current layer's points, from 0, default the latest) | Pushes in to that node (about 30%; slow push 0.9s by default, `data.camera:"snap"` at spec level for a 0.28s fast push), dimming the rest; when already pushed in, the next highlight moves over at the same magnification | `{"at":5,"kind":"highlight","data":{"index":1}}` |
| `enter` | `data.index` (which node to dive into, default the latest), `text` (the new centre's name, default the node name), `data.style` (the new centre object's center_style), `dur` (default 1.6) | Scale traversal: the push starts on the at frame, around at+0.55×dur the screen fills with one colour and cuts to the new layer, and by at+dur the new centre object has finished drawing out; every later point belongs to the new layer (write the first new point's at after at+dur) | `{"at":4,"kind":"enter","data":{"index":0},"text":"tokeniser"}` |

Minimal spec:
```json
{"grammar":"y1_kurzgesagt","duration":6,"data":{"center":"search engine"},"cues":[
  {"at":0.3,"kind":"point","text":"crawl"},{"at":1.1,"kind":"point","text":"index"},
  {"at":2.2,"kind":"enter","data":{"index":1},"text":"inverted index"},
  {"at":4.2,"kind":"point","text":"word → page"}]}
```

#### y2_vox (collage desk: screenshots, clippings, red string, highlighter)

spec-level data: none.

| kind | Fields | Notes | Example |
|---|---|---|---|
| `image` / `clip` (synonyms) | `image` or `frames` (recording frames), `text` = a black torn-edge label pressed into the bottom-left (12fps typing), `data.halftone: true` for greyscale halftone, `data.fit:"cover"` + `data.focus` + `data.aspect` to crop to fill around the focus | Slides onto the desk from at; a print (white border, aged paper, shadow, tape), proportional and uncropped by default. While the camera holds on one, it fills eight or nine tenths of frame. Landscape lays out left→right, vertical top→bottom; the red string is drawn out first, and the camera trucks over 0.30s before at | `{"at":1,"kind":"image","image":"screenshot.png","text":"home page"}` |
| `title` | `text` (empty or whitespace-only warns and is skipped) | A black label bar with white type, typing at 13 characters/second. Good for landing the point at the end, never as an opener | `{"at":5,"kind":"title","text":"there are three threads to this"}` |
| `point` | `text` | An index card with a rule, typed (short gaps speed it up to at most 40 characters/second) | `{"at":4,"kind":"point","text":"published a day before the announcement"}` |
| `highlight` | `data.rect=[x,y,w,h]` (relative to **the current image**, 0..1; relative to the cropped frame under `fit:"cover"`) | Highlighter sweeps over → red circle → camera pushes over (slow push 0.9s by default, `data.camera:"snap"` at spec level for a 0.28s fast push; when the box starts off-screen it pushes first and arrives one frame before at). Eyeballed rects are usually off by 20–30% — check with `--stills` first | `{"at":2.5,"kind":"highlight","data":{"rect":[0.1,0.2,0.3,0.1]}}` |

Minimal spec (y2 needs real material: if you have no screenshot, photo or original text to paste, do not pick y2 — see section II):
```json
{"grammar":"y2_vox","duration":6,"cues":[
  {"at":0,"kind":"image","image":"screenshot.png","text":"site announcement"},
  {"at":1.6,"kind":"highlight","data":{"rect":[0.1,0.2,0.3,0.1]}},
  {"at":4,"kind":"point","text":"two weeks later the site changed its price"}]}
```

#### y3_whiteboard (whiteboard hand-drawn: say one sentence, write one sentence, draw icons, circle key points)

spec-level data: none.

| kind | Fields | Notes | Example |
|---|---|---|---|
| `title` | `text` | Starts at 7.5 characters/second and speeds up automatically to catch the next cue. Never used as an opener — the first stroke draws first | `{"at":4,"kind":"title","text":"why write tests"}` |
| `point` | `text` | Draws a small circle as a bullet, then writes, starting at 16 characters/second | `{"at":1.5,"kind":"point","text":"someone watching while you change code"}` |
| `draw` | `data.icon` (`person cat network doc chat bulb check cross screen stack gear target clock chart`; a misspelling warns and only the caption is written), `text` = the caption under the icon (shrinks first if it will not fit), `data.arrow: false` skips the arrow | Sits alongside the line just written; consecutive draws are joined with orange arrows | `{"at":2.5,"kind":"draw","text":"checked automatically","data":{"icon":"check"}}` |
| `image` | `image` | Zigzag reveal plus a hand-drawn frame, proportional and uncropped | `{"at":4,"kind":"image","image":"sketch.png"}` |
| `highlight` | `data.index` (which one, from 0), `data.target`: `"title"` / `"draw"` / `"image"` (counts points by default), `data.style: "underline"` | Circles in orange or underlines; omit index for the most recently written item | `{"at":5,"kind":"highlight","data":{"index":0,"style":"underline"}}` |

Minimal spec:
```json
{"grammar":"y3_whiteboard","duration":6,"cues":[
  {"at":0,"kind":"draw","text":"checked automatically","data":{"icon":"check"}},
  {"at":1.4,"kind":"point","text":"someone watching while you change code"},
  {"at":3.0,"kind":"draw","text":"safe to refactor","data":{"icon":"gear"}},
  {"at":4.6,"kind":"highlight","data":{"target":"draw","index":0}}]}
```

#### y4_storytime (bean character telling a story: bubbles, reaction close-ups, insert shots)

spec-level data: `character` — **must be your own frame library** (AI-generated frames, see `references/art-motion/10-characters.md`; delivery line in `references/art-motion/character-detail.md`); the code-drawn presets (`neutral`/`bun`/`author`) and the look object are discontinued, and startup fails whether you write one or not. Without image generation, do not use y4 — switch to y2/y5, or use scenes and tell it with hands and objects. To supply frames, write a directory (render.py strips the extension and uses the filename as the pose name: `rest talk point shrug type stiff react back`, with `<pose>_open` as the mouth-open frame), or write `{"frames": {"talk": "me/talk.png", …}}`; frames are transparent PNGs with the feet at the bottom-centre of the image, and you need at least rest or talk. The camera holds and the character does not breathe; change comes from fast cuts, reaction close-ups slamming in, and insert shots. With `window.VO_ENV` it lip-syncs to the narration envelope; without it, it synthesises from the character count. `safe` only moves type (bubbles, insert big words); the character, the desk and the reaction close-up face are graphics and will reach into the subtitle band in vertical — subtitles over the body still read fine, but do not expect them to get out of the way.

| kind | Fields | Notes | Example |
|---|---|---|---|
| `point` / `title` (synonyms) | `text` = the verbatim narration (sets the mouth-move duration, ≈6.5 characters/second), `sub` = the short line actually shown in the bubble (≤12 characters is best; only shown if you write it, otherwise text is used), `data.pose`: `talk` / `point` / `shrug` / `type` | The bubble pops and the mouth starts moving on the at frame | `{"at":0.1,"kind":"point","text":"I asked it to fix a typo for me,","sub":"just one character"}` |
| `highlight` | `data.mark` (default "?") | A "?" or "!" pops out plus a worried shrug | `{"at":4,"kind":"highlight","data":{"mark":"!"}}` |
| `react` | `dur` (measured from at, default until the next cue) | Jumps to a big reaction close-up: dead eyes plus a sweat drop, saying nothing | `{"at":3,"kind":"react"}` |
| `insert` | `sub` = the line they type on the computer (wraps if long, at most 3 lines), `text` = the big words that slam out, `data.hit` (**absolute seconds**, default at+1.3, or at+0.4 when there is no sub), `data.count` + `data.unit` (the top-right counter stops at this number when the words land), `data.app` (window title, default "AI Assistant"), `dur` (measured from at, default until the next cue) | Cuts to a close-up of the computer screen on the desk: typing → the reply scrolls faster and faster like a wall of code → the big words slam out | `{"at":2,"kind":"insert","sub":"fix a typo","text":"changed 40 files","data":{"hit":3.4}}` |

Minimal spec:
```json
{"grammar":"y4_storytime","duration":6,"cues":[
  {"at":0.1,"kind":"insert","sub":"fix a typo","text":"changed 40 files","data":{"hit":1.5}},
  {"at":2.6,"kind":"react"},
  {"at":4.0,"kind":"point","text":"I only asked it to change one character.","sub":"just one character"}]}
```

#### y5_kinetic_type (kinetic type: one cue, one page)

spec-level data: `palette: [[ground, type colour], …]` (cycled per page).

| kind | Fields | Notes | Example |
|---|---|---|---|
| `title` / `point` | `text` the main word (shrinks automatically if long, at most two lines), `sub` the secondary line, `data.label` (small label top-left), `data.key` (the word in the secondary line to colour), `data.num` (giant background index) | The main word slams in on the at frame; page changes are a colour-band wipe (starting 0.3s before at). Two or more points = a list: it draws a progress track plus a giant background index | `{"at":1.8,"kind":"point","text":"Slow","sub":"change only one spot","data":{"label":"01","key":"one spot"}}` |
| `number` | See the number rules above | A page with one big number | `{"at":4,"kind":"number","sub":"share that pass first time","data":{"value":87.5,"decimals":1,"suffix":"%"}}` |
| `highlight` | `data.word` (a word inside the main word; omit to brush the whole main word) | Highlighter plus a small scale bump; when the highlighter is the same colour as the type (yellow type on a deep-blue page) the word under it reverses out to the ground colour. A word that is not in the main word warns and does nothing (for words in the secondary line use `data.key`) | `{"at":3,"kind":"highlight","data":{"word":"Slow"}}` |

Minimal spec:
```json
{"grammar":"y5_kinetic_type","duration":5,"cues":[
  {"at":0.7,"kind":"number","sub":"share that pass first time","data":{"value":87.5,"decimals":1,"suffix":"%"}},
  {"at":2.2,"kind":"point","text":"Slow","sub":"change only one spot","data":{"key":"one spot"}},
  {"at":3.6,"kind":"highlight","data":{"word":"Slow"}}]}
```

### Samples (`scripts/art-motion/engine/clips/`)

```sh
cd <skill>/scripts
uv run --with playwright python engine/render.py --spec scripts/art-motion/engine/clips/t3_finance_chart.json --out t3.mp4   # Nvidia revenue for five fiscal years (real 10-K data): the bars grow in three passes, one per word
uv run --with playwright python engine/render.py --spec scripts/art-motion/engine/clips/t2_keynote_ui.json   --out t2.mp4   # screenshot card opens + a box around the number, vertical screenshot, then one big number
uv run --with playwright python engine/render.py --spec scripts/art-motion/engine/clips/t1_3b1b.json         --out t1.mp4   # gradient descent: the loss curve first, then the formula transforms, then the curve morphs
uv run --with playwright python engine/render.py --spec scripts/art-motion/engine/clips/y2_vox.json          --out y2.mp4   # a screenshot opens and lands on the desk, highlighter + red circle + push-in, closing label lands the point
uv run --with playwright python engine/render.py --spec scripts/art-motion/engine/clips/y3_whiteboard.json   --out y3.mp4   # whiteboard: draw then write, icons alternating with short lines, finally circle the first icon
uv run --with playwright python engine/render.py --spec scripts/art-motion/engine/clips/t2_fullbleed_pulse.json --out t2b.mp4   # two real terminal screenshots full-bleed: push to the timer, truck to the second, pull back to the whole screenshot and slam the number on top to close (number's data.over)
# there is also y1_kurzgesagt (a drop of seawater → dive into a diatom) / y4_storytime (opens on a screen close-up) / y5_kinetic_type (opens with a number slam); add --width 1080 --height 1920 to any of them for vertical; sample assets are in examples/assets/: the three charts are t3's own final frames (numbers settled, no playhead, no paths), the two terminal screenshots are real captures of python3 -m timeit output
# the samples demonstrate how to write a spec: do not carry their subject, composition or assets into a finished film
```

### Notes for the pipeline director

- Do not stuff a segment with cues: by section I's shot lengths, a 3–8 second clip is most comfortable with 2–5 cues; pack them in and the writing is forced to speed up and the camera cannot arrive in time.
- **The three hard rules of writing a spec** (this is where page-flip PPTs mostly come from): the first cue is a picture event (a curve, a screenshot, data growing, a dive-in, an icon, a screen close-up, a number slam), not a title at second 0; text cues (title, point) are no more than half the total, and the same kind never appears 3 times in a row; every on-screen `text` and `sub` stays within 14 characters, and the verbatim narration belongs to the subtitle track (when y4 has a `sub`, `text` only sets the mouth-move duration and never goes on screen, so it is exempt).
- Grammars with type in frame (t1/t3/y3/y5) compete with the pipeline's burned-in subtitles; when compositing, move the subtitles clear or do not burn them for that segment.
- Transparent mode (`--alpha`) only removes the background layer; the elements keep their own shadows, so y2's paper and t2's glass card read on a transparent ground as "a card floating over the picture". Under t3 alpha the type carries a halo in the theme ground colour (default black on white paper = a white halo; `theme:"dark"` gives light type a dark halo), so it still reads over another picture; t1's white type carries a dark halo.
- **A screenshot pasted into vertical must box the half-sentence being spoken.** A screenshot on a vertical desktop is about 900px wide, and 16px body text in a web page needs a 2–2.5× push to be legible; box a full-width run of text (box width close to frame width) and the red circle will not fit, so the camera cannot push in. Split a sentence that spans two lines into two highlights, one per keyword (measured 2026-10-04: split this way, a 2.4× push gives type about 50px high). Eyeballed rects are usually off by 20–30% — render one with `--stills` to check.
- **Stepped animation inside a grammar file must count from at.** A step like "on twos" quantised against the absolute time grid (`MO.step(t, 12)`) reveals an element up to one step early (2 frames early at 30fps). Write `MO.step(t − at, 12)` so the at frame is the first frame. y4's character frames are still taken on the absolute 24fps grid, so a cue can land 1 frame off — check before use.

---

## VI. Regression (when this was imported into the skill, 2026-10-04)

| Target | Result |
|---|---|
| 16 original segments (`eras.js`), 36 all-style samples (`--film gallery`) | 61 frames at the same instants pixel-identical before and after; every qa run reports no error and determinism ✓, motion/pop numbers unchanged, cost back-to-back 21.5 → 22.3 ms/frame (within noise) |
| 8 demo films vs the experiment originals | 16 instants per film (including transition windows) pixel-identical; all 25 qa segments report no error and determinism ✓; motion, pops and cost match the original project (each film's first segment now starts at 0 instead of 8/16s, and the qa sampling window differs, so the first segment's numbers differ slightly) |
| After the 2026-10-05 final-review fixes | 87 qa segments across 8 sample specs + 16 original segments + 36 samples + 8 demo films all deterministic ✓ with no page errors; sample stills changed only as expected (t2 differs by 1 colour step = the determinism fix, y5's deep-blue page keyword moved to orange, y1's title genuinely fades out); an independent final review of 36 specs (landscape samples, vertical, stress, boundary, alpha) found no 🔴 |
| After 2026-10-10, when pulsed camera moves, real-material pieces and whole vertical films entered the engine | 16 original segments, 36 all-style samples, 8 demo films and the long-scroll demo, 18 instants each, pixel-identical before and after in landscape (demo y4 explicitly uses `char: 'author'`); 9 sample specs rendered in both landscape and vertical, qa determinism ✓; the push / bands / iris / comicPanels transitions of the vertical test film compute correctly at 1080×1920 |
| Known pops | y1_s3 (the 42×→1× pull-out mid-shot), y2_s2/s3 (fast pan and push to fill the photo), t1_s3 (flying into the neuron), y5's beat accents — all designed camera moves or beat flashes, present in the originals. Since 2026-10-10 qa records a monotonic push or truck shorter than 0.35 seconds as a camera event: in the demo films t1_s3's 1.51s, y5 k4_agent's 2.2s and t3_s1's 2.1s are now recorded as camera events; the rest are longer than 0.35 seconds (or are single-frame on-twos jumps) and are still recorded as pops |
| 2026-10-10 gate and one-command delivery | qa before and after the change: motion, still-frame pairs, determinism and framing unchanged for the 8 demo films and 9 sample specs; pops dropped only by the ones now recognised as camera events (counted as events: 3 in the demo films; 1 in sample t2_keynote_ui, 3 in y4_storytime, 2 in y5_kinetic_type — all pushes, slams or pose cuts of 0.07–0.34 seconds), while pushes longer than 0.35 seconds and single-frame on-twos jumps are still reported; synthetic film (the same three images, 3 seconds per shot): a constant slow push of 7.5% per shot gives 0.000 fast-motion frames, a red light, while one 0.3-second 30% fast push per shot gives 0.095, a green light; in whole-film mode a single 0.3-second fast push used to record 8 pops and now records 1 camera event, while a one-frame white flash is still recorded as a pop |

---

## VII. Pitfalls

- **(Measured 2026-10-04 wiring into a narration pipeline) In y2, after a push-in the next box sat off-frame and the highlighter started sweeping outside the picture.** The audience saw it 7 frames late. Fixed: when the box's start point is not inside the current shot, the camera moves there first and arrives one frame before at, then reveals; the push magnification is also constrained by "keep the red circle in frame" (the circle is 1.24× the box width and 1.5× its height).
- **(2026-10-04 clip review) t3's ticks lied, categories lost their names, and the big number sat on the line's leading end.** `fmtTick` only kept decimals when the step was <1, so with a step of 2.5 the ticks −2.5/2.5/7.5 were printed as −3/3/8; 10 category bars in vertical were thinned by `ceil(n/6)`, and the annotated "first" happened to lose its name; number was pinned to the plot area's top right, which is exactly where a rising line's end sits. All three are fixed (see the t3 entry in section V).
- **(Same review) In y2 the camera left before the type card had finished typing.** It only looked at the next item's at−0.95. It now waits for "finished typing + 0.5s hold" before leaving (at the latest at−0.4), and when the gap is short it raises typing from 13 to at most 40 characters/second.
- **(Same review) The full-width space in PuHui Medium/Bold has zero width.** The source font (Alibaba PuHuiTi 3.0, the 65/85 weights) already gives it 0, so "RMB" and "y-axis does not start at 0" ran together into one string. `font_subset.py` now sets it to the width of an ideographic character when it builds a subset, and existing files were fixed with `--fix-widths`.
- **(Same review) t3's vertical annotation landed exactly in the burned-in subtitle band.** The vertical chart's baseline is at y≈1660 and the annotation at y≈1460, overlapping the subtitles of a 1080×1920 film (1400–1520). `safe` was added.

- **(2026-10-05 clip final review) Everything written to the samples was right, and it fell out of frame as soon as it met vertical and real lengths.** An independent final review of 33 specs (landscape samples, self-written vertical, stress, boundary, alpha) found 12 🔴: empty text in y2 hung the renderer in an infinite loop; on y5's deep-blue page the highlighter was the same colour as the yellow type and painted the main word out, and long numbers went out of frame in vertical; 7 of t1's points in vertical pushed into the subtitle band; in t3 vertical the subtitle and source line went out of frame, the annotation covered a neighbouring bar, and on a transparent ground the type was invisible over a dark background; y1's labels were clipped in vertical; y3's captions went out of frame; y4's typing overflowed the bubble; t2 differed by 1 colour step between two renders of the same moment (a reused buffer kept the previous frame). Self-testing also turned up `TY.charsIn` not multiplying the outer opacity (y1's promised title fade was a one-frame disappearance), t3's lowest negative bar value covering the category name, and `TY.fit` counting lines without measuring line width. The pattern: **anywhere something "does not fit" there has to be a way out — shrink, then break, then give way, and only then warn**; a layout tuned only at sample length breaks the moment it meets real narration.

- **The two experiment sets each wrote a `window.YT` with a completely different API.** On merge they were split by function into 8 namespaces, and same-name-different-meaning items were renamed: G2's `zoomThrough` (rush into a colour block) → `fillZoom`, G2's `spring(t, freq, decay)` → `MO.springHz`, G1's `circlePts` (an open ellipse) → `DG.ellipsePts`.
- **woff2 fonts fail the glyph check.** The engine's `U.loadCmaps` only decodes WOFF1/TTF, so G3's woff2 threw console.error the moment it loaded and qa failed the build. Everything was converted to woff on import.
- **A background driven by whole-film time changes phase depending on where the film sits on the timeline.** The keynote demo's glow field was originally scheduled at 8–16s, and its composition changed completely once it became a standalone film; `T2.PHASE = 8` preserves the approved frame. In parameterised clips the glow field reads clip time only and is unaffected.
- **Ticks must enclose all the data.** `CH.ticks` only gave whole ticks inside the range, so with a maximum of 130 the top tick could be 100 and the bar burst out of the axes; the clip now adds one tick step above and below.
- **System fonts are not in the skill.** The serif in the Vox demo (Songti SC) and the code font in the kinetic-type demo (Menlo) are macOS system fonts and look different on another machine; the parameterised clips have all been switched to fonts the skill ships.


## The whole narrated film and the ninth grammar

The 8 above all ship parameterised clips. There is also [presenter-style finance explainer](animation-grammar/y6_presenter_explainer.md), which ships the grammar and reference code for a whole film but no parameterised clip yet. For full narrated production, frame-framing checks and lessons flowing back, see [the whole narrated film and lessons flowing back](12-whole-film-feedback.md).

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
