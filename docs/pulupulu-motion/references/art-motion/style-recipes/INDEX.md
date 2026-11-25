# Style Master Index (36 existing production runs + 16 research recipes, updated 2026-10-15)

> **Read this sentence first: the 35 sample frames share one composition** (window at upper left, cat at lower left, girl standing at the right holding a cup; `assets/all-styles-overview.jpg` too). That is the mechanism of the art-history speedrun film — the style changes, the scene does not — not the composition of these styles. For a new subject, re-compose for that subject: the renderers, brushwork, colour logic and motif motion in the cards can be taken; the coordinates, characters and furniture in the room must not be carried over.

When choosing a style, look at the status and category tables below first, then open the corresponding card. "Quality" is the current production level (★★★ recognisable at a glance, directly usable; ★★ recognisable but with obvious weaknesses; ★ needs redoing), not the intrinsic difficulty of the style. A weakness is what to surpass first the next time you do this style.

Styles split into two layers. **Material layer**: brushwork, material, and the handling of light and colour, which can sit on any subject (products, data, storytelling all fine). **Period specimen**: the current sample frame makes the period or the artist's motifs prominent; copying it directly suits speedruns, time travel, homage; moving it to a new subject should re-distil the visual language and composition, and the sample's limitations must not be treated as the artist's own limits. When unsure, put it in the material layer; when a style straddles both (e.g. Hopper's hard-edged light blocks are a transferable lighting treatment), judge by your use.

## Check Status and Transfer Scope First

The new research cards have an attached single-scene project trial (`--film style_studies`), watchable, but they have not passed style fidelity and cross-scenario verification; the star ratings of the existing cards below do not apply to them. For a first cross-subject use read [method 15](../15-style-transfer.md). Material layer/period specimen is how the existing sample frames are organised, not a permanent restriction on which subjects an artist's overall style can carry; whether it transfers is decided by the new scene verification. Content and fixed coordinates in famous works do not enter the style definition.

## New Research Recipes (17; rebuilt one by one under protocol 16 from 2026-10-16)

**Rebuild status**: 38 Giotto, 42 Guardi, 45 Renoir, 46 Pissarro, 47 Sisley, 48 Gauguin, 50 Ma Yuan, 51 Persian miniature and 52 South Park have had their demos rebuilt under [protocol 16](../16-style-demo-95.md) (original anchoring + `scripts/art-motion/engine/lib/medium.js` medium channel). Self-scores 65–82, independent reviews 53–74 (42 and 45 not reviewed), **none reached 80, so all of them are still "research recipes", not production runs**; taste items await the author; the remaining 8 are still the old 10-15 trials (quality about 35–55, do not treat as usable production runs). Progress and each one's weaknesses in `_rework-progress.md`. Old versions backed up in the skill root `_archive/scenes_20261016/`.

| Card | Research scope | Implementation status |
|---|---|---|
| [38_giotto](38_giotto.md) | Giotto: mass and narrative relations | Research recipe; single-scene prototype |
| [39_piero](39_piero.md) | Piero: geometric order and clear volume | Research recipe; single-scene prototype |
| [40_raphael](40_raphael.md) | Raphael: harmonious organisation and natural connection | Research recipe; single-scene prototype |
| [41_michelangelo](41_michelangelo.md) | Michelangelo: sculptural quality and tension of pose | Research recipe; single-scene prototype |
| [42_guardi](42_guardi.md) | Guardi: air, broken light and loose edges | Research recipe; single-scene prototype |
| [43_lorenzetti](43_lorenzetti.md) | Ambrogio Lorenzetti: readable social space | Research recipe; single-scene prototype |
| [44_cortona](44_cortona.md) | Pietro da Cortona: Baroque mass and flowing groups | Research recipe; single-scene prototype |
| [45_renoir](45_renoir.md) | Renoir: interwoven warm and cool, figures with warmth | Research recipe; single-scene prototype |
| [46_pissarro](46_pissarro.md) | Pissarro: the flow of life and figures within their setting | Research recipe; single-scene prototype |
| [47_sisley](47_sisley.md) | Sisley: air, weather and coherent landscape | Research recipe; single-scene prototype |
| [48_gauguin](48_gauguin.md) | Gauguin: flatness, contour and symbolic colour | Research recipe; single-scene prototype |
| [49_chagall](49_chagall.md) | Chagall: memory space and emotional colour | Research recipe; single-scene prototype |
| [50_ma_yuan](50_ma_yuan.md) | Ma Yuan: off-centre weight, empty space and spare brushwork | Research recipe; single-scene prototype |
| [51_persian_miniature](51_persian_miniature.md) | Persian miniature: layered space and precise narrative | Research recipe; single-scene prototype |
| [52_south_park](52_south_park.md) | South Park: digital cut-out and limited performance | Research recipe; single-scene prototype |
| [53_pixar](53_pixar.md) | Pixar: a style family of form, material and performance | Research recipe; single-scene prototype |
| [55_dunhuang](55_dunhuang.md) | Dunhuang murals (Northern Dynasties): mineral colour on dry mud plaster and lines flying sideways | Research recipe; single-scene prototype (v1, ~72) |

Ghibli does not count as new: [25_ghibli](25_ghibli.md) keeps its original watercolour-background production run and adds an overall visual and performance study; the latter cannot borrow the old scene's measured results.

## Material Layer (Can Sit on Any Subject)

| id | Style | Core renderer / technique | Motif motion (how the picture comes alive) | Signature transition (entering it) | Quality | Current weakness |
|---|---|---|---|---|---|---|
| 09_postimp | Van Gogh | flow-field brushstrokes in three passes (walls vertical-long / ground in perspective / the rest) + regional palettes + outlines; prop layer; visibleLines touch-up | starry-sky vortices, lamp halos expanding outward, direction field flickering like flame, vortex cat | starry vortex pulls in | ★★★ (benchmark) | 120ms per frame, the heaviest |
| 08_impressionism | Impressionism | short brushstrokes with a regional pastel palette (fixed positions), fine strokes in the window view | light dapples drift and flicker, poppies sway, clouds move, ribbon flutters | brushstroke colour dots fill the screen | ★★ | faces and hands shredded by the strokes |
| 29_seurat | Seurat pointillism | optical colour mixing: 21-colour pure palette juxtaposed in proportions, complementary dots, equal-sized dots | light diffusion, dots breathing | the picture crystallises into dots | ★★ | too static; grid too regular |
| 25_ghibli | Ghibli (existing watercolour background + overall language study) | watercolour washes (transparent layering + water-mark edges), cel crescent shadows | gauze curtain billowing in the wind, grass blades swaying in sheets, tree-shadow dapples | wet paper bleeding | ★★ | characters weaker than the background |
| 17_ink | Chinese xieyi ink | brush-tip flying white, ink bleed blurred out, empty space, seals | the opening strokes write themselves, ink bleed spreads, shrimp antennae move | (opening in the speedrun) | ★★ | characters not xieyi enough (review 6/10) |
| 13_pop | Lichtenstein pop | Ben-Day dots via createPattern, thick black outlines | Warhol four-panel colour swap, thought dots flash, cat wiggles its hips, onomatopoeia box shakes | lightning + halftone | ★★★ | — |
| 14_8bit | 8-bit pixel | 240×135 per pixel, 14-colour palette, 1px black outline on parts | tail, HUD hearts flash, ? block bumped for coins (15–30fps stepping) | pixel blocks scale up and down | ★★★ | cat's head clips the windowsill |
| 26_vaporwave | Vaporwave/cyber neon | two-colour neon glow, perspective grid, VHS channel-separation post, kana drawn as light tubes along paths | sunset bars rise, grid rolls forward, sign flickers, tracking noise band | VHS tearing + roll-up | ★★★ | part boundaries glow too |
| 35_shinkai | Shinkai light and atmosphere | cumulonimbus, Tyndall shafts, cel hard shadow bands, bloom | light particles drift, clouds move | diagonal light sweep | ★★ | interior background density too low |
| 32_rembrandt | Rembrandt chiaroscuro | whole-frame lighting map multiplied, window light + candlelight | dust in the light shaft, cloud shadows dim the window light | old-film iris in and out | ★ | figures flat (review 5/10), most in need of a redo |
| 11_cubism | Analytic Cubism | translucent gradient planes stacked in space, facet cutter (triangles not clipped), Picasso-style two-view face | CAFÉ letters swap, window-pane facets slide, newspaper trembles | geometric fragments shift and reassemble | ★★ | too bright, large dark-brown planes insufficient |
| 30_matisse | Matisse cut-outs | irregular scissor edges, pinned-paper shadows, saturated flat fill | paper shapes flutter, seaweed sways | the blue paper with pinned cut-outs sweeps past | ★★★ | gouache brush marks too heavy |
| 16_2026 | Contemporary flat illustration | grain stipple density function, unoutlined colour blocks | character performance (jump / clap cup / shatter / gasp / sign), damped secondary action | three-colour concentric ring aperture | ★★★ | — |
| 22_constructivism | Russian Constructivism (narrow use) | greyscale photo halftone (variable dot diameter 45°), red wedge black circle, Cyrillic block letters drawn on paths | slogan stamped letter by letter, then bouncing in a wave | (B film opening) | ★★★ | missing the megaphone-shaped letter cone |
| 12_bauhaus | Bauhaus (narrow use) | pure geometric composition, Schlemmer figure joint discs | clock hands turn steeply, Mondrian grid colour swap, cat bats a ball | red-yellow-blue geometric shape rotates and scales | ★★★ | cat's head off the armature position |
| 04_roman | Pompeii mosaic (narrow use) | distance field placing stones along contours, weighted L∞ Voronoi mortar, layout computed once and colour flowing each frame | wave-band border scrolls clockwise, Vesuvius smokes and throws sparks | mosaic tiles flip and spread out from the cat | ★★★ | little facial detail at small scale |
| 15_raytrace | Early ray-traced CGI (narrow use) | uniform plastic shading, per-pixel chequerboard reflection, chrome ball environment mapping | purple ring rotates, lens flare, green glow in the cat's eyes | green wireframe → scanline render | ★★ | cat legs are straight posts, face like a mask |

## Period Specimens (Suited to Speedruns, Time Travel, Homage)

| id | Style | Core renderer / technique | Motif motion (how the picture comes alive) | Signature transition (entering it) | Quality | Current weakness |
|---|---|---|---|---|---|---|
| 01_cave | Cave rock art | noise-relief rock wall + ragged charcoal dot edges + ochre soaked into the rock face | animals run alternating two poses, firelight flickers, embers | (opening) | ★★★ | human figures too cartoonish, not primal enough |
| 02_egypt | Egyptian tomb painting | profile face with frontal eye convention, flat fill with fine outlines, 24 hand-written hieroglyphs | scarab pushes the sun, Aten's rays with little hands opening and closing, hieroglyphs rewritten stroke by stroke | tapestry strip drops and bounces | ★★★ | elbow holding the cup too stiff |
| 03_greek | Attic black-figure | black silhouette + terracotta incised lines + purple-red band with white dots | meander band scrolls in reverse, boat rises and falls with leaping dolphins, lyre sways | pottery vase rotates on a roller | ★★★ | skirt hem too thick |
| 05_gothic | Gothic illuminated manuscript | per-pixel gold leaf (brushed + embossed, 1px bright line offset), giltness mask highlights | gold leaf highlight sweeps diagonally, vines sway, snail crawls, mouse runs | parchment page turn | ★★★ | gold hair reads as a hood |
| 06_renaissance | Renaissance sfumato | a whole layer lightly blurred + a high-opacity sharp layer, craquelure / canvas weave / yellow varnish | da Vinci's ornithopter flies past, broken light on the river, floating dust | divine light through a window | ★★ | cat too cartoonish; overall too static |
| 10_nouveau | Mucha Art Nouveau | variable-width paths (thick outside, thin inside), offset silhouette underlay | sun rises, halo rotates, flowers sway, S-shaped heat, wavy hair | gold-edged organic form grows | ★★★ | cat's pose stiff |
| 18_klimt | Klimt Golden Phase | reuses the Gothic gold leaf, spiral/eye motifs, realistic face against a flat gold robe | eye motifs on the robe blink in turn, gold flakes drift | gold leaf spirals out from the head | ★★★ | the hands on the table do not join the sleeves |
| 19_munch | Munch expressionism | long curved streamline strokes (20–30 steps along the flow field), per-row sine warp of the whole world | the whole painting writhes, blood-red sky flows | Scream colour bands press down from the top | ★★ | the wall was once read as Van Gogh |
| 20_dunhuang | Dunhuang murals | earth-red ground with mineral colour, flaking spots (background only), saturation fading | apsara ribbons, ceiling streamers, lamp flames | ribbon sweeps past, old paint flakes and falls | ★★ | apsara shapes crude |
| 21_kusama | Kusama polka dots | hand-drawn irregular circles, hexagonal grid modulo the true period | dots swell and shrink ring by ring from the cat, pumpkins, infinity mirror room | dots grow and clip the new painting | ★★★ | figures the same colour as the wall, held only by outline |
| 23_dali | Dalí surrealism | melting clock deformation, long-shadow shear affine | clocks drip, long-legged elephants walk, ants circle a watch, shadows lengthen | new painting drips down with round-headed droplets | ★★ | figures too vector-illustration |
| 24_hopper | Hopper American realism | two-version light/shadow cutout (light and dark versions clipped by light block), hard-edged light patches | light patch slides slowly across the face, a figure's shadow on the wall drinks tea in sync | hard-edged sunlight sweeps past | ★★★ | cat in shadow the whole time |
| 27_kirby | Marvel Kirby cosmic era | four-colour halftone, misregistered plates, black shadow masses feathered with hatching, krackle energy dots | large onomatopoeia, panel close-up of the cat's eye, energy dots | (C film opening) | ★★ | more like Lichtenstein, missing Kirby perspective and blocky hands |
| 28_monet | Monet water lilies and Japanese bridge | short brushstroke reflections on the water, light trembling on the surface | lilies drift, willow shadows sway, ripples spread | water ripples out | ★★ | wall is pond water, floor is wood — awkward space |
| 31_haring | Keith Haring | thick black uniform-width lines, radiating action lines | figures dance in hard 8fps cuts, everything bounces to the BPM | dancing figure scales up, a new painting inside its body | ★★★ | the girl is not Haring enough |
| 33_rubberhose | 1930s rubber-hose cartoon | pie-cut eyes, noodle arms, white gloves, 12fps stepping, film scratch flicker | everything bounces on the beat | (old film before the lamp is lit backstage) | ★★★ | most of the motion is film noise |
| 34_shadowpuppet | Chinese shadow puppetry | translucent cut-out leather, riveted joints, 10fps stepping, oil lamp behind the screen | rods control stiff joints, wrist flicks | lamp lit behind the screen | ★★★ | overlaps multiply to black; 121ms too slow |
| 36_picasso_blue | Picasso Blue Period | monochrome blue, broad strokes, Prussian-blue thick outlines, elongated bodies | slow breathing | colour drained to blue, then a broad brush sweeps | ★★ | shapes not melancholy enough |
| 37_rick_morty | [Rick & Morty](37_rick_morty.md) | SVG rounded dark-grey fine outlines, flat fill, mottled background | holding a cup, blinking, gaze, tail wag | set separately per narrative | ★★ | separate SVG preview/render, not in the old 35-style Canvas gallery; no walking rig |

## Quality Distribution and Next Steps for the 36 Existing Production Runs

- ★★★ 20 styles, ★★ 15 styles, ★ 1 style.
- **The most common weakness is the character**: once a background goes through the style renderer it looks like that style, but characters using only a vector armature with flat fill look pasted on (positive experience no. 8). The next quality round starts with "characters also go through the same renderer / are reshaped in that style": Rembrandt, Picasso blue, ink, Ghibli, Dalí, Marvel.
- Transition collection: `_transition-migration-test.md` (A–D add 19) + notes inside each card.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs: narration and voice timing → skill **`tts-intonation`** · merging or translating another
library → skill **`agent-skill-sourcing`** · rights and likeness review before publishing → skill
**`media-content-safety`** · sourcing a reference video → skill **`streaming-mirror-extraction`** ·
3D or footage-based shots → skills **`headless-three-video-render`** and **`cinetic`** ·
type-first films → skill **`kinetic-typography`**.
