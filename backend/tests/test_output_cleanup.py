import importlib.util
import json
import os
import sys
import time
from pathlib import Path


def load_cleanup():
    path = Path(__file__).resolve().parents[2] / "scripts/cleanup-unused-outputs.py"
    spec = importlib.util.spec_from_file_location("cleanup_unused_outputs", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cleanup_removes_only_old_orphans_and_keeps_referenced_assets(monkeypatch, tmp_path):
    cleanup = load_cleanup()
    root, data = tmp_path / "backend/outputs", tmp_path / "backend/data"
    root.mkdir(parents=True)
    data.mkdir(parents=True)
    job, active, orphan, board, spare = (character * 32 for character in "abcde")
    movie = root / job / "clips/final.mp4"
    movie.parent.mkdir(parents=True)
    movie.write_bytes(b"protected-master")
    keyframe = root / "storyboards" / board / "scene_01.png"
    keyframe.parent.mkdir(parents=True)
    keyframe.write_bytes(b"referenced-keyframe")
    for name in (active, orphan, "storyboards/" + spare):
        directory = root / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "temporary.dat").write_bytes(b"unused")
    for path in [root, *root.rglob("*")]:
        os.utime(path, (time.time() - 7200, time.time() - 7200))
    records = [{"id": job, "status": "completed", "request": {"script_text": f"KEYFRAME: storyboards/{board}/scene_01.png"},
                "clips": [{"url": f"/outputs/{job}/clips/final.mp4"}]},
               {"id": active, "status": "running", "clips": []}]
    (data / "jobs.json").write_text(json.dumps(records))
    for platform in ("youtube_uploads", "tiktok_uploads"):
        (data / f"{platform}.json").write_text("[]")
    monkeypatch.setattr(cleanup, "PROJECT", tmp_path)
    monkeypatch.setattr(cleanup, "ROOT", root)
    monkeypatch.setattr(cleanup, "DATA", data)
    monkeypatch.setattr(sys, "argv", ["cleanup", "--apply"])
    cleanup.main()
    assert movie.read_bytes() == b"protected-master"
    assert keyframe.read_bytes() == b"referenced-keyframe"
    assert (root / active).exists()
    assert not (root / orphan).exists()
    assert not (root / "storyboards" / spare).exists()


def test_cleanup_rejects_root_new_directories_and_symlinks(monkeypatch, tmp_path):
    cleanup = load_cleanup()
    root = tmp_path / "outputs"
    root.mkdir()
    monkeypatch.setattr(cleanup, "ROOT", root)
    new = root / ("f" * 32)
    new.mkdir()
    link = root / ("e" * 32)
    link.symlink_to(tmp_path, target_is_directory=True)
    assert not cleanup.candidate(root, 60, set(), set())
    assert not cleanup.candidate(new, 60, set(), set())
    assert not cleanup.candidate(link, 60, set(), set())


def test_startup_orphan_cleanup_preserves_shared_storyboard_library(monkeypatch, tmp_path):
    import api
    image = tmp_path / "storyboards" / ("a" * 32) / "scene_01.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"shared-story-input")
    for path in [tmp_path, *tmp_path.rglob("*")]:
        os.utime(path, (time.time() - 7200, time.time() - 7200))
    monkeypatch.setattr(api, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(api, "jobs", {})
    monkeypatch.setattr(api, "youtube_uploads", {})
    api.cleanup_orphan_output_roots(min_age_seconds=60)
    assert image.read_bytes() == b"shared-story-input"
