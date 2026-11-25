# Specialized workflows

Owner: punch-up, product demo and talking-head grammars


Punch-up of an existing film, product-demo continuity, talking-head packaging, and the eight JSON-driven grammar templates.

Part of the `pulupulu-motion` skill. The entry point and the gate table live in `SKILL.md`.

## 9. Specialized Workflows

### 9.1 Punch-up (Making an Existing Film Much Better)
Do not "polish" a flat film with longer eases or shadows. Copy old `index.html` and `treatment.md` to `tools/` (never overwrite old renders in `out/`), then:
1. **Diagnose with numbers:** Run `om qa <dir>` (flat = most seconds < 1 motion/sec; healthy launch = 4–15 with 1 dip), `om qa <dir> --sheet` (look for repeated slide layouts), `om sound <dir>` (fix `warning score:` and flat energy), and spectrogram. Report before-numbers to user.
2. **Keep** the spine, approved copy/claims, palette, type, material, and delivery settings. **Rebuild** layouts, eases, camera, cut points, and score.
3. **Pass the Slide Test:** Replace any slide-like stretch with one of: **Full bleed** (material fills frame) · **Macro** (cut to changed detail at ≥⅓ frame, using measured 10%-grid coordinates) · **In space** (perspective row/stack, step camera) · **All at once** (versions fly out into wall, pull one forward) · **Collision** (two elements meet on beat, one emerges). Keep caption/tag positions fixed in screen space, never over material.
4. **Frame on the change:** When UI edits/transforms, camera is already zoomed in (≥⅓ frame). Follow dynamic targets in `OM.clock` via `getBoundingClientRect() / scale`.
5. **Rewrite score on the picture's grid**, adding one instrument role per section.

### 9.2 Product Demo Continuity
For cross-device / UI workflows, follow the causal viewing arc: **Full device → Action close-up (typing/click) → Full device (reply) → Cross-device juxtaposition (primary readable, secondary anchor) → Detail extraction (remove chrome) → Result notification** (reusing opening avatar/request).
- Separate 4 layers: **content/scroll**, **device/window frame**, **framing wrapper**, **fixed captions**.
- Planar framing formula (top-left `transform-origin`, unscaled layout offset `(bx, by)`, local focus `(fx, fy)`, target screen point `(vx, vy)`, scale `s`):
  `x = vx - bx - s * fx`, `y = vy - by - s * fy`.
- Write a shot log per seam: `Event | Active reading zone | Kept identity anchor | Start/End framing | Action | Settle time | Read window | Next-shot new info`.

#### 9.2b An ad for a real product — three gates that come before craft

A product ad fails differently from an explainer: not by looking dull, but by **misrepresenting the product**.
Run these three gates and paste their output into `ADMIT.md`.

1. **Fact proof.** A table of every on-screen claim against the exact line on the product's own page that
   supports it. Anything you cannot source is removed before delivery, not softened. No invented metric, no
   invented testimonial, no invented customer logo, no feature the page does not list. Paraphrasing a feature
   into something that sounds bigger is a misrepresentation, not a copy edit.
2. **Essence proof.** One sentence: what the product actually is, and the one thing the ad must never imply.
   Then check every frame against it. Worked example — an orchestration IDE for agentic development sells
   *"let AI build, you review"*: the human approval gate must be **visible**, twice if the runtime allows, and
   no frame may show code shipping without it. A tighter cut is always available that does not break this.
3. **Beat-sync proof.** Declare BPM, render length in beats, and the beat grid. Then *measure* the cut times on
   the encoded file — frame-to-frame luminance MAD peak detection is enough — and report the offset in frames
   from each cut to its nearest beat. Every cut within ±2 frames. State the maximum.
   Length should be a whole number of beats: `frames = beats × 60 / BPM × fps`, so nothing is padded.

For an ad, loudness deliberately differs from the default gate: **-14 LUFS integrated, true peak ≤ -1.0 dBTP**.
That is an override of the gate table, allowed because the brief outranks the defaults — write the override and
its reason into `ADMIT.md`, and normalise the pre-encode WAV a little quieter (-14.0 / -2.2 dBTP) so AAC
inter-sample overshoot still clears the peak ceiling.

Reuse the product's **real** assets where they exist (its own feature illustrations, logo, palette pulled from
its CSS): a faithful screen beats a prettier invented one, and an invented dashboard is the fastest way to lose
the trust the ad was bought to build.

#### 9.2c When the supplied asset *is* the design — a poster, pack shot or key visual

An owner hands over a finished poster and asks for an ad from it. The gates above still apply, plus four rules
that only bite in this case:

- **The asset's pixels are the authority for every word and number — not the brief.** A brief written from memory
  quoted a horsepower figure the poster did not print and a displacement figure it never contained; the copy gate
  caught it and refused to render the claim. Read the asset at 4–6× magnification (`PIL` crop + `ImageEnhance`),
  transcribe its text block, and put into the brief only what is physically printed. A spec you cannot point at in
  the file is **removed**, never corrected from outside knowledge — an ad that improves on the client's own
  artwork is a wrong number with a nice frame around it.
- **Move the product as a rigid body only.** Push, rotate a few degrees, parallax, a specular sweep — never a warp,
  bend, liquid or non-uniform stretch on a vehicle, device or face. List the exact transforms applied to the hero
  layer in `ADMIT.md`; "it was only scaled" is checkable and a mesh distort is the thing that makes a premium ad
  look cheap.
- **Cut brand marks out as raw pixels and leave them untouched.** Crop the shield/wordmark from the supplied file
  at native resolution, apply no filter, no resample-redraw and no animated transform, and record the crop
  rectangle. Re-drawing or recolouring a mark is a fidelity and rights failure, not a style choice.
- **A supplied still does not have to fit the frame.** A 4:5 poster in a 9:16 ad is **extended, not cropped**:
  sample the asset's own background at its edges and continue that field above and below so the product stays
  whole. Cropping through a wheel, a face or a headlight signature is the defect a viewer names first, and it
  contradicts the same "product is never cut" rule the money-shot push-in tempts you to break.

### 9.3 Talking-Head Packaging (`--template talking-head`)
1. **HDR check first:** If `ffprobe` shows `arib-std-b67` (HLG) or `smpte2084` (PQ), tone-map to SDR `yuv420p` before importing.
2. **Extract & align words:** `om voice talk --audio talk/assets/talk.mp4 --text script.txt` (supply spoken-form `--text`, e.g. `"twenty-something models"`, so Whisper aligns accurately; aim ≥ 90% match).
3. **Pick 3–6 moments** (~1 every 4 s): name plate, counting stat card, 4–8 character keyword overlay, chapter card at turns, corner badge. Never package what's already shown or duplicate card + keyword overlay.
4. **Anchor to words:** Use `cue` in `om set` (`OM.cue`, `lead: 0.25s`, `"nth": 2` for repeats). Verify every cue exists in `assets/voice.words.json` (generated in the project by `references/narration/scripts/tts-prosody.py`, not shipped in this repo).
5. **Keep off the speaker:** Measure `subjectX`, `subjectW`, `subjectTop`, `subjectBottom` from real frames (`om look --at`); raise `cardBottom` if speaker holds objects.
6. **9:16 & Transparent Overlay:** `om fork talk talk-9x16 --size 1080x1920`. For NLE overlay: `om render talk --transparent` (ProRes 4444 `yuva444p12le` with `#talk` removed and transparent `html/body`); verify alpha with `ffprobe` + `ffmpeg` overlay check.

### 9.4 Grammar Templates (8 JSON-Driven Explainers)
Start with `om new <dir> --template <id>` when narration fits a structured explainer:
- `math-3b1b` (formulas, curves, ML; 1 sentence = 1 transform) · `keynote-ui` (launch cards, screenshot highlights) · `finance-chart` (trends, turning points; bars from 0) · `kurzgesagt` (systems, parts, scale) · `vox-collage` (real docs/clippings) · `whiteboard` (step-by-step "why") · `storytime` (first-person stories/fails) · `kinetic-type` (lists/chapters ≤ 5 items).
- Edit `data-composition-variables` + `<script type="application/json" id="clip-spec">`, not `vendor/clip/`. Anchor cues with `"word"`, `"nth"`, `"edge": "end"`, `"offset"`. Never guess `highlightRect` by eye — measure with `om look --at`.

---
