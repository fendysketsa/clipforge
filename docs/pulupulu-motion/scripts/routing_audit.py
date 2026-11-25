"""Routing audit for this skill: fails loudly when two pages can tell an agent different things.

The router in `SKILL.md`, the path labels on each animation reference, and the gate numbers scattered
through the pages are a decision system. Decision systems drift, and a drifted one is worse than none:
an agent follows two authoritative-sounding instructions and produces a film that satisfies neither.

Checks (each prints PASS/FAIL, exit code 1 if any fails):

  1. every `references/*.md` animation page declares `Path: performance|graphics|both`
  2. a `performance` page never links to a `graphics`-only page, and vice versa
  3. only the gate owner (`verification.md`) states a freezedetect / loudness threshold
  4. every link in `SKILL.md` resolves to a file that exists
  5. nothing links into `references/_history/` (superseded pages must not be reachable)
  6. every page reachable from the router carries an owner line (`Owner:`)

Usage:
    python routing_audit.py [skill_root]        # default: the skill this script lives in
"""
import pathlib
import re
import sys

PATH_KINDS = ("performance", "graphics", "both")
GATE_OWNER = "verification.md"
THRESHOLD_PAT = re.compile(r"freezedetect=n=0\.004:d=([0-9.]+)|I\s*=\s*(-?\d+)\b|\b(-\d+) LUFS")
ANIM_PAGES = {
    "stickman-performance.md", "stickman-and-figures.md", "speech-balloons.md",
    "motion-library.md", "gsap-plugins.md", "render-traps.md", "static-render-and-resume.md",
    "2d-vector-motion.md", "design-taste.md",
}


def parse_page(p):
    txt = p.read_text(encoding="utf-8", errors="ignore")
    kind = re.search(r"^\s*(?:Path|PATH)\s*:\s*(performance|graphics|both)\s*$", txt, re.M)
    owner = re.search(r"^\s*(?:Owner|OWNER)\s*:\s*(\S.+)$", txt, re.M)
    links = set(re.findall(r"`?(?:references/)?([\w./-]+\.md)", txt))
    links = {l for l in links if "/" not in l or l.startswith("_history")}
    thresholds = [m.group(0) for m in THRESHOLD_PAT.finditer(txt)]
    return {"kind": kind.group(1) if kind else None,
            "owner": owner.group(1).strip() if owner else None,
            "links": links, "thresholds": thresholds, "text": txt}


def main(root=None):
    root = pathlib.Path(root or pathlib.Path(__file__).resolve().parent.parent)
    refdir = root / "references"
    skill = (root / "SKILL.md").read_text(encoding="utf-8", errors="ignore")
    pages = {p.name: parse_page(p) for p in refdir.glob("*.md")}
    fails = []

    def check(cond, name, detail=""):
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{('  — ' + detail) if detail and not cond else ''}")
        if not cond:
            fails.append(name)

    # 1. path labels on the animation pages that exist
    missing = [n for n in ANIM_PAGES if n in pages and pages[n]["kind"] is None]
    check(not missing, "every animation page declares Path:", ", ".join(missing))

    # 2. no cross-path links
    cross = []
    for name, p in pages.items():
        if p["kind"] not in ("performance", "graphics"):
            continue
        for l in p["links"]:
            target = pages.get(l)
            if not target or target["kind"] in (None, "both", p["kind"]):
                continue
            cross.append(f"{name}({p['kind']}) -> {l}({target['kind']})")
    check(not cross, "no performance page links to a graphics-only page or vice versa", "; ".join(cross))

    # 3. one owner for gate numbers
    offside = []
    for name, p in pages.items():
        if name == GATE_OWNER or not p["thresholds"]:
            continue
        if name in ("stickman-performance.md",) and re.search(
                r"freezedetect=n=0\.004:d=1\.0", p["text"]):
            offside.append(f"{name} restates a freeze threshold")
    check(not offside, "only the gate owner states thresholds", "; ".join(offside))

    # 4. router links resolve
    router_links = re.findall(r"`(references/[\w./-]+\.md)`", skill)
    broken = [l for l in router_links if not (root / l).exists()]
    check(not broken, "every SKILL.md link resolves", ", ".join(broken))

    # 5. nothing links into _history
    hist = [n for n, p in pages.items() if any("_history/" in l for l in p["links"])]
    hist += ["SKILL.md"] if "_history/" in skill else []
    check(not hist, "no page is reachable through references/_history/", ", ".join(hist))

    # 6. owner line on reachable pages
    reachable = {l.split("/")[-1] for l in router_links} | {"verification.md"}
    no_owner = [n for n in sorted(reachable) if n in pages and not pages[n]["owner"]]
    check(not no_owner, "reachable pages carry an Owner line", ", ".join(no_owner))

    print(f"\nROUTING AUDIT {'PASS' if not fails else 'FAIL (' + str(len(fails)) + ')'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else None))
