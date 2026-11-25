"""Speech / thought balloons for frame-rendered films: layout geometry + drawing + timing.

The layout is a faithful port of `js/bubbles.js` from hmelberg/stick (MIT), which solves the problem
every hand-rolled balloon system gets wrong:

  * a bubble avoids every OTHER figure's head and every other settled bubble, but never its own speaker
  * if there is room above an obstacle it lifts over it; if not it slides beside it, trying the
    speaker's own side first
  * the push is weighted by the obstacle's alpha, so a bubble glides back as the one below fades out
  * the push eases in with horizontal overlap, so idle sway at the edge of a collision cannot make a
    bubble flicker between two positions

Constants are the reference's, in scene units, scaled here to pixels.

Standalone test (no film needed) — exercises the degenerate cases:
    python bubbles.py --selftest
"""
import argparse
import math

# Pixel constants for a 1080-wide canvas, agreed with the written spec so code and page cannot disagree.
# Scale everything by W/1080 for another width.
GAP = 18.0        # clear space kept between a bubble and what it avoids
MARGIN = 44.0     # distance kept from the frame edge (the side safe margin)
EPS = 1.0         # placed just past the gap so rounding cannot re-trigger a hit
SOFT = 28.0       # horizontal overlap over which a push eases in
HEAD_OUT = 1.30   # other figures' heads, as a multiple of head radius
HEAD_SELF = 1.28  # the speaker's own head: protects hat/hair, never the mouth
TAIL_GAP = 46.0   # room reserved above a head so the tail is a tail, not a stub


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


class Layout:
    """Scene-unit layout (the reference's own numbers). Scale in/out with `unit`."""

    def __init__(self, unit=1.0, protect_own_head=True):
        self.u = unit
        # The reference lets a bubble sit on its own speaker's head. Our films may not: the hat and
        # the hairline are part of the character, so the speaker's head is an obstacle too.
        self.protect_own_head = protect_own_head

    def layout(self, bubbles, heads, view):
        u = self.u
        gap, margin, eps, soft = GAP * u, MARGIN * u, EPS * u, SOFT * u
        v = view or {"x": 0, "y": 0, "w": 100 * u, "h": 100 * u}
        top = v["y"] + margin

        def overlap_x(ax, aw, bx, bw):
            return min(ax + aw, bx + bw) - max(ax, bx)

        def hits(a, b):
            return (overlap_x(a["x"], a["w"], b["x"], b["w"]) > -gap
                    and a["y"] < b["y"] + b["h"] + gap
                    and a["y"] + a["h"] > b["y"] - gap)

        def fit_x(cx, w):
            lo, hi = v["x"] + w / 2 + margin, v["x"] + v["w"] - w / 2 - margin
            return v["x"] + v["w"] / 2 if lo > hi else _clamp(cx, lo, hi)

        placed, out = [], []
        for b in bubbles:
            w, h = b["w"], b["h"]
            cx = fit_x(b["cx"], w)
            y = max(top, b["y"])
            dx = dy = 0.0
            def head_box(hd):
                mult = HEAD_SELF if hd["fig"] == b["fig"] else HEAD_OUT
                r = hd["r"] * mult
                # A balloon heading for the space above a head must reserve room for its tail,
                # otherwise the solver leaves it close enough that the tail collapses to a stub.
                above = (b["y"] + b["h"] / 2) < hd["y"]
                pad = TAIL_GAP if above else 0.0
                return {"x": hd["x"] - r, "y": hd["y"] - r - pad, "w": r * 2, "h": r * 2 + pad,
                        "alpha": 1.0, "head": True}

            obstacles = list(placed) + [head_box(hd) for hd in (heads or [])
                                        if self.protect_own_head or hd["fig"] != b["fig"]]
            skip = set()

            for _ in range(8):
                me = {"x": cx - w / 2, "y": y, "w": w, "h": h}
                ob = next((o for o in obstacles if id(o) not in skip and hits(me, o)), None)
                if ob is None:
                    break
                depth = overlap_x(me["x"], w, ob["x"], ob["w"]) + gap
                weight = _clamp(depth / soft, 0.0, 1.0) * (1.0 if ob.get("alpha") is None else ob["alpha"])
                up = ob["y"] - gap - eps - h
                if up >= top:                      # room above: lift over it
                    dy += (up - y) * weight
                    y = up
                    continue
                # The reference gives up here for a head ("no room above a head: live with it"),
                # which leaves a balloon sitting on someone's face. Our films cannot afford that,
                # so a head falls through to the same side-slide a bubble gets, and is only
                # accepted as covered when no side is clear either.
                ob_cx = ob["x"] + ob["w"] / 2
                first = 1 if (b.get("headX", cx) >= ob_cx) else -1
                moved = False
                for d in (first, -first):
                    nx = fit_x(ob_cx + d * (ob["w"] / 2 + w / 2 + gap + eps), w)
                    if not hits({"x": nx - w / 2, "y": y, "w": w, "h": h}, ob):
                        dx += (nx - cx) * weight
                        cx = nx
                        moved = True
                        break
                if not moved:
                    skip.add(id(ob))

            placed.append({"x": cx - w / 2, "y": y, "w": w, "h": h,
                           "alpha": 1.0 if b.get("alpha") is None else b["alpha"]})

            # Eased position: what the eye sees. The reference draws this while colliding on the
            # settled rect, so a partially weighted push can leave a bubble grazing a head.
            eased = {"cx": fit_x(fit_x(b["cx"], w) + dx, w), "y": max(top, max(top, b["y"]) + dy)}
            # Hard face-safety guard: if the eased rect touches a head while the settled rect is
            # clear, snap to settled. Never let the easing put a bubble on a face.
            eased_rect = {"x": eased["cx"] - w / 2, "y": eased["y"], "w": w, "h": h}
            settled_rect = {"x": cx - w / 2, "y": y, "w": w, "h": h}
            if any(hits(eased_rect, o) for o in obstacles if o.get("head")) and \
               not any(hits(settled_rect, o) for o in obstacles if o.get("head")):
                eased = {"cx": cx, "y": y}
            out.append(eased)
        return out


def wrap_lines(text, max_chars):
    words, lines, cur = text.split(), [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if len(cand) > max_chars and cur:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


def fit_text(text, max_chars=24, max_lines=3):
    """Returns (lines, truncated). Overflow loses the tail but never the meaning of the first line."""
    lines = wrap_lines(text, max_chars)
    if len(lines) <= max_lines:
        return lines, False
    kept = lines[:max_lines]
    kept[-1] = (kept[-1][: max_chars - 1] + "…") if len(kept[-1]) >= max_chars else (kept[-1] + "…")
    return kept, True


def selftest():
    """Degenerate cases the layout must survive. Prints PASS/FAIL per case."""
    lay = Layout(unit=1.0)
    view = {"x": 44, "y": 140, "w": 992, "h": 1580}
    heads = [{"fig": "a", "x": 260, "y": 900, "r": 63}, {"fig": "b", "x": 820, "y": 920, "r": 63}]
    ok = True

    def check(name, cond):
        nonlocal ok
        ok = ok and cond
        print(f"  {'PASS' if cond else 'FAIL'}  {name}")

    # 1. one bubble stays in the view
    r = lay.layout([{"fig": "a", "cx": 260, "y": 400, "w": 320, "h": 140, "alpha": 1}], heads, view)
    check("single bubble inside view",
          view["x"] <= r[0]["cx"] - 160 and r[0]["cx"] + 160 <= view["x"] + view["w"])

    # 2. a bubble pushed to the frame edge is clamped, never off-screen
    r = lay.layout([{"fig": "a", "cx": 10, "y": 400, "w": 360, "h": 140, "alpha": 1}], heads, view)
    check("edge bubble clamped", r[0]["cx"] - 180 >= view["x"] - 0.01)

    # 3. two bubbles never overlap
    bs = [{"fig": "a", "cx": 400, "y": 400, "w": 320, "h": 140, "alpha": 1},
          {"fig": "b", "cx": 430, "y": 420, "w": 320, "h": 140, "alpha": 1}]
    r = lay.layout(bs, heads, view)
    a = {"x": r[0]["cx"] - 160, "y": r[0]["y"], "w": 320, "h": 140}
    b = {"x": r[1]["cx"] - 160, "y": r[1]["y"], "w": 320, "h": 140}
    sep = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
    check("two bubbles do not overlap", sep <= -GAP + 0.9 or a["y"] + a["h"] <= b["y"] - GAP + 0.9
          or b["y"] + b["h"] <= a["y"] - GAP + 0.9)

    # 4. three bubbles still resolve without covering either head (a real rect test, not just y)
    bs3 = [{"fig": "a", "cx": 300 + 90 * i, "y": 420, "w": 320, "h": 140, "alpha": 1} for i in range(3)]
    r = lay.layout(bs3, heads, view)

    def rect_of(res):
        return {"x": res["cx"] - 160, "y": res["y"], "w": 320, "h": 140}

    def overlaps_head(rect, hd):
        return (rect["x"] < hd["x"] + hd["r"] and rect["x"] + rect["w"] > hd["x"] - hd["r"]
                and rect["y"] < hd["y"] + hd["r"] and rect["y"] + rect["h"] > hd["y"] - hd["r"])

    cover = any(overlaps_head(rect_of(res), hd)
                for res in r for hd in (heads[1],) if hd["fig"] != "a")
    check("three bubbles do not sit on the other head", not cover)

    # 4b. a bubble whose only escape is beside a head must still clear it
    heads_close = [{"fig": "a", "x": 330, "y": 620, "r": 63}, {"fig": "b", "x": 560, "y": 620, "r": 63}]
    r2 = lay.layout([{"fig": "a", "cx": 560, "y": 500, "w": 280, "h": 130, "alpha": 1}], heads_close, view)
    check("bubble moved off the listener's head", not overlaps_head(
        {"x": r2[0]["cx"] - 140, "y": r2[0]["y"], "w": 280, "h": 130}, heads_close[1]))

    # 4c. the speaker's own head is an obstacle too (protects hat and hairline)
    r3 = lay.layout([{"fig": "a", "cx": 260, "y": 850, "w": 300, "h": 120, "alpha": 1}], heads, view)
    check("bubble does not sit on the speaker's own head", not overlaps_head(
        {"x": r3[0]["cx"] - 150, "y": r3[0]["y"], "w": 300, "h": 120}, heads[0]))

    # 5. text fitting
    lines, cut = fit_text("I finally quit my job yesterday and I have been thinking about it for a year", 22, 3)
    check("long text fits 3 lines and is marked truncated", len(lines) <= 3 and cut)

    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(selftest())
    print(__doc__)

# ---------------------------------------------------------------- drawing
def measure(text, font):
    """Width/height of a wrapped block without a canvas, using the font's own metrics."""
    lines, _ = fit_text(text, 26, 3)
    w = max(font.getbbox(l)[2] for l in lines) if lines else 0
    h = sum(font.getbbox(l)[3] - font.getbbox(l)[1] + 8 for l in lines)
    return w, h, lines


def bubble_size(text, font, pad_x=26, pad_y=20):
    w, h, lines = measure(text, font)
    return w + pad_x * 2, h + pad_y * 2, lines


def draw_balloon(d, text, target, box, fill=(252, 248, 238), ink=(38, 32, 30),
                 radius=26, tail_w=None, width=4, head_r=63):
    """Draw one balloon with a tail pointing at `target` (the speaker's head centre).

    `box` is the settled rect from `Layout.layout`, i.e. {"cx", "y"} plus the intended w/h.
    Draw order matters: tail first, then body, then text - a tail can then never cross the text.
    """
    # tail first
    cx, y, w, h = box["cx"], box["y"], box["w"], box["h"]
    sel = _tail_edge(cx, y, w, h, target, head_r)
    if sel is not None:
        base, tip = sel[0], sel[1]
        half = (tail_w or max(26, min(w, h) * 0.20)) / 2
        # fill plus an ink outline on the two long sides: a fill-only tail is invisible whenever it
        # sits on a background of its own colour, which is most of the time
        d.polygon([(base[0] - half, base[1]), (base[0] + half, base[1]), tip], fill=fill,
                  outline=ink, width=width)
    # body, with the tail's base seam covered
    d.rounded_rectangle([cx - w / 2, y, cx + w / 2, y + h], radius=radius, fill=fill,
                        outline=ink, width=width)
    if sel is not None:
        base = sel[0]
        d.line([(base[0] - (tail_w or 26) / 2 + 2, base[1]), (base[0] + (tail_w or 26) / 2 - 2, base[1])],
               fill=fill, width=width)
    return {"cx": cx, "y": y, "w": w, "h": h, "edge": sel[3] if sel else None}


def _tail_edge(cx, y, w, h, target, head_r=63):
    """Pick the edge facing the target, clamp the base away from the rounded corners, and stop the
    tip at 1.22r + 10 px from the head so the tail belongs unambiguously to one speaker."""
    tx, ty = target
    gap = 18
    stop = head_r * 1.22 + 10          # the tail stops short of the head, it never enters it
    if ty >= y + h + gap:
        edge = "bottom"
        by = y + h
        bx = _clamp(tx, cx - w / 2 + min(36, w * 0.28), cx + w / 2 - min(36, w * 0.28))
        tip_y = min(ty - stop, ty) if ty - stop > by + 16 else by + 16
        return ((bx, by), (tx, tip_y), "bottom", "bottom")
    if ty <= y - gap:
        edge = "top"
        by = y
        bx = _clamp(tx, cx - w / 2 + min(36, w * 0.28), cx + w / 2 - min(36, w * 0.28))
        tip_y = max(ty + stop, ty) if ty + stop < by - 16 else by - 16
        return ((bx, by), (tx, tip_y), "top", "top")
    by = _clamp(ty, y + min(36, h * 0.28), y + h - min(36, h * 0.28))
    if tx < cx:
        bx = cx - w / 2
        return ((bx, by), (min(tx, bx - 16), ty), "left", "left")
    bx = cx + w / 2
    return ((bx, by), (max(tx, bx + 16), ty), "right", "right")
