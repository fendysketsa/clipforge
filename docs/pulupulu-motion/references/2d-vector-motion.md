# 2D vector characters & top-down tracks

Path: graphics
Owner: flat-vector craft and scrolling worlds


For stickman / vector-character films and aerial (top-down) shots, drawn in inline SVG
and driven by the same GSAP timeline. Everything here is a pose or a coordinate problem,
not a plugin problem — no MotionPathPlugin, no spritesheet.

## Rig a character as groups, not one path

```
.rig
  .prop      (bike / car / board)   + .wheel groups
  .riderbody
    .legs  .torso  .arms  .head     each its own <g>
```

One `<g>` per limb lets the timeline rotate joints while the whole `.rig` leans, wheelies and
tumbles. Repeating spin (wheels) = `rotation: 900`, `ease: "none"`, `duration` = the scene.

**Rotate each limb about its own joint, with `svgOrigin`.** `transformOrigin: "50% 50%"` on an SVG
`<g>` means 50 % of the padded viewBox, not of the limb — arms then swing about the middle of the
shot while the figure stays rigid, which is exactly the "no body movement" note a viewer gives you.
Pass the joint in user units instead:

```js
const HIP = "216 244", SHOULDER = "256 168", NECK = "264 150", KNEE = "200 278";
tl.fromTo(".torso", { rotation: -7 }, { rotation: 7, svgOrigin: HIP, duration: 1.2, yoyo: true, repeat: 5, ease: "sine.inOut" }, sceneStart);
tl.fromTo([".armFront", ".armBack"], { rotation: 10 }, { rotation: -8, svgOrigin: SHOULDER, … }, sceneStart + .05);
tl.fromTo(".head", { rotation: -9 }, { rotation: 6, svgOrigin: NECK, … }, sceneStart + .1);
```

Keep the joint coordinates in one `const` block beside the art so a redraw only edits numbers in one
place. A whole-`rig` lean alone is not animation: the body must keep ticking for the whole scene —
chest pitching, elbows flexing, head bobbing, knees pumping — and `duration × (repeat + 1)` has to
land exactly on the scene end or the timeline grows past the film length.

## Pad the viewBox before you animate rotation

A viewBox that hugs the art clips the figure the moment `.rig` rotates past ~30°: the DOM says
visible, the frame shows nothing, and the render looks like the character was deleted. Size the
box for the widest pose, e.g. art occupying `0 0 420 320` gets `viewBox="-190 -150 800 620"`.
The default origin for an SVG group is the viewBox centre, so a padded box also makes the tumble
spin about the middle of the shot instead of about a corner. Do not add `transform-box: fill-box`
unless you specifically want rotation about one joint.

Crash beat that reads: a **slide, not a tumble** — `power2.in` rotation of ~45–55° with a short
translation that keeps the machine near the tarmac, limbs thrown out on their own joints (arm
−80…−95°, opposite arm +70…+80°, knee ±35–45°, head −20°), dust circles scaling out at **ground
level** beside the bike, and a 2-frame accent flash (`yoyo: true, repeat: 1`), then a slow settle
rotation. Past ~90° the bike turns into an abstract stripe of fairing and nobody reads a crash.

## One art used twice: classes, not ids

Instantiate the same SVG in two scenes and every `id` inside is duplicated: `om check` fails with
`duplicate-id` and `querySelector('#x')` silently binds the first copy in the document, so the
second scene animates the wrong element. Address art by **class** (`.circuit`, `.marker`, `.lapglow`)
and scope every lookup (`scope.querySelector('.marker')`); give ids only to `clipPath`s and suffix
them per instance (`grassclip1`, `grassclip5`).

## Centring art on the page

Give the scene wrapper `position:absolute; left:0; right:0; width:100%` and the art
`position:relative; display:block; margin:0 auto`. An SVG positioned `absolute` inside a
`left:50%; transform:translateX(-50%)` wrapper has no width to centre inside, so it renders
off-frame or hard right — and throws off every x/y tween that follows.

## Top-down track without MotionPathPlugin

Sample the path once at load, then tween a proxy — the placement stays a pure function of `p`, so
any seek renders the same frame:

```js
const len = path.getTotalLength();
const pts = [];
for (let i = 0; i <= 320; i++) { const q = path.getPointAtLength(i / 320 * len); pts.push({ x: q.x, y: q.y }); }
glow.style.strokeDasharray = len + " " + len;
const state = { p: 0 };
const place = () => {
  const f = Math.min(.9999, state.p) * 320, i = Math.floor(f), k = f - i;
  const a = pts[i], b = pts[Math.min(320, i + 1)];
  marker.setAttribute("transform", `translate(${a.x + (b.x - a.x) * k} ${a.y + (b.y - a.y) * k})`
    + ` rotate(${Math.atan2(b.y - a.y, b.x - a.x) * 180 / Math.PI})`);
  glow.style.strokeDashoffset = len * (1 - state.p);
};
tl.to(state, { p: 1, duration: 10, ease: "power1.inOut", onUpdate: place, immediateRender: false }, start);
```

A circuit only reads as a circuit from above with these layers, in order: wide asphalt stroke
(~100 px), dashed centre line, kerbs, start/finish tick, marker + trail. The kerb is the cheapest
trick in vector — the same path twice, red `stroke-dasharray="26 26"` and white the same offset by
half a dash (`stroke-dashoffset="26"`), with the narrower asphalt stroke laid on top.

## Ground and speed

Put the ground strip inside the same wrapper as the figure and place it by maths, not by eye:
`ground_top = (wheel_bottom_y − viewBox_min_y) × (element_height / viewBox_height)`. Misaligned by
a few dozen pixels the vehicle visibly floats.

Two or three flat speed lines (rounded rects, ~35 % opacity) flying past carry “fast” better than
blur at 2D scale; keep them out of the caption band.

## Vehicles must read as their class at a glance

The wheels are the class signal. A thin circle with spokes and a rim reads as a **bicycle** no matter
how good the rest is, and that is the note you will get back. For a motorcycle:

- **Thick slicks:** a ring drawn as `circle` with `fill="none" stroke="#101216" stroke-width="24"`,
  plus a thin rim ring (~5 px) and a hub dot — no spokes, no wide inner disc.
- **Class cues on top of the wheels:** fairing with a wedge nose, windscreen, seat hump, upswept
  exhaust, front fork at ~15° from vertical, brake disc, and a number plate (white circle + numeral).
- **Livery is the character:** white body + blue wedge + red pinstripe for a works 500, plain blue +
  knobbly tyres for a dirt bike. Two palettes from one silhouette reads as two machines.
- **Rider above the bodywork.** Draw the rider's limbs *after* the fairing in DOM order and keep the
  torso line clear of it, or the stickman disappears into the bodywork — the whole point of the style
  is that a human shape stays legible.
- **Size:** the vehicle should span 55–75 % of the frame width. Under half the width it reads as an
  icon in a slide, not a character beat.

## Declutter rules for graphic-story frames

- **One text block per idea.** A scene headline and the narration caption saying the same thing
  ("JEREZ 1999" over a caption reading “Jerez 1999”) reads as a bug, not emphasis.
- **Art in the upper 60 %, captions in a scrim below it.** Carries for every graphic-story frame.
- `om check` reports `text-overlap` when two `<em>` highlights sit on adjacent caption lines — put
  them on one line instead of shrinking the type.

## Side-scrolling world (platformer beat, 9:16)

A journey film — walk, jump, arrive — is a camera problem, not a picture problem. Build it as **one
world with one camera number**, never as a stack of illustrated frames.

### One camera number, one placer

```js
const cam = { x: BEATS[0].cam };
const place = () => {
  props.forEach(el => el.style.transform = `translate3d(${el.dataset.wx - cam.x}px,0,0)`);
  clouds.forEach(el => el.style.transform = `translate3d(${el.dataset.wx - cam.x * 0.4}px,0,0)`);
  hills.forEach(el => el.style.transform = `translate3d(${el.dataset.wx - cam.x * 0.62}px,0,0)`);
};
BEATS.forEach((b, i) => tl.fromTo(cam, { x: i ? BEATS[i - 1].cam : b.cam }, { x: b.cam,
  duration: Math.max(.2, b.next - b.start), ease: "none", onUpdate: place, immediateRender: false }, b.start));
```

Parallax factors that read: clouds 0.4×, hills 0.62×, props 1×, characters fixed. `onUpdate` is a
pure function of `cam.x`, so any seek renders the same frame — no `Date.now()`, no per-frame state.
Characters stay at a fixed screen x and walk in place; the world does the travelling.

### Props: small local-coordinate SVGs, placed by transform

Give every prop its own element with a **local** viewBox (0,0 = its own top-left) and one `data-wx`.
Each SVG then rasters at its own size; nothing repaints the whole scene when the camera moves.

- **Ground props** sit by arithmetic, not by eye: `top = GROUND_TOP - height`. Forgetting this is the
  classic bug — house, pipe, school and crack all float in the sky because every prop defaulted to
  `top: 0`.
- Elevated props take an explicit screen top (blocks `GROUND_TOP - 300`, coins `GROUND_TOP - 420`).
- The pavement itself is one flat block plus a row of tick marks placed by the same placer; a tiled
  background gradient that moves is a paint trap (see below).

### Pixel characters

Two walk frames = two `<g>` groups **inside one `<svg>`**, `.f2 { opacity: 0 }`, swapped by
`tl.set(..., { autoAlpha })` on a fixed grid (0.26 s reads as a walk at 150 BPM). Raw `<g>` elements
directly inside a `<div>` are invalid HTML: each `<svg>` sibling then stacks **below** the previous
one, so a second copy of the character appears standing in the dirt — wrap them, or the bug looks
like a positioning error.

### Paint cost is what kills the render

`Page.captureScreenshot timed out` on this kind of film comes from the paint path, not the tweens.
Every one of these failed until removed:

- **A webfont inside SVG `<text>`.** `<text font-family="Anton">` inside an inline SVG forces the
  layer to re-raster every frame. Draw the glyph as shapes, or put the text in HTML.
- **`will-change: transform` on every prop.** Thirty promoted layers cost as much as one giant layer.
  Promote nothing and let Chrome paint small elements normally.
- **One 4400×1400 scrolling strip.** Halving its raster, wrapping it in `scale(2)`, or promoting it
  still stalls; the shape that works is many small props placed by transform.
- **A repeating gradient moved by `background-position`.** Repaints the whole band every frame.
  Flat fill plus placed tick marks.

After a stall, retry the render once or twice before redesigning anything — the same page often
renders on a second pass — but if two attempts fail, cut paint cost instead of retrying a third time.

### Captions in the sky, not at the bottom

In 9:16 the bottom ~520 px is the platform's own UI. On a side-scroller the props live low and the
sky is empty, so the caption belongs **in that empty sky** (deep ink with a light halo, or white over
a scrim) while art occupies the lower two thirds. This inverts the graphic-story rule above: flat
frames put captions in a bottom scrim, a platformer puts them where the frame is quiet.

## Scene-scale graphics: charts, globes, instruments, water

A chart, globe, barograph or ocean built from a small bitmap plate next to razor-sharp DOM type reads as a
collage at phone size (the diagnosis is in `references/design-taste.md` §3e). Build it in a `1080x1920`
`viewBox` instead — crisp at any zoom, no texture budget, and a route cannot come unstuck from the chart it is
drawn on.

### A globe turns by meridian compression, not by spinning a disc

A flat map on a rotating `<g>` reads as a steering wheel. Draw a circle plus twelve meridians as ellipses whose
semi-axis is a function of the rotation, and update them from one tweened angle:

```js
const faceMeridians = () => {
  meridians.forEach((ellipse, i) => {
    const lambda = (i / 12) * Math.PI * 2 + spin.angle;
    ellipse.setAttribute('rx', Math.max(0.5, Math.abs(Math.cos(lambda)) * R));
    ellipse.setAttribute('opacity', Math.abs(Math.cos(lambda)) > 0.08 ? 1 : 0);
  });
};
tl.to(spin, { angle: 4.2, duration: beat, ease: 'power1.inOut',
  modifiers: { angle: (v) => { spin.angle = v; faceMeridians(); return v; } } }, start);
```

The compression at the rim is what the eye reads as a sphere. Parallels are horizontal ellipses with
`rx = R*cos(lat)` and a small `ry`. An ellipse inscribed in a circle never exceeds it, so no `clipPath` is
needed — and a clip over per-frame geometry is a paint trap (`references/render-traps.md`).

### An instrument draws a live trace

Do not tilt a bitmap of a barograph; its case does not move, the pen does. Build the trace from a progress
value in a `modifiers` hook: `x` walks left to right, `y` is a baseline plus a small seeded wobble plus a
Gaussian dip per event, and the pen arm and its dot are positioned from the same last point. Coarse spacing
(10 px between vertices) keeps the per-frame string work small; the events land on the words that name them.

### Water: three phases, not a bob

A hull rocking on one sine of `y` is a bobbing sticker. Drive heave, pitch and roll off one clock:

```js
const heave = Math.sin(t * 1.05) * 26 + Math.sin(t * 2.31 + 1.2) * 8;
const pitch = Math.sin(t * 1.05 - Math.PI / 2) * 3.2 + Math.sin(t * 2.31) * 1.3;  // lags the heave
const roll  = Math.sin(t * 2.1 + 0.7) * 1.2;                                     // double frequency
```

The **quarter-phase lag** on pitch is the weight: a hull that pitches with the swell instead of after it reads
as pasted on. Give the wake, bow spray and any water covering the hull the same `heave`, or the water stays
still while the ship rises out of it.

Bands of sea move in **px per second** (20–90, near bands faster) wrapped by exactly one tile, with two copies
per row so a band can never uncover the frame edge. Seams, `stroke` outlines on closing edges and per-frame
path transforms are the traps — see `references/render-traps.md`, *Layered water*.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../SKILL.md) · [Art library index](art-motion/INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
