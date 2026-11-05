"""Deployment must wait for real work and fail closed on uncertain state."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("deployment_idle_guard", ROOT / "scripts/wait-for-backend-idle.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


@pytest.fixture
def snapshots():
    return {endpoint: [] for endpoint in guard.ENDPOINTS}


def orphan(**overrides):
    return {
        "id": "old-run", "status": "running", "trigger": "schedule",
        "progress_stage": "social_upload",
        "updated_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "processed": [{"job_id": "missing-job"}], **overrides,
    }


@pytest.mark.parametrize("endpoint", guard.ENDPOINTS[:-1])
@pytest.mark.parametrize("status", ["queued", "running"])
def test_actual_work_blocks_activation_with_identifying_details(snapshots, endpoint, status):
    snapshots[endpoint] = [{"id": "active-job", "status": status, "progress_stage": "source"}]
    blockers, stalled = guard.classify_work(snapshots, True, datetime.now(timezone.utc))
    assert len(blockers) == 1
    assert "active-job" in blockers[0] and "stage=source" in blockers[0]
    assert not stalled


def test_orphan_recovery_requires_explicit_flag(snapshots):
    snapshots["automation/viral-cc"] = [orphan()]
    now = datetime.now(timezone.utc)
    assert guard.classify_work(snapshots, False, now)[0]
    assert guard.classify_work(snapshots, True, now) == ([], ["old-run"])


@pytest.mark.parametrize("changes", [
    {"trigger": "manual"}, {"progress_stage": "clip_source"},
    {"progress_stage": "waiting_upload"}, {"progress_stage": "daily_upload_limit"},
    {"updated_at": datetime.now(timezone.utc).isoformat()},
    {"updated_at": "invalid"}, {"updated_at": None},
    {"updated_at": "2020-01-01T00:00:00"}, {"processed": []},
])
def test_uncertain_or_real_campaigns_are_never_recovered(snapshots, changes):
    snapshots["automation/viral-cc"] = [orphan(**changes)]
    blockers, stalled = guard.classify_work(snapshots, True, datetime.now(timezone.utc))
    assert blockers and not stalled


@pytest.mark.parametrize("key", ["job_id", "long_job_id"])
def test_existing_child_even_if_terminal_protects_campaign(snapshots, key):
    snapshots["automation/viral-cc"] = [orphan(processed=[{key: "existing-job"}])]
    snapshots["jobs"] = [{"id": "existing-job", "status": "completed"}]
    assert guard.classify_work(snapshots, True, datetime.now(timezone.utc))[0]


@pytest.mark.parametrize("command", [
    "ffmpeg -i source.mp4", "/usr/bin/ffprobe source.mp4",
    "python /app/clipper.py --job abc", "python youtube_uploader.py",
    "python /app/tiktok_uploader.py", "python long_animate.py",
    "/usr/local/bin/yt-dlp source", "python -m yt_dlp source",
])
def test_subprocess_safety_covers_media_and_download_workers(command):
    assert guard.MEDIA_PROCESS.search(command)


def test_docker_top_retains_pid_column_and_detects_workers(tmp_path, monkeypatch):
    # Reproduce Docker's PID requirement at the executable boundary. Earlier
    # tests mocked active_subprocesses itself and missed this daemon contract.
    docker = tmp_path / "docker"
    docker.write_text(f'''#!{sys.executable}
import sys
if sys.argv[1:4] != ['top', 'test-backend', '-eo']:
    sys.exit('Unexpected docker command')
if sys.argv[4:] != ['pid,args']:
    sys.exit("Error response from daemon: Couldn't find PID field in ps output")
print('PID COMMAND')
print('100 python -m uvicorn api:app')
print('101 /usr/bin/ffmpeg -i input.mp4')
print('102 python /app/youtube_uploader.py --job abc')
print('103 python -m yt_dlp https://example.test/source')
''')
    docker.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    assert guard.active_subprocesses("test-backend") == [
        "101 /usr/bin/ffmpeg -i input.mp4",
        "102 python /app/youtube_uploader.py --job abc",
        "103 python -m yt_dlp https://example.test/source",
    ]


def test_wait_drains_queue_instead_of_exiting(snapshots, monkeypatch, capsys):
    busy = deepcopy(snapshots)
    busy["jobs"] = [{"id": "render", "status": "running"}]
    states = iter([busy, snapshots])
    monkeypatch.setattr(guard, "read_snapshots", lambda _: next(states))
    monkeypatch.setattr(guard, "active_subprocesses", lambda _: [])
    sleeps = []
    monkeypatch.setattr(guard.time, "sleep", sleeps.append)
    assert guard.wait_until_idle(base_url="unused", container="unused", recover_stalled_cron=True, wait_seconds=60) == []
    assert sleeps == [15]
    assert "Waiting for active work" in capsys.readouterr().out


def test_empty_queues_do_not_override_live_subprocess(snapshots, monkeypatch):
    monkeypatch.setattr(guard, "read_snapshots", lambda _: snapshots)
    monkeypatch.setattr(guard, "active_subprocesses", lambda _: ["ffmpeg -i input.mp4"])
    with pytest.raises(SystemExit, match="subprocess.*still active"):
        guard.wait_until_idle(base_url="unused", container="unused", recover_stalled_cron=True, wait_seconds=0)


@pytest.mark.parametrize("failure", [OSError("API unavailable"), ValueError("invalid JSON")])
def test_api_failure_never_means_idle(monkeypatch, failure):
    def fail(_):
        raise failure
    monkeypatch.setattr(guard, "read_snapshots", fail)
    with pytest.raises(type(failure)):
        guard.wait_until_idle(base_url="unused", container="unused", recover_stalled_cron=True, wait_seconds=0)


def test_docker_inspection_failure_never_means_idle(snapshots, monkeypatch):
    monkeypatch.setattr(guard, "read_snapshots", lambda _: snapshots)
    def fail(_):
        raise subprocess.CalledProcessError(1, "docker top")
    monkeypatch.setattr(guard, "active_subprocesses", fail)
    with pytest.raises(subprocess.CalledProcessError):
        guard.wait_until_idle(base_url="unused", container="unused", recover_stalled_cron=True, wait_seconds=0)


def test_state_preserves_orphans_from_first_check(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"stalled_run_ids": ["first"]}))
    monkeypatch.setattr(sys, "argv", ["guard", "--state-file", str(state)])
    monkeypatch.setattr(guard, "wait_until_idle", lambda **_: ["second"])
    guard.main()
    assert json.loads(state.read_text()) == {"stalled_run_ids": ["first", "second"]}


def test_recovery_wrapper_forwards_help_without_docker_or_root():
    result = subprocess.run(["bash", str(ROOT / "scripts/activate-cron-upload-recovery.sh"), "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "--skip-build" in result.stdout and "--wait-seconds" in result.stdout


@pytest.mark.parametrize("args", [["--wait-seconds", "oops"], ["--wait-seconds"], ["--unknown"]])
def test_invalid_options_fail_before_any_side_effects(args):
    result = subprocess.run(["bash", str(ROOT / "scripts/activate-cron-upload-recovery.sh"), *args], capture_output=True, text=True)
    assert result.returncode == 2


@pytest.mark.parametrize("enabled", ["true", "false"])
def test_failed_drain_restores_original_cron_without_touching_runtime(tmp_path, enabled):
    # Exercise the real shell trap/order, replacing only host/root dependencies.
    # The copy stays outside the repository and uses a private deployment lock.
    root = tmp_path / "repo"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    private_lock = tmp_path / "deployment.lock"
    source = (ROOT / "scripts/activate-youtube-quiet-check.sh").read_text()
    source = source.replace('if (( EUID != 0 )); then', 'if false; then')
    source = source.replace('lock=/tmp/clipforge-recreate-compose-up.lock', f'lock={private_lock}')
    script = scripts / "activate.sh"
    script.write_text(source)
    binaries = tmp_path / "bin"
    binaries.mkdir()
    events = tmp_path / "events"
    python = binaries / "python"
    python.write_text(f'''#!{sys.executable}
import os, pathlib, sys
def event(value):
    with open(os.environ['EVENT_LOG'], 'a') as stream: stream.write(value + '\\n')
if sys.argv[1:3] == ['-m', 'py_compile']: sys.exit(0)
if sys.argv[1] == 'scripts/wait-for-backend-idle.py':
    event('drain'); sys.exit(4)
body = sys.stdin.read()
if "print('true'" in body: print(os.environ['ORIGINAL_CRON'])
elif 'sha256sum' in body: event('verify-image')
elif 'for attempt in range(30)' in body: event('restore:' + sys.argv[2])
elif 'data=b' in body: event('pause')
else: raise SystemExit('Unexpected Python invocation')
''')
    docker = binaries / "docker"
    docker.write_text(f'''#!{sys.executable}
import os, sys
with open(os.environ['EVENT_LOG'], 'a') as stream: stream.write('docker:' + ' '.join(sys.argv[1:]) + '\\n')
if sys.argv[1:3] == ['image', 'inspect']: print('sha256:test-image')
else: sys.exit('Runtime must not be changed before drain completes')
''')
    python.chmod(0o755)
    docker.chmod(0o755)
    env = {**os.environ, "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
           "EVENT_LOG": str(events), "ORIGINAL_CRON": enabled}
    result = subprocess.run(["bash", str(script), "--skip-build", "--no-wait"], env=env, capture_output=True, text=True)
    assert result.returncode == 4, result.stderr
    assert events.read_text().splitlines() == [
        "docker:image inspect clipforge-backend:latest --format {{.Id}}",
        "verify-image", "pause", "drain", "restore:" + enabled,
    ]
