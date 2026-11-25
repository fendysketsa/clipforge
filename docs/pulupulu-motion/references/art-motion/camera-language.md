# Camera language: how to use the camera

The expansion of "The director's demand: how to use the camera" in SKILL.md. Every number on this page states **when it applies and when to ignore it**. The numbers come from measured reference films and from films the author has signed off on; they are a starting point, not a quota. If you have a better camera design, build it — then watch it once at normal speed and view it side by side with the reference.

## 1. Three questions before you move the camera

1. **Where should the audience be looking at this moment, and can they read it at this shot scale?** If they can read it, do not move. If the picture is already moving on its own (live footage, a line being drawn, a curve growing, water being poured) there is even more reason not to move — a camera move only steals the scene.
2. **Is this beat a transition or an accent?** Carrying the eye to the next place, establishing a relationship, building mood — that is a transition, use the slow one. A reveal, a reversal, a key number landing, a punchline — that is an accent, and only that gets the fast one.
3. **What was the previous camera move?** If you pushed in, find a chance to pull back out or truck sideways; do not push in shot after shot. Use the same move three times running and the audience hears the metronome.

## 2. The move table

| Move | What it is for | Reference numbers | Where the number comes from | When to ignore this number | Engine |
|---|---|---|---|---|---|
| Stop | The audience is reading, the picture is moving on its own, the silence after a punchline | Hold as long as the voice-over needs; no floor and no ceiling | Vox hold segments measure a frame delta of 0.0–0.1; 3b1b's `wait` is static | — | Write no move |
| Slow push-in | Carry the eye to the next detail, push the emotion one step forward | 0.6–1.5s, `sineInOut`; push until "the thing to be looked at is readable", commonly 10–40% | Vox pushing into a photo 1.0–1.5s, finding a card 0.5–0.9s; 3b1b's native push about 1s; Heer & Robertson 2007 recommend about 1s with ease-in-out for data transitions in statistical charts (they write about chart transitions; borrowed here as an analogy) | A large push distance (2× or more) can go to 2s; when following musical beats, follow the beat | `push` on `CAM.track` (default 0.9s), `to` |
| Pull back | Return to the whole, establish "where it is", close a section, end the film | 0.8–2s, fast start, long tail settling | Vox pulls out in about 1s; Kurzgesagt's quick pull-back reveal 0.2–2s, long tail | Scale traversal (from a cell out to the Earth) takes its duration from "④" on the y1 card | `pull` (default 1.1s, `MO.longTail`) |
| Lateral truck / find the next item | On the same wall, the same table, walk from one item to the next; follow something that moves | 0.5–0.9s, `sineInOut`; tracking along the red line 1.3–1.8s, long tail | Measured in Vox | When following a moving object, speed follows the object | `glide` (default 0.7s) |
| Fast push-in | Accent: a reveal, a reversal, a key number | 0.25–0.35s pushing in 18–32%, then stop | The numbers used on the Nobel literature film r3 when it was approved (07 card item 29, which also swapped the material and the ground colour); School of Motion's kinetic text "camera push 6 frames + 2 frames pull back" | In kinetic text (y5) the fast push is the main grammar and follows the accents; in other grammars it is the minority | `punch`; `to` with `dur: MO.PULSE.punch` |
| Whip | The eye jumps suddenly ("I open the laptop → (screen)"), comedy timing | 0.26–0.30s with motion blur | y4's whip measured at 0.26s `expoInOut` | — | `pan`, `TRANSITIONS.whip` |
| Slam in | Big type, a number, a stamp, a new frame landing | 0.17s, 1.55→0.94→1.0 | Built for real on the approved film | At most once per shot; do not slam on every cut | `slam`, `MO.slam` |
| Hard cut / jump-in | Change shot scale without a camera move: reaction close-up, jump in one step | 0 frames | y4 storytime: hold + jump in, the punchline carried by the cut | — | `cut` |
| Slow drift / constant slow push | Mood shots, art-style frames where "the painting is always alive", lyrical MV sections, emotional long takes of 5 seconds or more | 1–4%/s as a starting point | No measured approved film: these are the numbers from the y1 and y2 demonstration films (4%/s, 1%/s); used on explainer shots they were judged the old way, used on mood shots they were never rejected — when done, view it side by side with the reference | **Slow-pushing a few percent on every shot of an explainer is PowerPoint** (the film from 07 card item 29) — that usage is out | `CAM.drift`, `CAM.at` |

Move tokens as they must appear in the shot list's Camera column (the linter greps the Chinese token, so the pair is not optional): Stop / Slow push-in / Pull back / Lateral truck / Fast push-in / Slam in / Whip / Cut.

All duration constants live in `MO.PULSE`. `CAM.track` with no `kind` is a slow push-in; `pull` with no `k` exactly cancels one default slow push-in, and the most reliable way back to the whole view is to write `z: base.z`. In parametric clips (t2, y1, y2) the highlight slow-pushes by default; it becomes a fast push-in only when `"camera": "snap"` is written in the spec's top-level `data` (`{"data": {"camera": "snap"}}` — written directly at the spec's top level (the same level as `grammar`), or into one cue's `data`, it has no effect and raises no error), and then the whole clip becomes a fast push-in, so write it only for the stretch that needs the accent.

## 3. Count and density: when it is governed, when it is not

**Principle**: an accent move is bold type in an article — bold the whole piece and nothing stands out. Push-ins have to go in and come back out.

| Case | Governed? | How to judge |
|---|---|---|
| Explainers, science, finance, whiteboard, Vox-type films | Yes | Fast push-in + slam + whip at or below one third of the shot count (lint ⑯); never three push-ins in a row (lint ⑮); if the finished film's "push-in count" is 8 or more per minute, film_gate flags yellow — watch it once at normal speed |
| The first 3-second hook of a Douyin or Video Channel cut | Density not governed | The hook can be dense; return to the normal rhythm after 3 seconds |
| Kinetic text (y5), music-beat sections | Fast push-in count not governed | The camera follows the beats and the accents; the music supplies the rhythm |
| Story, comedy (y4) | Push governed, cuts not | Mostly hold + hard-cut jump-in; push-ins are rare |
| MV, mood films | Governed by the emotion | The author's words (2026-10-11): "the camera moves and the transitions both feel monotonous and dry, lacking variety, lacking emotional expression". Slow push-in and slow drift in the verse, speed up only in the chorus, pull back in the interlude, transition peaks on the beat |
| Art-style speedruns, traversal films | Push-in not governed; "is the picture alive" is | One main move per scene + 2 motif loops; the camera can drift slowly the whole time |
| 3b1b (t1) | Push governed | The camera follows the object being looked at: one `smooth` push-in of about 1s, static during `wait`; a fast push-in only when a conclusion lands |
| Keynotes, screenshot tutorials (t2) | Push governed | Screenshot at full frame; slow-push only into the part being talked about that cannot be read, once or twice per image, then pull back to the whole image or truck to the next part |
| Finance charts (t3) | Push governed | The camera holds still while the chart grows itself; slow push-in of about 1s when pointing at a data point; a fast push-in only for the one or two most critical numbers in the whole film |
| Kurzgesagt (y1) | Push governed, ambient layer not | The ambient layer can move gently the whole time; slow push-in at named nodes; dives in and pull-outs take the scale-traversal durations |
| Vox investigation table (y2), whiteboard (y3) | Push governed, truck free | One world canvas; trucking the camera between items is the main grammar and can be used repeatedly; push in for the line that has to be read, pull back out when it has been read |

**Negative yardstick**: a 2026-10-12 Nobel economics vertical short, 102 seconds, 44 shots, about 48 push-ins in the code (one every 2.1 seconds on average), every one of them pushing in, each 0.28 seconds pushing 10–26%, almost no pull-backs and no lateral trucks. The author's words: "there are an awful lot of zoom-in camera moves. Too many, and the rhythm is too fast — not smooth at all". film_gate measured about 12 push-ins per minute on this film (a lower bound — half the push-ins over live footage cannot be measured).

## 4. Real material at full frame: the trap you fall into most easily

When one shot is one full-frame photo or recording, the only thing the camera can do is push in, and the whole film becomes "cut a photo, push, cut a photo, push". That Nobel short is exactly this. Fixes:

- **If the live footage is already moving, hold still.** People walking, hands moving — stack a push-in on top and the viewer feels seasick.
- **Push into one image once or twice at most**, and only when "this part cannot be read in the wide shot". Pushing once per noun mentioned is a metronome for the voice-over.
- **Change the entrance**: pull back out of a close-up to reveal the whole; truck in from one side; hard-cut from the previous shot's landing point into the same shot scale.
- **When several pieces have to be told back to back, lay them out on the same world canvas** (`MD.print` prints laid out on the investigation table, see the y2 card), truck the camera between items, and push-ins and lateral trucks then alternate, so the back-and-forth comes for free.
- **A cut does not mean pushing in again.** Start every shot's push from 1.0 and they stack into zoom-in after zoom-in.
- **The investigation table is not material shrunk and laid out.** When the camera stops on one item, that item has to fill 80–90% of the frame (y2 card); a large expanse of tabletop should appear only in transit and in the closing pull-back. In the 2026-10-12 A/B, the cut under the new rules switched to the investigation table and push-ins fell from 15 to 8, but at rest the photo filled only half the frame width and the beige tabletop showed a lot.
- **Landscape illustration in a vertical frame: crop first, then place.** A 16:9 illustration placed whole into 9:16 leaves a single strip in the middle with empty space above and below; crop the part the voice-over is currently on into a vertical composition and build the print or the full-frame from that, keeping the whole image only for the closing pull-back. Two independent agents each hit this on the same day.

## 5. How to self-check

- Storyboard stage: `storyboard_lint.py` checks three consecutive shots with the same move (a stop does not count), three consecutive push-ins, accents above one third, and a table with no move at all.
- Finished-film stage: the "push-in count" yellow light in `film_gate.py` means there are too many push-ins — go and look; the "fast-motion frame ratio" red light means the film barely moves. Note: a slow push-in of about 20% over 1 second and a 0.28-second fast push-in score about the same on this metric (2026-10-12, three frames measured on the Nobel short: 0.28s pushing 3 frames, 1.0s pushing 4–7 frames, 2.0s pushing 3–10 frames counted as fast motion), so you do not need to speed the camera up to clear the gate.
- **You cannot judge whether camera moves flow from extracted frames.** A grid of stills only shows composition; camera rhythm has to be watched at normal speed from the top of the finished film, at least the densest 30 seconds of it.

## 6. Provenance and history

| Date | Film | What happened | Where it landed on this page |
|---|---|---|---|
| 2026-10-08 | A Nobel literature explainer, r2 → r3 | r2 pushed in 7.5% at constant speed on every shot, plus a fixed beige base, a title bar and a photo frame, and was judged "it feels exactly like running PowerPoint"; r3 changed four things at once: real footage at full frame, a dark real environment, page frames removed, hold → 0.28s fast push-in → hold, and came back "much better now, finish it and post it" | The "bad usage" note on the slow-drift row, and the source of the fast push-in row. All four were changed together, so there is no telling which one did the work; later only "a fast push-in at every voice-over node" was written up as the rule, which is the same disease — "the same move on every shot" — at a different speed. On 2026-10-12 the author looked back and said "the literature one is pretty ordinary, the physics one is not bad" |
| 2026-10-10 | Claude's Day opening, r4 | "Very good, keep going at this rhythm": a slam, a hard 0.35s pull-out into a cross-section wide, a paper-plane lateral truck, floating dust added to the stills | What was approved is a set of moves used mixed — the pull-out and the lateral truck are both in it |
| 2026-10-05 | SpaceX whiteboard | The author picked r6; r17 had 5 more push-ins than r6 (not confirmed that this is what won the author over) | To be confirmed |
| 2026-10-11 | 七里香 (Qi Li Xiang) Monet MV | "The camera moves and the transitions both feel monotonous and dry, lacking variety, lacking emotional expression" | The MV row in section 3 |
| 2026-10-12 | Nobel economics short | "There are an awful lot of zoom-in camera moves. Too many, and the rhythm is too fast — not smooth at all" | The negative yardstick in section 3, and section 4 |

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.

## 7. Locked off: the static camera, and how a still frame still moves

A static shot is not a shot with gentle movement. It is a shot where the frame does not move at all:
**movement *in* the frame, never movement *of* the frame.** What moves is the subject, the light, a needle, a
wheel — never the composition. Movement inside a locked frame lets the audience read the frame, which is why the
grammar suits products, data, diagrams and type.

The failure mode is the "living still": a 1–3 % breathing push, a handheld float, a sinusoidal crop, a Ken Burns
pan. It is always added late, to stop a film feeling dead, and it always reads as cheap — worse, it drags the
**typography** with it, so the type appears to wobble. If a shot feels dead, the answer is a cut, not a nudge.

**A locked frame does not mean a stuck film.** Coverage supplies the variety: shoot the same subject from several
positions and cut between them. Two rules decide which cuts are legal, and they are numbers, not taste:

- **The 30° rule.** Between two shots of the same subject the camera position must change by **at least 30°**,
  otherwise the cut reads as a mistake — a jump cut rather than a new angle. This bites hardest on sprite
  turntables: a 20-frame set steps **18°**, so **cutting to the adjacent sprite is a defect.** Step two sprites
  (36°) minimum, three (54°) to be safe. Twenty sprites therefore give ten usable camera positions.
- **The 180° rule.** Do not jump across the subject's axis without a bridging shot; cross only through a front or
  rear elevation, or the subject flips and the audience loses orientation.

To make a small set of angles feel like a lot without moving the camera, change the **crop** (full, half, macro),
the **placement** of the subject in the field, and the **scale** between neighbouring shots — a cut from macro to
full is a real angle change — and vary the **hold lengths** (a 3 s hero, a 0.9 s detail flash). Keep the frame
furniture identical across shots (running head, footer, a rule, a scale strip): furniture that never moves is what
makes a locked camera read as deliberate instead of dead.

**Prove it instead of claiming it.** `scripts/static_camera_audit.py <film> --band text --max-px 0.5` estimates the
global translation between sampled frames by phase correlation; grain and noise do not translate, so a truly locked
shot scores ~0. Anything over half a pixel is a moving frame.

Two ways a pair is **not** drift, and the script excludes both: it moved further than a camera could (a hard cut,
`--cut-px`), or **the correlation peak collapsed** — below `--min-peak` (default 0.5) the two frames are not the same
composition at all, which is a cut, a dissolve or a wipe. Judge peaks before you trust a translation: on a real
locked-off film the peak sits near **0.99 inside a shot** and falls to **0.02–0.35 across a cut**. Without this, a
legal cut whose two compositions happen to be positionally similar gets reported as camera drift, which is how a
correct film gets wrongly rejected.

Measured both directions on real work:

| film | band | same-shot pairs | mean / median / max | verdict |
|---|---|---|---|---|
| locked-off build, 6:15 | text | 285 (34 cuts excluded) | **0.00 / 0.00 / 0.00 px** | PASS |
| locked-off build, 6:15 | picture | 303 (16 cuts excluded) | **0.00 / 0.00 / 0.00 px** | PASS |
| rejected cut with `crop=x='16+14*sin(t*1.45)'` | text | 67 (over 1.5 px) | 6.97 px mean, 68 of 94 over 1.5 px | FAIL |

That third row is the whole reason this page exists: the sinusoidal crop was added in a late "grading" pass to make
the film feel alive, and what the client saw was wobbling typography. A locked frame is the cheap, correct answer, and
it is also the fast one — a static composition can be drawn once and held.
