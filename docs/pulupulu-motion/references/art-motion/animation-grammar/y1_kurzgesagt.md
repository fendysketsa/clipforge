# Y1 · Kurzgesagt flat science: video animation grammar card

One sentence: draw an abstract concept as one concrete object, put it inside a glowing world that can scale without limit, and let the camera travel between scales; the environment layer (stars, particles) may keep drifting gently the whole time, the subject and the information change on narration beats, and once they settle, they stop.

Demo film: `scripts/art-motion/engine/demos/y1_kurzgesagt/` (render with `render.py --film demos/y1_kurzgesagt`) (8s, 3 shots, 2 transitions), overview: `assets/animation-grammar/y1_kurzgesagt_overview.jpg`
Basis: research into this style (the original research text and per-frame data stay in the experiment archive and were not collected into the skill; the numbers used are excerpted into this card) (two 2025 main films plus a measured pass on the 2014 "The Immune System", official Skillshare class transcript). Numbers tagged [measured] and [first-hand] come from there; those tagged [this film] are the parameters actually used in the demo film.

## Check before you start

1. **Write the visual metaphor of this passage first: what object does the abstract concept become** (a cell, a gear, a pipe, a city, a drop of water...). If you cannot name an object for that line, do not just put one glowing ball and a few label capsules on screen.
2. **The orange central planet in the demo film and in the samples is one way of drawing it, not the signature of this grammar.** The central object changes shape and colour with the subject. In parametric segment y1 the central object is set by the spec: `data.center_style` (colour, shape, whether it carries orbit rings) or `data.image` (crop a real photograph into the central object); leave it out and a neutral style is generated from the name, no longer that orange planet. It only draws "central object + satellite nodes", which suits the layered "what is inside it" telling; if the subject is not that structure, write your own shots (`demos/y1_kurzgesagt/` and `CAM`, `TOON` in `lib/`), or switch grammar.
3. **At least one state change per narration sentence** (pop out, morph, dive in, pull back). Count it sentence by sentence: two consecutive sentences with an unchanged frame means you owe an event — do not pad it with floating and slow pushes.
4. **Hold once the subject settles.** The environment layer (star twinkle, particle drift, distant clouds) may keep moving gently; the subject and the labels get no float and no breathing, and you do not fill a pause with a constant-speed slow push.
5. **Pause before you dive in.** Before a scale transition, let the object you are about to enter hold for 0.3s or more and light up, so the viewer knows which one comes next; interpolate the zoom logarithmically (`CAM.zlerp`).

---

## ① When to use it

**Use it:**
- Content about scale, about "what is inside": from cell to galaxy, from one pixel to a model, or "zoom in and you find...". The scale transition is standard equipment in this style.
- Content about mechanism, about systems: neural networks, the immune system, energy flow. It is the best fit for drawing invisible processes as glowing particles and links.
- The narration is calm, unhurried popular-science delivery. Kurzgesagt runs about 168 words/min; one hard cut carries roughly 2 sentences [measured].
- You need a "serious but cute" tone: bring out a mascot or a flock of birds to land the joke.

**Do not use it:**
- Real people, real events, documentary evidence: flat cartoon dilutes credibility — use Y2 collage for that.
- Steps and chains of reasoning: writing them out one by one reads better — use Y3 whiteboard.
- When the production budget is very small. The quality of this style rests entirely on "something is moving in every frame"; an official episode takes 1200+ hours [first-hand]. A Kurzgesagt done on the cheap looks like a cheap PPT.

## ② Frame composition

- **Pick the era first.** 2025 is the dark set: dark pixels occupy 61–68%, median saturation 0.84–0.89. 2014 was a light grey-white ground, low saturation. The two cannot be mixed [measured]. The first two shots of the demo film use the 2025 dark set, the third shot uses the bright set in daylight, copying their practice of "change the passage, change the whole colour temperature".
- **Palette** (2025 dark set, sampled from measurement):
  - Ground: `#05020F` / `#0E0631` / `#25155E`
  - Secondary ground: `#191670`, `#3826A3`, `#5F58DB`
  - Cyan accents: `#32BAEE`, `#7DD3DC`
  - Orange-yellow accents (glowing bodies): `#F48301`, `#E07919`, `#FACC12`, glow core `#F9EF93`
  - Magenta: `#BE3A95`, `#C83C7F`
  - Highlights and white type: `#E7DFE1`, `#F9FCFB`
  - Rule: one dark ground plus 2–3 high-saturation accents, with the accents contrasting against each other (orange-yellow against indigo, cyan against magenta) [measured + induction]
  - **The deep-purple ground above is only a dismantling record — do not copy it into a finished film.** The author has watched many AI-made films; his words were "we need to avoid the blue-purple gradient garbage palette, it's very AI slop"; the deep-purple starfield ground is exactly the most common instant AI smell in that kind of film, and `deliver.py` measures blue-purple ground and raises a red flag. If you want a dark set, use `ink` (deep ink) or `navy` (flat navy) from `references/art-motion/palette.md` and keep the rule "one dark ground plus 2–3 high-saturation accents"; in parametric segment y1 just write `"theme"`, and when it is omitted the default is flat deep ink.
- **Shape language**:
  - No outlines. Shadows are a block one step darker in the same hue; highlights are a white ellipse or a single arc [induction].
  - Rounded corners everywhere. Organisms are blobby organic forms, character heads are round, limbs are round-capped tubes.
  - A glowing body always carries radial glow. The point of the dark ground is to make the glow work.
- **[this film] Two-tone faceting**: `flat(c, path, body colour, shadow colour, highlight colour, v, w)`. Two offsets inside the shape: a shadow band left at bottom right, a thin highlight edge left at top left. v≈(10,12)px, w≈(4,5)px. The author's every part also goes through this pass, so he is drawn the same way as the scene and does not look pasted on.
- **Composition**: put the subject on the lower third, a little below centre, leaving sky above for stars and annotations. A scene splits into 5–6 parallax layers: starfield d=0.05, moon 0.12, far mountains 0.3, near slope 0.65, subject 1.0, foreground leaves 1.5 (the near layer blurred and dark). The official layer count is unpublished; measurement gives 2–5 layers [induction].
- **Characters**:
  - Kurzgesagt bird: egg-shaped body, big white eyes, small black pupils set forward, orange triangular beak. Wings are leaf shapes one step darker than the body, and each bird gets a different colour [first-hand + induction].
  - [this film] The cat is a teardrop body plus a round head, triangular ears with magenta inner ears, big white eyes; the robot is a rounded shell with a dark screen face and one glowing lens eye; the author uses the point pose of `the author.build`, and every part goes through two-tone faceting.

## ③ Motion paths

- **Official easing** [first-hand, Skillshare]:
  - Regular motion 50 frames (0.83s at 60fps). For something crisper use 30/20/10 frames; pops use 5–10 frames.
  - Loops use Easy Ease 33.3%, roughly `cubic-bezier(.333,0,.667,1)`.
  - Other motion uses 75% influence, roughly `cubic-bezier(.75,0,.25,1)`: a very soft start, a fast middle, a very soft finish.
- **Pops** [measured]: a card grows to 90% within 0.25s, overshoots to 108% at frame 20 (the detector card reaches 114%), and is back at 100% by about 0.5s.
  - [this film] identification labels use `backOut(q, 1.1)`, 0.5s long.
- **Stagger**: stagger like elements by 10–20 frames, limbs by 3–4 frames, leave 20 frames between actions [first-hand].
  - [this film] the title staggers per character by 45ms, each character 0.5s cubicOut. The pixel cat's 144 blocks stagger by 35ms per cell according to distance from the centre, each block flying in from the surrounding area over 0.5s with backOut(1.4). The neural network lights up layer by layer at 0.32s intervals, each node popping for 0.35s.
- **Ambient micro-motion and subject holds**: in the 2025 films, stretches with nothing moving at all for 0.5s account for only 0.3% [measured]; what moves is mainly the environment layer (star twinkle, particle drift, glow) and the thing currently being explained.
  - Explainer shots: the subject and the information elements hold still once settled; actions sit on narration beats (pop, morph, push, dive in).
  - Pure atmosphere shots (opening, the breathing space at a passage change) may keep slight ambient motion: stars twinkle, particles drift, the far field creeps.
  - Blinks: 5 frames closed, 10 frames open, irregular interval, **the eye never scales to 0** [first-hand].
  - [this film] 170 stars, each twinkling at its own phase, 1–3.5 rad/s. Foreground leaves at `blur(7px)` for defocus and depth of field. The robot bobs ±12px, its jet glow jittered by a two-sine at 23/37Hz. The cat's tail swings on a two-segment bezier. Grass blades sway at 2.1 rad/s. Firefly particles drift on the 0.8–1.3 layers. Signal pulses loop continuously along the links.
- **Camera** [measured]:
  - In the 2025 films about 1/3 of the time is spent zooming, about 10% panning, about 5% rotating, and pull-backs outnumber push-ins. Most zooming is scale travel and reveal, not pause-filling.
  - The new films' calling-out shot: hold → gentle push for about 0.9s → hold; moving to a new node takes 0.7s; only the reveal gets a fast push of 0.28s or a slam of 0.17s; hold length follows the narration; after pushing in, come back out with a pull-back (④ fast pull-back reveal). Scale travel times follow ④.
  - [this film] shot 1 used a 2.6s constant-speed push 1.00→1.10 — old practice; do not copy it in new films.

## ④ Transitions (6 common ones)

1. **Push through → the object's colour floods the frame → new scene** (the standard way to write a scale transition).
   - Measured: Immune 1:48, about 1.4s, accelerating then decelerating, peak in the middle.
   - [this film] transition B:
     - The camera interpolates logarithmically into the lit output node (0.45s, cubicIn), until the frame is full of yellow.
     - At the midpoint ±3 frames, dissolve to the robot's yellow-glowing eye. Both highlight points sit top-left, so the cut does not read.
     - Then pull back with cubicInOut 1.45s (42→1), landing in the new daylight palette.
     - Do not use expoOut: its initial slope is too steep, and the first frame throws away most of the scale.
2. **Dive into the object; inside is the next world** (a variant of the traverse).
   - [this film] transition A, 1.0s: the camera pushes logarithmically into the robot's lens on `bezier(.75,0,.25,1)` (1.1→60). The next shot appears only inside the "lens circle", and the circle grows with the push until it covers the screen, with a cyan halo on its edge. The next shot surfaces at the same time from 0.42× with expoOut.
3. **Fast pull-back reveal**: 0.2–2s, fast start with a long tail (measured: scale per 0.2s 1.074→1.040→…→1.0006). Used to link the microscopic and the macroscopic.
4. **Light or flash floods the frame**: use a light source in frame as the white-out, about 0.5s.
5. **Sweep wipe**: an object or a light band sweeps diagonally across frame with speed lines, about 0.4s.
6. **Duplicate and multiply until it fills**: for "so many that...", 3–6s.

Two more points [measured]:
- The hard-cut ratio is low, about 5 per minute, following narration sentence starts, 0–0.2s before the sentence start.
- The other picture changes are mostly 0.3–0.6s designed transitions, one every 4.6–6.7s.

## ⑤ Pacing and type

- **Shot length** [measured]:
  - Hard-cut shots: median 7–9s, mean about 11.5s.
  - But the "visual unit" changes every 4.6–6.7s, by way of a designed transition.
  - At least one state change per narration sentence: a label popping, an annotation swapping, a morph or a transition.
- **Aligning to the narration**: use the narration sentence timestamps as the skeleton; put the hard cut 0–0.2s before the new sentence start [measured]. The score is composed after the picture is locked (Epic Mountain) [first-hand].
- **Type**:
  - An annotation draws a thin white leader line first, then types the text character by character at about 40 characters/s; one narration sentence gets one annotation, which holds about 3s and is then wiped character by character [measured].
  - Chapter title cards every 2–3 minutes, full screen, word by word, background defocused.
  - Label capsules have large corner radii, filled with a saturated flat colour, bold sans inside.
- **[this film]**:
  - 3 shots in 8s is about 3× normal density, only so that the whole grammar can be seen in a demo. A real film should run 7–9s per shot.
  - Title uses PuHui-Heavy 76px, rising character by character.
  - Layer labels use PuHui-Medium 40px with an underline that extends out.

## ⑥ Implementation notes

> After being collected into the skill (2026-10-04 v0.4): the general functions in this card's "new" section have been unified into `scripts/art-motion/engine/lib/` (names changed to the unified MO / CAM / DG / TY / CH / UI / CL / TOON); the demo film's own code is in `scripts/art-motion/engine/demos/y1_kurzgesagt/`. For the library cheat sheet and "how to pick a grammar for a passage of narration", see `references/art-motion/09-animation-grammar.md`.

- Reused from the skill:
  - `PAINT.cached`, `U.rng`: determinism
  - `RIG.smooth`: smooth a point list into a Path2D; draws the cat, the hills, the leaves
  - `the author.build/pose/details`: the author
  - `PAINT.noise`
  - the engine's segment table, transition interface, offscreen A/B buffers
- New, now unified into the library (`scripts/art-motion/engine/lib/camera.js` / `motion.js` / `typo.js`):
  - `CAM.at(keys, t)`: keyframed camera, zoom interpolated logarithmically. `CAM.zlerp` magnifies by the same factor every frame, which is what makes a scale transition a constant-speed traverse. New films use `CAM.track` for holds and call-outs (defaults: push for a gentle push, glide for a node change, pull for a pull-back; punch/slam only on an accent, hold the rest of the time); parametric segment y1's highlight defaults to a gentle push, and only `"camera": "snap"` in the spec's top-level `data` makes it a fast push.
  - `CAM.anchor`: keeps the target point sliding to frame centre while zooming.
  - `MO.bezier(x1,y1,x2,y2)`: brings AE/CSS bezier easing into code, solved by Newton's method.
  - `MO.*`: sine, quint, expo, back, elastic and so on.
  - `TY.charsIn`: character-by-character entrance.
- The demo film's own (`demos/y1_kurzgesagt/kurzgesagt.js`; `flat` is now in the library as `TOON.flat`, `layer` as `CAM.layer`):
  - `flat()`: two-tone faceting.
  - `layer(c, cam, d, fn)`: parallax layer. Translation is linear in d, scale is `z^d`, so on a deep push the far field barely moves.
  - `Y1.cat`, `Y1.bot`, `Y1.bird`: the three characters.
  - `Y1.lensAt(t)`: lens circle screen coordinates, for transition A.
- **Key architecture**:
  - The camera is determined only by global film time. Inside a transition window the engine keeps drawing the outgoing shot into the A buffer as usual, and that shot computes its own "dive in" camera.
  - So a zoom transition is always a vector redraw and never blows a 1920 bitmap up 60× into mush.
  - The transition functions (`lensReveal`, `matchCut` in `transitions.js`) only handle "how A and B combine".
- Engine changes (only in this experiment's copy):
  - any segment in `eras.js` can take `dur` (seconds).
  - beat-punch impact is off by default; only `transition.punch:true` turns it on. An explainer should not have beat-synced stutter.

## ⑦ Representative works and first-hand references

- Sample films:
  - How Are Memories Stored Inside Your Brain? (2025) https://www.youtube.com/watch?v=PqtggjVAi8M
  - Why Humanity Will Never Leave The Solar System (2025) https://www.youtube.com/watch?v=Cyl3X88KEgg
  - The Immune System Explained I (2014) https://www.youtube.com/watch?v=zQGOcOUBi6s
- Official class (transcript of easing, loops, birds, character motion):
  - Skillshare "Motion Graphics with Kurzgesagt" Part 1 https://www.skillshare.com/en/classes/motion-graphics-with-kurzgesagt-part-1/631970755
  - Part 3 https://www.skillshare.com/en/classes/motion-graphics-with-kurzgesagt-part-3/140140401
- Official behind the scenes:
  - 1200 hours per film: https://www.youtube.com/watch?v=uFk0mgljtns
  - Official self-description: https://kurzgesagt.org/what-we-do?visit=videos
- Score: Epic Mountain https://www.epic-mountain.com

## ⑧ The 3 easiest things to get wrong

1. **Turning "always moving" into everything breathing.** Measurement shows only 0.3% of the 2025 films is still time, but what moves is the environment layer and the thing currently being explained, not every element floating. Explainer shot: the subject holds still once settled, and the actions sit on narration beats; a pure atmosphere shot keeps slight ambient motion such as star twinkle and particle drift. Motion padded out with everything floating and a constant-speed slow push still reads as a PPT.
2. **Zooming with linear interpolation, or scaling up a bitmap.**
   - Linear z is slow at first then violent, and the sense of travelling through breaks. Interpolate logarithmically.
   - Scaling the previous shot's screenshot 20× turns it into mosaic. The scene itself must redraw at the larger z.
3. **A bright, busy palette, or outlining things.**
   - Kurzgesagt in 2025 is "dark ground + 2–3 glowing accents", with the glow carrying the frame.
   - Add a black outline or use a mid-brightness ground and you slide into children's picture book or corporate flat illustration.
   - Shadows use one step darker in the same hue, never grey.

---

## Review and revision (independent agent, picture only, 7/10)

Review notes and how this round handled them:
- "Cat, grass and hills have outlines, looks like a children's illustration": grass blades changed from lines to thin filled triangles; the bright edge on the hilltops pressed down to one step from the body colour.
- "The black block in the bottom left looks like dirt": foreground leaves got `blur(7px)` for depth of field, colour lifted from near-black to `#0E0631`.
- "Title disappears for one frame": changed to a 0.55s sineInOut fade out.
- "Shot 3, the cat turns from orange to black with no explanation": the orange cat stays at the author's feet as "the one you know"; above the black cat a leader line and small type "a cat you have not seen" appear first, then the identification label pops.
- "7.8s the bird intersects the robot": bird height moved to 175/225px.
- "7.1–8.0 ending is almost static": the demo film added a 4%/s slow push at the time. Practice now: put an event at the end (a fast pull-back to show the whole thing, or a dive into the next layer), then hold.
- "3.03–3.10s the pixel cat is cut in half by the lens circle": not changed. This is the normal state of the "dive into the lens" reveal.

## QA (skill `scripts/art-motion/qa.py`, 2026-10-04, final after revision)

| Shot | Window measured (in-shot seconds) | Motion area % mean/peak | Static frame-pair % | Jump frames | ms per frame mean/peak | Determinism |
|---|---|---|---|---|---|---|
| y1_s1 | 0.0–2.58 | 1.57 / 2.58 | 0.0 | 0 | 32.9 / 34.6 | ✓ pixel-identical |
| y1_s2 | 1–2.68 | 3.36 / 4.42 | 0.0 | 0 | 6.1 / 7.2 | ✓ pixel-identical |
| y1_s3 | 0.9–2.68 | 17.94 / 91.88 | 0.0 | 8 (1.04–1.28s continuous) | 11.2 / 16.0 | ✓ pixel-identical |

Transition smoke test (each transition rendered once, slowest frame): y1_s2 (k_lens) 48.3ms; y1_s3 (k_fill) 36ms

How to read it:
- **Shot 3's 8 jump frames** fall in 1.04–1.28s, one continuous stretch, exactly the middle of the 42×→1× pull-out from the robot's eye; the whole frame is scaling, so the motion-area peak is 92%. This is a designed scale transition, not a single-frame glitch.
  - The first version used expoOut; the initial slope was too steep, the first frame jumped from 42× to 15×, and both review and qa flagged it.
  - Changed to cubicInOut, peak in the middle, matching the measured shape of Kurzgesagt's "traverse push".
- **Shot 1 at 33ms per frame**: foreground leaves added `filter: blur(7px)` for depth of field, slower than 9ms before the defocus, still far below the 150ms ceiling.
- A motion area of 1.6–3.4% looks low because Kurzgesagt's micro-motion is "many small things each moving": stars, particles, tail, bobbing, pulses. In the measured 2025 films completely still time is only 0.3%, and all three shots here have 0% static frame-pairs, so it lines up; but 0% static frame-pairs only says the environment layer is moving, not that the telling is good — you still have to check whether the sampled frames turn like pages.

Re-run: `uv run scripts/art-motion/qa.py --project scripts/engine --film demos/y1_kurzgesagt --out <dir>` (the table above is from the experiment; for the re-run after collection into the skill, see the regression table in 09).

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
