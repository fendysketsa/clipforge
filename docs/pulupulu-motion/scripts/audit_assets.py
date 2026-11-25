#!/usr/bin/env python3
"""Count the distinct assets each scene declares in a MANIFEST, and catch assets reused across scenes.

A brief that asks for ten assets per scene is worthless without a count, because the agent's own summary says
the count was met whether or not it was. This reads the manifest's per-scene tables instead of trusting prose.

    python scripts/audit_assets.py MANIFEST.md --min 10
    python scripts/audit_assets.py build*/MANIFEST.md --allow watermark --allow grain

Scene headings are any `##`/`###`/`####` line containing the word "scene" (or a `### 03 — name` shape). Table
rows are pipe rows minus the separator and the header. A leading all-digit cell is treated as a row number, so
both `<name> | how | why` and `1 | <name> | how | why` tables parse.

Exit 0 clean, 1 too thin or reused, 2 unreadable input.
"""
import argparse
import pathlib
import re
import sys

HEADING = re.compile(r"^#{2,4}\s+(.*)$")
SEPARATOR = re.compile(r"^\|?[\s:|-]+\|?$")
HEADERISH = re.compile(r"(asset|name|element|item)", re.I)


def blocks(text):
    """Split the manifest into scene blocks keyed by heading."""
    current, found = None, []
    for line in text.splitlines():
        match = HEADING.match(line)
        if match:
            head = match.group(1).strip()
            if re.search(r"scene", head, re.I) or re.match(r"^\d+\b", head):
                current = [head, []]
                found.append(current)
            else:
                current = None
            continue
        if current is not None:
            current[1].append(line)
    return found


def assets_in(lines):
    names, rows = [], 0
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|") or SEPARATOR.match(stripped):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not any(cells):
            continue
        rows += 1
        if rows == 1 and HEADERISH.search(" ".join(cells[:2])):
            continue  # header row
        if cells[0].isdigit() and len(cells) > 1:
            name = cells[1]
        else:
            name = cells[0]
        name = re.sub(r"[*`_]", "", name).strip().lower()
        if name:
            names.append(name)
    return names


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifests", nargs="+", help="MANIFEST.md files, or folders containing one")
    parser.add_argument("--min", type=int, default=10, help="assets required per scene (default 10)")
    parser.add_argument("--allow", action="append", default=[], help="asset name(s) exempt from the reuse rule")
    parser.add_argument("--allow-duplicates", action="store_true", help="count only; do not fail on reuse")
    args = parser.parse_args()

    paths = []
    for target in args.manifests:
        path = pathlib.Path(target)
        if path.is_dir():
            paths.extend(sorted(path.glob("**/MANIFEST.md")))
        elif path.exists():
            paths.append(path)
        else:
            sys.exit(f"audit_assets: no such path {target}")
    if not paths:
        sys.exit("audit_assets: no MANIFEST.md found")

    allowed = {name.strip().lower() for name in args.allow}
    thin, reused = [], []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        scenes = blocks(text)
        if not scenes:
            print(f"warn {path}: no scene headings matched — check the manifest layout")
            continue
        seen = {}
        total = 0
        for head, lines in scenes:
            names = assets_in(lines)
            total += len(names)
            if len(names) < args.min:
                thin.append((path.name, head, len(names)))
            for name in names:
                if name not in allowed:
                    seen.setdefault(name, []).append(head)
        for name, where in seen.items():
            if len(where) > 1:
                reused.append((path.name, name, len(where), where[0]))
        print(f"{path.name}: {len(scenes)} scene(s), {total} asset(s), "
              f"min {min((len(assets_in(l)) for _, l in scenes), default=0)}/scene")

    for name, head, count in thin:
        print(f"FAIL {name} [{head[:60]}] only {count} asset(s), needs {args.min}")
    if not args.allow_duplicates:
        for name, asset, count, first in reused:
            print(f"FAIL {name} asset reused in {count} scenes ({first[:40]} …): {asset[:60]}")

    problems = len(thin) + (0 if args.allow_duplicates else len(reused))
    print(f"\n{problems} problem(s)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
