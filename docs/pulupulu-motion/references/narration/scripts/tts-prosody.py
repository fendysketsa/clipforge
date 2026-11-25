#!/usr/bin/env python3
"""Phrase-level TTS with planned intonation -> one track + a measured timeline.

TTS APIs that expose no SSML, speed or pitch controls can still be given
prosody: cut the script into phrases, give each phrase its own pause after it,
shape each phrase with a little tempo/pitch/gain, then MEASURE every phrase and
hand the measured times to the film builder. The picture is built on the audio's
clock, so caption, image and voice cannot drift apart.

It also separates the two forms every technical script needs:

  text    SPOKEN form  - what the voice must say ("four oh four", "dee en ess")
  caption DISPLAY form - what the screen shows ("404", "DNS")

`--expand en|id` writes the spoken form for you from the display form and prints
every token it changed, so the choice is reviewed instead of assumed.

    python tts-prosody.py beats.json assets/voice.wav \\
        --voice tide --timeline assets/timeline.json --expand en

beats.json
    [{"id": "b01", "text": "It's 2 a.m. Your phone buzzes.", "gap": 0.55},
     {"id": "b02", "caption": "Layer three: origin — out of memory, 502.",
      "text": "Layer three: origin. Out of memory, five oh two.", "gap": 0.45}]

  text     spoken phrase (one idea, 4-12 words)
  caption  optional display form; if omitted, `text` is used on screen
  gap      silence AFTER the phrase, seconds (default 0.35)
  tempo    0.92-1.08 playback rate, pitch preserved (default 1.0)
  pitch    0.96-1.04 pitch factor, length preserved (default 1.0)
  gain     linear amplitude (default 1.0) -- prefer pause over loudness

Env: DEEPSEEK_API_KEY. Endpoint: POST https://api.deepseek.com/v1/tools/tts
"""

import argparse
import array
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import wave

API = "https://api.deepseek.com/v1/tools/tts"
RATE = 24000

# ---------------------------------------------------------------- spoken forms
# Spelled letters: an acronym a speaker spells out, not one they say as a word.
SPELLED = {
    "en": {"DNS": "D N S", "CDN": "C D N", "SSL": "S S L", "TLS": "T L S",
           "API": "A P I", "HTTP": "H T T P", "HTTPS": "H T T P S",
           "CPU": "C P U", "RAM": "RAM", "SQL": "S Q L", "JS": "J S",
           "UI": "U I", "UX": "U X", "URL": "U R L", "AWS": "A W S",
           "OOM": "O O M", "SLA": "S L A", "TTL": "T T L", "DB": "D B"},
    "id": {"DNS": "de en es", "CDN": "se de en", "SSL": "es es el",
           "TLS": "te el es", "API": "a pe i", "HTTP": "ha te te pe",
           "CPU": "se pe u", "SQL": "es ki u el", "URL": "u er el"},
}

# Status codes and similar: read digit by digit. ZERO below is DATA — the spoken form of
# a zero per language — and has to stay in the target language for the engine to read it.
CODE_RE = re.compile(r"\b([1-5])(\d)(\d)\b")
DIGIT = {"en": ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"],
         "id": ["nol", "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan"]}
ZERO = {"en": "oh", "id": "kosong"}
SPELL_JOIN = {"en": " ", "id": " "}

# Words that are fine on screen and wrong in the voice.
SAY = {"en": {"a.m.": "A M", "p.m.": "P M", "vs": "versus", "&": "and"},
       "id": {"vs": "versus", "&": "dan"}}


def expand(text, lang_value):
    """Display form -> spoken form. Returns (spoken, [(token, spoken) ...])."""
    note_entries = []
    out = text

    def code(m):
        a, b, c = m.group(1), m.group(2), m.group(3)
        if a == "5" and b == "0" and c == "0":       # 500 reads as a quantity
            spoken = "five hundred" if lang_value == "en" else "lima ratus"
        else:
            part_entries = []
            for d in (a, b, c):
                part_entries.append(ZERO[lang_value] if d == "0" else DIGIT[lang_value][int(d)])
            spoken = SPELL_JOIN[lang_value].join(part_entries)
        note_entries.append((m.group(0), spoken))
        return spoken

    out = CODE_RE.sub(code, out)
    for token, spoken in SAY.get(lang_value, {}).items():
        if token in out:
            out = out.replace(token, spoken)
            note_entries.append((token, spoken))
    for token, spoken in SPELLED.get(lang_value, {}).items():
        if re.search(rf"\b{token}\b", out):
            out = re.sub(rf"\b{token}\b", spoken, out)
            note_entries.append((token, spoken))
    return out, note_entries


def synthesise_audio(text, voice, api_key, attempt_count=4):
    body_text = json.dumps({"text": text, "voice_id": voice, "format": "wav"}).encode()
    req_value = urllib.request.Request(
        API, data=body_text,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST")
    for attempt_index in range(1, attempt_count + 1):
        try:
            with urllib.request.urlopen(req_value, timeout=180) as r:
                data = r.read()
            if len(data) <= 44:
                raise RuntimeError("empty audio - treat a cut-off response as a failure")
            return data
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode("utf-8", "replace")
            if e.code in (429, 503, 504) and attempt_index < attempt_count:
                time.sleep(2 * attempt_index)
                continue
            raise RuntimeError(f"TTS {e.code}: {msg}") from None
    raise RuntimeError("TTS: out of retries")


def perform_wav_to_samples(data):
    """WAV bytes -> (float samples in -1..1, rate)."""
    with wave.open(io.BytesIO(data), "rb") as w:
        chapter_record, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw_payload = w.readframes(w.getnframes())
    if width != 2:
        raise RuntimeError(f"expected 16-bit PCM, got {width * 8}-bit")
    pcm_value = array.array("h")
    pcm_value.frombytes(raw_payload)
    if chapter_record > 1:
        pcm_value = array.array("h", [sum(pcm_value[i:i + chapter_record]) // chapter_record for i in range(0, len(pcm_value), chapter_record)])
    return [s / 32768.0 for s in pcm_value], rate


def shape(active_raw_path, tempo, pitch, gain, active_out_path):
    """Per-phrase prosody shaping with FFmpeg; pitch via asetrate + compensating atempo."""
    chain_value = []
    if abs(pitch - 1.0) > 1e-3:
        chain_value.append(f"asetrate={RATE}*{pitch:.4f}")
        chain_value.append(f"aresample={RATE}")
        chain_value.append(f"atempo={1.0 / pitch:.4f}")
    if abs(tempo - 1.0) > 1e-3:
        chain_value.append(f"atempo={tempo:.4f}")
    if abs(gain - 1.0) > 1e-3:
        chain_value.append(f"volume={gain:.4f}")
    if not chain_value:
        shutil.copyfile(active_raw_path, active_out_path)
        return
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", active_raw_path,
                    "-filter:a", ",".join(chain_value), "-ac", "1", "-ar", str(RATE),
                    "-c:a", "pcm_s16le", active_out_path], check=True)


def run_cli():
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("beats")
    argument_parser.add_argument("out")
    argument_parser.add_argument("--voice", default="tide", choices=["stella", "tide"])
    argument_parser.add_argument("--timeline", default=None, help="write measured timings here")
    argument_parser.add_argument("--tail", type=float, default=0.8, help="silence after the last phrase")
    argument_parser.add_argument("--gain", type=float, default=1.0, help="master gain")
    argument_parser.add_argument("--expand", default="none", choices=["none", "en", "id"],
                    help="write the spoken form of digits and acronyms automatically")
    args = argument_parser.parse_args()

    lookup_key = os.environ.get("DEEPSEEK_API_KEY")
    if not lookup_key:
        sys.exit("DEEPSEEK_API_KEY is not set")

    beats = json.load(open(args.beats, encoding="utf-8"))
    outdir_value = os.path.dirname(os.path.abspath(args.out)) or "."
    cache = os.path.join(outdir_value, ".tts-cache")
    os.makedirs(cache, exist_ok=True)
    scratch_dir = tempfile.mkdtemp(prefix="tts-prosody-")

    rows, clip_entries, cursor_value, changed = [], [], 0.0, []
    for i, story_beat in enumerate(beats):
        display = str(story_beat.get("caption") or story_beat.get("text", "")).strip()
        spoken = str(story_beat.get("text", "")).strip()
        if not spoken:
            continue
        if args.expand != "none" and not story_beat.get("caption"):
            spoken, note_entries = expand(spoken, args.expand)
            for tok, say in note_entries:
                changed.append((story_beat.get("id", i), tok, say))
        elif args.expand != "none":
            # a caption was given: check the spoken line against it, do not rewrite
            _ignored, note_entries = expand(display, args.expand)
            for tok, say in note_entries:
                if re.search(rf"\b{re.escape(tok)}\b", spoken):
                    changed.append((story_beat.get("id", i), tok, f"STILL WRITTEN AS {tok} IN VOICE"))

        voice = story_beat.get("voice", args.voice)
        tempo = float(story_beat.get("tempo", 1.0))
        pitch = float(story_beat.get("pitch", 1.0))
        gain = float(story_beat.get("gain", 1.0))
        gap = float(story_beat.get("gap", 0.35))

        tag = hashlib.sha1(f"{spoken}|{voice}".encode()).hexdigest()[:12]
        active_raw_path = os.path.join(cache, f"{i:02d}-{tag}.wav")
        if not os.path.exists(active_raw_path):
            print(f"[{i + 1}/{len(beats)}] {voice}: {spoken[:56]}", file=sys.stderr)
            with open(active_raw_path, "wb") as fh_value:
                fh_value.write(synthesise_audio(spoken, voice, lookup_key))
        shaped_value = os.path.join(scratch_dir, f"{i:02d}.wav")
        shape(active_raw_path, tempo, pitch, gain, shaped_value)

        samples, rate = perform_wav_to_samples(open(shaped_value, "rb").read())
        if rate != RATE:
            raise RuntimeError(f"unexpected sample rate {rate}")
        thr_value = 0.004
        head_value = 0
        while head_value < len(samples) and abs(samples[head_value]) < thr_value:
            head_value += 1
        tail = len(samples)
        while tail > head_value and abs(samples[tail - 1]) < thr_value:
            tail -= 1
        samples = samples[max(0, head_value - 240): min(len(samples), tail + 480)]

        dur = len(samples) / RATE
        rows.append({"id": story_beat.get("id", f"b{i + 1:02d}"), "text": spoken,
                     "caption": display, "start": round(cursor_value, 3),
                     "end": round(cursor_value + dur, 3), "dur": round(dur, 3), "gap": gap})
        clip_entries.append((cursor_value, samples))
        cursor_value += dur + gap

    total = cursor_value - rows[-1]["gap"] + args.tail if rows else 0.0
    bus = [0.0] * int((total + 0.05) * RATE)
    for start, samples in clip_entries:
        at_value = int(start * RATE)
        for sort_key, v in enumerate(samples):
            inner_cursor = at_value + sort_key
            if inner_cursor >= len(bus):
                break
            bus[inner_cursor] += v * args.gain

    peak = max(1e-9, max(abs(v) for v in bus))
    if peak > 0.97:
        bus = [v * 0.97 / peak for v in bus]
    pcm_value = array.array("h", [int(max(-1.0, min(1.0, v)) * 32767) for v in bus])
    os.makedirs(outdir_value, exist_ok=True)
    with wave.open(args.out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm_value.tobytes())

    if args.timeline:
        json.dump({"total": round(total, 3), "beats": rows},
                  open(args.timeline, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    spoken_time = sum(r["dur"] for r in rows)
    print(f"{args.out}  {len(bus) / RATE:.2f}s  {len(rows)} phrase(s)  "
          f"speech {spoken_time:.1f}s / silence {len(bus) / RATE - spoken_time:.1f}s  peak {peak:.2f}")
    for r in rows:
        flag = "" if r["dur"] <= 4.5 else "  <- long, split it"
        print(f"  {r['id']}  {r['start']:6.2f} -> {r['end']:6.2f}  ({r['dur']:.2f}s){flag}  {r['text'][:52]}")
        if r["caption"] != r["text"]:
            print(f"                 on screen: {r['caption'][:56]}")
    if changed:
        print("spoken-form changes (review these):")
        for beat_id, tok, say in changed:
            print(f"  {beat_id}: {tok} -> {say}")
    if args.timeline:
        print(f"timeline -> {args.timeline}  (total {total:.2f}s)")


if __name__ == "__main__":
    run_cli()
