# Palette: one palette per film

The `palette` line above the shot table: pick one set from here and write its name, or define your own 3–6 values by the rules at the end of this page. Every parameterised clip spec writes the same `"theme"`, and scenes use only those colours (lighter, darker, more transparent is fine — no new hues).

## Off limits first

**Blue-purple gradient backgrounds, deep purple starfield backgrounds, neon cyan-purple glow, purple frosted glass**: the author's own words — we have to avoid this blue-purple gradient junk palette, it is very AI slop. These are the default colours AI falls into most often when it animates, and a viewer reads them at a glance as "made by AI".

`deliver.py` measures it: more than 30% of a frame in blue-purple (hue 225°–300°, saturation ≥0.30) counts as a blue-purple frame; blue-purple frames over 30% of the film is a red light, no delivery. When the subject itself needs blue-purple (a user-named cyberpunk purple, a Van Gogh Starry Night kind of image), add `--allow-blue-purple "reason"` at delivery: it drops to amber, and the reason goes into the facts section of the delivery notes.

Flat navy (hue around 210°, see `navy` below) is not off limits: it is one deliberate base colour, not a gradient and not glowing.

## Eight ready palettes

Each set has 6 keys: `bg` background, `surface` card / paper / panel, `ink` primary text, `sub` secondary text and hairlines, `accent` primary emphasis, `accent2` secondary emphasis. In a clip spec write `"theme": "wood"`, or write it as an object `{"name": "wood", "accent": "#B8452A"}` to change just one key.

| Name | Good for | bg | surface | ink | sub | accent | accent2 |
|---|---|---|---|---|---|---|---|
| `paper` | Humanities, history, reading, explaining an idea | #F3EDE2 | #FBF8F2 | #1B1A17 | #6B655B | #C8402F | #2F5D62 |
| `poster` | Opinion, conflict, popular science that lands one sentence hard | #FFD23F | #FFF6D6 | #111111 | #4A4433 | #FF5A36 | #14213D |
| `ink` | Technology, night scenes, serious subjects | #121417 | #1E2226 | #F2EFE8 | #A39E93 | #F2B33D | #5FB3A1 |
| `navy` | Product, data, phones and electronics (flat, no gradient) | #0D1B2A | #16293D | #EEF3F6 | #8FA3B3 | #5CC8E0 | #F2A93B |
| `bauhaus` | Design, structure, geometry, process | #EFE9DD | #FFFFFF | #111111 | #555555 | #D62828 | #1D4E89 |
| `snow` | Winter, medical, clean, laboratory | #E9EEF0 | #FFFFFF | #1F2A30 | #5E6B72 | #D9482B | #3E7C8C |
| `wood` | Daily life, kitchen, craft, things at home | #EDE3D1 | #F7F1E6 | #2B2622 | #7A6E62 | #C4552D | #3F5B4B |
| `chalk` | Classroom, derivations, formulas, working a problem | #23302B | #2E3D37 | #F1EFE6 | #A9B3AA | #F4D35E | #E87D5A |

## Define your own

- 3–6 colours: one background, one surface, one primary text, one secondary text, one or two accents. An accent points at one thing only within a shot.
- Fix the base first: light (paper, snow, wood) or dark (ink, navy, chalk). Never jump back and forth between light and dark within a film.
- Keep values out of the blue-purple zone: a colour at hue 225°–300° with saturation ≥0.30 is never a background and never used over a large area. `storyboard_lint` checks the values in the palette; anything in this zone is a red light.
- No gradient backgrounds, no neon outer glow. For depth use paper texture, grain, or two flat layers of light and shade.
- With real material (screenshots, photos), pull one or two colours out of the material as accents; the base colours still come from this set.

## Self-check

Before delivery, lay the extracted frames out in a row and look: is the background in the same brightness range from start to finish, are the accents only that one or two, does some shot suddenly sprout a white-background bar chart, a purple starfield, a neon border — "another film's colours". If so, redraw that shot against the palette.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
