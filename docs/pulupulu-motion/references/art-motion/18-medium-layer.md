# 18 · The medium layer: same scene, different way of painting, character repainted with it

When to read: when making a film where "the same scene passes through many ways of painting" (art-history speedrun, time-travel kind), or when some way of painting has to reach the point where "every stroke is really painted", or when you want an already-drawn character to walk into different painting styles without generating new images.

Conclusion first: split the scene and the way of painting into two separate processes. The scene states only "what colour is here, who does it belong to, which way the brush travels"; the way of painting is the other process, which paints stroke by stroke from those three things. Once split, one room function can serve a dozen ways of painting, and a character frame is just one region of the scene, repainted along with each way of painting.

"Way of painting" and "medium" below are the same thing; in the film one way of painting occupies one segment, and in the reference implementation the code calls one an era.

A complete runnable example is in `scripts/art-motion/engine/reference_films/painted_room/` (one room, 16 ways of painting, 44 seconds). It is not the same engine as `scenes/`; in `scenes/` one style is one scene file, which suits films where every segment has a different composition, whereas this suits films where the composition stays fixed and the way of painting changes. Issue 02 covers the five-layer mechanism of this kind of film; this piece covers how to make the "way of painting" layer thick.

## Two routes

- Adapt: copy `painted_room/`, change the room, the palette and the timeline (its README says which three places to change). Most new ways of painting can be assembled from the existing three traversals: brush, dot, patch.
- Write your own: the seven sections below are the practices that held up when building this engine; write your own by their reasoning. The parameters (stroke length, grid spacing, paste-back opacity) are that film's numbers, not a quota.

## 1. The scene hands over two images and a set of directions

Each frame, first draw the scene into two offscreen images: a colour image (each thing's own colour, gradients allowed) and a region-id image (which thing each pixel belongs to, one id per thing). Each thing also carries a stroke direction field: walls brushed vertically, floor along the wood grain, sky turning around the moon, cat fur following the body.

The painting process looks only at these two images: what colour a point is, who it belongs to, how far it is from an edge, how much detail is around it. It does not need to know whether it is painting a cat or a chair.

## 2. Paint stroke by stroke

Lay a grid over the picture, one stroke per cell: the start point is jittered slightly inside the cell, the stroke runs out along the direction field of the region that point belongs to, and stops when it reaches the region edge; the colour is the starting point's own colour, jittered slightly. Paint several passes from coarse to fine; the fine passes land only where there is a lot of detail (edges, facial features, small objects).

Don't draw a stroke as an equal-width round-capped line — that looks like wool embroidery. Split a stroke into several bristles, each inset slightly at its start and at its lift-off, so both ends of the stroke come out ragged; then add a light edge along one side of the stroke and a dark edge along the other, and you get the thickness of paint.

The same traversal with three things swapped is another way of painting: swap to round dots for pointillism, to small seamed squares for mosaic, to large cells sampling colour for pixel art; flat fill plus halftone dots is printing, flat fill plus paper grain and a little dry brush is ink wash. The medium's own ground (canvas, stone wall, paper, plaster) is laid down before the first stroke, and shows through where the strokes don't cover — that is correct.

## 3. Outline only the segment you can see

Outlining a whole polygon puts hidden line through the things in front, like an X-ray. Sample a point every few pixels along the contour and query the region-id image on both sides of the normal: only where one side is self and the other is not does this short segment get drawn. Colour patches on the body (orange on a cat's back) are recorded in the same group as the form they belong to, and don't break the outer contour.

## 4. To animate, take random numbers by "cell + pass"

Sequential randomness is fine for stills. The moment it animates, if one stroke is skipped this frame because its region changed, the random numbers of every stroke after it shift, and the whole picture is reshuffled every frame. Generate each stroke's random numbers from hash(cell id, pass number, seed): where the picture hasn't changed, that stroke is exactly where it was on the next frame; only where something passes through do the strokes change.

To make the picture "live", let strokes drift slowly along the direction field and fade in and out with a lifetime — don't reshuffle the whole frame.

## 5. Update the picture on 12s, move the camera on whole frames

Draw the scene and the strokes on a clock rounded to 1/12 s; camera push, pull and truck, and the seams of transitions, are computed at delivery frame rate. It looks like the texture of hand-drawn animation "on twos", the camera stays smooth, and render cost halves (the same picture is cached and used for two frames).

## 6. Characters: treat an existing frame as a region

Applies when: the character already has drawn frames (frame library, hand-drawn, 3D rendered to 2D), and this film can't or doesn't want to generate a new set per style. It is an extension of issue 10's method B (paste a fixed frame library) and does not replace method C: with image generation available and the character needing a new outfit in every style, method C has the higher ceiling.

Three steps:

1. Draw this frame into the colour image and write its silhouette into the region-id image. From that moment it is no different from a chair in the room; every way of painting repaints it with its own strokes.
2. When the colour doesn't fit the era (black-figure pottery, ink wash, papercut, monochrome print), first map the frame's pixels by luminance onto three or four colours of that era, then hand it to the painting process (in the reference implementation this is `HEROMAP` in `film2.js`, and the paste-back amount is `KEEP`).
3. Coarse strokes will smear the face. After painting, paste the original frame back at a little opacity so the facial features read. How much depends on the way of painting: the coarser the strokes, the more you paste back; flat-fill kinds need none.

Known edges: in ways of painting with very grey or very dark palettes (Cubism, cave) the character tends to wash out and needs its own extra step of luminance contrast; in flat-fill kinds the character basically keeps its original style and only changes colour, so anything more thorough means writing a deformation for that one way of painting (the Egyptian frontal-profile law, say).

## 7. Transitions are actions the character performs

If a mask sweeps across by itself, the audience sees "the film is changing style"; if the seam follows the character's body, they see "he changed the world". Four kinds, used in rotation, landing on the beat of the music:

- Pull: he reaches out and drags the next picture in from off-screen. The seam is a vertical curve bulging out at hand height, with a crease of bright edge and shadow behind it.
- Walk: the seam rides on him and crosses the frame with him, the front half of his body in one way of painting and the back half in another.
- Jump: on the landing frame the new way of painting splashes out from under his feet as an irregular circle, and things in the room bounce with it.
- Wave: a few brush strokes sweep past from the direction of his hand, and wherever they sweep, that is what changes.

He is drawn in the picture of both eras, and he changes way of painting wherever the seam cuts him, so the character needs no separate transition.

The ending can release all the ways of painting at once (vertical bars dropping in one after another, each bar one way, still painting the same room) — that reads more like a close than stopping on the last one.

Score and picture share one beat table: decide first how many beats each way of painting takes, and both the picture's cut points and the score's bars are computed from that table. One short motif changing instrument in each segment means the same thing as "the same room changing way of painting". See issue 05 for how.

## Pitfalls hit

- Loading images directly in a `file://` page taints the canvas and you can't export frames. In the render script read character frames as data URLs and pass them into the page.
- Remapping character colour per pixel is slow; cache by "frame + era".
- Creating offscreen canvases repeatedly fills memory; build a pool and reuse by slot.
- With multi-process rendering, the slow segments (impasto, pointillism) cluster in the middle of the film; cut frames into small blocks and deal them round-robin to the processes, don't cut into a few contiguous large segments per process.
- However fine the way of painting, sampling frames won't show the rhythm of the whole film. Watch it once at normal speed before delivery.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
