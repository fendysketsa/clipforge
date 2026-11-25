# 28_monet · 1899 Monet Water Lilies + Japanese Footbridge

> Source: migration test C (independent agent working from the read-only skill, 2026-10-04). After consolidation the scene code was ported to `scripts/art-motion/engine/scenes/28_monet.js`.

Filename at experiment time: `scenes/k2_monet.js` (176 lines). About 105ms per frame, frame difference 30% (mostly the water surface boiling).

**Composition**: wall = an Orangerie-style water lily mural (a whole surface of water), window = the green Japanese footbridge (arched bridge + wisteria + pond water), green Giverny shutters either side of the window, the girl sits in front of the mural.

**Pipeline (the no. 09 benchmark structure)**
1. Base plate `moBase`, redrawn every frame, because the water lilies drift and the willow shadows sway.
   - Water: vertical gradient `#b9c7e6→#8fa6d6→#6c84bf→#5a72a8`, plus 4 pale pink-yellow skylight reflections.
   - Willow shadows: 5 vertical bands, edges undulating horizontally by `sin(0.03y−3.2t+k)·14`.
   - Water lilies: 10 clumps, about 100 notched ellipses in total (rx 38–78, ry 12–21), 40% carrying pink/white flowers.
2. 4 stroke passes:
   - Water: cell 9, len 34, w 6.5, **horizontal** angle≈0±0.06, boil 6.
   - Window view: cell 6, len 13, w 4.5, slanted strokes on top, horizontal below, boil 6.
   - Floor: cell 12, len 34, w 8, **boil 0**.
   - Window frame/shutters: cell 6, one vertical and one horizontal pass, boil 0.
   - All passes outline 0 (Impressionism does not outline).
3. **The bridge gets its own layer**: in the base plate, a dark tree-shade ground `#24452a` is laid behind the bridge first; the bridge itself is underlaid with a thick `#3f8a62` line (20px) and outlined with a bright `#8fdcae` line. Strokes use cell 5 and a 5-colour pale blue-green palette. Without this the bridge is swallowed by the foliage palette and disappears completely.
4. Area palettes:
   - water `#5b6fb5 #7d8fd0 #9db5e0 #6aa0a8 #b7a6d8 #d9c8e8 #8fb8a8 #a6c4e8 #c8b0d8` (mix .45)
   - leaves `#5f8f4a #7fae5a #3f6f4a #9cc070 #6f9a7a #b4cc78`
   - pink `#f0a0b8 #f7d0dc #fff2f4 #e88aa0`
   - floor `#c69a6a #b07a5a #d8b08a #9a6a7a #8a7aa8 #e0bc90`
5. Character: flat fill in fill mode → source-atop fine strokes (cell 6, len 12, white dress colours sampled from `#fbf8f2 #e4e0f6 #cfd2ee #f8ecd0 #d8e8f2`) → **colour shadow**: a warm yellow α.22 linear gradient over the lit side and a purple α.32 one over the shaded side (source-atop) → then only the facial features, in thin `#5a4f8a` lines.

**Motif animation**
- **Water-surface light flicker**: 160 bright horizontal short strokes (`#fffbe8 #fdf0d0 #f8e0ec #e8f4ff`). Brightness `clamp(sin(t·(5..11)+φ)·sin(2.3t+i))`, jumping horizontally ±5px at 10fps.
- Water lilies drift `x+sin(1.3t+φ)·7+6t`, willow shadows undulate, 3 ripples (dashed ellipses ry=rx·0.22, expanding and fading out).
- Wisteria: 12 hanging clusters, each 9 pale purple dots from large to small, swaying by `sin(2.4t+0.9i)·8`. The straw hat's blue ribbon flutters.

**Character**: 1899 white summer dress, high collar, puff sleeves (ellipses at the shoulders), pale blue sash, the RIG straw hat painted `#ecd28a`.
**Pitfalls**
- With full-screen 6fps boiling the frame difference was 47% — noise over the whole screen.
- The first wisteria used thick lines and came out looking like smooth pills; changed to strings of dots.
- The counter is unreadable on top of the brush strokes; it needs a creamy-white glow with blur 18.

---

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
