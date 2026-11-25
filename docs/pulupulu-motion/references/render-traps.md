# Render traps and field notes

Path: both
Owner: renderer and encoder failure modes



Every failure that produced a black frame, a stall or a silently wrong duration, with the fix that worked.

Part of the `pulupulu-motion` skill. The entry point and the gate table live in `SKILL.md`.

## Field notes (learned on a real 30 s quiz film)

- **Looping ambient motion stretches the timeline.** A `repeat: 8` coin/particle tween is the film's last child, so GSAP reports the timeline as long as that tween ends — a 54 s film rendered as 91 s with a dead tail. Bound every repeat to the film: `const loops = Math.max(1, Math.floor((END - start) / d))` then `repeat: loops - 1`, and check `duration` with ffprobe after each render. The same arithmetic bites per-limb oscillation in a rig: `duration × (repeat + 1)` must equal the scene length, or a `len/5` step with `repeat: 6` runs 1.4× the scene and quietly pushes a 60 s film's soundtrack to 62.8 s. `om sound`'s printed length is the cheapest check that the timeline is still the length you asked for.
- **Anything with a `fromTo` must start hidden in CSS.** An element whose entrance tween begins at 36 s is otherwise visible from the moment its scene appears — `opacity: 0` in the stylesheet, tween it in. Same for source lines, counters and captions.
- **Captions that also carry narration want one chunk per spoken sentence.** Split the script into the sentences the voice will actually say, synthesise each chunk separately, and give every chunk a known start: the caption and the audio then cannot drift. Keep a `fromTo` hand-over between chunks (next fades in at its start, previous fades out 0.02 s before) so the text never blinks out between lines.
- **Hand a beat over to the next one; never let the frame blink black between them.** Hiding beat *i* at `end - 0.01` while beat *i+1* turns on at `start - 0.30` leaves pure `#000` frames for the whole narration gap — at 0.5–0.6 s gaps that is a 0.2–0.3 s black strobe before every single shot, the single biggest reason a beat-driven film feels broken while `om check` stays clean and `om qa` only reports holds. Keep the outgoing beat visible until the *next* beat's `start` (`tl.set(node, {display:'none'}, next ? next.start - .02 : END + .2)`) and bring the incoming plate in 0.15–0.2 s early on top of it. **The last beat is the one everyone forgets:** hiding it at its own `end` while the render continues to the padded audio length ends the delivered film on a black frame — `om check` reports `blank-frame` at the tail, and a Shorts loop replays that black. Bind the final hide to the film length, not to the beat.
- **Keep a caption band free of art.** Falling coins and camel friezes read fine above `~1030px`; below that put a soft scrim (`linear-gradient(#0b102000, #0b1020e6)`) and keep the captions and progress bar on top of it (`z-index`), or particles cross the words.

---

## Field notes (the CLI and the render path)

- **A negative position on the timeline is silently dropped.** `tl.set(el, {opacity:1}, shot.start - 0.02)`
  does nothing when that beat starts at 0, so the first label of the film never appears — while every later
  label is fine and `check` reports nothing. Wrap every computed position in `Math.max(0, …)`.
- **Tell an image model that a background plate *is* the frame.** Asked for "a full-frame plate", the model
  returns a small painted rectangle floating on paper, which cannot fill a 1080x1920 stage. The brief has to
  say: the image fills the canvas edge to edge, the sky reaches the top edge, the water reaches the bottom,
  no border, no card, no vignette — plus the horizon height as a percentage. With that sentence the same
  model delivered four usable plates first try.

- **GSAP overwrites the element's CSS `transform`, so never centre with `translate(-50%,-50%)` on anything
  you tween.** A centred subject is a `left:50%` box with a GSAP `x`/`y`/`scale` tween on the same node:
  the first tween writes `transform: translate(...)` inline, the CSS centring is gone, and the layer jumps
  half its own width to the right — the subject slides out of frame while every still you check *before*
  the tween looks correct. Centre with `gsap.set(node, {xPercent:-50, yPercent:-50})` and tween `x`/`y`
  afterwards; those compose correctly.

- **A stale `om-chrome-*` profile in Temp makes every later render time out.** The CLI creates a fresh
  Chrome profile per run (`mkdtempSync(tmpdir(), 'om-chrome-')`) and removes it on a clean exit; a run that
  was killed leaves the directory behind. Once a few are lying around, `Page.captureScreenshot timed out
  after 15000 ms` returns on the **first** frame of every project — including `pulupulu new --template
  blank`, which is the diagnostic that separates this from a paint problem in your own page. Prove it that
  way, then `rm -rf "$LOCALAPPDATA"/Temp/om-chrome-*` (or `rm -rf /tmp/om-chrome-*`) and render again.
  Kill only headless Chrome, never `taskkill //IM chrome.exe`.
- **Paint cost has a cliff, and it is per-layer size.** The same page rendered at hero widths of 890–980 px
  and timed out twice at 1140 px. When an asset gets bigger and renders start failing, the change that
  broke it is the size, not the timeline. Stay under roughly 1000 px for a full-alpha bitmap layer and
  animate a wrapper `<div>`, not the `<img>`: animating the image itself while `will-change:transform` is
  set re-uploads the bitmap per frame.
- **A CSS `filter: drop-shadow()` on a transforming layer is the same trap in another costume.** Bake the
  shadow into the PNG at build time (silhouette from the alpha channel, offset, composited behind) and the
  shadow follows the object for free, with no filter in the page at all.

- **Page boilerplate the CLI demands.** A hand-written `index.html` must load `vendor/gsap.min.js` *and* `vendor/om.js` before the inline script, create the timeline with `{ paused: true }`, and register it: `window.__timelines = window.__timelines || {}; window.__timelines['film'] = tl;`. Missing any of the three fails `om check` with "the composition did not start" or "OM.sfx is not a function". **The registration key must equal the root's `data-composition-id`** — a timeline registered as `film` under a root named anything else raises `timeline-id` and the studio seeks the wrong object, so name both the same string in the generator.
- **Every generated scene needs its own SVG `id` namespace.** A backdrop helper that emits `<defs>` (a ground gradient, a sky gradient, a grain `feTurbulence` filter) reuses one id per scene, and eighteen scenes then ship eighteen copies of `skyGrad`: `om check` fails `duplicate-id` and every `url(#…)` reference resolves to whichever came first, so all eighteen floors render with one scene's colours. Suffix every generated id with the beat id (`skyGrad{beat}`, `floorGrad{beat}`, `grain{beat}`) and pass the beat id down into each scene helper.
- **`om render` dies with `Page.captureScreenshot timed out after 15000 ms` when the page is expensive to paint.** Large multi-stop `radial-gradient` overlays and wide `box-shadow` blurs on many elements are enough to stall the compositor on every frame. Replace the vignette with a single `linear-gradient`, cut shadows to ~`0 6px 14px`, then re-render — the same page then renders 900 frames without a miss. Stills may pass while rendering still stalls, so test with `om render`, not only `om still`. **A repeating background pattern is a third trap:** a CSS "graph paper" grid (a `background-image` gradient pair plus a `background-size` tile) repaints the whole surface every frame and stalls exactly the same way — replace it with one static `linear-gradient` or a handful of SVG lines. **An SVG filter inside a `background-image` is the worst variant of it:** a `feTurbulence` grain shipped as a data-URI tile re-runs the filter over the full surface on every repaint and stalls a page whose stills look perfect — bake the noise to a PNG tile once (`PIL`, 220 px, `optimize=True`) and reference the file instead. If that tile is blended with `background-blend-mode: multiply` it must be near-white (mean ≈ 247, sd ≈ 7); a mid-grey noise tile multiplies a cream ground down to grey, which is a silent art bug no checker reports. A render that ends in a Node stack (`at listOnTimeout (node:internal/timers…`) and leaves nothing in `out/` is this timeout, not a JavaScript bug: check paint cost before reading the tween code.
- **A full-frame transform is only a trap when it SCALES.** Verified on a 1080×1920 inline `<svg>`: a `fromTo` on `scale` stalls the renderer (`Page.captureScreenshot timed out after 15000 ms`, twice in a row, on a page whose stills were fine), while the *same* element tweened on `y` renders in five minutes — Chrome re-rasterises a vector layer on scale, and merely composites it on translate. So the camera move on the plate is a **translate**: `tl.fromTo(art, {y:0}, {y:-150, duration: beat, ease:'none'}, beat.start)`, with `.art { will-change: transform }` and `gsap.config({force3D:true})`. Keep any *scale* on the plate static in CSS (`transform: scale(1.5)`) and scale only small inner groups. **A bitmap layer is exempt from the whole trap:** an `<img>` panel scaled 1.00 → 1.09 across a shot, or displaced in `y`, composites without re-rasterising its pixels — so an image-based film (generated prints, photographs, captured UI) gets a real camera move back, and that is the reason to bake art to PNG instead of inlining it as SVG. Test the difference in one still before building a film on it. **Do not blame the grain filter:** removing every per-beat `feTurbulence` did not stop the stall; consolidating the eighteen per-beat grain filters into one film-wide noise tile is still worth doing for paint cost, but it is not the fix. Use `ease:'none'` for camera moves inside a shot — an eased push leaves a still tail the QA reads as dead time. Also: a `repeat: -1` tween makes the timeline length infinite; compute a finite repeat (`Math.floor(END/dur) - 1`) or the render silently grows past the audio (a 87 s film became 117 s).
- **The QA motion and still metrics compare frames downscaled to roughly 96×54 greyscale, so only large-area, high-contrast movement registers.** A 46 px plate translate over five seconds, drifted background blobs at 1.1:1 contrast, grain jitter and small inner-group bobs all score as nothing however alive they feel at 1× — that is why `still for ≥1 s` and `flat opening` survive a film that visibly moves. Move area, not detail: a full-plate translate of 150 px per shot plus one wide high-contrast event at the open (a 1200 px line-clear flash bar) took one film from 28 held stretches and a failing opening to 10 stretches with `flat opening` cleared. Score the fix with `pulupulu qa` on the delivered file, not by eye.
- **Webfont text inside inline SVG is a fourth trap, and the worst one.** `<text font-family="Inter">` inside an `<svg>` forces Chrome to re-raster that layer every frame while the font resolves; a 21-scene film with one `39 ft` chip per scene rendered zero frames in 8 minutes and timed out, then rendered in 4 minutes once every SVG `<text>` was replaced by an HTML `<div>` overlay positioned at the same coordinates. Rule: **cheap to keep — SVG for shapes, HTML for words.** Strip SVG text mechanically (`re.sub(r"<text[^>]*>.*?</text>", "", svg, flags=re.S)`) and emit a `.lab { position:absolute; transform:translateX(-50%) }` div per label; CSS `font-weight:900` gives the same look with none of the cost.
- **HTML labels do not inherit an SVG element's rotation.** Moving words out of `<text>` into absolutely positioned `<div>`s gives up the transform stack: a card tilted `rotate(-3)` leaves its headline level and off-register. Either keep the label's container unrotated (correctness beats a 3° tilt) or apply the same `rotate()` to the label about the same origin — and re-open the frame after any resize, because label coordinates are absolute while the card scales from its own box.
- **`om still --out <path>` writes a single PNG at that exact path when `--at` holds one time, and a directory of `index-<t>s.png` when it holds a list.** A later `ls .om/frames/` then fails with "Not a directory" and the still looks missing. Name the out path explicitly when sampling one time; use the directory form when sampling several.
- **One still per scene is not enough when scenes share a backdrop helper.** A `railbed()`/`canyon()` helper added to fix “too sparse” scenes left `closed` drawing its rail at y = 1500 with an empty middle — visible only after sampling **every** beat's midpoint, not the four treatment frames. Build a contact sheet of all beats (`om still --at <midpoint of each beat>`, then tile them) and read it before the render pass.
- **An HTML element inside an `<svg>` renders nothing, and nothing warns you.** Raw `<g>`/`<rect>`/`<path>` children dropped straight into a `<div>` (a cloud layer, then a whole scene) produce a black frame, a clean console and a passing `om check`. Any scene fragment must be wrapped in `<svg viewBox="…">…</svg>` at the point it enters the DOM; grep the generated page for `<svg class=` per scene to prove it. **Two more traps, both found on a scrolling-world film:** a **webfont inside SVG `<text>`** (`<text font-family="Anton">`) forces that layer to re-raster every frame, so draw the glyph as shapes or put the text in HTML; and **`will-change: transform` on every prop** costs as much as one giant layer, because thirty promoted layers have to be composited separately. One huge scrolling strip (4400×1400) stalls no matter how you scale or promote it — the shape that renders is many small elements placed by transform (recipe: `references/2d-vector-motion.md`, *Side-scrolling world*). **Retry the render once or twice after a stall before redesigning** — the same page often renders on a second pass — but kill the **headless** Chrome instances a failed run left behind first, and only those — never `taskkill //IM chrome.exe`, which closes the user's own browser: on Windows run `powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | Where-Object { $_.CommandLine -match '--headless' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"` then a short sleep: a dozen orphans from earlier stalls compete for the same CPU and reproduce the identical timeout on a page that otherwise renders. If two attempts still fail after that, cut paint cost; do not spend a third attempt.
- **Render one still per scene, not only the four treatment frames.** Absolutely positioned blocks (`top: 520px` and friends) drift into each other as copy changes — a progress bar ended up lying across the card above it, invisible to `om check` and to the console, obvious in one screenshot. Pull a mid-animation frame from every scene and look at all of them before spending the render pass.
- **Audio goes stale silently.** After any edit to `index.html`, re-run `om sound` before `om render`; otherwise the render logs `no soundtrack` and writes a silent MP4. If a render still lands without audio, mux it: `ffmpeg -i out/film.mp4 -i assets/sound.wav -c:v copy -c:a aac -b:a 192k -shortest out/final.mp4`.
- **Build the composition from a generator script** (`build_film.py` writing `index.html`) when the film repeats a layout N times: rounds stay identical in structure, copy lives in one table, and a failed experiment is a one-line revert instead of hand-edited HTML. Write the CSS/JS in the generator as plain strings and substitute only small data tables (`json.dumps`), never as f-string bodies — a stray `{{ }}` left over from f-string style is a `SyntaxError: Unexpected token '{'` that costs a whole render pass. **Re-run `om fonts add <family> <dir>` after every regeneration:** the generator rewrites `<head>`, so the `@font-face` block the CLI injected is gone, `om check` returns `font-not-shipped` again, and the render falls back to a system face — read the check after the last build, not after the first.
- **Render filenames increment** (`film-v1`, `-v2`, `-v3`…), they are not overwritten: mux `$(ls -t out/*.mp4 | head -1)` rather than naming the expected file, or the mux dies on a path the renderer never wrote.
- **`OM.music` takes a product *or* a style, and the vocabularies differ.** `product` accepts only `devtool, ai, hardware, consumer, cute, creative, game, data, explainer, calm, guofeng, hype`; a sound name such as `cinematic`, `synthwave` or `piano` belongs in `style:`. `om sound --list` prints both lists. Passing a style as the product fails with `unknown product "cinematic"` and writes no soundtrack — check the `om sound` header line, not just that it exited 0.
- **Never name the film file from an id already used in another scene** — duplicated SVG art duplicates its `id`s; see `references/2d-vector-motion.md` for characters, aerial tracks and the declutter rules, and `references/topic-fit.md` for which subjects this pipeline can carry at all.
- **Silence the layout linter where the design is intentional:** `data-layout-allow-overflow` on mask-reveal containers (`overflow:hidden` is the reveal) and `data-layout-allow-occlusion` on full-frame transition veils.
- **`om qa` calls every thinking hold dead time.** On a quiz/trivia format the hold while the viewer reads the options *is* the format; answer it with a countdown pop per second plus a soft light sweep, and accept the remaining `still for ≥1 s` note instead of adding motion that fights the idea.
- **`om qa` and `om sound` are advisory, not gates.** They flag flat energy and missing contour; a drop on the final scene (`OM.music({ drop: 'scene:round5' })`) lifts the peak ~2.5 dB and is usually the cheapest fix.

---

## Traps that render nothing and report no error

These cost a whole review round on a real film. Every one leaves `check` green and the timeline looking
correct; only a frame that fails to change reveals them.

- **A duplicated function declaration silently wins.** A scripted patch replaced a function body but left the
  old one behind as a second `function wiggleShake(...)`; the later declaration overwrote the fix, so the
  defective version is what ran. After any scripted replacement, `grep -c "function <name>"` must return `1`.
- **A fade with no `duration` is a 0.5 s tween.** `tl.to(mat, { opacity: 0 }, at + 0.55)` overlaps every pass
  starting before `at + 1.05` and crushes its opacity back toward zero, so passes 2..N of a repeating effect
  render at about zero and look "invisible for no reason". Always pass `duration` explicitly on fades.
- **SVG elements have no `scale`.** `tl.fromTo(circle.scale, ...)` tweens `undefined`: the tween sits in the
  timeline, does nothing, and the element never pulses. Animate `attr: { r }` instead.
- **A sprite loop outlives its shot.** `loops: 14` on a foam sheet kept spawning cells 4.8 s into the next
  shot, filling a neighbour's frames with the previous scene's spray. Give `play()` a `cutoff` (the shot's
  `off` time) and break out of the loop past it.
- **Argument order is invisible at the call site.** `impactFlash(tl, at, 0.6)` reads like "strength 0.6" but
  the signature was `(tl, at, x, y, strength, size)`, so every bloom pinned to `x = 0.6`, the right slope,
  instead of the vent. When a helper takes more than three positional arguments, take an options object.
- **A shot that ends before its track does leaves orphans.** Layers vanished at `shot.end` while the audio ran
  to the timeline end, so the last 1.3 s was a stray smoke puff on blank paper. The final shot's `off` is
  `END + 0.3`, never its own `end`.
- **A grade applied as an alpha wash over the canvas is the wrong mechanism, and a multiply grade can stop the render.** `gl_FragColor = vec4(uTint, uMix)` with normal blending lifts the black point, so ink turns muddy brown and cream paper turns taupe — the film looks desaturated exactly where it should be most dramatic. Grade by multiplying instead; `THREE.MultiplyBlending` then **fails the renderer** with `THREE.WebGLState: MultiplyBlending requires material.premultipliedAlpha` and the page is rejected at `0.00s` while `check` stays green and a still renders fine. Set the factors explicitly (`blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.ZeroFactor, blendDst: THREE.SrcColorFactor`), which is a true `dst = src * dst`. Mechanism and palette: `references/design-taste.md` §5.

## Layered water: three traps a ship test exposed

- **A closed path has a vertical edge where it closes, and that edge slides into view.** A wave band drawn
  once per row and animated by one row leaves the shape's closing edge inside the frame, which reads as a
  diagonal seam through the sea. Draw the wave far past both frame edges (say -2400 to +2400) so the seam is
  unreachable, or use a repeating background tile.
- **Do not transform a huge SVG path per frame.** `setAttribute('transform', ...)` on a 4800 px wide path
  forces Chrome to re-raster the whole path area on every screenshot and the render dies with
  `captureScreenshot timed out`. Put the wave in a `background-repeat: repeat-x` tile on a div and move the
  div with `translate3d` — that stays on the compositor.
- **Water that does not cover the hull reads as hovering.** A side-view boat cut-out shows its whole rounded
  bottom; a floating boat shows a straight waterline. Cropping the PNG flat at the waterline (in PIL, before
  the render) costs nothing at runtime and fixes it permanently. An overlay "water in front of the hull" layer
  works too, but it doubles the paint and, worse, it has to follow the heave or the hull rises out of it.

## Build traps: stale inlining, splicing, and a clip that repaints

- **A build that inlines another file must inline it on every build.** A scene lived in its own `.svg` and a
  one-off patch pasted it into the page template; every later edit to the `.svg` was ignored by the build and
  the film rendered old geometry while the file on disk looked correct. Read the include at build time
  (`re.sub(r'<svg id="scene".*?</svg>', lambda _m: open(svg).read(), template, flags=re.S)`) and never paste
  content into the template by hand as a one-off.
- **Two `re.sub` calls whose offsets were both measured on the original string corrupt the second region.**
  Splicing by index (`s[:a.start()] + new + s[a.end():]`) changes every later offset, so the second splice
  cuts the wrong span and silently deletes whatever lived there — in one case two whole scene groups. Splice
  one match at a time and re-search, or replace by a unique anchor string. Assert the match count on every
  scripted replacement (`assert s.count(old) == 1`); an unmatched replacement that reports success is how the
  same defect survives a review round.
- **`clip-path` on a group whose contents change every frame is a paint trap.** Clipping forces a re-raster of
  the whole clipped area per screenshot: a globe whose meridians were recomputed each frame inside a clipped
  group died with `captureScreenshot timed out`, and the same page rendered once the clip was removed. Keep
  animated geometry inside its container by construction — an ellipse inscribed in a circle never exceeds it,
  so no clip is needed — and cap expanding radii at the container's edge.

## Two silent JS failures worth remembering

- **A `const` read inside a function that runs before its declaration is `NaN`, not an error.** `top: NaNpx`
  is an invalid value, so the element silently stays at its static position and the layer appears to be
  missing. Call the builder after the constants exist, or pass them in.
- **Assets with transparent padding break positional intent.** A foam PNG whose streak sits in the middle of a
  transparent 720x240 canvas cannot be placed by its top edge; crop to the alpha bounding box first, then
  position. Budget a re-render for every placement fix, because the visual gap is only visible in a frame.

## Long films: past two minutes it is a different pipeline

Five minutes at 30 fps is 9000 frames; seven is 12400. Nothing here is a new trap, but the arithmetic that is
survivable at 30 s becomes fatal at this length, so the order changes.

- **Render a 20 s slice end to end first** — intro plus one beat, picture and audio muxed — and watch it. The
  pipeline defects that appear at frame 7000 are visible at frame 300 if you look there first.
- **Stream frames into ffmpeg; never leave the PNG sequence on disk.** A full 1080×1920 sequence at this length
  is tens of gigabytes, and a disk that fills mid-render writes a truncated MP4 that still looks like a film.
  Keep PNGs only for the stills you are going to inspect.
- **The source render is not the deliverable.** A 5–7 minute vertical film renders at roughly 230–320 MB. That
  is the master, not the thing you send; never re-encode the master repeatedly to shrink it — make one delivery
  encode and one preview, both from the master.
- **Sizing that works for a chat hand-off**: master 1080×1920 `-crf 23 -preset medium` lands at 125–136 MB for
  5–7 minutes; a 720×1280 `-crf 31` preview lands at 12–17 MB; when that is still too heavy, 640×1138 `-crf 32`
  lands near 13 MB. Send the preview, keep the master on disk, and say where it is.
- **Never probe or review a file the encoder is still writing.** `ffprobe` answers `moov atom not found` and a
  half-written MP4 reports an inflated size, so the honest sequence is: wait for the process to exit, or sample
  the size twice ten seconds apart and require it to be unchanged. Judging a growing file wastes a whole round
  on a defect that does not exist.
- **A long timeline has no room for a static stretch.** Two seconds of stillness that read as a beat in a 20 s
  film is two seconds of dead screen here; every shot needs one continuous motion and the last minute needs the
  biggest event, or the film reads as a slide deck at 4× speed.

## How long will this take, and why is it slow

A render that runs for half an hour turns into a conversation about time. Answer it with arithmetic, and put
the arithmetic up front instead of waiting for the question.

- **Instrument the renderer at build time.** Print `frame i/N` plus a rolling seconds-per-frame every 60 frames.
  A renderer with no counter forces you to infer progress from file growth, which is wrong in both directions:
  `+faststart` holds the file near zero until the end, and a resume/segment writer jumps in steps. **File growth
  is not a progress meter**; a printed counter is the only honest one, and adding it costs four lines.
- **Identify the stage from the command line, not from a process count.** `tasklist | grep -c ffmpeg` reports
  two processes for one encode on a machine with package-manager shims (`C:\Users\…\scoop\shims\ffmpeg.exe`
  launches the real binary and both carry the same image name), and it looks like two encoders racing for one
  output file — a corruption bug that is not there. Read the actual argv before concluding anything:
  `powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='ffmpeg.exe'\" | ForEach-Object { $_.CommandLine }"`.
  That also tells you which stage you are watching: segment rendering, concatenation, or a final grading pass
  over the whole master (scale + crop + noise + CRF) — and the last one is slow and grows the file several-fold,
  which is normal rather than a runaway encode.
- **Give an ETA before the long render starts, measured, not guessed.** Frames = `duration × fps` from the
  timeline. If it is going to exceed a few minutes, say so with the two numbers that explain it (frames, and
  what each frame costs), and repeat it only at milestones — do not make the person ask, and do not answer with
  "still running".
- **When asked why it is slow, measure in one call rather than explaining.** Three readings decide it:

```sh
# 1. throughput: bytes gained over a fixed interval
a=$(stat -c %s out/picture.mp4); sleep 45; b=$(stat -c %s out/picture.mp4)
echo "$(( (b-a)/1024/1024 )) MB per 45 s"
# 2. where the CPU actually goes, per process
ps -eo pid,etimes,time,comm | grep -E 'python|ffmpeg|node'
# 3. the real denominator
python -c "import json;d=json.load(open('assets/timeline.json'));print(d['duration']*30,'frames')"
```

If accumulated **Python** CPU time dwarfs ffmpeg's, the per-frame compositing is the bottleneck and the encoder
is idle waiting on it — that is a different fix (simplify the composite, pre-bake layers) from an encoder-bound
render. Say which one it is.

- **Per-frame cost is set by what the frame is made of, not by resolution alone.** Measured on the same machine:
  flat vector or pixel-art frames are cheap — 8:33 of pixel art came out as 73.8 MB; **photographic, grainy
  bitmap plates are several times dearer** — 2:28 of them reached 105–114 MB, because high-frequency detail and
  grain are the expensive case for both the compositor and H.264. Budget wall time and file size from the plate
  type when planning, and say so in the ETA.
- **Offer the three knobs that buy time back, and say what each costs visually.** `-crf 18 → 20` (≈40 % smaller,
  much faster, invisible on a phone), **grain off** (the single biggest encoder saving), `30 → 24 fps`
  (17 % fewer frames, indistinguishable for slow camera work). Give the choice instead of silently shipping the
  slow path, and never trade frames away without saying which knob you turned.
- **Say when it is nearly done, with the projection.** Current size ÷ measured MB-per-minute against the master
  size you expect from the plan; when the file is within a minute of the expected total, say so, then report the
  gates on the finished file rather than a running estimate.

### Build the film as shots, not as one loop

The difference between a 65-minute build and a 30-minute build of the same 6-minute film was architecture, not
hardware. Two mistakes account for it, and both are the default shape if you do not decide otherwise:

- **One monolithic renderer over every frame.** 10,800 frames recomputed from scratch, each redrawing type that is
  identical on every frame of its shot. Draw each shot's typography and furniture **once** into a PNG and reuse it,
  render **shot by shot** into separate clips (content-hash the filename so only a changed shot re-renders), then
  assemble with a concat (`-c copy`) and mux the audio in the same command. Cache every clip on disk; **never
  re-render the film to fix one shot.**
- **A trailing grading pass over the whole master.** Scale + crop + noise + re-encode is a second full encode, it
  softens type through double resampling, and it is the pass that moves typography (see the drift entry above).
  Everything that must be true of the pixels must be true in the shot render. One encode.

Consequences worth building in from the start:

- **A locked composition is a held still.** `ffmpeg -loop 1 -t <dur> -framerate 30 -i shot.png` costs nothing. Hold
  **≤ 1.4 s** so `freezedetect d=1.5` stays honest, or give the shot one cheap moving element baked as a small PNG
  sequence (a specular sweep, a needle, a wheel blur) — never a per-frame recompute of the whole frame.
- **Bench the most expensive shot for 10 s and project before committing.** Measure achieved fps, multiply by the
  shot list, divide by worker count, and if the projection breaks your budget, cheapen the technique and write down
  what you traded. A measured PIL pipeline reached **~5.7 fps single-core**, which projects 11,250 frames to a few
  minutes across 10 workers on a 12-core machine — so say the projection out loud instead of waiting to find out.
- **Encoder settings that fit this:** `-preset veryfast` for shot clips, `-preset medium` only on the final concat,
  **`-crf 20`**, workers = logical cores − 1, and keep the shot list balanced — one giant shot among short ones sets
  the whole wall clock.
- **Report the cost table** in the proof document: `shot → frames → seconds → fps`, plus measured wall clock for the
  picture, the concat and the mux. It is the only way a reviewer can tell a slow technique from a slow machine.

## Delivery encodes that fail quietly

- **A preview height derived from the aspect ratio is often odd, and x264 refuses it.** `scale=720:405` (16:9 at
  720 wide) dies with `height not divisible by 2` and writes nothing, which reads as a broken encoder rather
  than a bad filter. Always let ffmpeg derive the other axis: `-vf "scale=720:-2:flags=lanczos"`.
- **`-movflags +faststart` keeps the output at ~0 bytes until the encode finishes.** The moov relocation runs at
  the end, so a preview still sitting at 0.0 MB after ten minutes is normal and `ffprobe` answers nothing about
  it. Watch the process exit, not the file size — killing a working encode and re-running it is how one preview
  costs two.
- **Never chain a syntax check in front of the render.** `node --check film.js && python render.py > log` under a
  background shell with no tty aborts on `stdin is not a tty`: the check exits 1, `&&` short-circuits, the
  renderer never starts, and the log holds nothing but the final exit code — the exact shape of a mysterious
  instant failure. Run the syntax check as its own call.

## A long timeline that is 90 % static

The most expensive defect found in a 7-minute film: the MP4 was 431 s long, decoded clean, had narration throughout,
and **355 s of it (82 %) was frozen**. The timeline was fine. The *animation* was not.

The cause is always the same shape. An entrance is eased — `easeOutCubic(local / 0.5)` — so it **saturates** after
half a second. If the last key pose is at 0.6 s of an 8 s scene, the remaining 7.4 s render the identical frame. A
second film did the same thing at 93 %: every easing reached 1.0 inside the first second, and nothing ever changed
again. Two films, two different authors, one bug.

**Diagnose with a measurement, not a viewing:**

```sh
ffmpeg -v info -i out/film.mp4 -vf "freezedetect=n=0.004:d=1.5" -f null - 2>&1 \
  | grep -oE "freeze_duration: [0-9.]+" \
  | awk -F': ' '{s+=$2; if($2>m)m=$2; n++} END {printf "%d holds, %.1f s (%.0f%%), longest %.2f s\n", n, s, s/TOTAL*100, m}'
```

Anything over ~10 % frozen, or a longest hold over ~3 s that is not a designed end card, is a slideshow.

**Two fixes, and you need both:**

1. **Give the scene a never-saturating term.** A drift that is a pure function of the scene clock and never reaches a
   limit: `breathe = 1 + 0.005 * (0.5 + 0.5*sin(local/79))`, plus a few pixels of sway on two different periods
   (`sin(local/53)*4`, `cos(local/67)*3`). Apply it to the scene container *after* the eased layers, so it cannot be
   overwritten, and expand the background fill by ~24 px so a scaled frame never reveals an edge.
2. **If the renderer de-duplicates frames, put the frame index in the key.** One renderer skipped identical frames for
   speed via `key = phase/elapsed` where `elapsed` was clamped at 17 — so it *explicitly* discarded 82 % of frames.
   `key = phase/elapsed/entry/local` plus the drift means every frame is genuinely different.

**When the drift lives in a page you cannot edit** (a design that overrides `document.body.style.transform` after your
hook), do it at encode time instead — a 2 % upscale with a sinusoidal crop is deterministic and always works:

```sh
ffmpeg -i master.mp4 -vf "scale=1104:1963:flags=lanczos,crop=1080:1920:x='12+10*sin(t/3.1)':y='12+9*cos(t/3.7)'" ...
```

That took a 93 %-frozen film to 7 % without touching the art.

**Add temporal noise at the same time, and use two drift frequencies.** A finished grading pass worth copying:

```sh
ffmpeg -i master.mp4 -vf "scale=1112:1976:flags=lanczos,\
  crop=1080:1920:x='16+14*sin(t*1.45)':y='28+14*cos(t*1.75)',\
  noise=alls=4:allf=t,format=yuv420p" -c:v libx264 -crf 19 -preset fast -movflags +faststart out/final.mp4
```

`noise=alls=4:allf=t` regenerates grain every frame, so no two frames are identical whatever the page did, and the
film reads as footage rather than as a render. Two incommensurate drift frequencies (1.45 and 1.75) mean the
wander never repeats a pattern, so a long film cannot fall into a visible cycle. Costs and caveats, both seen:

- **A drift added to stop a film feeling dead moves the typography, and that is a rejection, not a caveat.** A
data card or headline on the drifting layer shimmers sub-pixel for the whole film; the audience reports it as
"the text is wobbling" even when the picture looks alive. Measured on a rejected 6-minute cut with the
`crop=x='16+14*sin(t*1.45)'` pass below: **6.97 px mean movement per 0.2 s on the text band, 68 of 94 sampled
pairs over 1.5 px** — judged with `scripts/static_camera_audit.py --band text`. So:
  - **If the film is locked off by design, add no drift at all.** A static camera is a directing choice; the fix
    for a frozen film is *more shots*, not a moving frame. Grade only the plates if you must, and prove the type
    is still with `scripts/static_camera_audit.py --band text --max-px 0.5` (it must print PASS).
  - Only where the brief explicitly wants a live camera may the drift ship, and then it is a ±6–10 px **crop on
the picture only** with the type composited after the drift, judged at 1:1 on a text-heavy frame.
- **Scale-up-then-crop resamples twice**, so text edges soften slightly through lanczos (you upscale to 1112×1976
  only to have room to crop). Invisible on a phone, visible on a full-size frame of small type — check one before
  shipping.
- **Temporal grain forces a large file.** `+noise` at CRF 19 took a 6-minute 1080×1920 film past 400 MB against a
  56 MB pre-grade master. That is expected, not a bug: plan the delivery encode and the preview from the graded
  file, and quote the size before the encode so nobody reads it as bloat.

## Three traps measured on a 4K vertical build

All three cost real time on one film. They are cheap to avoid once named.

### 1. A Windows pipe rejects a 4K raw frame in one write

Piping `rgb24` frames into `ffmpeg -f rawvideo -i -` dies with `OSError: [Errno 22] Invalid argument` when a single
`stdin.write()` carries the whole frame — at 2160×3840 that is **24.9 MB per write**. Chunk it:

```python
CHUNK = 1 << 21                      # 2 MB
mv = memoryview(np.ascontiguousarray(frame).tobytes())
for k in range(0, len(mv), CHUNK):
    proc.stdin.write(mv[k:k + CHUNK])
```

The same code path then runs at ~7 s per 60 frames, so the trap is entirely about buffer size, not throughput.

### 2. Parallel frame rendering runs out of RAM before it runs out of CPU

A 2160×3840 float pipeline holds several copies of a frame per worker. On a machine with **2.4 GB free**, four
workers raised `numpy ... Unable to allocate 6.39 MiB` and ten raised `BrokenPipeError` (an ffmpeg child killed by
the allocator). Measure free memory before choosing worker count, and do not assume "more workers is faster":

- default to **serial** when a frame is ≥ 4K and free RAM is under ~4 GB;
- serial is cheap when shots are short — 900 frames finished in a few minutes;
- a pool of N workers needs roughly N × (frame bytes × 4) of headroom, so a 24.9 MB frame wants ~100 MB per worker
  before the compositor's own buffers.

### 3. A two-second shot with only a light pulse tests as a freeze

Two detail shots (`LED ignition`, `tail-light pulse`) animated a brightness sine and still tripped
`freezedetect=n=0.004:d=1.5` with a full **2 s hold**: measured inter-frame MAD was 0.43 and 0.38, with only
3.2–3.5 % of pixels moving by more than 4 levels. Deepening the pulse got to MAD 0.85 and still failed. What cleared
it was a **specular light sweep travelling across the subject** — a bright band crossing the frame is unmistakable
motion, it is cheap (a 1-D gaussian across a masked band), and it keeps the camera locked off because the light
moves, not the frame.

Rule: on a locked-off film, a shot whose only motion is a global brightness change is not motion. Give every shot one
element that **changes position**, even if it is only light.
