# 18_klimt · Klimt's Golden Phase (1907)

> Source: migration test A (independent agent working from the skill alone, 2026-10-04). Scene code was ported after integration to `scripts/art-motion/engine/scenes/18_klimt.js`.

Filename at experiment time `scenes/02_klimt.js` (223 lines). 0.45↔0.9s is 32.9% (mostly from the light sweep), adjacent-frame median 0.40%, but 14 of the 48 pairs are nearly static (see ②-2).

**Pipeline**
Gold-leaf wall (cached) → gold-dust four-point stars twinkling (lighter) → window "Birch Forest" pointillism → black-and-white chequer gold frame → flower-carpet floor → Hoffmann black-and-white chequer table → diagonal light sweep (drawn before the characters so they occlude it naturally) → cat → girl's golden robe (pattern layer via source-in against the silhouette) → realistic face and hands → flower crown → gold sleeves, gold cup → golden steam.

**Gold leaf**
- Per pixel: `f = 0.5 + fbm(x·.004)·0.55 + noise(x·.003, y·.08)·0.5 ± 0.05`, interpolated between `[120,78,18]→[196,148,52]→[246,216,128]`.
- One very faint square seam every 96px, standing for individual applied leaves.
- Wall: gold leaf × 480×270 fbm thumbnail, upscaled and multiplied (brown-gold mottling, like the ground of "The Kiss"), then 9000 gold and dark specks scattered over it.

**Pattern (golden robe)**
- 150 random points in four classes:
  - tricolour concentric circles (30%): red-white-blue, blue-gold-red, purple-white-gold;
  - gold spirals on dark brown (32%), each rotating at ±3rad/s;
  - Horus-style eye shapes (22%), blinking in turn: closed when `sin(2.2t+φ)>0.86`;
  - white dot clusters + red hearts (16%).
- The hem also carries 60 black-and-white vertical rectangles with gold outlines — the language of the man's robe in "The Kiss".
- **Flat ornament against a realistic face**: face and hands use radial gradients for volume (highlight `#fbe8da` → `#f0cfb8` → `#d8a88c` → edge `#b88068`), blurred blush and eye-socket shadow, only a 1.2px pale contour. The golden robe has a 3px dark outline. That contrast is Klimt.

**Other**
- Window "Birch Forest": 2600 autumn-leaf-coloured elliptical dots, 6 birch trunks with black marks; 14 falling leaves flipping as they fall.
- Flower carpet: 260 concentric-circle flowers, larger nearer the front (6→20px), nodding `sin(4.2t+φ)·0.18r`.
- Light sweep: 520px wide bright band at α.24, sheared with `transform(1,0,−0.45,1)`, lighter, sweeping **at constant speed** from −200 to 2300 in 1.15s.
- Gold dust: 420 particles, four-point stars when `sin(t·sp+φ)>0.55`. The first version's stars were too big, like Christmas decorations; radius changed from `s·(1+2.2a)` to `s·(0.6+1.1a)`.

**Pitfalls**
- Applying `source-in` per pattern wipes out the others, see ②-7.
- At α.38 the light sweep looked like lens flare; pulled back to .24.
- The first version had static stretches between adjacent frames: blinks are intermittent and the sweep is a soft gradient. Adding three things dropped static frame pairs from 20/36 to 0/36:
  - 34 gold-leaf fragments tumbling down (150px/s, squares and circles, gold gradient);
  - gold dust floating up at 26px/s;
  - flower nod amplitude from 0.18 to 0.35.
- The first version's gold spirals on the cat also covered the face; review said "looks like a rash", so they were confined to the body and cut to 46.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
