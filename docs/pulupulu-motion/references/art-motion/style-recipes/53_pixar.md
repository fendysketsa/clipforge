# 53_pixar · Pixar: A Style Family of Form, Material and Performance

Status: research recipe + single-scene engineering trial; established and produced 2026-10-15. Ships with `scenes/53_pixar.js`, run with `render.py --film style_studies --solo 53_pixar --from 0 --to 6`; it has not yet passed style fidelity or cross-scenario verification, so it cannot be upgraded to a mature style on that basis.

## Check First

Read [Cross-Scene Style Extraction](../15-style-transfer.md) first, then this card. The works are used to compare visual language; figures, objects, composition, and camera are not lifted directly. The stable features below are research generalisations; the implementation and transfer plan are hypotheses awaiting verification; official parameters or already-measured capabilities must not be claimed falsely.

## Scope

Pixar is not a single style. First pick one film-level art scope for the brief; the graphic, painterly feel of *Luca*, the realistic New York and abstract soul world of *Soul*, and so on cannot be fused into one without saying so.

## Transferable Visual Language

- Form: design a recognisable silhouette and size relationships first, then surface detail; big eyes, round faces and glossy plastic are not the universal definition.
- Material: materials carry story and character; cloth, skin, metal and so on must be differentiated; reflections do not override the art direction.
- Light and colour: light guides narrative focus and physical laws may be stylised; it is not a fixed golden rim light or blue-purple background.
- Performance: pose, centre of gravity, gaze and anticipation/follow-through are continuous; emotion comes from causal action, not from randomly swapping expression textures.

## Content That Varies by Brief

Do not default to giving every object a face or applying the same cute face everywhere; do not copy existing characters or force the use of Pixar software.

## Distinction from Adjacent Styles

Distinct from the early ray-traced CGI card's uniform plastic and reflecting spheres; this card designs form, varied materials and performance together. Boundaries between individual films must also be made explicit.

## Production Starting Point (To Be Verified)

Scenes of faceless objects may use 3D modelling with physics/keyframes; characters and anthropomorphic roles currently follow route 10's frame-library/compositing route. Full 3D character modelling and rigging is still a capability to be built; it must not bypass the entry's character rules or claim support that does not exist; a branch may be called valid only after picture verification. Purely code-based requirements must not be faked with a simple ball-and-cylinder person or a single AI background; expose the modelling, rigging and lighting gaps first.

Action speed, frame rate, camera, and score are set by this narrative; a quiet mood in the image is not the same thing as slow motion. Engineering integration follows the [Style Author Spec](../08-style-author-spec.md); an engine id is registered only after a new renderer has actually been built.

## Cross-Scene Test Prompts (Not a Fixed Template)

- An original adult repair technician tracing a machine fault.
- An unbalanced washing machine in an unattended launderette: an event happens with no added face.
- A newly designed animal character carrying things on a slick floor: check volume, contact and material.

Pick tests with different subjects / spatial scales / subject types; running the full set every time is not required. Record still-frame and motion acceptance separately; keep uncovered ranges marked as to be verified.

## References and Evidence Boundaries

- [Pixar RenderMan: stylisation running through form, material, light and effects](https://prod.renderman.pixar.com/stories/stylization-at-pixar)
- [Pixar's *Luca*: film-level art scope](https://www.pixar.com/luca)
- [Pixar's *Soul*: the realistic-environment branch](https://www.pixar.com/soul)
- [Pixar RenderMan: cinematography, materials and light in *Soul*](https://renderman.pixar.com/stories/cinematography-with-soul)

Primary museum / production material is used to check works and methods; encyclopedia entries only help with locating. Starting work still requires actually looking side by side at several original works or clips of different scenes and recording stable features and exceptions; a work list does not mean a multi-image visual experiment has been completed.

## Feedback After Use

Check this section's latest verified conclusions before use; what exists now is a technical check of a 6-second single-scene output; style fidelity and cross-scene visual verification are unfinished. Afterwards record only findings that affect results: date, subject, route taken, reference and output paths / hashes, problem, fix, verification status, and scope. Rewrite an invalid conclusion in place; do not append contradictory rules. Upgrade a research hypothesis to a production recipe only after it reproduces across scenes; for repeatable engineering problems, fix the tool first and test it. User preferences go into the taste profile separately and do not widen authorisation.


### 2026-10-15 · Single-Scene Trial Feedback

- Scene: faceless washing machine; event: the drum jams, the body shakes, cloth drops to the floor after the door opens; route: procedural 3D.
- Check: deterministic re-run test, full MP4 decode and independent frame-sampled review; short-film fast-motion metrics were downgraded to yellow under the existing gate and cannot be used to infer feature-length compliance.
- Boundary: this only proves the project runs and is watchable; similarity to the artist's/studio's style is still limited, and geometry, palette or texture parameters must not be treated as the final standard.
- Actual fix: the door opens before the cloth is released, and the cloth endpoints are constrained to the tile height; independent review closed out the original timing and ground-contact issues. This is a parsed mesh, not physical cloth simulation.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
