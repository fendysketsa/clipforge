# t3_finance_chart · Financial data chart animation

> One-sentence grammar: **build the coordinate system first, then let the data "grow" out, and finally label only one thing; one colour tells the story and the rest go grey; the numbers are always honest (bars start at 0, units and source written on the chart), and the animation only decides "how it appears", never "what the value is".**
>
> Demo film: `scripts/art-motion/engine/demos/t3_finance_chart/` (render with `render.py --film demos/t3_finance_chart`) (8s, 3 shots, all data fictional, an "illustrative data" badge bottom right on every shot) · overview `assets/animation-grammar/t3_finance_chart_overview.jpg` · code `scripts/art-motion/engine/demos/t3_finance_chart/`

## Check before you start

1. **For each chart, first write down its one "thing".** The title is that conclusion, and the callouts label only that; a chart you can't write that sentence for doesn't get made — use one big number or change grammar.
2. **The numbers have to reconcile.** The multiple in the title has to be computable from the numbers on the chart (write a ÷ b in the callout); the same number in two shots has to match; keep "rose to" and "rose by" distinct.
3. **The moment the data grows has to land on that word in the narration.** A bar chart writes several bar cues, each carrying `data.index`, so each bar grows only when it is spoken; don't put the title up at second 0 and then grow the whole thing in one go.
4. **Stop once it lands.** After the numbers land, hold at least 0.5s, with no constant drift; if a local detail has to be seen, slow-push into it when the narration points there (about 1s, Heer & Robertson: about 1s per step, ease in and out), and only the single most critical number gets a 0.28s fast push; or use `zoomThrough` to push into that point.
5. **Don't use the same layout more than 3 charts in a row.** Thin red rule + title + chart three times running is flipping through a report; break it with a push into a detail, a slammed-in big number, or a cut back to real material.
6. **The chart stays inside the film's world.** The chart shot's ground should belong to the same colour family as the shots around it: for a dark film write `theme: "dark"`, or put the film's ground colour into `safe.fill` (the chart ground follows it automatically, going to light type on dark); a white-background report look is only for films that are already white paper or web pages. Better still, draw the chart on an object inside the film's world: `--alpha` gives a transparent clip to stick onto a screen, a blackboard, or a sheet of paper in the picture. A white-background line chart suddenly cutting in with a fixed title bar on top of a night-scene film gets the review comment "disconnected from the whole film".

## ① When to use it

- **Use**: growth in revenue/profit/user count, share-price trajectories, market-share ranking changes (bar chart race), regional comparison (map shading), the turning point before and after an event. When the narration contains **specific numbers, times, comparisons** ("it rose 8.7× in five years", "after March 2023").
- **Use**: passages that need to be "credible" — the audience will screenshot and share, and will check.
- **Don't use**: a single number on its own (a big-type card instead, use t2's counting); when the data itself is unreliable or you are unwilling to credit a source (better not to make the chart); explaining a mechanism (use t1).

## ② Frame composition

| Item | Value | Basis |
|---|---|---|
| Ground | white `#FFFFFF` (Economist web charts); or FT salmon pink `#FFF1E5`; for dark films `theme: "dark"` (`#0E1116` ground, light type, cyan main bars) | Economist 2017 chart style guide; FT o-colors source |
| Layout | **thin red rule at the top (8px) + small red flag top left (96×22) + bold title (one conclusion) + subtitle (metric, unit) + source bottom left** | Economist style guide layout examples |
| Main palette | ECON RED `#E3120B`, blue `#006BA2`, cyan `#3EBCD2`, green `#379A8B`, yellow `#EBB434`, grey `#758D99`, black `#0C0C0C` | Economist chart palette |
| Emphasis method | **one colour tells the story, the rest go pale grey** (this film: the last bar stays blue, the rest transition to `#C6D2D8`) | Datawrapper, "use grey to suppress secondary data" |
| Grid | horizontal grid only, thin grey (this film α0.13, 1.5px); **only the zero baseline is a solid black line** (3px); y-axis tick values sit above the grid lines on the right | Economist style guide |
| Type | The Economist uses Econ Sans (Cnd); this film uses Roboto Condensed (numbers) + Source Han Sans (Chinese). Title 700, subtitle/axis 400; axis type smallest, source smallest and palest (75% black) | same as above |
| Up/down colours | **Mainland China A-shares: red up, green down** (this film); Hong Kong and Europe/US: green up, red down. For a Chinese-speaking audience the chart must state "red up, green down"; colour-blind-friendly alternative: blue/orange + ▲▼ symbols | Jiang et al. 2014 (JBDM); Bloomberg terminal colour-blind mode |
| Line width | main data line 5px (this film), moving average 4px; callout leader 2px | — |
| Shape language | rectangular bars, line + end dot, candlestick body + wick, small dot + leader callout | — |

## ③ Motion paths

- **Staging**: layout 0–0.5s → grid drawn in line by line from left to right (lag 0.12, easeOutQuint) → x-axis labels fade in and rise in sequence → data → emphasis colour change → callout. Each stage about 0.5–1.3s. Heer & Robertson 2007: complex changes are staged, always ease in and out, a single step "as long as it needs" about 1s; axes before data is industry convention (no empirical study, but it lets the audience know the "ruler" before the "quantity").
- **Bars**: grow from the 0 baseline, easeOutQuint, staggered in sequence (lag 0.22, 1.3s total); value labels ride the bar tops and count up in sync (`CH.bars`).
- **Line**: drawn by advancing along **x (time)**, not arc length — time flows at constant speed, so steep sections naturally draw fast and you read "spike"; a 9px dot at the head plus a price label following it (tabular figures); area gradient α0.14→0. This film 1.5s, smooth (the last price "lands" on the dot). D3's official example is 5000ms linear, which suits a standalone chart; compress to 1.5–2s in a video.
- **Callout**: triggered at the moment the line head **passes** the event point (`tHit` computed from the inverse of the easing function) — dot pops in (spring d0.45 bounce0.25) + a pulse ring → 0.12s later the leader draws → 0.3s later the text fades in. **One shot labels one thing only.**
- **Candlesticks**: appear one by one (lag 0.06, 0.2–1.3s), the body grows from open to close, the wick unfolds afterwards; volume bars in sync; the price at top right rolls with "the most recently appeared candle", coloured by the change relative to the start of the range.
- **Numbers**: count-up uses easeOutExpo (CountUp.js default 2s; 0.9–1.3s in a video); all rolling numbers are set in tabular figures to stop them jittering.
- **Camera**: once the chart has landed the camera stops, with no constant drift; camera moves go at the moment the narration points at a data point: a slow push of about 1s, or 0.7s to move to the next group of data; only the one or two most critical numbers in the whole film get a 0.28s fast push; during a push-through transition the camera keeps pushing vectorially (no bitmap scaling). The demo's 1→1.03 constant push on every shot is the old way; new films don't copy it.
- **Rank race (not used in this film)**: D3's official bar chart race is 250ms per keyframe, 10 linearly interpolated frames between them, 12 bars shown; a swap takes about 0.5s; rank changes have to be staggered so all the bars don't jump up and down at once.

## ④ Transitions (5 in common use)

1. **Panel slide push (`slidePush`)**: the new panel pushes in from the right and the old one pushes out to the left, with a vertical bar of brand red leading the way, 0.5s, `cubic-bezier(.7,0,.2,1)`. This film, shots 1→2. The new panel starts building its layout during the push (red rule growing, title surfacing).
2. **Push into a detail (`zoomThrough`, live + bScale0)**: the camera pushes 6× around the latest data point (the old shot re-draws itself vectorially), the new frame (the last 20 days of candlesticks) dissolves in from 0.6×, with the subject (the newest candle) aligned to the push point. This film, shots 2→3. When there is no circular opening you must set `bScale0`, otherwise the new frame looks like a small card floating in the middle.
3. **Morph between charts**: the same data in a different form (bars → dots → line); move into position first, then morph (Heer & Robertson: scatter → bars translates first then morphs; stacked → grouped changes width first then drops). **Never morph between different metrics** (a revenue bar turning into a share-price line implies the two share a scale).
4. **Axis relabelling**: when the data range changes, change the ticks first (old ticks fade out, new ones fade in), then move the data.
5. **Hard cut + unchanged layout**: swap one chart for another on the same layout, red rule and title position unchanged, only the content changes — the most common move in Economist videos.

## ⑤ Pacing and text

- **Shot length**: 2.5–6s per chart; this film's 2.8/2.7/2.5s is a compressed version (in real use one chart pairs with one or two sentences of narration). Narrative structure: establisher → trigger → peak → resolution (Amini et al. 2015, 50 professional data videos).
- **Syncing with the narration**: the number **lands exactly as it is spoken** — the bar finishing and the label stopping at 107.9 hits on "one hundred and seven point nine billion"; the callout pops as the line head passes the event, on "after the large model was released in March 2023". So fix the narration timings first, then work the animation start times backwards.
- **Text**: the title states the conclusion ("revenue rose to nearly 9× its original level in five years" — **"rose to", not "rose by"**: 8.7× means it rose to 8.7× the original, i.e. it rose by 7.7×; the review caught this once); the subtitle states the metric and unit ("annual revenue, ¥100m"); the multiple has to be computable from the numbers on the chart (107.9÷12.4=8.70); when the axis doesn't start at 0, say so in the subtitle ("vertical axis does not start at 0"); source in one line at bottom left; for fictional data the "illustrative data" badge sits bottom right on every shot.

## ⑥ Implementation notes

> After being taken into the skill (2026-10-04 v0.4): the general-purpose functions in this card's "newly written" list have been consolidated into `scripts/art-motion/engine/lib/` (renamed to the unified MO / CAM / DG / TY / CH / UI / CL / TOON), and the demo's own code lives in `scripts/art-motion/engine/demos/t3_finance_chart/`. For the library quick reference and "how to choose a grammar for a stretch of voice-over", see `references/art-motion/09-animation-grammar.md`.

- Reused from the skill: `scripts/art-motion/engine/engine.js`, `render.py`, `U.rng` (all fictional data is seed-generated and reproducible), `PAINT.hex`.
- Newly written `scripts/art-motion/engine/lib/chart.js` (`window.CH`): `lin` (linear scale, with `inv`), `ticks` (1/2/2.5/5×10ᵏ ticks), `grid` (grid drawn line by line, zero line thickened, tick values placed right), `xLabels`, `bars` (grow from 0 + counting in sync + highlight/grey-out), `line` (advance by x, head dot, area), `yAt`, `candles` (candle by candle, up/down colours configurable), `callout` (dot → leader → text), `tag` (red flag), `demoBadge` (illustrative-data badge), `mixHex`.
- `scripts/art-motion/engine/lib/motion.js`: `lagged`, `quintOut/expoOut` (called easeOutQuint/easeOutExpo at experiment time), `spring` (the callout dot); `TY.count/tabular/fmt`.
- Transitions (now in `transitions.js`): `slidePush`, `zoomThrough` (live, bScale0, focus).
- Event trigger time: `tHit = start + duration × smooth⁻¹(event x fraction)` (inverse function by bisection), so the callout is always in sync with the line head and changing the line's duration needs no manual tweaking.

## ⑦ Reference works and first-hand sources

- Reference works: The Economist's web charts and videos; FT charts; the data segments of Bloomberg Originals / Quicktake; Flourish's bar chart race.
- Economist chart style guide 2017 (mirror): https://sa.ipaa.org.au/wp-content/uploads/2026/02/Economist-CHARTstyleguide_20170505.pdf
- FT palette source: https://unpkg.com/@financial-times/o-colors/src/scss/_palette.scss
- Heer & Robertson 2007, Animated Transitions in Statistical Data Graphics: https://idl.cs.washington.edu/files/2007-AnimatedTransitions-InfoVis.pdf
- D3 bar chart race: https://observablehq.com/@d3/bar-chart-race-explained
- Correll et al. 2020 (the exaggerating effect of truncated axes — a broken-axis marker doesn't rescue it): https://arxiv.org/abs/1907.02035
- Datawrapper: bars from zero https://www.datawrapper.de/academy/why-our-column-and-bar-charts-start-at-zero ; dual axis https://www.datawrapper.de/blog/dualaxis ; colour blindness https://www.datawrapper.de/blog/colorblindness-part2
- The cultural difference in red-up/green-down: https://onlinelibrary.wiley.com/doi/10.1002/bdm.1800
- CountUp.js (easeOutExpo, 2s): https://github.com/inorganik/countUp.js

## ⑧ The three easiest things to get wrong

1. **Truncating the axis.** Bar charts always start at 0; lines and candlesticks may not, but the chart has to say so. Tufte's Lie Factor (effect on the chart ÷ effect in the data) outside 0.95–1.05 counts as distortion.
2. **Too many colours, everything is the protagonist.** One colour tells the story, the rest go grey; state clearly who the red and green are for (A-shares red-up, Europe/US red-down).
3. **Animation so busy the number can't be read.** No bouncing bars, 3D bars or rotating pie charts; stage it, ease in and out, about 1s per step; hold at least 0.5s after the numbers land so people can read them.

## qa numbers (`scripts/art-motion/qa.py` in the skill, 2026-10-04, before review)

| Shot | Motion % | Static frame pairs % | Jump frames | Mean/peak ms | Determinism |
|---|---|---|---|---|---|
| t3_s1 | 1.39 | 0.0 | 3 | 1.3/1.9 | ✓ |
| t3_s2 | 2.37 | 4.7 | 0 | 1.9/2.8 | ✓ |
| t3_s3 | 0.96 | 0.0 | 0 | 1.6/2.3 | ✓ |

Note: t3_s1's three "jumps" sit at lt 2.10/2.20/2.27s — exactly the frames where four bars go from blue to grey together (highlighting the protagonist) and the callout pops. Deliberate large-area changes, not artefacts.

## Revision (independent review → one round of changes, 2026-10-04)

| Review comment | Fix |
|---|---|
| 🔴 The title "rose nearly 9×" doesn't reconcile with the 8.7× callout (should be "rose to") | Changed to "revenue rose to nearly 9× its original level in five years"; the share-price page uses the same convention, "rose to 7.5× its original level" |
| 🔴 The monthly chart's endpoint ¥268 doesn't match the daily candle at 286.40 (and the push goes exactly into that point) | Monthly last point = latest price 286.4, the second-to-last month's close = the daily chart's start 242; **numbers between two shots must be derivable from each other** |
| 🟡 At 5.6s "¥268" double-exposes with the counting price, two large red numbers | The price head label retracts within 0.2s of the push-through transition starting |
| 🟡 "Volume" sits on top of the candlesticks, volume bars hit the 240 grid line | Label moved to the empty space bottom right; volume bars normalised to the maximum, 6px gap left |
| 🟡 The daily candle page can't be read in 2 seconds | Removed the 5-day moving average; candles complete in 1.3s, the parenthetical lands at 1.75s, hold 0.75s |
| ⚪ Red-up-green-down collides with the brand red | Kept (for an A-share audience), subtitle reads "red up, green down (A-share convention)"; for an overseas version switch to green-up or blue/orange |

qa after revision:

| Shot | Motion % | Static frame pairs % | Jump frames | Mean/peak ms | Determinism |
|---|---|---|---|---|---|
| t3_s1 | 1.44 | 0.0 | 3 | 1.3/1.7 | ✓ |
| t3_s2 | 2.45 | 4.7 | 0 | 1.9/2.6 | ✓ |
| t3_s3 | 0.91 | 0.0 | 0 | 1.7/2.9 | ✓ |

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
