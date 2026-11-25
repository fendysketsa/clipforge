# Sourcing icons, vectors and illustrations

Owner: icons, vectors and their licences

Where a film needs an object (locomotive, server, shield, truck, leaf, clock, mascot), do not hand-draw
crude geometry and do not invent a grey box. Take a real vector file, then make it belong to the film.

This document is the whole loop, in the order that keeps you out of trouble:

> **decide the film's drawing language → search → fetch → classify → group into a family → pick →
> normalise → integrate → look at it at final size → record the licence**

Skipping the first or the ninth step is how a sourced icon ends up looking worse than a drawing. Both
have their own section, because both were skipped in real builds.

---

## 1. Decide the film's drawing language first

The icon family has to match **the film**, not only the other icons. Two films built from the same
library need opposite choices:

| The film is drawn as | Compatible glyphs | Incompatible, and why |
|---|---|---|
| **Flat fills, no outlines** (solid shapes, silhouettes) | single-colour **solid/silhouette** glyphs | stroke-only line-art — reads as a sticker pasted on, because every neighbouring shape is edged in colour while the glyph is drawn only in edges |
| **Line-art** (outlines, x-ray drawings, blueprint look) | **line** glyphs at the same stroke weight | solid silhouettes — read as a black blob that ignores the film's language |
| **Duotone / flat colour blocks** | 2-tone glyphs, or solid glyphs recoloured to the two tones | multicolour illustrations — a third and fourth hue appears from nowhere |
| **Painted / textured** (art-motion styles) | illustration-style vectors, or nothing at all — draw it | UI icons — a 24×24 UI glyph in a painted frame reads as interface furniture, not scenery |

Write the decision into `materials.md` before downloading anything, e.g.
`film language: flat fills → accept single-colour silhouettes only`. Every later argument about an icon
becomes a lookup instead of a taste debate.

---

## 2. Where to get them: svgrepo.com

An index of openly licensed icons and clip-art. Direct SVG download, no account, no API key:

```sh
# page:  https://www.svgrepo.com/svg/547900/teaching-task
# file:  https://www.svgrepo.com/show/547900/teaching-task.svg
curl -sL -A "Mozilla/5.0" -o materials/icons/clock_547900.svg \
  https://www.svgrepo.com/show/547900/teaching-task.svg
```

- **Search index:** `https://www.svgrepo.com/vectors/<query>/` — a listing page with ids and slugs,
  never family metadata. §3 has queries that actually return usable glyphs.
- **Collections:** `https://www.svgrepo.com/collections/<name>/` — a collection *is* a single design
  family, which is exactly what a film needs. Prefer it over search when the film needs 3+ icons.
- **Name the file `<slug>_<id>.svg`.** The id is the only thing that leads back to the licence page;
  dropping it turns provenance into a guess.

### Licence rules

| Label on the icon page | Use |
|---|---|
| SVG Repo License (default) | free, commercial OK, attribution appreciated not required; no reselling as-is |
| Public Domain / CC0 | free, no attribution |
| MIT / Apache / MPL | free, keep the notice in `materials.md` |
| CC BY / CC BY-SA | free with visible credit — fine for editorial, awkward for a 60 s ad |
| CC BY-NC | **non-commercial only** — never in a client or monetised deliverable |
| Logo license | trademark belongs to the company; using a brand mark needs a reason and their rules |

When the deliverable is a client film, stay on SVG Repo License / PD / MIT. Anything else gets swapped,
not shipped.

**If the label cannot be read, the asset has no licence.** SVG Repo renders the licence block with
JavaScript, so `curl` and plain HTML extraction return a shell with no label in it — that happened on
every icon in this skill's own reference film. In that case write `license: not verified` in
`materials.md` and treat the file as a **placeholder**: swap it for a set whose licence is stated
(Iconoir MIT, Tabler MIT, Lucide ISC, Feather MIT, Heroicons MIT, Bootstrap Icons MIT — all state it in
their own repo, not in a JS widget) before anything commercial or public ships. Never quietly upgrade
"not verified" to "SVG Repo License": that is the difference between a cleared asset and a liability.

---

## 3. Search vocabulary that returns usable glyphs

A listing page sorts by relevance to the *word*, so the word decides what you get:

| Need | Query | Why it works |
|---|---|---|
| an object for a scene | `locomotive`, `train-track`, `railway-station`, `canyon`, `mountain-top-summit-sunrise` | concrete nouns; two-word compounds exist where the single word does not |
| a symbol/UI glyph | `warning-triangle`, `coin`, `ruler`, `sun` | singular — the plural usually returns a grid-of-items illustration instead |
| a silhouette specifically | `<noun>-solid`, `<noun>-fill`, `<noun>-glyph` | style words cut a 50-hit list to a handful |
| a line glyph specifically | `<noun>-outline`, `<noun>-line`, `<noun>-stroke` | same, opposite direction |
| one coherent set | `collections/<set-name>/` | family by construction; still classify the files (§4) |

What real searches showed:

- **A search page lists ~50 hits and they are not one family.** One page of `train` held a 16×16 solid
  glyph, a 24×24 stroke-2 line set, a 64×64 silhouette and a 64×64 eleven-colour illustration.
- **Ids cluster by source set.** Icons from the same set sit in the same numeric neighbourhood, so when
  you like one glyph, look at the ids around it before searching again.
- **A missing query is not a missing asset.** `steam-locomotive` returned 0 hits on a day when
  `locomotive` returned 50 — including a better glyph than the compound would have produced.

---

## 4. Fetch, then classify before you trust it

Download, then read the file itself. Four numbers decide everything:

```sh
curl -sL -A "Mozilla/5.0" -o materials/icons/x_403803.svg https://www.svgrepo.com/show/403803/locomotive.svg
grep -c '<svg'  materials/icons/x_403803.svg                  # must be 1: an HTML block page has none
grep -o 'viewBox="[^"]*"' materials/icons/x_403803.svg        # 24x24 UI icon · 64x64 glyph · 512/1024 illustration
grep -o 'stroke-width="[^"]*"' materials/icons/x_403803.svg   # present = line set
grep -oE '(fill|stroke)="#[0-9a-fA-F]{3,6}"' materials/icons/x_403803.svg | sort -u | wc -l
grep -o '<path' materials/icons/x_403803.svg | wc -l
```

By hand that stops scaling after five files, so the skill ships a tool:

```sh
# one line per file: grid, line-or-solid, colour count, path count, verdict
python scripts/art-motion/icon_audit.py --film-style solid classify materials/icons

# group into families and expose the outliers (one matrix per group)
python scripts/art-motion/icon_audit.py --film-style solid families materials/icons

# strip width/height, recolour to the palette, keep the viewBox; prints the manifest row
python scripts/art-motion/icon_audit.py normalise materials/icons/locomotive.svg --colour "#120a08"

# contact sheet at final size — the gate that catches what the text cannot
python scripts/art-motion/icon_audit.py --film-style solid contact materials/icons \
  --out materials/icons/contact.html --size 110 --columns 7
```

`--film-style` is the §1 decision: it is what turns "1 colour" into either *usable* or *this will read as
a sticker*. The tool refuses to guess when the text genuinely cannot tell:

```
64x64     solid  1c   6p  sw=-   likely silhouette — confirm on the contact sheet
                                 (thin strokes hide in one colour)
1024x1024 solid  4c   9p  sw=-   undecided: 9 paths / 4 colours — open the contact sheet;
                                 one-colour etched art and silhouettes look identical in text
64x64     solid  11c  46p sw=-   multicolour — fights a controlled film palette
24x24     line   1c   2p  sw=2   line-art in a flat-fill film — will read as a pasted sticker
```

That last comparison is the real lesson: a **one-colour etched illustration** and a **silhouette** are
indistinguishable in the file's text — the same "6 paths, 1 colour" described both the accepted
locomotive and the rejected etched canyon. Only the rendered sheet separated them.

---

## 5. One family, not five

A frame with one outline icon, one solid icon and one duotone icon reads as clip-art soup, and that is
what "looks cheap" actually is. Inside the family chosen in §1, the set must agree on:

1. **Grid** — 24×24 (UI), 64×64 (glyph), 512/1024 (illustration). Mixing grids makes optical sizes
   wrong even at the same CSS width.
2. **Stroke weight** — compare `stroke-width` in two files; 1.5 and 2 side by side look like two hands.
3. **Corner language** — all sharp or all rounded.
4. **Density** — a 46-path icon next to a 3-path icon looks like a mistake, not like contrast.

`families` prints exactly this grouping. From the railroad film's download folder, 27 files fell into
13 groups, and the accept list came from the largest compatible one:

```
[OK] 64x64|solid|mono|-    -> 5 files  (locomotive, canyon-silhouette, warning-triangle …)
[OK] 24x24|line|mono|2     -> 5 files  (coin, sun, train-track, warning …)  ← wrong language for this film
[OK] 24x24|solid|mono|-    -> 3 files  (flag, warning-circle …)
[OK] 16x16|solid|mono|-    -> 2 files  (sun, train)
```

If the set you want does not exist, **redraw the odd one out at the same stroke weight** instead of
importing a second family. One hand-drawn glyph inside a family looks intentional; two families look
assembled.

---

## 6. Monochrome or multicolour: the decision

Default to **monochrome**, recoloured into the film's palette. Multicolour is a deliberate exception.

**Monochrome (recoloured) when:**
- the icon is furniture — it labels a card, a node in a diagram, a list row, a step;
- it repeats (3+ instances) or animates in sequence, so it must not fight the accent colour;
- it sits inside a card or on a coloured ground;
- it is small (< 160 px) — colour detail is invisible there anyway;
- the film's palette is 2–3 colours and each colour means something.

**Multicolour (original colours) when:**
- the object is the subject of the shot, not furniture — the one hero icon of a scene;
- its real colour carries meaning a viewer would miss (brand logo, national flag, food, mascot, product);
- it appears once, at large size, on a neutral ground, and the film has an accent colour to spare;
- it must be recognised instantly (app icon, payment mark).

**Never:** mix multicolour assets from different sets (their palettes clash), put a multicolour icon on a
saturated card, or use multicolour for a diagram node that changes state — state colour must be yours.

**Budget, not decoration.** In a 21-shot story film **two** shots needed a real object (a locomotive, a
flag); the other 19 were bespoke geometry no library carries (a buckling rail, canyon strata, a
newspaper masthead). One sourced icon per scene is decoration and reads as such.

---

## 7. Normalise the file

Most downloads hardcode `fill="#000"` per path, which defeats recolouring and makes animation awkward.
The normalise contract, applied once at import:

1. **Strip `width`/`height`**, keep `viewBox` — the wrapper decides the size.
2. **Remove the `<?xml …?>` prologue and `<!-- … -->`** — they survive inlining and bloat the page.
3. **Strip `metadata`, `<sodipodi:namedview>`, unused `<defs>` gradients, editor ids** — a duplicated
   `id="path1234"` across two inlined glyphs breaks `url(#…)` references.
4. **Hand colour to the film:** either `currentColor` (when inlined into HTML that sets `color`) or one
   palette hex at build time. The baked original colours are the thing you are removing.
5. **One asset per file**, named `<slug>_<id>.svg`, so the licence record and the file cannot drift.

```sh
python scripts/art-motion/icon_audit.py normalise materials/icons/flag_527710.svg --colour "#ffd23f"
# wrote materials/icons/flag_527710.svg  grid=24x24 paths=2
# manifest row: | `flag_527710.svg` | <source URL> | <licence> |
```

Fill that manifest row in the same minute you normalise the file. It is the only step with no way of
being noticed later when it is missing.

---

## 8. Integrate: inline at build time, never fetch at render time

When a film is generated by a `build.py`, read the glyph from `materials/` and paste it into the scene
during the build. The composition stays self-contained — no network at render time, which the
seek-determinism rule requires — and recolouring becomes a parameter instead of a hand-edit:

```python
def icon(name, x, y, k, colour=None, opacity=1.0):
    """Inline a downloaded glyph (viewBox 0 0 64 64); recolour at build time."""
    raw = open(os.path.join(ICONS, name), encoding="utf-8").read()
    inner = re.sub(r"^.*?<svg[^>]*>", "", raw, flags=re.S)
    inner = re.sub(r"</svg>.*$", "", inner, flags=re.S)
    if colour:
        inner = re.sub(r"#[0-9a-fA-F]{3,6}", colour, inner)
    return f'<g transform="translate({x},{y}) scale({k})" opacity="{opacity}">{inner}</g>'
```

**The scale is the part that goes wrong.** `k` multiplies the *glyph's own grid*, so a 24×24 glyph at
`k=6.4` is only 154 px wide inside a 1080-wide frame:

| Glyph | Grid | `k` | Rendered | What happened |
|---|---|---|---|---|
| flag | 24 | 6.4 | 154 px | blob against a 420 px flagpole — rejected |
| flag | 24 | 7.4 | 178 px | still small; readable only because the pole shrank with it |
| flag | 24 | 14 | 336 px | ran off the right edge — computed from the pole, not the frame |
| locomotive | 64 | 5.1 | 326 px | correct: sized to the rail gauge, wheels seated on the rail |

Rules that follow from the table:

- **Measure the neighbour, then pick `k`.** The flag relates to the pole; the locomotive to the gauge.
- **Seat on a constant, not by eye:** `y = SURFACE_Y - glyph_height * k`; if the glyph has wheels or a
  base, put that contact line on the surface, not the bounding box.
- **Check the frame edges before rendering:** `x + grid_width * k <= 1080`.
- **Layer order:** ground → props → sourced glyph → smoke/light overlays → caption band.

More traps:

- **Path count:** a 900-path icon animates badly. Keep hero icons under ~120 paths.
- **Animate the wrapper, not the paths:** scale/rotate/mask the container. Per-path draw-on needs a line
  set (`stroke-dasharray`), not a solid one.
- **Never put webfont `<text>` inside the inlined SVG** — it re-rasters the layer every frame and can
  stall a render completely (see the render-trap notes in `SKILL.md`). Position an HTML `<div>` over the
  SVG instead.
- **Credits:** if the licence needs it, one 18 px line in the end card, not a paragraph.

---

## 9. Look at it at final size — the gate text cannot pass

The contact sheet is not optional: both failures this document is built around were invisible in every
text metric.

```sh
python scripts/art-motion/icon_audit.py --film-style solid contact materials/icons \
  --out materials/icons/contact.html --size 110 --columns 7
# render it (Chrome headless, or pulupulu still) and actually look
```

What you check, in order:

1. **Does it read as the object?** At 110 px the etched canyon read as decoration; the silhouette
   locomotive read as a locomotive — same grid, same colour count, same path count.
2. **Is the weight in the film's register?** Thin strokes vanish beside thick flat shapes; thick strokes
   shout beside thin ones.
3. **Is the silhouette still closed?** Wheels, coupling rods and cab details merge into one blob at phone
   size. Shrink the sheet to ~40 % and look again — that is the phone test.
4. **Greyscale pass:** desaturate the sheet. If two icons become the same grey mass, they will be
   ambiguous in a fast cut.
5. **Contrast against the film palette:** a mid-grey glyph on a mid-brown ground disappears. Aim for the
   4.5:1 body-text ratio for anything that carries meaning.

---

## 10. Failure log (each of these shipped at least once)

| Symptom | Cause | Fix |
|---|---|---|
| The picture reads as decoration, not an object | hand-drawn crude geometry instead of a real vector | source one glyph from a matching family (§5) |
| The icon looks like a sticker | line-art glyph inside a flat-fill film | match the film's language (§1), not the other icons |
| Colours fight the film | 11-colour illustration inside a 3-colour palette | force to one palette colour, or pick another glyph |
| A flag reads as a yellow blob | 24×24 glyph at `k=6.4` = 154 px beside a 420 px pole | size from the neighbour (§8) |
| A glyph hangs off the frame edge | `k` chosen without the `x + width*k <= 1080` check | compute the box before placing |
| A locomotive floats above the rails | placed by bounding box | seat the contact line on the surface constant |
| A doc points at a file that does not exist | paths rewritten from memory after a merge | run the path audit from `agent-skill-sourcing` |
| Licences missing from `materials.md` | recorded "later" | fill the manifest row at normalise time (§7) |

---

## 11. Checklist before the asset goes in the film

1. Film's drawing language written down; every icon accepted or rejected against it.
2. Family decided (`families` shows one dominant group); grid/stroke/weight/density all matching.
3. `classify` verdicts read; every "undecided" resolved by looking at the contact sheet.
4. Monochrome by default; multicolour only for a single hero object on a neutral ground.
5. Normalised: no `width`/`height`, no XML prologue, no metadata, colour handed to the palette.
6. Inlined at build time — nothing fetched at render time.
7. `k` computed from the neighbour, contact line on the surface, frame edges checked.
8. Looked at on the contact sheet at final size, in greyscale, and at phone scale.
9. Licence recorded per file; unreadable label ⇒ `not verified` ⇒ placeholder, never a named licence.
10. `materials.md` states either the sourced files or one honest line about why no library asset fits.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../SKILL.md) · [Art library index](art-motion/INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
