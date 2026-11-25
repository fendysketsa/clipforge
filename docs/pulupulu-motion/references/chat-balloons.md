# Speech and thought balloons

Path: both
Owner: balloon text, balloon screen-space geometry, balloon clearance, balloon timing

Absorbed from `hmelberg/stick` (`js/bubbles.js`, `say`/`think` commands, `PROMPT.md`) and extended with
what that reference deliberately leaves out. Working implementation: `scripts/bubbles.py` — `Layout.layout()` returns settled positions,
`draw_balloon()` draws tail-then-body-then-text, `bubble_size()` measures a wrapped block.
`python scripts/bubbles.py --selftest` must print PASS before you trust a layout.

**This page owns balloons and nothing else.** It does not decide motion, acting or staging — for a character
performance that is `stickman-performance.md`; for narration captions it is `narration-and-captions.md`. If a
balloon page and a motion page ever disagree, the motion page wins on motion and this page wins on geometry.

## 1 · When a balloon exists at all

A balloon appears only when a character has an audible spoken line. It is not a caption: captions transcribe
narration for the viewer, balloons are speech that belongs to a figure on screen.

- one balloon per speaking figure; two at once **only** while overlapping speech is genuinely audible
- a thought balloon only during an interval you declared as a thinking beat — never as decoration
- no balloon over a character who is not speaking, and none during silence
- if the film already carries narration captions, reserve the caption plate as a forbidden rectangle and pass
  it into the solver as an obstacle (see §4)

## 2 · Safe area

Coordinates are for a 1080×1920 delivery; scale every number by `W / 1080`.

| zone | rect (x0, y0, x1, y1) | purpose |
|---|---|---|
| dialogue safe rect | `44, 140, 1036, 1720` | default: clears the frame edges and the bottom-right watermark |
| caption-compatible rect | `44, 140, 1036, 1520` | use when bottom captions are active (plate sits at y ≥ 1560) |
| platform-UI rect (Shorts/Reels) | `44, 220, 928, 1400` | top 220, bottom 520, right 14 % reserved for app UI |
| watermark exclusion (hard) | `760, 1830, 1080, 1920` | no balloon body or tail may enter it |

A balloon body must lie **strictly inside** the active rect. A tail may point outside the body but must not
enter the watermark exclusion or leave the frame.

## 3 · Anchor and tail

- **Desired centre**: the speaker's head x, biased slightly away from the partner
  (`cx_want = hx + outward × 0.45 × r`, `outward = -1` if the speaker is left of the partner, else `+1`).
- **Desired top**: above the head — `y_want = (hy − 1.35 r) − tail_gap − h`, with
  `tail_gap = clamp(0.55 r, 34, 58) px` (add 14 px for a thought cloud).
- **Edge selection**: `bottom` when the body clears `hy − 0.85 r`; `top` when it starts below `hy + 0.85 r`;
  otherwise `right` or `left` toward the head.
- **Base clamping**: keep the tail base `min(36 px, 0.28 × edge_len)` away from the rounded corners
  (`rx = 26 px`), base width `≈ 0.34 ×` the shorter edge side, minimum 26 px.
- **Tip**: stop at `1.22 r + 10 px` from the head centre (minimum tail length 16 px). The tip must be
  unambiguously nearer its own speaker than any other head.
- **Draw order, two passes**: all tails and thought puffs first, then all bodies with a base seam cover, then
  all text. A tail can therefore never cross another balloon's text.

## 4 · Collision solver

Inputs: active balloons sorted by `(speech_start, priority)` — the earlier speaker keeps its spot — every
head on screen (including the speaker's own), and the safe rect.

Constants for 1080 wide: `GAP 18`, `MARGIN 44`, `EPS 1`, `SOFT 28`, `MAX_PASSES 8`, `TAIL_GAP 46`.

`TAIL_GAP` is ours, not the reference's: a head is treated as an obstacle **46 px taller on top** when a
balloon is heading for the space above it. Without that padding the solver settles the balloon close enough
that the tail collapses into a 16 px stub — measured, not theoretical.

A hit is "closer than GAP", not "overlapping" — horizontal separation under 18 px counts.

Per hit, in order:

1. **Lift over** — if `ob.y0 − GAP − EPS − h ≥ safe.y0`, raise the balloon toward that line.
2. **Slide beside** — try the speaker's own outward side first, then the opposite: `fit(ob.cx ± (ob.w/2 + w/2 + GAP + EPS))`.
3. **Below the chin** — heads only, in an extreme close-up, only when the result clears every head.
4. **Face-safety guard** — the push is alpha-weighted and eased, so the *drawn* position can end up closer
   than the *settled* one it collided on. If the eased rect touches a head while the settled rect is clear,
   **draw the settled rect.** This is the one place we deliberately diverge from the reference, which draws
   the eased position and can leave a balloon on a face.
5. **Compact reflow** — re-wrap the text at `0.78 × w` (down to a 34 px font floor, max 3 lines) and re-run.

**The speaker's own head is an obstacle.** The reference exempts it; we do not, because the hat and hairline
are part of the character. `bubbles.py` enforces both this and the guard in step 4, and its self-test fails if
either regresses.

## 5 · Timing

- **Source of truth**: measured speech onset/offset from `timeline.json` (`dialogue_voices.py`). Never a timer,
  never a character count.
- **In**: `max(0, speech_start − 0.04)`, pop over 0.14 s — alpha 0→1, scale 0.86→1.0, `ease_out_cubic`.
- **Hold**: alpha 1.0 from speech start to speech end.
- **Short pause**: after the line, hold at most `min(0.28, gap − 0.24)` s; `0.02` s when an overlapping line
  takes the floor. A balloon must be fully gone during any silence longer than 0.28 s.
- **Out**: 0.16 s fade — alpha 1→0, scale 1.0→0.94, `ease_in_cubic`.
- **Interruption**: the interrupted balloon leaves on the fade, the interrupter's balloon arrives on its own
  onset — they may overlap only inside the measured overlap.

## 6 · Text

- max 3 lines, wrap at 24–30 characters for a 1080-wide frame; font floor 34 px, target 38–42 px
- truncated text gets a single `…` on the last line and lost tail — never a fourth line
- keep the mouth visible: a balloon anchored above the head cannot cover the mouth, a balloon beside the head
  must stay clear of the chin band
- optional speaker name in small caps inside the balloon's top-left when two figures share the frame and the
  audio alone does not disambiguate

## 7 · Degenerate cases to test (all covered by `--selftest`)

| case | expected |
|---|---|
| one balloon, roomy frame | inside the safe rect |
| balloon pushed to the frame edge | clamped, never cropped |
| two balloons at once | never overlap; one lifts or slides |
| three balloons | still no head covered |
| balloon whose only escape is beside a listener's head | slides clear of the head |
| balloon requested over its own speaker's head | lifts, never sits on the hat |
| long line | 3 lines maximum, ellipsis, no overflow |
| balloon during silence | does not exist |

## 8 · Drawing, not just placing

Geometry that is never drawn proves nothing. `draw_balloon()` exists so the two can be checked together, and
it carries three lessons that only showed up on a rendered frame:

- **a tail drawn with fill only is invisible** whenever it sits on a background of its own colour, which is
  most of the time — outline the two long sides with the same ink as the body
- **draw the tail before the body**, then cover the base seam with a short fill stroke, or the base edge cuts a
  line across the balloon's bottom border
- **the tip stops at `1.22 r + 10 px` from the head centre** and never enters the head; a tail that touches the
  crown reads as a horn, not as speech

## 9 · Failure this page exists to prevent

A first sample shipped without a balloon system and the dialogue lived in captions. The second shipped
balloons that covered a partner's face during an interruption. The third shipped two balloons on top of each
other for four frames because the push was eased and nobody checked where it was actually drawn. All three are
geometry bugs with geometry fixes, which is why the solver is a pure function with a self-test instead of
inline drawing code.
