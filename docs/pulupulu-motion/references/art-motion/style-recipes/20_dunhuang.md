# 20_dunhuang · Dunhuang murals (Mogao Caves, High Tang)

> Source: migration test A (independent agent working from the skill alone, 2026-10-04). Scene code was ported after integration to `scripts/art-motion/engine/scenes/20_dunhuang.js`.

Filename at experiment time `scenes/04_dunhuang.js` (215 lines). 0.45↔0.9s is 6.6%, adjacent-frame median 1.98%.

**Pipeline**
Earth-red ground layer (cached): `P.texture #a5452f`, dark `#7a3020`, plus sparse faded rosettes, a scroll border along the top + triangular valance (alternating green/white/red + gold beads) → window = azurite sky: auspicious clouds, a flying apsara → scroll-pattern window frame → lotus-brick floor (cached) → humen low table, oil lamp → cat → girl (Tang donor figure) → steam scroll-clouds → ceiling flowers → overlay pass.

**Line and colour**
- Iron-wire line (tiexian miao): constant 2.6px, colour `#5a2414`. The face uses a redder `#8a3a24`.
- Mineral colours: earth red `#a5452f`, malachite `#3f8f6e / #6ab08e`, azurite `#2f5f8f / #5a86b0`, white `#ecdfc4`, gold `#d8b05a`.

**Tang costume**
- Striped skirt (jianse qun): red ground, diagonal trapezoid green stripes every 44px, fanning wider downward with x.
- Azurite short jacket, white cross collar, high-waist red sash.
- High bun: two ellipses stacked above headTop, plus a gold hairpin and three hair flowers.
- Face makeup: huadian (four-petal red flower on the forehead), xiehong (a red arc at each temple), lip dot, moth brows.
- The teacup is Yue ware celadon.

**Shawl (pibo) `shawl(pts,w)`**
- Travelling-wave point list → ribbon, with white dashed floral strokes and red dots.
- Rear section: `x = back + 230q + 64q·sin(4.2q − 5.5t)`, the last 30% lifting upward.
- Front section drapes down around the arm.
- Pitfall: the first version's lateral amplitude was only 18–34px and almost vertical, so it looked like a chair's upright. Lateral displacement has to exceed 200px, plus the upward lift at the end, before it reads as silk in flight.

**Apsara (feitian)**
- Lying horizontal facing left, 1.35×, flying past the window at 300px/s.
- Three ribbons as travelling waves; one arcs from the shoulder over the head and flings behind — that big arc is the apsara's most recognisable form.
- Halo, hair bun, flower tray.
- Auspicious clouds are round blobs with tapering tails, drifting at 40–76px/s.

**Overlay (aging)**
- Whole image `saturation` blend at α.3 to desaturate, then multiply a pale earth texture at α.5.
- Per-pixel flaking: where `fbm(x·.0032)+0.12·noise(x·.03) > 0.3`, expose the whitish-grey ground `#d8c6a2`; 0.28–0.3 is the dark line at the flaking edge.
- The areas near both faces are set as protected zones, no flaking.
- 500 craquelure lines random-walk; soot gradient over the top 380px.
- Pitfalls:
  - At noise frequency .006 the flaking came out as sesame speckle across the whole screen, like dirt. Dropping to .0032 and raising the threshold gives discrete patches.
  - The final version sets both the cat (380–720, 530–920) and the girl (1070–1530, 240–950) as protected zones, flaking only the background.
  - Xiehong α down to .32, otherwise it looks like a scar.
  - The apsara's halo was a solid green circle in the first version and read as a "swimming ring"; changed to α.28 translucent with fine lines.
  - With `#c8843a` the cat turned brownish-yellow once desaturated; changed to `#e08a3a`; added `look: sin(2.6t)` head turns and 2.5× more breathing, otherwise only the tail moved for that whole segment.

**Motif animation**
- Ceiling: 30 four-petal flowers, rotating and flipping as they fall.
- Oil lamp: flame flicker `1+0.12sin(17t)+0.08sin(29t)`, plus a glow.
- Paint flakes: 10 flakes detach from flaking edges, flipping and falling on parabolas.
- The bell on the cat's collar swings.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
