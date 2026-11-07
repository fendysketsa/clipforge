import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
import signal
import sys

import pytest


@pytest.fixture
def recovery():
    path = Path(__file__).resolve().parents[2] / "scripts/recover-youtube-unknown-checks.py"
    spec = importlib.util.spec_from_file_location("checks_recovery_script", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def stuck():
    return dict(id="target", status="running", video_url="https://www.youtube.com/watch?v=abcDEF12345",
                title="Draft title", clip_name="clip.mp4", publish_at="2026-11-08T13:30:00+00:00",
                source_job_id="job", clip_url="/outputs/job/clip.mp4", visibility="public",
                logs=["Checks belum menampilkan hasil final; uploader tetap memantau"] * 3)


@pytest.mark.parametrize("line", ["UPLOAD_CONFIRMED: ready", "Tombol final diklik dan diterima",
                                "CLAIMED_UPLOAD_ABORTED: claim", "CHECKS_DRAFT_RECOVERY_ONCE: attempted"])
def test_legacy_recovery_rejects_finalized_claimed_or_already_recovered(recovery, stuck, line):
    stuck["logs"].insert(0, line)
    assert not recovery.eligible(stuck)


def test_legacy_recovery_rejects_actual_pending_checks(recovery, stuck):
    stuck["logs"] = ["Checks masih berjalan; menunggu sampai semua centang aman"] * 3
    assert not recovery.eligible(stuck)


def test_legacy_recovery_can_resume_recent_timeout_but_not_historical_failures(recovery, stuck):
    stuck.update(status="failed", updated_at=datetime.now(timezone.utc).isoformat(),
                 error="Draft sudah memiliki video-id. Step 3 Checks belum selesai")
    stuck["logs"].append("REMOTE_UPLOAD_CHECKPOINT_LOCKED: preserved")
    assert recovery.eligible(stuck)
    stuck["updated_at"] = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    assert not recovery.eligible(stuck)


def test_legacy_recovery_matches_exact_worker_arguments(recovery, stuck):
    args = ["python", "youtube_uploader.py", "upload", "/app/data/clip-abcdef.mp4",
            "--title", "Draft title", "--publish-at", stuck["publish_at"]]
    assert recovery.matching_worker(args, stuck)
    for index in (3, 5, 7):
        changed = list(args)
        changed[index] = "unrelated"
        assert not recovery.matching_worker(changed, stuck)


@pytest.mark.parametrize("changed_checkpoint", [False, True])
def test_legacy_recovery_stops_only_matching_worker_then_requeues_same_id(monkeypatch, tmp_path, recovery, stuck, changed_checkpoint):
    proc = tmp_path / "proc" / "123"
    proc.mkdir(parents=True)
    args = ["python", "youtube_uploader.py", "upload", "/app/data/clip-abcdef.mp4",
            "--title", stuck["title"], "--publish-at", stuck["publish_at"]]
    (proc / "cmdline").write_bytes("\0".join(args).encode())
    monkeypatch.setattr(recovery, "Path", lambda p: tmp_path / str(p).lstrip("/") if str(p).startswith("/proc") else Path(p))
    calls = []
    killed = []
    counter = 0
    def request(path, payload=None):
        nonlocal counter
        calls.append((path, payload))
        if path == "youtube/uploads":
            return [stuck]
        if path == "youtube/uploads/target":
            counter += 1
            if counter == 1:
                return {**stuck, "video_url": "https://www.youtube.com/watch?v=different01"} if changed_checkpoint else stuck
            return {**stuck, "status": "failed"}
        assert path == "jobs/job/youtube-uploads"
        assert payload["clip_url"] == stuck["clip_url"]
        assert payload["publish_at"] == stuck["publish_at"]
        return {**stuck, "status": "queued"}
    monkeypatch.setattr(recovery, "request", request)
    monkeypatch.setattr(recovery.os, "kill", lambda pid, sig: killed.append((pid, sig)))
    monkeypatch.setattr(sys, "argv", ["recover", "--apply"])
    if changed_checkpoint:
        with pytest.raises(RuntimeError, match="Checkpoint changed"):
            recovery.main()
        assert killed == []
        assert not any(payload for _, payload in calls)
    else:
        recovery.main()
        assert killed == [(123, signal.SIGTERM)]
        assert calls[-1][0] == "jobs/job/youtube-uploads"
