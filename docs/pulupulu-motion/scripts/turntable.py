"""Validate a 360-degree turntable image set and give the numbers a film needs.

A turntable is N sprites of the same object at equal angle steps. Using one in a frame-rendered film goes
wrong in four predictable ways, and this checks all four before you wire it into a timeline:

  1. loop seam     - the last frame must step back to the first like any other step, not duplicate it and
                     not jump; a duplicate pair is an invisible stall, a jump is a visible snap
  2. step drift    - consecutive per-pixel differences should be roughly even; one near-zero pair is a
                     duplicated frame, one outlier is a dropped or mis-ordered frame
  3. axis wander   - the object's own centroid moves between frames if it was not rendered on its rotation
                     axis, so playing the sequence makes it walk across frame. Measure, then pin an anchor
  4. stepping      - at 30 fps a full turn in T seconds holds each sprite 1.5·T video frames. Below ~3 the
                     motion reads smooth; above ~6 it reads as stop-motion, which is a style decision, not
                     an accident.

Usage:
    python turntable.py <dir> [--glob "*_frame_*.png"] [--fps 30] [--turn-seconds 6]
Exit 1 if the set is unusable (missing frames, size mismatch, no alpha, seam duplicate/jump, step outlier).
"""
import argparse
import pathlib
import sys

from PIL import Image, ImageChops, ImageStat


def load(p):
    return Image.open(p).convert("RGBA")


def mad(a, b):
    return round(sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 4, 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--glob", default="*_frame_*.png")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--turn-seconds", type=float, default=6.0)
    a = ap.parse_args()

    root = pathlib.Path(a.dir)
    files = sorted(root.glob(a.glob))
    if len(files) < 4:
        print(f"FAIL: found {len(files)} frames in {root} — a turntable needs at least 4")
        return 1
    frames = [load(f) for f in files]
    sizes = {im.size for im in frames}
    fails = []

    print(f"frames     : {len(files)}")
    print(f"size       : {sizes.pop() if len(sizes) == 1 else 'MISMATCH ' + str(sorted(sizes))}")
    if len({im.size for im in frames}) != 1:
        fails.append("frame sizes differ")

    # alpha
    al = frames[0].split()[-1].histogram()
    tot = sum(al)
    clear, opaque = al[0] / tot * 100, al[255] / tot * 100
    print(f"alpha      : {clear:.1f}% fully transparent, {opaque:.1f}% fully opaque")
    if clear < 1:
        fails.append("no transparent background — the object is baked into a plate")

    # steps + seam
    steps = [mad(frames[i], frames[i - 1]) for i in range(1, len(frames))]
    seam = mad(frames[0], frames[-1])
    mean = sum(steps) / len(steps)
    print(f"step MAD   : min {min(steps):.2f} · max {max(steps):.2f} · mean {mean:.2f}")
    print(f"loop seam  : {seam:.2f}  ({'ok' if 0.5 * mean <= seam <= 1.8 * mean else 'SUSPECT'})")
    dup = [i + 1 for i, d in enumerate(steps) if d < 0.25 * mean]
    odd = [i + 1 for i, d in enumerate(steps) if d > 1.9 * mean]
    if dup:
        fails.append(f"near-duplicate step(s) after frame {dup} — a duplicated sprite stalls the turn")
    if odd:
        fails.append(f"outlier step(s) after frame {odd} — a dropped or mis-ordered sprite jumps the turn")
    if not (0.5 * mean <= seam <= 1.8 * mean):
        fails.append("loop seam does not match the other steps — either a duplicate or a jump at the wrap")

    # axis wander
    cxs, cys = [], []
    for im in frames:
        bb = im.split()[-1].getbbox()
        if not bb:
            fails.append("an empty (fully transparent) frame")
            break
        cxs.append((bb[0] + bb[2]) / 2)
        cys.append((bb[1] + bb[3]) / 2)
    if cxs:
        dx, dy = max(cxs) - min(cxs), max(cys) - min(cys)
        print(f"axis wander: x {dx:.1f} px · y {dy:.1f} px across the set")
        if dx > 2 or dy > 2:
            print("             -> pin the object: translate each frame so a fixed anchor stays put")
            print("                (front-wheel contact patch or bbox centre-bottom beat bbox centre;")
            print("                 bbox centre moves because a bike is narrower head-on than side-on)")

    # stepping table + how many sprites a smooth turn would need
    n = len(frames)
    print(f"\nstep table @ {a.fps} fps, {n} sprites = {360 / n:.1f} deg/step")
    for T in (8, 6, 4, 3, 2, 1.5):
        hold = a.fps * T / n
        verdict = "smooth" if hold <= 3 else ("slightly steppy" if hold <= 6 else "stop-motion look")
        print(f"  full turn {T:>4}s -> {n / T:5.2f} sprites/s -> {hold:4.1f} video frames per sprite  ({verdict})")
    need = int(-(-a.fps * a.turn_seconds // 3))  # ceil, for <=3 video frames per sprite
    print(f"\nfor a smooth {a.turn_seconds:g}s turn: {need} sprites needed, this set has {n}")

    if fails:
        print("\n".join("  FAIL " + f for f in fails))
        print(f"\nTURNTABLE FAIL ({len(fails)})")
        return 1
    print("\nTURNTABLE PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
