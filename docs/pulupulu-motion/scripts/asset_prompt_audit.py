"""Audit a written asset-prompt set against the universal rules in `stickman-visual-prompts.md`.

A prompt set is cheap to fix and expensive to discover in a render: a missing establishing plate, a prompt
that says "same as before", two neighbouring shots at the same size, or a character whose head and limbs are
never restated. This checks all of that before a single generation is spent.

Usage:
    python asset_prompt_audit.py prompts.md              # expects 7 prompts
    python asset_prompt_audit.py prompts.md --count 9

Prompt-file format — one section per plate:

    ### 1. Main — characters — [action summary]

    Scene: ...            (or Subject: for a figure-free plate)
    Camera: medium-wide, low angle, figure right of centre, focus on the hands
    Characters: ... big round head ... black stick-line limbs ... muted blue shirt ...
    Action: ...
    Background: ...
    Style: flat-minimal. Flat digital illustration, solid fills, crisp edges. Prohibited: gradients, ...
    Composition: ...

A plate that must contain no figures says so: any of "no characters", "no people", "no figures".

Exit 0 = every check passed. Exit 1 prints each failure with the plate number.
"""
import argparse
import re
import sys

SHOT_SIZES = ["extreme wide", "wide", "medium-wide", "medium wide", "medium close-up", "medium",
              "close-up", "extreme close-up", "insert"]
CROSS_REF = [r"same character", r"same style", r"as before", r"previous image", r"previous scene",
             r"continue the previous", r"refer to the earlier", r"as we established"]
VAGUE = [r"\bbeautiful\b", r"\bstunning\b", r"\bcinematic\b", r"\bamazing\b", r"\bhigh quality\b",
         r"\bbest quality\b", r"\bmasterpiece\b"]


def sections(text):
    """Split a prompt document on '### <n>.' headings."""
    parts = re.split(r"\n(?=#{3}\s*\d+[.)])", text)
    out = []
    for p in parts:
        m = re.match(r"#{3}\s*(\d+)[.)]\s*(.*)", p.strip())
        if not m:
            continue
        out.append({"n": int(m.group(1)), "title": m.group(2).strip(), "body": p.strip()})
    return out


def field(body, name):
    m = re.search(rf"^\s*{name}\s*:\s*(.+)$", body, re.M | re.I)
    return m.group(1).strip() if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompts")
    ap.add_argument("--count", type=int, default=7)
    args = ap.parse_args()

    text = open(args.prompts, encoding="utf-8").read()
    secs = sections(text)
    fails = []

    def fail(n, msg):
        fails.append(f"plate {n}: {msg}")

    if len(secs) != args.count:
        fails.append(f"expected {args.count} plates, found {len(secs)}")
    if not secs:
        print("no plates found — check the '### <n>.' headings")
        return 1

    figure_free, sizes = [], []
    for s in secs:
        b = s["body"]
        # figure-free plates
        no_fig = bool(re.search(r"no characters|no people|no figures|no silhouettes|no human", b, re.I))
        if no_fig:
            figure_free.append(s["n"])
        # cross-reference and vague language
        for pat in CROSS_REF:
            if re.search(pat, b, re.I):
                fail(s["n"], f"cross-reference phrase '{pat}' — restate the facts instead")
        for pat in VAGUE:
            if re.search(pat, b, re.I):
                fail(s["n"], f"vague adjective '{pat.strip(chr(92) + 'b')}' carries no instruction")
        # camera
        cam = field(b, "camera")
        if not cam:
            fail(s["n"], "no 'Camera:' line")
        else:
            # longest first: "medium-wide" must not be read as "wide", or neighbouring-shot
            # repetition goes undetected
            size = next((x for x in sorted(SHOT_SIZES, key=len, reverse=True) if x in cam.lower()), None)
            if size is None:
                fail(s["n"], "camera line names no shot size")
            else:
                sizes.append(size)
            if not re.search(r"eye level|low angle|high angle|overhead|three-quarter|profile|"
                             r"over-the-shoulder|from behind|angle", cam, re.I):
                fail(s["n"], "camera line names no angle")
        # scene/subject
        if not (field(b, "scene") or field(b, "subject") or field(b, "setting")):
            fail(s["n"], "no 'Scene:' or 'Subject:' line")
        # character restatement
        if not no_fig:
            low = b.lower()
            if "head" not in low:
                fail(s["n"], "character plate does not describe the head")
            if not re.search(r"stick-line|stick line|tapered|limb", low):
                fail(s["n"], "character plate does not describe the limbs")
            if not (field(b, "characters") and field(b, "action")):
                fail(s["n"], "character plate needs both 'Characters:' and 'Action:'")
        # style + prohibition
        style = field(b, "style")
        if not style:
            fail(s["n"], "no 'Style:' line")
        elif not re.search(r"prohibit|avoid|no ", style, re.I):
            fail(s["n"], "'Style:' line carries no prohibition list")

    if len(figure_free) != 2:
        fails.append(f"expected exactly 2 figure-free plates (one establishing, one detail), found "
                     f"{len(figure_free)}: {figure_free}")
    for a, b in zip(sizes, sizes[1:]):
        if a == b:
            fails.append(f"two neighbouring plates share the shot size '{a}'")

    print(f"plates: {len(secs)}  figure-free: {figure_free}  shot sizes: {sizes}")
    if fails:
        print("\n".join("  FAIL " + f for f in fails))
        print(f"\nASSET PROMPT AUDIT FAIL ({len(fails)})")
        return 1
    print("\nASSET PROMPT AUDIT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
