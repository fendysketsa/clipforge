# Motlab integration — 20 November 2026

## Result

Motlab is integrated into **generated story videos** (`long_animate`), reusing
ClipForge's existing approved keyframes/footage, Hypit narration script, measured
TTS timeline, captions, branding, audio assembly, checkpoints and review gates.
Its renderer becomes the default when the operator has not explicitly selected
another engine. Existing `remotion` and `ffmpeg` selections remain supported.
Article Presenter/Hypit Quick continue using their existing renderer.

Actual sample exports with original vector illustrations and Indonesian neural
narration:

- [Full HD portrait — 1080×1920, 15.8 seconds](demo/ryuundy-motlab-1080x1920.mp4)
- [Portrait preview — 540×960](demo/ryuundy-motlab-540x960.mp4)
- [Landscape — 960×540](demo/ryuundy-motlab-960x540.mp4)
- [Representative Full HD frames](demo/fullhd-contact.png)
- [Representative landscape frames](demo/landscape-contact.png)

These demonstrate the compositor. They are not an automatically published or
production-QC-approved story. The sample's words are projected inside measured
Edge sentence windows; this is not a forced-alignment claim for each word.

## Analysis of Motlab

Source: [staryone/motlab](https://github.com/staryone/motlab), reviewed commit
`aabf482162a39ec1faef755f427a585f55713e76`, with the separately inspected npm
package **@motlab/cli 0.3.0** and its locked dependencies.

The useful part for ClipForge is its deterministic canvas `renderAt(t)` contract,
in-browser WebCodecs encoding and local media decoding. Motlab composes authored
graphics and supplied media; existing ClipForge providers still produce the
people, places, images and performances. The software requires Node 24+.
Its advertised comparative speed is not adopted as a production guarantee.

The npm package's core renderer, motion helpers, runtime and footage decoder
match the reviewed source after line-ending normalization. Its Chrome discovery
predates the repository's Playwright fallback. ClipForge therefore supplies the
explicit browser executable already installed in the backend image. No upstream
dependency is patched at startup. See `upstream-code-check.json`.

## Implemented creative behavior

- A single frame clock governs picture, caption and motion. Captions are drawn
  once after picture compositing, so a dissolve cannot fade/double the dialogue.
- Camera movement follows each shot's existing framing and subject placement;
  close-up zoom remains bounded. Authored headings settle after their entrance.
- Landscape can use an editorial split; portrait retains space for the picture,
  caption and platform controls. Empty headings remain empty, and internal
  production labels do not become viewer copy.
- Explicitly authored, narration-supported flows such as
  **Air → Turbin → Listrik** become persistent connected objects. Droplet,
  rotating turbine and electricity tokens reveal on available speech/caption
  anchors. Unknown labels stay literal; missing/reordered/negated source support
  suppresses the diagram. No statistics or causal relationship is invented.
- The story-planning prompt can request such a diagram for an actual explained
  process. It does not force diagrams onto emotional/story passages.
- Existing footage retains its playback speed; outgoing picture handles can
  freeze after the source ends. The final duration and geometry must match the
  measured narration before the renderer succeeds.
- `render_experiment` records renderer variant and a stable recipe hash for the
  existing upload/performance fields. CTR, first-30-second retention, average
  view duration and subscriber conversion can be compared after publication
  within matched formats/series. No view increase is claimed from these demos.

## Integration and readiness

- `backend/motlab_story_renderer.py`: renderer preflight, supported-flow planning,
  project assembly, heartbeat progress, encoded-output validation and experiment
  metadata.
- `backend/motlab/scene.mjs`: local deterministic canvas compositor. Narration and
  authored copy are JSON data, not executable scene code supplied by articles.
- `backend/motlab/render.mjs`: version-checked Motlab wrapper, one worker, H.264,
  cancellation/timeout and local rendering.
- `backend/remotion_story_renderer.py`: shared manifest preparation keeps the
  same script, assets, frame boundaries, overlaps, captions and branding for both
  engines.
- `backend/long_animate.py`: engine dispatch, readiness before TTS/image work,
  truthful renderer metadata and existing master-audio/QC assembly.
- Docker uses Node 24 and installs Motlab from its committed npm lockfile with
  lifecycle scripts disabled. No agent setup or separate activation is needed.
- The source manifest covers the Motlab wrapper, scene and package lockfile;
  startup checks verify the installed version. `/api/generation/rendering`
  exposes the capability contract used by normal readiness checks.
- Existing operator settings, publication holds and remote upload identity are
  not rewritten. Render failure blocks completion rather than silently falling
  back to an incomplete output.

## Verification

**257 focused tests passed** across the new renderer, Remotion compatibility,
Long Animate, Article Presenter, Hypit Quick, Compose/readiness and the preceding
reference/theme work. Python compilation, Node syntax/version checks and
`git diff --check` passed. See `regression-results.xml`.

Actual render and media checks:

- All three demo exports contain **474 H.264 frames at 30 fps**, exactly 15.8
  seconds, plus AAC narration. The scripts were checked by the actual Hypit CLI.
- All 1,422 exported demo frames decoded successfully; zero black frames were
  detected. Representative encoded frames were visually inspected in both
  orientations.
- Seeking a canvas to 7.3s, then 2s, 12s and back to 7.3s produced identical hashes
  at 7.3s. Adjacent encoded caption glyph masks changed by about 1–2% from codec
  edges, with the same cue geometry.
- Chromium played the Full HD MP4 to 15.8s with 474 decoded frames, **zero dropped
  frames** and no media error. This was muted playback; subjective listening
  approval is not asserted.
- A separate 2-second MP4 footage test passed through Mediabunny/WebCodecs and
  produced exactly 60 frames.
- The existing Remotion renderer actually exported a separate 2-second MP4
  under Node 24. The npm Motlab package was not used merely as a stub.

Evidence: `encoded-and-determinism-check.json`, `browser-playback-check.json`,
`footage-check/encoded.mp4`, `legacy-remotion-check.mp4`, and the editable demo
scripts/manifests/SVML under `demo/`.

## Runtime activation

The exact standard deployment command was attempted:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

It stopped before building because sudo requires a password. The current
backend still responds healthy, while `/api/generation/rendering` returns 404.
Therefore **source integration and local encoded examples are verified; server
activation is not verified**. See `runtime-status.json`.

The temporary Node 24 and Python test environment did not replace the host's
Node installation or persisted operator configuration. No video was uploaded,
scheduled or published during this task.
