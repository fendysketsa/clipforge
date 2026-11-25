# y4 · Storytime Stick-Figure Character Animation (YouTube storytime animation)

> One-line grammar: **The voiceover is the lead; the picture is a sticker pack of expressions cut to the voiceover — the character snaps between a few poses (0.1s) and then holds still, and the joke lands by cutting to a big reaction close-up and shutting the mouth on that beat.**

Representatives: TheOdd1sOut (James Rallison), Jaiden Animations, Domics. Tools: per Jaiden's FAQ and secondary sources, all three used Flash / Adobe Animate in their early work (no primary text obtained for this; background only).

---

## ① When to use it

**Use it:**
- First-person accounts of experiences, of screw-ups, of "the first time I…": the voiceover has setup, turn and payoff, and one laugh you can pause on.
- The audience wants "this person": the creator's cartoon avatar shows up every episode, and viewers recognize the persona, not the linework (Pappis's genre study: avatars "are often distinguishable by hairstyle alone").
- Limited budget, steady weekly output: one character, five or six poses, three mouths carry a whole episode.

**Don't use it:**
- High-density tutorials, data explainers → use y5 kinetic typography or an infographic. Viewers watch the character waiting for a joke and retain none of the numbers.
- Content with no "I" in it (industry news, product comparisons) → the character has no position to perform and degrades into a sticker that opens its mouth.
- A voiceover that isn't funny and has no pauses → this style amplifies the voiceover; it does not rescue it.

## ② Frame composition

**Composition**
- Medium shot (waist up, head at 25–35% of frame height) is the default camera. Put the character center or off to one side and leave the other side for "the thing he's talking about" (a computer, the other person, an object).
- The background only establishes "where": one wall, one desk, one window, 3–5 large color blocks. A white or flat-color ground works perfectly well (Pappis: "white backgrounds or a crude sketch of a scene").
- Reaction shots strip the environment: the face fills the frame (head radius ≈ 1/3 of frame height), the background goes flat plus a vignette.
- Punchline shots often invert it: cut to an **extreme wide** and the person becomes tiny ("small and helpless" is itself the joke).

**Palette (actual values from the demo film)**

| Region | Value | Notes |
|---|---|---|
| Skin | `#FFE2CC` | Pale, near-white — TheOdd1sOut's "marshmallow man" is pure white; Jaiden runs warmer white |
| Hat / white tee | `#FFFFFF`, hat band `#E4E4E8` | White things stand up on black outlines |
| Shorts | `#CDBB97` | |
| Character line | `#1B1B1F` | Darkest in the film |
| Wall / desk / floor | `#DCE9EC` / `#E2C29B` / `#E8DCC8` | Low saturation, high value: the background is always "lighter" than the character |
| Background line | `#5B6470` 3px | Lighter than the character line, less than half as thick |
| Reaction-shot void | `#3D405B` + radial vignette | Cool, dark, presses all attention onto the face |
| Mouth / tongue / blush | `#6E2430` / `#F07B7B` / `rgba(255,140,120,.35)` | The only saturated color in the mouth; the open-and-shut reads instantly |

**Line weight**: character line = head radius × 0.05 (4px minimum) — medium shot R=165 → 8px, big close-up R=360 → 12px, wide R=95 → 6px. The line thickens and thins with the camera zoom (Flash's default behavior); background lines stay fixed at 3px. **Character line ≥ background line × 2** is the root of this style's "the person always pops out."

**Shape language**: all round, all blunt. The head is a slightly squashed circle (width 1.0R × height 0.93R), the body is a bean (width 1.0R × height 1.2R), the whole figure 3.2R — **the head is about 58% of body height**. An arm is one tube with rounded ends, no elbow, no fingers; the hand is a circle. No right angles anywhere except on props.

**Character build (the author's storytime version)**
- Keep two signatures: a **pure white bucket hat** (rounded-trapezoid crown + wide brim angling down + light gray band) and **round black glasses** (frame line at 1.5× the outline weight — the glasses are the "eyes" of this face). From the original design keep only the white tee, khaki shorts and a black watch (a small black block on the near wrist).
- The eyes are black dots inside the lenses (0.075R) with one white highlight; "dead fish eyes" shrink the dot to 0.035R and drop the highlight.
- Expression rides mainly on the **eyebrows** (the short heavy line between brim and frame): raised = alarm, inner ends raised = hurt, flat = unimpressed. The mouth has only five states: smile arc, flat line, wavy line (worry), half open, full open.
- Show a little black hair at the sideburn so the audience knows there is hair under the hat, not a bald head.

## ③ Motion paths

**Measured on the source films (this pass; 480p re-uploads; first and last 10s trimmed; method: 160×90 grayscale frame differencing)**

| | TheOdd1sOut "Mom's Punishment" (30fps, 475s) | Jaiden Animations "Being Not Straight" (24fps, 902s) |
|---|---|---|
| Average shot length ASL | **2.43s** (median 1.87s, IQR 1.03–3.07s) | **5.73s** (median 3.21s, IQR 1.67–6.67s) |
| Adjacent frames fully static | **70.7%** | 51.2% |
| Static run length | median **0.40s**, p75 0.70s | median 0.08s (= the hold of one on twos) |
| Motion run length | median **100ms** (3 frames) | median 42ms (1 frame) |

How to read it: TheOdd1sOut is **snap (0.1s) → hold (0.4–0.7s) → snap again**, with the frame completely still seven-tenths of the time; Jaiden is **on twos and continuously moving** (12 drawings/sec), with longer shots. Hallis Blaney, animation supervisor on the Netflix series *Oddballs*, put it most precisely in the Toon Boom interview: "TheOdd1sOut is pose-to-pose, very little animation… it's basically switching between images," and the hardest part of converting it to a series was keeping that snappiness and avoiding "too soft, too slow." The demo film takes the middle: pose snapping from TheOdd1sOut, breathing and lip sync from Jaiden.

**Demo film parameters**

| Motion | How | Numbers |
|---|---|---|
| Character frame rate | all character motion stepped at 24fps (`MO.step(t,24)`), camera smooth at 60fps | Flash's default 24 |
| Pose change | arm target points interpolated with `expoOut` | **0.10s** (2–3 frames at 24fps) |
| Pose-change recoil | body squashes 7% vertically at the switch, Ebberts spring recoil (volume conserved, lateral inverse) | `settle(dt, -0.07, freq 3.5, decay 9)`, settles in ≈0.35s |
| Lip sync | read the voiceover RMS envelope, **a new shape allowed only every 1/12 second** (on twos); three mouths | envelope <0.06 closed, <0.22 half open, else full open |
| Talking nod | head dips when the mouth opens | 0.015R × mouth level |
| Breathing | vertical body scale | ±1.2%, period 1.6s |
| Blink | fixed schedule, 2.4–3.6s apart | 2 frames closed @24fps (83ms); "unimpressed" slow blink 3 frames |
| Eye line | the dot shifts toward whatever is pointed at | 0.09R |
| Camera | the demo used medium, close-up, a slow push on a near shot and a slow pull on a wide (slow push on every shot — the old way); new films hold still first, and change comes from hard cuts and jump-ins; a smash-in only for the punchline | demo: medium +3.5%/2.0s; close-up +6%/1.2s; wide 0.53→0.50 (quintOut); near 1.90→1.98 |
| Opening | camera settles 1.04→1.01 (0.5s expoOut) instead of "a static first frame" | |
| Sweat drop | slides down the side of the face from the temple | 0.9s, expoOut blended with linear |
| Lens glint | white diagonal band sweeps across both lenses | 0.3s |
| "?" | pops above the head, backOut 30% overshoot, then sways ±3° | 0.26s |

Entrances/exits: storytime has almost no "entrance animation" — on the first frame after the cut the character is already in place and already talking. Only props and symbols (?!, sweat drop, numbers) pop in (`backOut`, 15–30% overshoot).

## ④ Transitions (5 common ones)

1. **Hard cut** — the vast majority. One voiceover sentence, one shot; cut when the line changes. Demo S3→S4 (close-up → extreme wide of the same room) is a hard cut, and the joke comes from the scale contrast.
2. **Smash cut to a reaction close-up** — the new frame is there on its first frame, springing from 1.22× back to 1 (freq 3, decay 11), with a 55% white flash over the first 2 frames and a low "dun." Use for "he says something insane → look at his face." `TRANSITIONS.smash`.
3. **Whip pan** — whip the camera toward "the thing he's looking at," `expoInOut` 0.26s, stacking 16 offset copies mid-move for horizontal motion blur, plus a whoosh. Use for gaze transfers like "I open the laptop → (the screen)." `TRANSITIONS.whip`.
4. **Jump-in** — cut from the same camera position straight to roughly 2× closer, no background change. Use for "he repeats it," "he realizes," "the punchline line." Demo S4→S5: in the wide he says "these…", then on the breath before "where do they go" it hard-cuts to a 1.9× near shot so the punchline face reads. This requires the wide and the near shot to be **one world canvas with only the camera swapped** (`world.js`); otherwise the jump gives itself away.
5. **Over-the-shoulder / POV** — cut to what he sees (screen, phone, the other person), with the back of his head in the foreground. Demo S2: the author's back — white hat + band, ear, glasses temple hooked over the ear, short black hair, nape, white tee collar, and a cool rim light all around the screen side (the first version drew it as a pure black silhouette and review read it as "another shadow person"). The foreground does not follow the camera push, only rises and falls with breathing, and parallaxes against the screen — the frame instantly "has space."

## ⑤ Rhythm and text

- **Cuts follow voiceover sentences, not musical beats**: one sentence ≈ one shot. The demo's 5 shots average 1.75s (2.0 / 2.4 / 1.2 / 1.65 / 1.5), inside TheOdd1sOut's measured interquartile band of 1.03–3.07s.
- **Put transitions in the breath between two sentences, and change subtitles on the same frame as the cut**: the first version whipped on the first two characters of "it at one breath" and review flagged "the cut lands mid-sentence"; fixed to L1 ends (1.87s) → 2.0s whip → 2.26s settle → speech resumes at 2.30s.
- **Put reaction shots in the silence between two sentences**: demo S3 runs a full 1.3s with no line at all, only crickets — that pause is the joke. In the edit: after the insane line ("three thousand lines") **do not start the next one immediately**; leave 0.8–1.5s for the face.
- **Hold ≥0.9s after the punchline**: the "?" pops at 7.80s and the film ends at 8.75s so the SFX tail finishes naturally (the first version left only 0.4s; review: "the laugh beat got cut off").
- **Text**: native YouTube storytime does not burn in subtitles (it relies on CC); it only puts words on screen that "need to be seen" — text on a screen, key numbers (the demo's "3000 lines" set in PuHuiTi Black 230px, `#FFCB6B`, slammed in with 23% overshoot). Chinese platforms need burned-in subtitles: white 50px, 10px black stroke, whole sentence cut in and out, no animation (moving subtitles compete with the character for the eye).
- In-frame numbers align to **the same word** as the voiceover: the syllable "three thousand" (3.70s) = 3000 slams in = low thump = screen shake (9Hz, fully decayed in 0.3s).

## ⑥ Implementation notes

> After absorption into the skill (2026-10-04 v0.4): the shared functions from this card's "new" section are unified into `scripts/art-motion/engine/lib/` (names changed to the unified MO / CAM / DG / TY / CH / UI / CL / TOON), and the demo's own code lives in `scripts/art-motion/engine/demos/y4_storytime/`. For the library cheat sheet and "how to pick a grammar for a stretch of voiceover," see `references/art-motion/09-animation-grammar.md`.

- **Reuse from the skill**: the engine (segment table, offscreen compositing of the outgoing and incoming segments during a transition, `GLOBAL_OVERLAY`), `render.py`, `PAINT.cached` (the whole room background cached as one image), `U.rng` seeded randomness (the color-block layout of the code waterfall).
- **Two engine changes (already merged into the skill engine)**: any segment in the segment table can carry `dur` in seconds — no need to fit eighth notes, because storytime cuts on voiceover, not on the beat; a transition can take `punch: 0` (or film-level `window.PUNCH = 0`) to switch off the engine's default beat impact (storytime has no beats).
- **Newly written, now unified into the library** (`scripts/art-motion/engine/lib/toon.js` / `typo.js` / `camera.js` / `motion.js`, transitions in `transitions.js`):
  - `TOON.bean(c, {x, y, s, char, pose, expr, mouth, blink, look, squash, bob, tilt, lw})`: front-facing bean character, fully procedural Path2D, returns the coordinates of both hands and the head (for placing props and symbols). The bean character this code draws is kept only for the demo and for white-box previz: after watching films made with several models, the author judged code-drawn figures to read as AI at a glance (his words: "the little people and robot characters in a lot of videos are just bad"). The y4 parameterized clip accepts only your own frame library (`data.character.frames`, AI-generated frames; see No. 10 and `references/art-motion/character-detail.md`), and startup fails without a frame library.
  - `TOON.POSES`: rest / talk / point / type / shrug / stiff — each pose is nothing but the target point of the two hands relative to the shoulders (unit: head radius).
  - `TOON.mouth(t)`: reads `window.VO_ENV` (the 60fps RMS envelope exported by the audio script), quantized on twos to 0/1/2.
  - `MO.springHz / settle / backOut / expoOut / step`, `CAM.with`, `CAM.drift` (the handheld micro-drift the demo used; a new film that holds still holds still — no drift), `TOON.sweat`, `TOON.mark`.
  - Transitions `whip`, `smash` (the charge-into-a-color-block transition used by y5 was renamed `fillZoom` when it went into the library; `bands / push` also available).
- **This film's `y4_storytime/story.js`**: `STORY.poseAt(keys, t)` (pose timeline + pose-change recoil), `blinkAt`, `alive` (nod + breathing), subtitle overlay.
- **Audio (`build_y4.py` in the experiment archive, not absorbed into the skill)**: lays the voiceover, synthesizes the SFX (whoosh, keyboard, bloop, thump, "dun," crickets, pip, boing), and exports `vo_env.js` at the same time. The voiceover is a macOS `say` Eddy placeholder — **re-export the envelope after swapping in a real voice track and the lip sync follows automatically**.
- **One room, three shot sizes**: `y4_storytime/world.js` draws the room as a single world canvas (x −1000..2900, y −700..1700, static parts cached whole); S1 (zoom 1.01–1.045), S4 (0.53→0.50) and S5 (1.90→1.98) only swap `CAM.with`. The bookshelf, plant and pendant lamp that only the wide sees are already in the world. The world must be one ring larger than the widest shot, or camera drift exposes black edges (all three black-edge bugs in v1 were this).
- Key parameters: character 24fps, lip sync 12/sec, pose change 0.1s + 7% recoil, character line 0.05R.

## ⑦ Representative works and primary references

- TheOdd1sOut channel: https://www.youtube.com/@theodd1sout ; the re-upload of "Mom's Punishment" measured here: https://www.bilibili.com/video/BV14s411M7x4
- Jaiden Animations channel: https://www.youtube.com/@JaidenAnimations ; the re-upload of "Being Not Straight" measured here: https://www.bilibili.com/video/BV1xu411r734
- Domics channel: https://www.youtube.com/@Domics
- Toon Boom × Atomic Cartoons, *Oddballs* from YouTube to series ("pose-to-pose, very little animation," "he never did lip sync on YouTube," "too soft, too slow"): https://www.toonboom.com/atomic-cartoons-on-bringing-oddballs-from-youtube-to-series
- Konstantinos Pappis, *The Odd Ones Out: The Rise of YouTube Storytime Animation* (Animation Studies; genre history and visual grammar: round-faced avatars, white grounds, no frame-by-frame, closer to an animated storyboard): https://journal.animationstudies.org/article/id/135/
- TheOdd1sOut wiki (source of "marshmallow man"): https://en.wikipedia.org/wiki/TheOdd1sOut
- Dan Ebberts' inertia bounce expression (source of freq 3, decay 5): http://www.motionscript.com/articles/bounce-and-overshoot.html
- Maker thread "add a little bounce when changing pose": https://forum.wickeditor.com/t/whoever-wants-to-make-a-storytime-animation/5940

## ⑧ The 3 easiest things to get wrong

1. **Treating it as "full animation," with everything moving.** The life of this style is "snap + hold": seven-tenths of TheOdd1sOut's frames are completely static. When everything drifts slowly, the result is soft and has no rhythm (the "too soft, too slow" the *Oddballs* team feared most). Pose changes must be as fast as 0.1s and then **actually stop**; continuous micro-motion goes only to breathing, blinking and small background props, amplitude ≤ 1–2%.
2. **Drawing the background as well as the character.** Background saturation, contrast and line weight all sit one step below the character (this film: 3px gray background lines vs 8px black character lines). The moment the background gets busy, the eye leaves the face and the voiceover's joke is lost.
3. **Not giving the reaction shot any silence.** Starting the next line immediately after the insane one is the same as telling the joke away. Reaction shots go in the gap of the voiceover, at least 0.8s. Hold the camera and give only one or two small details (sweat drop, slow blink, eyebrows collapsing); to push it, jump in one size on the punchline beat (hard cut to about 2× closer) or smash in for 0.17s — don't fill with a constant-speed slow push.

---

## Demo film

- Finished film: `scripts/art-motion/engine/demos/y4_storytime/` (render with `render.py --film demos/y4_storytime`) (8.75s, 60fps, with temporary voiceover + SFX); one frame per shot overview: `assets/animation-grammar/y4_storytime_overview.jpg`
- Project: `scripts/art-motion/engine/demos/y4_storytime/` (`eras.js` segment table, `story.js`, `world.js` world canvas, `s1_desk.js / s2_screen.js / s3_react.js / s4_wide.js / s5_close.js`); the shared parts are in `scripts/art-motion/engine/lib/`
- Shot list: S1 medium, talking to camera (0–2.0s) → whip → S2 over the shoulder at the screen, code waterfall + "3000 lines" (2.0–4.4s) → smash → S3 reaction big close-up, silence (4.4–5.6s) → hard cut → S4 extreme wide of the same room, "I ask it: these…", glance at the computer, point at it (5.6–7.25s) → jump-in → S5 near shot, palms up, "where do they go?" + "?", hold (7.25–8.75s)

## Review fixes (independent agent, finished film only)

The first version drew 5 "must fix" notes; all handled:
1. Three black-edge leaks (S1 left/top, the smash recoil dipping below 1, the S4 camera drifting down) → made the world canvas bigger + clamped the `smash` scale at ≥1. After the fix, scanned all four edges frame by frame: 0 frames showing black.
2. The punchline had no room to breathe → split out the S5 jump-in shot, with a 0.95s hold after the "?".
3. S1 and S4 were not the same room → rebuilt as one world canvas with a camera swap.
4. The over-the-shoulder silhouette read as another person → drew in back-of-head identifiers + rim light.
5. The whip cut mid-sentence and the second subtitle came late → moved the whip into the breath, subtitles on the same frame as the cut.
Two "could be better" notes handled: eyebrows collapse 0.15s after the second cricket in S3 (the SFX was at 5.23s and the expression at 5.38s, mismatched); in S4's two pauses, added "glance at the computer → back to camera" and pointing at the computer while saying "these." Subtitles lost the space between Chinese and English ("makeAIhelp me", "3000lines").
Not changed: the lines are uniform-weight vector strokes with no hand-drawn jitter — that is exactly what TheOdd1sOut / Jaiden's Flash vector lines look like; kept.

## qa.py numbers (after fixes, `uv run scripts/art-motion/qa.py --project scripts/engine --film demos/y4_storytime`)

| Segment | Motion % | Static frame pairs % | Jumps | Mean/peak ms | Deterministic |
|---|---|---|---|---|---|
| s1_desk | 1.47 | 8.6 | 0 | 9.9/10.4 | ✓ |
| s2_screen | 6.0 | 0.0 | 0 | 1.7/3.8 | ✓ |
| s3_react | 1.73 | 0.0 | 0 | 5.6/6.1 | ✓ |
| s4_wide | 0.77 | 16.2 | 0 | 9.6/9.9 | ✓ |
| s5_close | 3.27 | 3.1 | 0 | 10.9/11.4 | ✓ |

Transition smoke test (whole-frame peak): whip 47.9ms, smash 10.1ms, cut 15.7 / 20.5ms. The first version reported one jump each in s1, s2 and s4 (the opening settle, the 3000 slam, the fast pull-out at the top of the wide); after the fixes, 0.
Read this table carefully: qa's empirical threshold "static frame pairs >40% reads as stuck" **does not apply to storytime** — 70.7% of TheOdd1sOut's adjacent frames are completely static, and that is the style, not a stall. This film's static frame pairs run 0–16%, far "livelier" than the source, deliberately taking Jaiden's continuous breathing; to get closer to TheOdd1sOut, switch off breathing, nodding and the background micro-loops and keep only lip sync and pose snapping (static frame pairs would rise sharply; not measured this pass).

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
