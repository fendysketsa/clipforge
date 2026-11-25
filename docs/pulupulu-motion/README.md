# pulupulu-motion

**A skill that teaches your AI coding agent to make motion-graphics films.**

You describe the film. Your agent writes it as a web page (HTML + GSAP), renders it frame by frame in the Chrome
already installed on your machine, and hands you an MP4 with music, sound effects and a spoken narration.

No video editor. No timeline app. No cloud render farm. The film *is* the page, and the page is a text file the
agent can edit — which is why an agent is good at this and a person in a GUI is not.

---

## Contents

1. [What it can make](#1-what-it-can-make) · [and what it cannot](#what-it-cannot-do)
2. [What you need before starting](#2-what-you-need-before-starting)
3. [Step 1 — install the renderer](#step-1--install-the-renderer-do-this-once)
4. [Step 2 — install the skill into your agent](#step-2--install-the-skill-into-your-agent)
5. [Step 3 — check the machine](#step-3--check-the-machine)
6. [Step 4 — your first film](#step-4--your-first-film)
7. [Model compatibility](#5-model-compatibility) · [Narration with DeepSeek TTS](#6-narration-with-deepseek-tts)
8. [41 example prompts you can copy](#7-example-prompts-you-can-copy) ← the big list
9. [What a good prompt contains](#8-what-a-good-prompt-contains)
10. [Prompts that fail](#9-prompts-that-fail-and-why)
11. [When something goes wrong](#10-when-something-goes-wrong)
12. [What is inside this repository](#11-what-is-inside-this-repository)
12. [Licence](#12-licence)

---

## 1. What it can make

Vertical shorts (1080×1920), landscape (1920×1080), or any size a brief needs — H.264 + AAC, with:

- **Type-driven films** — kinetic typography, big numbers, quotes, chapter cards.
- **Explainers** — one beat, one sentence, one picture, timed to measured speech.
- **Data stories** — bar/line/area charts, counters, comparisons, drawn SVG maps.
- **Launch and product films** — feature beats, UI-as-illustration, b-roll made of shapes and icons.
- **Style films** — 57 art-direction recipes (Bauhaus, ukiyo-e, Ghibli, vaporwave, Rembrandt, 8-bit, constructivist, and 50 more) turned into moving scenes.
- **Narrated films** — Indonesian or English voice, numbers spoken as words while the screen keeps digits (`502` → *five oh two*).
- **Music and sound** — scores generated locally, plus sfx, mixed under a ducked narration track.
- **Point-to-edit revisions** — `om studio` opens a live preview; you click the thing you dislike and the agent changes exactly that.

### What it cannot do

Better said up front than discovered after an hour of work. This tool renders **flat vector geometry, type,
charts, maps, icons and colour-coded objects** well. It does badly, and should refuse:

- real footage it does not have,
- a real person's face or likeness,
- articulated human or animal anatomy, or lip-sync,
- a continuous physical action performed by a body.

A drawn stand-in for archival material is a provenance problem, not a style choice.

---

## 2. What you need before starting

| Requirement | Why | Check |
|---|---|---|
| **Node ≥ 22** | runs the renderer CLI | `node -v` |
| **Google Chrome** (or Chromium/Edge) | the only renderer; nothing is uploaded | open Chrome once |
| **FFmpeg on `PATH`** | muxes picture + sound into MP4 | `ffmpeg -version` |
| **Python 3.9+** | narration, language audit, delivery checks | `python --version` |
| **DeepSeek API key** (optional) | only for DeepSeek TTS narration — see §6 | `echo $DEEPSEEK_API_KEY` |

Installing the three that are easy to forget:

```powershell
# Windows (PowerShell)
winget install OpenJS.NodeJS.LTS
winget install Gyan.FFmpeg
winget install Python.Python.3.12
```

```sh
# macOS
brew install node ffmpeg python
```

```sh
# Ubuntu / Debian
sudo apt install nodejs ffmpeg python3
```

---

## Step 1 — install the renderer (do this once)

The renderer is the **`huashu-motion` CLI** (MIT, [alchaincyf/huashu-motion](https://github.com/alchaincyf/huashu-motion)).
The documents in this skill call it `pulupulu` because the author runs a rebranded local build; the command it
installs is **`om`**. Both names run the same program with the same flags.

```sh
npm install -g huashu-motion@0.5.1     # the version these commands were tested against
om --version
```

Want the newest instead? `npm install -g huashu-motion` installs 0.6.x; if a command refuses a flag, `om --help`
is the authority. Pin `@0.5.1` when you need the film to build exactly as documented here.

**Never call `npx` per command.** `om check`, `om still` and `om render` run dozens of times per film; a network
round trip on each one is the most common self-inflicted slowdown in this workflow.

If your agent runs in a sandbox that forbids launching Chrome or binding `127.0.0.1`, give it permission to run
outside that sandbox — otherwise it cannot look at a single frame.

---

## Step 2 — install the skill into your agent

A skill is just a folder. Get this repository somewhere permanent, then put it where your tool looks.

```sh
git clone https://github.com/Alucard0x1/pulupulu-motion.git
```

Then follow your tool's row.

### Claude Code

Personal (all projects):

```sh
mkdir -p ~/.claude/skills && mv pulupulu-motion ~/.claude/skills/
# Windows: move the folder to %USERPROFILE%\.claude\skills\pulupulu-motion
```

Per project: `.claude/skills/pulupulu-motion/`. Type **`/pulupulu-motion`** to invoke it, or simply ask for a film
and Claude loads it by description.

### Codex CLI

```sh
mkdir -p ~/.agents/skills && mv pulupulu-motion ~/.agents/skills/
```

Codex also reads `.agents/skills/` from the current directory up to the repository root, so a team can commit the
skill with a project. To switch one off without deleting it, add `[[skills.config]]` in `~/.codex/config.toml`.

### Gemini CLI

Gemini takes commands as TOML. Create `~/.gemini/commands/film.toml`:

```toml
description = "Make a motion-graphics film with pulupulu-motion"
prompt = """
Read ~/.gemini/pulupulu-motion/SKILL.md and follow it exactly.
Task: {{args}}
"""
```

Put the repository anywhere (that path is a suggestion), and keep a short pointer in `GEMINI.md` so the agent finds
it in every session. Project-level commands go in `<project>/.gemini/commands/`.

### Cursor

Either `AGENTS.md` at the repository root, or a project rule `.cursor/rules/pulupulu-motion.mdc`:

```md
---
description: Motion-graphics films via pulupulu-motion
alwaysApply: false
---
For any motion-graphics, explainer or data-story video task, read
docs/pulupulu-motion/SKILL.md first and follow its workflow and gates.
```

### Windsurf

Put the folder in the project and add `.windsurf/rules/pulupulu-motion.md` with the same three lines as the Cursor
rule. Workspace rules are version-controlled and travel with the repository.

### Cline

Add `.clinerules/pulupulu-motion.md` with the same pointer text. Cline reads the whole directory, so one file per
concern is fine.

### GitHub Copilot (VS Code / CLI)

Add the pointer to `.github/copilot-instructions.md` (or root `AGENTS.md`):

```md
When asked for a motion-graphics film, explainer, launch video or data story, read
SKILL.md in the pulupulu-motion folder and follow it before writing any HTML.
```

### Hermes Agent

```
# Windows
%LOCALAPPDATA%\hermes\skills\media\pulupulu-motion

# macOS / Linux
~/Library/Application Support/hermes/skills/media/pulupulu-motion
```

Hermes discovers it automatically and loads `SKILL.md` only when a task matches.

### Anything else

Point the agent at the file. That genuinely is the whole install:

> Read `pulupulu-motion/SKILL.md` and follow it. Finish by rendering an MP4 and verifying it.

The folder is self-contained: `SKILL.md` is the router, everything in `references/` is material it opens only when
the current step needs it.

---

## Step 3 — check the machine

Ask the agent to run the preflight, or run it yourself from the skill folder:

```sh
python scripts/doctor.py
python scripts/doctor.py --project film/      # also checks the page contract
```

Exit code `1` means a film cannot be made on this machine yet — it names what is missing. Do this **before**
writing scenes, not after.

---

## Step 4 — your first film

Paste this into your agent:

> Use the pulupulu-motion skill. Make a 20-second vertical (1080×1920) explainer with no narration about why
> bees matter, in English, saved to `~/films/bees`. Show me two still frames before you render.

What happens behind that sentence: `om new` creates the project, the agent writes a storyboard, builds the page
from it, runs `om check`, renders stills and **looks at them**, then `om render` and `ffmpeg` produce
`out/final.mp4`. Expect the first render in a few minutes for a 20-second film.

---

## 5. Model compatibility

**Fully optimised for:**

- **DeepSeek v4-1071 Flash**
- **Claude Opus 5.5**
- **Claude Opus 4.6**
- **Kimi K3 Pro**
- **GLM 5.3**
- **Gemini 4 Argon**
- **Gemini 4 Carbon**
- **Gemini 4 Neon**

"Optimised" is a claim about the files, not a slogan, so here is what it actually consists of:

- **A router, not a manual.** `SKILL.md` stays under ~2k tokens. The agent reads it first, then opens exactly one
  reference page for the step it is on — so a model with a smaller context budget is not asked to hold the whole
  skill at once.
- **Imperative, checkable rules.** "Measure the audio before building the picture", not "consider the pacing".
  A model that follows instructions literally still ends up with a film that renders.
- **Every step names the command that proves it.** The agent can self-verify (`om check`, `om still`, `om qa`,
  `deliver_check.py`) instead of describing success.
- **Machinery catches what taste would miss.** Dead motion, black frames, drifted captions and leaked language each
  have a gate script, so a cheaper or faster model is caught by a test rather than by your eyes at the end.

Any agent that can read a file and run a shell command can use this skill — it is plain Markdown with one entry
point and no framework. If your model is not on the list above, run the still-frame check early rather than trusting
a long render.

---

## 6. Narration with DeepSeek TTS

Narration is what separates a film from a slideshow, and it is where most pipelines cheat: they pick a duration,
then squeeze the voice to fit. Here the voice is made first and **measured**, and the picture is built on the
measurement.

DeepSeek's text-to-speech is a plain text-to-WAV service — **no SSML, no speed, no pitch, and no word timings.**
Both voices, **`stella`** (female) and **`tide`** (male), speak Indonesian and English. Everything a motion film
actually needs is built on top of that by `scripts/deepseek_voice.py`:

| Command | What it does |
|---|---|
| `probe` | checks the key and both voices before you spend anything |
| `speak` | one line → one WAV, cached, so a re-run only pays for the lines you changed |
| `beats` | per-phrase synthesis with planned gaps and tempo → a **measured** `timeline.json` |
| `lay` | puts lines on the film's grid: per-line start/end, overlap warnings, peak control |
| `gate` | synthesise → ASR → compare, phrase by phrase: proof the voice said the words on screen |
| `asr` | transcribes an existing WAV, for auditing a delivery |
| `cost` | billed characters and price **before** you spend it |

```sh
export DEEPSEEK_API_KEY=...        # environment only, never a project file
python scripts/deepseek_voice.py probe
python scripts/deepseek_voice.py cost beats.json --expand en
python scripts/deepseek_voice.py beats beats.json film/assets/voice.wav \
    --voice tide --timeline timeline.json
python scripts/deepseek_voice.py gate beats.json --voice tide --expand en
```

Exit codes: `0` ok · `1` gate failed · `2` bad usage or missing key · `3` provider error after retries.

Rules the skill enforces around the voice:

- **Caption = the spoken sentence.** `502` on screen, *five oh two* in the voice — notation may differ, words may not.
- **Durations come from measurement.** A timeline guessed in advance drifts within three beats.
- **Never compress speech to hit a round number.** Ask for a shorter script; the film follows the voice.
- **One voice per film**, and pauses are deliberate — 200–400 ms between beats reads as rhythm, not as a gap.
- **The key stays in the environment.** These scripts read `DEEPSEEK_API_KEY` from it and never write or print the value.

**No DeepSeek key?** Use the local voice instead: `om voice` (Kokoro or the system voice) needs no account and
produces usable narration. You lose the per-phrase prosody planning, and you still measure the result the same way.

---

## 7. Example prompts you can copy

Each one is written the way you would say it out loud, with the details that make it work. Replace the subject —
keep the structure. The twelve template names below are the ones `om templates` actually lists.

### First films

1. > Make a 15-second vertical film for Instagram announcing our new coffee subscription. English, no narration,
   > bold type on a cream background, one line per shot, ends with our name. Save it to `~/films/coffee`.

2. > Build a 45-second 16:9 explainer with narration about how a credit card transaction travels from the shop to
   > the bank. Plain English, calm pace, diagram-led — no stock photos. Save to `~/films/card-flow`.

3. > I need a 30-second vertical film about the water cycle for 12-year-olds, Indonesian narration, friendly and
   > warm, with the words on screen matching exactly what the voice says. Save to `~/films/water-cycle`.

4. > Make three 8-second vertical variants of the same message — "your data stays on your device" — with different
   > colour directions, then render them all and show me a contact sheet.

### Data stories

5. > Make a 40-second vertical data story from this table: [paste numbers]. Animate one bar per beat, put the real
   > value on screen while the voice says it as words, and hold the final comparison for two seconds. English
   > narration. Save to `~/films/revenue`.

6. > Turn this CSV into a 16:9 animated chart film — line chart drawing left to right, then a callout on the
   > biggest drop, with a two-second hold at the end. No narration, music only.

7. > Use the `finance-chart` template for a 15-second vertical film of this quarter's numbers [paste], clean grid,
   > one annotation only, no decorative noise.

8. > Show my country's population growth 1960–2025 as a vertical film with a running counter and a shape that
   > fills as the number rises. Verify the numbers against the source before rendering.

### Templates — say the name and the work collapses to the right shape

9. > Use the `kurzgesagt` template to make a 30-second vertical film about what is inside a lithium battery: the
   > glowing planet is the concept, each part a satellite node, and the camera goes into one node.

10. > Use the `kinetic-type` template for a 20-second vertical film of this quote [paste quote] — the words are the
    > visuals, no images at all, progress track on the right, highlighter on the punch word.

11. > Use the `vox-collage` template for a 40-second 16:9 explainer about why housing got expensive — screenshots
    > and note cards taped to a paper desk, red string, highlighter marking the one number that matters.

12. > Use the `whiteboard` template for a 30-second vertical explainer about photosynthesis: a marker writes each
    > sentence as it is said, doodles an icon beside it, arrows between causes, circles the key point, pulls back
    > to show the whole board.

13. > Use the `math-3b1b` template for a 40-second film about how a neural network learns — black board, one idea
    > at a time, an equation transforming into the next, symbols colour-matched to what is drawn.

14. > Use the `keynote-ui` template for a 30-second vertical launch film: dark glowing backdrop, glass cards
    > springing in, one screenshot with a highlight box, one big number counting up.

15. > Use the `ui-space` template for a 25-second 16:9 film of our dashboard: cut the screenshot into layers that
    > fly apart in depth, rebuild the parts that change in code, camera pushes into one comment and settles flat.

16. > Use the `object-3d` template for a 20-second vertical hero shot of our logo as a real object in a lit
    > studio — low swinging reveal, then a push into a detail, then a hero frame with the name.

17. > Use the `talking-head` template to package the video in `assets/talk.mp4`: name plate, two count-up number
    > cards, keyword callouts, a chapter card and a corner badge, each landing on a spoken word, laid out for 9:16
    > and kept off the speaker's face. Also export the transparent overlay for Premiere.

18. > Use the `blank` template and build a 12-second opener from nothing but type and colour — I want to see the
    > smallest film that still follows the whole contract.

### Characters and story

19. > Use the `storytime` template for a 25-second vertical story about my first day at a new job — but do **not**
    > reuse its stick-bean character: design my own flat-vector character and keep it consistent in every shot
    > (same outfit, same proportions). English narration.

20. > Make a 30-second vertical story with one simple character who wants something and does not get it until the
    > last shot. Flat vector, expressive but not detailed, no faces beyond dots and brows.

### Style and art direction

21. > Make a 20-second vertical film in Bauhaus style about the history of the circle, using only flat colour,
    > geometric shapes and typography. Check `references/art-motion/style-recipes/` and follow the recipe properly.

22. > Do the same subject in ukiyo-e style, then in vaporwave style, and show me the three side by side so I can
    > pick. Keep each under 12 seconds.

23. > Read a still from this film I like [attach image] and build a 15-second scene that matches its palette,
    > paper texture and type weight. Do not copy its content, only its visual system.

24. > Make a 25-second vertical film about the invention of the shipping container in a **1960s editorial print**
    > style: halftone, muted ink, sans-serif captions, camera moves like a magazine spread turning.

### Long scroll and other formats

25. > Make a 60-second **long-scroll** film: one continuous vertical world the camera travels down, chapter after
    > chapter, no cuts. Narration in English, and the camera must never stop moving.

26. > Take the project in `~/films/bees` and `om fork` it to 16:9 — re-layout properly for landscape, do not just
    > letterbox it.

### Narration work

27. > Write a 35-second English narration about the invention of the barcode, split it into beats, synthesise it,
    > then measure every phrase and build the film from the measured timeline. Do not guess a single duration.

28. > Re-record this narration in a calmer voice and tighten the pauses between beats by about 200 ms, then
    > re-time the picture to the new audio.

29. > Read my script aloud and tell me which sentences are unspeakable before you synthesise anything.

### Fixing an existing film

30. > Punch up `~/films/card-flow`. The middle 15 seconds are dead — the camera drifts and nothing happens. Find
    > the beats where the narration says something happens and make the picture react to it.

31. > Run `om qa` on this render and fix what it reports: pops, dead time, hard cuts. Show me the before/after
    > contact sheets.

32. > Every frame from 12 to 18 seconds is black. Diagnose it against `references/render-traps.md`, fix the cause
    > rather than removing the scene, and prove it with stills at 12, 15 and 18 seconds.

33. > The narration is missing in the final MP4. Check how it was muxed — it has to be `-map 0:v:0 -map 1:a:0` — and
    > re-deliver with `scripts/deliver_check.py`.

34. > Some Indonesian is still on screen in the English version. Run `scripts/lang-audit.py` and remove every line
    > it flags, including strings inside `<script>`.

### Tooling jobs

35. > Grab the materials from this product page — logo, screenshots, colours, fonts — with `om grab`, then tell me
    > what you actually got before proposing a film.

36. > Render `om swatch` direction cards for four palettes you think suit a finance product, and tell me which one
    > fails the contrast warnings.

37. > Add a discreet watermark "by Alucard0x1" to the delivered MP4 using `scripts/add_watermark.py`, and a creator
    > card with a portrait and its licence credit using `scripts/add_creator_card.py`.

38. > Generate a 20-second cinematic score with `om sound` under the narration, duck it by about 12 dB while the
    > voice speaks, and confirm the loudness ends up around −15 LUFS.

39. > Add "Anton" and "Playfair Display" to the project with `om fonts add`, then re-render the titles with them.

40. > Export a shareable package: a ≤10 MB GIF and a standalone HTML player with the project source, via `om share`
    > and `om export html`.

### Point-to-edit revisions

41. > Open `om studio`. I will click the elements I want changed; apply each comment with `om look` and `om done`,
    > and re-render when the queue is empty.

---

## 8. What a good prompt contains

The agent cannot read your mind, but it can read a sentence with these seven things in it:

| | Example |
|---|---|
| **Subject** | the invention of the barcode |
| **Audience** | warehouse managers, not children |
| **Platform + aspect** | vertical 1080×1920 for Instagram |
| **Duration** | about 30 seconds |
| **Language** | English narration, English on screen |
| **Narration or not** | narrated, or "music only, no voice" |
| **Where to save** | `~/films/barcode` |

Add a **style instruction** ("flat vector, Bauhaus, 1960s print, cinematic dark") when you care, and a **reference**
(an image, a past film, a recipe name) when you have one. If you have no subject, say so — the skill asks for one
instead of inventing a film about nothing.

Two habits worth keeping:

- **Ask for stills before the render.** Correcting a frame costs seconds; correcting a rendered minute costs the
  whole render.
- **Ask for verification, not adjectives.** "Run `om qa` and fix what it reports" produces a better film than
  "make it amazing".

---

## 9. Prompts that fail, and why

| Prompt | What goes wrong |
|---|---|
| "Make me a viral video" | no subject, no format, no length — you get a guess you reject |
| "Use this real photo of a person and animate their face" | out of scope; the honest answer is that this tool cannot, and a drawn stand-in is a provenance problem |
| "Make it exactly 60.0 seconds, squeeze the narration" | speech gets compressed and sounds rushed; length follows measured speech |
| "Use stock footage" | it has no footage, and a lookalike substitute reads as a collage |
| "Just make it look professional" | nothing to act on; name the style, palette or reference instead |
| "Render it and don't ask me anything" | you lose the still-frame checkpoint, where most rejections are caught cheaply |

---

## 10. When something goes wrong

- **`pulupulu: command not found`** → the CLI is not installed. `npm i -g huashu-motion@0.5.1`, then use `om`.
- **`om: command not found`** → the global npm prefix is not on `PATH`. `npm prefix -g` prints it; on Windows the
  binaries sit in that folder, on macOS/Linux in its `bin/`.
- **`doctor.py` exits 1** → read the line it prints; usually Node, FFmpeg, or Chrome missing.
- **The render stalls at frame 1** → a stale `om-chrome-*` process, or a full-frame filter / `feTurbulence` /
  `repeat:-1`. See `references/render-traps.md`; don't restart the render twenty times.
- **All frames are black** → the composition is missing its `data-*` contract attributes, or the renderer never
  started Chrome. `om still . --at 2` tells you in two seconds.
- **The final MP4 has music but no voice** → the mux used `-shortest` without explicit maps. Use
  `-map 0:v:0 -map 1:a:0`, or just run `scripts/deliver_check.py`.
- **Motion looks like a slideshow** → the picture is not reacting to the narration. Ask for beat-level motion, not
  camera drift.
- **Wrong language on screen** → `python scripts/lang-audit.py . --lang en`; art templates leak.

---

## 11. What is inside this repository

```
SKILL.md                       the router the agent loads: may I do this job, what to run,
                               what must pass, which page has the detail
references/cli.md              commands, page contract
references/workflow.md         the nine steps, project contract, mux recipe
references/narration-and-captions.md   beats, captions, one-language gate
references/design-taste.md     palettes, element budget, rhythm
references/motion-library.md   twenty motion languages, techniques, 3D layer
references/workflows-specialized.md   punch-up, product demo, talking head, grammars
references/audio-and-music.md  musical worlds, sfx, narration synthesis
references/render-traps.md     every failure that produced a black frame or a stall
references/verification.md     what to check, in what order, what no gate proves
references/measuring-a-reference.md   cut lists, motion curves, palettes, loudness from a reference film
references/art-motion/         57 style recipes, 9 grammar cards, camera language
references/stickman-and-figures.md  rig, principles as frame counts, snap-and-hold, the what-if format
references/ui-motion/          timing/easing tables, emotion mapping, choreography
references/narration/          tts-intonation skill + tts-prosody.py
references/generated-assets.md how to commission and validate image assets
scripts/doctor.py              read-only preflight
scripts/deliver_check.py       mux with explicit mapping, then validate the file
scripts/deepseek_voice.py      DeepSeek speech toolkit: speak, cost, lay, beats, asr, gate
scripts/lang-audit.py          fails the build when the wrong language survives
scripts/add_watermark.py       stamp a credit inside the delivery encode
scripts/add_creator_card.py    portrait + licence credit on the end card
scripts/art-motion/            shot-list linter, film/sub-zone gates, QA, delivery gate
scripts/art-motion/engine/     Playwright render engine for style-recipe scenes
```

### Rules baked in the hard way

- **Caption = the spoken sentence.** The only licensed difference is notation.
- **Measure the audio before building the picture.** A guessed timeline drifts within three beats.
- **Never compress speech to hit a round number.** Duration negotiates; format does not.
- **Mux with explicit maps.** `om render` embeds the score, so a bare `-shortest` keeps the music and drops the voice.
- **Check the language mechanically.** Templates leak; `lang-audit.py` is the gate.
- **A huge animated SVG re-rastered every frame stalls the renderer.** Move small props, not a 4400 px strip.

---

## 12. Licence

MIT © 2026 Alucard0x1 — see `LICENSE`.

The renderer (`huashu-motion`) is a separate MIT project by Huashu / [alchaincyf](https://github.com/alchaincyf)
and is **not** bundled here; you install it yourself. Third-party components, their licences, and one character
that is **not** free to reuse are listed in `THIRD-PARTY-NOTICES.md`.
