# Stickman visual asset prompts — the universal rules

Path: both
Owner: the prompt set that an image model is asked to draw — coverage, continuity, camera, prohibitions

Absorbed for its **style-independent mechanisms** from a "Stickman Visuals" prompt-engineer spec. That
document bundles two different things: rules that stay true whatever the picture looks like, and one specific
art direction (flat fills, pure white heads, muted palette). Only the first kind lives here. The second kind is
a **style profile** — pick one per film, in the brief, and never inherit it silently.

Related: `generated-assets.md` (cropping and mounting the result), `design-taste.md` (palette owner),
`style-references.md` (resolving a named reference), `verification.md` (gates).

## 1 · Coverage: the set every film needs

Whatever the shot count, an asset set is incomplete without these three kinds of plate:

| kind | job | failure if missing |
|---|---|---|
| **main beat** | the moment the film exists for; a clear action, readable in one glance | the film has no centre |
| **supporting beats** | the development before and the consequence after | the film is a single idea repeated |
| **one environment-only plate** | establishes place, period, scale; **no figures in it** | the world reads as a backdrop painted behind the characters |
| **one object/detail insert** | the artefact the story turns on, framed tight; **no figures in it** | the audience never gets close enough to the thing that matters |

The count follows the film, not a magic number. A 20-second piece is well served by 5–7; a nine-minute film
needs one per beat plus its establishing and detail plates. What does **not** scale is the rule that the two
figure-free plates exist.

Why this is universal: it is about **coverage**, not style. It is also the specific thing three consecutive
samples here got wrong — every one of them stayed in a single lateral stage for its whole runtime.

## 2 · Every prompt must be self-contained

An image model has no memory of the last prompt. So:

- **never write** "same character as before", "same style as the previous image", "continue the scene",
  "refer to the earlier prompt", "as we established"
- **restate** the important visual facts in every prompt: head shape and fill, limb treatment, the clothing
  colours, the one accessory, the palette, the light, the period

A character's description is short enough to repeat: shape of head, fill colour, line treatment, two
garments and their colours, one accessory. Repeat it verbatim — that repetition *is* the continuity system.

## 3 · Camera must be specified, and must not repeat

Every prompt states: **shot size**, **camera angle**, **subject placement**, **framing**, **what is in focus**.
Descriptive cinematography language only — no platform-specific camera commands.

Shot sizes: extreme wide · wide · medium-wide · medium · medium close-up · close-up · extreme close-up.
Angles: eye level · low · high · overhead · three-quarter · side profile · over-the-shoulder · from behind.

No two neighbouring plates may share the same shot size, and a set should use at least four different sizes.
A film whose plates are all "medium, eye level" is a slideshow with different drawings.

## 4 · Lighting is a mood instruction, not a physics request

Name the light and where it comes from — soft window light, overcast daylight, warm practical lamp, low sun —
and say what that does to the mood. Do not ask for ray tracing, caustics, volumetric fog or photoreal bounce:
those requests pull an illustration model toward realism, which is the one thing that breaks a stylised film.

## 5 · Prohibitions are part of the prompt, and belong to the profile

Every style profile carries a **negative list** — what must not appear. The mechanism is universal; the items
are not. A flat vector profile prohibits painterly shading and gradients; a textured profile prohibits flat
fills and sterile geometry. Write the list once per profile and paste it into every prompt of that film.

A prompt without a prohibition list drifts toward the model's default taste, which is photorealism.

## 6 · Text inside a plate is a liability

- keep it to a short label or a single number, and **write the exact wording**
- prefer a symbol, an arrow or a diagram over a sentence
- never ask for a code listing unless the listing is the subject
- never let a plate carry a caption — captions are drawn by the film, not baked into art

## 7 · Facts are stated, not decorated

For documentary subjects: correct dates, correct names, chronological order, period-appropriate objects and
architecture. Distinguish **documented** events from **illustrative reconstruction**, and never present an
imagined meeting or line of dialogue as documented. If a detail is uncertain, choose the neutral visual — an
empty room, a machine, a diagram — instead of inventing a precise claim.

## 8 · No vague adjectives

"Beautiful", "cinematic", "stunning", "high quality", "use the same style" carry no instruction. Replace each
one with the feature that would produce it: *"a single figure centred in the lower third, two-thirds of the
frame left empty, cool wall against warm floor"*.

## 8b · Lock identity with an accepted frame, and check drift scene to scene

Two rules that a production log added to the prompt discipline above:

- **Use one accepted frame as the identity reference.** After the first plate of a character is approved, keep
  that file and pass it as an image reference for every later plate of the same character, alongside the
  verbatim text block. Text alone drifts; a reference frame does not.
- **Check style drift between scenes, not only frame quality.** A set can pass frame by frame and still fail,
  because scene 6 quietly goes flatter than scenes 1–5, or one close-up makes a face more realistic than the
  rest. Put the plates side by side at the end and ask *"is any one of these from a different film?"* — the
  honest answer is usually the last one you generated, which is where the drift enters.

## 9 · The profile slot — what is deliberately NOT universal

These are style decisions. They belong in a named profile in the brief and must never leak into the rules:

- head fill and outline (pure white with a thin black outline is **one** choice, not the law)
- limb treatment (uniform black stick-lines vs tapered strokes with hands)
- palette (muted beige/blue/green is **one** profile; a saturated warm set is another)
- background density (minimal geometric vs layered and lived-in)
- whether accessories, hair, glasses or hats are allowed — they are what makes two stick figures tell apart
  at a glance, so a profile that forbids them must say how identity is carried instead
- shading and texture (flat fills vs gradients, glow and grain)

Two profiles are in use here and both are valid:

| profile | looks like | prohibitions |
|---|---|---|
| `flat-minimal` | solid fills, crisp edges, uniform line weight, muted palette, generous negative space | gradients, painterly shading, texture, brush strokes, photorealism |
| `lively-textured` | layered set with light pools, warm/cool contrast, practical glow, props with silhouette | flat sterile fills, uniform grey, empty backgrounds, missing shadow direction |
| `modern-story` | **big-head stick characters on finely illustrated painted backgrounds**, one night-blue base with a warm practical lamp, cinematic suspense that can turn warm | flat fills on the characters, sterile backgrounds, cartoon-flat lighting, missing shadow direction |

`modern-story` is the profile for horror and emotional narrative: the character stays a big round head on
simple limbs, while the *set* is painted in detail. The contrast between the two is the style — do not
"upgrade" the character to match the background, and do not flatten the background to match the character.

Pick one in the brief, write it in `DESIGN.md`, and do not mix them inside a film.

## 10 · Gate the prompt set before you spend a generation on it

`scripts/asset_prompt_audit.py` checks a written prompt set against §1–§4 and §8:

```bash
python scripts/asset_prompt_audit.py prompts.md --count 7
```

A worked example of a compliant set (7 plates, MotoGP): `assets/examples/asset-prompt-set-motogp.md`.

It fails on: a missing establishing or detail plate, a cross-reference phrase, a prompt with no camera line or
no shot size, two neighbouring plates with the same shot size, a character prompt that does not restate head
and limb treatment, a vague adjective, or a missing style/prohibition line. Run it before generating, and again
after any edit — a prompt set is cheap to fix and expensive to discover in the render.
