# 10 · Characters: AI-generated frames for people, code for compositing

When image generation or character images are involved, first use the [image capability guide](images.md) to pick the tool currently available or import existing assets; private character assets and platform choices are not defaults for all users.

## Choosing how to implement characters

The same character can be implemented three ways (side-by-side of A and B in `assets/character/author-portrait_compare.jpg`; the effect of C in the Kurzgesagt and whiteboard demo films):
- **A code-drawn**: only for motion blockouts, previz, and purely geometric symbols (blocks, terminals — things that are geometric to begin with). Do not code-draw people, anthropomorphic characters, robots, or objects with faces into a finished film; see `references/art-motion/character-detail.md`.
- **B paste a pre-approved frame library directly**: easy to keep the character consistent, but you must reconcile the frame library's art style with the scene's.
- **C generate action frames in the film's art style, then composite**: use reference images to hold identity, key out the green screen, then let code control motion and material.

Live-action and anthropomorphic characters use only B or C, and must clear the delivery line in `references/art-motion/character-detail.md`; without image generation, deliver only hands and backs, or no people. The style cards record the known weaknesses of each character type.

## B: pasting a pre-approved frame library

- Frame library: character frames you have already finalized (waving, dragging, etc.; 8 transparent PNGs per action; generic action frames you prepare yourself; the three character frame sets bundled with the long-scroll demo are in `scripts/art-motion/engine/demos/long_scroll/frames/`).
- Loaded as an image asset at engine start; rendering swaps frames via `floor(t*9)%8` — limited animation, no tweening.
- Placed with the bottom-center of the feet as the anchor; `face=-1` flips horizontally.
- Apply the film's material to the frames (Vox: add a white cut-paper edge and a drop shadow; brush-stroke styles can run a layer of fine strokes over the frames with source-atop).

Extension of B: when one set of frames must go through many art styles without regenerating, hand the frame to the painting engine as a region of the scene to be repainted (remap colors by luminance, then blend a little of the original frame back on top to keep the face); the method and its limits are in section 6 of 18.

## C: generating a version in the art style

1. **Generate**: use an image model that supports reference images, such as gpt-image (for prompt patterns see [the author-gpt-image](https://github.com/Alucard0x1/pulupulu-motion)); run batches serially. ref = the character's three-view design sheet or the master of an approved frame library; write the prompt to state clearly:
   - the style's **form grammar** (not just "XX style"): Kurzgesagt flat color blocks with no outline and shadows one step darker in the same hue; Vox black-and-white halftone newsprint photos with a white cut-paper edge; whiteboard black marker line art with orange hatching; Monet short strokes of light patches...
   - **pose and camera blocking aligned** ("profile facing right, arm extended, pointing right"); if it must move, generate a multi-frame sprite in one image (4×2, eight frames; put the frame count at the start, lock "the same character" for consistency, give only key poses and let the model fill the in-betweens, "each frame standing bottom-center in its cell, same size").
   - green screen `#00B140` (a white hat and white T-shirt cannot use a white background).
   - fixed specs (using the author's persona as the example): **pure white** bucket hat (the model likes to paint it light gray — pin it down), round black glasses, white T-shirt, khaki shorts, white clogs, black watch on the left wrist, big head, small body.
2. **Verify provenance**: base it on the actual tool-call record, input/output linkage, and human visual checking; PNG metadata cannot prove which model generated a file. For asset integration see the [image capability guide](images.md).
3. **Key and split frames**: `scripts/art-motion/key_split.py` (removes green spill, splits poses by column; for whiteboard line art use `--white` to crop only without keying, then composite with multiply); use `scripts/art-motion/key_green.py` when you need to keep the original frame coordinates.
4. **Composite**: code decides only position, size, orientation, frame-swap timing, and material; interactive objects such as pebbles, ripples, and props are still drawn by code and aligned to the hand position.

## When code drawing is still used

In finished films: silhouettes, backs, hands (drawn properly in the film's art style), and things that are geometric anyway (blocks, terminal windows). Robots, chibi figures, stick figures telling a story, and giving objects faces are retired — see `references/art-motion/character-detail.md` for the reasoning and the replacements. `scripts/art-motion/engine/lib/rig.js`'s girl/cat rigs, `rig_legacy.js`, and `scripts/art-motion/engine/lib/toon.js` stay: for motion reference (where the hand and feet are, to anchor AI frames), blockout previz, and characters already finalized in style demos such as the art-history speedrun.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
