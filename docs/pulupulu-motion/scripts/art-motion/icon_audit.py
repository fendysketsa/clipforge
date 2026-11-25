#!/usr/bin/env python3
"""Classify, group and normalise SVG icons before they enter a film.

Why this exists: a search page gives you ids and slugs, never family metadata. Two icons that
look related in a grid can be a 24x24 stroke-2 line set and a 1024 painted illustration, and
dropping the second into a flat-shape film reads as a sticker. This tool answers, per file:
which grid, line or solid, how many colours, how many paths — and whether the set is one family.

Subcommands
  classify  <paths...>            one line per file: grid, style, colours, paths, verdict
  families  <dir>                 group by (grid, style, colour bucket, stroke weight), flag outliers
  normalise <file> --colour #hex  strip width/height, recolour, keep viewBox; prints a manifest row
  contact   <dir> --out page.html HTML contact sheet to render at final size (pulupulu still)

Text only, stdlib only: this runs on any Python the user has.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from dataclasses import dataclass, asdict

COLOUR_RE = re.compile(r'(?:fill|stroke)="(#[0-9a-fA-F]{3,6}|rgb\([^)]*\)|[a-z]+)"')
VIEWBOX_RE = re.compile(r'viewBox="([-\d.\s]+)"')
WIDTH_RE = re.compile(r'\swidth="[^"]*"')
HEIGHT_RE = re.compile(r'\sheight="[^"]*"')
STROKE_W_RE = re.compile(r'stroke-width="([\d.]+)"')
SHAPE_RE = re.compile(r"<(path|circle|rect|polygon|polyline|line|ellipse)\b")
NAMED_IGNORE = {"none", "currentcolor", "transparent", "inherit"}


@dataclass
class Report:
    path: str
    grid: str
    grid_size: float
    style: str
    colours: int
    colour_list: str
    paths: int
    stroke_width: str
    family: str
    verdict: str

    def row(self) -> str:
        return (f"{os.path.basename(self.path):38s} {self.grid:14s} {self.style:6s} "
                f"{self.colours:2d}c {self.paths:3d}p sw={self.stroke_width:5s} "
                f"{self.verdict}")


def _grid(source: str) -> tuple[str, float]:
    match = VIEWBOX_RE.search(source)
    if not match:
        return ("no-viewbox", 0.0)
    parts = [p for p in match.group(1).split() if p.strip()]
    label = "x".join(parts[2:4]) if len(parts) >= 4 else " ".join(parts)
    try:
        size = float(parts[3]) if len(parts) >= 4 else 0.0
    except ValueError:
        size = 0.0
    return (label, size)


def inspect(path: str, film_style: str) -> Report:
    source = open(path, encoding="utf-8", errors="replace").read()
    grid, size = _grid(source)
    raw_colours = {c.lower() for c in COLOUR_RE.findall(source)} - NAMED_IGNORE
    colours = {c for c in raw_colours if c.startswith("#") or c.startswith("rgb")}
    named = sorted(c for c in raw_colours if not c.startswith(("#", "rgb")))
    strokes = STROKE_W_RE.findall(source)
    has_stroke = bool(strokes) or 'stroke="' in source
    fills_none = 'fill="none"' in source
    style = "line" if (has_stroke and fills_none) else ("mixed" if has_stroke and colours else "solid")
    paths = len(SHAPE_RE.findall(source))
    sw = ",".join(sorted(set(strokes))) or "-"
    colour_list = ",".join(sorted(colours)) or ",".join(named) or "none"

    total_colours = len(colours) + len(named)
    if total_colours >= 5:
        verdict = "multicolour — fights a controlled film palette; skip or force to one colour"
    elif style == "line" and film_style == "solid":
        verdict = "line-art in a flat-fill film — will read as a pasted sticker"
    elif style == "line":
        verdict = "line glyph — fine for a line-film, recolour to the palette"
    elif paths <= 3 and total_colours <= 2:
        verdict = "likely silhouette — confirm on the contact sheet (thin strokes hide in one colour)"
    elif paths >= 40:
        verdict = "very detailed — check it still reads at 1080 px, else simplify"
    else:
        verdict = (f"undecided: {paths} paths / {total_colours} colour — open the contact sheet; "
                   f"one-colour etched art and silhouettes look identical in text")

    bucket = "multi" if total_colours >= 5 else ("mono" if total_colours <= 2 else "duo")
    family = f"{grid}|{style}|{bucket}|{sw}"
    return Report(path, grid, size, style, total_colours, colour_list, paths, sw, family, verdict)


def collect(targets: list[str]) -> list[str]:
    found: list[str] = []
    for target in targets:
        if os.path.isdir(target):
            for name in sorted(os.listdir(target)):
                if name.lower().endswith(".svg"):
                    found.append(os.path.join(target, name))
        elif target.lower().endswith(".svg"):
            found.append(target)
    return found


def cmd_classify(args: argparse.Namespace) -> int:
    files = collect(args.targets)
    if not files:
        print("no .svg found", file=sys.stderr)
        return 2
    reports = [inspect(f, args.film_style) for f in files]
    if args.json:
        print(json.dumps([asdict(r) for r in reports], indent=1))
        return 0
    print(f"{'file':38s} {'grid':14s} {'style':6s} {'col':3s} {'paths':4s} {'stroke':8s} verdict")
    for report in reports:
        print(report.row())
    print(f"\n{len(reports)} file(s) · style of the film: {args.film_style}")
    return 0


def cmd_families(args: argparse.Namespace) -> int:
    files = collect(args.targets)
    reports = [inspect(f, args.film_style) for f in files]
    groups: dict[str, list[Report]] = {}
    for report in reports:
        groups.setdefault(report.family, []).append(report)
    print(f"{len(reports)} file(s) in {len(groups)} group(s) "
          f"(grid | line-or-solid | colour bucket | stroke width)\n")
    for family, members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        mark = "OK " if len(members) >= 2 else "one"
        print(f"[{mark}] {family}  -> {len(members)} file(s)")
        for member in members:
            print(f"        {os.path.basename(member.path):36s} {member.verdict}")
    if len(groups) > 1:
        print("\nMore than one group means more than one family. Either keep the biggest group and "
              "redraw the rest at its stroke weight, or import a whole collection instead.")
    return 0


def cmd_normalise(args: argparse.Namespace) -> int:
    source = open(args.file, encoding="utf-8", errors="replace").read()
    out = WIDTH_RE.sub("", source)
    out = HEIGHT_RE.sub("", out)
    if args.colour:
        out = re.sub(r'(fill|stroke)="(#[0-9a-fA-F]{3,6}|rgb\([^)]*\))"',
                     lambda m: f'{m.group(1)}="{args.colour}"', out)
    if args.strip_metadata:
        out = re.sub(r"<metadata\b.*?</metadata>", "", out, flags=re.S)
        out = re.sub(r"<\?xml[^>]*\?>", "", out)
        out = re.sub(r"<!--.*?-->", "", out, flags=re.S)
    destination = args.out or args.file
    if not args.dry_run:
        open(destination, "w", encoding="utf-8", newline="\n").write(out.strip() + "\n")
    grid, _ = _grid(out)
    paths = len(SHAPE_RE.findall(out))
    print(f"{'would write' if args.dry_run else 'wrote'} {destination}  grid={grid} paths={paths}")
    print(f"manifest row: | `{os.path.basename(destination)}` | <source URL> | <licence> |")
    return 0


def cmd_contact(args: argparse.Namespace) -> int:
    files = collect(args.targets)
    if not files:
        print("no .svg found", file=sys.stderr)
        return 2
    cards = []
    for path in files:
        report = inspect(path, args.film_style)
        svg = open(path, encoding="utf-8", errors="replace").read().strip()
        body = re.sub(r"<\?xml[^>]*\?>", "", svg)
        cards.append(
            f'<figure><div class="art">{body}</div>'
            f'<figcaption>{html.escape(os.path.basename(path))}<br>'
            f'{report.grid} · {report.style} · {report.colours}c · {report.paths}p</figcaption></figure>')
    page = f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
  body {{ margin:0; background:#111; color:#eee; font:14px/1.4 system-ui, sans-serif; }}
  main {{ display:grid; grid-template-columns:repeat({args.columns}, 1fr); gap:{args.gap}px; padding:{args.gap}px; }}
  figure {{ margin:0; background:#1c1c1c; padding:{args.gap // 2}px; }}
  .art {{ height:{args.size}px; display:flex; align-items:center; justify-content:center; }}
  .art svg {{ max-width:100%; max-height:100%; }}
  figcaption {{ font-size:11px; color:#8fa; margin-top:6px; }}
</style></head><body><main>{''.join(cards)}</main></body></html>"""
    open(args.out, "w", encoding="utf-8", newline="\n").write(page)
    print(f"wrote {args.out} ({len(cards)} icons at {args.size}px). Render it, then look: "
          f"detail that disappears here also disappears on a phone.")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--film-style", default="solid", choices=["solid", "line", "mixed"],
                        help="how the film itself is drawn; decides whether a glyph will clash")
    sub = parser.add_subparsers(dest="command", required=True)

    classify = sub.add_parser("classify", help="per-file grid, style, colours, paths, verdict")
    classify.add_argument("targets", nargs="+")
    classify.add_argument("--json", action="store_true")
    classify.set_defaults(func=cmd_classify)

    families = sub.add_parser("families", help="group icons and flag the outliers")
    families.add_argument("targets", nargs="+")
    families.set_defaults(func=cmd_families)

    normalise = sub.add_parser("normalise", help="strip width/height, recolour, keep viewBox")
    normalise.add_argument("file")
    normalise.add_argument("--colour", help="hex to force every fill/stroke to, e.g. #120a08")
    normalise.add_argument("--out")
    normalise.add_argument("--strip-metadata", action="store_true", default=True)
    normalise.add_argument("--dry-run", action="store_true")
    normalise.set_defaults(func=cmd_normalise)

    contact = sub.add_parser("contact", help="HTML sheet of every icon at final size")
    contact.add_argument("targets", nargs="+")
    contact.add_argument("--out", default="icons-contact.html")
    contact.add_argument("--size", type=int, default=120, help="box size in px at final scale")
    contact.add_argument("--columns", type=int, default=6)
    contact.add_argument("--gap", type=int, default=16)
    contact.set_defaults(func=cmd_contact)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
