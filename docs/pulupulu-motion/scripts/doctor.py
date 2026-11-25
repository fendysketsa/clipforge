#!/usr/bin/env python3
"""Read-only preflight. Run this before promising anyone a film.

    python scripts/doctor.py                 # human output
    python scripts/doctor.py --json          # for a script or a CI step
    python scripts/doctor.py --project DIR   # also check that DIR looks like a pulupulu project

Exit 0 = every hard requirement is present. Exit 1 = something a film cannot be made without is missing.
Nothing here writes to disk, starts a server, installs a package or calls the network.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

HARD = ("node", "ffmpeg", "ffprobe")
SOFT = ("pulupulu", "om")


def run(command):
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=24,
                              shell=False).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def version_of(binary):
    for flag in ("--version", "-version", "-v"):
        out = run([binary, flag])
        if out:
            return out.splitlines()[0][:80]
    return "present, version unknown"


def check_binary(name):
    path = shutil.which(name)
    return {"name": name, "ok": bool(path), "path": path or "", "version": version_of(path) if path else ""}


def check_python():
    return {"name": "python", "ok": sys.version_info >= (3, 9),
            "path": sys.executable, "version": sys.version.split()[0]}


def check_deepseek():
    """The narration route needs a key; the film itself does not, so this is a warning, not a failure."""
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if key:
        return {"name": "DEEPSEEK_API_KEY", "ok": True, "path": "environment",
                "version": f"set ({len(key)} chars)"}
    # the key usually lives in the agent's own .env rather than in the shell that runs this check
    for candidate in (os.path.expanduser("~/AppData/Local/hermes/.env"),
                      os.path.expanduser("~/.config/hermes/.env"),
                      os.path.expanduser("~/.hermes/.env")):
        if not os.path.exists(candidate):
            continue
        for line in open(candidate, encoding="utf-8", errors="ignore"):
            if line.strip().startswith("DEEPSEEK_API_KEY=") and line.split("=", 1)[1].strip():
                return {"name": "DEEPSEEK_API_KEY", "ok": True, "path": candidate,
                        "version": "found in .env, not exported — load it before calling the TTS script"}
    return {"name": "DEEPSEEK_API_KEY", "ok": False, "path": "environment", "version":
            "not set — narration via DeepSeek TTS is unavailable, system TTS still works"}


def check_disk():
    probe = os.path.abspath(os.sep)
    try:
        free = shutil.disk_usage(probe).free / (1024 ** 3)
    except OSError:
        return {"name": "disk", "ok": True, "path": probe, "version": "unknown"}
    # a 90 s 1080x1920 film plus its intermediate PNG frames needs a few GB, not a few hundred MB
    return {"name": "disk", "ok": free >= 3, "path": probe, "version": f"{free:.1f} GB free (want >= 3)"}


def check_project(directory):
    """The page contract lives in the project, not in the CLI, so it has to be checked in the project."""
    findings = []
    page = os.path.join(directory, "index.html")
    findings.append({"name": "index.html", "ok": os.path.exists(page), "path": page, "version": ""})
    for vendor in ("gsap.min.js", "om.js"):
        path = os.path.join(directory, "vendor", vendor)
        findings.append({"name": f"vendor/{vendor}", "ok": os.path.exists(path), "path": path, "version": ""})
    if os.path.exists(page):
        html = open(page, encoding="utf-8", errors="ignore").read()
        findings.append({"name": "data-composition-id", "ok": 'data-composition-id="film"' in html,
                         "path": page, "version": '#stage must carry data-composition-id="film"'})
        findings.append({"name": "window.__timelines", "ok": "__timelines" in html, "path": page,
                         "version": "the renderer looks for window.__timelines[<composition id>]"})
    return findings


def check_art_motion():
    """The style-recipe route lives in a pinned bundle, not in the repository. Optional, so never blocking."""
    target = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "scripts", "art-motion", "engine")
    lib = os.path.join(target, "lib")
    if os.path.isdir(lib):
        return {"name": "art-motion engine", "ok": True, "path": target, "version": "installed"}
    return {"name": "art-motion engine", "ok": False, "path": target, "version":
            "not installed — only needed for the style-recipe route: python scripts/install_art_motion.py"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--project", help="a pulupulu project directory to check as well")
    args = parser.parse_args()

    results = [check_python()] + [check_binary(name) for name in HARD] + [check_binary(name) for name in SOFT]
    results.append(check_deepseek())
    results.append(check_disk())
    results.append(check_art_motion())

    hard_names = set(HARD) | {"python"}
    cli_ok = any(item["ok"] for item in results if item["name"] in SOFT)
    if not cli_ok:
        results.append({"name": "cli", "ok": False, "path": "", "version":
                        "neither `pulupulu` nor `om` on PATH — install the CLI once; do not call npx per command"})

    if args.project:
        results.extend(check_project(args.project))

    failed = [item for item in results if not item["ok"]]
    blockers = [item for item in failed if item["name"] in hard_names or item["name"] == "cli"
                or (args.project and item["name"] in
                    ("index.html", "vendor/gsap.min.js", "vendor/om.js", "data-composition-id", "window.__timelines"))]

    if args.json:
        print(json.dumps({"ok": not blockers, "checks": results,
                          "blockers": [b["name"] for b in blockers]}, indent=1))
    else:
        for item in results:
            mark = "ok  " if item["ok"] else "MISS"
            print(f"  [{mark}] {item['name']:<22} {item['version']}")
        print()
        if blockers:
            print("BLOCKED: " + ", ".join(b["name"] for b in blockers))
            for item in blockers:
                if item["version"]:
                    print(f"  {item['name']}: {item['version']}")
        else:
            print("preflight passed — every hard requirement is present")
        warnings = [item for item in failed if item not in blockers]
        for item in warnings:
            print(f"  note: {item['name']} — {item['version']}")
    sys.exit(1 if blockers else 0)


if __name__ == "__main__":
    main()
