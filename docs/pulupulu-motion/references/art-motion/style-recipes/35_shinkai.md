# 35_shinkai · 2016 Shinkai light and shade

> Source: migration test D (an independent agent implementing straight from the read-only skill, 2026-10-04). After integration the scene code was ported to `scripts/art-motion/engine/scenes/35_shinkai.js`.

File name at experiment time: `scenes/r4_shinkai.js`, about 71ms per frame.

**Pipeline**: realistic interior (cool-warm gradient on the walls, perspective floorboard seams, aluminium-framed window, wall calendar, desk, cached) → sky + cumulonimbus + utility poles and wires + distant rooftops + contrails + birds → water beads on the glass → white gauze curtain → window-shaped light patches on the floor and the wall (with the curtain's shadow swaying inside the wall patch) → potted plant → cat, girl (cel, cel) → heat haze → Tyndall shafts + light dust → lens flare → bloom → soft-light cool/warm separation.

**Key parameters**
- Cel function `cel(c, p, base, shade, rim, {sd, rw, lx, ly})`:
  - Shadow = clip(p) ∩ ¬(p translated by (lx·sd, ly·sd)). Implemented with evenodd: one large rectangle + the translated p, used as the clip.
  - Rim light = clip(p) ∩ ¬(p translated back by rw).
  - The light comes from the window, lx=−1, ly=−0.55, so shadows fall on the lower right. sd: 22–30 for large parts, 10 for the face, 8 for small parts; rw 3–9.
  - Line colour #6a4632, line width 2.2. Drawing each part in the order "fill → shadow → rim → line" makes occlusion correct by itself; visibleLines is not needed.
- Under the window the cat is backlit: lx=0.5, ly=1, the dark side underneath, plus a lighter warm rim rgba(255,220,160,.55) along the top of the head and the back.
- Colours: skin #ffe8dc/#f2b6a8; blonde #f8d681/#d8a050; white school uniform #fbfbfe/#b9c3dc; navy #2c3a66/#1b2446. Angel ring: a 9px bright arc rgba(255,250,226,.85) behind the head.
- Animation eye: white 8×12, iris with a vertical gradient #1f3f7a → #3f7fd0 → #9fd4ff, two highlights, upper lid 3.4px plus one lash at the eye corner.
- Cumulonimbus: 70+12 puffs. ① draw every puff as a blue-grey silhouette (linear gradient #b7c6e6 → #8297c6) ② for each puff draw a white radial ball of 0.82r offset toward the sun at (+0.22r, −0.3r) ③ blur the whole layer 3px, then composite a 55% sharp layer. Each puff's radius breathes with 0.05·sin(1.3t), and the whole mass drifts at 10px/s.
- Glow:
  - Sun core: r130.
  - 10 star rays: length 90/170, rotating at 0.25rad/s.
  - Horizontal streak: 840×4.
  - 5 hexagonal ghosts: on the line from the sun to the frame centre at 0.45/0.75/1.25/1.6/2.0 times the distance, α 0.04–0.12.
- Tyndall: 3 wedges, blurred 18px then cached, screen, α 0.75 + 0.25·sin(3.4t). 60 dust motes, radial gradient, flickering.
- Bloom: draw the whole frame into a 480×270 canvas → blur 6px, brightness 1.1 → scale back up and composite screen at α0.28.

**Motif animation**: the cloud mass churning and drifting, contrails, a flock of birds flapping, one water bead sliding down the glass (leaving a trail), the gauze curtain and its shadow on the wall swaying, the potted plant's leaves swaying, hair strands blown by the wind, the star rays rotating, the shafts brightening and dimming, dust motes. Motion area 3.0%.

**Pitfalls**
- With the sun placed on the corner of the window frame, the glow spills onto the wall and looks like a lamp hung there. The sun must sit inside the glass, glow radius ≤130.
- The first version of the clouds gave each puff a radial gradient and then stroked a "lit arc" around it, and the result read as a pile of soap bubbles. You want "silhouette + offset bright ball + blurred/sharp two layers".
- The first full-frame horizontal streak was 1800px long and looked like a bug line. Trimmed it to 840px near the sun, α0.35.
- A water bead drawn as a solid circle floats in the air like a bubble. Draw only the lower-rim arc, a transparent body at α0.22 and one highlight dot.
- A variable-name collision (two `const cg`) made the whole scene fail to load, and it was silently swapped for the placeholder frame (see ② item 1).

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
