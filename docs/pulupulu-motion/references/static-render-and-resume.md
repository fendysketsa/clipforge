# A film that renders cleanly and barely moves

Path: both
Owner: resumable and streamed rendering


Every gate can pass and the file can be technically perfect while the picture is a slideshow. This page is how it
happens, how to prove it, and the three fixes that worked on a 7-minute vertical film.

## The symptom, measured

`ffmpeg -v info -i out/film.mp4 -vf "freezedetect=n=0.004:d=1.5" -f null - 2>&1 | grep -oE "freeze_duration: [0-9.]+"`
sums the frozen spans. Two delegated builds that both looked finished on paper measured:

| build | frozen | longest hold |
|---|---|---|
| A | 354.9 s of 431 s (**82 %**) | 9.20 s |
| B | 399.9 s of 429 s (**93 %**) | 10.60 s |

A film that is 80 %+ still is not motion graphics, whatever the stills look like. Run this before delivery, not
after a rejection. `silencedetect` is the audio twin: `-af "silencedetect=n=-40dB:d=1.5"` should find nothing.

## Cause 1 — easing that saturates inside the first second

The common shape is one entrance per scene and nothing after it:

```js
const enterP = easeOutCubic(localT / 0.60);   // reaches 1 at 0.60 s
const p = Math.min(17, local - turns[phase]); // clamps at 17 frames, then constant
```

After ~0.6 s every animated value is pinned, so a 8.6 s scene is 90 % identical frames. Restraint makes it worse:
told "do not overdesign", a model removes the secondary motion first and leaves one fade at the top of each scene.
**Pair every restraint instruction with a continuity requirement**: something must move for the whole scene, not
just at its entrance.

## Cause 2 — frame de-duplication keyed on the animated state

One renderer skipped frames it considered unchanged:

```js
const key = `${phase}/${elapsed}/${entry}`;   // saturated values -> identical key
if (cachedFrame === key) { frames.push(""); }  // renderer reuses the previous JPEG
```

With `elapsed` clamped, the key freezes and the renderer *deliberately* emits 82 % duplicates. When patching the
animation, also put the frame index in the key (`…/${local}`) — otherwise a genuinely moving scene is still
sampled as static.

## Fix A — an ambient drift that never saturates

Add motion that is a pure function of the local frame and has no end state: a slow sway plus a fraction of a
percent of scale. Pure functions of `localT` keep the render seek-deterministic, which is the property the whole
pipeline depends on.

```js
const breathe = 1 + 0.012 * (0.5 + 0.5 * Math.sin(localT / 1.9));
const sx = Math.sin(localT / 1.1) * 14;
const sy = Math.cos(localT / 1.4) * 10;
stage.style.transformOrigin = "540px 960px";
stage.style.transform = `translate(${sx}px, ${sy}px) scale(${breathe})`;
```

Amplitude matters: 4 px of sway with a 2.6 s period stayed **below** the freeze detector (88 % still) — it reads
as "not frozen" to a human and as identical to a 0.4 % pixel comparison. Around 10–14 px with a ~1 s period
moved the same film to 7 %.

## Fix B — camera drift at encode time, when the page fights back

If the page's own animation is driven outside your control (or a `body` transform is reset while scene DOM is
rebuilt), stop fighting it and add the drift in the encode: scale up ~2 % and crop a window that sways.

```sh
ffmpeg -y -i master.mp4 -vf "scale=1104:1963:flags=lanczos,crop=1080:1920:x='12+10*sin(t/3.1)':y='12+9*cos(t/3.7)',format=yuv420p" \
  -c:v libx264 -preset medium -crf 18 -c:a copy out/drift.mp4
```

Measured on the 93 % build: **85 % → 7 %** frozen, longest hold 3.4 s. It costs one re-encode and a 2 % upscale;
that is cheaper than a failed delivery. Keep the master.

## Fix C — render in resumable spans when one Chrome cannot finish

A single pass over 12,930 frames died with:

```
playwright._impl._errors.TargetClosedError: Page.evaluate: Target page, context or browser has been closed
```
at scene 21 of 50, losing 21 scenes of work. Restart the browser instead of nursing it: N scenes per browser,
one segment file per span, skip a span whose segment already exists.

```python
for i, span in enumerate(spans):
    segment = SEG / f"seg_{i:02d}.mp4"
    if segment.exists() and segment.stat().st_size > 100_000:
        continue                      # a crash costs one span, not the film
    render_span(i, span, timeline, art, port)
```

Three worked settings: 8 scenes per span, `--disable-dev-shm-usage --no-sandbox --disable-gpu`, and a fresh
`chrome-span-NN` profile per span (reusing one profile is what invites the crash).

**Validate a segment; do not just look for one.** The skip test above (`exists() and size > 100_000`) accepts any
file, including one written by an earlier `--slice` experiment: 300 frames sitting where the span needs 5,520.
The span is skipped, the concat succeeds, and the delivered film silently loses its first three minutes while
`ffprobe` reports a duration short of the narration instead of an error. Send test and slice renders to their
own output directory, and gate the skip on the segment's frame count or duration matching the span (or delete
`work/segments/` after any experimental run).

**The concat gotcha that will bite you next:** paths inside a concat listing are resolved relative to the
**listing file's own directory**, not the shell's cwd.

```sh
# listing lives in work/, entries must say segments/seg_00.mp4
ffmpeg -f concat -safe 0 -i segments.txt -c copy video_only.mp4   # run with cwd=work/
```

`Impossible to open '../seg_00.mp4'` is this bug, not a missing file. Mux the narration after the concat, and cut
to the timeline length with `-t` so the last word lands with the picture.

## After the fix, expect the file to grow

De-duplication was also compression: the patched build went 13 MB → 44 MB because every frame is now unique. That
size is the film finally existing; deliver a smaller preview from it rather than reverting the motion.
