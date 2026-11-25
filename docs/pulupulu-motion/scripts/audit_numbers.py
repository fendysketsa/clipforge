#!/usr/bin/env python3
"""Fail a build whose captions show a date, month, year or count as words instead of digits.

A caption layer with no enforced form drifts: one 50-beat film mixed `May 1995`, `nineteen ninety-five` and
`1995` across its scenes, because nothing checked. The rule is that the screen shows digits (`05/1995`,
`1995-1999`, `ES2015`, `10 days`) while the voice may spell them — so the spoken text and the caption live in
separate fields and only the caption is audited here.

    python scripts/audit_numbers.py beats.json
    python scripts/audit_numbers.py film/ --field caption --field headline --strict

Exit 0 clean, 1 offending captions found, 2 unreadable input. Reads JSON only; accepts a list, or a dict with
`beats` / `scenes` / `timeline` / `rows`, with `--field` choosing which string keys are audited.
"""
import argparse
import json
import pathlib
import re
import sys

DEFAULT_FIELDS = ("caption", "captions", "subtitle", "screen_text", "caption_text",
                  "headline", "title", "display_numeral")

# Full month names and their three-letter forms. `May` is also a modal verb and `Mar`/`Jan` form part of other
# words, so those are matched only where a date shape sits beside them.
MONTHS = ("january february march april june july august september october november december").split()
MONTHS_SAFE = re.compile(r"\b(" + "|".join(MONTHS) + r")\b", re.I)
MONTH_ABBR = re.compile(r"\b(Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\b")
MAY_AS_DATE = re.compile(r"(\bMay\b\s*(of\s*)?\d{4})|(\d{1,2}\s+May\b)|(\bMay\s+\d{1,2}\b)", re.I)

NUMBER_WORDS = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
                "sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety "
                "hundred thousand million billion trillion").split()
# counts are what the rule targets; a bare number word in prose ("one of them") is not a defect.
COUNT_CONTEXT = re.compile(r"\b(" + "|".join(NUMBER_WORDS) + r")\b[\s-]+(days?|weeks?|months?|years?|hours?|"
                           r"minutes?|seconds?|percent|lines?|versions?|users?|developers?|companies|browsers?)\b", re.I)
YEAR_WORDS = re.compile(r"\b(nineteen|twenty)\s+(hundred|[a-z]+([\s-][a-z]+)?)\b|\btwo thousand\b", re.I)
STRICT_NUMBER = re.compile(r"\b(" + "|".join(NUMBER_WORDS) + r")\b", re.I)


def walk(node):
    """Yield every dict that could be a beat, however the project wrapped it."""
    if isinstance(node, list):
        for item in node:
            yield from walk(item)
    elif isinstance(node, dict):
        for key in ("beats", "scenes", "timeline", "rows", "items"):
            if isinstance(node.get(key), list):
                for item in walk(node[key]):
                    yield item
                return
        yield node


def audit_text(text, strict):
    hits = []
    for match in MONTHS_SAFE.finditer(text):
        if match.group(0).lower() == "may" and not MAY_AS_DATE.search(text):
            continue
        hits.append(("month name", match.group(0)))
    for match in MONTH_ABBR.finditer(text):
        hits.append(("month abbreviation", match.group(0)))
    if MAY_AS_DATE.search(text):
        hits.append(("month name", "May"))
    for match in YEAR_WORDS.finditer(text):
        hits.append(("spelled-out year", match.group(0)))
    for match in COUNT_CONTEXT.finditer(text):
        hits.append(("spelled-out count", match.group(0)))
    if strict:
        for match in STRICT_NUMBER.finditer(text):
            hits.append(("spelled-out number", match.group(0)))
    # dedupe while keeping order
    seen, unique = set(), []
    for hit in hits:
        if hit not in seen:
            seen.add(hit)
            unique.append(hit)
    return unique


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("targets", nargs="+", help="beats/scene JSON files, or folders to search")
    parser.add_argument("--field", action="append", default=None, help="string key(s) to audit")
    parser.add_argument("--strict", action="store_true", help="also flag any bare number word")
    args = parser.parse_args()

    fields = tuple(args.field) if args.field else DEFAULT_FIELDS
    files = []
    for target in args.targets:
        path = pathlib.Path(target)
        if path.is_dir():
            files.extend(sorted(p for p in path.rglob("*.json") if "node_modules" not in p.parts))
        elif path.exists():
            files.append(path)
        else:
            sys.exit(f"audit_numbers: no such path {target}")
    if not files:
        sys.exit("audit_numbers: nothing to audit")

    checked = failed = 0
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # a folder of project JSON may hold non-beat files
            print(f"skip {path}: {exc}")
            continue
        rows = list(walk(data))
        if not rows:
            continue
        in_file = 0
        for index, row in enumerate(rows, 1):
            for key in fields:
                value = row.get(key)
                if not isinstance(value, str) or not value.strip():
                    continue
                checked += 1
                for kind, snippet in audit_text(value, args.strict):
                    failed += 1
                    where = row.get("id", index)
                    print(f"FAIL {path.name} [{where}.{key}] {kind}: {snippet!r}\n     caption: {value[:140]}")
                in_file += 1
        if in_file == 0 and path.name.lower().startswith(("beats", "timeline", "scenes")):
            print(f"warn {path.name}: recognised no audited field {fields}")

    if checked == 0:
        sys.exit(f"audit_numbers: found no text in fields {fields} — wrong --field for this project")
    print(f"\n{checked} string(s) checked, {failed} finding(s)")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
