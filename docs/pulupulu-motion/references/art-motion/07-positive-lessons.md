# 07 · Positive experience: what has been proven to work

This page records practices that are reusable in real work, the evidence for them, and the conditions under which they apply.

This page records only **what was done right**: the practice, the evidence (what was measured / who reused it successfully and under what conditions), why it works, and when to use it. Pitfalls live in each reference's "Pitfalls" section. Every entry carries its source: when someone reuses it successfully later, add a line to the evidence; when reuse fails, write the boundary down clearly.

---

## I. Direction and mechanism

**1. A transition = the signature language of the next style.**
- Evidence: all 15 transitions in the art-history speedrun were designed this way; two independent agents in migration tests A and B both rated it "the most valuable, most transferable sentence in the whole skill"; the 9 new transitions (gold-leaf spiral spreading open, The Scream's colour bands pressing down, an apsara's ribbon peeling the old painting away, polka dots growing out, a melting droplet, hard-edged sunlight, wet paper bleeding, VHS tearing...) were derived almost straight from that sentence, with no detours.
- Why: a transition does two jobs at once — it says goodbye to the old style and announces the new one. Within 0.3 s the audience knows "who comes next".
- How to use it: list the new style's most recognisable formal elements (material, brushwork, motif, media glitch), pick one that can go "from nothing to full", and build it as a process growing out of an object inside the frame (the cat, the cup, the head).

**2. Speedrun / traversal films: one skeleton, one choreography, N ways of painting = "the same pair of characters travelling through time", for free.**
- Evidence: RIG.girl/RIG.cat return Path2D + anchors and all 36 styles reuse them; both A and B said "when the style changes, the person and the cat are still standing in the same place, the blocking and the action line up automatically, and that effect comes for free".
- How to use it: only for speedrun and traversal films that "change style inside one scene": fix the character skeleton and the action curves first, then write the style — the style only changes "how it is painted", not "where they are, how they move". Everything else composes for its own subject, and the style itself may decide the composition; do not carry this skeleton's blocking over.

**3. The protagonist's action has to be continuous across segments, driven by whole-film time.**
- Evidence: in the first cut of migration test A every segment repainted on local time, and the review said outright "the audience sees her raise the cup five times, not one moment in five painting styles"; after switching to whole-film time (`PAINT.cupCycle(t)`) the pose on either side of a transition matched and the "two heads" continuity break disappeared.
- How to use it: in speedrun and traversal films, drive character action off whole-film time t, always; only "a performance exclusive to this segment" uses local lt.

**4. A beat grid plus an impact on the beat point acts on both the old and the new layer.**
- Evidence: v1 impacted only the new layer and the review measured the first 6 of 15 transitions dragging 0.1–0.17 s behind the beat; with both layers impacted at once, the first picture change in all 15 transitions landed on the beat (±2 frames), with frame deltas of 7–33 on the beat.
- How to use it: in any cut-to-the-beat edit, that one frame on the beat must carry a whole-screen visible change.

**5. Open by letting the first painting "paint itself".**
- Evidence: in migration test A the first 0.45 s of the ink section wrote the strokes out in a reveal and let the ink bleed spread; the review approved it, and frame 0 is no longer blank paper.
- How to use it: when the film's first segment has no transition to borrow, open on that style's "process of making the picture" (strokes writing themselves out, a print laying down one colour plate at a time, pixels lighting up row by row).

## II. The beauty of the frame

**6. A regional palette matters more than colour jitter.**
- Evidence: the first Van Gogh pass only jittered colour and was "noise points in the same blue"; only after each region got its own 7–8 colour set (`P.swatch`) did it become Van Gogh. A's Munch (sky/fjord/mountain/wall/ground, one group each) copied this straight over and it worked.
- How to use it: for any brushstroke or colour-dot style, fix the colour groups by region first, draw every stroke's colour from its group, then mix in 30–45% underpainting colour to keep the light and shade.

**7. Give large areas to the renderer, keep small objects and characters on their own layer, and add the lines last.**
- Evidence: the sunflowers and the table legs were smashed into one lump by the big brushstrokes and only read clearly after the layers were split; B's Hopper "two-version light-and-shadow crop" is this rule generalised.
- Boundary: ink, print and pattern pipelines run in a different order (paper is the ground, ink only ever adds on top; the pattern itself is the renderer) — see 04.

**8. Characters have to go through the same renderer, otherwise they look like pasted-on cut-outs.**
- Evidence: of the 36 styles, the ones where the character also went through the renderer (Van Gogh's fine strokes, mosaic stones, 8-bit pixels, faceted solids, black-figure silhouette, shadow-puppet cut-through) blend best; the ones painted flat on a bare vector skeleton (ink figure 6/10, Ghibli figure "like flat vector", Dalí "leans vector illustration") are the weakest point of their segment.
- How to use it: after painting a character flat, apply at least one "material treatment of that style" — brushstrokes, grain, a paper-texture multiply, an ink-bleed edge, halftone dots, colour-plate misregistration.

**9. Type inside a style is better drawn as paths than set in a font.**
- Evidence: B's Cyrillic block letters (5×7 modules) and neon-tube kana; Rome's mosaic letters (monospaced heavy strokes, every stroke ≥2 stones wide). A font subset missing a glyph silently falls back to a system font and the look changes on another machine.
- How to use it: draw titles, signage and labels as paths in that style's material wherever you can; when a font is unavoidable, verify the glyph is there first.

**10. The material's physical process is the renderer.**
- Evidence: ukiyo-e "fill colour offset (3,2) px against the ink line + 暈し horizontal brush streaks" = colour woodblock printing; mosaic "layout computed once, colour flows through the stones every frame" = how a real mosaic animates; gold leaf "horizontal brushed noise with the y frequency 20× the x frequency" gives metal in one pass and A's Klimt reused it directly.
- How to use it: before writing a new renderer, ask "how was this picture actually made in the real world" and write that process as code.

**11. Small things have to be drawn bigger than instinct says.**
- Evidence: ukiyo-e wave claws at 22–50 px read as nothing; 44–74 px is what The Great Wave off Kanagawa needs; A had to scale Qi Baishi's shrimp 1.45× and the apsara 1.35× before they read.

## III. Motion

**12. Art-style frames: each scene = one main action + 2–4 small loops taken from that style's motifs.**
- Evidence: cutting stills alone cannot express motion inside the painting; the 16 segments built on this rule measured qa motion area 1.6–14% with zero jumps.
- Boundary: this governs art-style frames (the painting has to stay alive). Explainer shots follow item 29 — the motion lives in the events.
- How to use it: build the motif-action list from the motion heat map of the breakdown; with no reference film, list the style's 3 most recognisable formal elements yourself and give each one a way to move.

**13. Let the direction field vary continuously over time instead of reseeding the whole screen at 8 fps.**
- Evidence: reseeding the full screen at 8 fps gave frame deltas of 18–20 (bigger than a transition) and the review read it as "the painting is flickering"; with stroke positions fixed and the direction field swaying continuously, jumps went to 0 and motion area to 9%. Boil is left to line art only.

**14. The modulo period of a scrolling pattern equals the pattern's true period.**
- Evidence: A's polka-dot skirt took its modulo from the dot spacing and the wrap frame jumped whole-screen (2.7× frame delta); taking the modulo from the two-row period of the hex grid made it vanish.

## IV. Stability and efficiency

**15. Spec + reference implementation + parallel agents in groups, passing first time.**
- Evidence: 16 eras in 4 parallel groups, 30–35 minutes each, all delivered usable on the first pass; the 4 later migration-test groups (20 new styles) also delivered on the first pass. The spec spelled out the interface, the available libraries, the hard requirements, the self-checks and the delivery notes; the reference implementation made the "five-layer structure" something you could copy outright.

**16. Always dispatch an independent review agent before delivery; it looks only at the finished film.**
- Evidence: the review of reproduction v1 caught 4 classes of problem — dragging behind the beat, whole-screen flicker, too static, the cat breaking the scene; the review of migration A caught "raising the cup five times", "two heads", "transparent arm"; the review of B caught "ЧАЙ reads as ЧАИ" and "the pink outfit looks like no clothes" — the maker had looked 3 times and seen none of it.

**17. Accept with numbers: qa.py.**
- Evidence: motion area, static frame pairs, jumps, real elapsed time (forced GPU flush) and determinism verified 16 segments in one 40-second run. Comparing only first and last frame misses stutter (A: Klimt 33% change but 14/48 frame pairs static); measuring only JS time reports a fake 1 ms (B).

**18. Seed everything random; render the same instant twice and it is identical pixel for pixel.**
- Evidence: all 36 styles passed the cold/warm render comparison; the render does not flicker and can be re-rendered in pieces and stitched.

**19. Cache everything static; each frame draws only what moves.**
- Evidence: Bauhaus 2.5 ms, Pop 5 ms, 8-bit 3 ms; 4 of B's 5 segments cached the whole base plate. The heaviest, Van Gogh (three passes of strokes over the full frame), took 117 ms, and the whole film still rendered at 60 fps in under 2 minutes.

## V. Breakdown and reference

**20. Use a reference frame as the image-generation reference to lock composition; overlay a grid on an AI design sheet to read the key points.**
- Evidence: gpt-image given the original film frame as reference, blended at 50% with the original, matched almost pixel for pixel; the first hand-written coordinates for the girl's skeleton looked like a boy, and after overlaying a 20 px grid and reading the points it took one pass to get a 17-year-old blonde girl.

**21. A motion heat map tells you before you start that "the painting is alive".**
- Evidence: before seeing the heat map I assumed each segment was a single still painting; the heat map showed 2.5–34% of each segment moving, which decided the whole route.

**22. Fit the grid using "the largest step size at 80% inliers".**
- Evidence: least-squares residuals pick a very small step and force it through every point; the change fitted 14.1 frames from 16 detected points (128 BPM eighth notes), with 3 false detections marked as outliers.

## VI. Scaling (evening of 2026-10-04, integrating 36 styles)

**23. Let independent agents each build their own wheels first, then merge into one library.**
- Evidence: the 4 migration-test groups each wrote their own brushes/renderers/post, and the merge consolidated them into brush.js (7), render.js (14) and post.js (6); after porting 20 segments to the shared library, 16 of them matched the original project pixel for pixel outside the character boxes — the library's API was enough to carry real usage.
- Why: unifying the library first designs abstractions nobody uses; let real styles grow first and only what appears more than twice goes into the library (the reverse of "three lines of duplication beat premature abstraction" also holds: repeat three times and it should be collected).

**24. A migration test is the best requirements document you will get.**
- Evidence: the brief "read only the skill, build a style the skill doesn't have, write feedback" brought back 60-odd concrete problems from 4 agents (silent degradation, hard-coded durations, timing that doesn't flush, skeleton bugs, mislabelled dabs), each with a reproduction scenario; none of them had surfaced in the author's own use.
- How to use it: every time the skill gains a large capability, send 2 agents that have only read the skill at a problem they have not seen, and require "what helped / where you got stuck" back.

**25. The acceptance tool has to be accepted too.**
- Evidence: qa.py once went all green, yet during the merge it turned out never to execute transition code at all — one transition referenced a function that didn't exist and the whole frame crashed without a report; only after adding a "transition smoke test" was it caught. The glyph check compared with measureText and under-reported on Mac; it now reads the font file's character table.
- How to use it: deliberately make each check fail once (delete a scene, write a transition wrong, use a missing glyph) and confirm it really goes red.

## VII. Video animation grammars (evening of 2026-10-04, 5 YouTube + 3 tech-finance)

**26. Measure sample films first, then decide the grammar.**
- Evidence: the first Vox pass in G1 used a torn-paper transition, and counting frames through 5 Vox samples showed it never once appears; the first whiteboard pass pushed into a thought bubble, and the RSA samples don't have one either. G2 measured one TheOdd1sOut film: average shot 2.4 s, seven out of ten adjacent frame pairs completely static — the opposite of the instinct that "animation should always be moving".
- How to use it: before building a grammar, run `breakdown.py` on 2–5 representative films to measure shot length, static ratio and transition types, then write the card. The "style traits" in your head usually belong to somebody else.

**27. The camera is decided by whole-film time alone; a transition function only composites two shots.**
- Evidence: Kurzgesagt's 60× scale traversal is redrawn as vectors the whole way through and never blurs; Vox's "transition" between table and whiteboard is the camera move itself, qa jumps 0. G3: a push-in transition lets the old shot keep pushing the camera itself rather than scaling up a screenshot — to pass through a round object the zoom factor must be ≥ 1100/radius, or the last frame jumps.
- How to use it: a world canvas plus a viewport; never do a scale transition on an already-rendered bitmap.

**28. The frame where it "unveils" is the accent.**
- Evidence: G2's kinetic type sets the segment start to "bar line − unveil point × transition duration" so every visual event lands on the same frame as the kick drum. This and item 4 (beat impact on both layers) are two cases of the same principle.

**29. Static does not mean stuttering; but "every shot moves a little" and "every shot slowly pushes in" are the same disease.**
- Evidence: seven out of ten static frames in storytime is the style (the punchline is the cut to a reaction close-up with the mouth shut); kinetic type stops the words once they land and hands the sense of motion to the camera and the background. A Nobel-prize literature explainer (2026-10-08) with the same voice-over, the same material and the same 31-shot storyboard: r2 pushed in 7.5% at constant speed on every shot, plus a fixed beige ground, a title bar and a photo frame, and the author said "it feels exactly like playing a PowerPoint, absolutely rubbish"; r3 switched to full-frame live footage, real dark environments and no page frames, and the camera became stop → push in 18–32% over 0.28 s → stop, glide sideways 0.30 s at the same scale, slam in over 0.17 s, and it was approved. Completely static frames went from 16% to 72%, fast-moving frames from 0.7% to 10%. Four things changed at once, so there is no telling which one did the work. After that "push in fast at every voice-over node" was written up as a global rule; a 2026-10-12 Nobel economics short pushed in about 48 times in 102 s, every one of them inward, and the author said "too many times, and the rhythm is too fast — not smooth at all"; the same day the author looked back at the literature film: "the literature film is very ordinary".
- How to use it: qa's "static frame pairs >40% reads as stutter" does not apply to explainers, stories or type-driven films — holding still is correct there. The root of the PowerPoint feel is "the same move on every shot", no matter whether that move is a slow push or a fast push. Move the camera by "what should the audience be looking at right now": transitions use a slow push, a glide or a pull back (0.6–1.5 s); fast pushes and slams are kept for accents; after pushing in there has to be a way back out. For the move table and when the count is governed, see `camera-language.md`.

**30. A review has to check logic and number conventions, not just the picture.**
- Evidence: the G3 review caught "the output neuron connects to the hidden layer, not to pixels", "'up 9×' should be 'up to 9× the original'" and "the monthly chart ends at ¥268 but the daily candle ends at ¥286.40" — all three had perfect pictures and wrong content. Hard rules for finance charts: never mislead with a truncated axis (if truncated, state "the vertical axis does not start at 0" in words), units, source, and a corner mark for illustrative data.

**31. One focus per screen; structure first, then data, then mark only one thing.**
- Evidence: kinetic — "the main word slams in, the rest rise out of a mask"; finance — "axis first, then the data, then mark only one thing"; 3b1b — "one colour is one concept, a morph turns the previous concept straight into the next, almost no cuts" — three grammars arriving independently at the same conclusion.

## VIII. Characters

**32. People go to the image-generation model, code only composites — split the work by "who is good at it", not by "how pure the route is".**
- Evidence: comparing three directions on the same frame, the code-drawn chibi was judged "absolutely rubbish", while the G2 frame library and the AI frames redrawn to the style were both "very good"; across the 36 styles the commonest weak point is also the character. Code is good at regularity (stroke fields, geometry, camera work, time, physics, determinism); the model is good at getting faces and human figures "right".
- How to use it: see 10. Ask of every layer "who draws this best" before deciding what to draw it with.

## IX. Wiring into the voice-over pipeline (night of 2026-10-04, measured end to end)

**33. Render a clip by finished-film frame count and take its window from the finished timeline — cuts and speed ramps stop mattering.**
- Evidence: between the two beats that had to be swapped sat a 3.65 s pause the rough cut had removed, and the rough cut was also sped up globally; rendering them as one continuous stretch of finished-film time (119 frames) and swapping them in, the shot's `rate` after compiling = 1.0, 119 rendered frames = 119 shot frames, only 1 chapter re-rendered (30–57 s) and the other 7 chapters untouched. Chapters match the clip frame for frame; the frames where the picture moves, 28/29 and 127/137, project an offset of 0 (the rest is encoding noise, symmetric plus and minus).
- Why: the pipeline's director layer works in source seconds and the finished film in finished seconds; the animation only lives inside the finished film. Taking the window from the finished timeline sidesteps three conversions at once: speed ramps, cut points, and "beat end = next beat start".
- How to use it: in the voice-over pipeline, write a small script wrapping the three steps "draft (take the window from the finished timeline, emit a spec draft) → render → verify (check sync frame by frame)" — see 09's "Clip contract".

**34. A cue names the word, not the second; convert to frames at render time.**
- Evidence: across 5 cues (a bar growing, an annotation popping up, a clipping showing, two highlighter passes) the error between the reveal frame and the word's start was −0.48 to +0.09 frames, all of it from rounding to frames; when the narration changed and the window frame count changed, render rejected it outright instead of drifting silently.
- Why: a second is a second-hand number copied from the word list and every copy is a chance to be wrong; the word is the director's real intent (the annotation pops when a certain number is spoken), and the conversion belongs to the script.
- How to use it: `{"word": "7.8", "kind": "highlight"}`; for a word that occurs more than once add `nth`, and write `offset` up front when you need it.

**35. Vertical, with real screenshots pasted in: split into two highlighter passes following the half-sentence the narration has reached, each aimed at one keyword.**
- Evidence: with a box around the whole passage (width 0.93) the red circle didn't fit and the camera couldn't push in, and body text about 20 px high is unreadable on a phone; split into two half-sentence boxes following the narration, one keyword each, pushed in 2.4×, the text stood about 50 px high; when the second box was off-screen the camera moved over first and then unveiled it.
- Why: the bottleneck in vertical is frame width, so one focus can only be half a sentence; Vox is already a "look at this one sentence" grammar, and circling along with the narration sentence by sentence fits it exactly.
- How to use it: crop the screenshot from the frame as-is (keep a copy named `_source-frame`), and render one frame with `--stills` to check the rect first — eyeballing is usually off by 20–30%.

**36. A type-carrying grammar yields to the subtitle band; the subtitles do not yield to the animation.**
- Evidence: in t3's vertical original layout the annotation landed at y≈1460, overlapping the burned-in subtitles (1400–1520); with `safe` added the chart laid out at 300–1430, the same safe area as the other contain material in the film, and sampled frames showed zero occlusion. The first independent review said "a screenful of pure white wedged between dark screenshots — the brightness jump is the most obvious thing"; adding `safe.fill` = the film's ground colour turned the two strips into dark grounds like the adjacent screenshots, and the chart became a card in the same position.
- Why: subtitles are burned in once at export, so moving them per segment means touching the export chain; the animation is parametric, and moving itself is the cheapest thing it can do.
- How to use it: write `safe` into the spec (the pipeline's draft computes it from the ASS and the contain_box).

## IX. From demo film to reusable clip

**33. A good demo film ≠ still good once parameterised; parameterisation needs its own review.**
- Evidence: the demo films for all 8 grammars passed independent review; extracted into spec-driven clips and reviewed again, only 3 were usable as-is: swapping in real data exposed a scale rounding bug, category labels being dropped, and a big number running into the leader line; the subtitle-yield parameter was ignored in 6 of 8; the camera left before the text card finished typing; on the whiteboard the last frame's pen covered the character 不 ("not") and reversed the meaning. A demo film's input is chosen by the author; a clip's input is whatever the pipeline hands it.
- How to use it: change the input when reviewing a parameterised clip — negative numbers, decimals, long titles, vertical, no screenshot, transparent background, over-long text — feed at least one "unfriendly" spec to each; the sample material used for acceptance has to be clean itself too (don't use a screenshot of a table-of-contents page as the example).

## X. Wiring into voice-over video

**34. Render an animation segment on "finished duration + word-level timing", with key frames landing on the keywords.**
- Evidence: in a copy of a vertical voice-over film, two stretches inside one chapter were replaced with animation (t3 finance chart explaining a set of number comparisons, y2 Vox pushing into a screenshot of the official text); the frame count matched the shot exactly, 7 keywords within −0.48 to +0.09 frames.
- Why: animation appears only where a screen recording can't explain it (one number comparison, one official sentence), and a real person plus screen recording stay on either side; the picture event unveils only when he reaches that word, as if he were pointing at it while talking.
- How to use it: beat → take finished duration and word-level timing → generate spec → render → freeze and write back (interface in 09's "Clip contract"). Numbers come only from the source table, and the source is written on the image.

**35. Don't add narrative gags he didn't ask for.**
- Lesson: decoration that keeps accumulating on a character steals attention from the scene, so confirm a narrative gag in a sample film first.
- How to use it: what a review flags as "missing" is information for him to judge, not authorisation for me to add things; to add a structural gag, show it in a sample film or in the direction notes first and wait for his nod.

## 2026-10-05 00:34:23 +0800 · Allocate grammar by explanatory task within one voice-over

Practice: for a real original post or manuscript, use Vox's material table tracking lines and highlights; for rules, controlled variables and sound-image relations, use 3b1b's continuous object transformation; fix the voice, the subtitles and the timeline first, then replace the picture. Evidence: one voice-over film's 467.8 s of narration and 270 subtitle lines were reused after the entire visual style was rebuilt, and the two final MP4s have matching AAC raw packet hashes and the same locked mix; there is no post-publication retention data yet. Why: the picture carries the explanatory action of its own passage and the material serves readability; the grammar allows stillness after the image has been read or derived, and does not need background micro-motion to pad the motion count. Applies to: voice-over films that alternate real material with mechanism explanation.

## XI. Long-scroll traversal films (the author travelling through famous paintings, 2026-10-05)

**36. One skeleton file plus per-segment parallelism: 24 worlds and 4 agent groups assembled in one pass.**
- Evidence (the skeleton and 3 of the segments went into `scripts/art-motion/engine/demos/long_scroll/`, method in 11): `scripts/art-motion/engine/demos/long_scroll/lib/world.js` defines only the segment interface (width, ground line, walk frames, interaction at/dur/frame, back/front/seam), the protagonist's progress, the protagonist clipped at boundaries, and the corner tick; the four groups each wrote 6 segments, and sorted by era they assembled in one pass into 123.7 s, qa determinism ✓, jumps 0; the review checked the ground height and the protagonist's continuity across all 23 boundaries and passed every one. The key is that the whole-film constants (ground line 760, body height 300, stride speed) are hard-coded in the skeleton.
- How to use it: for a long film, write the skeleton and the interface first, then dispatch the groups; in the interface **time every event relative to "interaction start"** (`WORLD.actT`, `item.atAct`), never "the nth second after entering the segment" — the whole-film stride speed later went from 330 to 560 and not one segment needed its timing changed.

**37. Trim each segment's speed so the musical boundaries land on the first beat of the bar.**
- Evidence: the 24 boundary moments are fixed, and even the best single BPM was 112 ms off; after giving each segment a whole number of beats and trimming its speed between 86 and 104 BPM segment by segment, all 24 boundaries landed on the first beat of the bar, max error 11.7 ms, mean 3 ms.
- How to use it: when the picture is fixed first and the music scored afterwards, don't insist on one BPM; the ear cannot hear a ±8% speed difference between segments, but it hears an instrument change that misses the downbeat.

**38. The camera only goes in, never back.**
- Evidence: in v1 the camera moved forward to make room during an interaction and pulled back at the end, and 17 of 24 segments showed a 68–256 px "rewind" that qa could not measure and a review spotted at a glance. After switching to "target position = historical maximum + Gaussian smoothing" there were 0 backward moves in the whole film, and neither stopping nor starting stutters.
- How to use it: for a horizontal long scroll that follows the protagonist, make the camera position function monotonic; adding a "camera backward count" to qa would be better still.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
