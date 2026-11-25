# 23_dali · 1931 Dalí Surrealism (The Persistence of Memory)

> Source: migration test B (independent agent working from the read-only skill, 2026-10-04). After consolidation the scene code was ported to `scripts/art-motion/engine/scenes/23_dali.js`.

Filename at experiment time: `scenes/c2_dali.js` (about 235 lines). Median 47ms per frame (first frame 84ms); frame difference 4.6%.

**Pipeline**
1. The base plate is split into three caches because the shadows have to sit in between: `dali_bg` (sky, sea, rocks, ground) → shadows drawn every frame → `dali_wall` (broken wall fragment with the window opening + dead branch) → `dali_block` (stone slab table + stool) → soft clocks → character.
2. **Volumetric fill `vol(c, path, x0,y0,x1,y1, a, b, occl, blur)`**: a linear gradient fill, then inside a clip a dark rim is stroked with shadowBlur to make the inner shadow. There is no line art anywhere in the film; the academic roundness comes entirely from this.
3. **Long shadows**: each object's silhouette is projected onto the ground with a shear affine, `setTransform(1, 0, −kx, ky, kx·yg, yg·(1−ky))`, where yg is that object's ground contact line (wall 700, table/cat 905, figure 930). All silhouettes are first drawn into one offscreen (pure black), then composited as a whole at α 0.55, blur 1.5px, so overlapping shadows don't darken. A clip keeps only the ground portion (y > 594). `kx = 0.85 + 0.6·easeInOut(lt/1.2)`, so the shadows visibly lengthen over 1.2s.
4. **Soft clock `softMap(o, sag)`**: disc local coordinates (u,v) → screen. The part with v ≤ fold lies on the tabletop (y compressed to 0.28–0.32); the part with v > fold hangs down: `X = cx + u·(1 − flare·q)`, `Y = … + d·(0.62 + 0.3·sag) + central sag Gaussian + sin ripple`. The outer frame, dial, 12 ticks, two hands (sampled along the mapping into soft lines) and the fold highlight **all go through the same mapping**.

**Key parameters**: `flare = −0.12`; a negative value makes the hanging part splay outward like soft cloth, with a round lower edge; a positive value pinches it into an ice-cream cone. drip 0.18–0.4. sag goes from 0.1 → 1.4 within 1.2s: the first version was 0.35→1.0 and review said "the clock isn't visibly dripping". Three clocks: windowsill R72, table edge R88, dead branch R64 (fold −34, mostly hanging). Hand speed 4.5–6.5 rad/s.

**Motif animation**: the three soft clocks keep sagging while the hands turn at different speeds; the stilt elephant on the horizon (four thin legs stepping alternately with π/2 phase offset, knees bending slightly at 0.52 height, body jittering at 14Hz, obelisk on its back) moves left 70px per second; 9 ants crawl in ellipses around the orange pocket watch; the long shadows lengthen; the cat's tail softens and droops (tip y + q²·34).

**Character**: Spanish girl, pale blue long dress + white collar, blonde bun, no line art, volume from gradient + inner shadow, features in thin dark brown lines. The cat uses gradient orange, stripes with a blur 2px semi-transparent brush (soft), eyes with a radial gradient; the white chest switched to a smooth ellipse (606,768) 40×92 instead of `K.white`.

**Palette**: sky `#22407c → #5f88bd → #e9dcae`; sea `#8aa6b8 → #4f6f86`; rocks `#e8c27a / #9a6a34`; ground `#d2ad70 → #7a5129`; wall `#f4ead2 → #cdbf9f`; clock gold `#f0d27c / #9a7426`, dial `#f6efd6`.

**Pitfalls**
- The first shadows were cast toward the viewer (ky>0, downward) and were all eaten by the bottom edge of the frame. The sun has to sit low in the front left so the shadows lie back to the right (y′ = yg − ky·(yg − y)).
- Shadows fall on the ground and must be drawn beneath the wall and table, so the base plate has to be split into layers — one cache all the way down won't work.
- With flare>0 the soft clock's drip grows and it becomes an ice-cream cone.
- This counter's backing colour is deep blue sky, and the dark brown lettering originally set was invisible; changed to off-white letters + dark drop shadow.

**Still improvable**: the figure is still rather vector-illustration; finer highlights and reflected light in the dark areas could be added; the reclining soft "self-portrait" creature from The Persistence of Memory could serve as a fourth motif.

---

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
