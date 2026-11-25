# Narration, storyboard and captions

Owner: storyboard, narration captions and the one-language gate


The storyboard contract, the one-language gate, and how caption timing is derived from measured speech.

Part of the `pulupulu-motion` skill. The entry point and the gate table live in `SKILL.md`.

## The interval model — this page wins over any other page

Three intervals per beat, and they are not the same interval. When another page states a different rule,
this one takes precedence.

| interval | comes from | may do |
|---|---|---|
| **speech** | measured: the onset and offset of the phrase in `voice.wav` | never invented, never nudged to make a cut land |
| **caption** | a partition of the speech interval, windows weighted by each chunk's word count | starts at speech onset, ends at speech offset, never outside it |
| **picture** | derived: starts up to 0.14 s before speech onset, holds until the next picture starts | may lead speech (a cut before the word) and may hold across a pause; may never lag it |

The picture is allowed to overlap the previous shot; the caption is not allowed to overlap another caption,
and neither is allowed to leave its beat. If a chunk cannot fit its window at the caption's font size, cut a
word from the phrase — do not shrink the type and do not speed the read.

**One schema, everything derived from it.** `beats.json` is the only authored file:

```json
[{"id": "b01", "text": "In nineteen eighty four, a programmer in Moscow built a game out of falling blocks.", "pause_after": 0.55}]
```

`deepseek_voice.py beats … --timeline timeline.json` measures the phrases and writes `timeline.json` with
`start`, `end` and the film `duration`. The page generator reads the timeline for picture and caption
timing; captions chunk `text` and never re-author it. A storyboard document is for the person, not for the
build — if the generator reads two sources, the caption drifts within three beats.

## 3a. Storyboard & narration contract (before any HTML)

A narrated film that comes back as "captions don't match the story" was authored on two clocks: the words in one table, the pictures and captions in another. Fix it by construction, not by proofreading.

**Write `storyboard.md` first — one row per beat, nothing else in the file:**

```text
beat | spoken phrase (verbatim)            | picture (the ONE thing that changes) | pause after
b01  | Two in the morning and your phone rings. | 02:00 clock, phone buzzing      | 0.55
b02  | Your site is down.                   | red flood + 500, hard cut in         | 0.90
b03  | You check hosting: the machine is alive. | dashboard card, all green         | 0.50
```

Rules that make the film cohere:
1. **One beat = one spoken phrase = one visual change = one caption.** If a beat needs two pictures, it is two beats.
2. **The caption is the spoken phrase, verbatim.** Never a summary, never a rephrase, never "better written" — a caption written separately from the voice drifts away from the story within three beats, and the viewer sees it immediately. The **only** licensed difference is *display form vs spoken form*: the voice says `five oh two` while the screen shows `502`, the voice says `D N S` while the screen shows `DNS`. Same sentence, different notation — see the `tts-intonation` skill §2b for how to decide per token, and let `tts-prosody.py --expand en|id` write and audit it. Style it with `<em>`, never rewrite it.
   - **Chunk to 2–4 words on the spoken punctuation, and never leave a one-word last chunk.** Splitting a phrase into fixed-size groups strands a single final word (`In nineteen eighty` / `four,`), which occupies a whole cue slot alone and reads as a typo rather than a caption. After chunking, merge any trailing chunk of one word into the one before it, and size the cue windows from the measured beat length divided by the final chunk count — not by the count before the merge.
   - **Dates, months and versions are digits on screen, and the two layers are separate fields.** One `text` field serving both the voice and the screen drifts: on a 50-beat history film a caption layer mixed `May 1995`, `nineteen ninety-five` and `1995`, because nothing enforced a form. Author `say` (speakable: *in may, nineteen ninety-five*) beside `caption` (screen: `05/1995`, `1995–1999`, `ES2015`, `10 days`) — same sentence, notation only — and fail the build with `scripts/audit_numbers.py`, which rejects a caption carrying a month name, a spelled-out number or a spelled-out year while leaving the `say` field free to speak them.
   - **Show notation, speak words — and weight cue windows by their word count.** A year reads as `1984` on screen while the voice says *nineteen eighty four* (a spelled year splits across cues and the first chunk reads as the wrong year); small prose numbers keep their words, and a large statistic compresses to a readable unit (`2 million`, not `2 000 000`). Give each cue a window weighted by its own length instead of an equal share of the beat — an equal share makes a one-word chunk linger as long as a four-word one, which is what makes captions feel late. Never split a year or a number+unit across two cues. Detail: `references/visual-craft.md` § *Number and year captions*.
3. **Narration is written to the clock, not to the screen.** Budget ≈ **2.4–2.7 spoken words per second**: a 60 s film holds **120–150 words including pauses**. Over budget means cutting words, not reading faster.
4. **Phrases of 4–12 words, one idea each**, with a planned pause after (0.2 s inside an idea, 0.5 s for a new claim, 0.9–1.2 s before the payoff). Full method: the `tts-intonation` skill.
5. **The timeline is measured audio, never a number picked in advance.** Synthesise the phrases, measure each one, emit `timeline.json`, then place every beat's picture and caption inside its own `[start, end]` window. Film length = the timeline total.
6. **Split the voice from the score before it is too late:** `om sound` is generated against the film length produced by the timeline, and the mix is padded with `apad=whole_dur=<film length>`.

**Self-check before building:** read the storyboard aloud, ticking a finger per word. Any beat whose phrase cannot be said inside its slot is already broken — cut words now, not after the render. Then check the reverse direction: every picture must be *caused* by its phrase (the phrase "disk full" cannot sit on a shot of a server rack) — and when the phrase names a set, a count or a shape, draw exactly that: a beat about *twelve pentominoes* cannot show four-cell tetrominoes, and a beat about *seven shapes* cannot show twelve, however good the grid looks. **The same holds for a named
object: if the caption names a cross, a mirror or a knife, that object has to be in the frame.** A shot can be
beautiful, correctly lit and on time and still fail this — the frame looks fine on its own, so nothing but a
noun-by-noun comparison finds it. List the object nouns in the caption and tick each one against what the beat
draws before the render; an agent-built film is where this slips, because the caption and the art are written in
the same pass and neither one is wrong. Two beats showing the same layout with different captions is a slide deck, not a storyboard.

## 3c. One language, checked mechanically (not by proofreading)

**The film's language covers every visible string and the voice: captions, headlines, card labels, tags, units, end card — plus art-template literals, which are the ones that leak.** Copy tables get translated on a re-language; the headline baked into a `visual()` template does not. One Indonesian film was rebuilt in English with every caption and card converted and still shipped the flood beat with the old-language headline, because that string lived in the generator's HTML, not in `beats.json`.

So the gate is mechanical, and it runs on the **rendered HTML**:

```sh
python scripts/lang-audit.py film/index.html --lang en    # exit 1 = leftovers
```

`scripts/lang-audit.py` strips tags/styles for the markup pass, then scans **two** haystacks against the *other* language's stopword list and fails the build: the visible text, and the **string literals inside `<script>`**. The second one is not optional — a runtime label or a canvas caption lives only in JS, so an audit that drops scripts wholesale (the original behaviour) cannot see the leak it exists to catch. Repro of both directions: a page whose only foreign text sits in a script returns hits with `where: script` and exit 1, and the same page under `--no-scripts` passes. Prove the gate is alive that way after touching it, before trusting a green run.

Read those literals with a small hand-written scanner, not a regex: a character class that must exclude both the quote and the backslash ends in a trailing backslash and either refuses to compile or matches across the closing quote, returning fragments like `').textContent = '`. Filter out identifiers, selectors and URLs by shape, dedupe, then scan. Wire it into the generator so it cannot be skipped:

```python
subprocess.run([sys.executable, "../lang-audit.py", os.path.join(OUT, "index.html"),
                "--lang", "en"], check=True)   # build.py aborts on a leak
```

Then look at one frame per scene. The audit catches tokens, not tone: a frame can pass the scan and still read like a translation.

## Field notes (narration, captions and the clock)

- **Budget the whole runtime, not just the speech.** Narration plus score plus mux is three passes over the
  same clock; a 8:33 film at 30 fps is ~15,400 frames, so a length error found after the render costs the
  render. Lock the measured total against the brief before the first frame.
- **A fixed duration in the brief is a spec, not an output.** When the ask is "20 seconds", the total the TTS
  happens to produce is not the answer — count words against the clock first, cut, then synthesise. Trailing
  gaps are where the extra time hides: eight short dialogue lines whose speech summed to 18.2 s came out at
  22.3 s once the planned pauses and one interruption overlap were placed, overshooting a 20 s target by two
  seconds nobody budgeted. Short conversational lines read around **2.3 words per second of speech** and about
  **1.9 including gaps**, noticeably slower than continuous narration (2.4–2.7), so a 20 s two-hander holds
  roughly 38–42 spoken words — not 50.
- **Mux with an explicit map, or the narrator disappears.** `pulupulu render` already embeds the score, so `ffmpeg -i render.mp4 -i mix.wav -c:v copy -c:a aac …` picks the render's own music-only audio stream and silently drops the mix — the delivered film plays music and no voice, while `om qa`, `ffprobe` and every level check still look healthy (one AAC stream, −16 LUFS). Always `-map 0:v:0 -map 1:a:0`, then confirm the voice is really in the file by transcribing a slice of the **final MP4**, not of `voice.wav`.
- **The per-phrase ASR gate is not optional.** Slice `assets/voice.wav` at each beat's measured window, transcribe each slice, and compare with the script before building the picture. On one 60 s explainer it caught two phrases the ear would only notice at 1× playback: a three-word fragment that the engine transcribed as a nonsense phrase in another language, and a loanword-heavy line that came back as gibberish English. Both were fixed by rewriting the words, not the audio — fragments get a full sentence, loanwords get outnumbered or moved on screen.
- **A caption sized for a monitor is a smudge on a phone.** Measured across three delivered films of the same
  subject: captions at 20–28 px on a 1920-wide frame were fine on a desktop and unreadable at arm's length on a
  phone, while 36–40 px on a dark plate with a narrow accent bar down the left edge read comfortably and stayed
  clear of the artwork. Set the caption size in the generator once, and check it on a phone-sized crop, not on
  the full frame.
- **A caption that stops mid-clause reads as a truncation bug, not as a continuation.** When one sentence
  spans two or three beats, per-beat chunking strands fragments on screen (`Its control software had crashed,
  forcing` / `Out went the built-in garbage collector,`) and the viewer reads broken text over an otherwise
  finished frame. Make every beat's caption a complete clause: cut the script so a sentence ends where the
  beat ends, or close the partial beat with an ellipsis and open the next one with an ellipsis. Rewriting the
  script costs minutes; discovering it after the render costs the render.
- **Caption drift is a build-order bug, not a proofreading bug.** When the copy table, the caption table and the scene timings are authored separately they disagree within three beats. Generate all three from one `beats.json` plus the measured `timeline.json`, one beat per spoken phrase, and the mismatch cannot exist.
- **A calm opening still needs motion.** A hook beat whose only movement is a caption fade scores `flat opening` (0.5–1.2 motion/sec) and loses the scroll. Push the hero element (scale 1.0 → 1.06 over the beat) and pulse one peripheral element; that alone lifts the first five seconds above 2 without turning the film loud.

## Commercial copy: every line must sell, and every line must be understood

Applies to any film selling something — an ad, a product page, a launch film. Two failures are equally fatal: copy
that says nothing, and copy nobody understands.

**Every on-screen line is exactly one of three kinds.** If a line fits none of them, it is not copy, it is noise:

1. **FACT** — a sourced spec in plain words: `187 kg wet. 218 hp.` `1,477 mm wheelbase.`
2. **BENEFIT** — what that spec does for the buyer: `The crank spins backwards. The bike turns sharper.`
3. **CTA / BRAND** — `Configure yours.` `Book a test ride.` plus the manufacturer's own brand line, if they have one.

A line whose only content is atmosphere does not exist in a commercial film. Write the classification into the
proof table for every line with its timecode; a FACT needs its source URL. Unclassifiable lines get rewritten, and
the honest count of how many had to be rewritten is worth reporting.

**An instrument readout is a claim.** A dashboard, gauge, telemetry panel, HUD or spec screen filled with
plausible numbers — a lap time, a road speed, a gear, a lean angle — is fabricated data on screen, not decoration,
and it fails the same gate a headline does. Animated invented telemetry is the version that survives review longest,
because the numbers move and therefore look authored. Two honest options: every figure inside the display is
sourced, or the display shows **only sourced specifications** and is labelled as such (cycling the real peak power,
torque, rev limit, screen resolution reads as a deliberate spec panel and keeps the instrument's visual language).
Draw the instrument however you like; never invent what it reads. The same rule covers a licence plate, a chassis
stamp, a lap counter, a serial number and a temperature.

**Abstract copy is the default failure.** Real examples of lines that passed a visual review and failed a copy
review: `SYMMETRICAL BALANCE · EVERY ANGLE`, `CONTINUOUS PROFILE / SCULPTED FAIRING FLOWING FROM NOSE TO TAIL`,
`PURE GEOMETRY / ICONIC ITALIAN PROPORTIONS`, `MECHANICAL GRIP / ENGINEERED FOR TRACK-DAY PRECISION`. Each is an
adjective standing where a number belongs.

Banned as non-commercial: *sculpted, proportions, geometry, velocity, symphony, orchestrated, unleashed, redefined,
pure, iconic, every angle, where X meets Y, experience the,* and **engineered for** unless a concrete number follows.

**Length limits, set by the phone:** headline ≤ 5 words · deck ≤ 9 · footer ≤ 12 · data caption ≤ 6. A longer idea
is two shots.

**Translate the technology; never drop the fact.** A technical term is the reason the buyer is watching, so keep it
and pay for it with a plain line on the same or the next shot: *counter-rotating crankshaft* → `The crank spins the
opposite way. Less lift, sharper turn-in.` · *Öhlins Smart EC semi-active* → `Suspension that adjusts itself, corner
by corner.` · *biplane winglets* → `Two wings. More downforce, less wheelie.`

**The test that catches everything:** would a sixteen-year-old who knows nothing about the category understand the
line? If not, rewrite it. Never solve an unclear line by deleting the fact it carried.
