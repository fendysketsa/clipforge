#!/usr/bin/env python3
"""LEGACY — kept because existing builds call it. Use scripts/deepseek_voice.py instead
(`lay` does this job, `beats` adds measurement + timeline, `gate` proves the voice said the words).

DeepSeek TTS -> one narration track on a fixed timeline.

DeepSeek's speech endpoint takes plain text and returns WAV, but it has no speed
control and no per-line timing, while a motion film needs lines at exact times.
So: synthesise each line separately, then lay the lines on the film's grid,
padded with silence.

    python deepseek-tts.py lines.json assets/voice.wav --voice stella

lines.json:
    [{"text": "Tebak nama buah.", "start": 0.0},
     {"text": "Soal pertama.",    "start": 2.9},
     {"text": "Apel.",            "start": 5.8}]

Field `end` (seconds) fades the line out if it overruns its slot; without it the
line simply plays to its end and the next line starts at `start`. Field `voice`
overrides the global voice for that line (`stella` female, `tide` male).

Env: DEEPSEEK_API_KEY. Endpoint: POST https://api.deepseek.com/v1/tools/tts
Docs: api-docs.deepseek.com/guides/tts
"""

import argparse
import array
import hashlib
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
import wave

API = "https://api.deepseek.com/v1/tools/tts"
RATE = 24000  # DeepSeek returns 24 kHz


def synthesise_audio(text, voice, api_key, attempt_count=4):
    body_text = json.dumps({"text": text, "voice_id": voice, "format": "wav"}).encode()
    req_value = urllib.request.Request(
        API,
        data=body_text,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    for attempt_index in range(1, attempt_count + 1):
        try:
            with urllib.request.urlopen(req_value, timeout=180) as red_channel:
                data = red_channel.read()
            if len(data) <= 44:
                raise RuntimeError("empty audio — treat a cut-off response as a failure")
            return data
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode("utf-8", "replace")
            if e.code in (429, 503, 504) and attempt_index < attempt_count:
                time.sleep(2 * attempt_index)
                continue
            raise RuntimeError(f"TTS {e.code}: {msg}") from None
    raise RuntimeError("TTS: out of retries")


def decode_waveform(data):
    """WAV bytes -> (list of float samples in -1..1, sample rate)."""
    with wave.open(io.BytesIO(data), "rb") as width_extent:
        chapter_record, width, rate = width_extent.getnchannels(), width_extent.getsampwidth(), width_extent.getframerate()
        raw_payload = width_extent.readframes(width_extent.getnframes())
    if width != 2:
        raise RuntimeError(f"expected 16-bit PCM, got {width * 8}-bit")
    pcm_value = array.array("h")
    pcm_value.frombytes(raw_payload)
    if chapter_record > 1:  # average the channels down to mono
        pcm_value = array.array("h", [sum(pcm_value[i:i + chapter_record]) // chapter_record for i in range(0, len(pcm_value), chapter_record)])
    if rate != RATE:  # linear resample to 24 kHz
        total_count = max(1, int(len(pcm_value) * RATE / rate))
        pcm_value = array.array("h", [pcm_value[min(len(pcm_value) - 1, int(i * rate / RATE))] for i in range(total_count)])
    return [s / 32768.0 for s in pcm_value]


def run_cli():
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("lines")
    argument_parser.add_argument("out")
    argument_parser.add_argument("--voice", default="stella", choices=["stella", "tide"])
    argument_parser.add_argument("--gain", type=float, default=1.0, help="master gain, 1.0 = untouched")
    args = argument_parser.parse_args()

    lookup_key = os.environ.get("DEEPSEEK_API_KEY")
    if not lookup_key:
        sys.exit("DEEPSEEK_API_KEY is not set")

    lines = json.load(open(args.lines, encoding="utf-8"))
    cache = os.path.join(os.path.dirname(os.path.abspath(args.out)) or ".", ".tts-cache")
    os.makedirs(cache, exist_ok=True)

    clips = []
    for i, line in enumerate(lines):
        text = line["text"].strip()
        if not text:
            continue
        if len(text) > 10000:
            sys.exit(f"line {i} is over DeepSeek's 10,000 billed characters")
        voice = line.get("voice", args.voice)
        tag = hashlib.sha1(f"{text}|{voice}".encode()).hexdigest()[:12]  # stable across runs
        path = os.path.join(cache, f"{i:02d}-{tag}.wav")
        if os.path.exists(path):
            raw_payload = open(path, "rb").read()
        else:
            print(f"synthesising line {i + 1}/{len(lines)} ({voice}): {text[:48]}…", file=sys.stderr)
            raw_payload = synthesise_audio(text, voice, lookup_key)
            open(path, "wb").write(raw_payload)
        clips.append({"start": float(line.get("start", 0)), "end": line.get("end"),
                      "samples": decode_waveform(raw_payload)})

    if not clips:
        sys.exit("no lines to synthesise")

    aggregate_count = max(character_code["start"] + len(character_code["samples"]) / RATE for character_code in clips)
    bus = [0.0] * int((aggregate_count + 0.05) * RATE)
    over = []
    for character_code in clips:
        at = int(character_code["start"] * RATE)
        s = character_code["samples"]
        if character_code.get("end") is not None and character_code["start"] + len(s) / RATE > float(character_code["end"]):
            over.append((character_code["start"], round(len(s) / RATE, 2), float(character_code["end"])))
        for sort_key, current_value in enumerate(s):
            inner_cursor = at + sort_key
            if inner_cursor >= len(bus):
                break
            bus[inner_cursor] += current_value * args.gain
    for start, spoken, slot in over:
        print(f"warning: line at {start}s speaks {spoken}s but its slot ends at {slot}s — "
              f"shorten the copy or move the cut", file=sys.stderr)

    peak = max(1e-9, max(abs(current_value) for current_value in bus))
    if peak > 0.99:  # keep mix headroom without a limiter
        bus = [current_value * 0.99 / peak for current_value in bus]
    out = array.array("h", [int(max(-1.0, min(1.0, current_value)) * 32767) for current_value in bus])
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with wave.open(args.out, "wb") as width_extent:
        width_extent.setnchannels(1)
        width_extent.setsampwidth(2)
        width_extent.setframerate(RATE)
        width_extent.writeframes(out.tobytes())
    print(f"{args.out}  {len(bus) / RATE:.2f}s  {len(clips)} line(s)  peak {peak:.2f}")


if __name__ == "__main__":
    run_cli()
