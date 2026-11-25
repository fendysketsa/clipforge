# Motion library: formats, languages, techniques, depth

Path: graphics
Owner: motion vocabulary for graphic elements



The twenty motion languages, the technique vocabulary, and what the 3D layer may and may not be used for.

Part of the `pulupulu-motion` skill. The entry point and the gate table live in `SKILL.md`.

## 7. Motion Library: Formats, Languages & Techniques

### Formats Quick-Reference
- **Launch sting (6–15 s):** Hook (0–4B) → product action (4–16B) → drop hero (16B) → payoff (20–26B) → mark (26–32B). Muted-safe, name ≥ 1.5 s.
- **Launch film (30–90 s):** Cold open on result/problem (0–5 s) → 2–4 distinct capability moments → optional non-UI spectacle → proof → mark (2–4 s). Climax at 70–85%.
- **Feature demo (10–45 s):** Context (1–2 s) → action → response → readable result. Follow §9.2 continuity.
- **Explainer (30–180 s):** Question → intuition → step-by-step mechanism (1 visual change/sentence) → payoff → whole-system recap.
- **Data story (15–60 s):** Question → baseline (bars start at 0!) → change → turning point → takeaway + source.
- **Kinetic manifesto (8–30 s):** 1 word/phrase per 1–2 beats → build → silence/break → payoff → mark.
- **Showreel (10–20 s):** ~8 sections of 1–1.3 s on one spine (colour, HUD chrome, shape, track).
- **Social hook / ad (6–20 s, 9:16):** Hook in 0.5 s → problem → product → CTA ≥ 2 s. Safe zones at 1080×1920: top 220 px, bottom 520 px, right 14%.
- **Resource list loop (8–25 s):** Title + count → numbered items (~2–2.5 s each) with chapter counter → full wall → seamless return to frame 0.
- **Loop (4–12 s):** Last frame = first frame including velocities (`om qa --loop`).
- **Step promo (15–30 s):** Problem (2–3 s) → 3–6 numbered working UI cards + progress bar → completion receipt → mark.

### 20 Motion Languages
Mix at most 3 languages in 30 s, carrying a shared spine (palette, shape, or cursor) across switches:

| Language | Says | Best for | Template / Route |
|---|---|---|---|
| `cursor-demo` | It works; here's how | Workflows, SaaS, AI apps | `blank` + §9.2 |
| `continuous-morph` | One crafted system | Consumer apps, UI states, loops | `blank` |
| `card-montage` | Step by step, real | Indie promos, step promos | `blank` |
| `kinetic-type` | Claim with conviction | Slogans, lists, hooks, endings | `kinetic-type` / `blank` |
| `modular-grid` | Precise, engineered | Dev tools, infra, fintech, specs | `blank` |
| `data-story` | Here's the evidence | Metrics, earnings, milestones | `finance-chart` / `blank` |
| `mechanism` | Why it works | AI/ML, algorithms, math/science | `math-3b1b` |
| `system-diagram` | How parts connect | Infra, APIs, agent pipelines | `blank` |
| `flat-world` | Wonder, scale | Science, health, education | `kurzgesagt` |
| `editorial-collage` | Real; look at this line | News, commentary, case studies | `vox-collage` |
| `hand-drawn` | Human, thinking aloud | Teaching, friendly brands | `whiteboard` |
| `character` | Emotion, heart | Stories, mascots, agents as actors | `storytime` |
| `3d-object` | Tangible, premium | Hardware, logos, devices, UI in space | `object-3d` / `ui-space` |
| `generative-field` | Intelligence, mood | Model launches, music, ambient loops | `blank` |
| `liquid-glass` | Premium consumer | iOS apps, photo/media | `blank` |
| `photo-led` | The real world | Travel, food, fashion, UGC ads | `blank` |
| `showreel` | Range & mastery | Capability reels, "made with X" | `blank` |
| `retro-digital` | Culture, edge | CLI tools, dev culture, games | `blank` |
| `art-styles` | Culture, delight | Showcases, unexpected direction C | `blank` (canvas/SVG) |
| `talking-head` | Real person behind it | Founders, creators | `talking-head` |

### Techniques Vocabulary & Rules
- **Timing & Easing:** `expo.out` (0.5–0.9 s) for arrivals (sfx at ~35% where it visually lands); `OM.spring(0.08)` UI / `OM.spring(0.25)` playful / `OM.spring(0)` damped; `power2.inOut` for camera moves only; `linear` for tickers/drifts/rotations only; anticipation (2–6% reverse move 0.1–0.15 s prior); stagger (30–60 ms UI, 15–25 ms letters); exits faster than entrances (0.25–0.4 s `power2.in`).
- **Entrances:** Mask reveal (`overflow:hidden`, `yPercent: 110 -> 0` `expo.out`), scale from 0 on spring, SVG `stroke-dashoffset` draw-on, deterministic `type-on` (`Math.floor((t - t0) * cps)`), `clip-path` wipe. **Avoid `blur-in`** as a generic entrance. **Never** animate `left`/`top`/`width`/`height` (animate `x`, `y`, `scale`, `rotation`). An SVG `<g>` target also needs `transformOrigin: "50% 50%"` (`transform-box: fill-box`), or a `pop`/`stamp` scale paints from `(0,0)` and the element flies in diagonally. Physics: overshoot for things arriving in air; something that lands on a surface accelerates (`power2.in`) and locks with a 4 px recoil — `back.out` bounces it back through solid ground.
- **Continuity devices (prefer over cuts):** Shared element box morph, UI pill/card morph, flood-and-contract (0.3–0.35 s overscale), nested reveal (pull back from result into editor/app), path-follow, match cut, whip (0.15–0.25 s + `--blur`), colour-field flip, collapse into the mark. **Avoid crossfades** between scenes.
- **Camera (`OM.camera('#world')`):** `cam.to(tl, t, { fit: '#el', pad: 120, duration: .8, ease: 'expo.inOut' })`, push in, pull back, screen-studio zoom (1.6–3×), linear drift (3–6% during holds — no dead frames!), parallax, camera shake (2–6 px decaying 0.2 s via `OM.random(seed)`). Never reverse direction mid-scene.
- **Typography:** Variable font weight/width animation, scale slam (140–200% → 100%), word-by-word on beat, kerning squeeze, pill highlight (0.3 s L→R), text reel, strike-through & replace, punctuation as character, type as mask container.
- **UI & Data:** Cursor choreography (hover ×1.55, press −15% + ripple), prompt receipt on screen, chat-bubble stack, completion receipt (`6/6`, 100% ring), split compare, count-up with `tabular-nums`, bars from zero, price anchor flip.
- **Finishing:** Motion blur (`om render --blur`), 60 fps (`data-fps="60"`) for fast UI, seeded grain (3–6% opacity), HUD chrome / chapter counter (`01/08`), editor-on-screen keyframes. **Use particle bursts / glow sparingly** (only on 1–2 major hits or light-emitting terminals).

---

## 8. Depth & 3D (`OM.space` & `OM3`)

**Field notes from a 2D-cut-out-on-3D-stage film (paper theatre).** Cut-outs work in space exactly like the
reference plates: one transparent plane per layer at its own `z`, one continuous camera, type left in DOM.

**Working recipe (validated at 1080×1920).** A copyable starting page lives at
`templates/paper-theatre.html` — copy it, swap the assets, keep the numbers until a still gives you a reason
to move them. Three layers per shot, bottom-anchored, one camera for the film:

| layer | z | size | bottom (`y`) | stays |
|---|---|---|---|---|
| back plate | −6 | 9.6 tall / 5.2 wide | −3.4 | fills the frame, owns the horizon |
| mid subject | 0 | 3.3 tall or 2.2–3.2 wide | 0 | the character or machine the beat is about |
| front detail | +2.5 | 1.2 tall or 1.4–2.4 wide | −0.7 | slips past frame edges, sells the parallax |

**Size each layer on the axis that matches its shape.** A portrait cut-out (a standing person, ~0.85:1) is
sized by height. A wide subject — an island at 2.35:1, a wave, a ship, a strip of stilt houses — must be
sized by **width**, with the height derived from the asset's own pixel aspect (`h = w × px_h / px_w`) in the
builder. The same number that frames a character makes an island span the entire frame and swallow the
horizon behind it, and the shot reads as a mountain range instead of an island in a strait.

Cut-out material: `MeshBasicMaterial({ map, transparent: true, toneMapped: false, depthWrite: false,
`alphaTest`: 0.02 })`. Without `alphaTest` the transparent margin still writes depth, and a nearer layer
punches a rectangular hole in the one behind it.

Camera: `OM.space(stage.camera, {fov:30})`, `target [0, 1.1, 0]`, `distance 10 → 9`, `yaw ±5`, `pitch ≈1`.
Per shot a lateral dolly (`target x +0.8 → −0.7`, `sine.inOut`) is enough — the layers separate on their own.
Entry: the layers arrive at different speeds (`back z −8.4 → −6`, `mid y −1.2 offset`, `front x +1.6 offset`),
which is the whole point of putting paper in space. Textures: plates 760 px wide, cut-outs 520 px long side.
Show/hide with `tl.set(node, {visible})`, never a `tl.call` — callbacks fire on playback and leave every
sheet visible when the playhead is scrubbed or sought.

Four things cost a whole session and are not obvious:

- **`fov` on `OM3.stage` is VERTICAL (three.js default), and the visible height at a layer is not
  `0.536 × distance` in practice once pitch and `OM.space` framing are applied.** Do not compute sizes from
  theory. Calibrate once: put every layer's bottom edge at world `y = 0` (the camera target projects to the
  frame centre, so a bottom edge at the target's height lands at 50 % of the frame), then adjust ONE global
  factor on the **widths** (heights follow each asset's aspect) and render a still. Two iterations
  converge; arithmetic does not.
- **Texture size is the paint cliff in WebGL.** Nine planes at 1024² stalled `Page.captureScreenshot` at
  1080×1920 three renders in a row; the same page with backdrops at 760 px and cut-outs at 520 px rendered
  first try. If a WebGL page stalls, shrink the textures before touching the camera.
- **Turn off what flat art cannot use:** `dof: null` (bokeh on a flat cut-out is invisible and is the most
  expensive pass) and `shadows: false` (a shadow map under paper buys nothing). Those two flags plus smaller
  textures were the difference between a stall and a 16 s render.
- **Drop `OM3.cyc(…)` and `OM3.lights(…)` entirely when every layer is an unlit `MeshBasicMaterial` plane.**
  The studio sweep is then the only lit mesh in the scene: it costs a full lit pass on every frame and buys
  a background the plates already cover. On a six-shot film, shrinking the textures was not enough — two
  renders still stalled until the cyc and the lights were removed, after which the same page rendered first
  try. Lights only matter to the meshes that shade; count them before assuming they are free.
- **`data-om-signature="off"` on the film element.** Without it the renderer stamps a `Made with …` mark in
  the corner of the last frame — which is exactly the kind of credit text a client deliverable must not
  carry.
- **One label element per beat.** Three beats tweening the same `#lab` node leave it blank on a scrub: the
  last `opacity` set wins for whichever beat the playhead happens to cross. Create one node per beat and
  toggle each with `tl.set`.

When a depth direction is chosen, **the whole film lives in space** (every stretch has a camera move in space; transitions fly through layers, pull back to a wall, or rack-focus; flat is only a rare 1-beat contrast or `flat: true` landing).

- **CSS 3D (`--template ui-space`):** Sharp live DOM text, pickable pieces, `OM.space('#world', { fov })`. Pitfall: a page world flattens if any ancestor between `#world` and a layer has `overflow != visible`, `filter`, `opacity < 1`, or `mix-blend-mode` — put those on the layer itself.
- **Three.js (`--template object-3d`):** Extruded real SVG logos, device screens, GLBs, lighting & DOF (`vendor/three.min.js` + `vendor/om-three.js`).
  - `OM3.stage(canvas, { background, env: 'studio'|'room'|'x.hdr', exposure, fov, dof: { aperture: 0.002, maxblur }, bloom, fog, units: 'px' })`
  - `OM3.lights(stage, { span })` · `OM3.cyc(stage, { color, y, depth, radius })` (photo-studio sweep so there's no black void)
  - `OM3.logo(svg, { size, depth, bevel, color, metalness, roughness })` (extrudes real SVG in its own colours)
  - `OM3.screen(img, { width, aspect, bezel, depth, radius, body, glass, crop: [l,t,r,b] })` (unlit screen keeps exact UI colours)
  - `OM3.gltf('x.glb')` · `OM3.texture(url)` · `OM3.read(url, type)` (XHR/blob-safe for `file://`; export `.glb`, not multi-file `.gltf`)
  - `OM3.film(stage, tl, duration, cam, update)` · `OM3.region(id, object, stage, label)` · `OM3.ready(promise)`
- **Strong camera moves:** Swing reveal (close oblique yaw 40–55° → `expo.out` 1.5–1.8 s), Orbit drift (yaw 10–25° `sine.inOut` during holds), Push to detail (`fit` 0.9–1.3 s `expo.inOut`), Crane pull-back (distance ×1.5–2, pitch +15–25°), Snap (0.3–0.5 s on a beat), Land (`flat: true`). Never spin without a target or let a dark slab back fill frame 0.

---

### 9. Turntables — the 360° image sequence

A turntable is N sprites of the same object at equal angle steps, shot once and then driven by frame index.
It is the cheapest way to give a product a real third dimension without a 3D pipeline, and it fails in four
predictable ways. Check a set before you wire it in — `python scripts/turntable.py <dir> --turn-seconds 6`.

**What a good set looks like.** Equal step, no duplicated sprite, a loop seam that steps like any other step,
a cut-out alpha channel, and — the one people forget — the object actually centred on its rotation axis.

**The four checks, with real numbers from a 20-frame motorcycle set (18°/step, 2520×1420 RGBA):**

| check | good | what a bad one does | the set above |
|---|---|---|---|
| step size | even per-pixel difference across the set | one near-zero pair = a duplicated frame and an invisible stall; one outlier = a dropped or mis-ordered frame | MAD 17.9–36.7, mean 24.1 — even |
| loop seam | the last→first step matches the other steps | a duplicate pair stops dead at the wrap, a jump snaps | 28.6 — inside the range, loops clean |
| alpha | a real cut-out, >1 % fully transparent | object baked into a plate, cannot be placed on your own background | 65.9 % transparent, 18.7 % opaque |
| **axis** | centroid steady within ~2 px | the object **walks across frame** as it turns | **x drifts 162.5 px, y 51 px** — this one walks |

**Fixing axis wander.** Do not re-centre on the bounding-box centre: a motorcycle is much narrower head-on
(1876 px) than side-on (2413 px), so the bbox centre moves by design. Pin a *physical* anchor instead — the
front-wheel contact patch, or the bbox centre-bottom — and translate every frame so that anchor stays fixed.

**How many sprites you need.** At fps F a full turn in T seconds holds each sprite `F·T/N` video frames.
Below ~3 reads smooth, 3–6 slightly steppy, above 6 reads as stop-motion. At 30 fps with 20 sprites:

| full turn | sprites/s | video frames per sprite | reads as |
|---|---|---|---|
| 8 s | 2.50 | 12.0 | stop-motion |
| 6 s | 3.33 | 9.0 | stop-motion |
| 4 s | 5.00 | 6.0 | slightly steppy |
| 3 s | 6.67 | 4.5 | slightly steppy |
| 2 s | 10.00 | 3.0 | smooth |

So a smooth 6-second reveal needs **60 sprites, not 20**. If the source only has 20, either turn in 2 s, turn in
steps and own the stop-motion look deliberately, or add motion blur / a smear frame between sprites.

**Ways to use the sequence besides a full spin.** With frame index as the only input, all of these are cheap:

- **hero hold then turn** — hold the money angle 1–2 s, then one full turn on a beat
- **scrub to angle** — jump to a chosen sprite on a cut; reads as a new camera angle, not a rotation
- **ping-pong** — bounce between two angles; hides the fact that you have few sprites
- **jitter accent** — step ±1 sprite on a hit; a riff, not a rotation
- **whip cut** — cut between sprites 8 steps apart with a smear; reads as a fast whip pan

**Compositing.** Transparent RGBA means the turntable sits on any plate: add a contact shadow ellipse under the
anchor, a mirrored 12–18 % reflection below it, and a rim light that stays fixed in screen space — the light
must not rotate with the object, or the illusion breaks.

**Where the frames come from, and the rights.** Manufacturer sites often expose a `d-slider-360` widget whose
`data-image-urls` list points at the original masters; pull those rather than the CDN-resized versions. Those
images are the manufacturer's property: fine as reference, and for a promo you were commissioned to make for
that product, but publishing needs their approval. Log the source URL per frame and say so in `MANIFEST.md`.
