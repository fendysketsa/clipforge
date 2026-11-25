# The narrated-film workflow, end to end

Owner: the nine steps and project-level contract


The nine steps from brief to delivered file, and the project contract that keeps them deterministic.

Part of the `pulupulu-motion` skill. The entry point and the gate table live in `SKILL.md`.

## 3. Nine-Step Production Workflow

1. **Direct it.** Run `om learn <topics>` first. Read the product (site, repo, app, README, screenshots) and gather real material into `materials/` + `materials.md` via `om grab <folder|url> <dir>` and live app captures.
   - **Real material rules:** Logo on screen = real SVG/image file, never redrawn. UI = real capture for context, or **rebuilt in HTML/CSS** traced over a capture at exact size when it must move (typing, clicking, scrolling) — never grey placeholder boxes or invented UI. Photos/avatars/thumbnails = real product assets or openly licensed (Unsplash/Pexels/Wikimedia) with source + license in `materials.md`. Mask private data in local screenshots.
   - **Icons and objects come from a real vector library, not from your hands.** `svgrepo.com` serves direct SVG files (`https://www.svgrepo.com/show/547900/<slug>.svg`) and organises them into single-style collections. Take every icon from **one family** (line, solid, duotone, rounded — matching stroke weight, grid and corner language), keep them **monochrome and recoloured into the film palette** by default, and reserve **multicolour** for the one hero object whose real colour means something. License is per icon page: follow SVG Repo License / PD / MIT for client work, never CC BY-NC.
     - **Order of operations (do not shuffle it):** write the film's own drawing language down (`flat fills → silhouettes only`) *before* searching; then `classify` every download, `families`-group them, pick from the dominant compatible group, `normalise`, inline at build time, and **look at a contact sheet at final size** before the glyph enters the film. A line-art glyph in a flat-fill film reads as a sticker; a one-colour etched illustration and a silhouette are indistinguishable from the file text — only the rendered sheet separates them.
     - **Tooling:** `python scripts/art-motion/icon_audit.py --film-style solid classify DIR | families DIR | normalise FILE.svg | contact DIR` (grid, line-vs-solid, colour count, path count, family grouping, recolour, contact sheet). It says `undecided` when the text cannot tell — resolve those by looking, never by assuming.
     - **Licence:** record `name.svg_<id> — source URL — licence` in `materials.md` at normalise time. If the label cannot be read (SVG Repo renders it with JS), write `not verified` and treat the file as a placeholder, never as a named licence.
     - Full loop, search vocabulary, decision tables, failure log: `references/asset-sourcing.md`.
   - **When no library carries the object, generate the print instead of drawing it.** Pictorial material (a 1980s terminal, a magazine page, a console, a portrait mount, a map) is where hand-drawn paths read as stickers and an icon library has nothing. Brief a register into `DESIGN.md`, generate 1024 px prints four at a time with an image model, crop each to its content, mount it as a panel, and add all type in HTML. Full route with the crop script, mount geometry, register table and the one-round critique: `references/generated-assets.md`.
   - **Documented is not applied — this user checks.** A film built shot by shot on hand-drawn geometry while this section sits in the skill comes back as "why didn't you use the icon library" — the question this user actually asked. Close the loop mechanically: every build ends with a `materials.md` that either lists the sourced files (source URL + licence) or states in one line why no library asset fits that shot. Keep the budget small and honest — on a 21-shot story film **two** shots needed a real object (a locomotive, a flag) and the rest were bespoke geometry no library carries; an icon in every scene is decoration, which §3e forbids. In a flat-shape film only **single-colour silhouette** glyphs survive the recolour test; a line-art glyph among flat fills reads as a sticker.
   - **One-line user requests:** Do the research first, then send **one** plain message with what you understood (product + the one takeaway) and 3–4 high-impact decisions with your defaults marked and 2 real-world alternatives each (where it plays & length, energy, narration). Never send a multi-question form. Always settle **narration**: none (music+sfx), system TTS (`om voice --text`), user recording (`om voice --audio`), or footage audio. Default: none.
   - **Energetic default (when no style/energy named):** Frame 0 is the poster (subject already present, never blank/black or a lone glowing dot). Move at once, land the first burst < 5 s, cut on the beat, keep type large enough for a phone feed, and stay in the product's palette.

2. **Three directions** (skip only if user named a style or project already has one). Offer A (Fit), B (Amplify), and C (Unexpected) differing in **motion language or material**, not just colour:
   - **Exactly one** of the three must be a **depth direction** (`ui-space` or `object-3d`); the other two must have no 3D as their core idea. Never three quiet directions for a launch film.
   - If directions share a drawn character/emblem, build that artwork alone at full size first. Never draw organic animals/people as crude geometric SVG — cut from real art/photos.
   - For each direction, output the card below, render **one real full-res key frame** (`om still directions/a.html`), and run `om swatch directions.md`:
     ```text
     A · <name>       language: <id> (+ technique highlights)   look: <type, material, light>
     Palette:         <role #hex share · …> — from: <source of each colour>
     Logline:         <one sentence with hook and ending>
     Why it fits:     <message shape + personality sentence → this>
     Feel:            <route (continuous/montage/hybrid), BPM, events/bar, first 3 s muted>
     Risk:            <what could make it fail>
     ```
   - Keep `Palette:`, `look:`, and `Feel:` separable so the user can mix layers ("A's palette with C's composition"). Pick the music world yourself after direction approval; don't put music on direction cards unless asked.

3. **Treatment (`treatment.md`).** Write before building the full film:
   - **Rhythm sheet** (stretch, bars, energy 0–10, events/bar, moves, music) + **Beat map** (`bar.beat | time | what happens | language move | sound`).
   - **Four stills** (`om still <dir> --at t1,t2,t3,t4`): hook frame, hero moment, densest frame, end card.
   - **Continuity chain**: one line per transition naming what object or colour carries the eye from shot N to N+1. Any unlinked jump is a hard cut — keep only if intentional.

4. **Build the hardest shot first.** Use a grammar template (`om new <dir> --template <id>`) if narration fits a structured explainer; otherwise `om new <dir>` (`blank`, `ui-space`, or `object-3d`). Build the hardest/most important moment at full resolution with final fonts and colours before laying out the rest. Place `OM.sfx(name, t)` on landing frames and `scene:<id>` labels on `OM.beat(n)`.

5. **Look at it & self-critique.** Run `om check <dir>` (0 errors). Inspect `om still` frames (especially frame 0, end frame, and 0.25 beats after every cut). Render without `--blur`, run `om qa <dir> --sheet`, and inspect every contact sheet for identical-tile runs (dead time), slide-like repeats, and ugly mid-transition frames. Watch at 1× speed (or have a cold reviewer agent watch it) and write & fix the 3 notes a demanding director would give.

6. **Give it sound.** Run `om voice` first if narrated, then `om sound <dir>` (ducks music automatically). For launch films, write a custom ABC `<script type="text/vnd.abc" id="om-score">` (Composer mode, §10); use `OM.music({ product })` only for quick drafts/stings. Fix every `warning score:` line. Aim for 8–15 `OM.sfx` hits per 30 s. Check spectrogram (`ffmpeg -i assets/sound.wav -lavfi showspectrumpic=s=1600x400 spec.png`) to verify hits align and no stretch is empty. Skip only for `--transparent` overlays or requested silence.

7. **Hand over studio.** Run `om studio <dir> --no-open &`, share the URL, and loop on `om inbox <dir> --wait` → `om look` → minimal edit / `om set` → `om done` until signed off. Re-run `om sound` after any timing change.

8. **Export & Share.** Render final export with `om render <dir> --blur` (and `data-fps="60"` for fast UI). Run `om qa <dir>` (`--loop` for loops). Run `om share <dir>` and write `out/share/share.md` in the user's language (what the film is + 1 concrete making detail). Report the MP4, GIF, and `share.md`, noting the end carries a small toggleable signature. Never post anything yourself.

9. **Harvest.** Run `om learn harvest <dir>` on sign-off to distil studio edits/comments into `~/.pulupulu-motion/experience.md`.

---

## 11. Project Contract, Determinism & Comment Loop

```text
my-film/
  index.html      # Single root composition per project (drafts go in tools/)
  vendor/         # gsap.min.js, om.js (+ three.min.js, om-three.js for 3D, clip/ for grammars)
  assets/         # fonts, images, audio (sound.wav generated by om sound)
  out/            # Renders from om render
  .om/            # history, inbox.jsonl, render log
```

- **Root & Variables:** `<html data-composition-variables='[{"id":"title","type":"string","default":"…","group":"Copy"}]'>` (types: `string`, `number`, `color`, `boolean`, `enum`). Root element needs `data-composition-id`, `data-width`, `data-height` (optional `data-fps="60"`, `data-duration`, `data-om-signature="off"|"top-left"`). Omit `data-duration` so hold variables control length via `tl.to({}, { duration: V.endHold })`. Bind with `data-var-text="id"`, `var(--id)`, `data-om-var="id"` (for JS-split text), and `OM.vars()`.
- **Pickable Targets & Scenes:** `data-om-id="name"` on every interactive/visible element (or `OM.region(id, t => [x,y,w,h] | null, label)` for canvas). Scenes: `tl.addLabel('scene:intro', 0)`.
- **Signature:** Films ≥ 4 s automatically show a subtle "Made with pulupulu-motion" for the last 1.2 s in a free corner. Leave one corner clear (`om check` warns `signature-covers`), or set `data-om-signature="off"` only when requested or for paid client deliverables.
- **Seek Determinism (Renderers jump to `t`, never play sequentially):**
  - Always use `tl.fromTo(..., { ... }, { ..., immediateRender: false })` so start states don't leak to frame 0.
  - **Never** use `overwrite: true` on a timeline.
  - Keep every timeline position `>= 0`.
  - Hide groups with `opacity`/`autoAlpha`, not `visibility`.
  - Quantise hard cuts half a frame in (`(Math.floor(t * fps) + 0.5) / fps`) and counters to whole frames when using `--blur`.
  - Put decorative overlays (vignette, grain) **before** content in DOM, or mark intentional overlaps with `data-layout-allow-occlusion` / `-overflow` / `-overlap`.
  - No `Date.now()`, no `Math.random()` (`OM.random(seed)`), no external network URLs at render time.
  - Canvas/WebGL loops use `OM.clock(tl, t => draw(t), duration)` (runs *after* GSAP tweens on every seek).
- **Comment Loop:** `om inbox <dir> --wait` → `om look <id> <dir>` → minimal edit (`om set` or targeted `index.html` edit without renaming `data-om-id`s) → `om done <id> <dir> --note "<1-line summary>"`. Every version is saved in `.om/history` (`om undo` always works).

---
