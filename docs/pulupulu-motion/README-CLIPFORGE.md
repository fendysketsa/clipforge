# pulupulu-motion — vendored guidance (ClipForge)

**Status:** optional agent skill, documentation and tooling only. It is **not**
part of the ClipForge runtime, Docker images, cron, QC, or any upload path.

## Provenance

- Upstream: <https://github.com/Alucard0x1/pulupulu-motion>
- Licence: MIT © 2026 Alucard0x1 — full text in [`LICENSE`](./LICENSE).
- Renderer dependency described by the skill: `huashu-motion` (`om`), a separate
  MIT project. **Not bundled and not installed by ClipForge.**
- All original notices are preserved in [`THIRD-PARTY-NOTICES.md`](./THIRD-PARTY-NOTICES.md).

## Why it was kept

It is a compact, checkable craft guide for motion-graphics films: HTML + GSAP
pages rendered frame-accurately in Chrome, measured narration, style recipes,
and verification gates. Several of its rules are useful vocabulary for this
studio's editorial and QC work:

- caption text equals the spoken sentence (notation may differ, words may not);
- measure the audio before building the picture;
- explicit FFmpeg stream maps when muxing picture and sound;
- a still-frame check before committing to a full render;
- language and dead-motion gates, not self-graded adjectives.

ClipForge already enforces the overlapping safety rules in its own code
(`caption_clearance.py`, transcription/retention measurement, upload evidence
and independent QC). Nothing here weakens or replaces those gates.

## Safety review (before vendoring)

- 233 files, ~3.1 MB, plain Markdown + Python + small JS; no minified blobs.
- No obfuscation, `eval`, `os.system`, credential files, or embedded secrets.
- Network use is explicit and limited to: DeepSeek TTS (reads
  `DEEPSEEK_API_KEY` from the environment, never writes it), an npm registry
  version check, and fetching public style-reference pages.
- Subprocess use is local `ffmpeg`/`ffprobe`/Chrome for rendering and checks.
- One upstream character, **"bean Huashu" / 豆子花叔**, is explicitly **not
  licensed for reuse**. Do not copy that likeness; design original characters.

## Boundaries

1. Do **not** install `huashu-motion` globally or add it to either Dockerfile.
2. Do **not** use this skill as a replacement renderer for Short, Long, or
   Facebook production. Those remain owned by Motlab/Remotion and their QC
   evidence chains.
3. Do **not** publish anything made with it through ClipForge's autopilot
   unless it passes the normal rights, QC, publication-hold and remote-identity
   gates.
4. If used manually, keep API keys in the environment only, never in a project
   file or a commit.

## Entry point

Read [`SKILL.md`](./SKILL.md) first; it routes to one reference page at a time.
Machine preflight, if the operator wants to use the skill outside deployment:

```sh
python scripts/doctor.py
```
