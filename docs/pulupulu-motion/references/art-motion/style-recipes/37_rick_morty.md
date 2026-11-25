# 37_rick_morty · Rick & Morty flat outlined cartoon

When the shot table uses a code-drawn character, write `Style: 37_rick_morty flat Rick & Morty-style cartoon` and `Character: original semantic SVG character`, which enables the narrow exception in the character check; `y4` still needs a frame library.


Source: an SVG single-frame reproduction and animation experiment on 2026-10-14. The 36th style banked; the internal ID is 37_rick_morty, to avoid overwriting the existing 36_picasso_blue. It is a stand-alone style; crossing into other schools is only an optional narrative.

## First checks before you start

- This case is an SVG pipeline; it cannot be added straight into the Canvas engine's eras.js or recorded as Canvas through the ordinary render.py, or the SVG characters go missing. Use this case's render.py to screenshot the whole page, or export the video first and then wire it in as an engine clip. The old 35-style gallery and the overview image stay as they are; this case previews on its own.
- The example contains only a code-drawn room, girl and cat, and depends on no screenshots from the film, no Rick/Morty character assets and no audio. When migrating to new subject matter, keep the drawing method and re-stage the scene.
- This style permits drawing characters as semantic SVG against an explicit reference, which is a narrow exception to the existing "characters come from AI-generated frames" route; it does not extend to live-action portraits or arbitrary chibi characters.

## A runnable starting point

Copy the whole `scripts/art-motion/engine/reference_films/rick_morty/` directory into the project. Opening index.html directly gives offline preview, playback and time dragging. No Node, API or web fonts are needed.

```sh
uv run --with playwright playwright install chromium
uv run --with playwright python render.py --stills 0,1,2 --out verify
uv run --with playwright python render.py --from 0 --to 8 --fps 24 --out style36.mp4
```

Video export additionally needs ffmpeg. The entry point defaults to 8 seconds of silence, and --to can specify a longer duration. The per-frame interface `window.seek(t,state)`: t is a non-negative number of seconds; omitting state auto-lifts the cup and shifts the gaze; passing state takes full control of the performance. state contains `look:[x,y]`, `catLook:[x,y]` (each axis -1..1), `sip`, `catJump`, `gBlink`, `cBlink` (all 0..1). seek does not accumulate state, so out-of-order rendering works; automatic blinking and tail-wag depend on t.

Division of labour between the files: svg-kit.js provides rounded outlined primitives, curves and seeded textures; room.js draws the layered characters and the scene, with the colours gathered in the C object; index.html handles preview and seek; render.py handles whole-page per-frame screenshots and encoding.

## Drawing method and motion

1920×1088 native coordinates, viewBox `0 4 1920 1080`. Outline #222323, 2.35px by default, round caps and joins; detail lines 1.6–2.6px. Warm grey wall #cdbf96, wood floor #9b7752, skin #efc4a0, sky #a7d6ea; hard-edged flat fills, a few dark planes in the same colour family, low-contrast mottling kept in the background. Characters and props share one outline; do not patch in texture with realistic lighting.

The face rests on contour proportion, the eyelids and a few curves for the mouth; large eye whites, small dot pupils, no glossy glass eyes with highlights. Hair spikes use mixedPath, cheeks and limbs use smoothPath. Body, head, arm-cup, eyelids and pupils are grouped; fix the still frame first, then move it with the existing anchors. The tail generates a closed contour from a centreline + width; never swap in a random shape per frame.

Default performance: the cup lifts slowly, the head turns through a small angle, the gaze drifts, deterministic blinking, cat tail-wag. catJump is a sine airtime progress, and body and tail share the displacement; there is no landing squash and no walk cycle. During the cup lift the shoulder anchor stays where it is and the cuff follows the cup.

## Migrating from a reference frame to other scenes

Test composition and occlusion first, then take the median colour of a region; thresholding dark outlines to cut out connected colour blocks can help locate coordinates, but auto-traced paths must not be taken as the character skeleton. Group hands, eyes, face, hem and furniture semantically; the still frame is frame 0 of the skeleton. Walking needs toe-driven two-bone IK with the phase advanced by actual distance travelled; this case has no walk rig, so it cannot be used to claim that walking works for arbitrary characters.

A front-facing character moving sideways scissor-legs easily: widen the base between the feet, shorten the stride, turn the gaze instead; do not mirror a character wearing asymmetric clothing. Sort ground objects by the y of the foot/base, and clip wall texture with a matching shape. When SVG and Canvas share a page, isolate the modules with an IIFE; an SVG filter's userSpaceOnUse region takes real canvas coordinates and must not be written as 0,0,1,1.

## Verification and feeding back afterwards

The bundled render.py uses Chromium's `--disable-partial-raster` to avoid the anti-aliasing differences that SVG partial rasterisation brings. Independent re-check on 2026-10-14: under this configuration, a cold start and the out-of-order frame grabs of [1,7,1,1,0,1] gave a 0-pixel difference in the t=1 screenshot; an ordinary browser only guarantees a deterministic DOM state, so identical screenshots pixel for pixel cannot be claimed.

After every change, verify at minimum under the rendering configuration above that a cold start and an out-of-order seek are pixel-identical at the same instant, that the frame changes between two instants, that there is no cropping at 0 and at the maximum expression, and that the browser reports no errors; then check the head-body seam and the eyelids by eye. Example quality is provisionally ★★: it runs, but the modelling and the complex motion still have room to improve; the contour score from the original garage reproduction must not be transferred to this room as its similarity score.

Read this card's shortcomings before use; write new findings back into the card with the date, scene, evidence and verification status. When an old conclusion stops holding, revise the original sentence first, and do not upgrade a single experience into a whole-style rule; for a fault that reproduces reliably, fix the code first and test for determinism.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
