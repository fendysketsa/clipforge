# Y6 · Presenter-style finance explainer

A cartoon presenter strings information together across paper, charts and keywords. Suitable for business history, product mechanics, and knowledge explainers with emotional reactions. Reference code is in `scripts/art-motion/engine/reference_films/spacex/spacex_lin/`; this is the 9th grammar card, and currently it has no standalone parameterised clip and no character sprite attached.

## Pre-flight checks

- Allocate layouts in the storyboard first: side-on presenter, full-screen numbers, left/right comparison, character stepping into the diagram, reaction close-up. Do not fix presenter-left/diagram-right for the whole film.
- Prepare generated frames in at least two framings, full body and bust; sitting and leaning poses need real corresponding frames.
- The first `cast` keyframe of each segment must give `x` and `s` explicitly, to prevent inheritance across segments causing regressions.
- For nested drawing use `*=` for opacity, so the outer fade-out is preserved.
- The top-bar year, subtitles and segment titles read from the same time source.
- Run `qa.py` text-box framing on the first version; once there is a light-background cut without subtitles, run `subzone_gate.py` too.

## Frames and motion

The character uses AI-generated frames, with code controlling the foot anchor, position, size and frame switching. Pose changes cut hard with a slight pop, avoiding different silhouettes dissolving into a double image. Talking and mouth-closed switch with the voiceover timing; the mouth stops during pauses; walking uses full gait frames. Pose heights are aligned by median; reaction close-ups use bust assets, never a hard upscale of a whole-frame screenshot.

Numbers land when the voiceover reads them. During the count, do not assert ahead of time with "over", "+" and the like; the emphasis circle appears after the number lands. The pause after the highlight must be left in at the script and voiceover stage.

## Reference implementation

`common.js` provides `presenterFrame`, `drawFigure`, `hud`, `yearAt`, `popK` and `L.cast`. `prep_presenter.py` demonstrates frame switching and the foot anchor. The transition `transitions/lin_page.js` only turns the page; the presenter and the top bar can continue across pages.

Known limitations: the character occluding text and the character being cropped by a push-in still need eyeball review; pushing in on full-frame bitmaps in the reference code crops easily, so new films should prefer a scene camera. Assets and voiceover must be supplied by you; this card cannot be used directly as a complete film template.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
