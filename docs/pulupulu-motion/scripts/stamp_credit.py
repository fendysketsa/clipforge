#!/usr/bin/env python3
"""Stamp one credit line into every source and document of a repo this user owns.

Idempotent: a file that already carries the mark in its first lines is skipped. Placement depends on
the file type so the mark never breaks a parser — after YAML frontmatter for Markdown, after a shebang
for Python/shell, after a doctype for HTML, never into JSON at all.

    python stamp_credit.py . --owner Alucard0x1
    python stamp_credit.py . --owner Alucard0x1 --dry-run

Then re-prove the tree parses: `python -m compileall -q .`, `node --check` on .js, `json.load` on .json.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

LAYOUT = {
    ".py": "# {mark}",
    ".sh": "# {mark}",
    ".yml": "# {mark}",
    ".yaml": "# {mark}",
    ".js": "// {mark}",
    ".mjs": "// {mark}",
    ".css": "/* {mark} */",
    ".html": "<!-- {mark} -->",
    ".md": "<!-- {mark} -->",
}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".om", "out", ".tts-cache", "vendor"}


def frontmatter_end(lines: list[str]) -> int:
    """Index just past a closing '---' when the file opens with YAML frontmatter."""
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                return index + 1
    return 0


def stamp(path: str, template: str, mark: str, pattern: re.Pattern) -> str:
    lines = open(path, encoding="utf-8", errors="replace").read().split("\n")
    if any(pattern.search(line) for line in lines[:8]):
        return "skip"
    extension = os.path.splitext(path)[1].lower()
    line = template.format(m=mark)
    if extension == ".md":
        at = frontmatter_end(lines)
        pad = [""] if at else []
        new = lines[:at] + pad + [line] + pad + lines[at:]
    elif extension in (".py", ".sh"):
        at = 1 if lines and lines[0].startswith("#!") else 0
        new = lines[:at] + [line] + lines[at:]
    elif extension == ".html":
        at = 1 if lines and lines[0].lower().startswith("<!doctype") else 0
        new = lines[:at] + [line] + lines[at:]
    else:
        new = [line] + lines
    open(path, "w", encoding="utf-8", newline="\n").write("\n".join(new))
    return "stamped"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--owner", required=True, help="name to credit, e.g. Alucard0x1")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    mark = f"by {args.owner}"
    pattern = re.compile(rf"\bby {re.escape(args.owner)}\b")
    counts = {"stamped": 0, "skip": 0}
    stamped, skipped_json = [], 0

    for dirpath, dirnames, filenames in os.walk(args.root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in sorted(filenames):
            extension = os.path.splitext(name)[1].lower()
            path = os.path.join(dirpath, name)
            if extension == ".json":
                skipped_json += 1          # no comment syntax: a mark here breaks every consumer
                continue
            template = LAYOUT.get(extension)
            if not template:
                continue
            if args.dry_run:
                lines = open(path, encoding="utf-8", errors="replace").read().split("\n")
                already = any(pattern.search(line) for line in lines[:8])
                counts["skip" if already else "stamped"] += 1
                if not already:
                    stamped.append(path)
                continue
            outcome = stamp(path, template, mark, pattern)
            counts[outcome] += 1
            if outcome == "stamped":
                stamped.append(path)

    total = counts["stamped"] + counts["skip"]
    verb = "would stamp" if args.dry_run else "stamped"
    print(f"{verb} {counts['stamped']}/{total} file(s) · {counts['skip']} already carried the mark · "
          f"{skipped_json} JSON skipped (no comment syntax)")
    for path in stamped[:20]:
        print(f"  {path}")
    if len(stamped) > 20:
        print(f"  … {len(stamped) - 20} more")
    print("now re-prove the tree: compileall · node --check · json.load")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
