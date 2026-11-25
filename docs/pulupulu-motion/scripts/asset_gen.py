#!/usr/bin/env python3
"""Generate and validate a plate or cut-out asset for a film, from a written brief.

A film that needs a better explosion, a truer ship or a missing cut-out must be able to make that asset and
prove it is usable, without a human in the loop. This script is that loop:

    brief (JSON)  ->  image model  ->  validation against the film's own rules  ->  manifest entry

Validation is the part that matters. A generator will happily return a JPEG-looking PNG with no alpha, a
white card behind the subject, or a palette that fights the film. Those are checked here, and a failing asset
is reported as a failure instead of being wired into a timeline where it is impossible to diagnose later.

Usage:
    python asset_gen.py briefs.json            # run every entry
    python asset_gen.py briefs.json --only s6  # one entry
    python asset_gen.py briefs.json --check    # validate existing files, generate nothing

Brief entry:
    {
      "name": "s6_ember_vent",
      "kind": "cutout" | "plate",
      "size": [512, 512],                # required for cutout; ignored for plate
      "min_alpha": 0.35,                 # cutout: fraction of pixels that must be transparent
      "palette": ["#14120f", "#c8452a"],  # every one of these must appear within tolerance
      "prompt": "…the full visual brief for the model…"
    }
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
TOLERANCE = 26  # per-channel distance accepted when checking palette presence


def run_model(prompt, out_path, workdir):
    """One image-generation call. codex takes the prompt on stdin; -i would swallow it."""
    # on Windows the CLI is a .cmd shim: subprocess with shell=False will not find a bare "codex"
    exe = None
    for candidate in ("codex", "codex.cmd", "codex.exe"):
        exe = shutil.which(candidate)
        if exe:
            break
    if not exe:
        return 127, "codex CLI not found on PATH"
    cmd = [exe, "exec", "--skip-git-repo-check", "-m", "gpt-6.2-sol",
           "-c", "model_reasoning_effort=medium", "--add-dir", workdir.replace("\\", "/")]
    # the prompt must end with the flat instruction to save, because the agent has a filesystem
    text = (prompt.strip() + "\n\n"
            "Save the result as exactly this path, overwriting if present:\n"
            f"{out_path}\n"
            "Do not create any other file. Do not describe the image back to me; just generate and save it.\n")
    proc = subprocess.run(cmd, input=text.encode("utf-8"), cwd=workdir,
                          capture_output=True, timeout=900)
    return proc.returncode, proc.stdout.decode("utf-8", "replace") + proc.stderr.decode("utf-8", "replace")


def run_agy(prompt, out_path, workdir, model="gemini-4-neon-medium"):
    """One image-generation call through the agy CLI.

    agy reaches an image model through its built-in `image-generator` subagent, which runs asynchronously and
    answers with a FILE PATH — there is no size/format/seed parameter, so everything has to be in the prompt
    text, including the absolute save path. The model reports success in prose whether or not it wrote the
    file, so the caller still has to check the filesystem and the validation gates.
    """
    exe = None
    for candidate in ("agy", "agy.cmd", "agy.exe"):
        exe = shutil.which(candidate)
        if exe:
            break
    if not exe:
        return 127, "agy CLI not found on PATH"
    text = (prompt.strip() + chr(10) * 2 +
            "Gunakan subagent image-generator milikmu untuk membuat gambar ini, lalu simpan hasilnya "
            "PERSIS di path absolut ini: " + out_path + chr(10) +
            "Jangan membuat file lain, jangan mengubah file lain, dan jangan menjelaskan gambarnya kembali.")
    cmd = [exe, "--print", text, "--model", model, "--add-dir", workdir.replace("\\", "/")]
    proc = subprocess.run(cmd, cwd=workdir, capture_output=True, timeout=1200)
    return proc.returncode, proc.stdout.decode("utf-8", "replace") + proc.stderr.decode("utf-8", "replace")


def hex_to_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def validate(path, entry):
    """Return a list of problems. Empty list means the asset may be used."""
    problems = []
    if not os.path.exists(path):
        return [f"file was not created: {path}"]
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    width, height = img.size

    if entry.get("kind") == "cutout":
        alpha = img.split()[3]
        transparent = sum(1 for v in alpha.getdata() if v < 8) / (width * height)
        if transparent < entry.get("min_alpha", 0.3):
            problems.append(f"only {transparent:.1%} of the pixels are transparent — this is not a cut-out")
        # a card or a frame shows up as fully opaque rows or columns at the edges
        corners = [alpha.getpixel(p) for p in
                   ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1))]
        if all(c > 240 for c in corners):
            problems.append("all four corners are opaque — the generator drew a background card")
        # Size is a hint, aspect is the contract: an image model rarely returns the exact pixel count
        # asked for, but a different ASPECT means it composed a different picture and the art cannot be
        # placed where the shot needs it. A proportional mismatch is resized, never failed.
        want = entry.get("size")
        if want:
            want_aspect = want[0] / want[1]
            got_aspect = width / height
            if abs(got_aspect - want_aspect) / want_aspect > 0.18:
                problems.append(f"aspect {got_aspect:.2f} is far from the requested {want_aspect:.2f} "
                                f"({width}x{height} vs {want[0]}x{want[1]}) — the model composed a different picture")
            elif (width, height) != tuple(want):
                print(f"   note sized {width}x{height}, will be resized to fit {want[0]}x{want[1]}")

    for colour in entry.get("palette", []):
        target = hex_to_rgb(colour)
        pixels = img.convert("RGB").getdata()
        step = max(1, len(pixels) // 40000)
        found = False
        for index, pixel in enumerate(pixels):
            if index % step:
                continue
            if all(abs(pixel[i] - target[i]) <= TOLERANCE for i in range(3)):
                found = True
                break
        if not found:
            problems.append(f"palette colour {colour} is missing from the image")
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("brief")
    parser.add_argument("--only", help="run one entry by name")
    parser.add_argument("--check", action="store_true", help="validate existing files only")
    parser.add_argument("--outdir", default=os.getcwd())
    parser.add_argument("--provider", choices=("codex", "agy"), default="codex",
                        help="which CLI reaches an image model; agy uses its image-generator subagent")
    parser.add_argument("--model", default="gemini-4-neon-medium",
                        help="agy model id, ignored for codex")
    args = parser.parse_args()

    entries = json.load(open(args.brief, encoding="utf-8"))
    if isinstance(entries, dict):
        entries = entries["assets"]

    failures = 0
    for entry in entries:
        if args.only and entry["name"] != args.only:
            continue
        path = os.path.join(args.outdir, entry["name"] + ".png")
        print(f"== {entry['name']} ({entry.get('kind', 'cutout')})")
        if not args.check:
            if args.provider == "agy":
                code, log = run_agy(entry["prompt"], path, args.outdir, args.model)
            else:
                code, log = run_model(entry["prompt"], path, args.outdir)
            if code != 0:
                print(f"   model exited {code}")
                print("   " + "\n   ".join(log.strip().splitlines()[-6:]))
        problems = validate(path, entry)
        if problems:
            failures += 1
            for problem in problems:
                print(f"   FAIL {problem}")
        else:
            size = Image.open(path).size
            print(f"   ok  {path}  {size[0]}x{size[1]}")

    print(f"\n{failures} asset(s) failed validation")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
