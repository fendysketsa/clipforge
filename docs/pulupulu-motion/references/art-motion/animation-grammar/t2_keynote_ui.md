# t2_keynote_ui · Keynote-style interface and gradient motion

> One-sentence grammar: **one thing per screen, the product itself (screenshot, screen recording, physical object) as the hero, nouns and numbers settling when the narration reaches them; type tightened, springs with no bounce or light bounce.** Glow-blob gradient grounds, frosted-glass cards, gradient type, centred blur-in and decorative float are all optional packaging — use sparingly (see "Check before you start").
>
> Demo film: `scripts/art-motion/engine/demos/t2_keynote_ui/` (render with `render.py --film demos/t2_keynote_ui`) (8s, 3 shots) · overview `assets/animation-grammar/t2_keynote_ui_overview.jpg` · code `scripts/art-motion/engine/demos/t2_keynote_ui/`

## Check before you start

1. **This set is the easiest to read as an AI template.** Glow-blob ground + frosted-glass card + gradient type + centred blur-in + floating cards: put all five up together and the viewer recognises a template instantly. Before you start, ask: is there a real product screenshot, screen recording, photograph of the thing? If yes, let it be the full-frame main image and push in to the part you are talking about, with no blobs and no glass cards; pick at most two of the five packaging tricks per film.
2. **Screenshots must be big.** In a shot with a screenshot, screenshot width ≥ 80% of frame width (vertical ≥ 90%); when the narration reaches the part of the screenshot you cannot read clearly, push in to it (default gentle push about 0.9s; only when that part is a reveal or a comparison result, a 0.28s fast push). Push into one screenshot at most once or twice; after pushing in, pull back to the whole thing or pan to the next part. One small card drifting on a wide field of blobs is the fourth way of doing it wrong, "dead background". Parametric segment t2 defaults to this: the screenshot spreads full-frame (aspect preserved, no crop, with a darkened blurred copy of the same image padding all four sides), and the highlight moment pushes in (gentle push by default; only `"camera": "snap"` in the spec's top-level `data` makes it a fast push), with the same-magnification pan between consecutive screenshots. The old glass card requires an explicit `data.frame: "glass"`. If you write your own shots, use `CAM.track` (the shot action table) and `MD.cover` (full frame + focal point + push-in); for how to choose actions see `../camera-language.md`.
3. **Count the layouts.** Write out the layout of every screen in the board (title screen, three cards side by side, big number, screenshot card); if the same one runs ≥2 screens in a row, change it: screenshot push-in, number slam, before/after comparison. "Title → three feature cards → big number" looping for the whole film is a paged PPT.
4. **Hold after settling.** No card float, no constant-speed slow push to fill a pause; the next action goes on the moment the narration says the noun or the number. The number is about what was in that screenshot (the ratio of two timings, the conclusion of this page): write `data.over: true` on the number — the camera pulls back to the whole screenshot, the screenshot dims, the number slams on top, no cut to a separate blob-ground screen.
5. **Colour follows the product.** Take the base colour and accent from the product's own brand colours; do not default to purple-blue-cyan blobs; for bad news, serious events or non-launch subjects, do not use this dark keynote ground.

## ① When to use it

- **Use**: product/feature launch, version updates, "three new features", price and spec announcements, opening brand film, the "what is this product" passage inside a longer video. Best when the narration is **nouns + numbers** ("Plover 2", "320 ms latency", "1 million tokens"): one sentence per screen, the type floats in when the noun appears, the number settles when it is spoken.
- **Use**: when an interface screenshot has to be explained clearly — screenshot full-frame, push in to the part being discussed; putting it in a glass card or standing it up in 3D is optional packaging, use sparingly.
- **Do not use**: explaining mechanism (glass and blobs carry no logic — use t1); data trends (use t3); serious incidents / bad-news earnings (this language carries a built-in "good news" mood); when the content has no "hero" that can be magnified (nothing left but empty blob shots); popular science, story, news and other non-launch subjects — do not use this ground as a general-purpose template.

## ② Frame composition

| Item | Value | Basis |
|---|---|---|
| Base colour | near-black: this film `#050508`; Apple `#000/#161617/#1d1d1f`; Linear `#08090a` (one step up `#0f1011/#141516`, body `#f7f8f8`, stroke `#ffffff14`) | measured from both sites' CSS |
| Glow blobs (optional, use sparingly) | 4 radial-gradient blobs composited with screen → blur 90px at 1/4 size → scale up to fill → overlay 3.5% static grain to prevent banding. Hues from the Stripe family: purple `(150,90,238)`, blue `(56,104,255)`, cyan `(120,214,255)`, a touch of warm red `(255,96,84)`; then press a 38% black radial gradient over the centre to give white type its contrast | Stripe 2021 gradient `#a960ee #ff333d #90e0ff #ffcb57` |
| Blob motion (optional) | each blob drifts with amplitude 90–260px, period 9.5–13s, **avoiding a 5s period** (HIG: avoid sustained oscillation at ~0.2Hz) | Apple HIG Motion |
| Glass card (optional, use sparingly) | background sample blurred 40px (Apple nav `saturate(180%) blur(20px)`, NN/g says bigger is better) + 7.5% white fill + 14% white gradient top light band + 1.5px gradient stroke (bright top-left, dark bottom-right) + large shadow (blur 70–80, y+30–40, α0.5) | apple.com globalheader.css; NN/g Glassmorphism |
| Corner radius | card 36px; **concentric radii**: inner icon ground radius = 36 − 14 padding = 22 | WWDC25 "child radius = parent radius − padding" |
| Typeface | Inter (the closest open-source face to SF Pro; Linear uses Inter); Chinese: Source Han Sans. Titles 600 weight, **tracking tightened −0.02 ~ −0.03em at large sizes** (`T2.track`) | Apple 96px −0.015em, Linear 64px −0.022em, OpenAI 64px −0.03em |
| Type hierarchy | white `#f5f5f7` primary, `rgba(235,235,245,.6)` secondary, `#a7a7b4` eyebrow (tracking +6px); the product name may take a white→pale purple→pale cyan horizontal gradient (optional, use sparingly: gradient type plus blobs together is a template) | Apple site hierarchy convention |
| Composition | one focal point per screen; with a screenshot, full-frame (width ≥80%) pushed in to the part being discussed; centred symmetric three cards (equal width 480, gap 52) only for a feature list with no screenshot; the big number occupies ≥55% of frame width | — |
| Shape language | rounded rectangles, capsules, thin-line icons (round caps, uniform stroke, SF Symbols feel, `UI.icon`) | — |

## ③ Motion paths

- **Springs (main tool)**: SwiftUI duration + bounce parameterisation, `MO.spring(t,{duration,bounce})`: mass=1, stiffness=(2π/d)², damping=4π(1−bounce)/d → damping ratio ζ=1−bounce. **Default bounce 0** (most general); 0.15 is crisp with almost no bounce (this film's card entrance d=0.75, bubbles d=0.5); 0.3 is visibly bouncy; >0.4 is exaggerated for UI. `.smooth/.snappy/.bouncy` are all d=0.5.
- **Curves (non-spring)**: apple.com nav `.32s cubic-bezier(.4,0,.6,1)`; this film's type float uses CSS `ease` = `(.25,.1,.25,1)` (`MO.appleOut`); Linear's main ease-out-quad `(.25,.46,.45,.94)` .16s; Stripe recommends <500ms, `(.2,1,.2,1)`. `MO.bezier(x1,y1,x2,y2)` covers all of them.
- **Type entrance** (centred blur-in is optional, use sparingly; doing it on every screen of a film turns it into a template): blur 18–26px → 0, offset up 16–40px → 0, alpha → 1, 0.7–1.0s (`TY.blurIn`). Eyebrow → product name → subtitle stagger 0.2–0.4s.
- **Card entrance**: from 170px below, rotated ±0.55rad about Y (≈31°, the side cards facing outward), scale 0.9 → springs into place; three cards stagger 0.1s. 3D uses `UI.persp` (vertical strip slicing, persp 1800px; Stripe uses 600, Linear 1000).
- **Camera and holds**: hold after settling, no decorative float, no constant-speed slow push to fill a pause. The camera moves only when the narration reaches the part of the screenshot you cannot see clearly: default gentle push about 0.9s to that part, 0.7s to move to the next part; a fast push of 0.28s only for a reveal or a comparison of two numbers; number or big-type slam 0.17s (1.55→0.94→1.0); hold length follows the narration. After pushing in, pull back to the whole screenshot or move to the next part — do not push in shot after shot. The demo film's 7px card float (`MO.float`) and constant-speed camera push 1→1.045 are old practice; do not copy them in new films.
- **Counting**: starts 0.25s after the card settles and runs 0.9s (count a given number only once — after expanding to full screen keep "1 million", do not recount from 0); `easeOutExpo` (CountUp.js's default easing) — the last digit settles slowly; numbers **set tabular** (`TY.tabular`; Canvas cannot enable tnum and will jitter if unaligned).
- **Light sweep**: a bright band at −20°, 110–140px wide, sweeping across in 0.8–0.9s; `source-atop` on offscreen type (lights only the glyphs), `lighter` on cards; the three cards compute progress from their own screen positions, so it reads as one light.

## ④ Transitions (5 common)

1. **Blur push (blurPush)**: the old frame scales to 0.92 + blur 24px + fades out, the new frame comes from 1.06 blurred down to 1.0 sharp, 0.55s, `ease`. **Underneath, lay a heavily blurred copy of the old frame scaled 1.08**, so the shrinking frame does not show black edges. This film's shot 1→2.
2. **Shared-element expand (expandRect)**: (the new frame's first frame must be **opaque** inside the card — the card is translucent, so any dissolve shows the old and new type stacked) the selected card (scaled to 1.06 first, the two side cards retreating and dimming to 45%) expands from its own screen rectangle to full frame, radius 38→0, spring d=0.55 bounce 0; the new frame is scaled to the card size from the start and sits inside it. **The selected card stops floating before the expand**, so the transition starts from a stable rectangle. This film's shot 2→3.
3. **Match cut**: the same object in the same position across two shots (product name → card title position).
4. **Mask wipe / light-sweep cut**: change the picture behind the light band as it sweeps past.
5. **Refraction instead of cross-fade** (Liquid Glass): change the refraction/blur strength gradually as an element enters, rather than dropping opacity directly (this film's blur-in type follows this idea).

## ⑤ Pacing and type

- **Shot length**: a keynote screen usually runs 5–8s (Jobs 2007 iPhone: 70 seconds, 9 screens ≈ 7.8s per screen); product films quick-cut at 1.5–3s. This film 2.6/3.0/2.4s.
- **One thing per screen**: one noun, one number, one card. After a dense passage, leave one empty screen for the viewer to breathe (the counterweight in Presentation Zen).
- **Aligned to the narration**: type starts floating 0.2–0.3s before the noun is spoken (the float itself takes 0.7s, so it is sharp exactly when the word lands); the number **settles** when the narration speaks the value — count start = moment the number is spoken − count duration; the three cards entering in sequence maps to "first, second, third".
- **Type**: title ≤6 characters or one product name; subtitle one line ≤16 characters; card: 4-character title + one line of description + one big number + unit (one size smaller, one grey step down).

## ⑥ Implementation notes

> After being collected into the skill (2026-10-04 v0.4): the general functions in this card's "new" section have been unified into `scripts/art-motion/engine/lib/` (names changed to the unified MO / CAM / DG / TY / CH / UI / CL / TOON); the demo film's own code is in `scripts/art-motion/engine/demos/t2_keynote_ui/`. For the library cheat sheet and "how to pick a grammar for a passage of narration", see `references/art-motion/09-animation-grammar.md`.

- Reused from the skill: `scripts/art-motion/engine/engine.js`, `render.py`, `PAINT.cached/hex`, `U.rng`.
- New, now unified into the library `scripts/art-motion/engine/lib/ui.js` (`window.UI`): `mesh` (blob ground), `grainTex`, `backdrop` (blurred copy, the frosted-glass sample), `shadow` (draws only the shadow), `glass` (frosted-glass card), `sheen` (light sweep, `comp` optional), `persp` (pseudo-3D about the Y/X axis), `icon`, `rr/rrPath`, `scratch`.
- `scripts/art-motion/engine/lib/motion.js`: `spring/smoothSpring/snappy/bouncy`, `bezier/appleOut/emphasized`, `float`; numbers and type in `scripts/art-motion/engine/lib/typo.js`: `TY.count/tabular`, `TY.blurIn` (called MO.textIn during the experiment).
- Transitions (in `transitions_info.js` during the experiment, now in `transitions.js`): `blurPush`, `expandRect`.
- Performance: one blob draw per frame (at 1/4 size) + one blurred background copy, averaging 40–60ms per frame (qa with GPU flush); 8 seconds at 60fps renders in about 1 minute.
- Pitfalls (already fixed in the library): ① **blur pulls transparent pixels in from outside the canvas**; drawn into an offscreen that is not cleared it accumulates frame by frame, and qa reports determinism ✗ — lay down an unblurred copy of the original first; ② adjacent perspective slices overlapping by 0.75px leave a stripe on translucent texture — snap slice boundaries to whole pixels end to end, and draw into an offscreen first, then composite back with alpha as a whole; ③ `UI.sheen` sets a composite mode internally, which overrides a `source-atop` set outside it, so it is exposed as a parameter.

## ⑦ Representative works and first-hand references

- Representative works: Apple iPhone / Apple Intelligence launch films and apple.com product pages; OpenAI GPT-4o / o-series launch videos; the Linear site and Linear Release videos; Stripe 2020–21 site gradients.
- https://developer.apple.com/videos/play/wwdc2023/10158/ (Animate with springs: duration/bounce)
- https://developer.apple.com/videos/play/wwdc2018/803/ (Designing Fluid Interfaces: start from 100% damping)
- https://developer.apple.com/videos/play/wwdc2025/219/ (Meet Liquid Glass)
- https://developer.apple.com/design/human-interface-guidelines/materials , /motion , /typography
- https://www.nngroup.com/articles/glassmorphism/
- https://web.archive.org/web/20211015000000/https://stripe.com/ (gradient values)
- https://stripe.com/blog/connect-front-end-experience (<500ms, curve)
- https://linear.app/now/how-we-redesigned-the-linear-ui (LCH colour, Inter)

## ⑧ The 3 easiest things to get wrong

1. **Nothing behind the glass.** Frosted glass only blurs what is behind it; "glass" on a flat dark ground is a grey rectangle. Draw coloured, undulating blobs first, then sample-blur by the card's screen position.
2. **Springs too bouncy, too much motion.** bounce defaults to 0, entrances at most 0.15–0.3; >0.4 immediately looks cheap. Move one group of things at a time.
3. **Big type with untightened tracking, blob colours gone muddy.** Above 64px use −0.015 to −0.03em; each blob keeps its own colour region (screen composite + large blur) — do not linearly average several colours into grey-purple mud.

## qa numbers (skill `scripts/art-motion/qa.py`, 2026-10-04, before review)

| Shot | Motion % | Static frame-pair % | Jumps | mean/peak ms | Determinism |
|---|---|---|---|---|---|
| t2_s1 | 0.58 | 35.4 | 0 | 39.8/51.4 | ✓ |
| t2_s2 | 2.62 | 8.5 | 0 | 60.2/65.0 | ✓ |
| t2_s3 | 1.84 | 9.6 | 0 | 44.3/51.0 | ✓ |

Note: t2_s1's "35% static frame-pairs" comes from the demo film's blob drift and its 4.5% constant push (old practice); the per-frame change stays below qa's pixel threshold (>12 levels); sampling two frames 1s apart (1.6s vs 2.6s in the film) gives 26.8% of pixels changing by more than 12 levels and 78% by more than 4. A static frame-pair figure says nothing about quality either way: an explainer holding for long stretches is correct, and a constantly drifting film with a low static frame-pair figure still looks like paged PPT.

## Revision (independent review → one round of changes, 2026-10-04)

| Review note | Fix |
|---|---|
| 🔴 2.55–2.75s and 5.6–5.85s, the transitions show black edges around the sides | under blurPush / expandRect lay the old frame scaled 1.08 and blurred 30px |
| 🔴 while the card expands, "long-term memory" and "1 million" double-image; after expanding it recounts from 0 | the new frame's first frame is opaque inside the card; the full-screen page keeps the same "1 million tokens" wording, no recount |
| 🔴 at 6.95s the count jumps from 999,023 to 1,000,000 in one frame and "tokens" gets crowded out | removed the duplicate count along with the item above; units are laid out from measured widths of all three segments, no longer nudged in by eye |
| 🟡 the end card appears for only 0.4s, at y≈1020 outside the safe area | end card floats in 1.2–1.8s, holds 0.6s, at y=972; the chat panel moves up 65px as a whole |
| ⚪ the card says "1 million" while the full screen says "1,000,000" | unified to "1 million" |

qa after revision:

| Shot | Motion % | Static frame-pair % | Jumps | mean/peak ms | Determinism |
|---|---|---|---|---|---|
| t2_s1 | 0.58 | 35.4 | 0 | 39.5/51.6 | ✓ |
| t2_s2 | 2.62 | 8.5 | 0 | 57.2/59.9 | ✓ |
| t2_s3 | 0.97 | 15.4 | 0 | 43.0/48.7 | ✓ |

(Transition smoke test: blurPush slowest at about 137ms per frame, including two full-screen blurs.)

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
