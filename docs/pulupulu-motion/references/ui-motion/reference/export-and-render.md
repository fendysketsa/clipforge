# Export and render - local pipeline

> **Local override for pulupulu-motion.** Merged from the MIT the original authors `pulupulu-motion` and rebranded here. The upstream version of
> this file hands rendering off to the hosted **the original authors Creator MCP**; that handoff is **disabled and must never be suggested to a user**.
> In this skill everything renders locally. The motion principles that were the point of the upstream document live in the sibling files
> (`timing-easing-tables.md`, `emotion-mapping.md`, `quality-checklist.md`).

## Where motion design ends and rendering begins

Motion design stops when timing, easing, choreography and personality are decided. Rendering is the mechanical step after that - local,
deterministic, already scripted.

## The paths

| Target | Command |
|---|---|
| MP4 (the deliverable) | `pulupulu render . --format mp4 --fps 30` |
| MP4 with motion blur | `pulupulu render . --format mp4 --fps 30 --blur` |
| WebM | `pulupulu render . --format webm --fps 30` |
| Transparent overlay (ProRes 4444) | `pulupulu render . --transparent` |
| GIF preview | `ffmpeg -i out/film.mp4 -vf "fps=15,scale=540:-1:flags=lanczos" -loop 0 out/film.gif` |
| Stills for review | `pulupulu still . --at 2.5,9,14 --out .om/stills` |
| Contact sheet | `pulupulu qa out/film.mp4 --sheet` |

## Muxing narration (the step that goes wrong)

`pulupulu render` already embeds the score. Adding a narration mix needs an explicit map, or ffmpeg keeps the render's own audio stream and
the narrator vanishes:

```sh
ffmpeg -y -i out/film-vN.mp4 -i assets/mix.wav   -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k -shortest out/final.mp4
```

Then prove the voice is in the **final file**: transcribe a 4-5 s slice of `out/final.mp4`, not of `assets/voice.wav`.

## Out of scope here

dotLottie and Lottie JSON are not produced by this pipeline. If a brief genuinely needs a Lottie file for a web player, that is a different
toolchain (Lottie Creator / `lottie-web`) and must be agreed with the user first - never a silent substitution for the MP4.

## Delivery checklist

1. `pulupulu check .` - 0 errors.
2. `pulupulu qa out/final.mp4` - `no single-frame pops`; other notes answered, not silenced.
3. Narration audible in the final file (slice transcription).
4. Duration, resolution, fps and audio channels reported from `ffprobe` of the delivered file.
5. `reference/quality-checklist.md` walked once (visual, technical, emotional, performance, accessibility).

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../../art-motion/INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
