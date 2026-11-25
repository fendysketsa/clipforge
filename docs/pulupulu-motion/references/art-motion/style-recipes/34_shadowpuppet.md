# 34_shadowpuppet · Chinese shadow puppetry

> Source: migration test D (an independent agent implementing straight from the read-only skill, 2026-10-04). After integration the scene code was ported to `scripts/art-motion/engine/scenes/34_shadowpuppet.js`.

File name at experiment time: `scenes/r3_piying.js`, about 121ms per frame (each leather piece gets its own offscreen pass, so there are many multiplies).

**Pipeline**: the shadow screen (radial warm light from the oil lamp behind it + screen wick hotspot + 3px cloth weave, weave cached) → props layer (window lattice, table, vase of flowers, square-backed chair, cached) → butterfly → cat → girl, one offscreen layer per group → each layer first stamps an offset soft shadow, then multiplies the body → rivets → control rods → wooden frame.

**Key parameters**
- Puppet-piece function `piece(g, path, col, carve)`:
  - Fill.
  - Carve the pattern with destination-out inside the clip.
  - Inside the clip, stroke a same-colour "leather edge" 2×edge wide, so the carving can never cut through the outer contour.
  - Stroke a 2.6px dark-brown edge #3a160a.
- Carving library:
  - Roe-pattern dots: s14–22, r3–3.5.
  - Rosette flowers: 5 elliptical petals, s36–46.
  - Cloud scrolls: small Archimedean spirals, line width 3.4, s24–40.
  - Lattice squares: s26–32.
  - Carved lines: line width 3–7.
- Stamping onto the screen: `stamp(layer)` first multiplies at α0.28 with blur 6px and offset (7,5), standing in for the ghost the piece casts when it does not sit flush against the cloth; then multiplies the body. Transmission = screen colour × leather colour, so overlapping pieces darken naturally.
- Colours: red #c0352a, green #2f7d4c, amber #d99a2e (blonde hair = amber leather), yellow #e2bd4a, blue #2c5a8a, orange #d9782a (the cat).
- Screen: radial #fff6d6 → #f2d7a0 → #cf9a58 → #7a4a20; flame disturbance `fl = 0.5·noise(3ts) + 0.3·noise(9ts)`, with ts stepped at 15fps. The light centre drifts ±26/±18px, the hotspot radius is 260+40·fl.
- The female lead's "hollow face": once the hair is drawn, destination-out the whole face, stroke only the face contour, then add the phoenix eyes (long upswept upper line + lower lash line + pupil dot), willow-leaf brows and a dot of lip colour.
- Mapping the orange-and-white cat: orange = orange leather; white chest, white muzzle, white legs and paws = **cut the whole area away, leaving only the leather edge**; tabby = carved lines. This holds for every silhouette / cut-out style: white areas are simply cut out.
- Motion:
  - The whole girl sways about (1260,930) by ±0.012rad; the head turns about the neck rivet by ±0.06.
  - Lifting the cup is stepped at 10fps.
  - Slack wrist: dangle = 0.35·sin(11·ls)·(1 − 0.6·cup); the cup swings along with the hand.
  - The cat's head nods about the neck by 0.1·sin(6ts) + 0.05.
  - The tail is 4 hinged segments, each rotating relative to the one before by 0.3·sin(7ts − 0.9i) + 0.38, the whip tip lagging segment by segment.
  - The dangling hairpin's bead strings swing.
- Rods: 5px dark-brown lines, blur 1.2px multiply, running from the neck, wrist, cat's back, cat's head and butterfly down to the bottom edge of the frame.

**Motif animation**: the flame makes the light pool on the whole screen jump, the butterfly (wings flip via scaleX at 12fps, rod attached), the wrist swing, the cat's nod and tail whip tip, the hairpin. Motion area 6.8%.

**Pitfalls**
- Table legs lying over the skirt: after multiply, red × green is close to black and becomes a black trapezoid. Darkening at overlaps is correct in shadow puppetry, but do not put the overlap on the visual focus — just move the table legs off it.
- The first version of the cat's front legs was one solid orange rectangle that covered the white chest. Only two almost fully cut-away white legs let it read as "orange and white".
- Rods crossing the main body read as clutter: run a rod down and out from the piece, never across another character.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
