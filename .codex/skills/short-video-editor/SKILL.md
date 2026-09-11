---
name: short-video-editor
description: Render selected timestamp ranges into 1080x1920 Shorts with dynamic ASS subtitles, safe audio normalization, and source-file protection. Use after clip selection or when the user supplies exact timestamps and asks for MP4 output. Do not choose moments from a raw video, claim source rights, upload, or publish.
---

# Short Video Editor

Render only approved candidates. Never modify the source video and never upload automatically.

## Inputs and preflight

Require:

- local source path;
- exact `start` plus `duration` or `end`;
- destination path different from the source;
- transcript segments or an existing ASS/SRT subtitle file;
- confirmation that any `rights_review_required` gate is resolved before rendering.

Prefer `selected_clips.json` from `$viral-clip-selector`. Refuse candidates marked unsafe, below the requested quality floor, or missing complete boundaries.

Record the source size and modification time before and after the batch. Stop if either changes.

## Preferred ClipForge path

Use the repository pipeline when face-aware reframing, active-speaker layouts, silence-aware structural repair, metadata sidecars, or the full Auto FYP treatment is wanted:

```bash
python3 backend/clipper.py \
  --source-file videos/kajian.mp4 \
  --top 3 --min 25 --max 45 \
  --export-indexes 1,2,3 \
  --crop-mode person \
  --visual-mode auto_fyp \
  --output outputs/shorts
```

Candidate indexes must come from a review run using the same source and settings. `--confirm-source-rights` may be supplied only after the user explicitly confirms it.

## Deterministic FFmpeg fallback

Use the bundled scripts when exact timestamps are already approved and a simple local render is preferable.

First create dynamic ASS subtitles from ClipForge `transcript.json`, subtracting the clip's source start:

```bash
python3 .codex/skills/short-video-editor/scripts/make_ass_subtitle.py \
  --input outputs/source/transcript.json \
  --output outputs/shorts/clip-01.ass \
  --offset 125.4 \
  --duration 34.2 \
  --keywords "iman,sabar,hikmah"
```

Then render a vertical MP4:

```bash
.codex/skills/short-video-editor/scripts/render_short.sh \
  --input videos/kajian.mp4 \
  --output outputs/shorts/clip-01.mp4 \
  --start 125.4 \
  --duration 34.2 \
  --subtitles outputs/shorts/clip-01.ass \
  --fit blur
```

Use `--fit crop` only when a center crop will not remove the speaker or essential text. The fallback normalizes speech toward `-16 LUFS`, limits true peak to `-1.5 dBTP`, writes H.264/AAC MP4, and refuses to replace an existing output unless `--replace-output` is explicit. It always renders to a temporary file and atomically moves the finished file into place.

## Edit rules

- Keep the first spoken value within 2 seconds; trim silence, not semantic context.
- Use subtitles derived from actual speech. Correct transcription spelling without paraphrasing the speaker.
- Keep important captions inside the vertical safe area and avoid covering faces.
- Emphasize a few meaningful keywords; do not flash every word aggressively during solemn content.
- Make CTA appear only after the payoff. Do not cut off the final answer to insert it.
- Avoid reaction effects during Qur'an recitation, prayer, grief, or serious religious rulings.
- Preserve natural voice. Do not clone or synthesize the source speaker's voice without explicit authorization.
- Do not add third-party music, B-roll, logos, or images unless their rights are documented.

## Verification

For every output:

1. Use `ffprobe` to confirm `1080x1920`, H.264 video, expected duration, and an audio stream when the source contains audio.
2. Confirm subtitles are legible and synchronized at the opening, midpoint, and ending.
3. Confirm the hook, main point, and payoff remain faithful to the transcript.
4. Confirm the source size and modification time are unchanged.
5. Return output and sidecar paths plus any remaining human-review flags.

Rendering is complete only after these checks pass. Publication, YouTube login, scheduling, and upload require a separate explicit user request.
