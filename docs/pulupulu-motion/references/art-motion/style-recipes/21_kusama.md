# 21_kusama · Yayoi Kusama infinite polka dots

> Source: migration test A (independent agent working from the skill alone, 2026-10-04). Scene code was ported after integration to `scripts/art-motion/engine/scenes/21_kusama.js`.

Filename at experiment time `scenes/05_kusama.js` (124 lines). 0.45↔0.9s is 17.3%, adjacent-frame median 2.98%, JS side 4–28ms.

**Writhing dots**
- Every dot's radius is multiplied by one "travelling wave emanating from the cat": `wave = 0.82 + 0.28·sin(dist·0.012 − 6t)`.
- All the dots in the room swell and shrink in rings outward from the cat's position, like breathing. This one function brings the whole screen to life.

**Dot layout**
- Wall: large dots (30px, spacing 104) + small dots (10px, offset) as two hexagonal grids, each with ±25–50% jitter. Each dot is a slight ellipse with a random rotation, like hand-drawn.
- Floor: 9 rows, larger and sparser nearer the front (6→28px), flattened into 0.42 ellipses for perspective.
- Red dress white dots 13px, spacing 52, **crawling down the dress** at 46px/s (clipped to the dress silhouette, y offset modulo).
- Cat: white dots on orange areas, red dots on white areas, each crawling downward.
- A red dot on the cheek as well (Kusama's body painting), and a red-and-white polka-dot bow on the head.

**Infinity mirror room (window)**
- 3D lattice of lights: 13×7×3, 6 colours. z cycles toward the camera at 0.3/s, perspective projection F150.
- Each light is a solid small core plus a 3.2× glow, added with lighter.
- Pitfall: the first version scattered the lights randomly with big glows and they smeared into bokeh. A regular lattice + small solid cores is what gives the sense of infinite mirror repetition.

**Yellow pumpkin**
- 5-lobed ellipse, drawn outside → in.
- Each lobe gets black dots in rows: largest in the middle column (9.5px), shrinking toward the sides and top/bottom, dot size also following the travelling wave.
- Whole-pumpkin breathing: scale `1 ± 0.025·sin(5t)` about the base.

**The ending, "self-obliteration"**
- lt 1.0–1.26: a red overlay fades in, and a full-screen 120px hexagonal dot lattice swells in rings from the cat's position out to 0.47× spacing. Then for about 0.15s only the dot lattice breathes gently, giving the ending somewhere to land (review pointed out the first version had no hold frame).
- The last frame rests on white dots on red.
- Pitfall: the first version let the dots grow without limit and ended on a white screen. The radius has to be capped, and it must end on a dot lattice, not a flat colour.
- Pitfall: the dress and the wall are both white dots on red, so the girl dissolves into the picture. The final version thickens her contour to 4.5px and removes the red dots from the cat's white areas, preserving the orange/white boundary.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
