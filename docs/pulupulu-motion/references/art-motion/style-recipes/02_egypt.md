# 02_egypt · 1350 BC Egyptian Tomb Painting (code-only)

File: `scenes/02_egypt.js` (about 460 lines). Performance: warm max 20.7ms / mean 10.5ms (1920×1080); `init()` prewarms the cache at boot, so the first frame no longer stalls for 170ms. Determinism check passes.

## Pipeline
1. **Static layer `eg_static` (cached once)**: plaster wall → hieroglyph columns → window (cornice / color-block frame / white ground / Aten sun disk / uraeus serpent) → pottery jars ×3 → offering table and offerings → gold chair → blue bowl → ground line and multi-band frieze along the bottom → deep blue band → color-block borders on top/left/right.
2. **Animated motifs (drawn every frame, cheap)**: flowing water glyphs, Aten rays with the little hands at their tips opening and closing, two long rays reaching in front of the cat to hold the ankh, the scarab pushing the sun ball.
3. **Characters**: redrawn in the Egyptian convention; RIG.drawGirl/drawCat are bypassed, taking only the anchors and the choreography.
4. **Mural surface**: `eg_surface` mottling layer composited `multiply` over the whole frame + `P.grain` + 6 random-walk hairline cracks (the cracks live in the surface layer, so they cross the figures — like real wall ageing).

Egyptian wall painting is "no perspective, flat fill, contour line", so **no brush renderer is used here**, and the lines do not boil either (clean 2.2–2.8px dark-brown lines `#2a1810` are what reads as authentic). Period feel comes entirely from convention (profile face with frontal eye, frontal shoulders) + palette + pattern density.

## Palette
Wall `#eadcb8` → mottled shadow `#d8c597`; four-color border red `#b8322a` blue `#2a58a8` yellow `#e2b13a` green `#2e8a55`, cream between blocks `#f2ead6`, black seam `#231a14`; gold `#e0ab38`/dark gold `#a8741c`/bright gold `#f3d27a`; deep blue band `#1c2236`; column divider red line `#9a2b22`; Aten sun disk `#c8372b`, rays `#c23a2a`, little hands `#b4452c`; skin `#e6b282` (the pale yellow ochre of Egyptian women); cat orange `#e08a3c` stripes `#b45a1c` white `#f6efe0`; scarab lapis `#2c56b0` + turquoise `#3fa6a0`.

## Hieroglyphs (the strongest period cue)
- **24 glyph functions** are written (ankh, sun disk, bread, reed, owl, falcon, heron, horned viper, Eye of Horus, cartouche, scarab, seated figure, leg, arm, basket, house, three verticals, feather, djed pillar, shen ring, jar, lotus, nfr, mouth, water), each drawn with 10–20 strokes inside a ~50px box, carrying its own candidate colors. Line width 3.1 (about 3px after scaling), `round` caps.
- Column layout measured off the source: left 3 columns x=78..306/y=66..566, upper middle 4 columns x=852..1172/y=66..452, right 4 columns x=1560..1866/y=252..882, 1 column left of the cat x=298..366/y=614..886.
- Layout: seed `U.rng(1350)`, filled column by column downward, glyph scale = column width/78×(1.0–1.14), spacing 6–11px; **no adjacent repeats within a column, the same glyph ≤3 times per column, scarab/water down-weighted 60%** (the first version had no limits and the screen ended up covered in scarabs, like stickers).
- The layout is computed at module init and the positions stored — that way the water glyphs can stay out of the cache and be drawn separately each frame. At least 6 water glyphs are guaranteed.

## Motif animation (all driven by lt/t only, deterministic)
| Motif | Method | Numbers |
|---|---|---|
| Scarab pushing the sun ball | x(lt)=800+642·(lt−0.394), measured from the source at 10.7px/frame; modulo 2160 to loop; ball roll angle = ball center x/radius; two leg poses `floor(lt*15)%2` (changes every 4 frames at 60fps) | Whole thing ×1.22, ball r=23×1.22 |
| Aten little hands opening/closing | open=0.5+0.5·sin(2π·lt/0.4+k·0.9), finger spread (0.1+0.24·open) | Period 0.4s, 13 inside the window + 2 outside |
| Ray micro-tremor | tip x+=3·sin(7t+1.3k), y+=2·cos(6t+k) | ±3px |
| Flowing water glyphs | zigzag phase = floor(lt·12)·0.5, 12fps stepping, 4 steps per cycle | 0.33s/cycle, like hand-painted frame by frame |
| Cup raise | `cup = lerp(0.8,1,choreo.cup)`: the source is "drinking at the lips the whole time", so only the last 20% of the lift plus choreo.sip head tilt plays | — |
| Cat | choreo.tail tail swing (RIG.cat.tailPts), blink (t≈2.18–2.30, landing on this segment's lt≈0.77–0.89), breathe upper body | — |

Motion amount: lt 0.45↔0.9 (avoiding the beat-punch zoom) gives 3.5% moving pixels, concentrated in the ray hands, cat tail, girl's head and arms, and scarab — not much, but all of it at eye focus.

## Characters: Egyptian convention
**Girl** (`RIG.girl({dy:-25})`, dy puts the feet on the y=900 ground line):
- Profile from `G.face`; **frontal eye** drawn by hand: almond white + black pupil r4.2 set against the upper lid, upper lash line 3.2px trailing 18px back (kohl tail), long brow.
- **Frontal shoulders**: the torso does not use G.torso; draw a wide trapezoid x 1270–1452 by hand (both shoulders visible, wider at the top, narrower at the bottom).
- White linen: fill skin first, then veil white at `alpha .9` → a little skin shows through = translucent linen; 27 fine bezier pleats fan from the waist to the hem (clipped to the skirt, `rgba(120,96,70,.5)` 1.3px), chest vertical pleats at 9px spacing.
- Broad collar: 5 concentric half-ellipses (blue/red/green/gold/blue, rx 50→88, ry 24→55), outer ring with 18 alternating red/blue teardrop pendants.
- **Golden braids**: clip the wig silhouette, then draw 15 vertical braids, each = 11.5px dark gold base line + 8.5px gold line + an alternating diagonal segment (herringbone) every 8px, lengths staggered at the ends. The first version paved it with small beads and looked like "golden caviar"; long strands + diagonal segments were needed to read as braiding.
- Gold headband (bezier 15px black base/11px gold/3px bright gold) + rear hanging ribbon, large gold earrings, gold armlets (gold 8px + blue 2.5px bar).
- **Cup-holding arm**: RIG's default puts the hand at the cup's side and the shoulder mid-torso, so the elbow swings far out. Changed to "hand supporting under the cup (at the foot)", shoulder moved to the front shoulder (1282,476), `RIG.ik2(sh, hand, 140, 160, -1)` so the elbow drops to chest height.
- Blue lotus cup: petal-shaped body + three pale-blue petal lines + foot, following G.cup's position/tilt.

**Cat = seated Bastet** (`RIG.cat({dy:-5})` for headC, tailPts, blink, breathe; body drawn by hand):
- Silhouette: upright chest + round haunches, **forelegs inside the silhouette**, one white mass from chest to front paws, then two lines dividing the two forelegs + toe lines. The first version drew the forelegs as two separate white columns, like bowling pins.
- Head turned in profile + tall pointed ears + frontal almond eyes (yellow `#e8cf4a`, vertical pupils, black liner tails), white muzzle, whiskers, gold earrings.
- Collar clipped to "body ∪ head" (`Path2D.addPath` to merge), otherwise the round-head stroke pokes out at the neck; Eye of Horus gold pendant.
- Orange tabby: 9 stripes on the back, 4 on the thighs, 5 deep-orange arcs on top of the head, one cross-band every 3 tail sample points, white tail tip.

## Pitfalls hit
- selfcheck's 0.2↔0.7 diff reports "the whole frame is moving" in this segment — that is the engine's beat-punch zoom (lt<0.36s), not the scene moving. To see real motion, compare two frames at lt≥0.4.
- `P.texture` takes about 170ms the first time; prewarm it in `init()` (called at engine boot), otherwise it stalls on the first frame of the T01 transition.
- The rubble chunks in the source ref are transition residue, not picture content — do not copy them (they are absent from the design sheet too).
- The year-plate area 1500–1890×40–210 keeps only wall; the right hieroglyph column starting at y=252 avoids it exactly.
- Review rework: at native size the cat's ear tips sit at y≈530, pressing onto the window frame's bottom color block (y 530–560) as if the head were shoved into the frame. Changed to anchor at the feet (540,898) and shrink the whole cat to 0.85 with a canvas transform (RIG.cat still s=1); ear tips land at y≈585. The tips of the two long rays are converted with the same transform via `catPt()`, so the little hands still land on the cat's head/muzzle. The back line and haunches were shifted forward 12–20px to make the Bastet sit taller. **Lesson: aligning the cat, the human and the window frame each to the standard composition frame is not enough — those two frames sit very close at y≈540–600, so any part that exceeds the skeleton frame (like taller ears) must be checked separately for clearance against neighbouring objects.**

## Rework v2: Egypt read as too static (shot-review report item 3)
Metric: whole-film renderFrame, still segment frames 112–140, 480×270 per-frame mean absolute difference (counter masked out). **Before 0.32 → after 0.84 (source 0.90)**, performance warm max 21.7ms.
- **Cup-raise loop**: at lt<0.35 follow choreo and lift to the lips; after that, one loop every 0.6s `cup = 1 − 0.46·(1−cos 2πu)/2` (cup drops from the lips to 0.54 and lifts back). While the cup is at the lips, add head tilt `sip += 0.3·clamp((cup−0.78)/0.22)·(0.65+0.35·sin 13lt)`, head tilt up to ~0.2rad. This item contributes the most.
- **Inscriptions being written**: every 0.12s pick 6 glyphs from a shuffled table (seed 77, across all columns): first erase with a sub-rectangle of the wall texture via `drawImage`, then stroke the glyph with `setLineDash([p·95, 999])` (each subpath's dash starts from its own beginning, so it looks exactly like stroke-by-stroke writing), with filled parts appearing only at p>0.55; the ink color settles from bright gold `#f6c846` back to its original color, with a 10px gold shadowBlur afterglow, finishing in 0.36s. About 18 glyphs are being written at any moment.
- **Aten pulse**: period 0.45s; ray lengths ±9% in sequence along the fan (phase −0.55k, like a wave sweeping through), line width 2.2→3.8, little hands scale 0.9–1.2 overall with finger spread 0.03–0.45; a gold glow and bright ring pulse outside the sun disk, and the disk is redrawn on top of the glow to keep it red. Little-hand coordinates are clamped inside the window (x 428–752, y≤512), otherwise stretching clips half a hand off at the frame edge.
- **Cat**: tail amplitude `tail·2.1 + 0.25·sin 9.5t`; both ears twitch quickly out of phase (once every ~0.38s for 0.1s, rotating 0.32–0.38rad about the midpoint of the ear base).
- Lesson: fine-line motifs like the Aten rays and water glyphs barely register in a 480×270 frame diff. **To measure "visibly moving", you need local motion with enough area** (arm + head, whole-glyph erase-and-rewrite); fine-line swaying is decoration only. The first version pulsed the sun disk with translucent orange on top of it, which washed the red disk to orange at the peak; the fix was a glow outside the disk plus a bright ring.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
