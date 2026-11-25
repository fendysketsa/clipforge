# Shot list template: shot list first, then build

Step 1 of the track tier. The open tier is advised to write one first too; lint there is optional.

A shot list is this film's storyboard: lock one visual style first, then one row per shot, writing down exactly **what object is in the frame, what it is doing, how the camera moves, how many characters sit on screen, and what builds it**. Write this table and the film cannot turn into a deck that grows one page longer, nor into a collage where every shot has its own style; fail to write one row and that shot is not thought through yet — leave the code alone.

## How to write it

Copy the block below into `<project>/shot-list.md` (called `shot-list.md`), fill in the first three lines above the table, then fill one row per shot:

```markdown
Style: <one sentence: one style card or one drawing method, used for the whole film>
Palette: <a name from references/art-motion/palette.md, or 3–6 #hex values>
Character: <none / hands and back only / frame library <path>>

| Time | Subject | Action | Camera | On-screen text | Method |
|---|---|---|---|---|---|
| 0–3 | <noun: a person, a thing> | <verb: what it is doing right now> | Stop / Slow push-in / Pull back / Lateral truck / Fast push-in / Slam in / Cut | <≤8 characters, may be empty> | <y4 clip shot-01.json / scenes/xxx.js / footage: photo> |
```

**Keep the three lines above the table starting with the literal keys `Style:`, `Palette:`, `Character:` — `storyboard_lint.py` reads those keys (it also accepts the original Chinese keys, so old shot lists still lint).** The optional fourth line `Allow blue-purple: <reason>` is the only way past the blue-purple palette check.

| Column | Write this | Never write |
|---|---|---|
| Time | `0–3`, `3–7.5` or `0:03–0:07`; the previous shot's end is the next shot's start | |
| Subject | a noun you can point at on screen and say "that's it": a slice of bread, a spore, the protagonist's hand | titles, key points, text, lists, labels, subtitles, cards, background, the frame, icons; empty shots, flat colour, black frames, gradient backdrops (the protagonist is not in the picture) |
| Action | a verb — this object's own action: drifts in, cracks open, burrows in, gets sliced off | appears, displays, shows, fades in, appears one by one |
| Camera | this shot's main move, chosen by "where should the audience look at this moment": Stop / Slow push-in / Pull back / Lateral truck / Fast push-in / Slam in / Cut. Fast push-in and slam-in are accents — only for a reveal, a reversal, a key number; after you push in, come back out. Uses and durations of each move: `references/art-motion/camera-language.md` | a push-in on every shot; a constant slow push-in on every shot |
| On-screen text | ≤8 characters per shot, may be empty; verbatim narration belongs to the subtitles | whole narration sentences, three-line key points |
| Method | what builds it: a parameterised clip in which grammar (name the spec file), `scenes/<id>.js` drawn in code, real footage at full frame | a different grammar on every shot |
| Tags (optional column) | small labels pinned beside the object in this shot, separated by 、 | more than 3 in one shot; a row of glowing pills |

The linter counts one per Chinese character and one per run of Latin letters or digits, so for English on-screen text read ≤8 as roughly eight words.

The three lines above the table (the style lock):

- **Style**: one sentence naming the one drawing method for the whole film, e.g. "warm wood-toned paper illustration, flat fills with fine pencil lines, afternoon side-light in a kitchen". Changing the scene is fine; changing the style is not — cartoon people, a dark code screen, starry-sky icons, a white-background bar chart, paper, web screenshots in rotation: each shot looks fine on its own and the whole film is a collage.
- **Palette**: one set from `references/art-motion/palette.md`, or 3–6 colour values. Every clip spec writes the same `"theme"`, and scenes use only these colours too. No blue-purple gradients, no deep-purple starfields, no neon cyan-purple. Only when the user names blue-purple themselves (cyberpunk purple, a Van Gogh Starry Night) add the line "Allow blue-purple: <reason>".
- **Character**: if a person or an anthropomorphic character has to appear in frame, read `references/art-motion/character-detail.md` first. With image generation available, generate frames with AI and write "frame library <path>"; without it write "hands and back only" or "none", and tell the story with hands, a back, a silhouette, an object. Code-drawn chibi figures, white-shell robots, coins and little balls that grew a face are retired.

Five requirements — check each one after writing:

1. **The first 3 seconds are one concrete small scene, and the ending lands on an action of the protagonist or the main object**: the opening is a person or a thing doing something related to the topic, not a title, not "today we're going to talk about"; the ending is an action such as slipping it into a pocket, closing a book, pulling back to see the whole — text may sit on an object inside the picture, and you do not close on a centred quote card.
2. **One example carries the whole film and one style runs all the way**: the same slice of bread, the same two hands, the same machine from first to last, and every shot tells what happened to it; every shot sits inside the style written on the style line.
3. **One shot is 2–6 seconds**: an individual shot may run to 8 seconds.
4. **Text-led shots ≤30%**: a shot counts as text-led when the subject column is a title/word, the on-screen text is 7 characters or more, or the shot is built with y5 kinetic text.
5. **Two adjacent shots never share a composition**: this shot is a full-frame close-up, so the next becomes a lateral truck, another object, another shot scale. What changes is the composition and the camera move, not the style.

Two hard lines for the method column (step 3 of the track tier states them too): **a single parameterised clip holds at most 8 seconds** (the same .json totalling no more than 8 seconds across the table); **one film uses at most 2 clip grammars**, every spec writes the same `theme`, and the remaining shots are drawn with scenes on the same palette, or real footage at full frame.

## Check

```sh
uv run <skill>/scripts/art-motion/storyboard_lint.py <project>/shot-list.md --script <project>/script.txt   # add --script when there is a narration script
```

It returns red / amber / green per shot plus the fix, and exits non-zero on any red. On a red light, fix the shot list and re-run — **no writing code until the red lights are clear**. Amber is workable: write the reason for each one item by item into the delivery notes. What lint checks: whether the three lines above the table (style, palette, character) are written; whether the palette holds blue-purple values; whether the character line is code-drawn figures, whether the subject column names a robot, a figure or a stick figure while the character line is not a frame library, whether y4 is used without a frame library, whether coins or little balls were given a face; the subject column must not be empty, must not be pure layout vocabulary, must not be an empty picture (empty shot, flat colour, black frame); the action column must carry an action; on-screen text ≤8; neither the first shot nor the last may be text-led; text-led ≤30%; with `--script` given, the numbers in the on-screen text (percentages, years, numbers with units) must be findable in the script (the script writing "sixty percent" counts too); with a Tags column, more than 3 tags in one shot is amber; a single shot is 2–6 seconds (6–8 seconds amber, over 8 seconds red); three consecutive shots with the same camera move is amber (Stop and Lateral truck do not count), three consecutive push-ins is amber, fast push-in / slam-in / whip on more than one third of the shots is amber; the same clip totalling over 8 seconds in the method column, or more than 2 clip grammars, is red. "One example throughout", "every shot really is the same style" and "adjacent compositions differ" cannot be checked by a machine — check them yourself.

## Example: why bread goes moldy (54 seconds, landscape)

This is a writing demonstration: do not carry the subject, the objects or the shot order into your film. What carries the whole film is the same bag of sliced bread and the two hands of its owner, Xiaoman; the face never enters the frame.

Style: Warm wood-toned paper illustration, flat fills with fine pencil lines, every shot under the same slab of afternoon kitchen side-light
Palette: wood
Character: Hands only (Xiaoman's hands, no face)

| Time | Subject | Action | Camera | On-screen text | Method |
|---|---|---|---|---|---|
| 0–3 | Xiaoman's hand and a bag of sliced bread | The hand tears the bag open, a fingertip stops on a blue-green speck | Stop | | scenes/kitchen.js |
| 3–6 | That green patch | A ring of white fuzz around the patch's edge spreads outward like a map | Slow push-in | Not there three days ago | Footage moldy-bread photo, full frame |
| 6–10 | A single spore | The spore drifts in through the window gap, tumbling, and lands on the bread | Lateral truck | Spore | scenes/spore.js |
| 10–14 | That spore | The spore shell cracks open and a white thread pushes into the bread | Fast push-in | | scenes/spore.js |
| 14–18 | The air holes in the bread's cut face | The white thread forks along the air holes, boring down like tree roots | Pull back | Hyphae | scenes/hyphae.js |
| 18–22 | The starch grains inside the bread | The hypha tip sprays enzymes and snips the starch grains into grains of sugar | Slow push-in | Starch→sugar | scenes/hyphae.js |
| 22–26 | The thermometer-hygrometer on the kitchen wall | The needle slides from 15°C to 28°C, water beads condense on the bag's inner wall | Cut | 28°C | scenes/kitchen.js |
| 26–31 | The two mold-area curves | The counter-top one charges upward, the fridge one crawls along the bottom | Stop | Much slower in the fridge | t3 clip shot08.json |
| 31–35 | The little stalks on the mold surface | Stalk after stalk lifts a black spore ball, and the ball bursts with a bang | Slam in | | scenes/hyphae.js |
| 35–39 | A cloud of spores | The spore cloud drifts across the tabletop and settles on the bag of steamed buns beside it | Lateral truck | Next stop | scenes/spore.js |
| 39–43 | Xiaoman's hand and the bread knife | The tip measures against the corner with the green patch — cut it off and eat the rest? | Stop | Just cut it off? | scenes/kitchen.js |
| 43–47 | The cut face of the sliced bread | An X-ray peels it open layer by layer: the invisible hyphae have long since filled half the slice | Fast push-in | The part you can't see | scenes/hyphae.js |
| 47–51 | Xiaoman's hand and the bin | The hand drops the whole bag of sliced bread in and snaps the lid shut | Cut | | scenes/kitchen.js |
| 51–54 | Xiaoman's hand and a fresh bag of sliced bread | The hand pushes the new loaf into the freezer; the door shuts and frost slowly creeps up the bag | Pull back | Cold, dry, sealed | scenes/kitchen.js |

Why this table passes: one style and one palette are locked above the table, and the person shows only hands; the opening is a pair of hands tearing a bag open and finding the mold, not a title; the ending returns to the same two hands, pushing a fresh loaf into the freezer, with three words written on an object in the picture rather than on a quote card; the same bag of sliced bread runs from first to last; none of the 14 shots is text-led; the only parameterised clip is the t3 curve in shot 8, whose spec writes `"theme": "wood"`, the same palette as the scenes; the camera follows "where should the audience look at this moment": slow push-in when a detail has to be read clearly (the green patch, the starch grains), lateral truck when following something that moves (the spore, the spore cloud), pull back when the whole has to be seen (hyphae boring down, the freezer door closing at the end), and stop when the picture is moving on its own (the curve growing, the knife tip measuring); fast push-in and slam-in are used three times only, kept for the three "so that's how it works" moments — the spore shell cracking, the spore ball bursting, the cut face opening up. After a push-in the film comes back out with pull back, lateral truck, stop or a hard cut, so there are never three push-ins in a row. Shot 8's curve is schematic; mark it "illustrative data" in the finished film.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
