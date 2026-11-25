# 05 · Rhythm and score

Breakdown method and reusable rules: `style-recipes/_soundtrack-art-history-speedrun.md`, the art-history-speedrun soundtrack card (section 5, "Reusable rules", can be copied straight out); synthesis script template (original example score): `scripts/art-motion/audio/synth_art-history-speedrun.py`, the art-history-speedrun synth.

## Key points

1. **Fix the BPM grid first; picture and music both land on the grid.** 128 BPM with a 0.234s eighth note suits speedrun/montage. `eighths` in `eras.js` is how many eighth notes each segment occupies.
2. **Acceleration comes from shorter segments, not a faster tempo.** 6 → 4×5 → 3×4 → 2×3 → 1×3 → the ending stretches.
3. **One three-note motif, each segment swapping in that style's representative instrument and transposing with the chord.** A four-chord loop is enough for the harmony.
4. **Hard onsets between segments; no crossfades, no whooshes.**
5. **Closing sound design: stop — suspend — slam — reaction — resolve** (ding → falling slide whistle → shatter → cat meow → low plucked bass), with timings aligned to the picture's event frames.
6. **Loudness**: match the reference film's integrated LUFS and true peak; compare relative differences segment by segment.
7. Treat what an all-modality model hears as a candidate only: the instruments can be trusted, but BPM, motif note count and sound-effect timing must be re-checked with onset detection.

## Counterpoint with the picture

- Transition start = grid point; the camera impact (scene layer 1.03 → 1.0, 20 frames) lands on the same point, so the audible "click" and the visual kick are one event.
- The action frames of the closing performance (cup pat 3, cup hits the floor) align to audio onsets within 3 frames.
- With no reference film: write the segment table first (how many eighth notes per segment), then generate the picture timeline and the score together; after that, changing the rhythm means editing `eighths` in one place.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
