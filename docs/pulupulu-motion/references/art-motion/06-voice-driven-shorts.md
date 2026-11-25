# 06 · Voice-over-driven art shorts (draft method, awaiting validation on the first real film)

Goal: from a voice-over performance, produce animation with coherent shots and imagery in a chosen era's or artist's style. For the current whole-film method see 12 (voice-over whole films and lessons flowing back).

> ⚠️ This page is a plan extrapolated from the art-history speedrun engine; **it has not yet been run on a real voice-over**. When the first film is done, delete this line and write the measured results back in.

## How it differs from the speedrun film

| | Speedrun film | Voice-over short |
|---|---|---|
| Timeline | BPM grid | voice-over word-level timestamps (from your transcription tool, e.g. Whisper-style word-level timestamps) |
| Style | style changes every segment | **one style throughout** (one artist / one era) |
| Camera | fixed position | needs camera language: push and pull, pan, change of shot scale, follow |
| Narrative | skeleton fixed, style changes | style fixed, content changes with the voice-over |

## Process

1. **Voice-over → shot list**: split by sentence; for each sentence decide "what is on screen while this is said" (concrete object / metaphor / character action / text), and tag shot type (wide / medium / close-up / push / pan) and duration (from the word-level timestamps). Show the author 5–10 rows of the shot list before starting work.
2. **Fixing the style = fixing the renderer + palette + line**: take the closest card in the style-recipe library as the starting point; for a style with no card, write a new renderer per section 3 of no. 04. Produce one frame first (three-way hard gate: the same frame of the same voice-over sentence, interpreted in three styles, for the author to choose).
3. **A world, not a picture**: a voice-over film cuts between shots, so build the scene as a "world canvas" larger than the frame (e.g. 5760×3240), with every element in world coordinates; the camera = the viewport (centre, zoom, rotation). The renderer acts on the frame drawn out of that viewport, and brush size is set in screen pixels, so brushes do not thicken when you push in — this is the key to "the painting is moving" rather than "the image is being scaled up."
4. **Flow between shots**:
   - Within a scene: viewport interpolation (push, pull, pan), with ease in and out.
   - Changing scene: make the transition in that style's own language (Van Gogh: a swirl of brushstrokes carries the frame away; ukiyo-e: a wave; ink wash: ink blooming out) — the layer-3 mechanism of no. 02.
   - Match cut: the shape of the previous shot matches the shape of the next (rim of a cup → the moon).
5. **Type and voice-over**: keywords can be written into the picture in that style's typeface or brushwork (mosaic tiles, calligraphy, neon); no generic subtitle bar — subtitles go on a separate track in the editing project.
6. **Music**: reuse the grid method of no. 05, except the grid yields to the voice-over rhythm (put transitions and musical accents in the gaps between sentences).
7. **Acceptance**: watch it side by side with the voice-over; is the picture talking about the same thing for every sentence; is every shot moving; is the style recognisable at a glance.

## Division of labour with the video pipeline

Transcription, timeline, mixing and delivery of the voice-over run through your video pipeline; this skill owns only the "art animation picture" track, producing a silent MP4 or ProRes that the editing project uses as its picture track.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
