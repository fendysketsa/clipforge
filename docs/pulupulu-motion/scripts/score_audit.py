"""Judge a score by measurement: is it a track, or is it a drone — and is it broken?

The two rejections this script exists for are not taste calls. A score that "sounds weird" measures as a lot of
energy above 4 kHz with almost none below 250 Hz, plus sample-level clicks. A score that is "just a drone" measures
as a low onset count: the harmony is continuous and almost nothing strikes. Both are visible in numbers before a
single listener complains, and both are fixable in the generator rather than by re-recording.

    python score_audit.py score.wav [--lufs -14] [--min-onsets 14] [--min-low 20] [--max-high 18]

Works on a WAV, or on the finished MP4 (audio is decoded out). Exit 1 when any target fails.
"""
import argparse
import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

SR = 48000
BANDS = [(20, 60), (60, 120), (120, 250), (250, 500), (500, 1000),
         (1000, 2000), (2000, 4000), (4000, 8000), (8000, 16000)]


def decode(path: str) -> np.ndarray:
    """Mono float array at SR, from any file ffmpeg can read."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "a.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", path, "-vn",
                        "-ac", "1", "-ar", str(SR), str(out)], check=True)
        with wave.open(str(out), "rb") as w:
            raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def loudness(path: str):
    """Integrated LUFS and true peak from ffmpeg's EBU R128 meter — the authority, not an internal estimate."""
    p = subprocess.run(["ffmpeg", "-v", "info", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    i = tp = None
    for line in p.stderr.splitlines():
        s = line.strip()
        if s.startswith("I:") and "LUFS" in s and i is None:
            try:
                i = float(s.split()[1])
            except (IndexError, ValueError):
                pass
        if s.startswith("Peak:") and "dBFS" in s:
            try:
                tp = float(s.split()[1])
            except (IndexError, ValueError):
                pass
    return i, tp


def tilt(a: np.ndarray):
    spec = np.abs(np.fft.rfft(a * np.hanning(len(a))))
    f = np.fft.rfftfreq(len(a), 1.0 / SR)
    total = spec.sum() + 1e-12
    rows = [(lo, hi, spec[(f >= lo) & (f < hi)].sum() / total * 100.0) for lo, hi in BANDS]
    low = spec[f < 250].sum() / total * 100.0
    high = spec[f >= 4000].sum() / total * 100.0
    return rows, low, high


def onsets(a: np.ndarray, win=1024, hop=256):
    """Spectral-flux peaks per second. The objective reading of "energetic" versus "drone"."""
    n = (len(a) - win) // hop
    if n < 8:
        return 0, 0.0
    flux = np.zeros(n)
    prev = None
    for i in range(n):
        mag = np.abs(np.fft.rfft(a[i * hop:i * hop + win] * np.hanning(win)))
        if prev is not None:
            flux[i] = np.maximum(mag - prev, 0.0).sum()
        prev = mag
    thresh = flux.mean() + flux.std()
    peaks, last = 0, -99
    for i, v in enumerate(flux):
        if v > thresh and (i - last) > 3:
            peaks += 1
            last = i
    return peaks, peaks / (len(a) / SR)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--lufs", type=float, default=-14.0, help="integrated target (default -14 for an ad/short)")
    ap.add_argument("--lufs-tol", type=float, default=0.6)
    ap.add_argument("--max-peak", type=float, default=-1.0, help="true peak ceiling in dBFS")
    ap.add_argument("--min-onsets", type=float, default=14.0, help="onset density floor per second")
    ap.add_argument("--min-low", type=float, default=20.0, help="minimum share of energy under 250 Hz, percent")
    ap.add_argument("--max-high", type=float, default=18.0, help="maximum share of energy above 4 kHz, percent")
    ap.add_argument("--json")
    a = ap.parse_args()

    x = decode(a.path)
    dur = len(x) / SR
    rows, low, high = tilt(x)
    peaks, rate = onsets(x)
    d = np.abs(np.diff(x))
    clicks = int((d > 0.25).sum())
    dc = float(x.mean())
    rms = float(np.sqrt((x ** 2).mean()))
    crest = float(20 * np.log10(np.abs(x).max() / (rms + 1e-9))) if rms > 0 else 0.0
    lufs, tp = loudness(a.path)

    print(f"file        : {Path(a.path).name}  ({dur:.3f} s)")
    print(f"loudness    : {lufs if lufs is not None else 'n/a'} LUFS   true peak {tp if tp is not None else 'n/a'} dBFS")
    print("spectral tilt:")
    for lo, hi, pct in rows:
        print(f"  {lo:>5}-{hi:<5} Hz {pct:5.1f}%  {'#' * int(pct)}")
    print(f"body        : {low:.1f}% under 250 Hz    {high:.1f}% above 4 kHz")
    print(f"rhythm      : {peaks} onsets = {rate:.2f}/s   crest {crest:.1f} dB")
    print(f"cleanliness : {clicks} sample-level clicks   DC {dc:+.5f}")

    fails = []
    if lufs is not None and abs(lufs - a.lufs) > a.lufs_tol:
        fails.append(f"loudness {lufs} LUFS is off the {a.lufs} target by more than {a.lufs_tol} — gain it, do not re-mix")
    if tp is not None and tp > a.max_peak:
        fails.append(f"true peak {tp} dBFS is over the {a.max_peak} ceiling")
    if clicks > 8:
        fails.append(f"{clicks} sample-level clicks — an envelope starts or stops in one sample; give every voice an attack")
    if low < a.min_low:
        fails.append(f"only {low:.1f}% of the energy is under 250 Hz — the mix has no body")
    if high > a.max_high:
        fails.append(f"{high:.1f}% of the energy is above 4 kHz — hiss-forward, which is what 'weird' means to a listener")
    if rate < a.min_onsets:
        fails.append(f"{rate:.2f} onsets/s is under {a.min_onsets} — this is a sustained bed, not a rhythm-led track")
    if abs(dc) > 0.01:
        fails.append(f"DC offset {dc:+.4f} — high-pass the bus")

    if a.json:
        Path(a.json).write_text(json.dumps({"duration": dur, "lufs": lufs, "true_peak": tp,
                                            "low_pct": low, "high_pct": high, "onsets": peaks,
                                            "onset_rate": rate, "crest_db": crest,
                                            "clicks": clicks, "dc": dc, "fails": fails}, indent=1),
                                encoding="utf-8")
    if fails:
        print()
        for f in fails:
            print("  FAIL " + f)
        print(f"\nSCORE AUDIT FAIL ({len(fails)})")
        return 1
    print("\nSCORE AUDIT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
