# 33_rubberhose · 1930 rubber-hose cartoon

> Source: migration test D (an independent agent implementing straight from the read-only skill, 2026-10-04). After integration the scene code was ported to `scripts/art-motion/engine/scenes/33_rubberhose.js`.

File name at experiment time: `scenes/r2_rubberhose.js`, about 20ms per frame.

**Pipeline**: flat paper-coloured monochrome base (vertical wallpaper stripes + diamond dots, floorboard seams, watercolour darkening in the corners, cached) → sky outside the window (sun face, clouds, trees) → window frame and polka-dot curtains → chair → table (bent legs + dancing flowers) → girl → cat → `saturation` grey desaturation + multiply #f2e8d2 for the faded look → film layer.

**Key parameters**
- Beat bounce: `bnc(tq, ph) = |sin(π(tq/BEAT + ph))|`, BEAT = 60/128. Every object bounces amp pixels about its own contact point: squash on landing with sx=1+0.09k, sy=1−0.09k, stretch about 5% in the air. Phases are offset by 0.25 of a beat: table 0.5, girl 0.25, cat 0.75, sun 0; the hair bow 0.05, a little later than the body, counted as follow-through.
- Stepping: all characters and motifs use `tq = floor(t·12)/12` (on twos, on twos); lifting the cup is also stepped at 12fps; the film layer uses floor(t·24).
- Character construction: take anchor points only from the skeleton.
  - Head: a big round face of radius 82 around headC.
  - Pie-cut eye: white eye socket + black pupil, with a wedge cut out of the black pupil by arc(−1.45..−0.85); 3 lashes above.
  - Arms: a rubber hose = one quadratic Bézier from shoulder to hand, constant thickness, black outline +10px.
  - White gloves: 4 fingers, flared cuff, 3 lines on the back of the hand.
  - Polka-dot skirt down to the ankle (the demure cut).
- Cat: body via `RIG.smooth(K.bodyPts)`, mid grey #a39a84 (= the ginger), tabby #5e574b, white chest and paws #fbf7ec; the tail is a wavy rubber hose `sin(7q − 9tq)·26q`.
- Film layer:
  - Gate weave ±1.5/±2px.
  - Flicker: each frame composites white at α0.02–0.09, then black at 0–0.06.
  - Scratches: 3 vertical lines, repositioned on floor(t·6), so one scratch survives several frames.
  - 14 dust specks per frame + the occasional hair.
  - The grain layer is shifted randomly ±20px each frame.
  - Rounded film gate: roundRect r60, plus vignette.

**Motif animation**: everything bounces on the beat, the sun face's rays rotate at 1.6rad/s and the face nods on the beat, the dancing flowers (stems swinging ±0.35rad, leaves waving like hands, petals turning), one smoke ring per beat, the curtain hem swinging on the beat, film flicker and scratches. Motion area 40%, but most of it is film noise (see ② item 5).

**Pitfalls**
- The skeleton's cat body is a polyline; in a cartoon the straight edges show at once, so it must be smoothed.
- Forcing the whole frame into one colour requires a single saturation desaturation pass after the characters are drawn, otherwise the gloves and the cup keep a warm cast.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
