# GSAP plugins in a seek-scrubbed film

Path: graphics
Owner: GSAP plugin usage and seek-safe recipes


Every GSAP plugin is free since Webflow acquired GreenSock. There is no Club tier, no auth token, no
private registry. `SplitText`, `MorphSVG`, `DrawSVG`, `MotionPath`, `CustomEase`, `CustomWiggle`,
`CustomBounce`, `Physics2D`, `ScrollSmoother` all ship in the public `gsap` package. The old assumption
"the vendored `gsap.min.js` is core only, so hand-roll everything" is wrong — bundle the plugins instead.

## Bundle them at the same version

Plugin builds must match the core build (`gsap.version`). Mismatched minor versions fail silently: the
plugin registers, the tween runs, the property never applies.

```bash
V=3.14.2   # must equal the version inside vendor/gsap.min.js
for f in DrawSVGPlugin MotionPathPlugin CustomEase CustomWiggle CustomBounce SplitText Physics2DPlugin; do
  curl -sfL "https://unpkg.com/gsap@$V/dist/$f.min.js" -o "vendor/$f.min.js"
done
```

Register once, before the timeline is built, in this order after `gsap.min.js`:

```html
<script src="vendor/gsap.min.js"></script>
<script src="vendor/CustomEase.min.js"></script>
<script src="vendor/CustomWiggle.min.js"></script>
<script src="vendor/CustomBounce.min.js"></script>
<script src="vendor/DrawSVGPlugin.min.js"></script>
<script src="vendor/MotionPathPlugin.min.js"></script>
<script src="vendor/SplitText.min.js"></script>
<script src="vendor/Physics2DPlugin.min.js"></script>
```

```js
gsap.registerPlugin(CustomEase, CustomWiggle, CustomBounce, DrawSVGPlugin, MotionPathPlugin, SplitText, Physics2DPlugin);
```

Prove the bundle loaded before building anything: `typeof CustomWiggle.create === 'function'` in the page.
A missing plugin does **not** throw on `registerPlugin` — it throws nothing at all and the tween is a no-op.

## Safety triage for a paused, scrubbed timeline

The renderer never plays the timeline. It sets the playhead to `t = frame / fps`, paints, screenshots,
repeats. Judge every plugin by one question: *is its output a pure function of `time()`*?

**Safe** — writes only tweened properties on each render:

| plugin | use it for |
|---|---|
| `CustomEase` | anticipation, overshoot, snap; anything the built-in eases cannot say |
| `CustomWiggle` | impact shake, tremor, rattle — decaying oscillation without hand-built keyframes |
| `CustomBounce` | a heavy object landing, a stamp hitting paper |
| `Physics2D` | debris, spray, thrown paper — real gravity arcs |
| `DrawSVG` | a route or rule drawing on; sets `stroke-dasharray`/`offset` internally |
| `SplitText` | splitting text is a **build-time DOM change**, then the words are animated normally |
| `MotionPath` | a target following a path, incl. `autoRotate` — pure interpolation |
| `MorphSVG` | shape-to-shape; pure path interpolation |
| `Flip` | **only** if `Flip.getState()` and `Flip.from()` run in the same synchronous build, before the first seek |

**Unsafe** — depends on a live clock, a viewport, or an event that never fires in a render:

- `ScrollTrigger` — needs scroll. There is none. `scrub` never advances.
- `Draggable`, `Observer`, `InertiaPlugin` — need pointer input.
- `ScrambleText` — its reveal is driven by an internal repeat over random characters; it is a callback in
disguise and desynchronises on a backwards seek.
- `gsap.quickTo()` — pointless: it exists to reuse one tween across high-frequency input.
- `GSDevTools` — development only, never in a rendered page.

**Conditional**: `PhysicsProps` (fine, but `Physics2D` covers the same ground), `EasePack` (fine, only
`expoScale`/`slow` add anything), `ScrollTo` (no viewport to scroll).

## Recipes that earn their place

### Impact shake — CustomWiggle through `modifiers`

The wiggle ease oscillates around a line from start to end, so the target **ends displaced**. Undo it with a
finite `yoyo: true, repeat: 1` (never `repeat: -1`, which makes the timeline infinite and stretches the
film). Write the offset inside `modifiers`: modifiers are re-evaluated on **every** render, so a backwards
seek cannot leave the object frozen mid-shake — an `onUpdate` callback would not be replayed.

```js
CustomWiggle.create('omBoom', { wiggles: 9, type: 'random', amplitudeEase: 'power2.out' });

function wiggleShake(tl, node, at, ampX = 0.09, ampY = 0.05, duration = 0.42) {
  const baseX = node.position.x, baseY = node.position.y;
  const proxy = { v: 0 };
  tl.fromTo(proxy, { v: 0 }, {
    v: 1, duration, ease: 'omBoom', yoyo: true, repeat: 1,
    modifiers: { v: (v) => {
      const w = v - 1;                    // 0 at rest, oscillating while the ease runs
      node.position.x = baseX + ampX * w;
      node.position.y = baseY + ampY * w;
      return v;
    } }
  }, at);
}
```

Amplitude is in world units for a THREE object (a 3.2-unit-wide island shakes by `0.1`, not by `10`).

Use `type: 'easeOut'`, never `type: 'random'`: the random type draws from `Math.random()` when the ease is
created, so two renders of the same page produce two different shakes and a re-render can no longer be
compared against the approved cut. If you want irregularity, bake it with `OM.random(seed)` into keyframes.

### Debris with gravity — Physics2D, cell by cell

```js
debris.planes.forEach((mesh, index) => {
  const t0 = at + index * (2 / 30);       // one cell per output frame
  tl.set(mesh.position, { x: mesh.position.x, y: mesh.position.y }, t0);
  tl.to(mesh.position, {
    physics2D: { velocity: 220 + index * 30, angle: -62 - index * 12, gravity: 900 },
    duration: 0.85, ease: 'none'
  }, t0);
});
```

`velocity` is world units per second: `220` is enormous for a 5-unit frame — start at `2–4` unless the stage
is in pixel space. `angle` is degrees, `-90` is straight up. Give each cell a different velocity and angle
or the burst moves as one rigid block, which reads as a sliding image, not an explosion. Pass `friction: 0`
explicitly: the trajectory is then a closed-form function of time, and a backwards seek lands on the same
parabola.

### Route drawn on a chart — DrawSVG

```js
tl.fromTo('#leg1', { drawSVG: '0%' }, { drawSVG: '100%', duration: 1.8, ease: 'power2.inOut' }, at);
```

The element needs a real `stroke` and `stroke-width`; `drawSVG` moves the *visible segment*, it does not
animate a fill. `DrawSVGPlugin.getLength(el)` and `.getPosition(el)` give the numbers if a marker has to ride
the head — but a marker is better done with `MotionPath` (below) than by re-deriving `getPointAtLength`.

Prefer DrawSVG over a hand-rolled `strokeDasharray` + tweened-offset proxy: the hand-rolled version needs a
`modifiers` hook to survive a seek, DrawSVG's property is already a plain tweened value. Never pass
`live: true` — it remeasures the path length mid-tween, which is a layout read on every frame.

### A thing travelling a path — MotionPath on a proxy

`MotionPath` writes `x`/`y` on its target. A THREE `Group` has `position.x`, not `x`, so drive a proxy and
copy it in `modifiers`:

```js
const rider = { x: 0, y: 0, rotation: 0 };
tl.to(rider, {
  duration: 3, ease: 'none',
  motionPath: { path: '#route', align: '#route', alignOrigin: [0.5, 0.5], autoRotate: true },
  modifiers: {
    x: (v) => { boat.position.x = v / 100; return v; },
    y: (v) => { boat.position.y = -v / 100; return v; },
    rotation: (v) => { boat.rotation.z = -v * Math.PI / 180; return v; }
  }
}, at);
```

`autoRotate: true` gives the tangent angle; negate `y` because SVG `y` grows down and world `y` grows up.

### Caption revealed word by word — SplitText

```js
const el = document.getElementById(cue.id);
el.style.display = 'inline';                      // a display:none element measures nothing
const split = SplitText.create(el, { type: 'words', wordsClass: 'cw' });
el.style.display = 'none';
tl.set(el, { display: 'inline' }, cue.at);
tl.fromTo(split.words, { yPercent: 55, opacity: 0 },
  { yPercent: 0, opacity: 1, duration: 8 / 30, stagger: 3.4 / 30, ease: 'power3.out' }, cue.at);
```

**Split words are `display: inline-block`, which collapses the whitespace between them** — the caption reads
`Krakatoa hadbeen`. SplitText does not insert space nodes. Fix it in CSS:

```css
.cw { display: inline-block; will-change: transform; }
.cw + .cw { margin-left: .26em; }
```

Split after the fonts are in use, or the line breaks settle after the split and words jump on the first
frame. Animating `yPercent` on `inline-block` words keeps the line box stable; animating `y` on `inline`
text shifts the baseline of the whole line.

### Anticipation and overshoot — CustomEase

```js
CustomEase.create('omStamp', 'M0,0 C0.2,0 0.1,1.35 0.5,1.12 0.72,0.96 0.86,1.02 1,1');
tl.fromTo(label, { yPercent: 140, scaleY: 1.18 }, { yPercent: 0, scaleY: 1, duration: 0.34,
  ease: 'omStamp' }, at);
```

A CSS cubic-bezier cannot overshoot past 1 — a hand-drawn `CustomEase` can, which is most of what separates
"motion graphics" from "things fading in".

## `gsap-utils` — the four that matter

| util | why it earns its place in a film |
|---|---|
| `mapRange(inMin, inMax, outMin, outMax, v)` | one narration timeline (0–73.6 s) mapped onto camera distance, grade strength, layer scale. One source of truth, no magic numbers per shot |
| `distribute({ base, amount, from: 'start' })` | stagger config for sprite cells and words; returns a function GSAP accepts as `stagger` |
| `snap(step, v)` | snapping a playhead or a camera key to the nearest output frame so two layers cannot land half a frame apart |
| `clamp(min, max, v)` | keeping a computed position inside the safe area when the beat timings change |

`random()` is **not** deterministic across page loads unless a seed is passed — use the project's
`OM.random(seed)` for anything baked into the timeline, and keep `gsap.utils.random()` for values computed
once at build time.

## A sprite sequencer that survives a seek

The obvious build — N stacked planes, one per sprite cell, each turned on by a zero-duration `set` — works,
but costs one mesh and one texture bind per cell. A single mesh with an index driven by `modifiers` is
smaller and has fewer moving parts:

```js
const cells = FRAMES.smoke.map((f) => OM3.texture('assets/' + f.tight));
const mesh = new THREE.Mesh(new THREE.PlaneGeometry(1, 1),
  new THREE.MeshBasicMaterial({ map: cells[0], transparent: true, depthWrite: false }));
const head = { i: 0 };
tl.to(head, { i: cells.length, duration: cells.length / 15, ease: 'none',
  modifiers: { i: (v) => {
    mesh.material.map = cells[Math.min(cells.length - 1, Math.floor(v))];
    mesh.material.needsUpdate = true;
    return v; } } }, at);
```

`Math.floor` on a tweened numeric index is a pure function of time, so a cold seek and a backwards seek both
land on the correct cell. Keep the plane's visibility on the timeline (`tl.set(mesh, { visible: true }, …)`)
and clamp the terminal index or the last frames read `undefined`.

## Determinism: the same film twice

A re-render that does not match the approved cut is a bug report you cannot answer. These are the leaks:

- **`Math.random()` anywhere in the build.** GSAP reaches it from `CustomWiggle` type `random`, tween values
  like `x: 'random(-20, 20)'`, `gsap.utils.random()` with no seed argument, and `distribute({ from: 'random' })`.
  Bake the values once with `OM.random(seed)` in a fixed order, or use a fixed ease type.
- **`gsap.utils.snap(1 / 30, t)`** snaps to the *nearest* output frame. Use it so two layers cannot land half a
  frame apart; for sprite cells prefer `Math.floor(frames)` (the cell that is actually showing).
- **`distribute({ each: 1 / 30, from: 'start' })`** gives a stagger in whole frames. Hand-written `0.037`
  staggers drift off the 30 fps grid and shimmer on the first frame of an event.
- **End-time arithmetic** must include `repeatDelay`: `start + duration * (repeat + 1) + repeatDelay * repeat`.
  Getting this wrong is how a shot's visibility window closes one repeat too early.
- **`autoRemoveChildren`** must stay `false` (the default) on the film timeline, or a backward seek into an
  earlier shot finds no children left to render.
- **Camera keys** are cheapest as one pure mapping:
  `const pan = gsap.utils.pipe(gsap.utils.clamp(0, 1), gsap.utils.mapRange(0, 1, -140, 96))`, then
  `pan(progress)` — no state, no accumulation, seek-safe by construction.

## What to ignore from `gsap-skills`

The upstream repo is written for websites a human scrolls and clicks. These parts are actively wrong here:

- **`will-change: transform` everywhere.** It is a compositing hint for a live page. In a headless capture it
grows the layer count that Chrome has to composite per screenshot, and it is one of the ways a render starts
timing out. Apply it only to the few layers that really move, never as a blanket rule.
- **`gsap.quickTo()`.** Only useful for high-frequency repeated updates (mouse followers). A scrubbed timeline
  has no such input.
- **ScrollTrigger, `scrub`, `pin`, `ScrollTrigger.refresh()`.** No scroll container exists.
- **`useGSAP()` / React / Vue sections.** The page is one static HTML file with an inline script.
- **"Reduce simultaneous work / pause off-screen animations".** Everything on screen is captured every frame
  by design; the lever that matters is *texture size and filter count*, not tween count.
- **"Animate transform and opacity, avoid width/height"** — correct, but the local reason is stronger than
  jank: a layout-triggering property re-rasterises the plate and can stall the screenshot.

## Traps this file exists because of

- Tweening **`scale` as a number** on a THREE object throws `Cannot assign to read only property 'scale'`.
  Tween `scale.x`/`scale.y`/`scale.z` (`tl.to(mesh.scale, { x, y, z })`).
- **`opacity` lives on the material, not the mesh.** `tl.set(mesh, { opacity: 1 })` is a silent no-op — sprites
  stay invisible while the timeline looks correct. Always `tl.set(mesh.material, { opacity: 1 })`.
- A `RingGeometry(0.88, 1)` stroke is 12 % of its radius: scaled to 1.5 units it paints an 85 px fat band, not
  a shockwave. Use `RingGeometry(0.986, 1, 128)` and expand it past the frame.
- `registerPlugin` never reports a missing file. Assert `typeof SomePlugin.create === 'function'` in the page
  so a broken vendor bundle fails at `check`, not at delivery.
