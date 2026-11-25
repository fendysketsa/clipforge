# 15 · Migrating an artistic language to a new subject

When to read: adding a new art style, applying an existing style to a different subject, separating near-neighbour styles, or when the user gives only an artist or studio name. If you only need one existing render parameter, read the matching practice card directly. This page studies artistic language; it does not replace the user's new story, scenes, and characters.

## First separate four things

- **Style language**: brushwork and material, colour relationships, lighting, form, spatial organisation. These should remain recognisable after the subject changes.
- **Compositional tendency**: for example an offset centre of gravity, group linkages, scale contrast. Re-solve it for the new frame and the new event; it is not fixed coordinates or the same layout in every shot.
- **Content and motifs**: the figures, clothes, bridges, boats, gardens, and deities in a famous painting. Unless this project needs them, they do not enter a new work automatically with the style.
- **Narrative and action**: who wants what, what resistance they meet, how the action changes the situation. Speed, camera movement, and beat come from the content; a quiet style can depict fast action, and limited animation can carry complex events.

Choosing an artist is not choosing a template from one famous painting. When a studio is named, first locate the art scope — film, director, period. Neither Ghibli nor Pixar shares a single drawing method across its whole output. Narrow the range using the user's examples and the subject; when several directions are equally reasonable, fold them into the existing three-direction concept sheets for selection rather than adding another formal approval round.

## Extracting across works

When establishing a range for the first time, usually look at at least 3 original works, or official clips from 3 different scenes, covering different subjects, scales, or lighting where possible. Consecutive frames, crops of the same painting, and the same composition recoloured do not count as independent samples. If material is insufficient, mark the gap clearly; do not pad the count or claim to have looked at something you have not. Cards that are mature and already evidenced can be spot-checked as needed; they need not be re-researched every time.

Write a short "style brief" and place it before or beside the project shot list:

1. Scope of application and source of the originals; verify attribution, medium, and period first.
2. 3–5 observable stable features, each noting which references support it and which do not apply.
3. Two points that distinguish it from the nearest-neighbour style. Renoir, Pissarro, and Sisley, for example, are not finished by sharing one broken-brushstroke filter.
4. The subject, event, space, and frame of this new scene; reconstruct them to fit the need, and do not lift them from the references.
5. Visual relationships to preserve, content that may change, and technical routes still to be validated.

Record "what appears in the painting" separately from "how the painter renders it". The palette records principal colour relationships and the organisation of light and dark; do not claim that a set of hex values is the artist's fixed standard palette; 3–6 principal colours do not mean every pixel may use only those colours. Texture, colour mixing, shadow, and reflection should serve the principal colour relationships. Existing colour preferences and gates apply as before; where an exception is genuinely needed, state the subject-based reason through the existing process and do not quietly disable the check.

## Validate the new scene first, then make it a capability

Start with concept sheets for this project's subject, still following the existing three-direction mechanism. Form, edges, light, and material for characters, animals, props, and background must be handled together; do not just apply a filter to the background. Choose the render route from current capabilities and state which part uses code, existing assets, the character frame library, or another approved tool.

The first time a research card is upgraded into a transferable recipe, stress-test it on different scenes, typically including character action, a scene with no people or only objects, and a scene that markedly changes scale or environment. Prompts may be inspired by the card's examples, but those examples must not become a new fixed template. Whether a landscape painter can handle a character close-up is within the to-be-proven range; do not promise in advance that every subject fits.

Check the still first: remove the artist's name and the famous work's signature objects — are form, colour and light, brushwork, and space still recognisable? Placed beside the near-neighbour style, is there a real difference? Then check motion: action contact, occlusion, texture coordinates, character identity, material consistency, and viewing at normal speed. A good still does not prove smooth animation; a sound written plan does not prove the image works.

## Be honest about status

- **Research recipe**: has sources and an explicit visual hypothesis and can guide attempts; has no dedicated implementation or image validation. A Markdown card with a matching name alone does not justify calling `render.py --solo <id>`.
- **Single-scene practice**: has implementation, output, and a check record, covering only that scene. Record reference parameters and failure boundaries.
- **Cross-scene validation**: different new scenes have passed independent image review, with the covered range recorded; animation validation is documented separately. Register procedural scenes under No. 08, and engine QA and delivery gates apply as usual.

One branch of a studio passing does not mean the whole family passes. A new card does not borrow star ratings, performance, or acceptance conclusions from old sample films. Same-room parameters in an old card are historical practice evidence and are only reference-worthy for a matching scene.

## Feeding experience back

Before use, read the card's scope, weaknesses, and latest measured results. After finishing, record in the card the date, task and scene, sources, implementation/output evidence, observations, fixes, validation status, and boundaries. If new evidence overturns an old conclusion, fix the original sentence and check the related routing; if a failure reproduces reliably, fix the tool first and test. User choices are recorded in the taste profile; a single work's features do not get promoted into rules for every work.

Source of this process: the October 2026 style-library expansion, where the user explicitly asked for attention to an artist's overall style and to fitting different creative subjects. Source research and implementation hypotheses are kept separate; entries with insufficient evidence stay in research status.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
