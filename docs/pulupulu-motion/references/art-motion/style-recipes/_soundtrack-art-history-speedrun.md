# Soundtrack method · code-synthesised score for a speedrun film (teardown method + original example)

This page is method distilled from one teardown: the reference film is X user Tak (@cherry_mx_reds)'s 15-second *Art History Speedrun*, whose score is itself code-synthesised. Only **how to analyse, how to write, how to mix** is kept here; there is no note-by-note transcription of the original track.

Companion script: `scripts/art-motion/audio/synth_art-history-speedrun.py`. The score is an **original example** (D minor, harmony Dm–B♭–F–C); the section structure matches the picture's `scripts/art-motion/engine/eras.js`, and the instrument library and mix chain can be reused directly — just swap in your own score.

---

## 0. One-sentence conclusion

The score for a speedrun-style short can be **a procedural arrangement on a strict BPM grid**: 17 eras laid out by "number of eighth notes" (6,4,4,4,4,4,3,3,3,3,2,2,2,1,1,1,9), each section shorter than the last, using "sections getting shorter" to create acceleration while the tempo itself stays fixed. Each section swaps in that era's representative instruments, and one three-note motif transposes with the chords through the whole film. After the music stops on the grid, a string of cartoon sound effects (ding, sliding whistle fall, crash, meow, closing pluck) finishes the end gag.

---

## 1. How to analyse a reference score

| What to measure | Method | Precision/reliability |
|---|---|---|
| Tempo and grid | superflux-style spectral flux on the STFT (hop 2.5ms), peaks taken as onsets, then least-squares fit `t = t0 + n·E` (28 onsets in total) | E = 0.23431s (eighth note) → **128.04 BPM**, grid zero t0 = 0.028s. All residuals within ±4ms, which human playing cannot achieve — enough to conclude it is code-scheduled |
| Era boundaries | three-way cross-check: ① grid position; ② peaks of the MFCC novelty curve (distance from the mean of 0.2s either side); ③ peaks of the frame-to-frame video difference | audio boundary (grid) and MFCC peaks deviate by ≤20ms. Picture transitions lag the audio by 0–0.2s (the picture uses 0.1–0.2s wipe/morph transitions) |
| Pitch | ① Spotify basic-pitch polyphonic transcription (ONNX, temporary Python 3.11 environment); ② 85ms FFT peaks on a sixteenth-note grid, gain >6dB before/after the onset marking a new note; ③ self-written CQT semitone energy map read by eye | melody lead high confidence (both methods agree). Inner harmony voices, and detail in the ukiyo-e and Van Gogh sections, medium confidence |
| Timbre | for each melody note take harmonic amplitudes 20–220ms after onset (H1–H8, ±1.5% narrowband), then measure the narrowband envelope's attack time and decay (+50/100/200ms relative to peak) | polyphony bleeds other voices in, so harmonic ratios can only be read as a tendency |
| Percussion | per sixteenth note, measure energy jumps >6kHz (noise type) and <150Hz (drum type) | high |
| Sound effects | for 13–15s, 20ms-step FFT peak tracking of frequency trajectories, aligned against the 2.1s picture contact sheet (one frame per 0.1s) | high |
| Loudness | ffmpeg ebur128; per section, BS.1770 K-weighted mean square without gating | overall **-14.3 LUFS, LRA 0.9 LU, true peak -2.4 dBTP** (the commonly heard "average -16.6dB" is the RMS mean, a different measure) |
| Omnimodal model "listening" | have an omnimodal model listen to the whole film and ask it questions framed from a composer's viewpoint | candidates only, re-check each one, see section 4 |

---


Two more lessons: timbre judgement is most reliable from "harmonic amplitudes 20–220ms after onset + narrowband envelope decay"; judging "is it code-synthesised" comes down to three things — whether timing residuals are within ±5ms, whether all timbres are textbook building blocks like sine/square/saw/exponential decay, and whether there is recording noise floor in the silences.

---

## 2. Original example score (the `era()` blocks in the script)

The time unit is the eighth note, start = `t0 + n·E`. The motif ♪♪♩ is marked "motif".

| # | Era | Length | Instrumentation | Notes written in the example |
|---|---|---|---|---|
| 1 | Cave | 6 | bone flute + hand drum + off-beat hits | descending augmented version A4–G4–D4 |
| 2 | Egypt | 4 | harp + sistrum | Dm→B♭ arpeggio; motif F5–G5–D5 |
| 3 | Greek black-figure | 4 | lyre + double aulos | B♭ chord; D5 → F5 |
| 4 | Rome | 4 | horn + war drum | motif C5–D5–A4, F→C→Dm |
| 5 | Gothic | 4 | organ | Dm → Gm/D, D2 pedal |
| 6 | Renaissance | 4 | harpsichord + bass viol | motif B♭5–C6–G5, Gm→F |
| 7 | Ukiyo-e | 3 | koto + taiko + hyoshigi | sixteenth-note plucking of the D miyako-bushi scale (D–E♭–G–A–B♭) |
| 8 | Impressionism | 3 | soft piano | motif variant A5–C6–G5, Fmaj7 → B♭ → Dm9 |
| 9 | Van Gogh | 3 | bright plucking + wind | D2 bass groove, scattered A5/F5/D6/E5 up high |
| 10 | Art Nouveau | 3 | celesta | motif D5–E5–A4, B♭→C→Dm |
| 11 | Cubism | 2 | piano-like struck strings | deliberately dissonant: D–G♯–C♯ → E♭–A–B♭–E |
| 12 | Bauhaus | 2 | marimba-like short notes + mechanical ticking | D stacked across five octaves → F/A → D |
| 13 | Pop | 2 | drum machine + cartoon stabs | kick, off-beat claps, D/F stabs |
| 14 | Pixel | 1 | square wave | F major triad thirty-second arpeggio |
| 15 | Ray tracing | 1 | supersaw | B♭ chord |
| 16 | Memphis | 1 | supersaw sustained chord + kick + rising glide (cat jumps onto the table) | C major suspended across the section end |
| 17 | 2026 | 9 | 128BPM house: four-on-the-floor kick, off-beat open hats, saw bass, square-wave plucks, pad | modulates to D major add9: F♯5 A5 D6 E6 F♯6 E6 D6 B5 A5 |

When writing your own score: fix a harmonic loop and a three-note motif first, then fill in each section's "representative instruments + transposed motif" from the section table; "outlier" sections (exotic, avant-garde) only change mode or add a tritone — rhythm and grid stay put.

---

## 3. Ending sound effects (by "stop—suspend—slam—react—close")

| Event | Synthesis method (functions in the script) |
|---|---|
| Music stops | the bass decays fast over about 150ms, no hard cut |
| Paw taps the cup "ding" | a few inharmonic rings at 5–7kHz plus a little 1.5kHz (`tink`), with a high-frequency swoosh at the same time (`swipe`) |
| Cup falls | a pure sine exponential slide from about 1550→325Hz, 0.35s (`slide_whistle`) |
| Shatters on impact | a thud around 80Hz + broadband noise (centroid 5–7kHz, about 0.45s decay) + ceramic inharmonic overtones + a few small shard collisions (`crash`) |
| Meow | harmonic synthesis on a linear broken-line pitch (up then down) + two formants, the loudest moment in the whole piece (`meow`) |
| Signature appears | two soft ~90Hz "boops" with a little sparkle (`end_thump`) |
| Closing | a low plucked note landing on the tonic |

All timings are aligned to picture events from the picture contact sheet (one frame per 0.1s).

---

## 4. Mix approach (second half of the script, usable as-is)

1. 0.5s small-room reverb, 12ms pre-delay, 9% wet
2. Per-section low-frequency warm bed: lay "triangle + octave-down sine, 250Hz low-pass" on the section's chord root (`BED_ROOT`), level computed automatically from the "floor relative to section loudness" value; sections that already have enough get none
3. Per-section 2–6kHz dynamic EQ (`MID_ORIG`)
4. Per-section added >6kHz air noise (`HF_ORIG`)
5. Per-section K-weighted loudness alignment to `target`, 4 iterations, 10ms smoothed gain to prevent zipper noise
6. Optional: steep 15.8kHz low-pass to emulate streaming AAC
7. Overall LUFS alignment, then look-ahead peak limiting

With a reference film, fill `target / MID_ORIG / HF_ORIG / LOW_FLOOR_ORIG` with per-section values measured from it (using section 1's methods); without a reference film, the example's "uniform relative values" are enough.

Lesson on softening attacks: the plucked model's 2ms hard attack sounds too "pointy"; switching to a 10ms linear attack, with higher harmonics attacking later (×1.6 per harmonic up, capped at 35ms) and the attack noise halved plus a 7kHz low-pass, makes the whole thing much more coherent.

Example output: 48k stereo, 15.06s, -14.0 LUFS, true peak -1.5 dBTP.

```
uv run --with numpy --with scipy --with soundfile python scripts/art-motion/audio/synth_art-history-speedrun.py
```

---

## 5. Reusable rules: a code-synthesised score for any animation

These can be copied directly.

1. **Fix a BPM grid first and align everything to it.** 128 BPM (eighth note 0.234s) suits "speedrun, montage" pacing; edit points, music onsets and sound-effect hits all land on `t0 + n·E`. The benefit is that however the picture is cut, the music never sounds messy. The reference's timing residual is only ±4ms, and that machine-like precision is itself part of the style.
2. **Accelerate by "decreasing eighth notes per section", not by raising tempo.** This film is 6 → 4×5 → 3×4 → 2×3 → 1×3, then the last section is lengthened (9) to let the audience breathe and leave room for the gag. Tempo unchanged, yet it feels more and more urgent; and since every section lands on the grid it stays naturally in sync with picture cuts. Method: list each section's picture duration, round to eighth notes, then adjust as a whole so the decrease becomes regular.
3. **One three-note motif, repeated with changed instruments and chord transposition.** Pick a short cell with a clear rhythm (the example score is ♪♪♩ "step up, then leap down"), play it once per scene on that era's or style's representative instruments, with pitch following the section's chord. A four-chord loop as the harmonic skeleton (Dm–B♭–F–C here) is enough; sections wanting an "outlier" feel (exotic, avant-garde) only change mode or add a tritone, leaving rhythm and grid alone. The opening can use an inversion or augmented version of the motif (the cave section here is a descending dotted quarter) to establish it first.
4. **No crossfades between sections.** New sections attack hard on the grid; the previous section's notes keep their own natural tails (plucked 30–300ms, sustained about 150ms release), and one sustained bass note can carry across a boundary to "stitch" two sections. That gives a clear "click" on every scene change without a break. Not every section needs a transition swoosh (the reference has none).
5. **Design the ending sound effects as "stop—suspend—slam—react—close"**:
   - stop: the music halts on the grid with about 150ms fast decay, no hard cut
   - suspend: a small "ding" as a lead-in, then the falling whistle (pure sine exponential sweep, about 0.35s, more than 2 octaves)
   - slam: thud + broadband noise + inharmonic overtones + a few shard collisions, decayed within about 0.45s
   - react: the character vocalises, e.g. a "meow" on a linear broken-line pitch, about 0.5s after the slam, the loudest thing in the piece
   - close: one or two soft "boops" with the signature, and a final low pluck on the tonic or dominant
   Everything aligned to event timings from the picture contact sheet (one frame per 0.1s).
6. **Loudness alignment method**:
   1. Measure the reference's overall values first (ffmpeg ebur128: integrated LUFS, LRA, true peak)
   2. Then measure K-weighted loudness per section, plus the differences of the 2–6kHz, >6kHz and 40–220Hz floors relative to section loudness
   3. After synthesis, in order: per-section low warm bed → per-section mid/high dynamic EQ → per-section air noise → per-section loudness iterative alignment (3–4 times, 10ms smoothed gain, preventing zipper noise)
   4. If the reference is AAC, add a 16kHz low-pass
   5. Finally align overall LUFS and apply look-ahead peak limiting
   Throughout, use "relative to section loudness" differences, not absolute values, so changing material or overall loudness needs no re-calibration.
7. **How to turn synth.py into a general template** (structure unchanged, only four blocks of data swapped):
   - `T0, E`: grid zero and eighth-note duration (BPM → `E = 60 / BPM / 2`)
   - `edges / target / MID_ORIG / HF_ORIG / LOW_FLOOR_ORIG / BED_ROOT`: section boundaries and per-section reference values; without a reference film, set `target` to a single value (e.g. -14) and the other three to "no top-up"
   - the score block of `era(n0, items)`: one row list per section, elements are `(relative eighth position, instrument function, gain, pan)`. The instrument function library (`pluck` plucked family, `additive` sustained family, `kick / clap / hat / taiko` drum family, `chip / supersaw` synth family) can be reused directly; a new style generally only needs the `pluck` harmonic table and decay parameters adjusted
   - sound-effect block: call `tink / slide_whistle / crash / meow / end_thump` at the event times, with parameters (frequency, duration) measured from the reference or set from rule 5's template
   The second-half mix chain (warm bed → EQ → air → loudness iterations → low-pass → limiting) is kept as-is.
8. **Order of the analysis workflow**:
   1. Fit onsets to the grid with onset flux to get BPM and t0 first
   2. Do FFT new-note detection cell by cell on a sixteenth-note grid, then cross-validate with basic-pitch polyphonic transcription
   3. Judge timbre with narrowband harmonic ratios and envelopes
   4. Judge percussion from high- and low-frequency energy jumps
   5. Omnimodal models as candidates only, re-checked item by item. In practice it was reliable on instrument identification, and wrong on tempo (said 120, measured 128), motif note count, "transition swooshes" and sound-effect timing

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
