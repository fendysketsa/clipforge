#!/usr/bin/env python3
"""Install the art-motion engine — only if you take that route.

The style-recipe renderer (Playwright + fonts + demo scenes) is 37 MB of vendored material. It is not in
this repository, because a skill should not make every agent download an engine it may never use and
because a 37 MB tree is not reviewable. The Python tools, the clip specs and all the documentation ARE in
the repository; only the heavy runtime is fetched, pinned by release tag and verified by sha256.

    python scripts/install_art_motion.py --check                  # is it installed, and is it the pinned copy?
    python scripts/install_art_motion.py                          # fetch core (lib + demos + scenes, 20 MB)
    python scripts/install_art_motion.py --with-reference-films   # + study material (14 MB)
    python scripts/install_art_motion.py --force                  # re-fetch over a modified tree
    python scripts/install_art_motion.py --from-dir DIR           # offline: unpack from a local folder

Paths after install are identical to the ones every reference page cites, so no document changes.
Exit 0 = installed and verified. Exit 1 = not installed (or wrong bytes).
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(SKILL_ROOT, "scripts", "art-motion")
REPO = "Alucard0x1/pulupulu-motion"
TAG = "v1.0"

BUNDLES = {
    "core": {
        "asset": "art-motion-core-v1.0.tar.gz",
        "sha256": "d06fd1e0ca4cde653f59c6fb0b8495175845eb327cdc7f61b6127574ae992f56",
        "bytes": 20_300_000,
        "provides": ["engine/lib", "engine/demos", "engine/scenes"],
        "required": True,
    },
    "reference-films": {
        "asset": "art-motion-reference-films-v1.0.tar.gz",
        "sha256": "c862cc9dd154f326ae3551ab07d48fc57aa42572fde003ca694008b36e61b2ce",
        "bytes": 14_200_000,
        "provides": ["engine/reference_films"],
        "required": False,
    },
}


def marker_for(bundle):
    return os.path.join(TARGET, f".installed-{bundle}-{TAG}")


def installed(bundle):
    """Installed means: the marker exists AND every path the bundle provides is present."""
    if not os.path.exists(marker_for(bundle)):
        return False
    return all(os.path.exists(os.path.join(TARGET, path)) for path in BUNDLES[bundle]["provides"])


def url_for(bundle):
    return f"https://github.com/{REPO}/releases/download/{TAG}/{BUNDLES[bundle]['asset']}"


def digest(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(block)
    return hasher.hexdigest()


def fetch(bundle, source_dir=None, quiet=False):
    spec = BUNDLES[bundle]
    if source_dir:
        archive = os.path.join(source_dir, spec["asset"])
        if not os.path.exists(archive):
            raise SystemExit(f"missing local bundle: {archive}")
    else:
        handle, archive = tempfile.mkstemp(suffix=".tar.gz")
        os.close(handle)
        if not quiet:
            print(f"  downloading {spec['asset']} "
                  f"({spec['bytes'] / 1e6:.0f} MB) from {TAG} …")
        try:
            with urllib.request.urlopen(url_for(bundle), timeout=180) as response, open(archive, "wb") as out:
                shutil.copyfileobj(response, out)
        except Exception as error:  # network, 404, proxy: all the same instruction to the agent
            raise SystemExit(
                f"download failed: {error}\n"
                f"  fetch it by hand:  gh release download {TAG} --repo {REPO} -p {spec['asset']}\n"
                f"  then:              python scripts/install_art_motion.py --from-dir <folder>")

    actual = digest(archive)
    if actual != spec["sha256"]:
        raise SystemExit(f"checksum mismatch for {spec['asset']}\n  expected {spec['sha256']}\n  got      {actual}")

    if not quiet:
        print(f"  sha256 ok, unpacking into scripts/art-motion/ …")
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            name = member.name.lstrip("./")
            # the archive only ever carries these three (or one) top-level trees
            if not any(name == path or name.startswith(path + "/") for path in spec["provides"]):
                continue
            tar.extract(member, TARGET)
    with open(marker_for(bundle), "w", encoding="utf-8") as marker:
        marker.write(f"{spec['asset']}\nsha256 {spec['sha256']}\nfrom {REPO}@{TAG}\nby Alucard0x1\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="report state, download nothing")
    parser.add_argument("--with-reference-films", action="store_true", help="also fetch the study material")
    parser.add_argument("--force", action="store_true", help="re-fetch even if already installed")
    parser.add_argument("--from-dir", help="offline install from a folder holding the release assets")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    wanted = ["core"] + (["reference-films"] if args.with_reference_films else [])
    state = {bundle: installed(bundle) for bundle in BUNDLES}

    if args.check:
        if args.json:
            print({"target": TARGET, "tag": TAG, "installed": state})
        else:
            for bundle, ok in state.items():
                mark = "ok  " if ok else "MISS"
                need = "required" if BUNDLES[bundle]["required"] else "optional"
                print(f"  [{mark}] {bundle:<16} {need:<9} {url_for(bundle)}")
            missing = [b for b in wanted if not state[b]]
            print()
            print("art-motion engine ready" if not missing else
                  "install with: python scripts/install_art_motion.py" +
                  (" --with-reference-films" if "reference-films" in missing else ""))
        sys.exit(0 if all(state[b] for b in wanted) else 1)

    for bundle in wanted:
        if state[bundle] and not args.force:
            print(f"  {bundle}: already installed")
            continue
        fetch(bundle, args.from_dir)
        print(f"  {bundle}: installed and verified")

    missing = [bundle for bundle in wanted if not installed(bundle)]
    if missing:
        raise SystemExit(f"still missing after install: {missing}")
    print(f"\nart-motion engine ready at {TARGET}")
    print("  render a style-recipe film:  python scripts/art-motion/engine/render.py --help")


if __name__ == "__main__":
    main()
