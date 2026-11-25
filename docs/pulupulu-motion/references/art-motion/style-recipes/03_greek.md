# 03_greek · 530 BC Attic Black-figure Pottery — Code Drawing Notes

File: `scenes/03_greek.js` (plain Canvas 2D, no images). Final self-check: warm max 15.9ms / mean 7.6ms / cold 80ms, determinism passes, 22% of pixels moving in the 0.2↔0.7s motion diff.

## The trick in one line
Black-figure = the trio of **black-glaze silhouette + incision lines + added color**. All three are required:
- Silhouette: every figure/object filled `#1b120d` (near-black with warmth), no outline; form comes from the silhouette against the clay ground.
- Incision lines: "cut through" the black silhouette with 1.5–2px fine lines in bright clay orange `#e8904c` (drapery folds, facial features, boundaries where limbs overlap).
- Added color: purple-red `#8a2a37` bands (headband, cuffs, hem, collar, cushion) + small white dots (`#f6ead6`, r≈2, spacing 11–17px).
Get these three right and it reads instantly as a Greek vase with no texture at all.

## Palette
Clay `#dc6a2f`, bright clay (vase panel) `#e8803f`, black glaze `#1b120d`, purple-red `#8a2a37`, white `#f6ead6`, incision `#e8904c`, blond `#f2bd48`, bare clay (cat white areas) `#f3cfa4`, cat orange `#f2913f`, cat nose `#e7897a`.

## Pipeline and parameters
1. **Clay ground (cached `gr_bg`)**: compute per-pixel at 480×270 with fbm(×0.016, 4 octave) mottling ±30 plus **horizontal band noise** from `noise(x*0.006, y*0.85)` (throwing rings) ±9, then upscale to 1920×1080 (low frequencies are blurry anyway, saving 16× the computation); then draw 560 random horizontal fine lines (length 150–1050, alpha 0.03–0.08, dark/light variants) as throwing striations; 420 dark specks + 120 light specks; two passes of `P.grain`; 5 cracks (one segment every 9px, ±2px jitter, with a pale bright edge offset 1px drawn under each — the crack gets thickness immediately). Add a warm radial lift of 0.16 at the center. Cold start for the whole frame ~80ms.
2. **Vignette (cached `gr_vig`)**: radial 380→1180, outer edge rgba(30,6,0,.62), the last layer over the whole frame (bands included).
3. **Static black-figure layer (cached `gr_static`)**: picture frame (18px black edge + white dot chain at 11.6px spacing + inner fine line), grapevine (sine stem + triangular grape clusters of 3-2-1 dots), table (legs with animal-paw feet), lathe-turned chair legs (formed symmetrically from a [y,w] width table as a polyline), swan-neck chair back (13px thick stroked curve + elliptical head + triangular beak), amphora (24-point symmetric contour → `RIG.smooth`, bare clay panel + a small black cat, ray pattern at the base, one vertical 0.09 sheen gradient), two blocks of Greek inscription.
4. **Greek inscription**: the font library has no Greek glyphs → hand-written **stroke table** (each letter 1–3 polyline segments, in a unit cell 0..1). Letter height 30, stroke width 3.4, per-letter height ×(0.9–1.06) random, baseline ±6% jitter, vertices ±0.7px jitter; Ο drawn as a small circle (0.25 of letter height — the source has a small o too), Ι 2px wide. The hand-painted potter's inscription feel comes mostly from "letters of unequal height + a small o".
5. **Scrolling bands**: the top key pattern (period 60px, 7px black line, unit polyline `[[4,46],[4,0],[50,0],[50,34],[18,34],[18,14],[36,14],[36,22]]` + a continuous base line) and the bottom lotus-bud chain + ray pattern (period 76px = two 38px units, odd buds filled purple-red, so the true period is 76) are each prerendered as a strip of width W+2P, and each frame runs `drawImage(strip, -(off mod P))`. Offset curves:
   - Top: `off = 22·lt + 60·easeInOut((lt−0.49)/0.35)`, to the left;
   - Bottom: `off = −(18·lt + 76·easeInOut((lt−0.477)/0.367))`, to the right.
   The source only does one easeInOut cycle jump over frames 169–191; I added an extra 18–22px/s constant drift so the motion is visible in the first 0.47s of this segment as well.
6. **Motifs inside the frame** (drawn per frame, clipped to the frame): 6 dolphins (hand-written bezier silhouettes: beak, dorsal fin, ventral fin, forked tail + belly incision line + white eye dot) swim ±9px back and forth along their own heading with angle ±0.12rad, period 0.85s, phases 1.3 apart; the whole boat bobs ±4px and rolls ±0.025rad about (560,420), period 0.9s. White sail + purple-red stitching, crescent hull + scorpion-tail stern, purple-red cabin, reclining figure.
7. **Lyre**: pivots about the peg (1050,150) with `0.09·sin(2π·lt/0.8+0.5)` (±5°, ±17px displacement at the soundbox, clearly visible within 1 second). Tortoise-shell soundbox = black circle + incision ring + 5 incised small circles.
8. **Rosette**: 8-petal black ellipse + incised petal divisions + purple-red center, rotating `lt·1.6` rad/s alternating direction.
9. **Orange-and-white cat** (hand-drawn, not RIG's default polygon; tail uses `RIG.cat`'s tailPts driven by choreo.tail): scaled 0.9 about (548,903) to land in the standard frame; orange silhouette + 3.4px black stroke; white chest/paws/muzzle in the "bare clay" cream; **back stripes take 12 points equally spaced by arc length along the back contour and draw tapered stripes toward the body center (575,800)** (length 30–48, base width 10) — far more natural than hand-placed stripes; thigh arcs, vertical stripes on the forelegs; Archaic large round eyes (white + black pupil + highlight + a brow arc above), replaced by an arc when blinking; purple-red collar with white dots.
10. **Girl**: `RIG.girl({cup,sip,breathe,s:0.97,dy:-14,hair:'long'})` — scaled down and shifted so the feet land on the ground line at 903.
    - Fill RIG's Path2D (farSleeve/skirt/torso/neck) directly for the body; replace the far hand with a small ellipse (RIG's farHand looks like a blade inside a black silhouette).
    - **Head drawn by hand**: write the Greek profile (straight nose bridge merging into the forehead, fine chin) + hair silhouette in RIG's rest coordinate system, then replicate RIG's head motion with a canvas transform: `translate(neck)·rotate(G.tilt)·translate(−neck)·T`. Compute the same matrix again with `DOMMatrix` and use `Path2D.addPath(faceSil, M)` as the clip region for the incision lines.
    - **Blond hair** (the key to reading "blond girl"): inside the hair-region clip draw 11 wavy strands over the crown (quadratic bezier + normal-direction 2.6px·sin(7πu) ripple), 8 long locks down the back (sine, 4.5 half-waves + a small spiral at the tip), a double-spiral bun, 4 small curls at the brow, two spiral ringlets at the temples (a 6px black base stroke first, then gold at 2.2px, so they stay legible even outside the silhouette). Gold lines need to be 2.5px to have enough "mass" at 1080p; at 2px the hair stops reading as blond in a thumbnail.
    - Incision lines: 16 drapery folds (clipped to the body), almond eye (pale sclera + black pupil, frontal eye on a profile face), brows, nostril wing, lips, chin. **Boundary where the near arm overlaps the body/head**: clip (body ∪ head), then trace the incision along the arm contour — black on black can only be separated this way, and the face does not turn into a smear when the hand comes up to the lips.
    - Added color: 15px purple-red hem band + white dots, cuff band (clipped to the upper arm, a 15px band along the upper-arm normal + incision lines above and below), bracelet, 8 four-petal flowers of white dots, headband.
    - Kylix (wide shallow two-handled cup, half-width 32) follows `G.cup` (tilt included), purple-red line at the rim; steam is three "≀" fine black lines, phase `t·9`.

## What moves (all visible within 0–0.94s)
Cup raise (choreo.cup lifts to the lips over 0.9s with a slight head tilt), cat tail/blink/breathe, top and bottom band scrolling (drift + beat-synced cycle jump), lyre sway, boat bobbing, dolphins swimming, rosette spinning, steam twisting.

## Pitfalls hit
- Scaling RIG's hair silhouette directly made the back of the head too wide (the first version reached x=1450 and looked like a helmet); trimmed to 1424 per the design sheet, with the long hair only falling to y≈558.
- With the cup at the lips, black hand + black cup + black face merged into one blob: ① incision boundary where the arm meets the head, ② smaller cup (half-width 44→32), ③ a purple-red line left at the rim.
- RIG's cat has its crown at y=535 while the standard frame's cat top is 610; without scaling it presses into the frame's lower edge.
- With alternating odd/even buds on the bottom band the true period is 2 units (76px), so the prerendered strip's wrap period must be 76, otherwise the colors jump every 38px.
- `P.grain`'s seed = key length, so two grain layers must have keys of different lengths or they produce the same pattern.
- **The cup-raise endpoint must be period-styled (review rework)**: RIG's cup→mouth endpoint sits near the nose tip with the cup tilted −0.45rad, which with a wide shallow kylix looks like a beak or a pipe stuck onto the face, with the hand covering the mouth and chin. Replaced with custom IK: the lip point rest(1243,391) is transformed to screen with the head's DOMMatrix, the rim center = lip point −(30,−1) (the rim's right end just touches the lips), tilt −0.08·cup (≤5°), the hand's IK target = rim + (lerp(32,6,cup), 30), i.e. supporting under the foot; `RIG.ik2(S, handTarget, 165s, 122s, −1)` + `RIG.taper` to build the upper arm/forearm. The forearm stands in front of the chest, leaving the nose, lips and chin of the profile visible. The steam follows the rim.

## v1 shot-review rework (cat switched to black-figure + more top-band scrolling)
- **The cat must be drawn the same way as the human**: a cartoon cat with big round bright-orange eyes broke the illusion instantly in a black-figure scene. Changed to a black-glaze silhouette, with "orange and white" carried only by added color and incision lines: a 26px purple-red saddle band along the back contour, a purple-red patch on the crown (46×22 ellipse clipped inside the head), black tail base + 7px purple-red core; all tabby stripes are clay-orange `#f2913f` 3px **incision lines** (14 curved lines equally spaced by arc length along the back contour, aimed at the body center + 3 on the thigh + 3 on the forelegs + one ring every 2 points on the tail); white chest/muzzle/paws in white paint `#efe1c8`, with black incised toes on the paws; eyes changed to Archaic incised almond eyes (white-paint sclera + vertical black ellipse pupil + a small incision at the outer corner), blinking is a downward-curved incision; nose purple-red; whiskers incised on the left (over the black face) and black lines on the right (over the clay).
- **Scrolling a periodic pattern a whole number of cycles = first and last frame identical**: after one 60px cycle jump on the top band, the image is exactly the same as before, so still-frame comparison or frame sampling easily judges it as "not moving". Constant drift raised from 22→48px/s (bottom band 18→30px/s) to guarantee a phase difference between any two frames.
- Whole-film still-segment motion (480×270 mean frame diff): 03_greek 1.87 → 2.02, source 2.06. Warm max 17ms.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
