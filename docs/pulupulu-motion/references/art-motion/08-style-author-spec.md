# 08 · Style Author Spec (general edition, for scene writers and dispatched agents)

> Replaces the earlier `era-author-spec.md` that was hard-wired to the reproduction project. When you dispatch an agent to draw a style, give it the path to this page, plus the specifics from the "this project" section.

## Interface

One style segment = `scenes/<id>.js`:

```js
SCENES['<id>'] = { draw(c, lt, t) { /* fill 1920×1080 */ }, init(IMG) { /* optional: one-time precompute */ } };
```

- `c` target 2D context; `lt` this segment's local time (seconds, counted from the start of this segment's transition); `t` whole-film time.
- Segment table `eras.js`: `{ id, eighths or dur, transition: { type, dur }, counter: {...} }`. Film length is computed automatically from the segment table.
- Transitions `transitions.js`: `TRANSITIONS.<name> = (c, A_old, B_new, p, o) => {}`.
- Scene file missing, syntax error, not registered → the engine refuses to start; render/qa errors out. Never judge success by "it looks like it rendered".

## Read first (in order)

1. `references/art-motion/02-mechanism.md` (five-layer mechanism, used only by speedrun/time-travel films), `04-pure-code-painting.md` (pipeline, renderer cheat sheet, pitfalls), `07-positive-lessons.md`.
2. `references/art-motion/style-recipes/INDEX.md`: find the closest style as a starting point, then read that card.
3. Benchmark implementation `scripts/art-motion/engine/scenes/09_postimp.js`; the scene source of the closest style.
4. `lib/`: `paint.js` (noise/texture/renderer/palette/choreography), `rig.js` (character rig, visibleLines), `kit.js` and other utility libraries. **Look in the library first, then write your own.**

## Two starting points

**With a reference film**: first run `scripts/art-motion/analyze/breakdown.py` to get reference frames (`ref/segNN.png`), motion heatmaps, and transition contact sheets, then break it down per 01. Reference frames decide composition, motifs, and palette; the heatmap decides "what is moving in the picture".

**Without a reference film** (more common):
Read [cross-scene style distillation](15-style-transfer.md) first. When a new card is in research state, keep work generalization, production hypothesis, and hands-on evidence separate; rebuild the scene for the new subject, and do not inherit characters/props/layout from the famous work.
1. Write down the 3–5 most identifiable formal elements of the style (materials, brushwork, palette, motifs, medium traces). Consult primary sources (original artworks, art-history descriptions); when building a card for the first time, look at several different works and record stable features and exceptions — never generalize the whole oeuvre from a single famous piece.
2. Give each element a "way it can move" — how it would naturally move in the world of that painting (water ripples, paper flutters, gold glints, plates misregister, film jitters).
3. Work out how such a picture is actually made in reality (brush, carve, print, paste, inlay, spray, render), and write that physical process as a renderer.
4. Produce one frame first: compare the still frame against the original; only set it moving once it is recognizable at a glance.

## Hard requirements

1. **Composition**: speedrun/time-travel films place elements at the composition coordinates given by this project (identical across segments — transitions and "the same character travelling through" both depend on it). Other subjects compose per subject: the style decides composition and how light is used; do not reuse the demo room's coordinates.
2. **Characters**: speedrun/time-travel films use the `RIG` skeleton and shared choreography — change the drawing, not the blocking or the action; other subjects design characters and blocking per subject (humans use AI-generated frames, see 10). **Characters must also go through the style's material treatment** (brush strokes, grain, paper-texture multiply, ink-bleed edges, halftone dots, color-plate misregistration...), otherwise they look like pasted cut-outs — this is the most widespread weakness across the 36 styles. When you need line art, use `drawGirl/drawCat` with `mode:'line'` (it goes through visibleLines internally, so lines never cut through).
3. **The picture must live**: main action + 2–4 motif micro-loops, visible within the hold window. In speedrun/time-travel films character action uses whole-film time (`PAINT.cupCycle(t)` and the like) and does not reset at segment changes.
4. **Smoothness**: do not re-seed and re-shuffle the whole screen at a low frame rate (it reads as flicker); apply boiling only to line art or motif regions. Intentional "stepped frame rate" (rubber-hose 12fps, shadow puppet 10fps) uses `stepTime` — that is style, not stutter. For scrolling patterns the modulo period equals the pattern's real period.
5. **Determinism**: all randomness seeded; rendering the same t twice is pixel-identical.
6. **Performance**: static parts use `PAINT.cached`; offscreen canvases that read pixels use `willReadFrequently` and `g.reset()` every frame; target ≤150ms per frame (qa measures real time including GPU flush).
7. **Type**: prefer drawing the style's lettering as paths in that style's material; when using a font, first verify the glyphs exist with `U.assertGlyphs` (missing glyphs silently fall back to a system font).
8. **Aging stays off the body**: peeling, stains, and scratches go on the background only; set a protected zone over the character area (Dunhuang peeling spots landing on a back read as "holes in the clothing").

## Self-check and delivery

```sh
uv run --with playwright python <project>/render.py --solo <id> --stills 0.4,0.6,0.8,1.0 --out <render>/<id>   # stills
uv run <skill>/scripts/art-motion/qa.py --project <project> --ids <id>                                                # numbers
```

At least 3 rounds per segment: stills against the original/reference contact sheet → qa for motion/static-frame pairing/jumps/duration/determinism → fix. Four questions: ① Is the style recognizable at a glance? ② Are the characters right, and do they blend with the background? ③ Within the hold window can you see the picture moving, without flicker or stutter? ④ Any breakage (occlusion errors, broken lines, misregistration, blank areas, doubled text)?

Delivery: `scenes/<id>.js` + a recipe card (following the `style-recipes/` format: pipeline, key parameters and color values, how the motif animation is done, signature transitions, performance, pitfalls, what can still be improved). Write parameters, performance, and quality conclusions only from measurement; leave what you did not do in research state. Verifying a single scene does not license a claim of cross-scene verification. **Before delivering a multi-segment film, dispatch an agent that took no part in production to review the finished film alone.**

## Three-direction gate when unattended

With the author present: produce three versions of a new style direction or character interpretation on the same frame for them to choose.
With no one to ask (automated tests, overnight batches): execute the direction written in the brief, and list in the delivery note one sentence each for "the other two directions I could have offered", for them to choose when they come back.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
