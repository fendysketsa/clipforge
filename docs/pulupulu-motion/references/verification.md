# Verification and gates

Path: both
Owner: delivery gates and every threshold value



What has to pass, in what order, which tool proves it, and what each tool cannot prove.

Part of the `pulupulu-motion` skill. The entry point and the gate table live in `SKILL.md`.

## The gate table — the only place these numbers live

Every other page links here instead of restating a threshold. A second copy of a number is how one film
passes a gate that another fails.

| gate | performance path | graphics path |
|---|---|---|
| decode | `ffmpeg -v error -i film.mp4 -f null -` prints nothing | same |
| freeze | `freezedetect=n=0.004:d=1.0` → **zero** holds | `freezedetect=n=0.004:d=1.5` → zero holds, or a declared deliberate hold |
| silence | `silencedetect=n=-40dB:d=1.5` → zero, except a declared thinking beat | `silencedetect=n=-40dB:d=1.5` → zero |
| loudness | integrated `I = -16` LUFS, true peak ≤ −1.5 dBTP | same |
| acting | per-beat frame strips + region-change measure (`scripts/stickman_qa.py`) | not applicable |
| balloons | no balloon over any head, none over another balloon, inside the safe rect (`references/chat-balloons.md`) | only if balloons are used |
| duration | within 0.5 s of the brief | same |

Performance path is the tighter freeze window because an acting beat that holds a full second is dead
performance; a graphics film legitimately holds a composed shot, provided the hold is declared.

### Probe a file before you judge it — an unfinished mux is not a broken film

`moov atom not found` from `ffprobe`/`ffmpeg` means the MP4 is **still being written**, not that it is corrupt:
the `moov` atom is written last, so a mux in progress is a large file with no readable duration. The same shape
appears with `-movflags +faststart`, where the output sits near zero bytes until the encode completes.

- **Watch the size change, then re-probe.** A file that grew between two reads is unfinished. A 48 MB film that
  probed as `Invalid data` became a clean 73.8 MB / 8:33 file a couple of minutes later.
- **Only verify a file whose `ffprobe` returns the expected duration**, and take the integrity hash from that
  moment. Verifying an intermediate file invents defects that do not exist and misses the ones the final pass
  introduces — including a delivered file that silently changed under you.
- **The rule applies to a delegated agent's output too.** Its runner can still be muxing after it prints a done
  message; poll size and duration before either praising or condemning the build.

### Calibrate a gate against an input it must reject

A gate that has never rejected anything is not evidence, it is decoration — and a false pass is worse than no
gate, because it certifies. Before trusting any checker here, feed it a **known-bad control** and require a
failure. Three shapes, one per kind of gate:

| gate | control it must reject | what a broken gate looks like |
|---|---|---|
| motion / acting (`scripts/stickman_qa.py`) | a 3 s clip built from **one frozen frame** (`-loop 1 -i still.png`) | it reports `moving=True` on the control, so its pass on the real film means nothing |
| prompt set (`scripts/asset_prompt_audit.py`) | a copy with the detail plate deleted, `"same as before"` inserted, a camera line stripped of its shot size | it returns PASS on the mutilated copy |
| balloon layout (`scripts/bubbles.py --selftest`) | a request placed straight over the listener's head, and one over the speaker's own | it only ever tests cases that already pass |

Two calibration rules learned the hard way:

- **Measure the right statistic for the question.** A mean difference over a wide region cannot answer *did the
  figure move* — the empty background dilutes it, and a visibly acting film scored as frozen. Use the **fraction
  of the region whose pixels changed** plus the mean delta, and set the threshold from the control (0.0 % / 0.0
  on a frozen clip), not from taste. Line art is thin, so a high percentile of the region is dominated by
  untouched background and is the wrong statistic too.
- **Match enumerated tokens longest-first.** A shot-size check that scanned `wide` before `medium-wide` recorded
  a medium-wide plate as `wide`, so two neighbouring plates at the same size went undetected. Any gate that maps
  free text onto a fixed vocabulary must try the most specific member of that vocabulary first.

When a control exposes a bug, fix the gate — never soften the threshold until the control passes.

## 12. Verification & Independent Review

- **Machine checks (`om check` + `om qa --sheet`):** Verify 0 errors, no single-frame pops, no dead stretches (> 2 bars), no blank frame 0, clean loop seam (`--loop`), readable contrast, and valid audio spectrogram.
- **Cold Review Protocol:** Never grade your own film "done" from `om check` alone. Have an independent reviewer (or fresh context) watch the **final MP4** with only the original brief, confirmed direction, `treatment.md`, and a source table for on-screen text/numbers. Mandatory review question: *"At which timestamp does attention drop or feel flat?"*
- **Second opinion from another model, when the gates are green and it still reads cheap.** Six to eight stills pulled from the *delivered* MP4 plus the generator script in one folder, a brief that demands ranked fixes with px/colour/easing numbers, and a read-only instruction: `agy --print "<brief>" --model <id> --add-dir <folder>`, ids from `agy models` (they encode effort — never combine `--model` with `--effort`). Put `qa.txt` and `timeline.json` in that folder as well, and run a frontier model as a background job writing to a file — ten images plus the generator outlive a foreground call, and a call killed at the timeout saves nothing. **One round, then converge — this user pays for both sides.** A critique exchange is expensive and its
marginal value collapses after the first answer: send the stills, the generator and one brief that states what you assembled and what you believe is wrong, demand numbers back (px, seconds, easing, colour), apply everything you accept in a single pass, re-render once, and report what you took and what you rejected. Agree the convergence point with the user before starting rather than announcing rounds. Run that call as a background job writing to a file — ten images plus the generator outlive a foreground call, and a call killed at the timeout saves nothing. Two frontier models in parallel on the same brief is the exception worth paying for, because their disagreements mark where the craft decision actually is: a craft-focused model will rebuild your shading and miss that your material is fake, an editorial-focused one will hand you licensed sources and corrected facts and leave the frames plain. **Attach the frames with `-i` on `codex exec` and feed the brief on stdin** (`codex exec -m <model> -c model_reasoning_effort="medium" -i f1.png -i f2.png < prompt.txt > review.md`) — `-i` is variadic, so a prompt passed as an argument after the images is swallowed as another filename and the run exits with `No prompt provided via stdin`. Codex also runs long enough to need a background job with `notify`, like the `agy` calls. This finds what no checker sees: a blanket `scale()` cropping artwork, a caption scrim ending in a razor cut, labels off centre from a `translateX` fighting a GSAP `y`, `back.out` bouncing through floors, an SVG `pop` painting from `(0,0)`, and — on one film — twelve *tetrominoes* drawn on the beat that says *pentominoes*. Recipe and the full list: `references/visual-craft.md` §11.
- **Fix defects by layer:** Looks cheap → fix craft/type/lighting/materials (not camera). Looks boring → fix pacing/shot-scale/contrast/score (not decorative particles). Unclear → fix focal hierarchy/identity anchors/read time (not extra voice-over). When the complaint is "the visuals look weird and bad" and every machine gate passed, the defect is craft — re-derive the rules from `references/visual-craft.md` (its §10 lists the sources) and rebuild the shading, depth and composition of each scene; do not patch the eases, and do not defend the frame with the fact that `om check` is clean.

---

## 14. Verification gate order (what has to pass, in order)

1. `scripts/lang-audit.py film/index.html --lang <en|id>` — no leftovers from another language (§3c).
2. Shot list linted (`scripts/art-motion/storyboard_lint.py`) when the film uses the art path.
3. `pulupulu check .` — 0 errors.
4. Per-phrase ASR gate on the narration (`tts-intonation` §6), then the same check on a slice of the **final MP4**. Use the shipped command, not hand-rolled curl: `python scripts/deepseek_voice.py gate beats.json --voice <stella|tide>` synthesises, transcribes each phrase back and compares — **exit 1 means do not render**, and the fix is always the copy (a fragment becomes a full sentence, a loanword gets outnumbered), never the audio. Then `asr` on three or four 4 s slices of the delivered file proves the mix did not bury the voice.
5. `pulupulu qa <file>` — **Check digits and proper nouns as tokens, not as similarity**: a 0.6 transcript match passes a line that says the wrong year or the wrong surname. `no single-frame pops` is a gate; `still for ≥1 s` and `flat opening` are reading notes, answered with argument not with random motion.
6. One frame per scene opened and looked at **at full size**, plus 1× playback with sound. Never judge a 1080×1920 frame from a contact-sheet thumbnail: at 300 px wide, pale-toned art and a caption scrim read as blank paper, and the seams between pasted tiles read as extra content — a montage made one film look like it had a two-thirds-empty frame and three backgrounds visible at once, when a column scan showed art down to 94 % of the frame height and a single layer per frame. When a framing looks broken, measure it before rewriting it: scan one image column for rows that differ from the paper colour and compare that against the layout you intended. Also `pulupulu still . --at <one time> --out .om/name` writes a **file** at that path, not a directory; pass two or more times (`--at 2,12`) whenever you expect a folder of stills.
7. `references/ui-motion/reference/quality-checklist.md` — the five axes (visual, technical, emotional, performance, accessibility) walked once, out loud, on the finished film.
8. **Two objective slop gates on the delivered file, always when someone else built the scenes.** `ffmpeg -v info -i out/film.mp4 -vf "freezedetect=n=0.004:d=1.5" -f null -` lists every hold longer than 1.5 s, and `ffmpeg -v info -i out/film.mp4 -af "silencedetect=n=-40dB:d=1.5" -f null -` lists dead air over 1.5 s. Zero `freeze_start` and zero `silence_start` is the pass; a hit names the second to fix. A delegated build asserts "nothing is static" in prose — this counts it, takes seconds, and does not depend on the builder's own QA heuristics or on its definition of motion.

## Motion and audio gates, as numbers

Gates that produce a number beat gates that produce an opinion. Run all four on the delivered file, not on the
project:

```sh
# 1. nothing frozen
ffmpeg -v info -i out/final.mp4 -vf freezedetect=n=0.004:d=1.5 -f null -
# 2. no dead air under the picture
ffmpeg -v info -i out/final.mp4 -af silencedetect=n=-40dB:d=1.5 -f null -
# 3. the mix is where you think it is
ffmpeg -v info -i out/final.mp4 -af ebur128=peak=true -f null -     # aim ≈ −16 LUFS, peak under −1 dBFS
# 4. the voice is actually in the file, saying the script
ffmpeg -ss 18 -t 10 -i out/final.mp4 -vn -ac 1 -ar 24000 /tmp/asr.wav
python scripts/deepseek_voice.py asr /tmp/asr.wav
```

- **Report frozen seconds and the longest hold**, not "it moves". Under ~10 % and a longest hold that is a designed
  end card is normal; anything else goes back to `render-traps.md` §"A long timeline that is 90 % static".
- **When the mix misses — ~−19 LUFS with a true peak above 0 dBFS is the common shape from a raw TTS track —
  fix it on a remux, never a re-render.** Measure once, then apply those measurements with `linear=true` so the
  gain is one constant and the performance is untouched:

  ```sh
  # 1. measure (read input_i, input_tp, input_lra, input_thresh, target_offset)
  ffmpeg -v info -i assets/voice.wav -af "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json" -f null -
  # 2. apply, picture copied through untouched
  ffmpeg -y -i out/film.mp4 \
    -af "loudnorm=I=-16:TP=-1.5:LRA=11:measured_I=-19.2:measured_TP=1.0:measured_LRA=3.5:measured_thresh=-29.6:offset=0.3:linear=true" \
    -c:v copy -c:a aac -b:a 192k -ar 48000 -movflags +faststart out/final.mp4
  ```

  Then re-run the `ebur128` gate on the output (it should read −16 LUFS, peak near −1.4 dBFS). A true peak above
  0 dBFS is audible clipping on a phone speaker and no gate in the table reports it as a failure, so it ships
  silently unless you read the peak column.
- **Spot-check the narration with ASR at two points**, one early and one late, and paste the transcript into the
  manifest. It proves three things at once that no ffprobe can: the voice survived the mux, it is the right language,
  and it is saying the script — not a placeholder or a silent track with music over it.
- **Do not trust the author's own numbers.** Both agents above shipped manifests claiming a clean freeze check while
  the file was 82–93 % frozen; the check had been run on a slice, or not at all. Re-run the four commands yourself;
  they cost seconds.

## The last gate: compare your numbers with the reference's

If the brief named a reference, the film is not verified until the two sets of measurements sit in one table — see
`references/measuring-a-reference.md` for the method and the columns. Three comparisons catch almost everything:

- **cuts per minute and average shot length** — is the film the same *kind* of film?
- **mean and p90 motion (MAD)** — if our floor is far below the reference's, our holds are longer and it will look
  like a slideshow next to it, however good the frames are.
- **integrated LUFS** — 2 dB quieter than the reference reads as "flat" on a phone speaker even though nothing clips.

Difference is allowed; an unexplained difference is not. Either match the reference or say in the manifest why this
film departs from it.
