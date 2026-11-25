# Transition additions from the migration tests (A–D)

<!-- from migration test A -->
## Transitions (new block at the end of `transitions.js`)

| Transition | Enters | Technique and parameters |
|---|---|---|
| `goldLeaf` 0.5s | Klimt | 72px squares. Order key = distance from the girl's head (1300,380) × 0.78 + bearing angle × 0.12 + random × 0.08, so the gold leaf spreads out in a spiral. For each tile q = (1.32p−key)/0.32: while q<0.5 a gold flake drops into place from 1.3× with rotation, a gold gradient highlight moves with q, pressing over the spiral, eye-shaped or concentric dark pattern; while 0.5<q<1 B is revealed and the flake fades out. |
| `screamWarp` 0.5s | Munch | The old picture is distorted by a per-row sine, amplitude 70e. The wave front `y = lerp(−180, H+220, e) + 80sin(x·.0055 + 7p)` pushes from top to bottom; above the front is the new picture (distortion amplitude 60(1−e) gradually settling). The front presses 4 bands of 26px: `#b82a1e #e2541c #f08a24 #f4c03a`. |
| `apsara` 0.5s | Dunhuang | Front `x = lerp(W+260, −300, e) + 110sin(y·.006 + 5p)` sweeps right to left, the new picture on the right. On the front, 3 ribbons (malachite, earth red, azurite, width 44/38/32, travelling wave, white dashed flower outlines). Left of the front, fragments of the old picture (pixels taken straight from A) flip and fall along parabolas — that is "the old painting flaking off". |
| `dotBloom` 0.48s | Kusama | 58px hexagonal grid, dots grow out from the cat (540,760) in order of distance (outBack, up to 0.74× the spacing, exactly filling), with the new picture clipped inside the dots. Dots not yet filled have a white outline that gradually fades out. |

---

<!-- from migration test B -->
## Transitions `transitions_b.js`

| Enters | Name | Technique | Parameters | Per frame |
|---|---|---|---|---|
| Dalí | `melt` | The old frame sags in 4px vertical columns (`sag = 0.22·edge·e`, and stretched 0.3); the new frame sits above the liquid line edge(x), where edge = overall drop line (−160 → H+40, easeInOut) + 26 round-headed droplets (width 10–32, length 60–280, profile `(1−u²)^0.3`, each with its own start phase) + sine wave; the liquid surface is outlined with a dark edge (blur 3) + highlight | 0.36s | 86ms |
| Hopper | `sunShaft` | Old frame `multiply` cold green `rgba(70,120,110, 0.7·min(1,2p))` sinking into shadow; a slanted light block (slant 260px) sweeps its right edge across the full screen, inside it the new frame + `screen` warm light (0.45 → 0, fading out over p 0.6–1) + one window-mullion slant shadow travelling along; a bright edge on the leading edge | 0.34s | 76ms |
| Ghibli | `bleed` | 5 colour blooms open in t0 order (the window first), radius `q·1400·k`, q=easeInOut(seg(p,t0,t0+0.66)), boundary `R·(1 + 0.28·fbm(angle) + 0.05·sin 9a)`; outside, a 70px blur 18 bright halo (the water arrives first), inside the new frame, edge 5px `multiply` brown water stain. Both halo and stain α multiplied by (1−q) | 0.38s | 127ms |
| Vaporwave | `vhs` | First half old, second half new; in the p 0.38–0.62 segment a "field sync loss" rolls the whole frame up + a 40px black bar; tear bands of random height 6–54px drawn from A/B (probability of drawing B = p), horizontal offset ±130·sin(πp); magenta/cyan single-channel copies offset ±14 with `screen`; 160 snow lines | 0.30s | 88ms |

Commonality: every transition is "the physical process of the new style", not a generic wipe — melting is liquid, Hopper is light, watercolour is water, VHS is magnetic tape. When designing, ask first: "by what physical process would a frame in this style appear?"

---

<!-- from migration test C -->
## Transitions (`transitions_c.js`)

| Enters | Name | Technique and parameters |
|---|---|---|
| Monet | `ripple` | (distance denominator 1700, extra fade-in starts at p>.7, ensuring the four corners are already clear at p≈.85) The old frame is horizontally offset by a sine per 6px row strip, `dx=sin(0.045y−26p)·46·sin(π·min(1,1.2p))·(0.4+|y−cy|/H)`, like a reflection being stirred. The new frame is revealed by a clip made of 3600 **horizontal short-stroke ellipses** (length 40–110, height 9–17), rippling out ring by ring by elliptical distance to the cup (1000,600) (y×1.9). 3 pale dashed ellipses at the front, dashOffset following p; 140 water-glint horizontal lines flash in the middle. An extra fade-in layer above p>.85. |
| Seurat | `pointill` | Grid pitch 14: dots grow from 0 to r=6.4 (first 30%), the old frame under the dots fades to paper colour. Each dot's colour-switch moment `0.5·(0.6x/W+0.4y/H)+0.25·hash+0.15`, upper left first, with randomness; at the switch the dot scales up 1.35× and "jumps". After p>.6 the new frame develops under the dots, after p>.7 the dots retract. Each frame requires one getImageData on A and on B. |
| Matisse | `cutouts` | A 1100px-wide cobalt blue paper (left and right edges are sin irregularly cut) sweeps right to left, shadow (14,10) blur 12. On the paper, 260 gouache brush strokes, with pinned white/yellow seaweed (stem + 7 fingers), yellow/pink 6-point stars (rotating with p), red discs, each with a shadow. Behind the paper's right edge the new frame is already in place. |
| Haring | `radiant` | A V-shaped dancing figure, scale `s=0.15·320^easeInOut(p)`, growing from the cup as origin. First "stroke 30px black + fill black" to draw the outer contour, then on an offscreen fill the limbs white and `source-in` the new frame, giving the new frame inside the body; 16 radiating lines outside jump at 8fps; extra fade-in from p>.82. The first version's exponent was too slow (`0.08·40^…`, only 300px tall for the first 80% of the time, then a hard cut); the second version `0.15·120^…` still left a gap at the end, closable only with about 1 frame of fade-in, which the review judged a flash frame; the final version uses `s=0.15·320^easeInOut(p)`. |

**General transition lessons:**
- Transitions that need pixels (pointillism, water ripple) do getImageData on A/B each frame, about 10ms a time, acceptable.
- For transitions where "the new frame is hidden inside a shape", once the shape is a multi-segment union, do not `clip(union Path2D)`: inconsistent subpath winding cancels out into holes. Fill white on an offscreen instead, then `source-in`.

<!-- from migration test D -->
## Transitions (segment D at the end of `transitions.js`)

| Transition | New style's signature | Technique and parameters |
|---|---|---|
| `irisFilm` Rembrandt→rubber hose | 1930s cartoon iris in/out + old film | ①p<0.5: the old frame progressively gains `sepia(q) grayscale(0.7q) contrast(1+0.3q)`, the black iris closes to the cup rim (1236,420), R = R0·(1 − easeIn(q)), R0 taken as the distance to the farthest corner ②p≥0.5: the new frame springs open by R0·outBack(q) ③the circle is 48 segments, with ±1.5% hand jitter at 12fps ④film flicker, scratches and dust overlaid throughout |
| `lampGlow` rubber hose→shadow puppet | lighting the lamp behind the screen | ①old frame multiply rgba(70,34,12, min(1, 2.2p)), dimmed as if the lamp goes out ②the new frame revealed with a destination-in radial mask (solid to 0.55R, transparent at the rim), R = 1500·inOut(seg(p, .12, 1)), with ±7% flame flicker ③`lighter` warm halo sin(πp) plus one small flame |
| `flareSweep` shadow puppet→Shinkai | light leak, light sweep | A slanted (k=0.35) dividing line sweeps from −500 to W+700 (inOut). New frame on the left, old on the right. On the divider, 3 layers of `lighter` light bands: 520 wide α0.55 warm, 160 α0.85 white, 60 α0.6 cyan. Plus horizontal streaks, 40 light particles, 3 hexagonal light patches |
| `blueBrush` Shinkai→Blue Period | colour drained out + broad dry brush | ①old frame `color` blend with rgba(45,90,148, min(1, 2.2p)), leaving only blue; then multiply to darken ②6 broad strokes (each H/6+90 tall) alternately tilted ±18, brushing left to right in turn, start times staggered by 0.07. The brush head is a quadratic curve segment, top and bottom edges with 6–7px sine jitter ③within 80–280px behind the brush head, 26 dark/light gradient bristle lines (the paint not yet brushed even) |

General steps for designing a transition (suggested for layer 3 of no. 02): find the physical process in the new style that will "appear, light up, sweep across" → use it first to "contaminate" the old frame → the new frame emerges from the shape of that process → overlay a brief highlight or overshoot at the hit point.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
