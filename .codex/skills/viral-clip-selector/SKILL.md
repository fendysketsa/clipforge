---
name: viral-clip-selector
description: Rank and shortlist existing timestamped YouTube Shorts candidates with a transparent 0-100 quality score, diversity checks, and an 80-point gate. Use after a video analysis or when a candidate manifest already exists and the user asks to choose the best clips. Do not analyze raw video, invent timestamps, render media, or promise views.
---

# Viral Clip Selector

Choose a small, diverse, defensible batch from an existing candidate manifest. A viral score estimates packaging and retention potential; it is not a prediction or guarantee from YouTube.

## Required input

Require timestamped candidates containing at least `start`, `end`, `transcript` or `text`, and source identity. Prefer `analysis_manifest.json` from `$youtube-short-analyzer`; a native ClipForge `candidates.json` is also acceptable when its sibling metadata or explicit user input identifies the source.

If timestamps or transcript evidence are missing, stop and route the raw source to `$youtube-short-analyzer`.

## Hard gates

Reject a candidate before scoring when any condition applies:

- duration is outside the user's requested range;
- the sentence boundary hangs, or the answer/payoff is missing;
- the first meaningful idea starts later than 2 seconds after the cut;
- it relies on hidden context or changes the speaker's meaning;
- it is substantially redundant with a stronger selected clip;
- `religious_context_safe` is false;
- it contains unsupported accusations, unsafe claims, or misleading metadata.

Rights uncertainty is not a scoring penalty. Keep it as a separate `rights_review_required` gate that blocks rendering/upload until resolved.

## Score rubric

Score each eligible candidate from evidence, using these exact weights:

| Component | Points | Test |
|---|---:|---|
| Hook immediacy | 20 | Clear curiosity, tension, surprise, or high-value claim in the first 2 seconds |
| Standalone clarity | 20 | Viewer understands subject, claim, and stakes without prior footage |
| Payoff and ending | 15 | Delivers an answer/takeaway and ends cleanly or loops honestly |
| Retention density | 15 | Each beat advances the story; little silence, repetition, or filler |
| Emotional or practical value | 10 | Useful, relatable, moving, or discussion-worthy without manipulation |
| Specificity and novelty | 10 | Concrete detail or distinctive angle rather than generic advice |
| Editability | 5 | Speech, framing, and cut points can produce a clean 9:16 edit |
| Metadata fit | 5 | Accurate title, description, hashtags, and CTA are easy to derive |

`viral_score` is the sum, capped at 100. Do not raise a score to meet a quota. Compare with ClipForge's existing `score`, `retention_score`, `key_point_score`, `loop_score`, and `narrative_arc_score`; investigate large disagreements instead of averaging blindly.

## Ranking and diversity

1. Sort by `viral_score`, then payoff, standalone clarity, and hook immediacy.
2. Remove overlaps and near-duplicate topics. Prefer a smaller distinct batch over repeated variants of one point.
3. Select at most the requested count, default 3.
4. Apply the requested floor, default `viral_score >= 80`.
5. Label each result:
   - `90-100`: exceptional test candidate;
   - `80-89`: strong test candidate;
   - `70-79`: promising but needs a concrete edit or better boundary;
   - below `70`: weak source moment.

## Packaging

For every selected candidate, create:

- `title`: accurate curiosity, ideally concise and specific;
- `description`: two to four useful sentences, including context;
- `hashtags`: three to eight relevant tags, deduplicated;
- `cta`: one natural question after the payoff;
- `hook_overlay`: optional short text derived from the actual transcript;
- `edit_notes`: only changes supported by the source, such as trimming silence or emphasizing a verified keyword.

Never fabricate controversy, quotes, facts, or religious rulings to strengthen packaging.

## Output contract

Write `selected_clips.json` alongside the candidate manifest unless the user specifies another path. Preserve source identity and all original timestamps. Include:

```json
{
  "schema_version": 1,
  "source": "videos/kajian.mp4",
  "quality_floor": 80,
  "selected": [],
  "rejected": [],
  "selection_summary": {
    "requested": 3,
    "selected": 0,
    "outcome": "WEAK_SOURCE"
  }
}
```

Each selected item must contain the eight component scores, `viral_score`, `start`, `end`, `duration`, `transcript`, packaging fields, `risk_flags`, and `rights_review_required`.

If nothing reaches 80, return `WEAK_SOURCE` and specific source-selection advice. Do not render. Otherwise return `READY_FOR_RENDER` and pass the manifest to `$short-video-editor`.
