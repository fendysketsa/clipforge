# Character detail: either draw it properly, or keep the face off-screen

Read this page before you start whenever a person, an anthropomorphic character, a mascot, a robot, or anything with a face appears on screen. The author has watched films made by several models; in his own words:

- "The little people and robots in a lot of these videos are just too bad — we should define some of the detail level and effort requirements ourselves."
- "The colors and the human style figures all have a bit of AI slop to them." "The gold coin and the little figure interface has a bit of AI slop to them."

**A crude character is worse than no character.** The moment an audience sees a little figure with a round head and bean eyes, their first reaction is "an AI made this," and no matter how good the rest of the story is, that one glance drags it down.

## Choose the route first: three general routes plus one narrow exception for two flat-cartoon cards

The "Character" row ahead of the shot table states which one you picked here:

| What the character row says | When to take it | How to do it |
|---|---|---|
| `frame library <path>` | You have image-generation capability (the current session has an image-generation tool, or the user supplied character images) | Build an AI-generated frame library by method B/C in `references/art-motion/10-characters.md`, and pass the "delivery line" below |
| `hands and back only` | No image-generation capability, but the story needs a person | Draw only hands (holding an object, pointing at an object, putting an object into a pocket), backs, silhouettes, over-the-shoulder shots; the face never enters frame |
| `none` | The story can be told by objects alone | Make the object itself the protagonist: a battery, a bag of bread, a book — tell it through shape, color and motion; do not give it a face |

**Flat-cartoon exception, cards 37/52.** When you explicitly choose the Rick & Morty or South Park direction, you may design original semantic SVG characters in that card's style. Write `style：37_rick_morty …` or `style：52_south_park …` in the shot table and write `character：original-semanticSVG …` for the character. This is an exception to the method, not an exemption from inspection: check silhouette, identity, part hierarchy, contact, expression and motion; judge flat fills and simplified joints by that style's standard, and do not impose the realistic structure, two-layer shading and three material details of rules 2/4/5 below. It does not apply to live-action/realistic or any other style; writing merely "SVG" does not activate the exception. The South Park research card already has a single-scene prototype, but new characters and new subject matter still require fresh design and verification. `y4` still accepts only a frame library — the SVG exception cannot bypass its input contract.

**Retired** (drawn in code, these read as AI slop; lint and review both block them):

- The generic chibi figure: round head, bean eyes, blush, no neck, body is one rounded rectangle.
- The white-shell robot: white rounded shell, blue visor, one antenna, hovering or firing jets.
- Things that grew a face: a gold coin with a smiley, a lithium ion that frowns, a small ball with eyes, a battery with an emoji face.
- Stick figures and Harlem-shake figures used to act out a story (drawing a schematic symbol in whiteboard grammar does not count as acting out a story).

**Exception: the whole film's protagonist is an object character.** A paintbrush that jumps, a desk lamp, as the protagonist of the entire film — if it has been through the "three-direction hard gate" for its design, and the user has picked it, it may have a face and expressions: when the author made a promo, a faceless paintbrush was judged "too formal, too boring," and only a cartoon paintbrush with a face passed. The difference is in the effort: the protagonist is designed (identity prop, body structure, performance) and passes the delivery line below; what is retired is slapping an emoji face onto a coin, a ball, an ion as an afterthought.

`y4` clips accept only a frame library (`data.character.frames`); with no frame library the launch fails. Characters drawn in code inside the engine (`neutral`／`bun`／`author` in `scripts/art-motion/engine/lib/toon.js`) are no longer permitted in finished films.

## The delivery line: frame-library characters must pass these eight

When the character is made, first capture one close-up of it (scaled up to 2×), tick each item below against it, and write the result into the delivery notes. If it fails, go back to the image-generation step and redo it, or switch to "hands and back only."

1. **The silhouette is recognizable**: fill the character in solid black and you can still tell who it is and what action it is doing. A figure assembled from a circle plus a rounded rectangle is not recognizable.
2. **The proportions have a skeleton**: there is a neck, shoulders, elbows, wrists; head-to-body ratio is set by the style and stays constant for the same character across the whole film.
3. **Hands are hands**: you can see the shape of fingers or a glove, and they can really grip an object (the object is in the hand, not pasted beside it).
4. **At least two layers of light and shade**: base color plus shadow, plus a highlight or rim light; the light direction matches the scene.
5. **At least three material details**: cloth folds, stitching, hair strand groupings, fabric texture, shoelaces, watch strap… pick the ones this character should actually have.
6. **The performance is specific**: every appearance has one expression plus pose that matches this shot's content (frowning at a phone, then letting out a breath and stuffing the phone into a pocket) — not just blinking, not just bobbing up and down.
7. **Same system as the style**: the character's linework, coloring and palette are the same method as the background; it is not a sticker pasted onto someone else's drawing.
8. **Consistent throughout**: the same character's facial features, hairstyle, clothing and palette are consistent in every shot.

## No faces on objects: how to make an object "act"

Bringing a concept to life does not require drawing a face on it.

- **Use shape and motion**: a lithium ion huddles into a ball and moves slowly when cold; when it heats up it spreads out and runs fast. A battery bar shrinks one notch at a time in the cold wind.
- **Use scale**: something slams down from palm-size to filling the whole frame.
- **Use contrast**: two of the same object side by side, one frozen, one normal.
- **Use real objects**: a real battery cross-section, real frost texture, real screenshots.

## Self-check

Before delivery, pull 6 frames that contain a character or an object and look at them side by side. Ask three questions:

1. Is there anything that instantly reads as "the default AI little figure" or "the white-shell robot"? If so, change route.
2. Have you drawn a face on something that should not have one? If so, remove the face and tell it through motion instead.
3. Are the character and the background drawn the same way? If not, redo the character in the style, or let only hands appear.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
