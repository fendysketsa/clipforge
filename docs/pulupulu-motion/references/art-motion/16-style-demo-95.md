# 16 · Style demo protocol: from "flat illustration inspired by it" to "a painting you recognise at a glance"

When to read: when making or remaking any art-style demo scene (`scenes/<id>.js`), or when handing this page's path to an agent doing it. Issue 15 covers "how to research a style and how to transfer it"; this page covers "what level the demo has to reach to count, and how to get there step by step".

## Why the 17 demos added on 2026-10-15 are almost unusable

On 2026-10-16 we rendered them to stills and looked at them side by side, then pulled public-domain originals for comparison, and found five root causes (the great majority of the 17 fit; 45 Renoir is an external bitmap plus mesh warp and 44 has a valance, so they are not flat vector blocks, but they equally lack original anchoring and a medium layer):

1. **Nobody looked at the originals.** The recipe cards held only text descriptions and collection links, so whoever made them (the agent) drew from impression. The result: most images are the same modern flat illustrator with a different swatch set — the shapes are clean vector blocks and the style is reduced to "a palette plus a layer of grain".
2. **The card wording also took the anchor away.** "Don't generalise from a single famous work" and "don't copy the composition" were meant to prevent plagiarism; in practice they became "you are not allowed to work from the original". What should be prevented is copying the figures and coordinates of a famous painting, not learning its brushwork, its materials, its colour relationships and the logic by which figures are built.
3. **There is no "medium" layer.** The old benchmarks (09 Van Gogh, 17 ink wash) are strong because they push the picture through real art materials: flow-field brushstrokes, flying white, ink bleed. The new scenes are 35–70 lines that draw only shapes and never pass through art materials.
4. **One subject wrapped in every style.** Washing machines, water wheels and machine repair kept recurring (this round of rework did not fully avoid it either: 38 and 47 both have "wooden crate / cargo", and 51 uses the water-lifting wheel again — 47 has been changed to sacks, the rest are listed in the progress table to be fixed). Each style's own narrative logic (Ma Yuan's one corner, the all-over coverage of miniature painting, Gauguin's cropping, Giotto's lines of sight) was flattened away.
5. **No score threshold.** Self-check had only qa's technical items (it renders, it is deterministic, it doesn't flicker); nobody held up the original and asked "does it look like it", so anything that ran for 6 seconds counted as delivered.

## Protocol (in order, every step leaves an artifact)

### 1. Anchor in the originals

```sh
uv run <skill>/scripts/art-motion/analyze/fetch_reference.py --out <project>/reference/<style> "artist work A" "artist work B" "artist work C"
```

At least 3 **different works** (issue 15's standard). The script pulls public-domain images from Wikimedia Commons, saves them locally, extracts the dominant palette and produces a contact sheet. Then **actually look at that contact sheet** and write down:

- 5 signature features, each classified as "must have / bonus / forbidden". Example, Ma Yuan — must have: one-corner composition, large areas of empty space, axe-cut texture strokes; bonus: weeping willow, tiny figures looking into emptiness; forbidden: filling the whole frame, bright saturated colour.
- Dominant palette (use the colour values the script extracted; state what the lights lean toward and what the darks lean toward).
- How this kind of painting is physically made in reality (brushed, carved, drawn, spread, pasted). That physical process is the spec for the renderer.

### 2. Rebuild the composition of the subject by the style's own logic

Don't transplant the figures and coordinates of a famous work, but learn **how it organises the picture**: Ma Yuan's empty space plus one corner; miniature painting standing the ground up and covering it edge to edge, cutting buildings open; Gauguin cropping the foreground and dividing with diagonals; Giotto locking figures together with lines of sight; Impressionism giving half the frame to sky and letting the water drag the bank into broken strokes. Write one sentence, "this style's composition rule", then lay out the new subject by it. **One subject may not be wrapped in a second style.**

### 3. Draw "clean shapes", then pass them through a "medium channel"

Laying grain over flat vector is forbidden as a way of doing style. A scene has two layers:

- Shape layer: draw objects, people and space clean (Canvas paths or an offscreen canvas are fine).
- Medium layer: push the shape layer through real art materials with `scripts/art-motion/engine/lib/medium.js` or the older library.

| channel | what it does | used for |
|---|---|---|
| `MEDIUM.broken(src, o)` | redraw as stroke-by-stroke curved strokes, lights warmer and darks cooler | Impressionism (Sisley, Pissarro, Guardi, Renoir) |
| `MEDIUM.fresco(c, plate, o)` + `MEDIUM.plaster` | pigment eaten into the lime plus plaster grain, pinholes, seams | fresco (Giotto, Piero, Raphael) |
| `MEDIUM.silk` + `P.brush` / `P.inkWash` | silk weave, flying white, ink in five tones | ink wash (Ma Yuan) |
| `MEDIUM.flat(c, path, fill, o)` | cloisonné enamel: short strokes along the brush direction inside each flat colour block, plus thick, uneven dark contours | Gauguin, Synthetism, stained glass |
| `MEDIUM.figure(c, o)` | clothed figures with volume: robes, cloaks, folds, lines of sight | fresco, miniature, flat narrative |
| `MEDIUM.outline / hatchFill` | variable-width lines, hatching | woodcut, engraving, miniature shadows |

When the library has no matching channel, write a channel function into `medium.js`; don't hard-code it inside one scene.

### 4. One frame first, side by side

Produce stills first, don't animate first.

```sh
uv run --with playwright python <project>/render.py --film style_studies --solo <id> --stills 3 --no-counter --out render/<id>
uv run <skill>/scripts/art-motion/analyze/side_by_side.py --ref reference/<style> --frame render/<id>/t003.00.png --out compare/<id>.jpg
```

"a painting you recognise at a glance" can only be answered with this side-by-side image in hand.

### 5. Make the picture live: use the style's own motion logic

One main action plus 2 motif loops (issue 08, item 3). Each style's own way of moving: ink follows the wind, brushstrokes breathe, the water surface tears reflections apart, a fresco barely moves but lines of sight and handoffs move. Don't give every style the same fade-in/fade-out.

### 6. Score, threshold 80, at most two rounds

| item | points | how to judge |
|---|---|---|
| signature hits | 35 | tick off each "must have" from step 1; each miss costs 7 |
| credible medium | 20 | zoom to 1:1 and look: real art material or vector plus grain |
| composition and narrative | 15 | is the style's own organising method used, is the event readable at a glance |
| figure and object construction | 15 | is there weight, is there relationship; if it reads childish or like a sticker it scores below 8 |
| motion | 10 | alive without flicker, motion lands on the event |
| technical | 5 | qa determinism, framing, runtime |

**Two single-vote vetoes**: signature hits below 25; figures or the main subject read as childish (doodle-like). AI judges only the factual items; taste items (is the composition good-looking) are left to the author, the self-score is for ranking only and is not written up as "passed". If it is still below 80 after two rounds, write the status as research recipe, put the sticking points into the card's "still improvable" field, and don't register it as built.

**Self-assessment inflates.** For the 2026-10-16 batch, self-scores ran on average about 10 points above independent review (17 at most). So: the score table must carry item scores and the signature checklist; the independent review score is written next to the self-score and the lower one governs; if the "current weak point" column of the progress table contains a veto item, the status may not be written as "done".

## Rules for figures (the easiest link to break in the newly added styles)

This section is **merged into one** with the figure rules of SKILL.md's narrow bridge; this one governs:

- **General styles**: real people / the person themselves / anthropomorphic characters go through AI-generated frames plus matting (methods B/C); code handles only position, frame swapping and materials; with no image-generation capability, show only hands and backs.
- **Narrow exception (deliberately chosen flat-narrative styles where code may draw people)**: 37 Rick & Morty, 52 South Park-style cut-out, plus the fresco / miniature / Synthetism demos reworked on 2026-10-16 (38 Giotto, 48 Gauguin, 51 Persian miniature). These three are **research-grade demos, not character solutions for a delivered film**: when a protagonist the audience must identify with has to appear in a delivered film, still go through B/C.
- Figures in the exception still need weight and lines of sight: pupils turned toward the other person, hands reaching for the object, folds following the load. Doodle-style round head plus pill body fails.
- Don't enlarge a figure you can't do well: shrink it to a long shot, turn it into a back view, or let the frame crop the foreground figure.
- Don't borrow the costume colour combination of a named character (52 was changed for this reason, from teal hat with pale pompom); and don't copy the original's title-sequence composition wholesale either.

## Known pitfalls

- **Originals pulled back must be checked against the contact sheet**: search mixes in maps, modern photographs and museum-wall reproductions in gold frames (the third item for 42 Guardi is a photo of a modern church, the third for 47 is a framed reproduction, the first and third for 50 are the original of *Early Spring Walk on a Mountain Path* and a recoloured version of the same painting). `fetch_reference.py` only does approximate de-duplication and samples colour from the central 80%; it cannot tell "is this by this painter" or "are these three different works" — a human looks at that. Before writing a work title into the scene header comment, confirm it against the contact sheet.

- Draw the shape layer first, then redraw, and **draw the canvas the redraw uses in local coordinates** (a boat, say); don't repaint the whole screen every frame or it is slow. Small moving things like boats and people: draw to a small canvas → `MEDIUM.broken` → paste back.
- In the nine-argument form of `drawImage`, if `sx+sw` exceeds the source image width, the excess comes out blank; for sky drift use `sx = t*speed` and make the source wider than the stage (47's sky is 2600 wide).
- Small dots at edge notches had two sources, both fixed: the base image of `M.broken` is now expanded by 14px before blurring; when displacing the water surface row by row the target width must be widened (`dx-24, W+48`), otherwise the underlying base colour shows at both ends of the displacement.
- Ma Yuan-type ink wash: hanging strands must come in clusters, curved, of uneven length — evenly spaced vertical lines read as a fence. Figures always go "back view plus one stroke of drapery line plus reserved silk", never filled in.
- Gauguin-type: shapes are always round, never zigzags; zigzag figures read as emoji.

## This round (2026-10-16) progress and self-assessment

See the status column of `references/art-motion/style-recipes/INDEX.md` and `style-recipes/_rework-progress.md`. Self-assessment is for ranking, not an acceptance verdict.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
