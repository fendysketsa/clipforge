# 03 · One frame first, then let it move: four routes

When image generation or character images are involved, first use the [image capability guide](images.md) to pick the tool currently available or import existing assets; private character assets and platform choices are not defaults for all users.

The method the author wants: one frame first — design one frame that is artistically right, then make that frame move as required. On 2026-10-04 all four routes were actually run on one project; each has its own use case.

| Route | Who draws the picture | Who does the motion | Actual test | When to choose |
|---|---|---|---|---|
| **A pure code** | Canvas procedural drawing + style renderer | Code (choreography curves, IK, particles, boiling lines) | Art-history reproduction mainline (chosen by the author) | You must prove "the model produces artistic animation directly from code"; you need precise control over every element's motion; you need dozens of styles (swap the renderer, swap the style); you need frame-accurate alignment with the voiceover |
| **B AI layered assets + code motion** | Image model draws by layer (green screen, original frame coordinates preserved) | Code (translation, arcs, squash, physics, FX) | 2026 finale segment: 11 assets composited in one pass | You need the highest image quality and complex character performance; the art direction is realistic/illustration and code cannot draw it |
| **C video model first/last frames** | Image model draws one frame | Seedance first/last frame (same image at both ends) | Lovart Seedance 2.0 Van Gogh test: girl sets the cup down then lifts it again, starry sky turns, cat flicks its tail, composition holds throughout | You want the organic feel of "the whole painting flowing" without precise control; example/atmosphere shots |
| **D hybrid** | Background via B/C, characters via A, or the reverse | Code orchestrates the timeline uniformly | — | Big productions: background needs texture, characters need to be controllable |

## The common first step: one key-frame design still

Whichever route you take, start with one "correct frame":
- **With a reference film**: feed the "last frame before the transition starts" of that segment in the reference film to gpt-image as the reference image, and write the prompt as "keep the composition, camera, position and size of every object, palette, and brushwork of the reference image exactly; change only two things: ...". Measured against the original, a 50% overlay is nearly pixel-identical — composition is locked by the reference image, not by coordinates written in text.
- **Without a reference film**: design the composition per subject first (what the subject is, where in the frame, where the camera travels), and export a blockout screenshot as the reference image. Only speedrun/time-travel films fix a scene skeleton (standard composition coordinates) up front, with every segment aligned to it.
- **Three-direction gate**: character interpretation (this film: period women's clothing / the same person time-travelling / original head swapped onto a body) — produce three versions on the same frame for the author to pick. Pick the frame where the original character is male; that pulls the difference widest.

Pitfalls of the design still (all of them hit in practice):
- Writing an underage character (17 years old) plus any occurrence of "short skirt" gets the whole image rejected as sexual by moderation. Always describe clothing as long-cut, and add "modest clothing".
- Write coat color down to body parts: "orange-and-white cat (orange tabby on head, back, and tail; white muzzle, chest, belly, and all four paws)". Writing only "orange cat" produces an all-orange body.
- Writing an action into the description ("holding a cup, drinking tea") overrides the reference image's pose. To keep the original pose, write only "keep the hand gesture from the reference image".
- For text that must animate (years, titles), tell the model to "remove it, leave a clean background" and let code draw it; decorative text inside the picture must be spelled out character by character in the prompt.
- Run batch generation serially; base generation provenance on the actual tool-call record, input/output linkage, and human visual checking; PNG metadata cannot prove which model generated a file. For asset integration see the [image capability guide](images.md).

## Route B's key: green-screen assets keep the original frame coordinates

Use the design frame as the reference image, prompt: "draw only the XX in the reference image... everything else is flat #00FF00, no shadow, ground, or text. Position, size, and orientation exactly match the reference image." The generated character already stands at the original frame coordinates. When keying, **do not crop to the subject's bounding box and throw the coordinates away** — `scripts/art-motion/key_green.py` crops the edge and writes the top-left corner into sprites.json at the same time, so compositing pastes it back at the original coordinates and aligns in one pass.

## Route C's key: same first and last frame

Seedance 2.5/2.0 supports frames2video. Give the first and last frame the same design still → things inside the picture move and return to the original composition, so the clip's head and tail splice seamlessly into transitions. Prompt structure: ① camera completely locked (no push, pull, pan, tilt, zoom, or shake) ② hold composition/art direction/palette throughout — no photorealism, no adding or removing objects, no new text ③ list item by item "what moves in the picture and how it moves" (from the breakdown's motion list). Generate 5 seconds, take the best ~1 second, and retime it to the rhythm.
Channel: any Seedance integration that supports first/last frames (frames2video) works; the point is the prompt itself. Video generation is billed per call — test one short clip first.

## Route A's key

See `04-pure-code-painting.md`. One sentence (speedrun/time-travel films): one scene skeleton × shared choreography × one renderer per style × characters on their own layer drawn afterwards × line pass last. For other subjects, replace the first two items with composition and action designed per subject.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
