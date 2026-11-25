# Sound, music and narration synthesis

Owner: music, sfx and the mix


The sixteen musical worlds, composer mode, sound effects and levels, and the DeepSeek TTS route into the timeline.

Part of the `pulupulu-motion` skill. The entry point and the gate table live in `SKILL.md`.

## 10. Sound & Music

### 16 Musical Worlds (Pick by Product, Never Reuse Last Film's Band)
1. **Pulse minimalism** (130–150 BPM, 3/4 or 4/4, no drums, interlocking `marimba` + `piano` + `strings` + `pizz`) — AI, dev tools, infra, data.
2. **UK garage / 2-step** (128–134 BPM, `808`+`pop` skip beat, `rhodes` m9, `sinebass`, `pluck`) — urban, social, consumer mobile apps.
3. **Minimal techno** (122–128 BPM, 4-on-floor `808`, `synbass` 16ths, `sqlead` stabs, filter builds) — speed, infra, precision.
4. **Drum and bass** (170–176 BPM, `acoustic` breakbeat, `saw` reese, `warmpad`, `bell`) — extreme speed, sport, gaming.
5. **Funk / disco** (108–120 BPM, `acoustic` kit, octave `bass`, `clav`, `brass`) — joyful creators, design tools, playful consumer.
6. **Lo-fi hip-hop** (76–90 BPM, `lofi` kit, `rhodes` 7ths, `bass`, `vibes`) — notes, reading, calm productivity.
7. **Trap half-time** (136–150 BPM, `808`+`sub808`, rolling hats, `bell`) — hype, game launches (not default tech).
8. **Synthwave** (96–112 BPM, `gated` kit, `sinebass` octaves, `saw` arp, `sqlead`) — retro, nostalgia, games.
9. **Cinematic orchestral** (80–100 BPM, `cinematic` taiko, `lowstr` ostinato, `horn`, `brass`) — big model releases, hardware, historic scale.
10. **Lyrical piano & strings** (72–96 BPM, 3/4 waltz, Lydian #4, `piano` + `strings` + `harp` + `flute`) — warm, human, family, wonder.
11. **Jazz trio** (120–180 BPM swung `A3/ B/`, `acoustic` brushes, walking `bass`, `piano`, `vibes`) — writing tools, craft, warm premium.
12. **Acoustic folk** (92–112 BPM, `folk` stomps/claps, `guitar`, `uke`, `glock`) — friendly small teams, cute/everyday consumer.
13. **Chiptune** (140–170 BPM, `chip` kit, `tri` bass, `chip` arp lead) — pixel brands, games, playful dev tools.
14. **Ambient glass** (60–80 BPM, no beat, `warmpad`, `glass`, `kalimba`, `sinebass`) — privacy, wellness, meditative loops, quiet idents.
15. **Chinese-style electronic** (88–104 BPM, tight `pop` kick + `808` hats, `guzheng`, `dizi`, `erhu`, `sub808`) — Chinese culture, tea, heritage.
16. **Amapiano** (110–116 BPM, soft 4-on-floor, shakers + rim, `sub808` log drum, jazzy `piano`) — fashion, music, social launches.

### Composer Mode (`<script type="text/vnd.abc" id="om-score">`)
- Spot 3–5 sync points (`!mark:hook!`, `!mark:turn!`, `!mark:stop!`, `!mark:drop!`, `!mark:logo!`) matching `scene:<id>` timeline labels. Build picture on `OM.music({ bpm })` + `OM.beat(n)` for 0% tempo bend (or keep tempo bend < 8% by adjusting bar counts / `3/4` bars when scoring pre-cut film).
- **ABC syntax & rules:** Standard `X:1`, `T:`, `M:4/4`, `L:1/8`, `Q:1/4=120`, `K:Em`, `V:ID inst=... gain=... role=melody`. Every bar in every voice must sum to the exact meter (`om sound` prints `warning score:` if off — fix every warning!). Inline `[K:]` affects all voices; `[M:]` must be written in every voice.
- **Instruments:** `piano`, `strings`, `violins`, `violas`, `celli`, `basses`, `violin`, `trem`, `lowstr`, `pizz`, `stacc`, `harp`, `horn`, `brass`, `flute`, `dizi`, `erhu`, `guzheng`, `guitar`, `uke`, `rhodes`, `epiano`, `vibes`, `marimba`, `kalimba`, `glock`, `bell`, `glass`, `pad`, `warmpad`, `supersaw`, `saw`, `sqlead`, `synpluck`, `pluck`, `chip`, `tri`, `clav`, `bass`, `synbass`, `sub808`, `sinebass`.
- **Drums:** `inst=drums kit=pop|acoustic|808|cinematic|lofi|gated|chip|folk`. GM map: `C,,` kick, `^C,,` rim, `D,,` snare, `^D,,` clap, `^F,,` closed hat, `^A,,` open hat, `A,,` tom, `^C,` crash, `^F,` tamb, `^A` shaker.
- **Decorations:** `!pp!..!ff!`, `!crescendo(!..!crescendo)!`, `!diminuendo(!..!diminuendo)!`, `!accent!`, `!fermata!`, `!rit(!..!rit)!`, `!ped!..!ped-up!`, `!mark:name!`, `!hit!` (impact+subdrop), `!rise(!..!rise)!`, `!filter(!..!filter)!` (build), `!stop(!..!stop)!` (tape stop), `!stutter(!..!stutter)!` (beat repeat).
- **Arrangement craft:** Write a 3–4 note **motif** stated early, developed mid-film, and resolved as the sonic logo. Separate roles by register (no two parts clashing in same octave). Leave an empty half-bar/bar before the drop. Lift up a whole step (or relative major) at the reveal.
- **Fallback:** `OM.music({ product: 'devtool'|'ai'|'hardware'|'consumer'|'cute'|'creative'|'game'|'data'|'explainer'|'calm'|'guofeng'|'hype', style, drop: 'sceneId', ending: 'ring'|'button'|'stop', floor: 0.55 })`.

### Sound Effects (`OM.sfx`) & Levels
- `OM.sfx(name, at, { gain, pan, note, pitch, dur })` returns `at`. Place `at` on the **visual landing frame** (~30–45% into an `expo.out` or `back.out` tween, not the start!). For `riser`/`reverse`, `at` is the swell end.
- Effects: `pop`, `tick`, `click`, `type`, `shutter`, `thud`, `paper`, `stamp`, `draw`, `count`, `boing`, `slide`, `whoosh`, `whip`, `impact`, `ding`, `chime`, `sparkle`, `hit`, `glitch`, `subdrop`, `reverse`, `riser`.
- Vary repeats: pan 4 cards L→R; climb `note: i + 1` on `pop`/`ding`. 8–15 hits per 30 s; max 1 `impact` and 1 `chime`.
- **Levels:** Social master at −14 LUFS (−1.5 dBFS peak, sub-30 Hz cut); music ducks −12 LU under voice.

---

## 10a. Writing a score from scratch, and measuring it before a listener does

When the film has no narration and the composer is your own synthesiser rather than the ABC route, the score is a
piece of audio engineering with two failure modes a client names immediately and a gate can catch first:
**"the sound is weird"** and **"it is just a drone"**. Both are numbers.

```sh
python scripts/score_audit.py assets/score.wav --lufs -14 --min-onsets 14
```

It prints loudness and true peak (from ffmpeg's own `ebur128`), a nine-band spectral tilt, the share under 250 Hz
and above 4 kHz, onset density, crest factor, sample-level click count and DC offset — and exits 1 on any failure.
Run it on every candidate score, and again on the audio decoded out of the delivered MP4.

### "Weird" is hiss-forward, clicked and bodyless

| reading | what it means |
|---|---|
| >30 % of the energy above 4 kHz, <25 % under 250 Hz | hiss and cymbals with no body — the single most common cause of a score reading as "weird" |
| hundreds of sample-level spikes (|Δsample| > 0.25) | digital clicking, not music: an envelope or a noise burst starts or stops inside one sample |
| any DC offset | a synthesiser voice with no high-pass on the bus |

Every envelope gets an attack of **≥4 ms** (a squared sine ramp, not a step), and every noise layer is
**band-limited** — raw white noise is a hiss generator, and a band-passed noise burst is a snare.

### "Drone" is a low onset count, not a low tempo

Measure onsets as spectral-flux peaks per second. Calibration from three versions of the same 30-second brief:

| version | onsets/s | under 250 Hz | above 4 kHz | verdict |
|---|---|---|---|---|
| pad bed + sparse kick | 12.0 | 43.8 % | 19.9 % | reads as a drone however loud it is |
| the original patch | 9.4 | 23.5 % | 39.7 % | weird *and* droning |
| rhythm-led 140 BPM | **16.4** | 26.4 % | 16.8 % | energetic |

**A sustained pad cannot be fixed with volume.** Energy that never stops dominates the average spectrum, so what
the listener hears as "one hum" is really *nothing striking*. What raises onset density is percussive content:
16th hats, clap on the backbeat, a 16th bass with a filter envelope per note, off-beat chord stabs, tom fills — and
the pad either disappears or appears only under the drop.

**Sidechain the kick into bass and harmony** (duck ~60 % with a short release, one duck per kick). That pumping is
the mechanical difference between "a track" and "a chord with a thump"; lock a 55 Hz sub layer to the same kick
positions for weight.

### Gain-riding does not rebalance a mix; a spectral tilt does

Raising the kick and bass gains changed the measured tilt by under 1 %, because the **continuous** elements (the
16th bass line, the stabs, the hats) are present at every instant while the kick is present about a tenth of the
time. Rebalance with a bus tilt instead, and lower the offending voice's own filter:

```python
low_shelf = onepole(mix, 130.0)          # keep the body
high_band = mix - onepole(mix, 3800.0)   # the hiss band
tilted = mix + low_shelf * 1.15 - high_band * 0.62
```

and drop the acid/pulse bass cutoff (700–1100 Hz reads as midrange buzz; 260–420 Hz reads as bass).

### Do not squash the transients you just built

A hot pre-normalise followed by a hard look-ahead limiter took crest factor from 14.5 dB to 6.1 dB on this exact
score — every drum hit flattened into the bed. Normalise to a modest RMS, limit gently (look-ahead ~2 ms, ceiling
−1.2 dB), and keep a little drive off the bus. Then set the delivered level as a **gain applied after
measurement**, not as a target inside the synthesiser:

```sh
cur=$(ffmpeg -v info -i score.wav -af ebur128=peak=true -f null - 2>&1 | grep -oE 'I: *-?[0-9.]+ LUFS' | tail -1 | grep -oE '\-?[0-9.]+')
ffmpeg -y -i score.wav -af "volume=$(python -c "print(round(-14.0-($cur),2)) 
)dB" score_norm.wav
```

An internal K-weighting approximation is a convenience, never the authority: one written for this job reported
−11.0 LUFS where ffmpeg measured −14.0. Measure with ffmpeg, apply the delta, re-measure.

### "No harmony" and "sounds the same in every scene" are two separate defects

A rhythm-led score can be energetic, clean and still be rejected — once for sounding harsh, once for having no
harmony, and once for being uniform from the first shot to the last. Those are three different measurements.

**Harmony needs a progression, not a root note.** Trailer practice, which is what product films borrow: hold a
**pedal** on the tonic while chords shift above it, then run the driving loop **i – ♭VI – iv – V** (in A minor:
Am – F – Dm – E, where the major V borrows the leading tone and pulls hard home), put a **Neapolitan ♭II** on the
biggest card, raise the whole loop a **semitone** for the climax, and close on a **Picardy third** (A major). Four
chords, used deliberately, beat sixteen random ones.

**Bar equals shot.** Choose the tempo so the grid lands on the edit instead of near it. At 128 BPM a 4/4 bar is
**1.875 s**, so **16 bars = 30.000 s exactly — one bar per shot** on a sixteen-shot cut. Then the arrangement can
change bar by bar: pad thickness ramp, drums entering at bar 3, hook doubled at bar 13, drums out for two bars of
breakdown, strings only in the lift. That is what stops a film sounding uniform.

**Measure "uniform", do not judge it.** Take the RMS of every bar and report the spread:

| score | RMS per bar spread | verdict |
|---|---|---|
| one loop, same layers all the way | < 6 dB | reads as flat across the scenes |
| bar-by-bar arrangement | **18.8 dB** (intro −38 dB → lift −19 dB) | the film has an arc |

**Harshness is 2–5 kHz, and subtraction alone makes it dull.** Cut narrowly in that band, then **add saturation**
so the transient edges round off and low-mid density comes back — the two together, not either alone. Measured on
this score: 2–5 kHz fell from ~18 % to **3.8 %** of the spectrum with the saturation in the chain, and >8 kHz to
5.5 %.

**A −14 LUFS target will clip a dense mix.** Applying the measured gain to a busy score drove true peak to
**0.0 dBFS**. Put a real limiter after the gain (`alimiter=limit=0.82`) and re-measure: the same score landed at
−14.4 LUFS / −1.4 dBFS with crest restored to **15.6 dB** — inside the ad target, no clipping, transients intact.

### A melodic hook makes a product film sound like a jingle

A bell or glockenspiel playing a pentatonic figure in eighth notes is the single fastest way to make an aggressive
product film sound like a TV ident — and, in the wrong market, like a Chinese-style tune. It is not a mixing problem
and no EQ fixes it: **it is the presence of a singable melody at all.**

For a hard product (a superbike, a machine, a tool) the music should be **texture, not tune**. What replaces melody:

| layer | how it is synthesised | what it does |
|---|---|---|
| distorted kick | pitch envelope 150→48 Hz, `tanh(x*3)`, band-passed click | the pulse |
| sub | 41 Hz sine locked to every kick | weight |
| **inharmonic metal** | partials at 1 : 1.71 : 2.43 : 3.19 : 4.11, each with its own decay | struck steel — no pitch you can sing |
| anvil | noise 500–5200 Hz + rings at 1180 and 1873 Hz, saturated | impact accents |
| gated 16th pulse | noise band-passed 700–2600 Hz, 75 ms gate every 16th | the machine-gun spine |
| servo / scrape | swept band-passed noise, amplitude-modulated | mechanical motion |
| drone | detuned saws at A1/C2/E2 through a 220–460 Hz low-pass, saturated | menace and weight |

Keep the arc in **density and noise**, never in a tune: breakdown = pulse and servo only; drop = everything plus a
low flat-II cluster stab. Measured on this industrial pass: RMS spread **25.4 dB** across sixteen bars, 2–5 kHz held
at 13.6 %, above 8 kHz at 1.4 %, zero clicks.

Also worth stating plainly: a spectrum, onset count and crest factor tell you whether a score is harsh, thin, flat
or squashed — they cannot tell you whether it is good. Ask for a direction ("more industrial") and treat adjectives
like *warm, cold, driving, menacing* as parameters (melody present or absent, inharmonic or harmonic, noise or
tone), not as a volume knob.

### When hand-written synthesis stalls, delegate the score — with the rejections in the brief

Five synthesised scores failed in a row on the same 30-second spot (weird, drone, flat, jingle, then "it is bad").
The sixth, written by a different agent given the same brief and the picture, passed the audit first time. The lesson
is not that synthesis is wrong — it is that **a written score needs an ear, and a model without audio feedback is
guessing.** Recognise the plateau early: two consecutive rejections on the *same* axis mean the approach, not the
parameters, is wrong.

What made the delegated attempt succeed, all of it quotable into a future brief:

- **Every previous rejection, verbatim, with its measurement.** "Sounds like a Chinese jingle" is a usable
  instruction; "make it better" is not.
- **The grid, stated as arithmetic.** 128 BPM, one 4/4 bar = 1.875 s, sixteen bars = 30.000 s = one bar per shot.
- **A passing audit as the acceptance criterion**, not an opinion, and the audit script named so it can be run.
- **Permission to use a real generator** if the agent has one, with synthesis as the fallback.

What that pass did that the hand-written ones had not:

| technique | effect |
|---|---|
| strip everything below ~40 Hz (measured 0.41 % left) | the inaudible sub was eating headroom — one hand-written score had 20 % of its energy there |
| narrow **−6.8 dB notch at 3.1 kHz** | cuts exactly where hearing is most sensitive instead of widening a broad dip |
| measure **stereo phase correlation per band** (sub 0.969, mid/high 0.6) | proves the low end survives mono phone playback while the top keeps width |
| report **on-sets per second** as a target (14.93/s) | density, not loudness, is what stops a score reading as a drone |
| RMS per bar for all sixteen bars | the arc becomes a number (18.0 dB spread) instead of a claim |

### Structure the arc against the shot list

Map sections to the actual shot boundaries (build → full → a short breakdown → rebuild → drop on the hero shot →
tail on the end card). Keep the breakdown to a bar or two: a long quiet section is the drone returning. Put an
impact on the drop and on the end card, and a riser into each.

## 10b. Narration with DeepSeek TTS

When the film needs a spoken voice-over and the user has a DeepSeek key, DeepSeek's own speech endpoint is the cheapest path that speaks Indonesian. Same key as the chat models, separate endpoint — the tools live under `/v1/tools/`, not on the chat API.

**Endpoint** `POST https://api.deepseek.com/v1/tools/tts` · auth `Authorization: Bearer $DEEPSEEK_API_KEY` · body `{"text", "voice_id", "format", "filter_markdown"}` · returns `audio/wav` (default) or raw 16-bit mono PCM at 24 kHz. WebSocket `wss://api.deepseek.com/v1/tools/tts` streams `pcm`/`opus` for live read-aloud; a film only needs the HTTP form.

- **Voices:** `stella` (female, default) and `tide` (male). No voice cloning, no SSML.
- **Languages:** detected from the text, never passed — Mandarin, Cantonese, English, Japanese, Korean, Malay, **Indonesian**, Arabic, Thai, Vietnamese. Indonesian copy just works; no language parameter to set.
- **Limits:** 10,000 billed characters and 64 KiB per request, at most 30 minutes of audio, 50 requests in progress per account. A Chinese character bills as 2, any other character as 1. Price US$0.45 / 10k characters (limited-time US$0.225).
- **No speed control and no resume.** A response that ends early is a failure, not a short take — every line has to fit its slot by *writing* to length, not by stretching audio.

### Wiring it into a film

`om voice <dir> --text <file>` uses the system TTS, which is not DeepSeek. To use DeepSeek:

1. Write the script as lines with the time each line must start, e.g. `lines.json` = `[{"text": "Tebak nama buah.", "start": 0.0}, {"text": "Soal pertama.", "start": 2.9}]`.
2. Synthesise, measure and lay the lines on the timeline in one step — `scripts/deepseek_voice.py` (`beats --timeline timeline.json` writes the measured timeline*; `lay` is the simple path; `gate` transcribes every phrase back to prove it was spoken). Each line is cached, so a re-run only pays for changed copy. Full API contract, limits, error table, language-detection traps and the digit-vs-word decision table: `references/narration/deepseek-tts.md`. The old `scripts/deepseek-tts.py` still works and is kept for existing builds:
   ```sh
   DEEPSEEK_API_KEY=… python scripts/deepseek_voice.py lay lines.json assets/voice.wav --voice stella
   ```
   It prints the finished length, warns when a line overruns the `end` of its slot, and writes 24 kHz mono 16-bit WAV ready for FFmpeg.
3. Import it as the recording: `om voice <dir> --audio assets/voice.wav [--fit]`, or mux it directly when the film has no word-level cues (`ffmpeg -i out/film.mp4 -i assets/voice.wav -c:v copy -c:a aac -b:a 192k -shortest out/final.mp4`).
4. Re-run `om sound` afterwards: `om sound` ducks the music under the voice and re-mixes `assets/sound.wav` with narration in place.

**Cues need real timings, so keep the line list as the source of truth.** DeepSeek ASR (`POST /v1/tools/asr`, Ogg Opus or 16-bit PCM WAV, ≤120 s, ≤8 MiB) returns only the transcript plus `duration_ms` — no word-level timings — so it cannot drive `OM.cue` by itself. If a film needs word-accurate cues on DeepSeek speech, either measure them from the line list (TTS speaks a line almost immediately after its start) or align with the CLI's own aligner.

**Failure handling:** `400` = empty text or `Content Exists Risk` (content review — rewrite the line, do not retry); `429` = >50 requests in flight (serialise, one line at a time); `503`/`504` = busy or timed out (retry with backoff, the helper does 4 tries).

---

**Mixing the voice under `om sound`'s music.** `om sound` renders the score at roughly −14 LUFS, which is *louder than a TTS voice*: measure before shipping, because a cinematic score will bury narration and an ASR check will come back empty. The recipe that works — normalise the voice, duck the score with the voice as the sidechain, then sum:

```sh
ffmpeg -y -i assets/sound.wav -i assets/voice.wav -filter_complex "\
 [1:a]aformat=sample_fmts=fltp:channel_layouts=mono,loudnorm=I=-16:TP=-1.5:LRA=11,asplit=2[voice][sc0];\
 [sc0]apad=whole_dur=<film seconds>[sc];\
 [0:a]aformat=sample_fmts=fltp:channel_layouts=mono,volume=0.30[music];\
 [music][sc]sidechaincompress=threshold=0.02:ratio=12:attack=5:release=400[duck];\
 [duck][voice]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95,aresample=48000[out]" \
 -map "[out]" assets/mix.wav
```

**Pad the sidechain, or the picture gets cut.** `sidechaincompress` returns only as much audio as its sidechain has, so a 57 s voice under a 60 s score yields a 57 s mix — and `-shortest` on the mux then silently drops the last 3 s of picture. `apad=whole_dur=<film length>` on the sidechain copy is what keeps the mix (and the video) full length; check `ffprobe` on the muxed file against the render before reporting it.

Then mux onto the silent-ish render with `-c:v copy -c:a aac -b:a 192k -shortest`. Verify with `volumedetect` per segment: voice should sit ~5–10 dB above the score in every stretch that has speech.

**Cache keys in helper scripts must be stable.** Python's `hash()` is salted per process, so a cache named from it never hits and every run re-bills the whole script — use `hashlib.sha1` over the text and voice.

### Short-form narration: the measured target

A viral vertical short measured at **−14.1 LUFS integrated, LRA 1.6 LU, true peak −1.7 dBTP**, with only two
silences longer than 200 ms in a 55 s runtime and **≈197 words per minute** is not an outlier — it is the genre
standard. Fast shorts are loud, dense and breathless; the −16 LUFS / comfortable-pace default of a longer film will
read as slow and quiet beside them.

- Choose the target by genre: **−14 LUFS for a sub-90 s vertical short**, −16 for anything longer or calmer.
- 180–200 wpm with almost no pauses is normal here; when the script measures slower than ~150 wpm, cut words rather
  than speed the voice (`tts-prosody` cannot stretch without artefacts).
- Keep LRA low (1–3 LU). Wide loudness range in a 60 s short means the mix is pumping, not breathing.
- Two silence dips per minute is plenty. Long gaps are where a viewer's thumb starts moving.

**Verify narration by transcription, not by hope.** DeepSeek ASR (`POST /v1/tools/asr`) on 10 s slices of the final mix proves the words actually made it into the file; a whole 60 s file sometimes returns an empty transcript even when the slices transcribe perfectly. Send slices.

**DeepSeek TTS language quirks in Indonesian copy:** a line that starts with a bare name ("Dia Mansa Musa…") gets blended into one word — write "Dia, Mansa Musa, …" and the comma fixes it. Loan words read with English phonetics ("Juli" comes out as *July*) — prefer "bulan ketujuh". Isolated Latin text (a two-word line) can be detected as Mandarin, so always give the voice a full sentence.

---
