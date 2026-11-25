#!/usr/bin/env python3
"""Fail the build when text in the wrong language survives into the film.

Copy tables get translated; the *art templates* inside the generator do not.
Every re-language of a film ships at least one leftover headline unless the
rendered HTML is scanned mechanically.

    python lang-audit.py film/index.html --lang en
    python lang-audit.py film/index.html --lang id --json

Exit code 1 = leftovers found. Text inside <style> is ignored. Text inside
<script> IS scanned, but only through its string literals: a runtime label or a
canvas caption lives there and never shows up in the markup, so stripping scripts
wholesale hid exactly the leaks this tool exists to catch. BOTH languages'
stopword lists run: the check is "no tokens from the other language", not
"contains tokens of ours".
"""

import argparse
import json
import re
import sys

STOP = {
    # Indonesian stopwords: this block is the detector's DATA, not prose. It has to stay
    # Indonesian or the tool can no longer find Indonesian leaking into an English film.
    "id": ["situs", "mati", "menit", "jam", "pengguna", "kenapa", "berbunyi", "persiapan",
           "bukan", "mesin", "lapisan", "karena", "dengan", "untuk", "tidak", "sudah",
           "belum", "masih", "harus", "bisa", "kalau", "nggak", "cuma", "lo", "gue",
           "kamu", "kami", "kita", "mereka", "dan", "atau", "yang", "ini", "itu",
           "dari", "ke", "di", "pada", "akan", "adalah", "juga", "hanya", "lebih",
           "paling", "sering", "dilupakan", "penuh", "tidak bisa", "ratus", "kosong"],
    "en": ["the", "and", "your", "you", "with", "that", "this", "from", "for", "are",
           "was", "were", "have", "has", "not", "but", "what", "when", "why", "how",
           "site", "down", "layer", "minutes", "hours", "prepare", "preparation",
           "because", "while", "without", "should", "must", "before", "after"],
}

QUOTES = ('"', "'")


def collect_visible_text(html):
    """Everything a viewer can read: markup stripped, script/style removed."""
    html = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<style\b[^>]*>.*?</style>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    html = re.sub(r"<[^>]+>", " ", html)
    return html


def string_literals(block):
    """Every quoted literal in a script block, read by hand rather than by regex.

    A regex character class that must exclude both the quote and the backslash
    ends in a trailing backslash, and every attempt at it either refused to
    compile or matched across the closing quote and returned fragments such as
    "').textContent = '". A small scanner has neither failure mode.
    """
    out, index, length = [], 0, len(block)
    while index < length:
        quote = block[index]
        if quote not in QUOTES:
            index += 1
            continue
        cursor, buffer = index + 1, []
        while cursor < length and block[cursor] != quote:
            char = block[cursor]
            if char == "\n":
                break
            if char == "\\" and cursor + 1 < length:
                buffer.append(block[cursor + 1])
                cursor += 2
                continue
            buffer.append(char)
            cursor += 1
        value = "".join(buffer)
        if 3 <= len(value) <= 240:
            out.append(value)
        index = cursor + 1
    return out


def collect_script_strings(html):
    """String literals inside <script>: runtime labels, captions, canvas text.

    These never reach the markup, so an audit that strips scripts cannot see
    them. Selectors, keys and URLs are filtered out by shape, not by hope.
    """
    kept = []
    for block in re.findall(r"<script\b[^>]*>(.*?)</script>", html, flags=re.S | re.I):
        for value in string_literals(block):
            if re.fullmatch(r"[\w$.-]*", value):          # identifiers, keys, class names
                continue
            if re.match(r"(https?:|data:|fonts/|assets/|vendor/|[.#][\w-]+$)", value):
                continue
            if not re.search(r"[A-Za-z]{2}", value):
                continue
            kept.append(value)
    # the same string is usually written twice (inline script + timeline data)
    return "\n".join(dict.fromkeys(kept))


def audit(target_path, lang, scripts=True):
    html = open(target_path, encoding="utf-8").read()
    text = collect_visible_text(html)
    script_text = collect_script_strings(html) if scripts else ""
    other = "id" if lang == "en" else "en"
    found = []
    for where, haystack in (("markup", text), ("script", script_text)):
        for word in STOP[other]:
            for matched_object in re.finditer(rf"(?<![\w-]){re.escape(word)}(?![\w-])", haystack, flags=re.I):
                start = max(0, matched_object.start() - 40)
                found.append({"token": matched_object.group(0), "language": other, "where": where,
                              "context": " ".join(haystack[start:matched_object.end() + 40].split())})
    visited_keys, distinct_values = set(), []
    for hit in found:
        lookup_key = (hit["token"].lower(), hit["context"][:40])
        if lookup_key not in visited_keys:
            visited_keys.add(lookup_key)
            distinct_values.append(hit)
    return distinct_values


def run_cli():
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("target", help="index.html (or any generated page)")
    argument_parser.add_argument("--lang", required=True, choices=["en", "id"],
                    help="the language the film is supposed to be in")
    argument_parser.add_argument("--no-scripts", action="store_true",
                    help="skip string literals inside <script> (they are scanned by default)")
    argument_parser.add_argument("--json", action="store_true")
    args = argument_parser.parse_args()

    hits = audit(args.target, args.lang, scripts=not args.no_scripts)
    if args.json:
        print(json.dumps({"target": args.target, "lang": args.lang,
                          "other_language_hits": len(hits), "hits": hits}, ensure_ascii=False, indent=1))
    else:
        if not hits:
            print(f"language ok: no {('id' if args.lang == 'en' else 'en')} tokens in {args.target}")
        else:
            print(f"LANGUAGE LEAK in {args.target}: {len(hits)} hit(s) — film is supposed to be {args.lang}")
            for h in hits[:40]:
                print(f"  [{h['language']}/{h['where']}] {h['token']!r}  … {h['context']} …")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    run_cli()
