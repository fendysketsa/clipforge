"""Gates for a stickman performance film, measured on the encoded file.

Technical gates (numbers):
  decode clean, freezedetect holds, silencedetect gaps, integrated loudness / true peak

Acting gates (images + numbers, for your own eyes):
  per-stroke frame strips at 0.2 s spacing, plus the mean absolute difference of consecutive
  frames inside a region - so "the figure is moving" is a measurement, not an opinion.

Usage:
  python stickman_qa.py out/film.mp4 --strokes 4.4,10.5,17.6 --out verify/
  python stickman_qa.py out/film.mp4 --strokes 4.4 --region 0.15,0.25,0.85,0.90
"""
import argparse
import json
import pathlib
import re
import subprocess

import numpy as np
from PIL import Image


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def gate_decode(path):
    r = run(["ffmpeg", "-v", "error", "-i", path, "-f", "null", "-"])
    return {"gate": "decode", "ok": r.stderr.strip() == "", "detail": r.stderr.strip()[:400]}


def gate_freezes(path, d=1.0):
    r = run(["ffmpeg", "-v", "info", "-i", path, "-vf", f"freezedetect=n=0.004:d={d}", "-f", "null", "-"])
    durs = [float(m) for m in re.findall(r"freeze_duration: ([0-9.]+)", r.stderr)]
    return {"gate": "freeze", "ok": len(durs) == 0, "holds": len(durs),
            "total_s": round(sum(durs), 2), "longest_s": round(max(durs), 2) if durs else 0.0}


def gate_silence(path, d=1.5):
    r = run(["ffmpeg", "-v", "info", "-i", path, "-af", f"silencedetect=n=-40dB:d={d}", "-f", "null", "-"])
    n = r.stderr.count("silence_start")
    return {"gate": "silence", "ok": n == 0, "spans": n}


def gate_loudness(path):
    r = run(["ffmpeg", "-v", "info", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"])
    integ = re.findall(r"I:\s+(-?[0-9.]+) LUFS", r.stderr)
    peak = re.findall(r"Peak:\s+(-?[0-9.]+) dBFS", r.stderr)
    i = float(integ[-1]) if integ else None
    p = float(peak[-1]) if peak else None
    ok = i is not None and -17.0 <= i <= -15.0 and p is not None and p <= -1.0
    return {"gate": "loudness", "ok": ok, "integrated_lufs": i, "true_peak_dbfs": p}


def stroke(path, t0, region, outdir, step=0.2, frames=6):
    """6 frames at 0.2 s spacing -> strip image + mean absolute difference of consecutive frames."""
    imgs = []
    for i in range(frames):
        p = outdir / f"_s{t0}_{i}.png"
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t0 + i*step:.2f}", "-i", path,
             "-frames:v", "1", str(p)])
        if p.exists():
            imgs.append(Image.open(p).convert("RGB"))
    if len(imgs) < 2:
        return {"t0": t0, "error": "could not extract frames"}
    w, h = imgs[0].size
    x0, y0, x1, y1 = (int(region[0] * w), int(region[1] * h), int(region[2] * w), int(region[3] * h))
    # A mean over a wide region is diluted by empty background, so it cannot answer "did the
    # figure move". Measure how MUCH of the region changed, and how hard, instead.
    v = [np.asarray(im.crop((x0, y0, x1, y1)).convert("L"), dtype=np.int16) for im in imgs]
    mads, fracs, p95s = [], [], []
    for a, b in zip(v, v[1:]):
        d = np.abs(a - b)
        mads.append(round(float(d.mean()), 2))
        fracs.append(round(float((d > 12).mean()), 4))
        p95s.append(int(np.percentile(d, 95)))
    strip = Image.new("RGB", (len(imgs) * 230, int(230 * h / w)), (18, 18, 18))
    for i, im in enumerate(imgs):
        strip.paste(im.resize((230, int(230 * h / w))), (i * 230, 0))
    sp = outdir / f"strip_{t0}.png"
    strip.save(sp)
    for p in outdir.glob(f"_s{t0}_*.png"):
        p.unlink()
    mean_frac = sum(fracs) / len(fracs)
    mean_mad = sum(mads) / len(mads)
    # Line art is thin, so a high percentile of the region is dominated by untouched background:
    # judge on how much of the region changes plus the average delta. A frozen shot scores ~0 on both.
    moving = mean_frac >= 0.005 and mean_mad >= 1.0
    return {"t0": t0, "step_s": step, "region": list(region), "step_mads": mads,
            "mean_mad": round(sum(mads) / len(mads), 2),
            "changed_fraction": fracs, "mean_changed_fraction": round(mean_frac, 4),
            "p95_diff": p95s, "moving": moving, "strip": str(sp)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("film")
    ap.add_argument("--strokes", default="", help="comma separated start seconds")
    ap.add_argument("--region", default="0.10,0.25,0.90,0.92", help="x0,y0,x1,y1 fractions")
    ap.add_argument("--out", default="verify")
    args = ap.parse_args()

    outdir = pathlib.Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    region = [float(v) for v in args.region.split(",")]

    report = {"film": args.film, "gates": [gate_decode(args.film), gate_freezes(args.film),
                                          gate_silence(args.film), gate_loudness(args.film)],
              "strokes": []}
    for s in [v for v in args.strokes.split(",") if v.strip()]:
        report["strokes"].append(stroke(args.film, float(s), region, outdir))

    (outdir / "stickman_qa.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    failed = [g["gate"] for g in report["gates"] if not g["ok"]]
    stuck = [s["t0"] for s in report["strokes"] if not s.get("moving", True)]
    print(json.dumps(report["gates"], indent=2))
    for s in report["strokes"]:
        print(f"  t={s.get('t0')}  changed {s.get('mean_changed_fraction', 0)*100:.2f}% of region  "
              f"p95 {max(s.get('p95_diff', [0]))}  meanMAD {s.get('mean_mad')}  "
              f"moving={s.get('moving')}  {s.get('strip','')}")
    print(f"\nQA: {'PASS' if not failed and not stuck else 'FAIL'} "
          f"{'gates=' + ','.join(failed) if failed else ''} "
          f"{'static strokes at ' + str(stuck) if stuck else ''}")
    print(f"report -> {outdir/'stickman_qa.json'}")
    print("A machine pass only permits visual review: look at every strip before delivering.")


if __name__ == "__main__":
    main()
