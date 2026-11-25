"""Reference stickman performance rig — two-hander dialogue, 9:16 or 16:9, Pillow + ffmpeg.

Implements the rules in `references/stickman-performance.md`:
  authored pose vocabulary + squared blend, before->extreme->result envelopes, an acting listener,
  authored silence, pelvis above the floor line, planted feet with contact shadows, gaze + rigid
  head turn, a body shear that turns flat characters toward each other, speaker-biased two-shot
  camera, and secondary lag on hands and hair.

Input : timeline.json from dialogue_voices.py  ({"total", "fps", "lines":[{id,speaker,start,dur,end}]})
        direction.json (optional)  {"L1": {"arm":[["r","open_low",0.30,1.10]], "lean":0.02, ...}}
Output: out/picture.mp4 (+ muxed out/film.mp4 when --audio is given)

Usage:
  python stickman_rig.py --timeline audio/timeline.json --audio audio/dialogue.wav \
      --direction direction.json --out out/ [--size 1080x1920]
"""
import argparse
import json
import math
import pathlib
import subprocess

from PIL import Image, ImageDraw

TAU = math.tau
INK = (22, 20, 24)
PAPER = (250, 246, 236)
BG = (246, 240, 228)
FLOOR_TINT = (231, 218, 197)
FLOOR_LINE = (204, 188, 164)
WATERMARK = "by Alucard0x1"

UPPER, FORE = 132.0, 116.0
THIGH, SHIN = 164.0, 158.0

POSE = {
    "rest":       (0.26, 0.16),
    "reach":      (0.62, 0.30),
    "offer":      (0.92, 0.26),
    "receive":    (0.72, 0.52),
    "retract":    (0.40, 0.26),
    "palm_out":   (1.28, 1.15),
    "point_up":   (2.18, 1.02),
    "open_low":   (0.72, 1.02),
    "self_point": (1.10, 1.86),
    "shrug_out":  (1.14, 1.52),
    "count_two":  (1.95, 1.15),
    "scratch":    (2.30, 2.16),
}


def clamp(v, a=0.0, b=1.0):
    return a if v < a else b if v > b else v


def lerp(a, b, t):
    return a + (b - a) * t


def ease_out(t):
    return 1 - (1 - clamp(t)) ** 3


def ease_in(t):
    return clamp(t) ** 3


def ease_io(t):
    return 0.5 - 0.5 * math.cos(math.pi * clamp(t))


def env(t, t0, t1, attack_frac=0.22, release_frac=0.34):
    """before -> extreme -> result. Returns 0..1 with a real hold in the middle."""
    if t <= t0 or t >= t1:
        return 0.0
    d = t1 - t0
    a = max(0.06, min(attack_frac * d, d * 0.45))
    r = max(0.10, min(release_frac * d, d * 0.55))
    if t < t0 + a:
        return ease_out((t - t0) / a)
    if t > t1 - r:
        return 1 - ease_in((t - (t1 - r)) / r)
    return 1.0


def solve_arm(sign, pose, blend_rest=0.0):
    """Fixed-length 2-bone arm. blend_rest=0 is the gesture, 1 is rest."""
    u, b = POSE[pose]
    if blend_rest > 0:
        ru, rb = POSE["rest"]
        u, b = lerp(u, ru, blend_rest), lerp(b, rb, blend_rest)
    ex = math.sin(u) * UPPER * sign
    ey = math.cos(u) * UPPER
    hu = u - b if sign > 0 else u + b
    hx = ex + math.sin(hu) * FORE * sign
    hy = ey + math.cos(hu) * FORE
    return (ex, ey), (hx, hy)


class Actor:
    def __init__(self, name, x, floor, scale=1.0, hair="cap", accent=(196, 84, 46),
                 sex="m", face=1, turn=0.13):
        self.name, self.x, self.floor = name, x, floor
        self.scale = scale
        self.hair, self.accent, self.sex = hair, accent, sex
        self.face = face          # +1 turns toward screen-right, -1 toward screen-left
        self.turn = turn
        self.blink_period = 2.9 if sex == "m" else 3.4

    def parts(self, s):
        sc = self.scale
        hipy = self.floor - (THIGH + SHIN) * sc * 0.985 - s.get("lift", 0)
        pelvis = (self.x + s.get("weight", 0) * 26 * sc, hipy)
        lean = s.get("lean", 0.0)
        spine = 344 * sc
        neck = (pelvis[0] + math.sin(lean) * spine, pelvis[1] - math.cos(lean) * spine)
        turn = self.face * self.turn

        def shear(p):
            return (p[0] + turn * (self.floor - p[1]), p[1])

        neck = shear(neck)
        pelvis_drawn = shear(pelvis)
        head_r = 63 * sc
        ha = lean + s.get("head", 0.0)
        head_c = (neck[0] + math.sin(ha) * (head_r + 26 * sc) + turn * 46 * sc,
                  neck[1] - math.cos(ha) * (head_r + 26 * sc) - 8 * sc)
        # a real neck: the shoulders must sit well below the head, or the arms appear to
        # grow out of the ears
        sh = (neck[0], neck[1] + 62 * sc)
        arms = {}
        for side, sign in (("l", -1), ("r", 1)):
            pose = s.get("arm_" + side, "rest")
            blend = s.get("blend_" + side, 0.0)
            (ex, ey), (hx, hy) = solve_arm(sign, pose, max(0.0, 1.0 - blend) ** 2)
            arms[side] = {"shoulder": (sh[0] + sign * 30 * sc, sh[1]),
                          "elbow": (sh[0] + sign * 30 * sc + ex * sc, sh[1] + ey * sc),
                          "hand": (sh[0] + sign * 30 * sc + hx * sc, sh[1] + hy * sc)}
        legs = {}
        for side, sign in (("l", -1), ("r", 1)):
            fx = pelvis[0] + sign * 26 * sc + s.get("step_" + side, 0.0) * 26 * sc
            knee = (fx + sign * 1 * sc + self.face * 24 * sc, pelvis[1] + THIGH * sc * 0.98)
            legs[side] = {"hip": (pelvis[0] + sign * 14 * sc, pelvis[1]),
                          "knee": knee, "foot": (fx + sign * 2 * sc, self.floor)}
        return {"pelvis": pelvis_drawn, "neck": neck, "head_c": head_c, "head_r": head_r,
                "shoulder_pt": sh, "arms": arms, "legs": legs, "head_angle": ha}


# ---------------------------------------------------------------- directing
class Director:
    """Turns a measured dialogue timeline into per-frame acting state."""

    def __init__(self, tl, cast, direction=None, shots=None):
        self.tl, self.cast, self.dir = tl, cast, direction or {}
        self.lines = tl["lines"]
        self.total, self.fps = tl["total"], tl.get("fps", 30)
        if shots:
            self.shots = shots
        else:
            # Derive coverage from the dialogue: the line that cuts across another one is the
            # argument, so it gets a hard cut to a close-up. Everything else stays a two-shot,
            # because dropping a character out of frame hides the acting you paid for.
            cx_of = {a.name: a.x for a in cast}
            intr = next((l for l in self.lines if float(l.get("overlap_prev", 0)) > 0), None)
            if intr:
                i0, i1 = intr["start"], intr["end"]
                who = intr["speaker"]
                self.shots = [
                    dict(t0=0.0, t1=i0, scale0=1.34, scale1=1.40, cy=945, cx=540),
                    dict(t0=i0, t1=i1, scale0=3.10, scale1=3.18, cy=800,
                         # the head shears toward the partner, so bias the close on the same side
                         cx=cx_of.get(who, 540) + (-48 if who == "f" else 48)),
                    dict(t0=i1, t1=self.total * 0.74, scale0=1.60, scale1=1.67, cy=960, cx=540),
                    dict(t0=self.total * 0.74, t1=1e9, scale0=1.30, scale1=1.36, cy=945, cx=540),
                ]
            else:
                self.shots = [
                    dict(t0=0.0, t1=self.total * 0.34, scale0=1.34, scale1=1.41, cy=945, cx=540),
                    dict(t0=self.total * 0.34, t1=self.total * 0.72, scale0=1.58, scale1=1.68, cy=960, cx=540),
                    dict(t0=self.total * 0.72, t1=1e9, scale0=1.30, scale1=1.36, cy=945, cx=540),
                ]
        self.nods = []
        for i, l in enumerate(self.lines):
            who = "f" if l["speaker"] == "m" else "m"
            self.nods.append((who, l["start"] + l["dur"] * 0.35, +1))
            self.nods.append((who, l["start"] + l["dur"] * 0.85, +1))

    def speaking(self, t):
        act = []
        for l in self.lines:
            if l["start"] <= t <= l["end"]:
                u = (t - l["start"]) / max(0.001, l["dur"])
                act.append((l["speaker"], max(0.0, min(1.0, u * 6) * min(1.0, (1 - u) * 7))))
        if not act:
            return (None, 0.0)
        return sorted(act, key=lambda p: -p[1])[0]

    def nod(self, t, who):
        s = 0.0
        for w, base, sign in self.nods:
            if w == who and base <= t <= base + 0.45:
                s += sign * env(t, base, base + 0.45, 0.14, 0.24)
        return s

    def gesture(self, t, who):
        st = {"arm_l": "rest", "arm_r": "rest", "blend_l": 0.0, "blend_r": 0.0}
        spk, _ = self.speaking(t)
        if spk != who:
            e = 0.14 + 0.10 * math.sin(t * 1.7 + (0.0 if who == "m" else 1.9))
            st["blend_r"], st["blend_l"] = clamp(e) * 0.50, clamp(e) * 0.35
            return st
        for l in self.lines:
            if l["speaker"] != who or not (l["start"] - 0.02 <= t <= l["end"] + 0.02):
                continue
            card = self.dir.get(l["id"], {})
            for arm, pose, off, dur in card.get("arm", [["r", "open_low", 0.2, max(0.6, l["dur"] * 0.6)]]):
                e = env(t, l["start"] + off, l["start"] + off + dur)
                if e > st["blend_" + arm]:
                    st["arm_" + arm], st["blend_" + arm] = pose, e
        return st

    def state(self, a, t, hand_lag=2 / 30):
        who = a.name
        g = self.gesture(max(0.0, t - hand_lag), who)
        spk, amp = self.speaking(t)
        lean = head = weight = 0.0
        for l in self.lines:
            if l["speaker"] != who:
                continue
            card = self.dir.get(l["id"], {})
            e = env(t, l["start"], l["end"] + 0.18, 0.30, 0.42)
            lean += card.get("lean", 0.03) * e
            head += card.get("head", -0.04) * e
            weight += card.get("weight", -0.3) * e
        head += 0.055 * self.nod(t, who)
        weight += 0.22 * math.sin(t * 0.55 + (0.0 if who == "m" else 2.3))
        blink = 1.0 if ((t + (1.7 if who == "m" else 2.6)) % a.blink_period) < 0.10 else 0.0
        mouth = 0.0
        if spk == who:
            mouth = clamp(amp) * (0.55 + 0.45 * abs(math.sin(t * 17.0 + (0.0 if who == "m" else 1.1))))
        brow = 0.0
        for l in self.lines:
            if l["speaker"] == who:
                brow += 0.25 * env(t, l["start"], l["end"], 0.25, 0.35)
        return {"arm_l": g["arm_l"], "arm_r": g["arm_r"], "blend_l": g["blend_l"],
                "blend_r": g["blend_r"], "lean": lean, "head": head, "weight": weight,
                "blink": blink, "mouth": mouth, "brow": brow,
                "look": "other" if spk in (who, None) else "other"}

    def camera(self, t):
        spk, _ = self.speaking(t)
        bias = -34.0 if spk == "m" else 34.0 if spk == "f" else 0.0
        for s in self.shots:
            if t < s["t1"]:
                u = clamp((t - s["t0"]) / max(0.001, min(s["t1"], self.total) - s["t0"]))
                return dict(scale=lerp(s["scale0"], s["scale1"], ease_io(u)),
                            cx=s.get("cx", 540) + bias, cy=s["cy"])
        s = self.shots[-1]
        return dict(scale=s["scale1"], cx=s.get("cx", 540), cy=s["cy"])


# ---------------------------------------------------------------- drawing
def tapered(d, p0, p1, w0, w1, colour):
    """A limb segment drawn as a tapered quad. A uniform line ending in nothing reads as a stick;
    a taper plus a hand at the wrist is what makes a gesture point at something."""
    import math as _m
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    ln = _m.hypot(dx, dy) or 1.0
    nx, ny = -dy / ln, dx / ln
    d.polygon([(p0[0] + nx * w0 / 2, p0[1] + ny * w0 / 2),
               (p1[0] + nx * w1 / 2, p1[1] + ny * w1 / 2),
               (p1[0] - nx * w1 / 2, p1[1] - ny * w1 / 2),
               (p0[0] - nx * w0 / 2, p0[1] - ny * w0 / 2)], fill=colour)
    d.ellipse([p1[0] - w1 / 2, p1[1] - w1 / 2, p1[0] + w1 / 2, p1[1] + w1 / 2], fill=colour)


def make_renderer(director, cast, size, floor_y, watermark=WATERMARK, labels=True):
    W, H = size
    SS = 2
    ink = INK

    def to_screen(p, cam):
        return ((( p[0] - cam["cx"]) * cam["scale"] + W / 2) * SS,
                ((p[1] - cam["cy"]) * cam["scale"] + H / 2) * SS)

    def render_frame(t):
        cam = director.camera(t)
        img = Image.new("RGB", (W * SS, H * SS), BG)
        d = ImageDraw.Draw(img)
        fl = to_screen((0, floor_y), cam)[1]
        # a close shot can push the floor line past the canvas: clamp, or every
        # rectangle below it is inverted and Pillow raises
        fl = max(0, min(fl, H * SS))
        for i in range(13):
            x = to_screen((-40 + i * 96, 0), cam)[0]
            d.line([(x, 0), (x, fl)], fill=(241, 233, 218), width=int(6 * SS))
        # light pool on the floor so the characters stand somewhere
        pc = to_screen((W * 0.5, floor_y), cam)
        pw = 520 * cam["scale"] * SS
        d.ellipse([pc[0] - pw, pc[1] - pw * 0.22, pc[0] + pw, pc[1] + pw * 0.22],
                  fill=(238, 227, 206))
        if fl < H * SS:
            d.rectangle([0, fl, W * SS, H * SS], fill=FLOOR_TINT)
        d.line([(0, fl), (W * SS, fl)], fill=FLOOR_LINE, width=int(3 * SS))
        # three wall elements at different depths: a picture, a door, a clock
        # (centre x, width, bottom height above floor, height, colour) - anchored to the floor
        for cxw, ww, base, hh, col in ((0.115, 150, 300, 120, (214, 196, 168)),
                                       (0.885, 190, 0, 520, (206, 188, 160)),
                                       (0.500, 96, 380, 96, (216, 199, 172))):
            tl_ = to_screen((W * cxw - ww / 2, floor_y - base - hh), cam)
            br_ = to_screen((W * cxw + ww / 2, floor_y - base), cam)
            if br_[1] - tl_[1] > 4:
                d.rectangle([tl_[0], tl_[1], br_[0], br_[1]], fill=col, outline=(188, 172, 148),
                            width=int(3 * SS))
        # one floor prop both characters can act against
        bx = to_screen((W * 0.615, floor_y - 34), cam)
        bw = 62 * cam["scale"] * SS
        d.rectangle([bx[0] - bw, bx[1] - bw * 0.85, bx[0] + bw, bx[1] + bw * 0.25],
                    fill=(198, 158, 118), outline=(150, 116, 82), width=int(3 * SS))
        d.line([(bx[0] - bw * 0.35, bx[1] - bw * 0.85), (bx[0], bx[1] - bw * 1.25),
                (bx[0] + bw * 0.35, bx[1] - bw * 0.85)], fill=(150, 116, 82), width=int(4 * SS))

        for a in cast:
            st = director.state(a, t)
            p = a.parts(st)
            sc = a.scale * cam["scale"] * SS
            lw = int(max(2, 9.5 * sc / SS))
            fp0 = to_screen(p["legs"]["l"]["foot"], cam)
            fp1 = to_screen(p["legs"]["r"]["foot"], cam)
            for fp in (fp0, fp1):
                w = 118 * a.scale * cam["scale"] * SS
                d.ellipse([fp[0] - w, fp[1] - 15 * SS, fp[0] + w, fp[1] + 15 * SS],
                          fill=(222, 208, 186))
            for side in ("l", "r"):
                L = p["legs"][side]
                hp, kn, ft = (to_screen(L["hip"], cam), to_screen(L["knee"], cam),
                              to_screen(L["foot"], cam))
                tapered(d, hp, kn, lw * 1.15, lw * 0.95, ink)
                tapered(d, kn, ft, lw * 0.95, lw * 0.70, ink)
                tapered(d, ft, (ft[0] + a.face * 22 * sc, ft[1]), lw * 0.70, lw * 0.52, ink)
            tapered(d, to_screen(p["pelvis"], cam), to_screen(p.get("shoulder_pt", p["neck"]), cam),
                    lw * 1.30, lw * 1.10, ink)
            tapered(d, to_screen(p.get("shoulder_pt", p["neck"]), cam), to_screen(p["neck"], cam),
                    lw * 1.10, lw * 0.80, ink)
            for side in ("l", "r"):
                A = p["arms"][side]
                shp, elb, hnd = (to_screen(A["shoulder"], cam), to_screen(A["elbow"], cam),
                                 to_screen(A["hand"], cam))
                tapered(d, shp, elb, lw * 1.10, lw * 0.85, ink)
                tapered(d, elb, hnd, lw * 0.85, lw * 0.62, ink)
                hr_ = lw * 1.30
                d.ellipse([hnd[0] - hr_, hnd[1] - hr_, hnd[0] + hr_, hnd[1] + hr_], fill=ink)
            hc = to_screen(p["head_c"], cam)
            hr = p["head_r"] * cam["scale"] * SS
            d.ellipse([hc[0] - hr, hc[1] - hr, hc[0] + hr, hc[1] + hr], fill=PAPER,
                      outline=ink, width=int(lw * 0.85))
            if a.hair == "cap":
                d.chord([hc[0] - hr * 1.04, hc[1] - hr * 1.10, hc[0] + hr * 1.04, hc[1] + hr * 0.86],
                        190, 350, fill=a.accent)
                d.line([(hc[0] - hr * 1.02, hc[1] - hr * 0.30), (hc[0] + hr * 1.02, hc[1] - hr * 0.34)],
                       fill=ink, width=int(lw * 0.7))
            else:
                d.chord([hc[0] - hr * 1.05, hc[1] - hr * 1.12, hc[0] + hr * 1.05, hc[1] + hr * 0.22],
                        185, 355, fill=(58, 44, 40))
                prev = a.parts(director.state(a, max(0.0, t - 5 / 30)))
                swing = (p["head_angle"] - prev["head_angle"]) * 26 * SS
                base = (hc[0] + hr * 0.92, hc[1] - hr * 0.10)
                mid = (base[0] + hr * 0.62, base[1] + hr * 0.52 + swing * 0.5)
                tip = (mid[0] + hr * 0.24, mid[1] + hr * 0.68 + swing)
                d.line([base, mid, tip], fill=(58, 44, 40), width=int(lw * 1.7), joint="curve")
                d.ellipse([tip[0] - hr * 0.2, tip[1] - hr * 0.2, tip[0] + hr * 0.2, tip[1] + hr * 0.2],
                          fill=(58, 44, 40))
            gx = hr * (0.26 if a.name == "m" else -0.26)
            ey = hc[1] - hr * 0.06
            if st["blink"] > 0.5:
                for s in (-1, 1):
                    d.line([(hc[0] + s * hr * 0.30 - hr * 0.14, ey),
                            (hc[0] + s * hr * 0.30 + hr * 0.14, ey)], fill=ink, width=int(lw * 0.75))
            else:
                for s in (-1, 1):
                    cx0 = hc[0] + s * hr * 0.30 + gx
                    d.ellipse([cx0 - hr * 0.085, ey - hr * 0.10, cx0 + hr * 0.085, ey + hr * 0.10],
                              fill=ink)
            for s in (-1, 1):
                bx = hc[0] + s * hr * 0.30 + gx * 0.7
                by = ey - hr * 0.30 - st["brow"] * hr * 0.10
                d.line([(bx - hr * 0.17 * s, by), (bx + hr * 0.17 * s, by - st["brow"] * hr * 0.08 * s)],
                       fill=ink, width=int(lw * 0.7))
            mo = st["mouth"]
            mh, mw = hr * (0.06 + 0.22 * mo), hr * (0.20 + 0.10 * mo)
            my = hc[1] + hr * 0.34
            if mo > 0.06:
                d.ellipse([hc[0] - mw, my - mh, hc[0] + mw, my + mh], fill=ink)
            else:
                d.arc([hc[0] - mw, my - mh * 2.0, hc[0] + mw, my + mh * 1.2], 15, 165, fill=ink,
                      width=int(lw * 0.7))
        if labels:
            spk, _ = director.speaking(t)
            name = {"m": getattr(director, "name_m", "SAM"),
                    "f": getattr(director, "name_f", "MAYA")}.get(spk or "", "")
            if name:
                try:
                    from PIL import ImageFont
                    fnt = ImageFont.truetype("arialbd.ttf", int(34 * SS))
                except Exception:
                    fnt = None
                d.text((W * SS / 2, H * SS - 116 * SS), name, fill=(122, 106, 86), anchor="mm",
                       font=fnt)
        if watermark:
            d.text((W * SS - 190 * SS / 2 - 30, H * SS - 46 * SS / 2), watermark, fill=(150, 138, 120))
        return img.resize((W, H), Image.LANCZOS)

    return render_frame


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeline", required=True)
    ap.add_argument("--direction")
    ap.add_argument("--audio")
    ap.add_argument("--out", default="out")
    ap.add_argument("--size", default="1080x1920")
    args = ap.parse_args()

    tl = json.loads(pathlib.Path(args.timeline).read_text(encoding="utf-8"))
    direction = json.loads(pathlib.Path(args.direction).read_text(encoding="utf-8")) if args.direction else {}
    W, H = (int(v) for v in args.size.lower().split("x"))
    portrait = H > W
    floor_y = H * 0.78
    cast = [
        Actor("m", x=W * 0.235, floor=floor_y, scale=1.02, hair="cap", sex="m",
              accent=(196, 84, 46), face=1),
        Actor("f", x=W * 0.765, floor=floor_y, scale=0.94, hair="pony", sex="f",
              accent=(70, 104, 138), face=-1),
    ]
    d = Director(tl, cast, direction)
    render_frame = make_renderer(d, cast, (W, H), floor_y)

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    fps = tl.get("fps", 30)
    n = int(math.ceil(tl["total"] * fps))
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-pix_fmt", "yuv420p", str(out / "picture.mp4")], stdin=subprocess.PIPE)
    for i in range(n):
        enc.stdin.write(render_frame(i / fps).tobytes())
        if i % 120 == 0:
            print(f"  frame {i}/{n}", flush=True)
    enc.stdin.close()
    enc.wait()

    if args.audio:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(out / "picture.mp4"),
                        "-i", args.audio, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                        "-shortest", "-movflags", "+faststart", str(out / "film.mp4")], check=True)
        print("->", out / "film.mp4")
    else:
        print("->", out / "picture.mp4")


if __name__ == "__main__":
    main()
