---
name: youtube-short-analyzer
description: Analyze a long YouTube or local video into timestamped YouTube Shorts candidates without rendering. Use when the user asks to scan, transcribe, detect hooks, or find promising 25-45 second moments from a raw source, especially Indonesian Islamic lectures. Do not use when candidates are already selected or the task is only to render known timestamps.
---

# YouTube Short Analyzer

Turn one source video into an evidence-based candidate manifest. Analyze only; do not render or publish.

## Inputs

Collect or infer these values:

- `source`: a local video path or YouTube URL.
- `niche`: default to the source topic; use `kajian Islam` only when applicable.
- `candidate_limit`: default 10.
- `min_duration`: default 25 seconds.
- `max_duration`: default 45 seconds.
- `language`: default `id`.
- `output_root`: default `outputs/skill-review`.

Never infer that the user owns reuse rights. Analysis may proceed for review, but flag uncertain rights and do not authorize rendering or upload.

## Workflow

1. Verify that a local source exists, or that the supplied URL is a YouTube URL.
2. Record the source file size and modification time before processing. Never edit, move, rename, or delete it.
3. For Islamic material, read [references/islamic-content-rules.md](references/islamic-content-rules.md) before selecting boundaries.
4. From the repository root, use ClipForge's existing review-only pipeline:

```bash
python3 backend/clipper.py \
  --source-file videos/kajian.mp4 \
  --top 10 \
  --min 25 \
  --max 45 \
  --language id \
  --review-only \
  --output outputs/skill-review
```

For a URL, pass it as the positional argument and omit `--source-file`:

```bash
python3 backend/clipper.py "YOUTUBE_URL" \
  --top 10 --min 25 --max 45 --language id \
  --review-only --output outputs/skill-review
```

Use `--ai-enabled`, endpoint, model, and key options only when the user has configured and requested that AI endpoint. Add `--require-creative-commons` only when that restriction is requested. Add `--confirm-source-rights` only after an explicit user confirmation; the flag is an audit statement, not a bypass.

5. Locate `candidates.json` or `candidates_<seconds>s.json` under the created source folder. Treat `transcript.json` and source metadata as supporting evidence.
6. Audit every candidate against the checks below. Reject rather than repair by inventing words.
7. Recheck the source file size and modification time. If either changed, stop and report the integrity failure.

If the application dependencies are unavailable, inspect an existing timestamped transcript instead. Do not estimate timestamps from untimed prose.

## Candidate checks

A candidate is eligible only when all are true:

- The first meaningful spoken idea begins within 2 seconds of the cut.
- The clip is understandable without unseen context.
- Start and end are complete sentence or semantic boundaries.
- The ending supplies an answer, takeaway, reveal, or intentional loop.
- It contains no source-channel intro, outro, sponsor block, or filler.
- `boundary_quality` is not `menggantung`.
- `religious_context_safe` is true for Islamic content.
- The transcript supports every claim in the proposed hook and title.

Do not add a synthetic spoken hook during analysis. A text overlay may later summarize the actual claim, but it must not change its meaning.

## Output contract

Write `analysis_manifest.json` beside the native candidate file. Include `schema_version`, `source`, `source_metadata_path`, `native_candidates_path`, analysis parameters, outcome, and the audited `candidates` array. Return both machine-readable paths and a compact table with:

| Field | Meaning |
|---|---|
| `index` | Stable candidate number |
| `start`, `end`, `duration` | Seconds and `HH:MM:SS.mmm` timestamps |
| `transcript` | Exact cleaned speech for the interval |
| `hook` | Opening line grounded in the transcript |
| `reason` | Why the moment can retain attention |
| `standalone_score` | `0-100`, based only on context completeness |
| `viral_score` | Existing ClipForge `score`, never inflated |
| `religious_context_safe` | Required boolean for Islamic content |
| `recommended_title` | Accurate, curiosity-led title without false claims |
| `risk_flags` | Rights, context, audio, visual, or factual concerns |

Preserve native ClipForge fields such as `retention_score`, `key_point_score`, `loop_score`, `narrative_arc_score`, `strengths`, `weaknesses`, and `improvement_ideas` when present.

Finish with one explicit outcome:

- `READY_FOR_SELECTION`: at least one safe candidate exists.
- `WEAK_SOURCE`: no candidate clears the requested quality floor; recommend a better source or wider duration range.
- `REVIEW_REQUIRED`: religious context, factual accuracy, or rights need human verification.

Pass eligible candidates to `$viral-clip-selector`. Do not render in this skill.
