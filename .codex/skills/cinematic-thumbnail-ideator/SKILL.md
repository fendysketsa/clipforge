---
name: cinematic-thumbnail-ideator
description: Create truthful, high-impact cinematic thumbnail concepts and image-generation prompts from ClipForge clip evidence. Use when a user wants thumbnail ideas, A/B/C variants, keyframe direction, or a ClipForge-compatible thumbnail manifest. Do not render video, upload, publish, copy a reference design exactly, or invent people, events, quotes, and claims absent from the clip.
---

# Cinematic Thumbnail Ideator

Turn a finished ClipForge clip, candidate, transcript, or sidecar into thumbnail directions that remain readable at feed size and faithful to the source. Treat supplied thumbnails as mood references only: extract broad principles such as contrast, scale, energy, depth, and hierarchy without copying their wording, branding, faces, logos, or composition one-for-one.

## Required evidence

Use the strongest available combination of:

- clip title and transcript or candidate text;
- `hook`, `core_message`, and editorial angle;
- actual keyframes or `thumbnail_frame_seconds`;
- `thumbnail_eyebrow`, `thumbnail_headline`, and `thumbnail_support` from the sidecar;
- source identity only for factual grounding, never as promotional branding.

If the transcript or sidecar is missing, produce a provisional concept and label unsupported visual details as `needs_frame_review`. Never invent a facial expression, location, object, conflict, quote, religious ruling, or outcome.

## Creative target

Aim for an original Indonesian YouTube aesthetic with the cinematic energy of leading feed thumbnails:

- one instantly readable idea, not a synopsis;
- a dominant subject or object occupying roughly 45–65% of the frame;
- clear foreground, midground, and background separation;
- strong warm/cool contrast, controlled glow, rim light, and localized depth;
- one emotional or narrative tension supported by the clip;
- headline of 2–6 words, ideally no more than 28 characters per line;
- at most two headline lines plus one small eyebrow or badge;
- large type, thick outline or shadow, and generous negative space;
- visual drama from lighting, crop, scale, gesture, or evidence—not fabricated shock.

Avoid tiny track lists, walls of text, excessive badges, random arrows, emoji clutter, fake screenshots, misleading before/after imagery, copied channel marks, and decorative effects that obscure faces or evidence. Do not promise CTR, views, virality, or monetization.

## Workflow

1. Identify the single payoff, question, contradiction, or emotional beat actually present in the clip.
2. Select the best real keyframe. Prefer a clear face, gesture, meaningful object, or decisive scene; avoid blinking, motion blur, subtitles across faces, and source logos.
3. Create three genuinely different concepts:
   - **A — Human tension:** face or gesture leads; text states the unresolved tension.
   - **B — Evidence/object:** meaningful object, place, or visual proof leads; text names the discovery.
   - **C — Cinematic story:** wider environmental composition; text frames the stakes or payoff.
4. Choose a winner using the scorecard below. Do not make three cosmetic color variants of one layout.
5. Write an image-generation prompt that preserves identity and the real scene. Generative enhancement may improve lighting, separation, cleanup, and atmosphere, but must not replace the factual content.
6. Return the compact response and, when working with repository files, write `<clip-stem>_thumbnail_ideas.json` beside the clip sidecar. Do not overwrite an existing rendered thumbnail unless the user explicitly asks.

## Scorecard

Score each concept from 0–100:

| Component | Points | Test |
|---|---:|---|
| Feed-size readability | 25 | Main idea and headline remain clear at roughly 320 px width |
| Truthful curiosity | 20 | Creates a question without changing the clip's meaning |
| Subject hierarchy | 20 | Eye reaches the intended face/object first |
| Emotional specificity | 15 | Expression, gesture, or stakes are concrete and supported |
| Cinematic craft | 10 | Lighting, depth, color, and framing feel intentional |
| Brand distinction | 5 | Looks original rather than copied from the reference |
| Production feasibility | 5 | Can be made from available frames/assets without fabrication |

Recommend the highest-scoring concept only when it has no truthfulness blocker. If all variants are weak, return `NEEDS_BETTER_FRAME` with a precise frame or asset request.

## Prompt contract

Every variant must provide:

- `angle`: the one-sentence viewer promise;
- `eyebrow`: optional 1–3 words;
- `headline`: natural Bahasa Indonesia, 2–6 words, no fake quotation marks;
- `support`: optional, maximum 7 words;
- `keyframe_direction`: timestamp or observable frame criteria;
- `composition`: subject placement, crop, text zone, and depth layers;
- `palette`: 2–3 dominant colors with contrast intent;
- `image_prompt`: explicit aspect ratio, real subject/scene preservation, lighting, hierarchy, text-safe area, and exact visible copy;
- `negative_prompt`: distorted anatomy, altered identity, duplicate people, unreadable text, extra fingers, fake logos, watermarks, clutter, oversaturation, plastic skin, and unsupported objects/events;
- `evidence`: the transcript/sidecar facts supporting the concept;
- `score` and `score_breakdown`.

For long-form YouTube, use 16:9 and design at 1280×720 or higher. For Shorts, use the real 9:16 cover frame and keep the headline inside the central UI-safe area; do not pretend a custom Shorts thumbnail upload is guaranteed.

## Output contract

Return a short summary naming the winner, then valid JSON with this shape:

```json
{
  "schema_version": 1,
  "source_clip": "clip.mp4",
  "format": "youtube_16_9",
  "status": "READY_FOR_DESIGN",
  "winner": "A",
  "selection_reason": "",
  "needs_frame_review": false,
  "variants": []
}
```

Use `format: "shorts_9_16"` for a vertical cover. Each `variants` item follows the prompt contract above. Keep all claims traceable to `evidence` and preserve source attribution outside the artwork in the platform description/caption.
