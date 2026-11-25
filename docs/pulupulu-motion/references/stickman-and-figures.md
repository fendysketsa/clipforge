# Stick figures and flat characters

Path: performance
Owner: figure drawing, rig proportions, code-drawn rig rules


For films where the cast is a **stick figure or a flat cartoon body**: explainer stickmen, "what if" shorts,
character-led gags, history films with one mascot. The rig is the film — a stickman has no costume, no texture and
no shading to hide behind, so weight, timing and silhouette carry everything.

Read this when the brief has a character in it and the character has to *act*, not slide around.

## 1. Rig before you animate

Nothing else in this page matters if the character is one group of shapes being translated.

```
pelvis ── spine ── chest ── neck ── head
   │                 │                └─ brows, eyes, mouth (separate, scalable)
   │                 ├─ shoulder L/R ── upper arm ── forearm ── hand
   └─ hip L/R ───────┴─ thigh ── shin ── foot
```

- **Joints are angles over time, never translated images.** Store a pose as a table of joint angles plus the pelvis
  position and a facing flag; interpolation happens on angles.
- **Two-bone IK for arms and legs** when a hand or foot must be pinned to a point (a button, the floor). Give the
  limb a target and solve the elbow/knee angle; a straight FK leg will skate across the ground on every step.
- **Feet plant and stay planted** while the pelvis travels over them. The moment a foot slides, the character reads
  as a sticker instead of a body.
- **Facing flag** mirrored once per film at minimum: mirroring the whole rig is one line, and it re-reads a scene.
- **Accessory layer:** a hat, scarf, cape or backpack is a **child of the joint that owns it** and lags by 1–3
  frames. A scarf that starts and stops with the chest looks welded on; one that trails reads as wind.

## 2. The principles, converted into numbers

These are the animation principles that survive the removal of anatomy. Express them as frame counts, not as
adjectives.

| Principle | What it means here | Concrete |
|---|---|---|
| **Pose-to-pose** | key poses first, in-betweens after | a 8–12 pose scene: 3–4 keys, the rest interpolated |
| **Anticipation** | move *against* the action first | crouch 4–6 frames before a jump; lean back 3 frames before a slam |
| **Overshoot + settle** | pass the target, come back | snap to the extreme in 3–5 frames, overshoot ~6–10 %, settle in 2–3 frames |
| **Overlapping action** | connected parts start/stop at different times | pelvis → spine → head, each 1–2 frames behind; upper arm leads the forearm, forearm leads the hand |
| **Squash and stretch** | even one line can stretch | spine length +15–22 % at takeoff, −10 % on impact; limbs keep constant thickness |
| **Smear frames** | a limb crossing half the frame in 1–3 frames | draw one stretched directional shape for that frame instead of a pose |
| **Timing charts** | spacing = perceived weight | cluster in-betweens near the apex of a jump and at both ends of a hold; leave them wide mid-fall |
| **Arcs** | rotate, do not translate | hands and feet travel on arcs around their joint; a straight-line hand reads robotic |

Pose the whole body before you touch the face. A body in a wrong silhouette cannot be saved by an expression.

## 3. Keep it alive: snap, then hold hard

- **Snap into the extreme in 3–5 frames, then hold dead still.** Comedy and clarity both live in the hold; smooth
  8–12 frame easings feel like the character is underwater.
- **The hold is not a frozen frame** — the *camera* keeps moving, the scarf keeps drifting, the face keeps ticking.
  A hold where nothing at all changes is where a film starts to feel like a slideshow (see `render-traps.md` §
  "A long timeline that is 90 % static").
- **Never ease an entrance and then stop animating.** If your last key is at 0.6 s of a 7 s scene, 91 % of the
  scene is a still image with a caption.

## 4. The face carries the beat

An oversized head with two eyes and two brows can outact a whole limb animation.

- **Eyes and brows are separate, scalable elements.** A 2-frame brow snap (raise, drop, tilt) registers as a reflex;
  an 8-frame tween reads as slow acting.
- **Pupil shifts do the thinking.** A 6–10 px pupil move toward the thing being looked at is a whole intention.
- **Swap the drawing; do not tween the shape.** On an impact beat, replace the whole eye/brow group for 1–4 frames
  (a discrete swap reads as a reflex); reserve tweening for slow realisation.
- **One expression change per beat, not per frame.** Stacked micro-changes turn the face to mush at phone size.
- **No mouth needed** unless the character speaks on camera — brows and eyes carry surprise, dread and smugness.

## 5. Proportion and line, at phone size

- **Measured defaults from a working stickman channel** (1080×1920, 30 fps): head fill `#FFFFFF` with a
  `#141414` outline, **outline 7 px**, **limb stroke 10 px**, **head-to-body height ratio 0.42**, a rounded-pill
  torso, no fingers, and **expressions swapped as whole drawings every 1–4 frames on impact beats** rather than
  tweened. Adopt these as the starting numbers and adjust per film.
- **Head ≈ 1/5 of the frame height** in hero beats. A stickman at 1/8 of the frame is technically on screen and
  emotionally absent; this is the single most common reason a stick-figure film feels weak.
- **Thick strokes with round caps and ball joints**, one constant stroke weight for limbs, one heavier stroke for
  the torso. Varying the weight per frame makes the character look like it is breathing.
- **Silhouette test:** squint or shrink a frame to 200 px wide. If you cannot tell what the body is doing, the pose
  is wrong regardless of detail.
- **Paper-white head, ink-black limbs** is the highest-contrast pair and survives compression. Any colour you add
  goes on the accessory, not on the limbs.

## 5b. When the figure and the set are drawn by code

Everything above assumes a designed rig. If you are writing the drawing code yourself — canvas or inline SVG —
the rig rules still hold, but five layout bugs reliably turn a character film into a diagram film. None is
visible in one still; all of them are obvious on a contact sheet of twelve beats.

- **Lay every scene out in a normalised box, not in pixels.** Write one `frame(x0, y0, x1, y1)` helper that
  returns those four fractions multiplied by the canvas, and place every element from it. Motif coordinates
  hard-coded for one scene leave a 1920-wide frame ~70 % empty, which reads as unfinished, not as restraint.
- **The character must be in almost every beat.** A character-led film where the figure shows up in 3 of 12
  sampled beats is a diagram film with a mascot. Draw the figure by default and drop it only on a deliberate
  title or end card.
- **Define pose angles so 0 = hanging straight down.** With an arm vector of `(cos a, sin a)` a small angle
  points sideways out of the body and every pose reads splayed or upside-down; use `(sin a, cos a)`, and the
  same for legs, so "stand" is a small number and a raised arm is near 2 rad. This one convention fixes or
  breaks every pose at once.
- **Give the figure a contact shadow, and keep it off the frame edge.** A radial-gradient ellipse at the floor
  line under the pelvis is what glues a flat body to the ground; and clamp the figure's x to roughly ≤ 0.85 W,
  because a limb drawn at the edge is cropped in half and reads as broken anatomy.
- **Cap repetition and reserve a text band.** No motif should carry more than about one beat in eight, and
  never two beats in a row — one motif used on 13 of 110 beats is the first thing a viewer notices. Keep motif
  labels inside a safe band (top ~0.18 H, bottom ~0.82 H clear of the caption plate), and when you draw text
  inside a depicted monitor, card or panel, measure and truncate it: the drawn container's width is not the
  string's width, and it spills over the edge.

A code-drawn set also reads thinner than a generated one: flat geometry, one object, no light. When the brief
asks for "designed", generate the environment plates with an image model and animate the figure and type over
them (SKILL.md step 4) — the difference is density and light, and no amount of extra code-drawn props closes it.

## 6. A flat character in a 3D-looking world

The look that makes cheap stickman shorts look expensive: a **perspective room with soft light** around a **flat
character**.

- **Room:** floor plane plus two walls drawn to a vanishing point; a soft vignette. No texture needed.
- **Light:** one warm key on the visible faces, one cool fill in the shadows, and a **soft contact shadow under
  every object** — the contact shadow is what glues a flat character to a floor.
- **Depth of field:** reduce contrast on the far wall and blur it **once on a static layer**. Never per frame.
- **Atmosphere:** 20–60 drifting sparkle particles in one layer, plus a soft radial glow behind the subject. This
  is the cheapest signal of production value in the whole style.
- **Saturated palette.** Pale, desaturated worlds read as unfinished in this genre; keep it warm and bright.
- **Big outlined words:** 2–4 words, chunky rounded face, white fill with a thick dark outline, slight tilt, held
  ~1.5 s over continuing action. Same treatment every time so the words read as a system.

## 7. Camera rules for this genre

- **The camera never sleeps.** Micro-drift always, plus one or two long eased moves per shot. The camera is what
  keeps a held pose from looking frozen.
- **Slow and long over snappy.** 6–10 s glides, not 0.5 s whips.
- **Almost no cuts.** One continuous take per scene at most; cuts are what make imitations feel cheap.
- **Change the composition per beat.** Vertical framing used vertically: push in for the slam, wide for scale,
  tilt the floor for chaos, low angle for a countdown, tight two-shot for the twist. One horizon for a whole film
  is a slideshow with a moving camera.

## 8. The "what if" short format

The one story engine that dominates this style, and the reason those shorts hold attention:

1. **Title is a question.** "What if X happened?" — the viewer clicks to resolve it.
2. **0–3 s: state the premise.** No logo, no title card, no intro animation.
3. **By 8 s: the first consequence is already happening.** Escalation starts early and never pauses.
4. **The middle escalates the same idea** — bigger, faster, more absurd — instead of introducing a second idea.
5. **The last 5–10 s: a dry visual twist** that re-frames the answer. One snap pose, one hold, out.

Invent your own episode. Copy the shape, never the characters, the wording or the running jokes.

## 9. Verify a character film

- `ffmpeg -vf freezedetect=n=0.004:d=0.6` → **zero** holds, or every hold is a deliberate pose hold with the camera
  still moving. Report the count, the total seconds and the longest hold; "the camera moves" is not a measurement.
- **Watch a 4-frame strip per beat**, not single stills: a stick figure can look correct in one pose and broken in
  the in-between.
- **Check the extremes:** the highest and lowest frame of every action. That is where limbs detach from shoulders and
  feet leave the floor.
- **Sample the sentence the narration is speaking at that instant.** Picture and voice must agree on the same beat.
- **Look at it at 200 px wide.** If the pose does not read, it does not read on a phone either.
