# BRIEF — <product>, a <length> motion-graphics film, <aspect>, no narration

Copy this and fill the angle brackets. Written for a long product film where speech is absent, so the picture and
the typography carry every claim — the shape is wrong the moment narration is assumed.

## The film

`out/<name>.mp4` — **<W×H>, <fps> fps, between <min> and <max>**, H.264 + AAC. **No TTS narration.**

The subject in one sentence, the audience, and the platform. Then the one thing the film must be true to — the
product's own promise in the manufacturer's words, which no shot may contradict.

## The supplied material

Path, what it is, its licence status, and the exact command that measures it before anything is built (a turntable
check, an asset audit, a resolution and alpha check). **Say which assets are supplied and that everything else is
the builder's to make** — otherwise a builder either invents replacements for good material or leaves the film
empty waiting for more.

## Structure — the chapter map

A film past ~90 seconds needs chapters or it becomes one texture. Give a table, and say the proportions are the
point and the titles may be rewritten:

| # | ~time | chapter | what carries it |
|---|---|---|---|
| 1 | 0:00–0:30 | cold open | no logo, one element, a beat |
| 2 | … | the core mechanism | the diagram nobody else draws |
| 3 | … | the numbers | figures as kinetic type, every one sourced |
| 4 | … | the material / structure | cut-away drawn for this film |
| 5 | … | the differentiator | the thing the competitor cannot say |
| 6 | … | the shape | the one place the supplied hero material is allowed to be itself |
| 7 | … | the lineage / provenance | stated only as the maker states it |
| 8 | … | end card | name, key figure, marks |

Rules that go under the table: every chapter gets a title on a beat; **no supplied asset may be the only picture**
for a whole chapter (crop into the masters for macro detail, alternate with diagrams and full-bleed type); and the
last chapter needs the biggest event, not a fade.

## Information from the internet — sourced, not remembered

- Gather the facts yourself, then **prove them in a table**: every on-screen figure and the URL that supports it.
- Prefer the maker's own spec or press pages; a secondary source is labelled as such.
- **Never invent a number.** Two sources disagreeing means the maker's figure on screen and the discrepancy noted.
- State the model year being described and stay consistent with the supplied assets.
- Anything that cannot be sourced stays off screen.
- Marks, wordmarks and product geometry are never redrawn, recoloured or warped; the object moves only as a rigid
  body — push, crop, rotate, parallax, light sweep.

## Music — composed, not licensed

BPM and time signature with the arithmetic spelled out (`bars × beats = seconds = frames`), the instrumentation
layers, and **the arc**: which chapters build, where it peaks, where it breathes. Name the failure explicitly —
*one loop for the whole film is the failure mode* — and require the instrumentation map to change at least six
times, declared in `DESIGN.md`. Add sound design per chapter (whoosh on cuts, a click on each figure, a scrub on
the material chapter, an impact on chapter cards). State the loudness target with its override reason when it is
not the skill default.

## Prove it — `ADMIT.md`, measured on the encoded file

1. `ffprobe`: duration inside the window, frame size, rate, audio present.
2. `ffmpeg -v error -i out/<name>.mp4 -f null -` prints nothing.
3. `freezedetect=n=0.004:d=1.5` → zero holds. **A long film without narration fails here first**, because
   re-using one composition reads as a slideshow.
4. `silencedetect=n=-40dB:d=1.5` → zero, except a break declared with its timecode.
5. `ebur128`: integrated LUFS and true peak against the target.
6. **Supplied-asset proof**: the measurement of the supplied set, the correction applied, and every place each
   asset is used with its speed or rate.
7. **Fact proof**: the figure → URL table, model year stated.
8. **Brand proof**: which pixels are untouched and by what mechanism, plus the list of transforms applied.
9. **Chapter proof**: the chapter times measured on the delivered file, and the instrumentation map of the score.
10. Look at **≥ 20 finished frames at full size with your own vision**, at least two per chapter. Fix and
    re-render if a frame is cluttered, the type is unreadable at phone size, the subject is cropped through the
    product, or the frame is a wash of the brand colour.

Token usage comes from the harness log; never estimate it. Final message: path, duration, size, chapter count,
the three strongest moments, and the three weakest things about the film — not a synopsis.
