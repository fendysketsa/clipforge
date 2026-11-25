# y5 · Kinetic Typography / Infographic Motion (kinetic typography)

> One-line grammar: **The words are the actors — every keyword slams in on an accent, the key word is big enough to read in one glance, the rest rise out of a "slot" to land with the ear; there is only ever one focal point, the camera and the ground texture never stop moving, and the type does not move once it has landed.**

Lineage: Saul Bass's *North by Northwest* (1959) title sequence is widely credited as the first large-scale use of kinetic type in a feature; after 2008 the lyric/quote kinetic type of YouTube (the After Effects generation) made it the standard grammar for explainer openers, lists, quotes and data intros.

## Pre-flight checks

1. **First confirm this passage should let the words lead.** Use it only for lists, one-liners, numbers, chapter cards; if more than 30–60 seconds in a row is all type, switch grammar, or insert an image or a piece of evidence (screenshot, code card, chat bubble) every 2 pages.
2. **Count the characters.** Key word ≤4 characters, support line ≤14 characters; only one thing enters at any moment. Over that, split the page — don't shrink the type and cram.
3. **Never more than 3 consecutive pages of the same page type.** Four flips of "big word + support line + corner label" is a slide deck; break it with a page of numbers slamming in, a page of evidence, or one charge-into-a-color-block transition.
4. **Write every landing point as a bar number or a word in the voiceover.** A landing that is on neither the beat grid nor a word gets deleted or moved onto one.
5. **The type does not move once it has landed.** Motion comes from the beat bump, the page change, evidence entering — the key word does not drift and does not breathe.

---

## ① When to use it

**Use it:**
- Openers and chapter cards for explainers, lists, "X stages," "3 reasons": the information is **structure** (how many, which one, from what to what), not a picture.
- Quotes, one-liners, single-sentence conclusions: "reading it while watching" sticks better than "hearing and remembering."
- Number explainers: one number, one shot, the number itself is the lead.
- Voiceover with clear accented words ("it's not writing code, it's **describing requirements**").

**Don't use it:**
- Storytelling, emotional arcs → no faces, so the audience struggles to empathize (use y4 characters).
- Long explanatory voiceover with a screen full of type → viewers only read and never listen, and they can't even keep up with the reading. More than 30–60 seconds of pure kinetic type is tiring; use it for the opener, chapter cards and the conclusion card only.
- Lists with a lot of text (>5 items) → switch to a static infographic and talk through it slowly.

## ② Frame composition

**Composition**: one key word per screen. The key word is left-aligned and pressed against the left 1/3–1/2 of the frame (or mirrored to the right), the support line sits tight underneath it, and the other side holds one "piece of evidence" (code card, chat bubble, checklist). Put a small label ("stage 01") and a progress track in the upper corner. Keep at least 130px of margin on all four sides.

**Type scale (demo film)**: key word 340px (PuHuiTi 115 Black) : support line 96px (105 Heavy) : label 40px (85 Bold, letter-spacing 6px) ≈ **3.4 : 1 : 0.4**. The key word has to be read in 0.3 seconds, which is why it only gets 2 characters.

**Palette**: one full-screen ground color per chapter — changing chapter = changing ground (the color itself is the chapter number).

| Shot | Ground | Key word | Accent |
|---|---|---|---|
| Title | yellow `#FFD23F` | ink `#111111` | white "3" inside a coral circle `#FF5A36` |
| 01 completion | coral `#FF5A36` | white | yellow highlighter `#FFD23F` |
| 02 conversation | navy `#14213D` | yellow | yellow highlighter, blue bubble `#3A86FF` |
| 03 agent | off-white `#F4EFE6` | ink | coral underline, green check `#2BB673` |

Four grounds across the whole film + ink + white, and only ever one accent color.

**Shape language**: type is the largest shape; secondary shapes are rounded rectangles only (card r=26, bubble r=30, keycap r=22), true circles (number grounds), diagonal-cut blocks (highlighter, slope 0.18). The background is a dot grid at 64px spacing (6–10% opacity). No outlined type, no drop-shadowed type (the only shadow is the card's 8–18% offset shadow).

## ③ Motion paths

**Entrances (method chosen by "importance")**

| Element | Method | Curve and duration |
|---|---|---|
| Key word | **Slam**: 1.7× down to 1, opacity 0→1 over the first 0.06s | underdamped spring `1−e^(−10t)·cos(2π·2.2t)`, ~8% overshoot, settles in ≈0.35s |
| Title first word | Slam + rotation back to level, −8°→0 | same |
| Support line, label | **Rise out of a slot**: text pushes from +1.2× its own height up to 0 inside a mask below the baseline | `expoOut`, 0.30–0.35s |
| Number / icon / bubble / keycap | **Pop in**: scale 0→1 | `backOut`, s=2.6–3.0 (17–20% overshoot), 0.30–0.42s |
| Card | **Slide in**: from +700px or +260px below, with 3.4° of rotation settling to level | `expoOut` 0.40s |
| Typing | truncated per character | 13 characters in 0.5s (26 chars/sec), cursor blinks at 2Hz |
| Code completion | gray text appears at **0 frames** (completion is instantaneous anyway) → Tab turns it solid | keycap depresses 14%, e^(−18t) recoil |
| Highlighter / underline | brushes out left to right | `expoOut` 0.30s, brushed 1–3 eighth notes after the type appears |
| Keyword scale-up | at the accent beat, scale to 1.35× and pin; the highlighter scales with it | spring freq 2.5 / decay 9, on the same beat as its paired action (Tab press, checkmark) |
| Giant stage numeral | 900px, 5–13% opacity, pressed into the lower right, 1.35× down to 1 then a slow diagonal drift at 14/10 px/s | spring freq 2 / decay 8 |
| Checkmark | the stroke draws on by arc length while the box goes 1→1.25→1 | 0.22s; the strikethrough draws 0.08s later |

**Exits**: faster than entrances, on an accelerating curve (`expoIn`), 0.18s, elements offset 0.03s from each other, simultaneously scaling to 0.6, dropping 60px and going transparent. **Exits are faster than entrances** — the audience's attention has already left before the exit begins. Demo title section, last beat: everything except the "3" exits, leaving one shape to charge into.

**Stagger**: words on the same line are staggered by one eighth note (0.25s at 120 BPM); a group of small elements (three checks) is staggered one eighth note each too.

**Continuous motion (the type holds still; other things move)**
- Camera micro-drift: two sine channels, 5px amplitude, periods about 7s / 2.7s; rotation ±0.5°, very slow.
- Beat bump: the whole frame scales 1.2% on every quarter-note beat, decaying as `e^(−25t)` (≈0.12s) — the frame "breathes" with the kick.
- Background dot grid translates diagonally at 36px/s.
- Closing beat: camera pulls out 6% (`expoOut` 0.5s) and everything shrinks slightly = "resolution."

**Reference films (the two YouTube lyric kinetic-type re-uploads grabbed for this pass, 30fps)**: fully static adjacent frames account for only 10.3% (DISCORD) / 21.2% (Charlie Puth) — the frame is moving 70–80% of the time, the exact opposite of storytime's 71% static; large visual events (peaks where the whole frame changes by >1.5%) come every 0.66s / 0.83s on average, close to **one per beat** (the two tracks run about 105 / 99 BPM, one beat 0.57 / 0.60s). The demo's large-event density is one per eighth note (0.25s), twice as dense as the lyric videos — an explainer opener can afford that density; a long film should drop to one per beat.

## ④ Transitions (3 in the demo + 2 common)

1. **Zoom through**: the camera charges into a shape on the previous screen (the coral circle behind the "3"), that shape's color = the next screen's ground, and after it fills the frame the next screen drops from 1.25× back to 1. Scale up to 30× with `expoIn` over the first 55% of the time, settle with `expoOut` over the last 45%. `TRANSITIONS.fillZoom` (named zoomThrough in the experiment, renamed when it went into the library to avoid colliding with 3b1b-style camera zooms), params `cx, cy, k, maxZoom, fill`.
2. **Band wipe**: three diagonal bands (yellow→white→navy) sweep left to right in relay, offset 12%, the last band is the next screen's ground, and the next screen is revealed behind them. 0.5s `expoInOut`. `TRANSITIONS.bands`.
3. **Push**: old and new translate together, like sliding along one long canvas to the next panel. 0.35s `expoInOut`. `TRANSITIONS.push`.
4. **Mask wipe**: a shape (circle, rectangle bar, the type itself) acts as a mask, growing from small to reveal the next screen. The skill's existing `iris` works.
5. **Type morph / type as transition**: a word on the previous screen scales up into a full-screen color block, or a word whips out of frame and carries the old screen away.

**The alignment trick (the most valuable item in this pass)**: in the engine a transition starts at the new segment's `t0`, so to put the frame where "the new screen is revealed" exactly on the bar line, segment start = **bar line − the transition's reveal point × transition duration**. Demo: fillZoom reveal point p=0.55, duration 0.45 → start 1.75 (reveal at 2.00); bands reveal point ≈0.6, 0.5s → start 3.70; push uses expoInOut, where the eye's "arrival" is the moment displacement hits 90% (p≈0.58), not p=1 → start 5.80 (the first version computed start 5.65 from p=1, and review measured "the push finishes 8 frames before the downbeat"). Every landing point inside a shot is also written as a bar number `KT.b(n)`, never in seconds.

## ⑤ Rhythm and text

- **120 BPM, 4 bars + 1 beat to close (8.5s), one shot per bar** (title / stage one / stage two / stage three). Inside each shot: beat 1 the key word slams (plus the giant background stage numeral), beat 1.5 the evidence, beat 2 the support line, beat 3 the evidence action, beat 3.5 the keyword scale-up + highlight, beat 4 empty or exit; the 16th beat (8.0s) is the closing hit, then 0.5s of stillness. All four shots use the same beat map, swapping only left/right and content — from the second shot the audience "knows where the next hit is," and that is exactly where the sense of rhythm comes from.
- **Key words land on the strong beat (beat 1 of each bar)** with a low-end impact; small elements land on eighth notes with a pop; 0.3s before a transition a rising noise sweeps the ear into the next bar.
- Every visual landing has a sound and every accent has a picture — the demo's SFX table is `build_y5.py` in the experiment archive (not absorbed into the skill) and maps one-to-one onto the bar numbers in `scenes/*.js`.
- **Leave enough time to read**: the lower bound in English video-text guidance is 13 characters/sec (SSW); no primary standard was found for Chinese, so use the subtitling industry's practical ceiling of 7–9 characters/sec (unverified; treat as a rule of thumb). A 2-character key word holds at least 0.5s; a 7–8 character support line holds at least 1.0s.
- When syncing to voiceover: the key word = the accented word in the voiceover, and **the picture would rather be early than late — at most 1 frame early** — people are far more sensitive to "sound before picture" than "picture before sound" (EBU R37 broadcast sync tolerance is sound leading ≤40ms, lagging ≤60ms).

## ⑥ Implementation notes

> After absorption into the skill (2026-10-04 v0.4): the shared functions from this card's "new" section are unified into `scripts/art-motion/engine/lib/` (names changed to the unified MO / CAM / DG / TY / CH / UI / CL / TOON), and the demo's own code lives in `scripts/art-motion/engine/demos/y5_kinetic_type/`. For the library cheat sheet and "how to pick a grammar for a stretch of voiceover," see `references/art-motion/09-animation-grammar.md`.

- **Reuse from the skill**: the engine (segment table, transitions with old and new layers, `renderFrame`), `render.py`, `U.clamp / lerp / rng`; `PAINT` is not needed (this style uses no textures).
- **Engine changes (already merged into the skill engine)**: `window.BPM` is configurable (default 128, this film 120); any segment can carry `dur` in seconds; a transition takes `punch:0` to switch the punch off (this film uses its own beat bump, and it bumps on the beat, not on the transition's start).
- **Newly written, now unified into the library** (`scripts/art-motion/engine/lib/motion.js` / `typo.js` / `camera.js`, transitions in `transitions.js`):
  - Easing: `expoOut / expoIn / expoInOut / quintOut / backOut(p, s) / spring(t, freq, decay) / settle(t, amp, freq, decay)`.
  - Type: `TY.text` (scale and rotate about an arbitrary pivot, stroke, letter-spacing), `TY.width`, `TY.rise` (masked rise), `TY.pop` (pop in), `TY.typed` (typing), `TY.marker` (diagonal highlighter block), `TY.underline`.
  - Camera: `CAM.with(c, {x, y, z, r}, fn)`, `CAM.drift`.
  - Transitions: `fillZoom`, `bands`, `push`.
- **This film's `y5_kinetic_type/kinetic.js`**: `KT.b(n)` bar numbers, `KT.SZ` type scale, `KT.bump` beat bump, `KT.slam` key-word slam, `KT.dots` dot grid, the progress track (drawn on the `GLOBAL_OVERLAY` fixed layer, its value determined only by film time — the skill's No. 02 "continuous narrative anchor" usage; the first version drew it inside each segment and it jumped with the page on a push), `KT.key / keyMarker` (keyword rises first, then scales and pins at the accent beat), `KT.bigNum` (giant background stage numeral), `KT.cam`.
- **Chinese fonts**: the demo uses Alibaba PuHuiTi 3.0 at four weights (Black/Heavy/Bold/Medium); for licensing the open-source build swaps to Source Han Sans / Noto Sans SC 900/800/700/500, keeping the `PuHui-*` family names, with a full GB2312 subset (`scripts/art-motion/font_subset.py --gb2312`) — changing the topic normally needs no rebuild.
- **Music (`build_y5.py` in the experiment archive, not absorbed into the skill)**: numpy-synthesized drums (kick on every beat, clap on 2/4, hats on the offbeats) + bass (eighth notes on one root per bar) + event SFX (key word = boom, small element = pop, typing = click, checkmark = rising pop, pre-transition = riser).

## ⑦ Representative works and primary references

- Saul Bass title archive (Art of the Title): https://www.artofthetitle.com/designer/saul-bass/
- Wikipedia, "Kinetic typography" (the motion typography / fluid typography split; Bass as the feature-film pioneer): https://en.wikipedia.org/wiki/Kinetic_typography
- School of Motion, *Kinetic Typography in After Effects* Part 2 (frame counts: small words slide in over 4 frames, the key word whips in over 6 frames + 2 frames of overshoot settling back, camera push 6 frames + 2 frames pulling back; "the camera should move a little late, as if it's being pushed by the sound"): https://www.schoolofmotion.com/blog/kinetic-typography-after-effects-part-2
- School of Motion Part 3 (falls should accelerate, not ease out; on impact the whole comp scales up and returns to 100%): https://schoolofmotion.com/blog/kinetic-typography-after-effects-part-3
- Dan Ebberts' inertia bounce expression (`amp·sin(2πft)/e^(decay·t)`, default freq 3 / decay 5): http://www.motionscript.com/articles/bounce-and-overshoot.html
- Lee, Forlizzi, Hudson, *The Kinetic Typography Engine* (UIST 2002; moving type expressing emotion and tone): https://dl.acm.org/doi/10.1145/571985.571997
- On-screen text duration: https://www.ssw.com.au/rules/post-production-do-you-give-enough-time-to-read-texts-in-your-videos
- The two re-uploads measured here: DISCORD [Kinetic Typography] https://www.bilibili.com/video/BV1ts411S7Xa ; Charlie Puth – We Don't Talk Anymore (Kinetic Typography) https://www.bilibili.com/video/BV1by4y1r74Y

## ⑧ The 3 easiest things to get wrong

1. **Everything the same size, everything moving together.** No hierarchy means no focal point, and the viewer doesn't know what to read first. Key word to support line at least 3:1, and only one thing "entering" at any moment; everything else holds still.
2. **Type that keeps drifting.** Type must not move while it is being read (people can't read it). Continuous motion belongs to the camera micro-drift, the beat bump and the background dot grid; the type pins 0.35s after it slams in.
3. **Animation that misses the beat — or lands on the transition's start.** The first frame of a transition is not the accent; the frame where "the new screen is revealed" is. Move the segment start back by "reveal point × duration," then write every landing inside the shot as a bar number; every landing outside the beat grid scatters the film a little further.

---

## Demo film

- Finished film: `scripts/art-motion/engine/demos/y5_kinetic_type/` (render with `render.py --film demos/y5_kinetic_type`) (8.5s, 60fps, synthesized score at 120 BPM); one frame per shot overview: `assets/animation-grammar/y5_kinetic_type_overview.jpg`
- Project: `scripts/art-motion/engine/demos/y5_kinetic_type/` (`eras.js`, `kinetic.js`, `k1_title.js / k2_complete.js / k3_chat.js / k4_agent.js`); the shared parts are in `scripts/art-motion/engine/lib/`
- Shot list: K1 title "The 3 stages of AI writing code" → zoom through → K2 "completion" (code card + gray completion + Tab) → band wipe → K3 "conversation" (you one line, it a whole paragraph) → push → K4 "agent" (three TODOs check themselves off) + progress track full

## Review fixes (independent agent, finished film only)

Review verdict: "0–2s is standard kinetic type, and the '3' circle charging into the lens to become the next section's ground is the best design in the film"; "sound-picture alignment is almost perfect, every visual event lands on the 120 BPM grid, on the same frame as the kick." 5 "must fix" notes, handled as follows:
1. **Support lines held too briefly** (0.6–0.9s) → support lines come one beat earlier and are cut to 6–7 characters ("it completes the next line", "one sentence, a whole paragraph", "you only say what you want"), giving 1.0–1.5s of readable time (stage 2 is still tight, but a real voiceover fixes it); added 0.5s to the whole film.
2. **Stage 2's support line nearly hit the AI panel** (14px) → shortened the support line, right-aligned it, spacing >180px.
3. **The push page ran 8 frames early and the progress track jumped with it** → recomputed the segment start from the 90% displacement (5.80); moved the progress track to the `GLOBAL_OVERLAY` fixed layer, with the color changing on the reveal frame.
4. **The stage sections weren't kinetic enough** (numbers too small, keywords only highlighted, never scaled) → added the giant background stage numerals 1/2/3; keywords scale to 1.35× at the accent beat.
5. **The ending had no closing hit and everything went gray after the checks** → added a 16th-beat closing hit (camera pulls out 6% + 3.5% impact + low end + high bell), checked text turns green instead of gray, and shifted the content down 70px to fill the empty bottom.
Also: the code card now uses a monospace font (Menlo).
Not adopted: "extend each section to 2.5–3s, 10–11s total" — the demo brief is about 8 seconds, so cut characters instead of adding length.

## qa.py numbers (after fixes, `uv run scripts/art-motion/qa.py --project scripts/engine --film demos/y5_kinetic_type`)

| Segment | Motion % | Static frame pairs % | Jumps | Mean/peak ms | Deterministic |
|---|---|---|---|---|---|
| k1_title | 2.37 | 0.0 | 1 (t=1.63, title exit) | 1.0/1.6 | ✓ |
| k2_complete | 2.39 | 0.0 | 0 | 1.5/3.2 | ✓ |
| k3_chat | 2.59 | 0.0 | 1 (t=4.54, AI bubble grows) | 1.6/2.2 | ✓ |
| k4_agent | 2.88 | 0.0 | 3 (t=6.29 Agent + task cards; t=8.00/8.04 closing hit) | 1.6/2.0 | ✓ |

Transition smoke test (whole-frame peak): fillZoom 6.8ms, bands 4.8ms, push 3.8ms. All 5 jumps were inspected frame by frame; every one is a deliberate beat accent (qa doc: "a deliberate beat flash is not a fault"). Kinetic jumps should land on the beat — you can check jump timestamps against the beat grid, and only the mismatches are bugs.
After the fixes, scanned all four edges frame by frame: 0 frames showing black.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
