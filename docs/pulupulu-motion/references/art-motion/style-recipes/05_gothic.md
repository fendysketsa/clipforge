# 05_gothic · 1290 Gothic Illuminated Manuscript

11–22ms per frame (median 12ms). The static layer + gold-leaf mask are built once in `init()`.

## Pipeline
1. Static layer `goth_static` (cached): parchment → gold leaf → diamond diaper → gable, pinnacles, side columns → pointed-arch window with stained glass → table, throne → Latin text column → marginal knight.
2. Gold-leaf mask `goth_mask`: compute "goldness" per pixel over the static layer, `clamp((r-b-70)/50)·clamp((g-b-30)/40)·clamp((r-140)/40)`, and use the result as alpha. Parchment (236,223,194) has r−b of only 42 and is excluded; the pink band has a high b and is excluded too. **No need to redraw the gold shapes as a mask** — anywhere that is gold gets swept by the highlight automatically: background, initial capitals, gold balls, gable finials.
3. Each frame, in order: stained-glass twinkle → diagonal highlight → four-point stars where the highlight passes → vine ornament → snail → running mouse → cat → girl → grain.

## Gold-leaf feel (the spec's "fine texture + highlight")
- Per-pixel shading: `f = 0.52 + fbm(x·.0035)·0.42 + horizontal polish grain noise(x·.004, y·.09)·0.5 + upper-left lighting + grain±0.05`, then interpolate between goldLo #9c6a1a / gold #d9a63a / goldHi #f8de86. The polish grain's y frequency is more than 20× its x frequency, which is why it reads as horizontal brushed metal.
- Diamond diaper: 46px spacing, two families of diagonals (x+y and x−y constant). Each line is drawn twice: once dark, once bright offset 1.2px, so it looks cut into the gold. 4 pressed dots at each diamond center, bright upper left, dark lower right.
- Every 118×125px draw a very faint square seam, imitating leaf-by-leaf gold application.
- Diagonal highlight: first paint a linear-gradient band on a 920px-wide scratch, slope K=0.45 (the "/" direction). Multiply by the mask with `destination-in`, then composite back with `lighter` at α0.62. **Move at constant speed** `x = lerp(150,1650,(lt-0.08)/1.15)`. InOut easing was used at first and by 0.9s the highlight had already swept past the gold area, so nothing showed on the girl; at constant speed it reaches the window edge at 0.3s and sweeps exactly across the girl at 0.9s. The halo and the 11 fixed points use `|u − sweepX| < 70` to decide when a four-point star flash appears as the highlight passes.

## Motif animation (all readable within the 0.25–1.4s window)
- Vines: two stems of about 120 points each, each point offset by `sin(t·2.1+i·.09)·2.5`. Every 3–5 points hangs a three-lobed ivy leaf (blue/red/gold rotating) or a gold ball with 3 tendrils. Leaves swing about their attachment by `sin(t·3.1+k·1.7)·0.28`. Leaf scale was 0.85 in the first version — too small and sparse — changed to 1.05–1.45 to match the source's density.
- Stained glass: 26 random points light up a white radial glow when `sin(t·5+h·40) > 0.6`.
- The cat lifts one forepaw holding the mouse by the tail; the mouse swings like a pendulum `0.32·sin(t·5.5)` with its legs kicking. The snail crawls left at 62px/s with antennae wobbling; the mouse under the text column runs 360px over 0.12–1.17s, legs swinging 40 rad/s.
- The girl raises a gold chalice on the shared choreography; a four-point star flickers on its rim, and the steam above the cup is fine ink lines.

## Characters
- The girl is drawn directly from `RIG.girl`'s Path2D, in order, **without calling `RIG.drawGirl`**, for two reasons: drawGirl always renders a mug with a handle, and the cloak and halo need to be inserted between specific layers. Draw order: halo (centered on headC offset (16,−22), r=114, red ring plus 36 pressed dots) → long wavy blond hair → red robe (fine gold vertical stripes every 20px, one gold edge at the hem) → blue cloak (anchored on nape/back, gold edge) → head → gold chalice.
- The cat is the manuscript's "human-faced cat": the face is a cream ellipse, almond eyes with pupils pushed to the right side glancing at the girl, thickened upper lids, raised brows, downturned mouth corners, flushed cheeks. Only `legs[0]` is used; the other foreleg is drawn with `RIG.limb` in a raised pose.
- Latin body text uses UnifrakturMaguntia 44px. At 50px "cum poculo suo" gets pushed off the right edge. Sentence-initial Cattus/Nemo/Mus are in vermilion — the medieval rubication practice.

## Pitfalls
- The scratchpad is shared with other era authors and `check.py` was overwritten by someone else once. Keep self-check scripts in your own subdirectory.
- If the motion diff image uses lt=0 as its baseline it gets polluted by the engine's first 20 frames of camera punch (1.03 zoom). Take the baseline at lt≥0.35.

## v2 tuning
Vine swing ×2, leaf swing 0.42; stained-glass twinkle points 40; gold highlight α0.85 with a wider band. Still-segment frame diff 1.10 → 1.32 (source 1.64).

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
