# Measuring a reference film

Owner: turning a reference film into a written spec

When the brief is "make it look like *this*" — a channel, a competitor, a style the client likes — do not describe the
reference from memory. **Measure it**, and turn the measurements into the target numbers your own film has to hit.
This page is the method, the commands, and how to read the results.

It is also the cheapest way to settle an argument about pacing: "feel" is an opinion, `cuts per minute` is not.

## What to record, per reference

Place the files under `research/` in the project folder:

| File | Contents |
|---|---|
| `measurements.json` | every number below, per video |
| `cut-lists.json` | shot in/out timestamps, duration, one-line description of the shot |
| `contact-sheets/` | the stills you actually looked at (12 per sheet), plus full-rate strips |
| `style-spec.json` | the distilled rules as values a renderer can execute |

## Layer 1 — measure every frame without watching it

The three commands that do the real work. Run them on the reference, then on your own film, and compare.

```sh
# 1. cut list: where the shots change
ffmpeg -i ref.mp4 -vf "select='gt(scene,0.25)',showinfo" -f null - 2>&1 | grep -oE "pts_time:[0-9.]+"

# 2. motion energy per frame: tblend difference + blackframe reports the mean absolute difference
ffmpeg -i ref.mp4 -vf "scale=270:480,tblend=all_mode=difference,blackframe=99:32" -f null - 2>&1 | grep -oE "pblack:[0-9]+"

# 3. loudness and speech density
ffmpeg -i ref.mp4 -af ebur128=peak=true -f null - 2>&1 | tail -12
ffmpeg -i ref.mp4 -af "silencedetect=n=-32dB:d=0.2" -f null - 2>&1 | grep -c silence_start
```

Derive from them, and keep the raw series:

- **shot count, average shot length, median, longest, shortest, cuts per minute** (at two thresholds — 0.25 for hard
  cuts, 0.18 to catch dissolves and fast wipes);
- **motion curve**: mean and p90 MAD per second, plus the top 5–8 spike timestamps. This is where "pacing" actually
  lives, and it finds dead stretches you cannot see by scrubbing;
- **luma and saturation per second**, so a colour claim has a number behind it;
- **integrated LUFS, LRA, true peak, silence count** and an approximate **words per minute** (word count ÷ duration).

Threshold discipline: report the threshold you used. A cut count without its `scene` value is not comparable to
anything.

## Layer 2 — look at one still per shot

Extract the frame at **+300 ms into each shot** — by then the shot has settled into the composition it was designed
around — and tile 12 per contact sheet. Judge framing, palette, staging and subject scale across the sheet, not
still by still: consistency is a property of the set.

## Layer 3 — full rate only where quality is decided

For 2–3 moments per reference (the hook, the biggest action, the ending) extract **every frame** of a 1.0–1.5 s
window and lay the strip out side by side. Anticipation, spacing, ease, smear frames and snap-and-hold are invisible
in a contact sheet and obvious in a 30-frame strip.

Publish the sample counts in the report — frames measured, stills examined, strips — so the analysis is auditable.
"We analysed every frame" with no counts is the claim this method exists to make impossible.

## Reading the numbers

Three patterns that decide how a film should be built:

- **Cuts per minute is the genre.** Under ~2 cuts/min the film is a **continuous camera take** (dolly, orbit,
  flythrough) and every transition is movement, not editing. 12–15 cuts/min is a **cut-driven** film where each beat
  is its own frame. Most channels use both modes in different videos; pick one per film instead of averaging.
- **Average shot length tells you the unit of writing.** A 27 s average means one idea per shot and the camera does
  the storytelling; a 4 s average means one idea per *beat* and the cut does it. Write the storyboard in that unit.
- **A flat motion curve is a defect even when the picture is pretty.** Compare p10 and p90 of MAD. If your film's
  floor is far below the reference's, your holds are longer, and it will read as a slideshow next to the reference.

## Use the reference as the target, not the mood board

Put the reference's numbers and your film's numbers in one table before delivery:

| metric | reference | our film | verdict |
|---|---|---|---|
| cuts/min | 9.1 | 9.0 | ok |
| avg shot length | 8.4 s | 8.1 s | ok |
| mean MAD | 10.2 | 6.9 | **too still — add motion or shorten holds** |
| integrated LUFS | −14.1 | −16.0 | **2 dB quiet for this genre** |
| longest frozen hold | 0 s | 2.3 s | **fix** |

That table is the difference between "it looks similar" and "it is the same system".

## When the reference is a storyboard board, not a film

Clients increasingly send a **board**: a grid of numbered frames with timecodes, a title per shot, a style strip and a
header of fields (duration, format, focus). Treat it as four different things, because it is:

| what the board carries | how to use it |
|---|---|
| shot list, order, timecodes, the purpose of each shot | **the brief. Implement it exactly** — these are the decisions already made for you |
| style strip (`product cinematic`, `macro detail`, `tech cutaway`, `aero flow`, `studio lighting`) | a look to match, translated into palette, lighting and type rules you write down |
| header fields (`DURATION`, `FORMAT`, `FOCUS`) | intent, **not** authority — see the format trap below |
| the figures printed inside the frames | **never a source.** Verify every one |

**The format trap: the board's header can contradict the client's instruction, and the client wins.** A board headed
`FORMAT: 16:9 (4K)` delivered into a vertical platform is a mis-communication, not a spec — asking before building
costs one message, and building the wrong aspect ratio invalidates every composition in the film. When they say
9:16, that is 9:16 whatever the board says; keep the board's *resolution ambition* (build 2160×3840, fall back to
1080×1920 if the bench projects over budget) but never keep its aspect ratio against a spoken instruction.

**The numbers on a board are usually last generation's.** A board printed `215.5 hp (158.6 kW)`; the manufacturer's
current page for the model year said `218 hp (160.4 kW) @ 13,500 rpm`. Copy the board's figure into the film and you
ship a wrong claim with the client's own artwork backing it up — the worst kind, because nobody questions it. Rule:
every figure on a board goes into the fact table with a **manufacturer URL beside it**, the film prints the sourced
number, and the proof document records the discrepancy in one line so the client can see what changed and why.

**The frames are mockups, and some of their subjects do not exist in your assets.** A board shows a carbon-weave
macro, an exhaust outlet, a dash layout, a tail light, a licence plate. Your supplied material may only contain the
object itself. Decide per shot: crop into the masters and accept the detail is small, or generate a plate **from a
crop as the reference** in the same lighting, with no text or logo inside it. **Never fabricate a prop** — an invented
number plate with a country strip is fabricated content, and it is the kind of detail a client notices in the first
three seconds.

**Check each shot against its own title.** A board is a list of promises: `EXHAUST SYSTEM` must show the exhaust,
`COCKPIT` must show a cockpit. A shot whose headline is technically correct but whose subject is a different part of
the machine is a defect, and it is only visible when you compare title to picture shot by shot.

## When the reference is not available as a file

If you only have a link and the page will not serve media, say so and fall back to: one still per shot from the
public thumbnails, plus whatever the page exposes. Then state plainly which metrics are "not measured" — an honest
gap is usable, an invented cut count is not.

### Downloading a vertical reference

```sh
yt-dlp -f "bv*[width<=1080]+ba/b" --js-runtimes node --merge-output-format mp4 -o "ref/%(id)s.%(ext)s" <URL>
```

Two traps, both silent: `--extractor-args "youtube:player_client=android"` can cap the result at **360p**, and
`-f "bv*[height<=1080]"` **discards a 1080×1920 stream**, because on a vertical video the *height* is 1920. Select
by `width`. Verify what you got with `ffprobe` before measuring it.
