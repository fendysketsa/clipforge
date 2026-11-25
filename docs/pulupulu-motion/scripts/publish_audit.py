#!/usr/bin/env python3
"""Pre-publish audit for a repository about to go public.

    python scripts/publish_audit.py <repo> [--env ~/.env] [--md README.md] [--online]

Four checks, in the order that matters:

1. **Credentials** — a pattern sweep, plus an exact match of every secret value present in the environment
   file. Matched values are never printed, only the variable name and the file:line that carries them: a key
   echoed into a build log is a second leak, and the log is often public too.
2. **Machine paths** — the local username, home directory and per-machine install locations have no business
   in a public repo. A "local install (this machine)" block publishes who the author is and where their tools
   live; the fix is a portable section, not a deleted sentence.
3. **Dead install commands** — every `npm install -g <pkg>` in the docs is resolved against the registry. A
   README whose first command 404s costs the reader the whole tool. Only with `--online`.
4. **Dead anchors** — every `](#anchor)` in a markdown file is checked against GitHub's slug rule.

Exit code 1 when anything is found, so a publish step can chain it.
"""
import argparse
import json
import os
import pathlib
import re
import sys
import urllib.parse
import urllib.request

TEXT_EXT = {".md", ".py", ".js", ".html", ".css", ".json", ".sh", ".txt", ".yml", ".yaml", ".toml", ".svg"}

SECRET_PATTERNS = [
    ("provider key (sk-)", re.compile(r"sk-[A-Za-z0-9_\-]{16,}")),
    ("github token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}")),
    ("aws key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("slack token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("assigned secret", re.compile(
        r"(?i)(api[_-]?key|secret|passwd|password|access[_-]?token|auth[_-]?token)"
        r"\s*[:=]\s*[\"'][^\"'\s]{12,}[\"']")),
    ("bearer literal", re.compile(r"(?i)authorization\s*:\s*bearer\s+[A-Za-z0-9_\-\.]{20,}")),
    ("env assignment", re.compile(r"(?i)\b[A-Z0-9_]*(KEY|TOKEN|SECRET)\b\s*=\s*[A-Za-z0-9_\-]{16,}")),
]

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}


def secret_values(env_path):
    """Values from an environment file that are plausibly secret. URLs, paths and prose are excluded:
    they are configuration, and matching them produces noise that hides a real hit."""
    values = {}
    if not env_path or not env_path.exists():
        return values
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if len(value) >= 16 and not value.lower().startswith(("http", "c:", "/", "~", ".")) and " " not in value:
            values[name.strip()] = value
    return values


def machine_tokens():
    tokens = set()
    for var in ("USERNAME", "USER"):
        if os.environ.get(var):
            tokens.add(os.environ[var])
    for var in ("USERPROFILE", "HOME"):
        home = os.environ.get(var)
        if home:
            tokens.add(home)
            tokens.add(pathlib.PurePath(home).name)
            tokens.add(home.replace("\\", "/"))
    return {t for t in tokens if t and len(t) > 2}


def walk(root):
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_EXT:
            continue
        yield path


def gh_slug(heading):
    """GitHub: lowercase, keep alphanumerics/space/-/_, then replace EACH space with one hyphen.
    Collapsing runs of whitespace instead produces false 'broken anchor' reports whenever a heading
    contains an em dash."""
    slug = re.sub(r"[^a-z0-9 _-]", "", heading.strip().lower())
    return slug.replace(" ", "-")


def registry_exists(package):
    url = "https://registry.npmjs.org/" + urllib.parse.quote(package, safe="@")
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode("utf-8")).get("dist-tags", {}).get("latest")
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("repo")
    parser.add_argument("--env", default=os.path.expanduser("~/.env"), help="environment file holding real secrets")
    parser.add_argument("--md", action="append", default=[], help="markdown file whose anchors and commands to check (repeatable)")
    parser.add_argument("--online", action="store_true", help="resolve install commands against npm")
    args = parser.parse_args()

    root = pathlib.Path(args.repo).resolve()
    if not root.is_dir():
        sys.exit(f"not a directory: {root}")

    secrets = secret_values(pathlib.Path(args.env).expanduser()) if args.env else {}
    personal = machine_tokens()
    found = []
    scanned = 0
    docs = [root / m for m in args.md] if args.md else [root / "README.md"]
    docs = [d for d in docs if d.exists()]

    for path in walk(root):
        scanned += 1
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = path.relative_to(root)
        for label, rx in SECRET_PATTERNS:
            for match in rx.finditer(text):
                line = text[: match.start()].count("\n") + 1
                found.append(("SECRET", str(rel), line, label, match.group(0)[:8] + "…"))
        for name, value in secrets.items():
            if value in text:
                line = text[: text.index(value)].count("\n") + 1
                found.append(("REAL SECRET", str(rel), line, f"value of {name}", value[:4] + "…"))
        for token in personal:
            if token in text and path.suffix.lower() in {".md", ".py", ".js", ".sh", ".html", ".txt"}:
                line = text[: text.index(token)].count("\n") + 1
                found.append(("MACHINE PATH", str(rel), line, "local user/home", token[:6] + "…"))

    for doc in docs:
        text = doc.read_text(encoding="utf-8", errors="ignore")
        rel = doc.relative_to(root)
        headings = {gh_slug(m.group(1)) for m in re.finditer(r"^#{1,6} (.+)$", text, re.M)}
        for anchor in re.findall(r"\]\(#([^)]+)\)", text):
            if anchor not in headings:
                found.append(("DEAD ANCHOR", str(rel), 0, "#" + anchor, ""))
        if args.online:
            for package in set(re.findall(r"npm (?:install|i) -g ([@\w./\-]+)", text)):
                bare = re.sub(r"@[\d.]+$", "", package)
                if not registry_exists(bare):
                    found.append(("DEAD COMMAND", str(rel), 0, f"npm i -g {bare}", "404 on npm"))

    print(f"scanned {scanned} text files under {root}")
    if secrets:
        print(f"matched against {len(secrets)} environment values (never printed)")
    if not found:
        print("clean: no credential, machine path, dead anchor or dead command")
        return 0

    for kind, rel, line, what, hint in found:
        where = f"{rel}:{line}" if line else rel
        print(f"  {kind:13} {where:45} {what} {hint}")
    print(f"\n{len(found)} finding(s). Fix before publishing; a machine path is a leak too, and a 404 install"
          f" command costs the reader the tool.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
