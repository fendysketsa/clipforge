# Stickman performance — making a figure act instead of pose

Path: performance
Owner: character staging, acting, coverage and performance timing


Absorbed from `kaomei/stickman-video-director` (`b6-puppet-api.md`, `b6-actions.md`,
`b5-left-stage-motion.md`, `b3-semantic-motion.md`) and re-tested as code in this skill. Use it for
two-handers, dialogue, interviews, explainer characters, and any film whose selling point is that a stick
figure *performs*. For the drawing itself see `stickman-and-figures.md`; this page is about acting.

A stickman film fails at acting for six reasons. Every rule below exists to kill one of them.

| failure | what it looks like | the rule that fixes it |
|---|---|---|
| free-angle rig | limbs drift to angles no body holds; the "gesture" is a rotated stick | §2 authored pose vocabulary |
| linear tween | the arm slides to position and waits; nothing reads as weight | §3 action cards |
| frozen listener | the other character stands empty while someone talks | §4 the listener acts |
| dead air | gaps where nobody moves because nobody speaks | §5 authored silence |
| floating body | feet slide, hips sit on the floor line, no shadow | §6 the floor owns the feet |
| pixel motion | pixels change, meaning does not | §12 deletion test |

## 1 · Pose vocabulary before interpolation

Author the poses first, as named pairs, and never ship a limb at an interpolated angle that no pose
defines. A pose is `(upper_abs, elbow_bend)` in radians, **0° = hanging straight down**, positive swings
forward. Verified working set:

| pose | pair | reads as |
|---|---|---|
| `rest` | 0.26, 0.16 | relaxed stand — **keep a visible gap between arm and torso**, otherwise no gesture reads as a change |
| `reach` | 0.62, 0.30 | about to take something |
| `offer` | 0.92, 0.26 | holding something out |
| `receive` | 0.72, 0.52 | palm turned up, accepting |
| `retract` | 0.40, 0.26 | withdrawing, never a jump back to rest |
| `palm_out` | 1.28, 1.15 | "wait" / "calm down" — both arms |
| `point_up` | 2.18, 1.02 | making a point (fully extended 2.62/0.44 reads as a raised stick, not a point) |
| `open_low` | 0.72, 1.02 | small underhand "so…" |
| `self_point` | 1.10, 1.86 | hand to chest: "me", "my own" |
| `shrug_out` | 1.14, 1.52 | "I don't know" |
| `count_two` | 1.95, 1.15 | counting on fingers |

Rules that stopped looking broken:

- Blend toward `rest` with the **square** of the remaining envelope (`(1-blend)²`), not linearly. A linear
  blend at mid-envelope is 60 % rest and reads as no gesture at all — this alone made the first proof dead.
- One arm acts at a time unless the pose is explicitly two-handed (`palm_out`, `shrug_out`, `self_point`).
- A gesture must reach the full pose at its apex. If the silhouette at the apex is ambiguous, author a new
  pose instead of adding tween time.

## 2 · Action cards: before → extreme → result

Write every gesture as a card before writing code:

```
before   the posture and gaze that lead into the action
extreme  the single frame the audience should remember
result   what the body settles into, and what that lets the viewer read
attack   seconds from before to extreme (0.22 × duration)
hold     seconds at the extreme
release  seconds from extreme to result (0.34 × duration)
support  which foot carries the weight through all three
```

Envelope shape that works (`env()` in `scripts/stickman_rig.py`):

```python
env(t, t0, t1, attack=dur*0.22, release=dur*0.34)   # ease-out in, hold, ease-in out
```

- Attack 22 %, release 34 % leaves a real hold. Longer attacks read as drifting.
- Never keyframe a limb to arrive and stop — the release is what makes it weight.
- Gestures are timed to the **stressed syllable**, not spread evenly across the line.

## 3 · The listener acts — continuously

A listener who is not moving is the single clearest tell of a generated film. Every listener keeps:

- **gaze on the speaker** (pupil offset plus a small head turn), and looks away only when the script says so
- **nods tied to the speaker's content**, 0.45 s each, at moments you choose — not a metronome
- **weight shift** on a slow cycle (~1.8 s), deliberately out of step with the speech
- **blinks**: deterministic, 3 frames, every 2.9 s and 3.4 s for two characters so they never sync
- **hand life** at 10–18 % of a gesture pose. Above ~30 % the listener looks like they are gesturing too

Reaction latency matters: the listener responds 0.2–0.4 s **after** the trigger, not on the same frame.

## 4 · Silence is authored, not empty

A thinking beat is a directed action: eyes move first, then the head, then the body settles, and the other
character waits with a visible posture. Give it 0.8–1.0 s and put it in the timeline as a declared interval
so no gate reads it as a mistake.

## 5 · The floor owns the feet

Two numbers that broke every earlier attempt:

- **Pelvis height = `(thigh + shin) × 0.985` above the floor line.** Putting the pelvis *on* the floor line
  folds the legs below it and every frame reads as a tripod.
- **Feet stay at the world contact point** while the pelvis, shoulder and head shift for weight and lean.
  A stick figure that slides its feet is instantly fake.

Add a contact shadow ellipse at each foot (soft radial gradient, 0.4 alpha). Without it the character
floats even with correct geometry.

## 6 · Gaze, head and turn

- Pupils offset toward the partner: `±0.26 × head_radius`. Anything under ~0.15 is invisible at phone size.
- Head turn is a **rigid rotation about the neck**, ±0.20 rad, and it leads the body by ~2 frames.
- **Turning toward each other in flat 2D**: shear the whole figure above the ankle by
  `face × 0.13 × (floor_y − y)`. Feet stay planted, the head moves furthest toward the partner. This reads
  as a body angle without a second view; skip it and two characters look like they are posing for a photo.
- Expression is part of the head: brows ride the same envelope as the gesture (+0.9 surprise, −0.6 doubt),
  the mouth opens only while that character is actually speaking.

## 7 · Interruption and overlap

- An interruption = the incoming line starts **0.16–0.28 s before** the outgoing line ends. Shorter than
  0.16 s reads as a cut; longer than ~0.35 s reads as two people talking at once.
- The interrupted speaker's release is **cut short**, not finished gracefully: they stop mid-pose and their
  hand drops into the next gesture. That truncation is the acting.
- The interrupt's own gesture starts on its first stressed word, so it lands while the other is still talking.

## 8 · Camera for dialogue

- **Keep both characters in frame in every shot of a two-hander.** Dropping one out of frame to get a
  close-up hides exactly the acting you are paying for. Vary shot size and centring instead.
- **Bias the camera 30–40 px toward the current speaker** so their gesture owns the frame without a cut.
- Four shots for a 20 s exchange: wide two-shot → tighter two-shot for the argument → push-in for the quiet
  exchange → pull back for the ending. Every cut lands on a change of intent, never on a timer.
- Shot size ladder used in the proof: scale 1.34 → 1.60 → 1.70 (push) → 1.30, all with `cy ≈ 0.49 × H` so
  heads sit at about a third of frame height.

## 9 · Secondary lag

Nothing rides its driver exactly:

| part | lag |
|---|---|
| hand / wrist | 2–3 frames |
| head | 2 frames |
| ponytail, scarf, coat tail | 5 frames, plus a swing term driven by the head-angle delta |

## 10 · The deletion test

A movement earns its place only if **deleting it changes what the viewer knows**. Ask of every gesture,
nod and camera move: *what is different if this is removed?* Breathing loops, idle sway and caption changes
do not count as acting. If a beat has no answer, the beat has no performance — rewrite the beat.

## 11 · Gates

The numeric gates and their per-path thresholds live in **one** place: `references/verification.md`
(§ the gate table). Do not restate them here — run them from there, on the encoded file, not on source
frames.

Then the acting gates, which no number can pass for you — `scripts/stickman_qa.py` produces them:

- per-actor region change (changed-pixel fraction plus mean delta) for every sampled beat, with the frozen
  control that the same tool rejects
- a **frame strip per sampled beat** that you look at with your own vision and describe in words
- the three judgements kept separate: technical pass ≠ creative review ≠ user approval

## 12 · Minimal working recipe

```bash
python scripts/dialogue_voices.py --script dialogue.json --out audio/     # 2 voices, measured, overlap ledger
python scripts/stickman_rig.py --timeline audio/timeline.json --out out/  # renders 9:16 with the rules above
python scripts/stickman_qa.py out/film.mp4 --strokes 4.4,10.5,17.6 --out verify/
```

`scripts/stickman_rig.py` is the reference implementation of §1–§9 and §13 and doubled as the acceptance proof:
a 22 s two-hander, 0 freeze holds, −16.2 LUFS, both characters acting continuously.

## 13 · Limbs, hands and a set — what separates a proof from a diagram

Three details decided the quality of otherwise equal two-handers:

- **Draw the arm as a tapered stroke with a hand on the end.** A uniform-width line ending in nothing
  reads as a stick; taper it (9.5 units at the shoulder → 6 at the wrist) and put a small filled ellipse at
  the wrist. The hand is what makes a gesture *point at something*; without it `point_up` is just a raised rod.
  Same for legs: taper to the ankle, then a short foot stroke.
- **Give the two-hander a set.** A floor light pool, three wall elements at different depths (a frame, a door,
  a clock) and one or two floor props (a bag, a crate, a cup). The props are contact partners: one character
  reaches for the bag when they say they are leaving. A conversation on a blank wall has nowhere for the acting
  to happen.
- **Allow at least one hard cut.** Scale drift inside one shot is coverage, not directing. A two-shot → a
  close-up on whoever is pushing back is the cut that carries the argument. Keep both faces in shot for the
  rest; the close may crop the head, but only deliberately, framed on the eyes.
- **Name the speaker in the caption** ("SAM", "MAYA") when two characters share a frame and there is no
  dialogue audio to disambiguate. It costs one line and removes all confusion.

## 13b · Figure integrity, and the prop that must be acted on

A performance film is redrawn every frame, so a small geometry slip repeats for thousands of frames and is the
first thing a viewer notices. Check these on the frame strip, not in the code:

- **The hand is part of the limb, always.** Emit shoulder → elbow → wrist → hand from one state in one draw call.
  A hand positioned independently drifts off the arm and lands as a floating blob beside the body — the defect
  that most cheapens a finished film. When the hand lags (§9), lag the *target* the arm reaches for, never the
  hand's own coordinates.
- **Head radius is a locked per-character constant.** Never derive it from a state value or a pose. A head that
  grows in one shot reads as a broken doll, and a large head on a thin body breaks the stylisation faster than
  any missing detail.
- **Two characters in one frame never share a pose.** Identical posture, arm angle and gaze read as copy-paste.
  Differ the support foot, the idle hand, and what each is looking at.
- **A prop in frame must be acted on.** An open coffin, a lit fire, a laid table with two figures standing
  neutrally beside it is a still life with people in it. Someone reaches in, closes it, recoils from it — and
  the reaching hand is the action.
- **A caption may only name what is visible in that frame.** If the line says "cross", the cross is on screen in
  that shot; if it says "the blood", the red is in frame. Picture explaining the sentence is the rule, and
  naming an absent object breaks it more visibly than a plainer caption would.
- **Match the detail budget between plate and performer.** A photographic plate with nine props behind a
  two-line stick figure makes the figure read as a placeholder; give the figure the accessories the plate
  implies, or simplify the plate (§15 raises the same point for vehicles).

## 14 · What we deliberately did not copy

- **Hand-fitted painted cuffs, RGBA head packs, per-view neck-mount polygons.** They exist to glue procedural
  limbs onto painted raster bodies. A code-first vector rig builds sockets from primitives.
- **One approved sample as a compulsory visual target** (their Sample 1 stroke weight and caption profile).
  Keep the *method* — compare stroke and silhouette at matched head size — not the pixels.
- **A 35-subcheck acceptance package per film.** Take the applicable checks, leave the paperwork.
- **Static straight-leg-only stance.** That is a limitation of their painted cutouts; a 2-bone leg rig here
  can bend knees, so do it.
- **Hard 2.5–3 s shot caps.** Dialogue needs 4–6 s holds to let a reaction land. Use `freezedetect`, not a timer.

## 15 · Vehicles and racing

A rider, a driver or a pilot is a performer with the same grammar, but a vehicle adds a failure the figure
does not have: **a vehicle that travels at a constant pace over a static background is a screensaver.**

- **Speed is differential scroll, and it is measurable.** Move at least three layers at different rates —
  grandstand/hills slowest, barrier and run-off mid, kerb and asphalt fastest — and keep the near/far ratio in
  roughly the 3.5–5× band. Prove it by cross-correlating a background band across 6 consecutive decoded frames:
  one measured pair came out 121 px/0.2 s far against 473 px/0.2 s near — 3.9× on the straight, 4.8× at the apex.
  "It looks fast" is not the check; the ratio is.
- **The speed number must change with the action, not with the clock.** Braking 316 → 96 km/h into the apex and
  back to 224 on exit is acting; a constant 200 is a loop. Drive the engine pitch and gain from the same envelope
  as the vehicle's speed, or the sound and the picture disagree.
- **The machine has to be a machine.** Wheels rotate with enough rim and spoke to read the rotation, the fork
  compresses under braking and extends on exit, the front lifts or dives, tyre smoke and scrub exist, the chain and
  exhaust move. A fairing with two static discs under it is a sticker.
- **Match the detail budget between performer and prop.** The usual imbalance: the vehicle is drawn with fairing,
  rims, exhaust and livery while the rider's head is a blank oval. The eye then treats the *vehicle* as the
  character and the rider as luggage. Give the helmet the same care — visor line, chin bar, one livery accent —
  or simplify the machine to match.
- **Differential leaning is the acting.** Braking: body upright, arms braced, fork down. Corner: hips off the
  seat, inside knee out, head turned through the apex, lean angle changing across the beat. Exit: tuck, throttle,
  helmet down. Each is an action card (§2) with its own extreme.
- **An incident needs its recovery staged or it reads as a crash.** A vehicle left horizontal at the moment the
  audience should read as "saved it" is just a fall. Stage it in three — it steps out, knee/elbow/shoulder catches
  it, it comes upright — or cut the beat rather than shipping a fall labelled as a save.
- **A telemetry strip is a legitimate storytelling device in a short cut.** Position and phase
  (`P2 · LAST LAP · TURN 12`), speed and lap count carry stakes that no dialogue would fit in 20 s. Keep it in a
  fixed band, three or four digits values, updating with the action rather than scrolling.
- **A vehicle film needs coverage more than a dialogue film does.** One lateral stage for the whole runtime is a
  stage, not directing: cut at least once to a detail — the front wheel under braking, a low angle through the
  apex, a shot from behind on the exit. The permanent side view is the vehicle equivalent of two talking heads in
  one wide shot.
