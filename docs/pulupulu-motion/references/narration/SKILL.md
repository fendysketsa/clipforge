---
name: tts-intonation
description: >-
  Use when a narration track has to sound spoken rather than read — flat TTS,
  wrong emphasis, rushed clauses, robotic pacing. Controls prosody on TTS
  providers that expose no SSML, speed or pitch parameters (DeepSeek, many
  HTTP APIs) by segmenting the script into phrases, planning pauses, and
  shaping each phrase with measured micro-tempo, pitch and gain.
metadata:
  version: "1.0.0"
  license: "MIT"
---



# TTS intonation

Flat narration is almost never a voice problem. It is a **segmentation** problem: one long sentence handed to a TTS engine comes back as one long breath with a single falling contour at the end. The engine has no idea which word matters.

This skill makes narration carry meaning using only what a parameter-less TTS API gives you: **the text you send, where you cut it, how long you wait between pieces, and how you process each piece afterwards.**

Provider API contract, limits, error and language-detection traps, digit-vs-word table and the `gate` command:
[`deepseek-tts.md`](deepseek-tts.md) · tool: `python scripts/deepseek_voice.py {probe,speak,cost,lay,beats,asr,gate}`.

Provider-neutral. Verified end to end against DeepSeek TTS (`POST https://api.deepseek.com/v1/tools/tts`, voices `stella`/`tide`) — no SSML, no speed control, no pitch control, no word timings.

---

## 1. The one rule

**Prosody is decided before synthesis, not after.**

| Decision | Lever | Effect |
|---|---|---|
| Where an idea ends | phrase boundary | contour + breath |
| Which word leads | phrase order | stress lands on phrase start |
| How much weight | pause length | attention |
| How fast it feels | per-phrase tempo | urgency vs gravity |
| How high it sits | per-phrase pitch | excitement vs seriousness |

If the script arrives as finished sentences, the only remaining knobs are global and every line sounds the same. Cut the script into phrases first.

---

## 2. Phrase rules (write for the voice)

1. **One idea per phrase, 4–12 words.** Two ideas in one phrase = the second gets rushed.
2. **The stressed word goes first or last in its phrase** — those are the positions the engine accents naturally. `"DNS dead."` not `"What died in here is the DNS."` — the same rule holds in any language you narrate in.
3. **Punctuation is prosody.** A comma forces a micro-pause and a lift; a full stop lands flat; a colon leans forward; an ellipsis (`…`) stretches; a dash makes a snap cut. Use them deliberately, and never leave a doubled word or a stray space — TTS reads both verbatim.
4. **Numbers: spell them when the digit reading matters** ("five oh two", not "502" — engines read `502` as *five hundred two*, which is wrong for a status code). Keep digits only when the number is on screen and the voice should say it identically.
5. **Loan words follow the source language's phonetics.** Indonesian copy: `Juli` comes out *July*, `deploy` comes out English-mangled → write `bulan ketujuh`, `rilis`.
6. **Never start a phrase with a bare proper name.** `"Dia Mansa Musa pergi…"` blends into one token; `"Dia, Mansa Musa, pergi…"` fixes it. A full sentence around the name also stops short lines being detected as the wrong language.
7. **Lists get rising intonation for free** if each item is its own phrase with a short gap — the engine lifts on every non-final item.
8. **Questions need a question shape**, not just `?`: `"Bedanya apa?"` works; `"Bedanya."` + `?` does not exist.
9. **Never hand the engine a fragment.** A 3–6 word line with no function word in the target language is read as the wrong language or as garbled syllables: a 4-word line came back as *"Sitas Romati"* while the same content written as a full 6-word sentence transcribed clean. Even a punch line keeps 5–6 words and one connector.
10. **Loanwords must be outnumbered.** A short line built around one English technical term flipped the whole phrase into English phonetics — the engine transcribed *"layer three, origin, memory out, five oh two"* back as gibberish because the loanword hijacked language detection. Either bury the loanword mid-sentence inside three or more native words, or say the native word and put the English term **on screen** instead (speak the native phrase, show `ORIGIN` in the card). Same rule for *deploy*, *query* or *cache* inside a short line.

---

## 2b. Numbers, codes and acronyms (spoken form vs display form)

A technical script has two forms of the same sentence, and they are not interchangeable:

| | Written for the eye | Spoken by the voice |
|---|---|---|
| Status code | `404` | *four oh four* (zero read as "oh") |
| Acronym spelled out | `DNS`, `CDN`, `SSL`, `API` | *D N S*, *C D N*, *S S L*, *A P I* |
| Acronym said as a word | `NASA`, `SQL`, `RAM` | *NASA*, *sequel* or *S Q L*, *ram* |
| Quantity | `500 errors`, `2 a.m.` | *five hundred errors*, *two A M* |
| Year | `1992` | *nineteen ninety-two* |

The rule is not "digits are bad". The rule is:

> **Ask how a person would say it out loud, and write that in the voice; keep the digits on screen.**

- A **code** (status code, port, error number) is read **digit by digit**, with zero spoken as *oh* — in any language, use that language's word for the digit, never the cardinal number. `502` → *five oh two*, never *five hundred and two*.
- A **quantity** is read as a number. `500 visitors` → *five hundred visitors*.
- A status code and a quantity can be the same digits: `500` alone is *five hundred* (that is how people say the error), but `504` is *five oh four*.
- An **acronym** is spelled only if people spell it. `DNS` → *D N S*; `NASA` stays *NASA*; `SQL` is *sequel* for most engineers and *S Q L* for others — pick one and keep it for the whole film.
- Short tokens at a phrase start still break the language detector even when expanded: put the code **mid-sentence** (`the gateway answers five oh two`), not alone.
- On screen nothing changes: the caption keeps `404`, because the eye reads a code as a glyph, not as a word.

**Let the tool do it, then review.** `references/narration/scripts/tts-prosody.py --expand en|id` writes the spoken form from the display form and prints every token it changed:

```sh
python references/narration/scripts/tts-prosody.py beats.json assets/voice.wav --timeline timeline.json --expand en
#  b06: DNS -> D N S
#  b08: 502 -> five oh two
#  b09: 503 -> five oh three
```

If a beat carries both fields it keeps them apart and only audits:

```json
{"id": "b08", "caption": "Layer three: origin — out of memory, 502.",
 "text": "Layer three: origin. Out of memory, five oh two."}
```

`caption` is what the film renders; `text` is what the voice says. They must be **the same sentence** — differing only in how a number or acronym is written. A caption that rewords the sentence is the drift bug from the film-side skill.

## 3. The pause map

Silence is the cheapest emphasis you can buy. Set the gap **after** each phrase:

| Gap | Use |
|---|---|
| 0.18–0.25 s | inside one idea, list items |
| 0.30–0.40 s | between sentences of the same thought |
| 0.55–0.75 s | new section, new claim |
| 0.90–1.20 s | before the payoff line, or on a visual beat |
| 1.40–2.00 s | dramatic stop — use **once** per film |

Rules that keep it alive:
- **Never** give every gap the same length: a uniform 0.4 s grid is what "flat AI narration" sounds like.
- A gap before a line reads as *emphasis*; a gap after it reads as *thinking*. Use before for punch, after for grief.
- On a 60 s film: 1–2 gaps above 0.9 s, the rest under 0.6 s.

---

## 4. Micro-shaping per phrase

Apply these **after** synthesis, per phrase, so an over-long or rushed line can be corrected without re-recording the whole script:

```sh
# tempo only, pitch untouched (safest): 0.93 = weight, 1.06 = urgency
ffmpeg -i in.wav -filter:a "atempo=0.94" out.wav

# pitch up/down keeping length (r = factor; 1.04 ≈ +0.7 semitone)
ffmpeg -i in.wav -filter:a "asetrate=24000*1.04,aresample=24000,atempo=1/1.04" out.wav

# both, plus a little body and air
ffmpeg -i in.wav -filter:a "asetrate=24000*1.03,aresample=24000,atempo=0.96,highpass=f=90,acompressor=threshold=0.12:ratio=3:attack=8:release=180:makeup=1.6" out.wav
```

- Keep pitch shifts inside **±4% (±0.7 semitone)** and tempo inside **0.92–1.08**; wider reads as a different speaker.
- Pitch **down** for authority and bad news, **up** for curiosity and lists.
- `atempo` preserves pitch; the `asetrate` trick changes pitch and length, then `atempo` restores length. Both are deterministic and available in any FFmpeg build (no `rubberband` needed).
- Do **not** use amplitude for emphasis. A louder word sounds clipped, not important. Emphasis is a *pause plus a slower phrase*.

---

## 5. Timeline-first workflow

**Never place narration on a timeline you invented.** Measure the audio, then build the picture on those numbers.

1. Write `beats.json` — the film's beats, each with its narration phrase, gap after, and optional `tempo`/`pitch`/`gain`:
   ```json
   [{"id": "b01", "text": "Two in the morning. Your phone rings.", "gap": 0.7, "tempo": 0.97},
    {"id": "b02", "text": "Your site is down.", "gap": 1.1, "pitch": 0.97}]
   ```
2. Synthesise each phrase alone, shape it, and measure it:
   ```sh
   python references/narration/scripts/tts-prosody.py beats.json assets/voice.wav \
       --voice tide --timeline assets/timeline.json
   ```
   It caches per phrase (changing one line costs one line), writes a 24 kHz mono WAV, and emits `timeline.json` with the **real measured** `start`/`end`/`dur` of every phrase plus the film length.
3. Build the film from `timeline.json` only. One beat = one visual = one caption, shown during exactly `[start, end]`. Caption text is the spoken text, verbatim — a caption that paraphrases the voice is a caption that drifts away from the story.
4. Render length = the timeline's `total`, never a number chosen in advance.
5. Re-run synthesis whenever a phrase string changes; the cache keeps unchanged phrases free.

**Why this order:** a caption and its picture can only disagree with the voice when they were authored on a different clock than the recording. Deriving all three from measured audio removes the failure mode instead of fixing it later.

---

## 6. Verification

**Per-phrase ASR gate — run this before building any picture.** Slice the finished track at each phrase's own `[start, end]`, transcribe the slice, and compare it to the script. Any phrase that does not come back recognisable is a phrase that will sound wrong to a human too; rewrite the words (not the audio) and re-synthesise just that one — the cache makes it one API call.

```python
for b in timeline["beats"]:
    ffmpeg("-ss", b["start"], "-t", b["dur"], "-i", "assets/voice.wav", ... ".om/p.wav")
    print(b["id"], asr(".om/p.wav"), "| said:", b["text"])
```

The loop catches exactly the two failure modes that a whole-file transcription hides: fragments read as another language, and loanword-heavy phrases flipping to English phonetics.

- **Pad the slice before transcribing.** Slice from `start - 0.1` for `dur + 0.7` s. A slice under ~2.5 s gets its **language** mis-detected and comes back in another script (Hindi, Korean, Chinese) even when the audio is perfect; the identical line transcribed from a padded slice returns clean text. Slicing exactly `[start, end]` cuts the final word and invites the same false alarm.
- **Transcribe back in slices.** ASR on 5–10 s slices of the final mix (voice under music) proves the words survive the mix; a whole-file transcription can come back empty while every slice is perfect. DeepSeek: `POST /v1/tools/asr` with a WAV slice, Ogg Opus or 16-bit PCM, ≤120 s / 8 MiB. **Run the gate on the delivered MP4's audio, not only on `voice.wav`** — the mux is where narration goes missing.
- **ASR is a proxy, not ground truth.** When one line fails the gate and two rewrites around the same word also fail, stop rewriting: a single stubborn loanword (Indonesian `koin` is the known offender) makes the detector guess another language while the audio is fine. Ship it and tell the user which timestamp to listen to, rather than churning the script for a measurement artefact.
- **Duration sanity:** the reported total must equal the last phrase's `end` + tail. A track longer than the film is a phrase that overran its slot — shorten the copy, never the audio.
- **Overrun check:** if any phrase's measured `dur` exceeds `gap + 0.2 s` of what the storyboard budgeted, rewrite it shorter. TTS cannot be compressed reliably; writing is the fix.
- **Listen at 1×**, eyes closed, on phone speakers. What to catch: two sentences sharing one breath, a landing that flattens mid-thought, list items without lift, a name blended into the word before it.
- **Numbers and names** must be transcribed correctly by ASR; a mangled number in the transcript is a mangled number in the mix.

---

## 7. Failure table

| Symptom | Cause | Fix |
|---|---|---|
| Whole line falls flat at the end | one phrase per sentence | split at the comma before the main clause |
| "Robotic 1×" delivery | uniform gaps, all tempo 1.0 | vary gaps (0.2/0.4/0.6/1.0), slow the payoff to 0.94 |
| A word sounds swallowed | phrase starts with a bare name or a digit | add a comma or spell the number |
| Narration runs past the picture | copy written to fit the *screen*, not the clock | cut words; ~2.4–2.7 Indonesian words per second at tempo 1.0 |
| Two speakers seem to narrate | pitch/tempo pushed past ±4% / 1.08 | stay inside the range; emphasise with pause instead |
| Captions drift from the voice | captions authored separately | generate captions from `beats.json` text, timed by `timeline.json` |
| The voice reads "404" as *four hundred four* | code written as digits in the spoken line | `--expand en`, or write *four oh four* |
| An acronym becomes a word ("DNS" → "dense") | acronym handed over unspaced | space the letters in the spoken form: *D N S* |
| Stress lands on the wrong word | `"Why is your site down?"` with stress on *your* | reorder so the stressed word lands first or last: `"Your site is down. Why?"` |
| A short line comes back as syllables in another language | fragment with no function word to anchor the language | write a full sentence (`"It turns out your site is down."`) |
| A loanword drags the whole phrase into the wrong phonetics | loanword at the phrase start, or two loanwords in five words | bury the loanword mid-sentence or speak the native word and put the term on screen |
| The same line transcribes into Hindi/Chinese/Korean twice, and rewrites do not help | ASR language auto-detection on a short slice or a bare loanword | pad the slice to ≥2.5 s, then treat it as an ASR artefact: keep the line and flag the timestamp for the user |

---

## 8. Budgets that hold

- Indonesian at tempo 1.0: **≈2.4–2.7 words per second**, so one 60 s film holds **~120–150 spoken words** *including* pauses. Anything above 160 words will not fit however it is read.
- Cap: keep every phrase under ~4.5 s of audio; longer than that and the engine's own contour sags.
- A 60 s narrated film: 14–20 phrases, 1–2 long pauses, one tempo change on the payoff line.

## 9. Scripts

- `references/narration/scripts/tts-prosody.py` — phrase-level synthesis with per-phrase tempo/pitch/gain, gap map, measured `timeline.json`. DeepSeek TTS by default; `--endpoint` points it at any compatible JSON API returning WAV.
