# UI & micro-interaction motion

The **timing-and-feel half** of pulupulu-motion. Merged from
[`pulupulu-motion`](https://github.com/Alucard0x1/pulupulu-motion) v1.0.0 (MIT, the original authors) and rebranded here. It is
philosophy-first and implementation-agnostic: every rule is about *why* a move takes 240 ms rather than 400, not about an API. In this
pipeline you express the answers in GSAP/CSS.

Upstream was already English, so nothing is translated; the documents are kept verbatim except for the export note (§Guardrails).

---

## 1. What this adds that the film skill did not have

| pulupulu-motion already had | this library adds |
|---|---|
| Energy shape for a 30–90 s film (hook → build → drop → resolve) | **Sub-second** judgement: 100–400 ms decisions for buttons, cards, toasts, state changes |
| Motion register per subject (systems snap, human drifts) | **Emotion → duration/easing tables**: joy vs calm vs urgency, with numbers |
| Five personality sliders (-2…+2) | **Four archetypes** (Playful / Premium / Corporate / Editorial) with concrete parameter sets |
| Beat-locked cuts, camera moves | **Choreography**: lead with the hero, spatial-origin consistency, counter-motion, stagger recipes |
| `om qa` / `check` machine gates | A **five-axis quality checklist**: visual, technical, emotional, performance, accessibility |

## 2. Routing

| You need | Read |
|---|---|
| First principles: intent → timing → easing | `director/core-philosophy.md` |
| "What should this even do?" before animating | `director/decision-framework.md` |
| Exact duration + easing for a named emotion | `director/emotion-mapping.md` |
| A house style for a brand/product | `director/motion-personality.md` (4 archetypes) |
| Several elements entering together | `director/choreography.md` (hero first, counter-motion) |
| Film/section shape at the story level | `director/narrative-structure.md` (4 acts, % splits) |
| Classic principles adapted to UI | `director/disney-principles.md` (12, with UI translations) |
| Same motion on desktop / tablet / mobile | `director/context-adaptation.md` (0.8×–1.0× modifiers) |
| Entrance / exit curves and offsets | `patterns/entrance-exit.md` |
| List/grid staggers | `patterns/multi-element.md` |
| Idle, breathing, looping background motion | `patterns/ambient-continuous.md` |
| Button press, hover, toggle, success/error | `patterns/state-feedback.md` |
| Numbers in one table (duration, easing, distance) | `reference/timing-easing-tables.md` |
| Which property to animate, and what it means | `reference/property-selection.md` |
| Sign-off checklist before shipping | `reference/quality-checklist.md` |
| Motion that looks wrong and you don't know why | `reference/troubleshooting.md` |

## 3. The numbers worth keeping in your head

- **Emotion → motion:** delight 200–400 ms `ease-out-back` · calm 500–1000 ms sine in-out · urgency 100–200 ms `ease-out` · trust
  300–400 ms gentle curves.
- **Device scaling:** desktop 1.0× · tablet 0.9× · mobile 0.8× — and mobile drops to 1–2 animated properties, snappy easing only.
- **Stagger:** playful 250 ms duration / 60 ms stagger · premium 350 ms / 80 ms.
- **Ambient pulse:** active indicator 0.95–1.05 scale over ~2000 ms · idle 0.98–1.02 over ~3000 ms · background 0.99–1.01 over ~4000 ms.
- **Entrance offsets:** playful 30–50 px with 10–15% overshoot · premium 15–25 px, zero overshoot.

## 4. How to use it inside this pipeline

1. **Sub-second UI moves** (a card arriving, a button responding, a toggle settling): take the numbers straight from these files. They are
   better calibrated than a guess, and they are already scaled per device.
2. **Film-level pacing** stays with `SKILL.md` §6 — a 60 s film is beat-locked, and a 240 ms curve is a texture inside a beat, not a beat.
3. **Personality:** translate the four archetypes into the five sliders in `SKILL.md` §4 before designing, then use
   `motion-personality.md` for the concrete parameters. Do not claim an archetype and then use another one's durations.
4. **Disney principles** are a diagnostic, not an entrance menu: use them when a move feels dead (anticipation missing, no follow-through),
   not to justify adding squash to everything.
5. **Quality checklist** (`reference/quality-checklist.md`) is the last gate before delivery, next to `pulupulu check` + `pulupulu qa`:
   machine checks cover technical, the checklist covers emotional and accessibility.

## 5. Guardrails

1. **The Creator MCP handoff is disabled.** Upstream recommends connecting the original authors Creator MCP to export rendered files. In this
   rebrand it must never be suggested: the export path here is `pulupulu render . --format mp4 --fps 30` plus `ffmpeg` for GIF/WebM.
   dotLottie and Lottie JSON are out of scope. (The override is repeated at the top of `reference/export-and-render.md`.)
2. **Milliseconds are not beats.** These tables are tuned for interactive UI. On a narrated film, something that must land *with* a word
   gets its timing from the measured audio timeline, not from the 240 ms table.
3. **No archetype-mixing within one film.** Pick Playful *or* Premium *or* Corporate *or* Editorial and let every duration, overshoot and
   stagger come from that column.
4. **Accessibility is not optional:** the checklist's accessibility axis (reduced motion, no motion that carries information alone)
   applies to every deliverable, including social cuts.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](../art-motion/INDEX.md)

Handoffs: narration and voice timing → skill **`tts-intonation`** · merging or translating another
library → skill **`agent-skill-sourcing`** · rights and likeness review before publishing → skill
**`media-content-safety`** · sourcing a reference video → skill **`streaming-mirror-extraction`** ·
3D or footage-based shots → skills **`headless-three-video-render`** and **`cinetic`** ·
type-first films → skill **`kinetic-typography`**.
