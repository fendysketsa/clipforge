# 17_ink · Chinese freehand ink painting (Bada Shanren / Qi Baishi)

> Source: migration test A (independent agent working from the skill alone, 2026-10-04). Scene code was ported after integration to `scripts/art-motion/engine/scenes/17_ink.js`.

Filename at experiment time `scenes/01_ink.js` (313 lines). Frame diff 0.45↔0.9s is 3.3% (threshold 24), adjacent-frame median 0.62%, no static frame pairs.

**Pipeline** (the opposite of the 09 benchmark: paper is the ground, ink is only added, never laid down as a base). The opening does `lt += 0.12`, so frame 0 already carries the first few strokes — it is not a blank sheet (review pointed out that a blank first frame cannot serve as the cover).
Xuan paper (cached) → wash layer: pale-ink distant mountains, vermilion sun → mist bands (paper-coloured blurred ellipses drifting sideways) → a small bird skimming past → static strokes: window, desk, ground line, cached once drawn → bamboo branch (`ge-zi`-style leaves) → Qi Baishi shrimp in the hanging scroll → cat: ochre wash + burnt ink → girl: indigo wash + baimiao outline + drapery folds → steam wisps → seal.

**Xuan paper**
`P.texture('#efe6d0', scale .0025, amt 9, grain 7)`. On top, 2600 short paper-fibre arcs: half brown α.05–.13, half light α.12–.27. Plus a radial vignette reaching α.22 at the edges.

**Brush `brush(c, pts, {w, tone, dry, reveal, bristles, head, tail})`**
- Densify the point list with Catmull-Rom, then resample at 4px equal arc length (`KIT.resample`). Without resampling, the frequency of the flying-white (feibai) noise changes with stroke length.
- Pressure: `prof(q) = smoothstep(0,head,q) · (1−0.7·smoothstep(1−tail,1,q)) · (0.85+0.15·noise)`.
- Wet core: the whole stroke is a ribbon fill, width `w·prof·(1−0.85·dry·q^0.8)`, α = tone×0.72. Thinner toward the end, as if the ink is running out.
- Bristles: each is one **continuous** polyline, lateral offset ±0.475w·prof. When `noise(k·1.9, i·0.09)` drops below `dry·q^1.2·0.95+0.05` it breaks, and the paper showing through is the feibai.
- Pitfall: the first version stroked each little segment separately with round caps, and the joins piled up into dark beads that looked like bamboo nodes or rope. It has to be one continuous path per bristle, with butt caps.
- Parameters: window frame w14–18, dry .45–.6; desktop w22; drapery folds w4–6, dry .3–.4, tone .78; ground line w5, dry .85, tone .35.

**Wash layer `washLayer`**
- The shape is drawn to a scratch canvas first, then multiplied onto the paper, in two passes.
- Outer halo: `blur(halo·(0.4+grow))`, α = haloA·grow.
- Body: `blur(blur·(1.6−0.6grow))`.
- grow runs from 0 to 1 over lt: the opening bleeds in from nothing, after which the halo keeps slowly widening — that is "ink spreading on paper".
- Girl halo 12, α.6; cat halo 9, α.78; distant mountains halo 14.

**Reserved white (liubai)**
- The cat's white parts (muzzle, chest, paws) are cut out of the ochre layer with `destination-out`, exposing the paper colour. That reads more like ink painting than painting them white.
- The girl's cross-collar inner garment is cut out the same way.
- The face is filled with paper colour, then outlined with a 1.8px burnt-ink baimiao line.

**Colour**
- Ink `[16,14,12]`, split into five tones via tone (burnt .9 / dense .8 / heavy .6 / pale .35 / clear .15).
- Ochre (cat) `#c47a3c`; indigo (garment) `#6f8aa0`, wide sleeve `#7d97ab`; gamboge (blonde) `rgba(226,170,52,.75)` multiply.
- Rouge appears in only three places: sash, hairpin bead, lip dot, using `[190,40,40]`. Also vermilion sun `#d8553f`, seal `#c4281e`.

**Motif animation**
- **Opening write-out**: lt 0→0.45, each stroke `reveal = ss(d, d+l, lt/0.45)`, appearing in the order window, desk, bamboo, cat, figure.
- Bamboo: segmented pale-ink main stalk, swaying about (835,70) with `sin(2.9t)·0.11`, more toward the tips. 5 groups of `ge-zi` leaves, 3 each (L110, w15), flipping with `sin(7t+g)·0.2`.
- Mist bands: 4 paper-coloured ellipses, blur 14, α.72, drifting at 150–270px/s, so the distant mountains come and go.
- Bada-style bird: skims past from the right of the window at 420px/s, two strokes for the wings, about 8 flaps per second (`sin(52·lt)`).
- Qi Baishi shrimp (two in the hanging scroll, 1.45×): 6 pale-ink segments + one burnt-ink stroke over the head/thorax shell, two long and two short antennae as travelling waves, three-segment long claws, body flex `sin(7t)·0.12`, swimming along a curve.
- Bada white eyes: the cat's pupils are pushed to the top of the eye sockets, "white eyes to the sky".
- Seal: lt 0.3–0.4, pressed from 1.5× down to 1×, multiplied on; intaglio characters reading "Bai Shi".

**Pitfalls**
- Static strokes are drawn live during the write-out, then cached once into `ink_static`, otherwise thousands of bristles would be drawn every frame.
- The first version's bird path ran through the bamboo leaves and was invisible; moving it above the mist bands at y≈470 made it readable.
- The wash uses multiply, which is transparent, so the window-sill ink line shows through the cat's ears and the table legs show through the skirt — review read it as "the layering is wrong". The fix is to patch a layer of paper colour into the silhouettes of the cat and the dress first (clip, then drawImage the paper), then lay the wash on top. That is equivalent to "reserving that area on the paper first".

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
