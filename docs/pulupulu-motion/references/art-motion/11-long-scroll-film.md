# 11 · The long-scroll traversal film: one person walks left to right through painting after painting

The method behind "The Author Traverses Famous Paintings" (2026-10-05, 123.7 s, 24 worlds). Unlike the art-history speedrun (one room, the style changes), this is **a single horizontal long scroll**: each world is a laterally extending stretch of painting, joined end to end; the protagonist walks right the whole time, and at the instant he crosses a boundary his painting style changes along with the world.

Demo: `scripts/art-motion/engine/demos/long_scroll/`, holding 3 segments (Egyptian fresco → Monet's "Japanese Bridge" → 8-bit pixels), about 15.6 s.

```sh
uv run --with playwright python scripts/art-motion/engine/render.py --film demos/long_scroll --stills 1,5,9 --out test-render   # three still frames
uv run --with playwright python scripts/art-motion/engine/render.py --film demos/long_scroll --out long_scroll.mp4              # the whole piece
```

Browser preview: start a static server in `scripts/art-motion/engine/` and open `index.html?film=demos/long_scroll`; `&only=28_monet,14_8bit` schedules only those segments, `&v=330` tries a different walking speed.

## Files

| File | What it governs |
|---|---|
| `eras.js` | Film entry point: loads the libraries, `FILM_ORDER` (segment order), registers frame libraries, generates one segment with `dur = WORLD.total` |
| `scripts/art-motion/engine/demos/long_scroll/lib/world.js` | The `WORLD` skeleton: timeline (walk → stop and interact → walk), protagonist travel, camera, protagonist clipped at the boundary, boundaries, corner badges. **Read its header comment first** |
| `scripts/art-motion/engine/demos/long_scroll/lib/crossing.js` | `XING`: reads the frame library, draws actor frames (`XING.actor`), brush material, the Monet world |
| `scripts/art-motion/engine/demos/long_scroll/lib/acts.js` | `ACT`: small script helpers (the trajectory of a stone skipping on water, etc.) |
| `lib/xing2_*.js` | Small helpers shared by several segments, loaded on demand at the top of the segment file |
| `segments/<id>.js` | One file per world, calls `WORLD.add({...})` |
| `frames/<key>/` | Actor frame library: 8 transparent PNGs plus `meta.json` (each frame's foot anchor `ax/ay`, size, whether airborne `air`; `ref_h` is standing height in pixels) |

## Adding a segment

1. Create `<id>.js` under `segments/` and call `WORLD.add({ id, year, name, w, hero, acts, back, front, seam })`; the interface is in the header comment of `scripts/art-motion/engine/demos/long_scroll/lib/world.js`. Draw the world itself in code; where possible take an existing style scene in `scenes/<id>.js` and turn it into a laterally extending version (segment width 2000–2800).
2. Generate actor frames: one "walk, 8 frames" set per world, plus an "interact, 8 frames" set if there is interaction. Have the image model repaint in that style, key the green screen, split the frames (`scripts/art-motion/key_split.py`, method in 10), drop them into `frames/<key>/`, and write `meta.json`.
3. Add `<id>` to `FILM_ORDER` in `eras.js`.
4. Render stills to check both sides of the boundary, then run `qa.py --project scripts/engine --film demos/long_scroll`; determinism must be ✓.

## Key conventions (uniform across the film, hard-coded in the skeleton)

- **Ground line `WORLD.GROUND = 760`, protagonist standing height 300, protagonist at 720px on screen.** At both ends of a segment (within ±150px of x=0 and x=w) the ground must return to 760, and the horizon should sit around 480–560, so that both sides join when crossing a boundary. In between you may have bridges and steps (`ground: lx => y`).
- **Every event is timed relative to "interaction start."** Use `WORLD.actT(segment)` to get the film-wide time at which the interaction starts, then `r = S.t - WORLD.actT(ME)`; never write "the Nth second after entering the segment." When the film-wide walking speed was later raised from 330 to 560, not one segment written this way needed a change.
- **The camera only moves forward, never back.** Camera target = protagonist x − 720 plus the `lead` yielded forward during interaction; take the historical maximum, then Gaussian-smooth it, so the move is monotonic throughout and neither starting nor stopping stutters. If an interaction should hold the camera still, write `lead: 0`.
- **Each segment's boundary is drawn in that segment's signature language** (`seam`: paper edge, pixel checkerboard, colour-block dividing line, …). This is the long-scroll version of the speedrun film's "transition = the next style's signature language."
- **The protagonist's walk frame rate scales with walking speed** (`hero.fps`), 8 frames per gait cycle; if the segment needs one more layer of that style's material, write `hero.draw(c, key, i, o, S)` inside the segment and composite it yourself rather than touching the shared library.
- **Music**: picture first, music after. Give each segment a whole number of beats and nudge the tempo segment by segment between 86–104 BPM so that every boundary lands on the first beat of a bar (measured: max error 11.7ms across 24 boundaries); the ear cannot hear a ±8% per-segment tempo difference.
- **Do not add gags to the protagonist that nobody asked for.** The skeleton has a "stack souvenirs on the hat" feature (`FILM_HAT_ITEMS`) that easily competes with the scene for visual attention; it is off by default.

For more evidence and numbers see 07 (positive lessons), items 36–38.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
