# 09_postimp · 1889 Van Gogh (benchmark implementation)

File: `scripts/art-motion/engine/scenes/09_postimp.js`, about 110ms per frame (three full-frame stroke passes). Other eras are written following its structure.

## Pipeline
Flat underlay (large wall/floor/window/bed areas) → flow-field stroke repaint (region palettes) → prop layer (table, chairs, vase, picture frame, chandelier, each with its own small `source-atop` strokes) → environment line work (deep blue 4.5px, boiling at 8fps) → characters (flat fill → fine `source-atop` strokes → line work and features) → animated highlights (lamp halo dashed ring expanding outward, star twinkle, steam).

## Key parameters
- Direction field: wall vertical −π/2 ± 0.22·noise; floor along the perspective lines toward the vanishing point (960,330); starry sky along the tangent of the nearest swirl + 0.3t rotation; lamp halo along the circumference; headboard vertical, sheets nearly horizontal.
- Three stroke passes: non-wall non-floor cell10 len22 w6.5; wall cell14 len64 w8; floor cell12 len46 w8. Outline 0.8–0.9, mixed with 40–45% deep blue. New seed at 8fps.
- Region palettes (P.swatch, mixBase 0.3–0.45): wall `#7f9be6 #5f7fd8 #a7bbf2 #6c6fd2 #8ad0e6 #c3cbf6 #4f6cc8 #9a8fe0`; starry sky `#22339a #2f4fb8 #5c86dc #8fb6ee #1b2a78 #3c6bd0`; floor `#c0573c #a8453a #d7774a #8e3b30 #5f8f6a #c96a52 #e08a5c`.
- 7 spiral bands of orange/pale orange on the cat (clipped to the body, rotating 0.6rad/s) — the source's "swirl cat".

## Pitfalls
- One set of parameters over the whole image melts into a carpet: wall, floor and everything else must be three separate passes.
- Small props get shattered by large strokes: always split them into a prop layer.
- Color jitter alone produces "noise of the same blue"; the Van Gogh feel comes from the dozen-plus hues in the region palettes.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
