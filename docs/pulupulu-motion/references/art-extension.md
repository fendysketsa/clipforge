# Art, style and cinematic extension


How the merged art-direction library is laid out and which index to open first.

Part of the `pulupulu-motion` skill. The entry point and the gate table live in `SKILL.md`.

## This route needs a one-time install

`scripts/art-motion/engine/` (lib, demos, scenes ≈ 37 MB) is **not in the repository**. Fetch the pinned,
checksum-verified bundle before using any recipe on this page:

```sh
python scripts/install_art_motion.py --check
python scripts/install_art_motion.py                        # core, 20 MB
python scripts/install_art_motion.py --with-reference-films  # study material, 14 MB more
```

It lands on the exact paths cited below and in `INDEX.md`, so no other page changes. `scripts/doctor.py`
reports it as installed or missing; it is never a blocking requirement.

## 13. Art, style & cinematic extension (merged library)

Everything artistic lives in `references/art-motion/` — a curated library of style recipes, grammar cards and craft documents — with executable gates in `scripts/art-motion/`. Read `references/art-motion/INDEX.md` first — it routes every need to one file. The four entry points you will actually use:

| Need | Go to |
|---|---|
| Shot list before code, with the linter that enforces it | `references/art-motion/storyboard-template.md` → `scripts/art-motion/storyboard_lint.py` |
| Camera behaviour (push / pull / whip / slam / cut as punctuation) | `references/art-motion/camera-language.md` |
| A named visual style (57 recipes: cave → bauhaus → Ghibli → pixel → ukiyo-e) | `references/art-motion/style-recipes/INDEX.md` |
| An explainer grammar beyond GSAP cards (3b1b, keynote, finance chart, kurzgesagt, Vox, whiteboard, storytime, kinetic type, presenter) | `references/art-motion/09-animation-grammar.md` §selection → `animation-grammar/<card>.md` |

**When to reach for it:** the brief asks for an art style, an illustrative look, characters, a painted/scene-based film, a long-scroll traversal, or cinematic camera moves. **When not to:** a UI/demo/data explainer stays on the GSAP path in §3–§7 — the recipes cost far more and add nothing there.

Three guardrails, learned the hard way:

1. **The linter matches English and Chinese — write the shot list in either.** Required columns `Time | Subject | Action | Camera | Tags | On-screen text | Method`; camera cell one of `Stop ／ Slow push-in ／ Pull back ／ Lateral truck ／ Fast push-in ／ Slam in ／ Whip ／ Cut`; the three lines above the table are `Style ／ Palette ／ Character`, plus `Allow blue-purple` when you need it. English shot lists are fully validated — every rule bites on English subject and action cells, not just the camera column — so keep them in English unless you are updating a legacy list, where the Chinese camera tokens used by earlier versions still parse. Verdict legend for every code: `references/art-motion/INDEX.md` §8.
2. **Two render paths, never in one film.** `pulupulu render` (this skill's CLI) is for GSAP/CSS compositions. `scripts/art-motion/engine/render.py` (`uv run --with playwright`) renders style-recipe `scenes` and parameterised clip specs. Pick one per project; `film_gate.py`/`subzone_gate.py` only understand the shot-based project layout, while a `pulupulu` project is gated by `pulupulu check` + `pulupulu qa`.
3. **A style card is a starting point, not a registered scene.** Anything not yet implemented must be authored and verified against the reference (`15-style-transfer.md`, `16-style-demo-95.md`); never ship a card name as if it were a working scene.

**The library is English throughout.** Every document was translated and the Chinese filenames were renamed, so there is no `en/` subdirectory any more — `INDEX.md` is the one router, and every path inside the library resolves to a file in this repo. Chinese now survives only where it is *matched data* rather than prose: the shot-list linter's legacy control tokens, the CJK line-break classes and two sample glyphs. Translating those would blind the tools, which is why they stay. Upstream `assets/` (49 MB of showcase stills) was deliberately not copied — the recipes are code — and the clip spec JSON ships in `scripts/art-motion/engine/clips/` while the clip scripts sit in `.../engine/clips/`; the two directories are one letter apart and the wrong one to rewrite from memory. **After any merge or rename in this tree, re-prove the paths** with `path_audit.py . --fallback scripts/art-motion` from the **`agent-skill-sourcing`** skill (that skill's `scripts/`, not this one) — a namespaced merge silently kills references that the source project resolved from its own layout, and nothing in the render path tells you a doc now points at nothing.

### 13b. Timing, easing and feel at the sub-second level — `references/ui-motion/`

A library of timing-and-feel documents (English, kept verbatim). It answers the questions the film rules do **not**: how long a single move takes, which curve carries which emotion, how elements enter together, and how to scale motion per device. Read `references/ui-motion/INDEX.md` for the full routing; the four files that pay for themselves immediately:

| Question | File |
|---|---|
| How long, and with which easing, for a given feeling | `reference/timing-easing-tables.md`, `director/emotion-mapping.md` |
| Several elements entering or leaving together | `director/choreography.md`, `patterns/multi-element.md` |
| One house style for this brand (Playful / Premium / Corporate / Editorial) | `director/motion-personality.md` |
| Pre-delivery sign-off beyond machine checks | `reference/quality-checklist.md` |

Numbers to keep in mind: delight 200–400 ms `ease-out-back` · calm 500–1000 ms sine in-out · urgency 100–200 ms `ease-out` · trust 300–400 ms gentle curves · mobile runs at 0.8× desktop with fewer properties · staggers 60 ms (playful) / 80 ms (premium).

Three rules for using it here: **milliseconds are not beats** (anything that must land on a spoken word takes its timing from the measured audio timeline, not from a 240 ms table); **one archetype per film**, with every duration and overshoot taken from that column; and **the third-party Creator MCP handoff is not part of this skill** — export is `pulupulu render` plus `ffmpeg`, never a vendor MCP.
