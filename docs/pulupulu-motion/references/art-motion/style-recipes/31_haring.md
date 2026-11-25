# 31_haring · 1982 Keith Haring

> Source: migration test C (independent agent working from the read-only skill, 2026-10-04). After consolidation the scene code was ported to `scripts/art-motion/engine/scenes/31_haring.js`.

Filename at experiment time: `scenes/k5_haring.js` (109 lines). About 4ms per frame, frame difference 11.5%.

**Methods**
- Flat colour grounds: yellow wall `#ffd51c`, green floor `#16a54a`, 14px black horizon.
- Everything is 13px round-capped black line + flat fill, using `X.girl / X.cat` part by part "fill → stroke".
- **Dancing figure**: 7 limb segments + round caps built from a corrected `X.limb` capsule; **stroke everything at 2×LW black first, then fill colour once** to get the union contour. 4 poses (local key points, origin at the sole of the foot) **hard-cut at 8fps, no interpolation** — that is how Haring dances; motion arcs are added by the hands.
- **Radiating action lines**: n short straight lines on an ellipse around the object (length 22–34, line width 7–9), angle reseeded at 8fps. Used on the cat, the girl's head, the cup, the teapot, the red heart and the figure on the right.
- **Everything bounces on the beat**: `bounce=|sin(t·128/60·π)|^0.6`. The girl dy=−12·bb, the cat half a beat behind. The table squashes and stretches about its foot (sy 1−0.07(1−bb), sx 1+0.05(1−bb)) and its legs bend; the teapot jumps 26px; the window frame rocks ±0.025rad; the length of the "jump" line on the floor follows the beat.

**Motif animation**:
- The sun baby in the window: a white union silhouette, crawling in two alternating frames; 14 rays, lengths alternating at 8fps.
- 3 dancing figures on the wall (red/blue/pink, different phases, one mirrored).
- The red heart above the table, beating, with radiating lines.

**Character**: 80s New York girl. Oversized red sweater (a ribbed line at the hem), denim blue long skirt, white high-top sneakers. The face keeps only one eye dot and one red lip line (Haring's figures have no facial features at all; these are kept so she can be recognised). The thick black ear rings look like Walkman headphones, which fits the period.
**Pitfalls**: `RIG.limb`'s reverse end cap leaves a hole at the joint under thick strokes (see ②-1). The window transom has to be drawn under the baby. RIG's hairLines are thin lines, which violates "lines of equal weight" in Haring, and they also cut across the face when she tips her head back to drink, so they were removed.

---

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
