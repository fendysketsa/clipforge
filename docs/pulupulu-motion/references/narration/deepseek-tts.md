# DeepSeek TTS: the whole contract, and how to build prosody on top of it

DeepSeek's speech API is small on purpose: text in, WAV out. It gives you no SSML, no speed, no pitch,
no word timings and no voice cloning. A motion film needs all five. This document is how the gap gets
closed — one phrase at a time, measured, then proven by transcription.

Companion tool: [`scripts/deepseek_voice.py`](../../scripts/deepseek_voice.py) — `probe`, `speak`, `cost`,
`lay`, `beats`, `asr`, `gate`. Method for the prosody part lives in the **`tts-intonation`** skill.

---

## 1. What the API does and does not do

| Capability | Available | Consequence for a film |
|---|---|---|
| Text → speech | yes | one phrase per request |
| Voices `stella` (female) / `tide` (male) | yes | pick one per film; `voice` per line is allowed |
| WAV out (or raw 16-bit mono PCM @ 24 kHz) | yes | 24 kHz mono is the working format everywhere below |
| Language auto-detection (id/zh/yue/en/ja/ko/ms/ar/th/vi) | yes, and it can misfire | see §7 — this is the #1 source of silent failures |
| **SSML** | **no** | prosody comes from segmentation (§6) |
| **Speed / rate** | **no** | retime locally, ≤ ±8 % |
| **Pitch** | **no** | shape with ffmpeg after synthesis, ≤ ±4 % |
| **Word / phoneme timings** | **no** | measure the audio, never assume (§6) |
| **Voice cloning / custom voice** | **no** | casting is a choice between two voices |
| Resume a partial request | **no** | a failed request is re-sent whole |
| ASR with word timings | **no** (text + `duration_ms` only) | the gate is text-level, not word-level |

Anything not in that table is something the pipeline must do itself. Do not write a plan that assumes
otherwise — the API silently ignores parameters it does not implement, which is worse than rejecting them.

---

## 2. Auth and key hygiene

```
Authorization: Bearer $DEEPSEEK_API_KEY
```

- The key lives in the environment (`~/AppData/Local/hermes/.env` on this machine), never in a script,
  a commit, a log line, or a chat message.
- Print the **length**, never the value: `key: present (35 chars, value never printed)`.
- When a command needs it, export it in the same shell line rather than pasting it into a history-visible
  argument: `export DEEPSEEK_API_KEY="$(grep -m1 '^DEEPSEEK_API_KEY=' ~/.env | cut -d= -f2-)"`.
- A 401 is an auth problem, not a text problem: check the variable is exported in *this* shell before
  touching the copy.

---

## 3. Endpoints

```http
POST https://api.deepseek.com/v1/tools/tts
Content-Type: application/json
Authorization: Bearer $DEEPSEEK_API_KEY

{"text": "Your site is down.", "voice_id": "tide", "format": "wav", "filter_markdown": false}
```

- `format`: `wav` (default) or raw PCM (`pcm`, 16-bit mono 24 kHz). `wav` for files, `pcm` when feeding
  a player directly.
- `filter_markdown`: strips markdown syntax before speaking. Leave it on if the copy table contains
  `**bold**` or `#` markers; leave it off if a literal `*` is part of the words.
- Response body is `audio/wav` (~170 KB for a 3.7 s line). **A body ≤ 44 bytes is a failure**, not a
  short line — the 44 bytes are the WAV header with no samples.
- Streaming form `wss://api.deepseek.com/v1/tools/tts` emits `pcm`/`opus` frames for live read-aloud.
  A rendered film does not need it; do not use it just because it exists.

```http
POST https://api.deepseek.com/v1/tools/asr
Content-Type: multipart/form-data   (field: file)

-> {"text": "...", "duration_ms": 2400}
```

ASR is text + duration **only**. There are no word or phoneme timings, so caption karaoke must be driven
by measured phrase boundaries from your own timeline, not by ASR.

---

## 4. Limits and cost

| Limit | Value | What to do |
|---|---|---|
| Billed characters per request | 10,000 | split the script into lines long before this |
| Request body | 64 KiB | a 10k-character line with JSON overhead is already over |
| Audio length per request | ≤ 30 min | irrelevant for a short film |
| Parallel requests in flight | 50 | per-line parallel synthesis is fine; do not unbounded-thread it |
| Price | $0.45 / 10,000 billed characters | a 60 s film ≈ 700–900 characters ≈ **$0.03–0.04** |

Check before spending, especially when iterating on copy:

```sh
python scripts/deepseek_voice.py cost beats.json --expand en
# 16 phrase(s) · 812 billed characters · ~$0.0365 per full run
```

**Billed characters are the characters sent**, so every re-run costs again *unless* the cache hits
(§5). Speeding up is therefore a caching problem, not a parallelism problem.

---

## 5. Cache: the reason iteration is cheap

Each phrase is cached under a hash of `text|voice`:

```
assets/.tts-cache/003-9f1c2ab77d41e0.wav
```

- Editing one beat re-synthesises **one** beat; the other fifteen come from cache.
- The hash covers text and voice, so changing either invalidates exactly that file.
- The cache is keyed per line index as well, so reordering beats keeps most hits.
- Never ship `.tts-cache/` (it is git-ignored by the skill template) but never delete it during a
  session — it is the difference between a 4-second and a 60-second iteration loop.

---

## 6. Prosody without SSML

The engine cannot be told *how* to read; it can only be told *what* to read, and *where* to stop. So the
prosody is authored in the segmentation and the silences:

1. **Cut the script into phrases of 8–14 words.** A phrase is what one breath says. Never hand over a
   3–6 word fragment (§7) and never a paragraph.
2. **Plan a gap after every phrase** — `0.2 s` inside an idea, `0.5 s` between ideas, `0.9 s` before a
   turn, `1.5 s` after a landing line. The gap is authored data, not a player setting.
3. **Shape each phrase with micro tempo/pitch**, applied after synthesis and kept inside ±4 % pitch and
   ±8 % tempo. Outside that, formants shift and the voice audibly breaks:
   ```sh
   ffmpeg -i in.wav -af "atempo=1.04,asetrate=24000*1.02,aresample=24000" out.wav
   ```
   (`atempo` alone preserves pitch; `asetrate` shifts it. Use both only when you want both.)
4. **Measure every phrase, then lay them out.** The timeline is a *measurement* — never a guess, never
   `len(text)/14` characters-per-second arithmetic.

```sh
python scripts/deepseek_voice.py beats beats.json assets/voice.wav \
    --voice tide --timeline assets/timeline.json --tail 1.2
```

```
b01    0.00 → 3.16  gap=0.5  Between every rail, every thirty nine feet.
b02    3.66 → 5.02  gap=0.9  Your site is down.
b03    5.92 → 6.92  gap=0.4  Core engine.
```

`beats` warns when a phrase measures over the beat budget (`--max-phrase`, default 4.5 s). That warning
means **cut words**, not speed up: a compressed phrase is what "the narration sounds wrong" sounds like.

### Timing is negotiable, sentences are not

If the measured total overruns the brief, in this order: cut beats → extend the film (up to ~15 %) →
tighten gaps to a 0.2 s floor. Never push tempo past 1.08 and never drop a connector to save words — a
dropped connector is what makes the engine read the line as another language.

---

## 7. Language detection: the failure that looks like nothing

The engine auto-detects language per request. When a request gives it too little to work with, it picks
wrong, and the result is not an error — it is confident audio of the wrong language.

Measured on this provider, same voice, one 1.0 s two-word line in a non-English target language:

| Input | Transcript back |
|---|---|
| 1.0 s slice, no padding | `马真，INTP.` — transcribed as Chinese |
| same slice, 0.7 s of silence added before and after | `` (empty) |
| the same content as a full sentence with a connector | clean transcription in the target language |

Three rules follow, and they are not stylistic:

1. **Never hand the engine a fragment.** A 3–6 word line with no function word is read as another
   language. Write a full sentence and cut elsewhere.
2. **Outnumber loanwords.** One English technical term inside three words hijacks the whole phrase's
   phonetics. Either bury it mid-sentence inside native words, or speak the native word and put the
   English term **on screen**.
3. **Pad short slices before ASR.** Under ~2.5 s the ASR re-detects language too; 0.7 s of silence on
   each side fixes it. This applies to the *gate* (§8), not to the delivered track.

---

## 8. The gate: prove the voice said the words

Synthesis "succeeding" proves nothing about intelligibility. The gate synthesises each phrase,
transcribes it back, and compares:

```sh
python scripts/deepseek_voice.py gate beats.json --voice tide --threshold 0.6
```

```
id      meas  match  phrase -> heard
b01    3.16s   0.71  PASS  Between every rail, every thirty nine feet.
b02    1.36s   1.00  PASS  Your site is down.
b03    1.00s   0.00  FAIL  Core engine.
            heard:
2/3 phrase(s) survived the gate (threshold 0.60) · 72 billed chars
```

- Comparison is on normalised words: lowercase, punctuation and possessives stripped, filler words
  (`the/a/is/of…`) ignored, fuzzy on word prefixes so `railroad`/`railroads` matches.
- `0.60` is the default threshold. Numbers and proper nouns are the usual reasons a line sits at 0.7–0.8;
  a line under 0.4 is a real failure.
- **Exit code 1 means do not render.** Fix the copy: fragment → full sentence, loanword → outnumbered or
  moved on screen. Then re-run; the cache keeps the lines that already passed free.
- Run it on the **final mixed file** too (`asr` on a 4 s window at three or four points): the gate proves
  synthesis, the window check proves the mix did not bury the voice under music.

---

## 9. Digits, or the words for them

The engine reads what it is given. `502` is read *five hundred two* — wrong for a status code, fine for
a temperature. Decide per token, and write the decision into the copy table so the caption and the voice
can differ on purpose:

| Token in copy | Spoken form | Why |
|---|---|---|
| status/error code `502`, `404`, port `8080` | digit by digit (`five oh two`, `four oh four`, `eight oh eight oh`) | codes are names, not quantities |
| zero inside a code | `oh` (en) / the local word for zero | `zero` reads as a quantity |
| a number that is the point (`25 %`, `1.4 billion`) | cardinal/percent | it is a quantity |
| `1998`, a year | `nineteen ninety eight` | a year is spoken in pairs |
| **a year in the caption** | voice says `nineteen eighty four`, screen shows `1984` | notation, not transcription — a spelled year splits across karaoke chunks (`In nineteen eighty` / `four,`) and the first chunk reads as the wrong year |
| units (`450 ms`, `3 GB`) | cardinal + unit words | units need to be understood |
| an acronym (`DNS`, `CDN`) | letters, spaced (`D N S`) | unsplit, it becomes a word (`dense`) |

`--expand en|id` rewrites code-like tokens automatically; it is deliberately conservative (2–4 digit
tokens near code words, percentages). Anything else is authored by hand in the copy table.

---

## 10. Mixing the voice into the film

The voice is useless if the score covers it. Working recipe (measured, not guessed):

```
voice  : loudnorm I=-15 TP=-1.5 LRA=11        → asplit → apad to the film length
music  : volume 0.20–0.30                     → sidechaincompress by the voice
                       threshold=0.02:ratio=12:attack=5:release=400
mix    : amix normalize=0 → alimiter 0.95 → aresample 48000
```

Then `ffmpeg -i render.mp4 -i mix.wav -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k -shortest`.
Full commands and the ducking parameters live in `SKILL.md` §10.

Final check, always on the delivered file: **−14 to −15 LUFS integrated, peak ≤ −1 dBFS**, and the ASR
window check above returns the right words.

---

## 11. Error table and retry policy

| Symptom | Meaning | Action |
|---|---|---|
| `400` with empty body | empty text | the copy table had a blank phrase |
| `400` `Content Exists Risk` | provider-side content filter tripped | rewrite the phrase; do not retry |
| `401` | key missing or not exported in this shell | check the variable, not the text |
| `429` | too many requests in flight | back off exponentially; cap parallelism |
| `500/502/503/504` | provider busy | retry with backoff 2, 4, 8 s |
| body ≤ 44 bytes | cut-off response | treat as failure and retry — never write it to the track |
| audio but ASR returns empty | slice too short, or voice buried by music | pad the slice; check the mix |
| ASR returns another language | fragment, or a lone loanword | rewrite the line as a full sentence |
| same line transcribes differently every run | ASR language detection on a short slice | pad to ≥ 2.5 s, then treat as an ASR artefact and flag the timestamp |

The tool retries `429/5xx` three times with doubling backoff and never retries `400` (retrying a content
filter just burns money). Exit code `3` = provider error after retries.

---

## 11b. A take with a duration that is an outlier is a broken take, not a long sentence

Observed on a real production: a 54-character line came back as **22.7 s with 8.5 s of silence inserted after the
first sentence**, twice, and **editing a few characters to break the cache did not fix it**. The audio was
technically valid, the text was right, and the only symptom was duration.

So when one phrase measures far longer than its word count predicts:

1. **Run `silencedetect` on that single wav first** — `ffmpeg -i take.wav -af silencedetect=n=-40dB:d=0.8 -f null -`.
   A silent span inside the take is the signature; a genuinely long sentence has no internal silence.
2. **Split the phrase by sentence and synthesise the parts separately, then concatenate locally.** That fixed the
   case above: two clean parts joined to a 9.4 s take.
3. **Do not** retry the same text hoping for variance, and do not "fix" it by editing words — that spends calls on
   a cache miss and usually reproduces the same fault.

Add the measured seconds to the timeline only after the take is clean; a silent tail inflates the film and the
`silencedetect` gate at delivery then fails for a reason that looks like a mixing problem.

## 12. Checklist before the track is used
1. `probe` passes for the chosen voice.
2. `cost` printed and sane; no phrase over 4.5 s and none under 3 words.
3. `beats` produced **`timeline.json` from measurement**, and the picture build reads that file — no
   invented times.
4. `gate` exits 0 (every phrase ≥ threshold), and any rewrite went into the copy table, not into post.
5. Copy table and captions are **verbatim identical**; only notation differs (code on screen, spoken form
   in the voice).
6. Mix hits −14/−15 LUFS with peak ≤ −1 dBFS, and the ASR window check on the final MP4 returns the
   expected words.
7. `.tts-cache/` is not committed; the API key appears in no file, no log and no commit.

<!-- related-skills -->

---

**Where this fits** — part of the **`pulupulu-motion`** skill.
[Skill index](../../SKILL.md) · [Art library index](../art-motion/INDEX.md)

Handoffs and neighbouring skills (narration timing, merging another library, rights review, sourcing a reference video, 3D or footage shots, type-first films): `references/art-motion/INDEX.md`.
