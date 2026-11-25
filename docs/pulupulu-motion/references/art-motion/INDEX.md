# Art & style extension

This directory is the art-direction half of **pulupulu-motion**. It comes from the upstream skill
[`pulupulu-motion`](https://github.com/Alucard0x1/pulupulu-motion) v1.3.1 (MIT, author Alucard0x1), rebranded and
maintained here as the reference library for anything that is **art, illustration, style or cinematic camera
language** — the things a GSAP/CSS explainer does not cover. Every document in this directory is in English.

- Documents live here and in two subfolders: `style-recipes/` (named art styles) and `animation-grammar/` (explainer grammars). The numbers and rules in them are the source of truth.
- Executable gates copied alongside: `scripts/art-motion/` (storyboard linter, clip lint, film & sub-zone gates, QA, delivery gate, and the Playwright render engine).
- Upstream `assets/` (49 MB of showcase stills and style evidence) was **not** copied. Style recipes are code, not images.

---

## 1. Fast routing

| You need | Read |
|---|---|
| A shot list before any code | `storyboard-template.md` → then lint it (`scripts/art-motion/storyboard_lint.py`) |
| How to move the camera (push, pull, whip, cut, slam) | `camera-language.md` |
| A palette for this film | `palette.md` |
| May I draw a character / how detailed | `character-detail.md` |
| Reproduce the craft of a reference film | `01-breakdown.md` |
| Build one perfect frame first | `03-frame-first.md` |
| A named art style (Van Gogh, bauhaus, Ghibli, pixel, ukiyo-e…) | `style-recipes/INDEX.md` → that style's card |
| An explainer grammar (3b1b, keynote, finance chart, kurzgesagt, Vox, whiteboard, storytime, kinetic type, presenter) | `09-animation-grammar.md` §selection table → `animation-grammar/<card>.md` |
| Pure-code painterly drawing with Canvas | `04-pure-code-painting.md` |
| Long-scroll "walk through paintings" film | `11-long-scroll-film.md` |
| Same scene, different medium (and the character re-drawn with it) | `18-medium-layer.md` |
| What actually worked before (positive experience log) | `07-positive-lessons.md` |
| Checking a finished film against hard rules | `scripts/art-motion/{clip_lint,film_gate,subzone_gate,qa,deliver}.py` |

---

## 2. Storyboard, camera, craft

| File | What it is |
|---|---|
| `storyboard-template.md` | The shot-list template: three lock lines (style / palette / character) then one row per shot — subject, action, camera, on-screen text, method. Includes the worked example and the numeric constraints the linter enforces. |
| `camera-language.md` | Camera as punctuation: when a move is a transition and when it is an accent; push/pull/whip/slam/cut, proximity and readability at each shot scale. |
| `03-frame-first.md` | One full-resolution key frame before animation, then the four routes a film can take from that frame. |
| `01-breakdown.md` | How to dissect a reference animation in about an hour: what to measure, in what order, until it is reproducible in code. |
| `02-mechanism.md` | Why a fast art-history piece works — the mechanism behind the pacing. |
| `16-style-demo-95.md` | Protocol for going from "flat illustration inspired by X" to actually reading as X (the 95-point bar). |
| `08-style-author-spec.md` | Style-author spec: rules for whoever writes a `scene` or commissions one. |
| `15-style-transfer.md` | Migrating an art language to a new subject without it becoming a costume. |

## 3. Style recipes — `style-recipes/` (53 cards)

Start at `style-recipes/INDEX.md`. Each card is a working recipe (palette, stroke logic, texture, motion habits, what breaks it):

`01_cave` `02_egypt` `03_greek` `04_roman` `05_gothic` `06_renaissance` `08_impressionism` `09_postimp` `10_nouveau` `11_cubism` `12_bauhaus` `13_pop` `14_8bit` `15_raytrace` `16_2026` `17_ink` `18_klimt` `19_munch` `20_dunhuang` `21_kusama` `22_constructivism` `23_dali` `24_hopper` `25_ghibli` `26_vaporwave` `27_kirby` `28_monet` `29_seurat` `30_matisse` `31_haring` `32_rembrandt` `33_rubberhose` `34_shadowpuppet` `35_shinkai` `36_picasso_blue` `37_rick_morty` `38_giotto` `39_piero` `40_raphael` `41_michelangelo` `42_guardi` `43_lorenzetti` `44_cortona` `45_renoir` `46_pissarro` `47_sisley` `48_gauguin` `49_chagall` `50_ma_yuan` `51_persian_miniature` `52_south_park` `53_pixar` `55_dunhuang`

Underscore-prefixed files in the same folder are working notes, not recipes: rebuild progress, the art-history audio cue sheet, and the transition migration test.

**A style card is a starting point, not a registered scene.** Anything not yet implemented has to be authored and verified (§`15-style-transfer.md`), never assumed to exist.

## 4. Animation grammar — `animation-grammar/` (9 cards)

The selection table lives in `09-animation-grammar.md` (the largest document here — read the selection table first, then only the card it names):

| Card | Grammar |
|---|---|
| `t1_3b1b.md` | 3Blue1Brown-style maths / concept visualisation |
| `t2_keynote_ui.md` | Keynote-launch UI and gradient motion |
| `t3_finance_chart.md` | Finance / data chart animation |
| `y1_kurzgesagt.md` | Flat science-communication (Kurzgesagt) |
| `y2_vox.md` | Collage explainer (Vox) |
| `y3_whiteboard.md` | Hand-drawn whiteboard (RSA Animate) |
| `y4_storytime.md` | Storytime simple-character animation |
| `y5_kinetic_type.md` | Kinetic typography / infographic motion |
| `y6_presenter_explainer.md` | Presenter-led finance explainer |

A single parameterised clip holds **at most 8 seconds**; longer material splits into shots.

## 5. Drawing, characters, medium

| File | What it is |
|---|---|
| `04-pure-code-painting.md` | Painterly drawing with Canvas: how a code-drawn frame stops looking like clip-art. |
| `character-detail.md` | Either draw the character properly or keep the face out of frame — the detail levels, and when to use a pre-rendered frame library instead. |
| `10-characters.md` | Characters: AI generates the frames, code composes and animates them. |
| `18-medium-layer.md` | Medium layer: the same scene in a different medium, character re-rendered with it. |
| `11-long-scroll-film.md` | Long-scroll traversal film (a figure walking through successive paintings). |

## 6. Colour, rhythm, sound

| File | What it is |
|---|---|
| `palette.md` | One palette per film; the named sets and their hexes; the blue-purple default is banned unless asked. |
| `05-rhythm-and-score.md` | Rhythm and scoring: how picture cut points and music marks lock together. |
| `voice-api.md`, `13-voice-cloning.md`, `06-voice-driven-shorts.md`, `12-whole-film-feedback.md`, `voice-model-review.md`, `capabilities.md` | Voice-over pipeline notes (Volcengine/Doubao voice cloning). **Our narration path is DeepSeek TTS + the `tts-intonation` skill** — use these files only for the direction (how voice-over films are structured and reviewed), not for the API calls. |
| `images.md` | Optional image channel: existing assets versus image generation by the current agent. |

## 7. Executable gates — `scripts/art-motion/`

| Script | Gate |
|---|---|
| `storyboard_lint.py` | Lints a shot-list **before** any code. Subject blank / generic / abstract → red; on-screen text over its limit → red; shot length outside 2–6 s → yellow, over 8 s → red; first and last shot text-dominated → red; three shots in a row with the same camera → yellow. Accepts `--script` to check that numbers on screen match numbers spoken. |
| `clip_lint.py` | Lints a clip spec. |
| `film_gate.py` / `subzone_gate.py` | Whole-film and sub-zone gates (motion, dead zones, text overlap). |
| `qa.py` | Per-clip QA stills/metrics. |
| `deliver.py` | Delivery gate: red light = the film is not copied out; green/yellow writes `output/` plus a delivery note. |
| `engine/` | The Playwright render engine (`render.py`, `scripts/art-motion/engine/engine.js`, `clip.js`, `transitions.js`, `eras*.js`) used by the style recipes. |

**Caveats before using the gates**

1. **The linter reads English.** Subject, action, camera, tag and style-lock vocabulary are all matched in English (`title`, `appears`, `Fast push-in`, `bullets`, `Style:`…), and the older native tokens still match as well if an untranslated table is put in front of it. An all-English shot list is checked in full: the abstract-subject test, the weak-verb test and the text-led tests all fire on English wording. Verified — an English row `Title card | appears` comes back red on ①Subject, ②Action and ⑧Ending, so the linter is a real gate in English, not a rubber stamp. Write the table in the template's own language rather than translating cells afterwards.
2. **The engine is a second render path.** `pulupulu render` (the CLI in this skill) is the default for GSAP/CSS films. `scripts/art-motion/engine/render.py` renders style-recipe `scenes` and parameterised clip specs via `uv run --with playwright`. Two paths, two project shapes: do not mix them inside one film.
3. **These gates are advisory outside their own format.** `film_gate`/`subzone_gate` assume the shot-based project layout; for a `pulupulu` project the equivalent checks are `pulupulu check` + `pulupulu qa`. `compatibility.md` records what was verified and against which scope.

---

## 8. `storyboard_lint.py` verdict legend

Run it as `python scripts/art-motion/storyboard_lint.py <shot-list.md> [--script <script.txt>]`. Each shot prints one line beginning `[GREEN]`, `[YELLOW]` or `[RED]`, then one `[LEVEL] tag: what… Fix: …` line per finding, then a table summary and a verdict. Exit code `1` = red (fix the table, do not start coding), `0` = green or yellow only, `2` = file/table not found. Rules by tag:

| Tag | Rule | Level |
|---|---|---|
| ①Subject | **Subject** cell empty, or made only of abstract words (title, bullet, card, background, icon, empty frame…), or an empty picture (black frame, flat colour, gradient backdrop) | red |
| ②Action | **Action** cell empty, or only generic verbs (appears, displays, fades in, holds…) | red |
| ③On-screen text | **On-screen text** over 8 characters (a run of letters or digits counts one) | red |
| ④Opening | **First shot is text-led** — open on a concrete small scene (a hand, an object doing something) instead; also fires yellow when shot 1 already carries 4–6 characters of on-screen text | red · yellow at 4–6 characters |
| ⑤Text share | Text-led shots are more than **30%** of the film | red |
| ⑥Duration | Shot length outside **2–6 s** | 6–8 s or <2 s yellow · >8 s red · more than a fifth of the shots at 6–8 s red |
| ⑦Camera | Three consecutive shots share the same camera (Stop and Lateral truck excluded) | yellow |
| ⑧Ending | **Last shot is text-led** (centred quote card, pure type card) — land back on the character or object instead | red |
| ⑨Numbers | With `--script`: a numeral on screen (percent, year, number + unit) does not appear in the spoken script; a number written as words in the script counts as spoken | red |
| ⑩Tags | Tag column holds more than 3 tags in one shot | yellow |
| ⑪Number card | A text-led shot in the middle that is a bare number card | yellow |
| ⑫Style lock | Style lock missing any of the `Style` / `Palette` / `Character` lines | red |
| ⑬Palette | Palette hex sits in the blue-purple zone (hue 225–300°, saturation ≥0.30) | red (yellow if `Allow blue-purple:` is declared) · more than 6 colours yellow |
| ⑭Character | Character rule broken: the character line says code-drawn / chibi / robot; the subject column names a robot, stick figure, mascot or cartoon person while the character line is not a frame library; `y4` used without a frame library | red · coins or balls with faces yellow |
| ⑮Push-in | Three consecutive push-ins | yellow |
| ⑯Accent | Accent moves (fast push-in, slam in, whip) exceed a third of the shots | yellow |
| Camera | A camera cell left empty; or no camera move anywhere in the table (nothing but Stop and Cut) | yellow |
| Time span | Consecutive shots do not join up (a gap or an overlap) | yellow |
| Method | One parameterised clip spec runs over 8 s total; more than 2 clip grammars in one film; a shot with no method written; no Method column at all | red · yellow for the last two |

The summary line reads `Table: N shots, X s, M text-led`; the verdict is printed as `Verdict: GREEN`, `Verdict: AMBER` or `Verdict: RED`. Amber is the same `[YELLOW]` level, and each amber item needs its reason written into the delivery notes, one by one.

The tool also states what a machine cannot check and you must: one concrete example carrying the whole film, one style throughout, adjacent shots differing in composition, and the first 3 s being a scene rather than a title.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs: narration and voice timing → skill **`tts-intonation`** · merging or translating another
library → skill **`agent-skill-sourcing`** · rights and likeness review before publishing → skill
**`media-content-safety`** · sourcing a reference video → skill **`streaming-mirror-extraction`** ·
3D or footage-based shots → skills **`headless-three-video-render`** and **`cinetic`** ·
type-first films → skill **`kinetic-typography`**.
