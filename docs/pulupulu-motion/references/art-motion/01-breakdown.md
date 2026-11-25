# 01 · Breakdown: take a piece of animation and break it down to code-ready spec within an hour

The goal of the breakdown is not to write a viewing note; it is to produce **a spec you can program directly from**: start and end frames of every segment, transition mechanisms and parameters, in-frame action list, counter/subtitle value curves, composition coordinates, and the audio track's grid and instrumentation. The prose is an index; the numbers and contact sheets are the body.

First real run: on 2026-10-04, broke down a 15-second "Art History Speedrun" from X (16 art eras, 15 transitions); the whole pass took about 1.5 hours (storyboard agent 79 minutes, audio agent 22 minutes, in parallel).

## 1. Probe the physical parameters first (5 minutes)

```sh
ffprobe -v error -show_entries format=duration:stream=codec_type,width,height,r_frame_rate,sample_rate -of default=nw=1 src.mp4
```

For X videos take the highest tier from the syndication endpoint (pick the highest bitrate among `video_info.variants`); do not screen-record. If the source is 60fps, break down at 60fps — the frame number is the shared language of every downstream spec (seconds = frame/60).

## 2. Three overview images (10 minutes)

1. **Contact sheet**: 4fps × 480 wide, 30 frames per sheet, timestamped. One look tells you how many segments there are and what each one is.
2. **Key-frame overview**: pick the cleanest full frame of each segment and tile them 4×5. The map for all later work.
3. **Spectrogram**: `ffmpeg -lavfi showspectrumpic=s=1600x400:legend=1`. One look shows whether the instrumentation changes per segment, whether there are falling glissandi, shattering transients, or beats. Clean harmonics and a hard cut at 16kHz = code-synthesized + AAC.

## 3. Measure transitions and rhythm (15 minutes)

**Frame-to-frame grayscale difference**: downscale to 192×108 grayscale, mean absolute difference of adjacent frames. Static segments <2, transition segments 10–37. Threshold 5 plus a 12-frame debounce finds all transition starts in one pass. Save as `diff.npy` and share it with every agent.

After finding the starts, **fit a grid**: if the start intervals are integer multiples of a constant, there is a BPM grid (this film: start = 84 + 14.06·n frames, residual < 0.45 frames, = 128 BPM eighth notes). Once the grid is confirmed, write every picture and music timing as "the Nth eighth note".

**One 60fps contact sheet per transition**: start 2 frames before the start point, take one frame every 2 frames, 0.5 seconds, 15 cells. The mechanism is visible only here — descriptions like "8 vertical bars drop in sequence and bounce back", "20px blocks flip around the vertical axis and spread outward from the cat's position" would be written merely as "a block transition" from the coarse 4fps sheet.

**Take the reference frame as "the last frame before the transition starts"**, not the frame you think looks good. Taking it too early mistakes the previous transition's residue (debris chunks) for picture content (the first Egyptian pass fell into this).

## 4. In-frame motion: what is actually moving in each segment (15 minutes)

Motion heatmap: within each segment's static interval, take the per-pixel maximum frame difference, overlay it in red on a grayscale base, and label the "moving-area percentage".

The conclusion for this film overturned the first impression: I assumed "each segment is just one painting", but every segment actually had 2.5%–34% of its area moving — rock-art animals running with two alternating poses, a scarab pushing the sun disc, a meander band scrolling, Vesuvius smoking, gold-leaf highlights sweeping past, an ornithopter flying across, a four-panel grid changing colors... **Start work without this step and what you make is "transitions between images", losing the continuous motion inside the scene.**

The heatmap tells you "where it moves"; then look at the 60fps frames for "how it moves" (period, amplitude, two-frame alternation or continuous).

## 5. How to write the brief when splitting work across agents

- Storyboard agent and audio agent in parallel, each with a complete brief: asset paths, known facts (frame rate, duration, coarse segment table), required outputs, method requirements (prove with data, do not go on impressions), reply format (summary + the 3 least certain points).
- Have them **correct your list first**. On this film I misread the "1993→2026 iris transition" as a "Memphis era"; the storyboard agent's first item corrected it.
- Treat what an omni-modal model "hears" in the audio track as candidates only: instrument judgments are trustworthy, but BPM (reported 120, actually 128), motif note counts, and "one whoosh per segment" were all wrong and must be re-checked with onset detection.

## 6. Output list (what you should have after the breakdown)

| Output | Purpose |
|---|---|
| `shot-list.md` + `spec.json` | start/end frames per segment, transition mechanism and parameters, in-frame action, counter curves, composition coordinates |
| `transitions/T*.jpg` (60fps contact sheets) | frame-by-frame reference while writing transition code |
| `in-shot-motion/motion-heatmap.jpg` | what moves in each segment, and how much |
| `ending-action/` (if there is character performance) | per-frame centroid, trajectory, physical parameters (gravity px/frame²) |
| `audio-breakdown.md` + `synth.py` (template: `scripts/art-motion/audio/synth_art-history-speedrun.py`) | BPM grid, eighth-note count per segment, motif, instrumentation, SFX sequence |
| `keyframe-overview.jpg` + `generated-images/ref/*.png` | composition map, reference frame per segment |

Scripts: `scripts/art-motion/analyze/` (contact sheet, grayscale diff, transition contact sheet, motion heatmap); commands are in each script's docstring.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
