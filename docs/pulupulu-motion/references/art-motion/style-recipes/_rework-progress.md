# Rebuild Progress for the New Style Demos (from 2026-10-16, protocol see no. 16)

Old scenes (2026-10-15 version) are backed up in `_archive/scenes_20261016/`. The rebuilt new scenes overwrite `scripts/art-motion/engine/scenes/<id>.js` directly, same id, same `--film style_studies`.
Original reference material is not committed (re-run `fetch_reference.py` when needed); overview images and side-by-side images live in `assets/new-stylev2_evidence/` so later readers can re-check the scores.

Self-assessments are for ordering (protocol step 6); taste items belong to the author.

| id | Style | Status | Self-assessment | Independent review | Current weakness (to surpass first next round) |
|---|---|---|---|---|---|
| 38 | Giotto | Research recipe (after character rebuild) | ~70 | ~53 (first round) | Three figures' silhouettes pulled apart (different robe widths), hands changed to palm + fingers, both hands genuinely supporting the crate at the handover; still lacking crowd density, plaster too grainy |
| 42 | Guardi | Research recipe (v2 demo done, no independent review) | ~78 | — | Tower brushstrokes still read as stacked bricks; figures are silhouettes only; missing flickering white specks |
| 46 | Pissarro | Research recipe (v2 demo done, below 80) | ~75 | ~58 | Tree crowns look like cauliflower, trunks like palms; figures got hats but faces are still simple; the tree blocking the church has been removed |
| 47 | Sisley | Research recipe (v2 demo done, below 80) | ~80 | ~68 | Houses look like flat boards, windows into black blocks; poplars like seaweed; fixed the gap at the left edge, the telegraph poles, cargo changed to sacks |
| 48 | Gauguin | Research recipe (after repainting the woman's head) | ~74 | — | The woman changed to a profile + tall white cap crown + white cape collar, the calf given patches; the boy is still too simple, the trunk volume too large |
| 50 | Ma Yuan | Research recipe (v2 second round, closest to 80) | ~78 (second-round self-score, no independent review) | ~74 (first round) | Axe-cut strokes changed to short wide wedge strokes but still too dense; the trunk used one continuous thick line (in segments it read as bamboo joints, polygonal axe-cut read as arrows, both trials abandoned); the signature has only a seal; qa timed out loading under high machine load, so several still frames at different moments were used instead to confirm no errors and that motion exists |
| 51 | Persian miniature | Research recipe (after character rebuild) | ~72 | ~63 (first round) | Figures changed to Safavid type: slender, small head, tall turban with a red crown rod, waist-cinched long robe, small scattered flowers; the reader is too small, the face has no expression |
| 52 | South Park-style cut-out | Research recipe (v2 demo done, below 80) | ~75 | ~63 | Fixed: boarding one by one in a single column without overlapping, the stop sign no longer occluded, the near-Cartman hat colour replaced; the subject is still the show's title-sequence type |
| 39–41, 43, 44 | Piero, Raphael, Michelangelo, Lorenzetti, Cortona | Not rebuilt | old version ~35 | — | 39/40/43/44 go through the fresco channel (but the fresco channel currently has only the 38 example, itself only ~53, so do not treat it as a mature capability); 41 needs sculptural figures |
| 45 | Renoir | Research recipe (after character rebuild) | ~72 | — | Figures changed to a slender build (narrow shoulders, cinched waist, bell skirt, small head, curved arms), foreground a pair waltzing in an embrace (the woman in front); the background crowd is still small and too evenly spaced; missing the original's pastel skin glow |
| 49 | Chagall | Not rebuilt | old version ~40 | — | memory space: floating, tilting, colour blocks as emotion |
| 53 | Pixar | Not rebuilt | old version ~55 | — | material and subsurface light; three.js route |
| 54 | Ghibli direction | Not rebuilt | old version ~45 | — | cloud, wind, watercolour background density |

"Independent review" comes from a review agent that took no part in production on 2026-10-16, scoring against the no. 16 scoring sheet (its full report was not saved to disk; the key points have been folded into the table above and into the protocol). Self-scores and reviews differ by 7–17 points; take the lower one as authoritative. **None reached 80, so all are written as "research recipe" and not registered as production runs** — that is protocol step 6's own rule.

Evidence (overview image, six side-by-side original images): `assets/new-stylev2_evidence/`.

## How to Do the Next Round (Copy the Process That Worked This Round)

1. `fetch_reference.py` pulls 3 originals → look at the contact sheet → write 5 signatures (must-have / bonus / forbidden).
2. Re-set the subject by the style's own composition rules; form layer → `scripts/art-motion/engine/lib/medium.js` channel.
3. One frame first → `side_by_side.py` side by side → score. At most two rounds.
4. When done, add it to this table and change the recipe card's "Status" and "Still improvable" to measured conclusions.
| 43 | Lorenzetti | Research recipe (v2 three rounds, after character rebuild) | ~72 | — | Figures changed to slender long robes in 3/4 turn with a 20-person crowd; still missing the original's paint-layer thickness and perspectival depth; only two different originals |
| 40 | Raphael | Research recipe (v2 one round, figures reuse `figure`) | ~70 | — | Perspective coffered vault and chequerboard floor hold up, three groups' hands and eyes interlock; figures are still bell-robed with duplicate faces; missing the original's skin tones and fabric sheen |
| 41 | Michelangelo | Research recipe (v2 two rounds, red chalk drawing route) | ~70 | — | S-shaped torsion, long arms, shoulder blade / latissimus shading hold up; head still too round, missing hand detail; the bare-paper contrast in the lights could be stronger |
| 44 | Cortona | Research recipe (v2 three rounds: cloud masses reworked) | ~70 | — | Frame + gold roundel + central radiating gold light + cloud masses + rotating crowd + red and blue drapery bands hold up; figures are still bell-robed, missing the Baroque's strong foreshortening and strong chiaroscuro; the cloud highlight arcs are too cartoonish; only two different originals |

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
