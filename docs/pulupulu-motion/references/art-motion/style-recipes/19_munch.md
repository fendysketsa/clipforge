# 19_munch · Munch's "The Scream" expressionism (1893)

> Source: migration test A (independent agent working from the skill alone, 2026-10-04). Scene code was ported after integration to `scripts/art-motion/engine/scenes/19_munch.js`.

Filename at experiment time `scenes/03_munch.js` (~160 lines). Final version adjacent-frame median 2.27%, on the JS side roughly 90–140ms per frame.

**Flow-line renderer `flowLines` (new)**
- Seeds: 24px jittered grid, about 3600. Each seed is assigned a region (sky, fjord, mountain, wall, floor).
- Integrated along a "direction field that writhes over time", per-region parameters [steps, step, width, α]:
  - final: sky [32,7,10,.78], fjord [26,6,9,.78], wall [42,7,13,.5], floor [32,8,12,.55], plus 0–8 random extra steps per line.
  - one stroke travels 200–300px.
  - history: the second version was [26,6,7,.85], and an independent review still judged "at first glance it's Van Gogh", so it had to be longer, wider and less opaque.
- A line stops once it leaves its region, so region boundaries stay clean.
- **No outlines, translucent overpainting**: Munch is thin paint, long strokes. The first version copied Van Gogh's "dark outlines" and the wall became rows of caterpillar-short strokes — instantly Van Gogh. Removing the outline and raising steps from 10 to 26 fixed it.
- Lay a flat fill of the same hue underneath first (wall gradients `#a8401e` → `#5a1a14`), so what shows in the gaps between strokes is the same colour, not black.

**Direction field**
- Sky: `0.55·sin(x·.011 + y·.018 − 2.4t)`;
- Fjord: tangents around (620,470);
- Wall: vertical ±0.5 sine twist;
- Floor: toward the vanishing point (1000,640).

**Blood-red sky**
- The seed's band is decided by "a wavy y": `yy = y + 22·sin(x·.014 − 2.2t)`, band width 28px.
- 7-colour cycle: `#e2541c #f08a24 #f4c03a #c8301e #e8743a #f6a63a #b82a1e`.
- The bands themselves writhe, which is what makes "the sky flow".

**The whole world flows**
Finally the entire painting is displaced row-wise by `9·sin(y·.012 + 4.2t) + 4·sin(y·.031 − 6t)`, then column-wise by `6·sin(x·.009 − 3.6t)`, band height 4px, via `KIT.warpRows / warpCols`. The figure, cat and table all wobble with it, far cheaper than drawing separate shaking lines.

**Motifs**
- In the window: diagonal bridge planks, three railings (following the world warp), two distant figures in hats.
- The screamer: skull face, both hands pressed to the cheeks, mouth opening and closing `7+2sin(9t)`, body swaying `sin(3.2t)·0.12`.
- The table and chair legs are jittering wavy lines.
- Girl: 1890s Norwegian dark long dress + white collar, yellow-green face shadow (`rgba(120,150,70,.4)` at blur 8), 9 long blonde strands as a travelling wave `sin(9q − 7t)`.
- The cat's mouth is slightly open, as if infected by the scream from off-screen.

**Corner caption**: text drawn to an offscreen, then sine-warped row by row. Do not use comic handwriting fonts like Kalam (review said it broke the period); use IMFellEnglish.

**Pitfalls**
- After the whole-image row/column displacement, dark gaps appear at the left and right edges. `KIT.warpRows/warpCols` gained a margin parameter: each row is stretched by an extra 2×margin pixels, and margin must be greater than or equal to the maximum displacement.
- In line-art mode the raised cup arm gets crossed by the torso line; re-cover it with `KIT.nearArm` (see ②-16).

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
