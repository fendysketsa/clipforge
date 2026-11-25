# 02 · Mechanism: why "art history speedrun" looks good

This page covers the mechanism of "speedrun/time-travel" films: one scene, switching style or era (art-history speedrun, 100 years of one city, one person from eighteen to eighty). Every subject like this can be built on these five layers; explainer films, narrative films and single-style shorts are not built this way — design their composition per subject.

## The five-layer mechanism

**1. One fixed scene skeleton.** Across 16 eras, the positions of the window, table, cat, person and year plaque barely move (±40px). The viewer's eye needs an anchor before it can see clearly that what changes is the style. Because the positions are fixed, transitions can also use in-frame objects as their origin (the mosaic spreads from the cat's position, the iris opens from the cup).
→ How (speedrun/time-travel only): fix this film's composition coordinates first and align every era to them. In code that is one set of constants, not each segment drawing its own. Other subject matter does not inherit this room's coordinates.

**2. Every era is a living painting.** It holds for 0.25–1.4 seconds, but the picture keeps moving: one continuous action for the protagonist (raising the cup and drinking) + 2–4 small loops **taken from that era's own visual motifs** — cave-painting animals run on "two alternating poses" (which is the animation of the multi-legged running convention in cave art), the Egyptian scarab pushes the sun, the Greek meander band scrolls, Vesuvius smokes, Gothic gold foil glints, the Renaissance ornithopter flaps, the ukiyo-e great wave, Van Gogh's starry sky swirls, the Bauhaus dial turns, the Pop four-panel changes color.
→ How: for each segment, list "the three most identifiable formal elements of this era" and set them in motion. The motion must be visible inside the hold window (short segments need a fast rhythm).

**3. Transition = the next era's signature language.** Entering Egypt is stone blocks/tapestry dropping, entering Greece is a pottery roller turning the face, entering Rome is mosaic tesserae flipping, entering the Gothic is a parchment page turn, entering the Renaissance is divine light, entering ukiyo-e is the Kanagawa wave sweeping across, entering Impressionism is strokes and color dabs filling the frame, entering Van Gogh is the starry swirl, entering Art Nouveau is gilded organic forms growing, entering Cubism is geometric shards, entering Bauhaus is red/yellow/blue geometry rotating and scaling up, entering Pop is a lightning bolt + halftone dots, entering 8-bit is pixelation, entering ray tracing is a green wireframe → progressive render, entering 2026 is a three-color concentric ring iris.
→ How: do not pick generic transitions off a library shelf — grow each one out of "the new style's most identifiable formal element". Add camera impact on the first frame of every transition (scene layer scales up to 1.03, back to 1.0 in about 20 frames; the year plaque does not scale) — that is where the kick on the downbeat comes from.

**4. Beat-grid acceleration.** 128 BPM stays constant while the number of eighth notes per segment decreases: 6 → 4×5 → 3×4 → 2×3 → 1×3 → the ending stretches to 9+. The tempo never changes, but it sounds and looks more and more urgent; the last segment is stretched to leave room for the punchline. Transition durations shrink with it (0.4s → 0.13s), and so does the year roll (0.55s → 0.07s).
→ How: list the duration you want per segment, round it to eighth notes, then nudge the whole thing into a regular descent. Every cut point, music onset and sound effect lands on the grid.

**5. One continuous narrative anchor + a closing character gag.** The year counter is the only continuous thing in the film: its value is determined solely by global time, and during a transition the old and new layers both display the same rolling number, each in its own typeface (hand-drawn cave script for 40,000 BC → reed pen for 1350 BC → … → geometric sans for 2026). The ending gives the characters a gag (the cat pats the cup three times and pushes it off the table, the girl gasps, the signature writes itself out) and performs it fully with anticipation, squash and stretch, follow-through and secondary action — the first 11 seconds are "watch", these 4 seconds are "laugh"; the laugh is what gets the film shared.

## Addendum (2026-10-04 migration test A–D)

- **The protagonist's action runs continuously across segments**: the narrative anchor is not only the counter — the protagonist's action also follows film-wide time; if each segment redoes the action, the audience sees "raising a cup five times" instead of "the same instant in five painting styles".
- **If the counter displays years, segments must be ordered by date**; if they cannot be reordered, swap the corner label for an index or the style name (the engine's corner label is pluggable). Hard-cut the old and new labels at the transition midpoint so text does not double-print.
- **When the first segment has no transition to borrow, let the picture "draw itself"** (strokes writing it out, color plates landing one at a time, pixels lighting up row by row).
- **The more complex the signature transition, the longer it must run**: the original film's shapes are simple, so 0.4s is enough; gold leaf, color bands and ribbons need 0.48–0.5s.

For how to make the drawing layer thick (splitting scene and drawing method into two work stages, drawing stroke by stroke, turning transitions into character actions) see 18; reference implementation `scripts/art-motion/engine/reference_films/painted_room/`.

## Adapting to other subject matter

| Layer | This film | As "100 years of one city" it could be |
|---|---|---|
| Skeleton | window/table/cat/person | The same street corner: street lamp, shop signs, pedestrians, skyline |
| Living painting | era motif loops | Vehicles of each decade driving past, sign lettering flickering, things in the sky (kite → plane → drone) |
| Transition | next era's signature language | The next decade's medium: film burn, TV static, pixels, scanlines |
| Beat | 128 BPM descent | Same |
| Anchor + gag | year counter + cat pats the cup | Year counter + the same pigeon stealing food in every decade |

## Where not to go wrong

- Do not treat "16 eras" as a quota. The mechanism of speedrun/time-travel is "the style changes, the skeleton does not" — 3 eras work just as well; it is not the mechanism for every subject.
- Do not reproduce the original film pixel for pixel. Reproduction is a means of learning the mechanism; the deliverable is your own understood version (the author chose a blonde girl + an orange-and-white cat, which is swapping the characters on the original's skeleton).

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
