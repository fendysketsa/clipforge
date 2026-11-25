"""Two-voice dialogue for stickman two-handers: measured TTS, real turn-taking, one ledger.

Reads a script JSON, synthesises each line with DeepSeek TTS, measures every wav, and builds a
timeline that already contains the acting decisions an editor would make:

  gap_after     seconds of silence after this line before the next may start
  overlap_prev  seconds this line starts BEFORE the previous line ends (an interruption)

Usage:
  python dialogue_voices.py --script dialogue.json --out audio/ [--voice-m tide --voice-f stella]
Writes audio/<id>.wav, audio/dialogue.wav and <out>/timeline.json.

Script format:
{
  "voices": {"m": "tide", "f": "stella"},
  "lines": [
    {"id": "L1", "speaker": "m", "text": "I finally quit my job yesterday.", "gap_after": 0.34},
    {"id": "L2", "speaker": "f", "text": "Wait. Really?", "overlap_prev": 0.28}
  ]
}
"""
import argparse
import json
import os
import pathlib
import subprocess
import urllib.request

TTS_URL = "https://api.deepseek.com/v1/tools/tts"


def probe(path):
    return float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1",
         str(path)], capture_output=True, text=True).stdout.strip())


def tts(text, voice, out, key):
    body = json.dumps({"text": text, "voice_id": voice, "format": "wav",
                       "filter_markdown": True}).encode()
    req = urllib.request.Request(TTS_URL, data=body, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    if len(data) < 200:
        raise RuntimeError(f"TTS returned {len(data)} bytes for {text!r}")
    out.write_bytes(data)
    return probe(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True)
    ap.add_argument("--out", default="audio")
    ap.add_argument("--voice-m", default="tide")
    ap.add_argument("--voice-f", default="stella")
    ap.add_argument("--start", type=float, default=0.45)
    args = ap.parse_args()

    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise SystemExit("DEEPSEEK_API_KEY is not set")
    script = json.loads(pathlib.Path(args.script).read_text(encoding="utf-8"))
    voices = {"m": args.voice_m, "f": args.voice_f, **script.get("voices", {})}
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    dur, start, prev = {}, {}, None
    for i, line in enumerate(script["lines"]):
        f = out / f"{line['id']}.wav"
        if f.exists() and f.stat().st_size > 200:
            dur[line["id"]] = probe(f)
        else:
            dur[line["id"]] = tts(line["text"], voices[line["speaker"]], f, key)
        if i == 0:
            start[line["id"]] = args.start
        else:
            overlap = float(line.get("overlap_prev", 0.0))
            start[line["id"]] = start[prev] + dur[prev] - overlap + float(script["lines"][i - 1].get("gap_after", 0.0))
        prev = line["id"]
        print(f"  {line['id']} [{line['speaker']}] {dur[line['id']]:.2f}s @ {start[line['id']]:.2f}s")

    last = script["lines"][-1]
    total = round(start[last["id"]] + dur[last["id"]] + float(last.get("gap_after", 0.55)), 3)
    tl = {"total": total, "fps": script.get("fps", 30),
          "lines": [{"id": l["id"], "speaker": l["speaker"], "text": l["text"],
                     "start": round(start[l["id"]], 3), "dur": round(dur[l["id"]], 3),
                     "end": round(start[l["id"]] + dur[l["id"]], 3),
                     # carried through so the rig can find the interruption and cut on it
                     "overlap_prev": float(l.get("overlap_prev", 0.0)),
                     "gap_after": float(l.get("gap_after", 0.0))} for l in script["lines"]]}
    (out.parent / "timeline.json").write_text(json.dumps(tl, indent=2), encoding="utf-8")

    cmd = ["ffmpeg", "-y", "-v", "error"]
    for l in script["lines"]:
        cmd += ["-i", str(out / f"{l['id']}.wav")]
    parts, mix = [], []
    for i, l in enumerate(script["lines"]):
        ms = int(round(start[l["id"]] * 1000))
        parts.append(f"[{i}:a]aresample=24000,aformat=sample_fmts=s16:channel_layouts=mono,"
                     f"adelay={ms}|{ms}[a{i}]")
        mix.append(f"[a{i}]")
    fc = ";".join(parts) + ";" + "".join(mix) + \
        f"amix=inputs={len(script['lines'])}:normalize=0,apad=whole_dur={total}[out]"
    cmd += ["-filter_complex", fc, "-map", "[out]", "-ar", "24000", "-ac", "1",
            "-c:a", "pcm_s16le", str(out / "dialogue.wav")]
    subprocess.run(cmd, check=True)
    print(f"\ntotal {total}s -> {out/'dialogue.wav'} + timeline.json")


if __name__ == "__main__":
    main()
