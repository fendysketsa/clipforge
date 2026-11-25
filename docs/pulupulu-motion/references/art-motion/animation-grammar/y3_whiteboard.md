# Y3 · Whiteboard hand-drawn explainer (RSA Animate type): video animation grammar card

In one sentence: the speaker says one sentence and a hand writes that sentence and draws a diagram on a large whiteboard; the camera follows the argument across the board, and at the end it pulls back so the audience sees the whole argument as one drawing.

Demo film: `scripts/art-motion/engine/demos/y3_whiteboard/` (render with `render.py --film demos/y3_whiteboard`) (8s, 3 shots, 2 transition types + closing pull-back), overview: `assets/animation-grammar/y3_whiteboard_overview.jpg`
Basis: research into the style (the original research text and per-frame data stay in the experiment archive and were not taken into the skill; the numbers used are excerpted into this card). Measured RSA Animate's "Changing Education Paradigms" and Minute Physics's "Why is it Dark at Night?", and also checked VideoScribe's and Doodly's official documentation and first-hand accounts from Andrew Park and Henry Reich.

**Choose one grammar first; do not mix them:**
- RSA type: one large whiteboard, the camera moves across the board, 5.3 times per minute.
- Minute Physics type: one sheet per page, hard-cutting between sheets, 8.1 times per minute, the camera doesn't move.
- This card and the demo film follow the RSA type. The Minute Physics type's points are in ④ and ⑧.

## Check before you start

1. **"Too little drawing, too much writing" is a storyboard-level problem — fix the visual metaphor before you put pen to board.** On each board, first write down the object or the gag that has to be drawn, then decide what the words say; a handwritten full sentence is no longer than one line. Count it: if more than half the characters on the board coincide with the narration's words at that moment, it is too little drawing and too much writing, and adding puns or icons in post won't save it.
2. **Block templates have to rotate.** Blocks with the same structure — "year → object → orange label" or "dot → one line → one icon" — are not used more than 3 times in a row in a film; switch to a contrast (two panels side by side), a process (chained with arrows), a zoomed detail, or one full-width drawing.
3. **Don't hand-enter camera coordinates to frame a shot.** Solve them backwards from the bounding box of this segment's strokes (frame it, then leave margin); old words cut in half at the frame edge get pushed out of frame.
4. **Line style is fixed from the first stroke.** Solid = has happened, dashed = planned, dotted = a lead across segments; things on the board can only be erased or left in place, never faded out.
5. **Run every object's shape past "could this read as an obscene shape".** Round heads, flared sides and long vertical objects with round bases are the usual offenders; change them to a pointed head or a flat base before drawing.

---

## ① When to use it

**Use it:**
- Argumentative content: talks, opinions, causal chains, historical sequences. Content where concepts have relationships and can be drawn as one map fits best. Andrew Park's own words: put the information in space so people can see the relationships between things [first-hand].
- Short science explainers that follow one chain of reasoning: go Minute Physics type.
- Voice-over at a steady pace with clear keywords. RSA's writing speed is roughly equal to the speech rate, like "subtitles being handwritten" [measured].

**Don't use it:**
- Content that needs precise data charts; hand-drawing error is large.
- Content with complex action and spatial relationships; a whiteboard has no depth of field.
- Content that needs emotional intensity; monochrome line art is weak at it.
- Expecting it to "improve understanding": Türkay 2016's experiment found whiteboard animation did not teach better than other formats. Its value is in holding attention and in companionship [second-hand].

## ② Frame composition

- **Palette** (measured on RSA):
  - ground: pure white `#FBFBFB`
  - line: black `#0A0503`
  - the only accent: orange, text `#EB701F`, fill `#F3742D`; the pale orange made by hatching about `#E9A67C`
  - orange is about 22% of all stroke pixels, used only on keywords and hatch fills.
  - Minute Physics instead uses a pinkish off-white paper `#E7DBE1`, plus coloured-pencil pale yellow `#EDE6A2` and pale blue `#B5CBE8`.
- **[This film]**: ground `#FBFBFB`, line `#0A0503`, accent `#EF7226`. The cat's body is laid in with orange at 22% opacity.
- **Line width**: RSA strokes are about 0.6–0.7% of frame height, about 6–7px at 1080p; shadow hatching about 0.3%; title cap height about 5.5% of frame height. Minute Physics's lines are thicker, about 0.8% [measured]. [This film] line width 6.5px.
- **Composition**:
  - RSA is "plan the final whole picture first, then draw it backwards" [first-hand].
  - Each frame holds 3–6 image-and-text blocks, filled before moving on.
  - One smooth move travels only 0.23 frame widths, so the new and old blocks overlap over a large area and the audience can always see the edge of the previous block [measured].
  - The whole picture revealed at the end is one very long horizontal scroll.
- **Type**: RSA is all-caps handwritten lettering (comic-dialogue style). [This film] Chinese uses LXGW WenKai, subsetted into a woff.
- **The hand**:
  - A real right hand holding a black marker, entering from the **bottom right**, forearm angled down and to the right, covering 15–25% of the frame.
  - When it isn't drawing, the whole hand leaves the frame. Time on screen: RSA 49%, Minute Physics 40% [measured].
  - [This film] the code-drawn hand: bare forearm with a shaded side and hairs, index finger pressing the black marker, scale 0.82, swaying gently at 7 rad/s.

## ③ Motion paths

- **Writing speed** [measured, 9 cases]:
  - Body text median about 16 characters/second.
  - Opening titles at half that, about 7.5 chars/s, used to "state the question".
  - Narration is about 13 chars/s, so writing speed is roughly equal to the speech rate.
  - [This film] body text 16 chars/s; "cat？" ("Cat?") written at the title speed of 7.5 chars/s.
- **Drawing speed** [measured + inferred]:
  - Small icons 0.5–1s, a person's head about 2s.
  - RSA's median area of new ink is 0.25% of the frame per second.
  - Complex illustrations are not drawn on camera: either pre-draw them and reveal them as the camera moves over, or hard-cut the whole thing in and let the hand only fill colour.
- **[This film]**:
  - Stroke speed 2600 world pixels/second, about 2× RSA's live action. An 8s demo has to compress; slow it down for a real film.
  - Stroke duration is length divided by pen speed, minimum 0.04s per stroke, 0.02s between strokes.
  - Inside each stroke, sineInOut — slow at the start and at the end.
  - The author uses a 0.7s "Reveal" to uncover: the pen tip walks an 8-line zigzag inside his joint bounding box, and `DG.revealMask` turns the walked path into a clip; the line art only shows inside the clip.
  - The first version traced everything at once with `setLineDash` per part and ran the pen tip along the joints; the review judged "the pen doesn't lead the line", so it was changed.
  - Chinese characters have no stroke-order data, so each character is revealed with a 3-line zigzag and the pen tip moves back and forth with it, which looks like writing.
- **Speed-up factor**: Henry Reich shoots one frame per second, holding each for 2 frames while drawing, an equivalent of about 12× speed. RSA is inferred at 5–8× [first-hand + inference].
- **The "no hand" pop-in**: some of RSA's orange keywords pop in whole in post with no hand drawing them (ANAESTHETIC, CREATIVITY) [measured]. [This film] "×10 million images" and "It's a cat!" pop in with 0.3s backOut(2.2); the hand doesn't go there.
- **Pen tip path**:
  - When the gap between two strokes is <0.25s, the tip slides from the end of the previous stroke to the start of the next along an arc (sineInOut, lifted 30px).
  - For a longer gap, the hand lifts and leaves: 0.35s cubicIn retreating off-screen bottom right.
  - 0.3s before the next stroke it comes back in from bottom right with cubicOut.
- **Continuous motion**: the life of a whiteboard film comes from the hand always drawing. RSA's drawing activity barely correlates with the density of spoken words (|r|<0.07): when the talking pauses, the hand doesn't [measured].

## ④ Transitions (5 in common use)

1. **Smooth move, or push and pull on the board** (RSA's mainstay, 41 times).
   - 1.2–2.4s, **easeInOutSine**: measured peak/mean speed 1.49, theoretical sine 1.57.
   - One move is about 0.23 frame widths, overlapping the previous block by about 75%.
   - [This film] Transition B: 0.9s sineInOut (4.7→5.6s), a diagonal move of about 0.5 frame widths, pushing to 1.12× at the same time. When the move starts, the hand is drawing an orange connector line towards the new area — the hand leads the camera.
2. **Whip pan**: a fast pan with motion blur, about 0.8s, moving 0.5–1.2 frame widths in one go, used to jump to an area far across the board (RSA 15 times).
   - [This film] Transition A: 0.8s cubicInOut lateral move of about a full frame. Blur is stacked 9 times along the direction of velocity in those 0.8s only; smooth moves and pull-backs stay sharp.
3. **Pull back to reveal the whole picture** (the closing).
   - RSA's ending: grey fills the frame → 0.6s fast pull-back → about 9s pan across the scroll → pull back again to the whole picture.
   - VideoScribe has "Zoom at end?" ticked by default [first-hand].
   - [This film] 6.85→7.5s sineInOut pulling to 0.45×, hold 0.5s, while the whole board takes a very pale grey wash `#EEEEEC` over 0.5s.
4. **Cloud puff or explosion wipe**: a cartoon smoke puff fills the frame then disperses, about 1s (RSA once).
5. **Hard cut**: a hard cut to a pre-drawn image (RSA, sparingly); the Minute Physics type's sheet change by hard cut (the mainstay, 8.1 per minute); Minute Physics inverts the whole frame for the night-sky episode.

**Note**: "pushing into a frame or a thought bubble" and "page turns" do not appear in the samples. The first version of this film built a "push into a thought bubble"; after reading the research it was replaced with a whip pan plus a smooth move.

## ⑤ Pacing and text

- **Hold per block**: RSA's median time between two camera moves is 6.6s (quartiles 4.0–13.8s); Minute Physics's median shot is 7.1s [measured]. The demo film fits 3 blocks into 8s, about 2.5× a real film's density.
- **Aligned with the voice-over (the core)** [measured]:
  - Writing starts 0.2–0.8s after the matching phrase starts, median +0.5s.
  - Finished within 1s of the phrase ending: writing while speaking, slightly behind, **never ahead**.
  - The exception is visual setup (a pill bottle, an arrow), drawn a few seconds early and waiting for the line.
  - Minute Physics drops the image the moment the noun is said, median +0.3s.
- **Transitions cut on topic, not on pauses**: a new block corresponds to a new point in the argument [measured + inferred].
- **Music**: RSA has **no music** under the speech. Minute Physics has music throughout, about 9dB below the voice [measured].
- **Tool defaults**:
  - VideoScribe's hold after drawing defaults to 0.5s [first-hand], camera moves default to 1s [second-hand].
  - Doodly draws each asset for 3s by default [first-hand].

## ⑥ Implementation notes

> After being taken into the skill (2026-10-04 v0.4): the general-purpose functions in this card's "newly written" list have been consolidated into `scripts/art-motion/engine/lib/` (renamed to the unified MO / CAM / DG / TY / CH / UI / CL / TOON), and the demo's own code lives in `scripts/art-motion/engine/demos/y3_whiteboard/`. For the library quick reference and "how to choose a grammar for a stretch of voice-over", see `references/art-motion/09-animation-grammar.md`.

- Reused from the skill:
  - `KIT.densify / KIT.resample`: Catmull-Rom densify, then resample at equal arc length; `DG.hand` adds low-frequency noise on top
  - `PAINT.noise`, `PAINT.cached`
  - `the author.build/pose/details`: the author's line art
  - the engine transition interface
- Newly written, now consolidated into the library (`scripts/art-motion/engine/lib/diagram.js` / `camera.js`):
  - `DG.cum / DG.pointAt / DG.drawPartial`: trace a polyline out by length, returning the pen tip position.
  - `CAM.at`: keyframe camera.
  - `CAM.motionBlur`: motion blur.
  - `DG.revealMask / DG.zigzag`: zigzag reveal mask (added after the review).
- The demo's own (`demos/y3_whiteboard/whiteboard.js`; the stroke timeline, the slide between strokes and the marker have since gone into the library as `DG.board` / `B.penAt` / `DG.pen`):
  - **Stroke timeline**: `addLine / addText / addPop / addFill` are queued in order, durations computed automatically from length and speed, and on delivery `Y3.timeline` is printed to check each block's end time. In the first version the second block ran to 7.9s, 2.5s later than the camera move; that number is how it was caught.
  - `drawStroke`: five kinds — lines, text, pop-ins, fills, characters. Both text and characters are revealed with a zigzag mask, and the pen tip coordinate is taken straight off the mask's leading edge.
  - `penAt`: the path of the pen tip and the hand, including the slide between strokes, lifting out and entering.
  - `drawHand`: the hand and the marker.
  - Eraser-smear texture lives in screen space and follows camera translation only, not scale, otherwise pushing in 5× turns it into large grey blotches.
- **Key architecture**: all three shots draw the same whiteboard with the same camera, and every transition is `same`. The "transition" is itself camera motion, so nothing on the board can ever jump across a transition.

## ⑦ Reference films and first-hand sources

- Sample films:
  - RSA ANIMATE: Changing Education Paradigms https://www.youtube.com/watch?v=zDZFcDGpL4U
  - MinutePhysics: Why is it Dark at Night? https://www.youtube.com/watch?v=gxJ4M7tyLRE
- Andrew Park interview (Sketchnote Army 2025) https://sketchnotearmy.com/blog/2025/11/18/andrew-park
- Cognitive Media, "the hairy hand" https://www.hairyhand.co/about
- VideoScribe official documentation:
  - Camera and Zoom at end https://help.videoscribe.co/knowledge/use-zoom-and-set-the-camera
  - Draw entrance https://help.videoscribe.co/knowledge/draw
  - Entrance animations https://help.videoscribe.co/knowledge/entrance-animations
- Doodly defaults https://support.voomly.com/en/articles/12735753-doodly-how-do-i-customize-video-settings
- Learning-outcome research (cited second-hand) https://en.wikipedia.org/wiki/Whiteboard_animation

## ⑧ The three easiest things to get wrong

1. **Filling a whole block before speaking, or finishing speaking before drawing.** The magic of a whiteboard film is "say one sentence, write one sentence": writing speed equals speech rate, about 0.5s behind the narration. Draw-then-speak makes the audience wait; speak-then-draw makes the drawing a redundant recap. Don't draw complex illustrations live — pre-draw them and reveal them as the camera moves over.
2. **Cutting to a whole new blank block every time.** RSA's smooth move travels only 0.23 frame widths, so the new and old areas overlap over a large area and the audience always knows where they are within the big picture. Use the 0.8s whip with blur only when jumping far away. The ending must pull back to the whole picture — that is this genre's landing point.
3. **Too many colours, lines too thin or too even, the hand parked on screen the whole time.** Black plus one accent only, line width about 0.65% of frame height. The hand enters only while drawing and exits bottom right when done; emphasis words can pop in with no hand. Also don't mix RSA and Minute Physics: either one large whiteboard with camera moves, or one sheet per page with hard cuts.

---

## Review and revision (an independent agent sees only the finished film, 6/10, the lowest of the three)

Review comments and what was done this round:
- "The pen tip doesn't lead the line, several of the author's strokes surface at once; the text is wiped out by a mask":
  - The author switched to VideoScribe's Reveal method: the complete line art hides underneath, the pen tip walks an 8-line zigzag, wherever the pen passes it is revealed, and the tip is always on the leading edge.
  - Text changed to character-by-character writing: each character gets a stretch of time, the tip zigzags back and forth 3 lines inside the character box, and the mask reveals behind it.
  - Newly written `DG.revealMask` (a union of same-direction rectangular bars, so overlaps don't cancel under nonzero) and `DG.zigzag`.
- "0.4s dead zone after the whip pan": the second block starts drawing at 3.12s, and the hand enters as the whip finishes.
- "The screenshot frame line runs through the cat's head": each frame is filled with whiteboard colour before being stroked, so the front frame covers the lines of the one behind.
- "'Finding the pattern yourself' cut in half by the top edge": the third block moved down 60px as a whole.
- "After the pull-back the grey ground and eraser smears look like a dirty wall": the grey ground lightened to `#EEEEEC`, eraser-smear opacity halved.
- "The wide shot holds only 0.15s and the three drawings aren't connected":
  - An orange arrow pointing right added at the end of block one, so the whip pan has a direction.
  - An orange connector line drawn at the end of block two leading into block three, the hand leading the camera.
  - The pull-back moved earlier to 6.85–7.5s, the wide shot holds 0.5s.
- "The hand is a cartoon hand with a blue sleeve": changed to a bare forearm with a shaded side and hairs, closer to RSA's real hand. Still code-drawn.

## QA (`scripts/art-motion/qa.py` in the skill, final version after revision)

| Shot | Measurement window (s within shot) | Motion area % mean/peak | Static frame pairs % | Jump frames | Per-frame cost mean/peak ms | Determinism |
|---|---|---|---|---|---|---|
| y3_s1 | 0.35–2.48 | 3.1 / 5.31 | 0.0 | 0 | 6.5 / 6.9 | ✓ pixel-identical |
| y3_s2 | 0.8–2.23 | 4.65 / 9.57 | 0.0 | 0 | 6.5 / 7.3 | ✓ pixel-identical |
| y3_s3 | 0.85–3.23 | 4.45 / 10.94 | 0.0 | 0 | 8.3 / 9.0 | ✓ pixel-identical |

Transition smoke test (each transition rendered once, slowest frame): y3_s2 (same) 46.9ms; y3_s3 (same) 14ms

How to read it:
- None of the three whiteboard shots has a jump frame: every "transition" is camera motion over the same board, and nothing on the board can jump.
- Motion area 3–4.7% comes mainly from the hand and the line currently being drawn; it goes higher while the camera moves.
- Under 10ms per frame, because everything is vector line work with no pixel-level processing.

Rerun: `uv run scripts/art-motion/qa.py --project scripts/engine --film demos/y3_whiteboard --out <dir>` (the table above holds the numbers from the experiment; for reruns after being taken into the skill, see the regression table in 09).

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
