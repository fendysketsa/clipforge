# 52_south_park · South Park: Digital Cut-Out and Limited Performance

Status: research recipe; the demo was rebuilt on 2026-10-16 under protocol 16 (see "v2 Production Run" at the end of this card); neither the self-assessment nor the independent review reached 80, so it is not registered as a production run.

## Check First

Read [Cross-Scene Style Extraction](../15-style-transfer.md) first, then this card. The works are used to compare visual language; figures, objects, composition, and camera are not lifted directly. The stable features below are research generalisations; the implementation and transfer plan are hypotheses awaiting verification; official parameters or already-measured capabilities must not be claimed falsely.

## Scope

Study the series' principal digital cut-out visual and performance language; the realistic, anime and other drawing styles of special episodes are not the default. The official 2013 FAQ documents the digital cut-out reconstruction route; do not use it to claim the current software version.

## Transferable Visual Language

- Form: geometric, clear large silhouettes with a few key facial features; new characters have their own proportions and costume identifiers.
- Material: flat paper layers, restrained texture and occlusion; this does not automatically upgrade to smooth 3D or thick paper sculpture.
- Space: the background gives the action a place and contact points; characters and props share the flat scale.
- Performance: mouth shapes, eye direction, pose switches and pauses carry the information; limited animation does not mean the characters slide around like puppets the whole time.

## Content That Varies by Brief

Do not copy the four leads, the snow town, the school bus or the dialogue; studying the visuals does not mean offensive gags must be included.

## Distinction from Adjacent Styles

Distinct from Rick & Morty's fine outlines and more flexible linear characters; distinct from shadow puppetry's light-transmitting material and rod-driven joints.

## Production Starting Point (To Be Verified)

When this style is explicitly chosen, the shot table writes `Style: 52_south_park South Park-style digital cut-out` and `Characters: original semantic SVG paper-cutout characters`; original semantic SVG paper-cutout characters may be used, organised by part/pivot/expression state; this is a narrow exception for flat styles and does not extend to live action or other styles. Paper grain is bound to part coordinates; footsteps and contacts have states, not just whole-group translation. When generated frames are needed, route 10 still applies.

Action speed, frame rate, camera, and score are set by this narrative; a quiet mood in the image is not the same thing as slow motion. Engineering integration follows the [Style Author Spec](../08-style-author-spec.md); an engine id is registered only after a new renderer has actually been built.

## Cross-Scene Test Prompts (Not a Fixed Template)

- A newly designed adult property manager discusses a leak.
- A vending machine jams with no characters: limited performance must still read.
- Fast action of a multi-person evacuation: tests whether the constrained shapes stay readable.

Pick tests with different subjects / spatial scales / subject types; running the full set every time is not required. Record still-frame and motion acceptance separately; keep uncovered ranges marked as to be verified.

## References and Evidence Boundaries

- [South Park Studios: official FAQ on the digital cut-out reconstruction](https://southpark.cc.com/news/712d55/faq-do-you-still-use-construction-paper-to-animate-the-show)
- [Official episode portal: clips for comparing different locations and actions chosen at production time](https://southpark.cc.com/)

Primary museum / production material is used to check works and methods; encyclopedia entries only help with locating. Starting work still requires actually looking side by side at several original works or clips of different scenes and recording stable features and exceptions; a work list does not mean a multi-image visual experiment has been completed.

## Feedback After Use

Check this section's latest verified conclusions before use; what exists now is a technical check of a 6-second single-scene output; style fidelity and cross-scene visual verification are unfinished. Afterwards record only findings that affect results: date, subject, route taken, reference and output paths / hashes, problem, fix, verification status, and scope. Rewrite an invalid conclusion in place; do not append contradictory rules. Upgrade a research hypothesis to a production recipe only after it reproduces across scenes; for repeatable engineering problems, fix the tool first and test it. User preferences go into the taste profile separately and do not widen authorisation.


### 2026-10-15 · Single-Scene Trial Feedback

- Scene: launderette mishap; event: an original adult character presses a button, a sock flies out, a startled reaction; route: code drawing and animation.
- Check: deterministic re-run test, full MP4 decode and independent frame-sampled review; short-film fast-motion metrics were downgraded to yellow under the existing gate and cannot be used to infer feature-length compliance.
- Boundary: this only proves the project runs and is watchable; similarity to the artist's/studio's style is still limited, and geometry, palette or texture parameters must not be treated as the final standard.

## v2 Production Run (2026-10-16, self-score ~75, taste items pending author)

- Signatures: cut-paper feel (jittered edges, paper fibre), two white ellipses stuck on the face for eyes plus black dots, trapezoid body, short black post legs, flat fill + thin black outline, whole-block translation / pivot rotation.
- Route: `scenes/52_south_park.js`. Every shape is cut with `P.cut` to give it jittered edges; `kid()` animates around a neck/shoulder pivot; the mouth is a black half-ellipse opening and closing; falling snow steps at 12fps. Subject changed to a bus stop: the school bus slides in, the door snaps open, the children queue and hop aboard. Clothing colours avoid the combinations of the named characters.
- Measured: qa determinism ✓, no jumps, 6ms/frame, motion 5.3%.
- Still improvable: the children come out of one mould; boarding is just translation plus a hop; mouth shapes paired with dialogue are missing.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../../SKILL.md) · [Art library index](../INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
