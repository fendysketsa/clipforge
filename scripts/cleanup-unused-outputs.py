#!/usr/bin/env python3
"""Audit/prune orphan ClipForge outputs without touching retained jobs or assets."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT / "backend" / "outputs"
DATA = PROJECT / "backend" / "data"
IDENTIFIER = re.compile(r"[a-f0-9]{32}\Z")


def read_records(path: Path) -> list[dict]:
    if not path.exists():
        raise RuntimeError(f"Required runtime state is missing: {path}")
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise RuntimeError(f"Invalid runtime state: {path}")
    return records


def references() -> tuple[set[str], set[str], set[Path]]:
    jobs = read_records(DATA / "jobs.json")
    uploads = read_records(DATA / "youtube_uploads.json") + read_records(DATA / "tiktok_uploads.json")
    job_ids = {str(job["id"]) for job in jobs}
    boards: set[str] = set()
    protected: set[Path] = set()
    for job in jobs:
        text = json.dumps(job, ensure_ascii=False)
        boards.update(re.findall(r"storyboards/([a-f0-9]{32})/", text))
        for clip in job.get("clips", []):
            for value in [clip.get("url"), clip.get("thumbnail_url"), *clip.get("thumbnail_variants", [])]:
                if isinstance(value, str) and value.startswith("/outputs/"):
                    path = ROOT / unquote(urlparse(value).path.removeprefix("/outputs/"))
                    if ROOT.resolve() in path.resolve().parents and path.is_file():
                        protected.add(path)
    for upload in uploads:
        if upload.get("clip_deleted_at"):
            continue
        path = str(upload.get("clip_url") or "")
        match = re.match(r"/outputs/([a-f0-9]{32})/", path)
        if match:
            job_ids.add(match.group(1))
            file = ROOT / unquote(urlparse(path).path.removeprefix("/outputs/"))
            if ROOT.resolve() in file.resolve().parents and file.is_file():
                protected.add(file)
    for board in boards:
        protected.update(path for path in (ROOT / "storyboards" / board).glob("*.png") if path.is_file())
    return job_ids, boards, protected


def allocated(path: Path) -> int:
    seen = set()
    total = 0
    for item in [path, *path.rglob("*")]:
        stat = item.lstat()
        key = (stat.st_dev, stat.st_ino)
        if key not in seen:
            total += stat.st_blocks * 512
            seen.add(key)
    return total


def candidate(path: Path, min_age: float, job_ids: set[str], boards: set[str]) -> bool:
    root = ROOT.resolve()
    if path.is_symlink() or not path.is_dir() or root not in path.resolve().parents:
        return False
    relative = path.relative_to(ROOT).parts
    orphan_job = len(relative) == 1 and bool(IDENTIFIER.fullmatch(relative[0])) and relative[0] not in job_ids
    orphan_board = len(relative) == 2 and relative[0] == "storyboards" and bool(IDENTIFIER.fullmatch(relative[1])) and relative[1] not in boards
    if not (orphan_job or orphan_board):
        return False
    items = [path, *path.rglob("*")]
    if any(item.is_symlink() for item in items):
        return False
    return time.time() - max(item.stat().st_mtime for item in items) >= min_age


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--min-age-seconds", type=int, default=3600)
    args = parser.parse_args()
    if ROOT.is_symlink() or not ROOT.is_dir():
        raise RuntimeError("Outputs root must be an existing real directory")
    job_ids, boards, protected = references()
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in protected}
    paths = list(ROOT.iterdir()) + list((ROOT / "storyboards").glob("*"))
    targets = [path for path in paths if candidate(path, max(60, args.min_age_seconds), job_ids, boards)]
    report = {"apply": args.apply, "allocated_before": allocated(ROOT), "protected_sha256": hashes,
              "targets": [{"path": str(path.relative_to(ROOT)), "allocated_bytes": allocated(path)} for path in targets],
              "removed": [], "errors": []}
    if args.apply:
        for path in targets:
            # Re-read persisted state immediately before every destructive action.
            current_jobs, current_boards, _ = references()
            if not candidate(path, max(60, args.min_age_seconds), current_jobs, current_boards):
                continue
            try:
                shutil.rmtree(path)
                report["removed"].append(str(path.relative_to(ROOT)))
            except OSError as exc:
                report["errors"].append({"path": str(path.relative_to(ROOT)), "error": str(exc)})
        for relative, before in hashes.items():
            if digest(ROOT / relative) != before:
                raise RuntimeError(f"Protected output changed: {relative}")
    report["allocated_after"] = allocated(ROOT)
    report_path = PROJECT / "reports" / ("output-cleanup-20261103-applied.json" if args.apply else "output-cleanup-20261103-plan.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "protected_sha256"}, indent=2))
    print(f"Protected hashes verified: {len(hashes)}; report: {report_path}")
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
