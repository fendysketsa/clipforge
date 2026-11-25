---
name: pulupulu-motion
description: >-
  Use when making a motion-graphics film, launch video, explainer, data story or
  talking-head package. Directs it as editable HTML + GSAP, with local narration and
  music, and renders frame-accurately in headless Chrome. Also punches up an
  existing film. Needs Node, ffmpeg and the self-hosted `pulupulu` CLI; say so
  up front if one is missing.
metadata:
  author: "Alucard0x1"
  homepage: "https://github.com/Alucard0x1/pulupulu-motion"
  repository: "https://github.com/Alucard0x1/pulupulu-motion"
  version: "1.0"
  license: "MIT"
---

# pulupulu-motion

A film here is a **timeline in HTML** that Chrome renders frame by frame. Nothing is a video editor: you
write a page, the CLI screenshots it at a fixed frame rate, ffmpeg muxes the sound.

This file is the router. It answers: may I do this job, what do I run first, what has to pass, and which
page has the detail. Load a reference page only for the part you are working on.

## 1. Before promising anything

```sh
python scripts/doctor.py                    # read-only: python, node, ffmpeg, the CLI, key, disk
python scripts/doctor.py --project film/    # also: the page contract is present
```

Exit 1 means a film cannot be made on this machine. Do not discover that after writing scenes. Never call
`npx` per command: a network round trip on every `check`, `still` and `render` is the most common
self-inflicted slowdown in this workflow.

**This tool is the wrong choice when** the story needs footage it does not have, a real person's face or
likeness, articulated human or animal anatomy, a physical action performed continuously, or lip-sync. It
renders flat vector geometry, type, charts, maps, icons and colour-coded objects well, and those other
things badly. Say so instead of producing a lookalike: a drawn stand-in for archival material is a
provenance problem, not a style choice.

One exception to that paragraph, and it is a different route rather than a licence: an **original stick figure
performing** — a gag, a two-hander, a dialogue, a character explainer — is a solved capability here, not a
wrong choice. Take the performance route below and read `references/stickman-performance.md`.

## 2. Choose the production route — once, at plan time

Before preflight, pick **one** route, write it into the project (`PATH: performance` / `PATH: graphics`), and
do not revisit it mid-build. Two routes telling one film what to do is the failure this section exists to stop.

| route | matches when | owner |
|---|---|---|
| **Named engine** | the brief requires a specific renderer, runtime, or an executable art clip | that engine's contract; this skill supplies craft and gates only |
| **Stick-figure performance** | original stick figures are the on-screen performers — gags, demonstrations, dialogue, two-handers | `references/stickman-performance.md` (staging, acting, coverage) + `references/stickman-and-figures.md` (drawing). Render frames from code (`scripts/stickman_rig.py` or your own), not a GSAP page |
| **Material-led** | the picture is supplied footage, a real likeness, or licensed source material | that material, plus `references/credits-and-attribution.md` |
| **HTML motion graphics** | everything else: type, charts, diagrams, maps, icons, data | the page contract and the workflow in §3, motion from `references/motion-library.md` |

The routes do not mix inside one film. A performance film may carry graphic **elements** (a label, a chart
card, a balloon) drawn inside its frames; it is still a performance film. A graphics film with a mascot is
still a graphics film.

**Balloons are an overlay, not a route.** When a visible character has an audible spoken line and the brief
wants it on screen, load `references/chat-balloons.md` **after** the route owner. It owns balloon text,
geometry, clearance and timing; it never owns motion.

### When two instructions disagree, use this order

1. the explicit brief and any authorization it carries
2. the selected renderer's contract, and the delivery gates in `references/verification.md`
3. the route owner above, for production workflow
4. the named specialist page for its own field (balloons for balloons, `design-taste.md` for palette, …)
5. shared craft defaults, and `references/agent-routing.md` for model-specific review tactics

A leaf reference never changes the selected route or the gates. Sub-indexes and "read first" links are scoped
to their parent route. Start the root workflow in §3 only after the route is chosen.

## 3. The workflow, in order


One beat = one sentence = one shot. Timing comes from measured speech, never from invention.

1. **Brief.** Subject, audience, platform, language, whether there is narration. Ask for a missing subject;
   do not ask whether to narrate when a video was requested. When the request names a **channel or a video as the
   reference**, resolve it to real artefacts (oEmbed metadata, the channel's recent titles, the thumbnail in
   vision) before writing the brief: a style read off the name alone is how a whole run goes to the wrong film —
   `references/style-references.md`.
2. **Storyboard before HTML** — `references/narration-and-captions.md`. The caption is the verbatim spoken
   words, not a summary of them — and its **notation is digits**: dates, months, years, counts and versions read
   `05/1995`, `06/1997`, `1995–1999`, `ES2015`, `10 days` on screen while the voice may spell them aloud. Author
   `say` (speakable) and `caption` (screen) as two fields; gate both layers with `scripts/audit_numbers.py`. For a history, company or invention film the through-line is **one person
   making decisions**, not a list of products and dates: one beat = one decision or one consequence. A
   timeline of launches reads as a slide deck however good the art is.
3. **Narrate and measure.** `python scripts/deepseek_voice.py beats beats.json film/assets/voice.wav
   --voice stella --timeline timeline.json`, then `gate` to check every phrase by ASR. Route, voices and
   limits: `references/narration/deepseek-tts.md`.
4. **Build the page** from `timeline.json`, not from the storyboard. Contract: `references/cli.md`.
   **Every visual asset is commissioned from the image-capable agent — never draw, trace or procedurally
   paint one yourself, not even a plain background plate.** This covers the **environment**, not only the props:
   a set built from code-drawn geometry reads as flat shapes over an empty field next to films whose rooms were
   generated, and the gap is density and light, not effort. Self-made stand-ins read as stickers and come
   back as a rejection; briefing, cropping and assembly are your job, the art is not. Method:
   `references/generated-assets.md`.
5. **Check, then look — in a loop, before the long render.** `pulupulu check .`, then stills at 8–12 beats
   spread across the whole film (`pulupulu still . --at … --out .om/stills`), plus a 6-frame strip at 0.2 s
   for any beat whose whole point is a movement (`scripts/stickman_qa.py`, `scripts/review_pack.py`). A page
   that passes `check` can still render blank, and a wrong frame is not found by rendering 17000 frames
   first: judge frames, fix, judge again — the long render is the last step, never the way you discover the
   film is empty. In a character-led film, **count the sampled beats that actually contain the character
   performing an action**; a figure present in 3 of 12 sampled beats is a diagram film with a mascot, and a
   motif reused across 13 of 110 beats is the first thing a viewer notices.
6. **Render** — `pulupulu render . --format mp4 --fps 30`. Stalls, black frames and wrong lengths:
   `references/render-traps.md`. Instrument it (frames = duration × fps) and **state a measured ETA before the
   pass runs** when it will take more than a few minutes; if asked why it is slow, answer with the throughput,
   the per-process CPU split and the frame count, not with "still running" — recipe and the three speed knobs
   in the same page, § *How long will this take*.
   **Past about two minutes of film, render shot by shot with a cached clip per shot, and encode once** — a
   monolithic loop over every frame plus a trailing grading pass is how the same film takes 65 minutes instead of
   30, and that pass is also what moves the typography. § *Build the film as shots, not as one loop*.
7. **Mix and mux** with explicit stream mapping — `scripts/deliver_check.py --video out/film-vN.mp4
   --audio assets/mix.wav --out out/final.mp4` muxes *and* validates in one call. Manual recipe and the
   ducking chain: `references/workflow.md`.
8. **Validate the file you will deliver**, not the renderer's newest output:
   `python scripts/deliver_check.py out/film.mp4 --timeline timeline.json`.
9. **Deliver** with honest caveats: what is drawn rather than sourced, and what the QA note says.
   A delivered film is **English** — narration *and* every word on screen, unless the brief says otherwise
   — carries the owner's `by <owner>` watermark, and renders the licence credit for any borrowed asset or
   real person shown. Mechanics and licensing: `references/credits-and-attribution.md`.
   When the build was delegated to an external coding agent, the delivery also reports that run's token usage
   **parsed from its own log in this turn** and a rupiah conclusion at the current rate, labelled as a
   conversion at tariffs rather than a bill. A film long enough to be inconvenient travels as a sized preview
   plus the full file on disk — never as a truncated or re-compressed original.   When the full quality has to
   reach a phone, serve it and **verify the link** before sending it: Range support, an `ftyp` header, and a
   matching hash on a middle slice. Send the **page**, not the bare file — a media URL plays inline and gives a
   phone no way to save it, so serve an `index.html` with a player and a `?dl=1` download button and prove the
   button is in the response. Mechanics: `references/delivery-and-transfers.md`.

## 4. Gates

Only these block. Everything else a tool prints is a reading note: answer it with an argument or fix it,
but never report it as passed when it was not.

| gate | command | what it proves | if it fails |
|---|---|---|---|
| preflight | `python scripts/doctor.py` | the machine can render | stop, report what is missing |
| composition | `pulupulu check .` | page contract, no missing file | fix before rendering |
| language | `python scripts/lang-audit.py film/index.html --lang en` | no text in the other language, **including string literals inside `<script>`** | translate the literal, re-run |
| numbers | `python scripts/audit_numbers.py beats.json` | no month name, spelled-out number or spelled-out year survives in a caption | rewrite the caption in digits; the voice field keeps the spoken form |
| assets | `python scripts/audit_assets.py MANIFEST.md --min 10` | every scene names at least ten distinct assets and reuses none from another scene | build the missing elements, or merge the thin scenes |
| speech | `python scripts/deepseek_voice.py gate beats.json --voice stella` | every phrase transcribes back to its own words | rewrite the phrase; never ship a fragment |
| file | `python scripts/deliver_check.py out/film.mp4 --timeline timeline.json` (or `--video/--audio/--out` to mux first) | frame size, frame rate, audio present and long enough, true peak, delivery size | re-mux or re-encode |
| pops | `pulupulu qa out/film.mp4` | `no single-frame pops` | find the one-frame element |

`pulupulu qa` also reports motion per second, `still for ≥ 1 s` and `flat opening`. Those are judgements
about pacing, measured on a 96×54 greyscale comparison, so a low-contrast slow move can read as still. Use
them as a reason to look, not as a verdict to obey.

**What no gate proves:** that the film is good, that ASR heard the right number (check digits and proper
nouns as tokens), or that a caption sits where a platform's UI will not cover it.

## 4b. Seeing whether it actually moves

A still cannot show easing, weight or colour in motion, and "this scene is dead" has to be a measurement, not
an impression. `python scripts/review_pack.py --src out/film.mp4 --timeline timeline.json --strips 11.4 17.0`
writes one frame every 3 s, a triptych per beat (frame t | frame t+0.4 s | amplified difference, with the
changed-pixel count in the filename) and 6-frame strips at 8 fps — the strips are the only one of the three
that shows the shape of a movement. `measured.json` carries the numbers: a beat under ~2 % of the frame
changed in 0.4 s is a still image with narration over it.

Measure before believing a heuristic in either direction. `qa`'s 96×54 comparison misses thin-line motion
(a pulsing route read as 0.2 while 64k px actually changed), and equally, a healthy `check` hides a layer that
renders nothing.

When the pack goes to another model for judgement — or when your own third attempt has just been rejected —
the loop is in skill **`second-opinion-review`** at `second-opinion-review/references/delegated-build.md`.

## 4c. Your own bar is the one that fails

Every gate in §4 can pass on a film nobody wants to watch, because gates measure mechanics and the rejection
is about craft. The asymmetry is systematic, not bad luck: the measurable work (renderer, resume, freeze
detection, loudness) gets done and verified, while the unmeasurable work (is this frame worth looking at) gets
deferred to the end — and by then the render is done and the schedule argues for shipping it.

- **Write the craft acceptance before building, in words you can check in a frame.** Density of the set, how
  many beats contain the character, whether limbs carry a taper and a hand, whether the palette changes at
  all across the film. `references/design-taste.md` §restraint numbers and `references/stickman-performance.md`
  §13–14 exist for exactly this: copy the items, do not settle for the ones you can compute.
- **A brief you write for yourself is weaker than one written by someone else.** When the same class of film
  is also being built by a delegated agent, its output is your external standard — read the frames side by
  side, at matched size, and let it set the bar rather than defending your own. The weak brief is not only
  vaguer, it can be **factually wrong**: a spec quoted from memory instead of from the supplied file gets
  carried into the build, and only the builder's fact gate catches it. Put a verification gate in every brief
  you write, and expect it to be pointed at your own text — see `references/workflows-specialized.md` §9.2c
  when the picture is supplied.
- **Legibility of a defect is proportional to how early you look.** Three still-review rounds fixed a pose
  system that no amount of gate-reading would have caught; the same three rounds at the end would have meant
  re-rendering the film.
- **A self-made score is craft, not plumbing, and it fails review while every gate passes.** Two rejections the
  gates cannot see: a bed that is hiss-forward with no body (the listener's word is *weird*), and a bed whose only
  motion is sustained harmony (the word is *drone* — meaning nothing strikes, not that it is quiet). Both are
  measured before delivery by `scripts/score_audit.py`; the numbers that separate them, and why raising an
  instrument's gain does not rebalance a mix whose continuous voices cover every instant, are in
  `references/audio-and-music.md` §10a.

## 5. Traps that cost a render

Full detail and fixes in `references/render-traps.md`. The ones that stop a render dead:

- Raw `<g>`/`<rect>`/`<path>` written into a `<div>` renders nothing and warns nothing. Wrap every scene
  fragment in its own `<svg viewBox>`.
- A webfont inside inline SVG `<text>` re-rasterises that layer every frame. Put text in HTML, or draw it
  as shapes.
- `feTurbulence` as a per-frame filter — inline SVG *or* a CSS background — stalls the renderer. Bake the
  noise into a PNG tile once.
- A full-frame GSAP **scale** on an inline SVG re-rasterises the plate; translate composites fine, and a
  bitmap layer can be scaled. When a push is impossible, animate small inner groups.
- `repeat: -1` makes the timeline infinite: an 87 s film silently becomes 117 s. Compute finite laps.
- After a failed render, clear the stale `om-chrome-*` profiles in Temp — a few leftovers make **every**
  render time out on frame one, including the CLI's own blank template. Then kill only the **headless**
  Chrome left behind; `taskkill //IM chrome.exe` closes the user's own browser.
- Paint cost has a cliff around ~1000 px per full-alpha bitmap layer, and `drop-shadow` on a transforming
  layer costs the same as a filter per frame. Bake the shadow into the PNG, animate a wrapper `<div>`.
- **Stamp `data-om-signature="off"` on the film element.** Without it the renderer draws a `Made with …`
  mark into the last frame, and a client-facing deliverable carries no tool credit.
- **A resume key that ignores slice length ships a truncated film.** A 10 s test slice written to the same
  `work/segments/seg_00.mp4` path made the resume step treat span 0 as finished; the concat produced a film
  missing its first three minutes while every gate still passed on the file that existed. Compare each
  segment's real duration with the expected span length before concatenating.
- **Normalise the narration before the file counts as delivered.** Audio straight out of TTS measured
  −19.1 LUFS with a true peak above 0 dBFS (clipping). Two-pass `loudnorm` to −16 LUFS / −1.5 dBTP, then
  re-read `ebur128` to prove it, before calling the film finished.
- **Preview encoding: never hand x264 an odd dimension.** `scale=720:405` dies with `height not divisible by
  2` and writes nothing; use `scale=720:-2`. With `-movflags +faststart` the output stays near zero bytes
  until the encode completes, so a 0 MB preview file is not evidence of a stalled job. Keep a chat preview
  at or under ~13 MB; 16.6 MB was rejected by the gateway and cost a second full encode.
- **`node --check` inside a backgrounded `&&` chain can fail with `stdin is not a tty` and exit 1** — the
  render behind it then never starts and the log is empty. Run the syntax check as its own command.

## 6. Where the detail lives

| working on | page |
|---|---|
| **a visible character speaks and the line must appear on screen** | `references/chat-balloons.md` + `scripts/bubbles.py` (run `--selftest` first) |
| **writing the prompts an image model will draw from** — coverage, continuity, camera, prohibitions | `references/stickman-visual-prompts.md` + `scripts/asset_prompt_audit.py` |
| which model you are and the failure mode that comes with it — read *after* the route is chosen (§2) | `references/agent-routing.md` |
| commands, page contract, install | `references/cli.md` |
| the nine steps, project contract, mux | `references/workflow.md` |
| storyboard, captions, one-language gate | `references/narration-and-captions.md` |
| palette, element budget, personality, rhythm — plus the **restraint numbers**, the ten-assets-per-scene rule and the composition archetypes that stop template slop | `references/design-taste.md` |
| motion languages, techniques, 3D layer, **360° turntable sequences** | `references/motion-library.md` — §8 paper theatre, §9 turntables + `scripts/turntable.py` |
| GSAP plugins (all free), seek-safe triage, shake/debris/SplitText/DrawSVG recipes | `references/gsap-plugins.md` |
| a shot needs an asset that does not exist yet, or needs one repaired; launching `codex`/`agy` on a build, racing two of them on one brief, splitting one film across two agents (art on one, the build on the other), and capturing their token usage | `references/self-healing.md` + `scripts/asset_gen.py` |
| punch-up, product demo, talking head, grammars, **and an ad for a real product** — fact proof, essence proof, beat-sync proof, brand-integrity proof, and the supplied-poster case | `references/workflows-specialized.md` §9.2b–9.2c |
| **writing the brief for a long product film with no narration** — chapter map, sourced-figure table, music arc, the ten proofs to demand | `templates/brief-product-film-no-narration.md` |
| music worlds, composer, sfx, narration synthesis, **or a score written from scratch and measured for energy instead of trusted** | `references/audio-and-music.md` §10a + `scripts/score_audit.py`, `references/narration/deepseek-tts.md` |
| a blank, stalled or wrong-length render, a film that renders but barely moves, a render that dies mid-film, or a film long enough that frames must be streamed to ffmpeg | `references/render-traps.md`, `references/static-render-and-resume.md` |
| what to check, and in what order | `references/verification.md` |
| proving a scene moves, and packaging it for an outside reviewer | `scripts/review_pack.py` + skill **`second-opinion-review`** |
| style recipes, camera language | `references/art-motion/INDEX.md` |
| the brief names a reference channel, film or style to match | `references/measuring-a-reference.md` |
| a stick figure or flat character has to act, a "what-if" short, a character in a soft 3D room | `references/stickman-and-figures.md` |
| **two characters talking, conversation gestures, turn-taking, interruption, a listener that acts** | `references/stickman-performance.md` + `scripts/stickman_rig.py`, `scripts/dialogue_voices.py`, `scripts/stickman_qa.py` |
| **a rider, driver or pilot performing — racing, speed, lean angle, an overtake, a save** | `references/stickman-performance.md` §15 (differential layer scroll, detail budget, incident staging) |
| **a pixel-art film — hard pixel edges, indexed palette, white theme** | `references/pixel-art.md` |
| **handing the finished file over** — preview sizing, serving the full file over a tunnel, proving what the link serves | `references/delivery-and-transfers.md` + `scripts/serve_range.py` |
| proving the router itself has no conflicting instructions | `scripts/routing_audit.py` (run before any publish) |
| sourcing icons and vectors, licences | `references/asset-sourcing.md` |
| a watermark, a real person's portrait, licence credits, end-card compositing, a mark in the middle of the film | `references/credits-and-attribution.md` |
| art generated by an image model, cropping prints, mounting | `references/generated-assets.md` |
| flat-vector craft, scrolling worlds | `references/2d-vector-motion.md` |
| which subjects this renderer can carry | `references/topic-fit.md` |
| a brief phrased "in the style of <channel or video>" — resolving the reference into observed rules and rights | `references/style-references.md` |
| timing and easing at sub-second level | `references/ui-motion/` |
| publishing this skill (one commit, v1.0), and a README that installs it on any agent | `references/publishing-skills.md`, `references/publishing.md` |

The style-recipe route (`scripts/art-motion/engine/`) is **20 MB of vendored runtime that is deliberately not
in this repository**: a skill should not make every agent fetch an engine it may never use, and a 37 MB tree
cannot be reviewed. It installs pinned and checksum-verified, onto the exact paths the pages above cite:

```sh
python scripts/install_art_motion.py --check                   # is it there?
python scripts/install_art_motion.py                           # core: lib + demos + scenes, 20 MB
python scripts/install_art_motion.py --with-reference-films    # + study material, 14 MB more
```

Everything else — the Python gates, the clip specs, the documentation — is in the repository and needs no
install. Never commit the fetched tree back: `.gitignore` already covers it.

## 7. Scripts

| script | does |
|---|---|
| `scripts/doctor.py` | preflight, read-only |
| `scripts/deepseek_voice.py` | `probe · speak · cost · lay · beats · asr · gate` — narration and its measured timeline |
| `scripts/deliver_check.py` | validates the delivered file: size, rate, audio, peak, duration against the timeline |
| `scripts/lang-audit.py` | one-language gate over markup **and** script literals |
| `scripts/audit_numbers.py` | caption gate: dates, months, years and counts must be digits on screen |
| `scripts/audit_assets.py` | per-scene asset count and cross-scene reuse, parsed from the manifest tables |
| `scripts/art-motion/icon_audit.py` | icon families, colour count, contact sheet |
| `scripts/art-motion/qa.py` | pacing and pop heuristics on a rendered file |
| `scripts/add_watermark.py` | burns the owner's credit into the delivery encode — one generation, not two |
| `scripts/add_creator_card.py` | circle-masked portrait + name/role/licence credit on the end card, no re-render |
| `scripts/stamp_credit.py` | per-file `by <owner>` comments, only when the owner explicitly asks — never a publish step |
| `scripts/publish_audit.py` | pre-publish sweep: credential patterns and real secret values, machine paths, dead anchors, dead `npm` install commands |
| `scripts/review_pack.py` | review pack from a finished film: frames, per-beat triptychs with changed-pixel counts, 8 fps strips, `measured.json` |
| `scripts/score_audit.py` | scores a music bed by measurement: loudness and true peak from `ebur128`, nine-band tilt, onset density, crest, click count, DC — exits 1 on a drone or a hiss-forward mix |

## 8. Working with a person

Show frames, not adjectives. One hero frame per act kills a week of wrong work. When they correct you, put
the correction into this skill rather than into a chat reply.

**A long build gets a reporting cadence, not silence.** When a film or an agent build will run for more than a
few minutes, start a watcher that prints one progress line a minute from measured file state (newest files, file
size, whether `moov` exists yet) and report from that — the person should not have to ask "cek progress", and a
reply that says "still running" is worse than one that says what changed. Announce the cadence once, then keep it.

Handoffs: narration timing and prosody → skill **`tts-intonation`** · merging or translating another
library → skill **`agent-skill-sourcing`** · rights and likeness before publishing → skill
**`media-content-safety`** · sourcing a reference video → skill **`streaming-mirror-extraction`** ·
3D or footage-based shots → skills **`headless-three-video-render`** and **`cinetic`** · type-first films
→ skill **`kinetic-typography`**.
