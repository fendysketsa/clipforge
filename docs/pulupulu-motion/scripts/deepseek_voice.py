#!/usr/bin/env python3
"""DeepSeek speech toolkit for film narration: speak, lay, beats, gate, asr, probe, cost.

DeepSeek TTS takes plain text and returns WAV. It has no SSML, no speed, no pitch and no word
timings, so everything a motion film needs has to be built around it:

  * one line at a time            -> `speak`  (cached, so a re-run only pays for changed copy)
  * lines on the film's grid      -> `lay`    (per-line start/end, overlap warnings, peak control)
  * prosody by segmentation       -> `beats`  (planned gaps/tempo/pitch -> measured timeline.json)
  * proof the voice said the words -> `gate`  (synthesise -> ASR -> compare, per phrase)
  * what it will cost             -> `cost`

Every subcommand reads DEEPSEEK_API_KEY from the environment and never prints it.

    python deepseek_voice.py probe
    python deepseek_voice.py speak "Your site is down." --voice tide --out line.wav
    python deepseek_voice.py cost beats.json --expand en
    python deepseek_voice.py gate beats.json --voice tide --expand en
    python deepseek_voice.py beats beats.json voice.wav --voice tide --timeline timeline.json
    python deepseek_voice.py lay lines.json voice.wav --voice stella
    python deepseek_voice.py asr line.wav --pad 0.7

Exit codes: 0 ok, 1 gate failed, 2 bad usage or missing key, 3 provider error after retries.
"""
from __future__ import annotations

import argparse
import array
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
import wave

TTS_URL = "https://api.deepseek.com/v1/tools/tts"
ASR_URL = "https://api.deepseek.com/v1/tools/asr"
SAMPLE_RATE = 24000
CHARS_PER_REQUEST = 10000
BYTES_PER_REQUEST = 64 * 1024
USD_PER_10K = 0.45
MIN_ASR_SLICE = 2.5          # ASR language detection wobbles on anything shorter
VOICES = ("stella", "tide")  # stella = female, tide = male

DIGITS_EN = {"0": "oh", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five",
             "6": "six", "7": "seven", "8": "eight", "9": "nine"}
DIGITS_ID = {"0": "kosong", "1": "satu", "2": "dua", "3": "tiga", "4": "empat", "5": "lima",
             "6": "enam", "7": "tujuh", "8": "delapan", "9": "sembilan"}


# ----------------------------------------------------------------------------- api plumbing

def api_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        print("DEEPSEEK_API_KEY is not set — export it, or put it in the environment file the "
              "skill reads; never paste it into a command that gets logged", file=sys.stderr)
        raise SystemExit(2)
    return key


def post_json(url: str, payload: dict, timeout: int = 180, attempts: int = 4) -> bytes:
    body = json.dumps(payload).encode()
    if len(body) > BYTES_PER_REQUEST:
        raise RuntimeError(f"request body {len(body)} B is over the {BYTES_PER_REQUEST} B limit — "
                           f"split the text")
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"})
    return _send(request, timeout, attempts)


def post_multipart(url: str, field: str, filename: str, blob: bytes, timeout: int = 180,
                   attempts: int = 4) -> bytes:
    boundary = "----" + uuid.uuid4().hex
    parts = [f"--{boundary}".encode(),
             f'Content-Disposition: form-data; name="{field}"; filename="{filename}"'.encode(),
             b"Content-Type: audio/wav", b"", blob, f"--{boundary}--".encode(), b""]
    request = urllib.request.Request(
        url, data=b"\r\n".join(parts), method="POST",
        headers={"Authorization": f"Bearer {api_key()}",
                 "Content-Type": f"multipart/form-data; boundary={boundary}"})
    return _send(request, timeout, attempts)


def _send(request: urllib.request.Request, timeout: int, attempts: int) -> bytes:
    last = ""
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                blob = response.read()
            if len(blob) <= 44 and request.full_url == TTS_URL:
                raise RuntimeError("audio came back empty — a cut-off response is a failure, not a "
                                   "short line")
            return blob
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:400].decode("utf-8", "replace")
            last = f"HTTP {exc.code}: {detail}"
            if exc.code in (429, 500, 502, 503, 504) and attempt < attempts:
                wait = 2 ** attempt
                print(f"  {exc.code} — retry {attempt}/{attempts - 1} in {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            if exc.code == 400:
                print(f"  400 — check for empty text or a blocked phrase (`Content Exists Risk`): "
                      f"{detail}", file=sys.stderr)
            raise RuntimeError(last) from None
        except (urllib.error.URLError, TimeoutError) as exc:
            last = str(exc)
            if attempt < attempts:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"network: {last}") from None
    raise RuntimeError(last or "out of retries")


# ----------------------------------------------------------------------------- audio plumbing

def wav_to_mono(blob: bytes) -> array.array:
    """WAV bytes -> mono 16-bit samples at 24 kHz."""
    with wave.open(io.BytesIO(blob), "rb") as handle:
        channels, width, rate = handle.getnchannels(), handle.getsampwidth(), handle.getframerate()
        raw = handle.readframes(handle.getnframes())
    if width != 2:
        raise RuntimeError(f"expected 16-bit PCM, got {width * 8}-bit")
    samples = array.array("h")
    samples.frombytes(raw)
    if channels > 1:
        samples = array.array("h", [sum(samples[i:i + channels]) // channels
                                    for i in range(0, len(samples), channels)])
    if rate != SAMPLE_RATE:
        total = max(1, int(len(samples) * SAMPLE_RATE / rate))
        samples = array.array("h", [samples[min(len(samples) - 1, int(i * rate / SAMPLE_RATE))]
                                    for i in range(total)])
    return samples


def mono_to_wav(samples: array.array, path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(samples.tobytes())


def silence(seconds: float) -> array.array:
    return array.array("h", [0] * max(0, int(seconds * SAMPLE_RATE)))


def ffmpeg_to_wav(path: str) -> bytes:
    """Anything ffmpeg can read -> mono 24 kHz WAV bytes (for ASR input)."""
    tmp = path + f".{os.getpid()}.24k.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", path, "-ac", "1", "-ar",
                    str(SAMPLE_RATE), "-c:a", "pcm_s16le", tmp], check=True)
    blob = open(tmp, "rb").read()
    os.unlink(tmp)
    return blob


def read_wav_any(path: str) -> array.array:
    try:
        return wav_to_mono(open(path, "rb").read())
    except Exception:
        return wav_to_mono(ffmpeg_to_wav(path))


# ----------------------------------------------------------------------------- text helpers

def spoken_form(text: str, language: str = "en") -> str:
    """Write number-like tokens the way a reader says them, when the reading matters.

    A status code is digit-by-digit; a measurement is a cardinal. Only tokens that look like
    codes/short numbers are rewritten — see the decision table in
    references/narration/deepseek-tts.md.
    """
    table = DIGITS_ID if language == "id" else DIGITS_EN

    def code(match: re.Match) -> str:
        token = match.group(0)
        if len(token) > 4:            # 10000 is a cardinal, not a code
            return token
        return " ".join(table[digit] for digit in token)

    text = re.sub(r"\b\d{2,4}\b(?=\s*(?:error|status|code|at|on|:|,|\.|$))", code, text)
    text = re.sub(r"\b(?:HTTP|code|status)\s+(\d{2,4})\b",
                  lambda m: m.group(0).split()[0] + " " + " ".join(table[d] for d in m.group(1)), text)
    text = re.sub(r"\b(\d{1,2})%", lambda m: f"{m.group(1)} percent", text)
    return text


def normalise_for_compare(text: str) -> str:
    lowered = text.lower().replace("’", "'")
    lowered = re.sub(r"['’]", "", lowered)
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    words = [w for w in lowered.split() if w]
    keep = [w for w in words if w not in {"the", "a", "an", "and", "of", "to", "is", "in", "it",
                                          "that", "this", "you", "your", "its"}]
    return " ".join(keep or words)


def similarity(expected: str, heard: str) -> float:
    left = normalise_for_compare(expected).split()
    right = normalise_for_compare(heard).split()
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    remaining = list(right)
    hits = 0
    for word in left:
        best = None
        for candidate in remaining:
            if word == candidate:
                best = candidate
                break
            if best is None and (word.startswith(candidate[:4]) or candidate.startswith(word[:4])) \
                    and min(len(word), len(candidate)) >= 4:
                best = candidate
        if best is not None:
            remaining.remove(best)
            hits += 1
    return hits / max(len(left), len(right))


# ----------------------------------------------------------------------------- synthesis

def cache_dir_for(path: str | None) -> str:
    base = os.path.dirname(os.path.abspath(path or "voice.wav")) or "."
    cache = os.path.join(base, ".tts-cache")
    os.makedirs(cache, exist_ok=True)
    return cache


def synthesise(text: str, voice: str, cache: str, index: int, offline: bool = False) -> tuple[bytes, bool]:
    tag = hashlib.sha1(f"{text}|{voice}|v1".encode()).hexdigest()[:14]
    path = os.path.join(cache, f"{index:03d}-{tag}.wav")
    if os.path.exists(path):
        return open(path, "rb").read(), True
    if offline:
        raise RuntimeError(f"no cached audio for line {index} and --offline was requested")
    print(f"  synthesising {index + 1}: {text[:56]}…", file=sys.stderr)
    blob = post_json(TTS_URL, {"text": text, "voice_id": voice, "format": "wav"})
    open(path, "wb").write(blob)
    return blob, False


def load_items(path: str, expand: str | None) -> list[dict]:
    """Read a beats/lines table; fail with one sentence, not a traceback."""
    if not os.path.exists(path):
        raise SystemExit(f"no such file: {path}")
    try:
        data = json.load(open(path, encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path} is not JSON ({exc.msg} at line {exc.lineno}) — expected a list of "
                         f"{{text, start|gap}} objects") from None
    if not isinstance(data, (list, dict)):
        raise SystemExit(f"{path} must contain a list of phrases or an object with a beats/lines key")
    if isinstance(data, dict):
        data = data.get("beats") or data.get("lines") or []
    items = []
    for index, raw in enumerate(data):
        text = (raw.get("text") or raw.get("caption") or "").strip()
        if not text:
            continue
        spoken = spoken_form(text, expand) if expand else text
        items.append({**raw, "id": raw.get("id") or f"b{index + 1:02d}",
                      "text": text, "spoken": spoken})
    if not items:
        raise SystemExit(f"{path} has no phrases — every entry needs a non-empty `text` field")
    return items


# ----------------------------------------------------------------------------- subcommands

def cmd_probe(args: argparse.Namespace) -> int:
    cache = cache_dir_for(args.cache)
    print(f"key: present ({len(api_key())} chars, value never printed)")
    failures = 0
    for voice in VOICES:
        text = "Voice check, one two three."
        started = time.time()
        try:
            blob = post_json(TTS_URL, {"text": text, "voice_id": voice, "format": "wav"})
            samples = wav_to_mono(blob)
            print(f"  {voice:6s} ok   {len(samples) / SAMPLE_RATE:5.2f}s  "
                  f"{len(blob) // 1024} KiB  {time.time() - started:.1f}s round trip")
        except RuntimeError as exc:
            failures += 1
            print(f"  {voice:6s} FAIL {exc}")
    print(f"\naccess to {len(VOICES) - failures}/{len(VOICES)} voices · cache {cache}")
    return 0 if failures < len(VOICES) else 3


def cmd_speak(args: argparse.Namespace) -> int:
    text = spoken_form(args.text, args.expand) if args.expand else args.text
    cache = cache_dir_for(args.out)
    blob, cached = synthesise(text, args.voice, cache, 0)
    samples = wav_to_mono(blob)
    out = args.out or "line.wav"
    mono_to_wav(samples, out)
    print(f"{out}  {len(samples) / SAMPLE_RATE:.2f}s  voice={args.voice}  "
          f"{'cache' if cached else 'fresh'}  {len(text)} billed chars")
    return 0


def cmd_cost(args: argparse.Namespace) -> int:
    items = load_items(args.source, args.expand)
    billed = sum(len(item["spoken"]) for item in items)
    over = [item["id"] for item in items if len(item["spoken"]) > CHARS_PER_REQUEST]
    print(f"{len(items)} phrase(s) · {billed} billed characters · "
          f"~${billed / 10000 * USD_PER_10K:.4f} per full run")
    if over:
        print(f"over the {CHARS_PER_REQUEST}-char single-request limit: {', '.join(over)}")
        return 2
    longest = max(items, key=lambda item: len(item["spoken"]))
    print(f"longest phrase: {longest['id']} ({len(longest['spoken'])} chars) — "
          f"a phrase that long should probably be two beats")
    return 0


def cmd_lay(args: argparse.Namespace) -> int:
    items = load_items(args.source, args.expand)
    cache = cache_dir_for(args.out)
    placed, warnings = [], []
    for index, item in enumerate(items):
        blob, _ = synthesise(item["spoken"], item.get("voice", args.voice), cache, index)
        samples = wav_to_mono(blob)
        start = float(item.get("start", 0.0))
        placed.append({"id": item["id"], "text": item["text"], "start": start,
                       "end": item.get("end"), "seconds": len(samples) / SAMPLE_RATE,
                       "samples": samples})
    if not placed:
        print("nothing to lay out", file=sys.stderr)
        return 2
    total = max(p["start"] + p["seconds"] for p in placed)
    bus = array.array("h", [0] * int((total + 0.05) * SAMPLE_RATE))
    for placed_item in placed:
        at = int(placed_item["start"] * SAMPLE_RATE)
        if placed_item["end"] is not None and \
                placed_item["start"] + placed_item["seconds"] > float(placed_item["end"]):
            warnings.append(f"{placed_item['id']} speaks {placed_item['seconds']:.2f}s but its slot "
                            f"ends at {float(placed_item['end']):.2f}s")
        for offset, sample in enumerate(placed_item["samples"]):
            position = at + offset
            if position >= len(bus):
                break
            mixed = bus[position] + int(sample * args.gain)
            bus[position] = max(-32768, min(32767, mixed))
    for line in warnings:
        print(f"warning: {line} — shorten the copy or move the cut", file=sys.stderr)
    peak = max(1, max(abs(value) for value in bus))
    if peak > 32400:
        bus = array.array("h", [int(value * 32400 / peak) for value in bus])
    mono_to_wav(bus, args.out)
    print(f"{args.out}  {len(bus) / SAMPLE_RATE:.2f}s  {len(placed)} line(s)  peak {peak / 32768:.2f}")
    return 0


def cmd_beats(args: argparse.Namespace) -> int:
    """beats.json -> timeline.json + laid-out voice track, timed by measurement, not by hope."""
    items = load_items(args.source, args.expand)
    cache = cache_dir_for(args.out)
    cursor = 0.0
    timeline, warnings = [], []
    for index, item in enumerate(items):
        blob, _ = synthesise(item["spoken"], item.get("voice", args.voice), cache, index)
        samples = wav_to_mono(blob)
        if args.tempo and args.tempo != 1.0:
            samples = _retime(samples, args.tempo)
        seconds = len(samples) / SAMPLE_RATE
        gap = float(item.get("gap", args.default_gap))
        timeline.append({"id": item["id"], "text": item["text"], "spoken": item["spoken"],
                         "start": round(cursor, 3), "end": round(cursor + seconds, 3),
                         "seconds": round(seconds, 3), "gap": gap,
                         "voice": item.get("voice", args.voice),
                         "tempo": item.get("tempo", args.tempo or 1.0),
                         "pitch": item.get("pitch", 1.0)})
        if seconds > args.max_phrase:
            warnings.append(f"{item['id']} measures {seconds:.2f}s — over the {args.max_phrase:.1f}s "
                            f"beat budget; shorten the copy instead of speeding it up")
        cursor += seconds + gap
    total = cursor - (timeline[-1]["gap"] if timeline else 0) + args.tail
    bus = array.array("h", [0] * int(total * SAMPLE_RATE))
    for index, entry in enumerate(timeline):
        blob, _ = synthesise(entry["spoken"], entry["voice"], cache, index)
        samples = wav_to_mono(blob)
        if entry["tempo"] and entry["tempo"] != 1.0:
            samples = _retime(samples, entry["tempo"])
        at = int(entry["start"] * SAMPLE_RATE)
        for offset, sample in enumerate(samples):
            position = at + offset
            if position >= len(bus):
                break
            mixed = bus[position] + sample
            bus[position] = max(-32768, min(32767, mixed))
    peak = max(1, max(abs(value) for value in bus))
    if peak > 32400:
        bus = array.array("h", [int(value * 32400 / peak) for value in bus])
    mono_to_wav(bus, args.out)
    payload = {"voice": args.voice, "sample_rate": SAMPLE_RATE,
               "duration": round(len(bus) / SAMPLE_RATE, 3), "beats": timeline}
    if args.timeline:
        os.makedirs(os.path.dirname(os.path.abspath(args.timeline)) or ".", exist_ok=True)
        json.dump(payload, open(args.timeline, "w", encoding="utf-8"), indent=1)
    for line in warnings:
        print(f"warning: {line}", file=sys.stderr)
    print(f"{args.out}  {len(bus) / SAMPLE_RATE:.2f}s  {len(timeline)} beat(s)"
          + (f"  ·  timeline -> {args.timeline}" if args.timeline else ""))
    return 0


def _retime(samples: array.array, tempo: float) -> array.array:
    """Local tempo change without ffmpeg: drop/duplicate windows. Keep |tempo-1| <= 0.08."""
    if abs(tempo - 1.0) > 0.08:
        raise RuntimeError(f"tempo {tempo} is outside ±8% — outside that range pitch and timbre "
                           f"break; cut words instead")
    ratio = 1.0 / tempo
    total = max(1, int(len(samples) * ratio))
    return array.array("h", [samples[min(len(samples) - 1, int(i / ratio))] for i in range(total)])


def transcribe(blob: bytes) -> tuple[str, int]:
    """ASR returns text + duration only — there are no word timings to rely on."""
    raw = post_multipart(ASR_URL, "file", "slice.wav", blob)
    data = json.loads(raw.decode("utf-8", "replace"))
    return (data.get("text") or "").strip(), int(data.get("duration_ms") or 0)


def cmd_asr(args: argparse.Namespace) -> int:
    samples = read_wav_any(args.audio)
    if args.pad:
        samples = silence(args.pad) + samples + silence(args.pad)
    blob = io.BytesIO()
    with wave.open(blob, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(samples.tobytes())
    text, duration = transcribe(blob.getvalue())
    print(json.dumps({"text": text, "duration_ms": duration,
                      "seconds": round(len(samples) / SAMPLE_RATE, 2)}, ensure_ascii=False, indent=1))
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    """Per-phrase gate: synthesise, transcribe back, compare. The only check that proves the
    voice actually said the words, and the one that catches a fragment read as another language."""
    items = load_items(args.source, args.expand)
    cache = cache_dir_for(args.out)
    rows, failed = [], 0
    for index, item in enumerate(items):
        blob, _ = synthesise(item["spoken"], item.get("voice", args.voice), cache, index)
        samples = wav_to_mono(blob)
        seconds = len(samples) / SAMPLE_RATE
        padded = samples
        if seconds < MIN_ASR_SLICE:                    # short slices flip language detection
            padded = silence(0.7) + samples + silence(0.7)
        blob_out = io.BytesIO()
        with wave.open(blob_out, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(SAMPLE_RATE)
            handle.writeframes(padded.tobytes())
        heard, _ = transcribe(blob_out.getvalue())
        score = similarity(item["spoken"], heard)
        ok = score >= args.threshold
        failed += 0 if ok else 1
        rows.append((item["id"], item["spoken"], heard, seconds, score, ok))
    print(f"{'id':5s} {'meas':>6s} {'match':>6s}  phrase -> heard")
    for ident, spoken, heard, seconds, score, ok in rows:
        mark = "PASS" if ok else "FAIL"
        print(f"{ident:5s} {seconds:5.2f}s {score:6.2f}  {mark}  {spoken[:60]}")
        if not ok:
            print(f"            heard: {heard[:90]}")
    passed = len(rows) - failed
    print(f"\n{passed}/{len(rows)} phrase(s) survived the gate "
          f"(threshold {args.threshold:.2f}) · {sum(len(r[1]) for r in rows)} billed chars")
    if failed:
        print("Fix the copy, not the engine: a fragment becomes a full sentence, and a loanword gets "
              "outnumbered or moved on screen. Then re-run — the cache keeps the passing lines free.")
        return 1
    return 0


# ----------------------------------------------------------------------------- cli

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    probe = sub.add_parser("probe", help="check the key and both voices")
    probe.add_argument("--cache", default=".tts-cache")
    probe.set_defaults(func=cmd_probe)

    speak = sub.add_parser("speak", help="one line -> wav")
    speak.add_argument("text")
    speak.add_argument("--voice", default="tide", choices=VOICES)
    speak.add_argument("--out", default="line.wav")
    speak.add_argument("--expand", choices=["en", "id"], help="rewrite codes as spoken digits")
    speak.set_defaults(func=cmd_speak)

    cost = sub.add_parser("cost", help="billed characters and price before you spend")
    cost.add_argument("source")
    cost.add_argument("--expand", choices=["en", "id"])
    cost.set_defaults(func=cmd_cost)

    lay = sub.add_parser("lay", help="lines.json (text/start/end/voice) -> one track")
    lay.add_argument("source")
    lay.add_argument("out")
    lay.add_argument("--voice", default="stella", choices=VOICES)
    lay.add_argument("--gain", type=float, default=1.0)
    lay.add_argument("--expand", choices=["en", "id"])
    lay.set_defaults(func=cmd_lay)

    beats = sub.add_parser("beats", help="beats.json -> measured timeline.json + laid-out track")
    beats.add_argument("source")
    beats.add_argument("out")
    beats.add_argument("--voice", default="tide", choices=VOICES)
    beats.add_argument("--timeline")
    beats.add_argument("--default-gap", type=float, default=0.6)
    beats.add_argument("--tempo", type=float, default=1.0, help="global tempo, ±8%% max (argparse eats a lone %%)")
    beats.add_argument("--tail", type=float, default=1.2, help="silence after the last beat")
    beats.add_argument("--max-phrase", type=float, default=4.5, help="warn over this many seconds")
    beats.add_argument("--expand", choices=["en", "id"])
    beats.set_defaults(func=cmd_beats)

    asr = sub.add_parser("asr", help="transcribe a file (pad short slices)")
    asr.add_argument("audio")
    asr.add_argument("--pad", type=float, default=0.7)
    asr.set_defaults(func=cmd_asr)

    gate = sub.add_parser("gate", help="synthesise -> transcribe -> compare, per phrase")
    gate.add_argument("source")
    gate.add_argument("--voice", default="tide", choices=VOICES)
    gate.add_argument("--out", default="assets/voice.wav")
    gate.add_argument("--threshold", type=float, default=0.6)
    gate.add_argument("--expand", choices=["en", "id"])
    gate.set_defaults(func=cmd_gate)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
