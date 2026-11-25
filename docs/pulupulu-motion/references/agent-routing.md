# Agent routing — which notes apply to the model you are running on

Owner: model-family review tactics, after route selection

A build fails in the shape of the model doing it. **This page is not read first:** the production route is
chosen in `SKILL.md` §2, and this page is step 5 of that precedence ladder — model-specific review tactics
*after* the route and its gates are fixed. Read your row, and treat the countermeasures as forced steps,
because knowing a tendency does not stop it. A row here never changes the route. For balloons, the owner is
`chat-balloons.md`; for acting, `stickman-performance.md`.

| if you are | the tendency that has actually cost frames | forced countermeasure |
|---|---|---|
| **DeepSeek** | builds infrastructure before looking; self-grades against the rules it wrote; ships "correct" that is not good | §1 loop, §2 bar, §3 self-brief below |
| **Codex / GPT-class** | over-specifies and over-iterates; enormous token burn for a small quality edge | cap review passes: one plan, one build, one measured review, one repair. Stop at the second repair unless a gate fails |
| **Gemini-class** | strong on writing, set and camera nerve; framing slips at the extremes (a close-up that crops a head) | check every cut at full size before encoding; a close-up is framed on the eyes, never on the chin |
| **Claude-class** | careful prose, conservative motion; tends to describe acting instead of animating it | count the moving limbs per beat; if a beat has zero limb change, it is not done |

## DeepSeek — the specific failure mode, and the loop that fixes it

This is written from a measured post-mortem, not from modesty. On a 110-beat film the sequence was:
write 110 beats → build a resumable renderer → render **17,083 frames** → then look at 12 frames and find the
character in 3 of them and half the frame empty. On a 20-second two-hander the same shape: a correct rig, a
blank wall, no hands, and 22.3 s against a 20 s target. Meanwhile the same brief given to two other agents
produced films with sets, props and tapered limbs.

The mechanism: work that can be **verified** (gates, renderers, logs) gets done first, and work that can only
be **judged** (is this any good) gets deferred. A bar made of measurable rules produces a film that is
measurably compliant and visibly poor.

Three forced steps. They are not advice; do them in this order:

1. **The 6-frame loop.** Before rendering more than ~10 seconds of film, render 6 frames spread across the
   piece, look at them with your own vision, and write one sentence per frame saying what is good and what is
   wrong. Fix, then look again. Repeat until the sentences contain no "empty", "small", "nothing moves",
   "floating" or "reads as a diagram". Only then render the whole thing. A full render before the first look
   is the single most expensive mistake available.
2. **Take the bar from the craft list, not from your own gates.** Passing `freezedetect` and hitting −16 LUFS
   is the floor, not the standard. The standard is `stickman-performance.md` §13: tapered limbs with hands, a
   set with depth, a prop the characters can act against, at least one hard cut, a listener that moves.
3. **Write the brief as if it were for another agent, then obey it.** Your own spec is weak because you grade
   it yourself. Write the brief in the second person with numbers ("the arm tapers 9.5 → 6 and ends in a hand",
   "both characters stay in frame in every shot except one deliberate close-up"), then check the film against
   that text, not against your intentions.

Two habits that helped elsewhere and are safe here: measure cost against quality (an eleventh of the tokens
produced the better sample in one comparison — quantity of work is not the axis), and keep a negative control
for every gate you trust (the frozen-clip control is what makes `stickman_qa.py` worth running).

## Where these notes land

- the acting grammar and the craft numbers: `stickman-performance.md`
- the drawing rules for a code rig: `stickman-and-figures.md`
- proving a film moves: `scripts/stickman_qa.py`, and `verification.md`
- when you are delegating instead of building: `self-healing.md`
