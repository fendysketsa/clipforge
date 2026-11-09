"""Exercise export-lock recovery at the Docker CLI boundary, without a daemon."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-backend-image.py"
spec = importlib.util.spec_from_file_location("backend_image_build", SCRIPT)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

LOCK = """ERROR exporting to image
exporting layers 176.4s
failed to solve: mount callback failed on /var/lib/containerd/tmpmounts/containerd-mount558378242:
failed to open writer: ref moby/1/tmbgbpgisze5uton0mrdxagnp locked for 2m56.352757993s (since 2026-11-10 04:55:15 +0700 WIB): unavailable
"""


@pytest.mark.parametrize("output", [
    "failed to solve: process npm ci did not complete successfully: exit code: 1",
    "failed to solve: mount callback failed: no space left on device",
    "permission denied while trying to connect to the Docker API",
    "rpc error: code = Unavailable desc = server disconnected",
    "failed to open writer: ref moby/1/a locked for 2s: unavailable",  # no export evidence
    "exporting layers: permission denied",
])
def test_unrelated_failures_are_not_export_lock_retries(output):
    assert not builder.export_writer_locked(output)


def test_recognizes_the_users_exact_failure():
    assert builder.export_writer_locked(LOCK)


@pytest.fixture
def fake_docker(tmp_path, monkeypatch):
    binaries = tmp_path / "bin"
    binaries.mkdir()
    config = tmp_path / "scenario.json"
    events = tmp_path / "events.jsonl"
    docker = binaries / "docker"
    docker.write_text(f'''#!{sys.executable}
import json, os, pathlib, sys
args = sys.argv[1:]
scenario = json.loads(pathlib.Path(os.environ['BUILD_SCENARIO']).read_text())
events = pathlib.Path(os.environ['BUILD_EVENTS'])
previous = [json.loads(row) for row in events.read_text().splitlines()] if events.exists() else []
with events.open('a') as stream:
    stream.write(json.dumps({{'args': args, 'bake': os.environ.get('COMPOSE_BAKE')}}) + '\\n')
if args == ['compose', 'version']: sys.exit(0)
if args == ['compose', 'build', '--help']:
    print('--builder' if scenario.get('compose_supported', True) else '--no-cache'); sys.exit(0)
if args == ['buildx', 'version']:
    print('buildx v0.30'); sys.exit(scenario.get('plugin_status', 0))
if args == ['info', '--format', '{{{{.ID}}}}']:
    print('test-daemon'); sys.exit(scenario.get('info_status', 0))
if args[:2] == ['buildx', 'inspect']:
    mode = scenario.get('builder', 'absent')
    if mode == 'absent': print('ERROR: no builder "' + args[2] + '" found'); sys.exit(1)
    if mode == 'denied': print('permission denied'); sys.exit(1)
    print('Driver: ' + ('remote' if mode == 'wrong-driver' else 'docker-container')); sys.exit(0)
if args[:2] == ['buildx', 'create']:
    assert '--use' not in args
    assert args[args.index('--driver') + 1] == 'docker-container'
    assert args[args.index('--driver-opt') + 1] == 'default-load=true'
    sys.exit(scenario.get('create_status', 0))
if args[:4] == ['compose', '--env-file', '.env', 'build']:
    attempt = sum(row['args'][:4] == args[:4] for row in previous)
    outcome = scenario['builds'][attempt]
    print(scenario['lock'] if outcome == 'lock' else outcome)
    sys.exit(0 if outcome == 'success' else 17)
sys.exit('Unexpected command: ' + repr(args))
''')
    docker.chmod(0o755)
    monkeypatch.setenv("PATH", str(binaries) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("BUILD_SCENARIO", str(config))
    monkeypatch.setenv("BUILD_EVENTS", str(events))
    # Inherited developer preferences must not affect test assertions.
    monkeypatch.delenv("COMPOSE_BAKE", raising=False)
    monkeypatch.setattr(builder.time, "sleep", lambda _: None)

    def run(builds, **options):
        config.write_text(json.dumps({"builds": builds, "lock": LOCK, **options}))
        status = builder.build_backend(tmp_path)
        report = json.loads((tmp_path / "reports/backend-image-build.json").read_text())
        calls = [json.loads(row) for row in events.read_text().splitlines()]
        return status, report, calls

    return run


@pytest.mark.parametrize("outcomes", [["success"], ["lock", "success"]])
def test_success_and_transient_retry_reuse_the_original_cache(fake_docker, outcomes):
    status, report, calls = fake_docker(outcomes)
    assert status == 0 and report["status"] == "build_succeeded"
    assert len(report["attempts"]) == len(outcomes)
    assert not report["application_runtime_changed"]
    assert not any(row["args"][0] == "buildx" for row in calls)
    for attempt, outcome in zip(report["attempts"], outcomes):
        log = Path(attempt["log"])
        assert log.stat().st_mode & 0o777 == 0o600
        assert ("failed to open writer" in log.read_text()) == (outcome == "lock")


@pytest.mark.parametrize("existing", ["absent", "existing"])
def test_persistent_lock_uses_a_separate_cache_and_loads_the_image(fake_docker, existing):
    status, report, calls = fake_docker(["lock", "lock", "success"], builder=existing)
    assert status == 0
    assert report["recovery_builder"].startswith("clipforge-export-recovery-")
    create = [row for row in calls if row["args"][:2] == ["buildx", "create"]]
    assert len(create) == (1 if existing == "absent" else 0)
    final = calls[-1]
    assert final["bake"] == "false"
    assert final["args"] == ["compose", "--env-file", ".env", "build", "--builder", report["recovery_builder"], "backend"]
    assert [row["mode"] for row in report["attempts"]] == ["compose", "compose", "isolated-builder"]
    assert not report["application_runtime_changed"]


@pytest.mark.parametrize("outcomes", [
    ["npm ci failed"], ["permission denied"], ["no space left on device"],
    ["lock", "npm ci failed"], ["lock", "lock", "lock"],
])
def test_failures_are_bounded_and_never_reported_as_success(fake_docker, outcomes):
    status, report, calls = fake_docker(outcomes)
    assert status == 17 and report["status"] == "failed"
    assert len(report["attempts"]) == len(outcomes)
    assert len([row for row in calls if row["args"][:4] == ["compose", "--env-file", ".env", "build"]]) == len(outcomes)
    assert not report["application_runtime_changed"]


@pytest.mark.parametrize("options", [
    {"builder": "wrong-driver"}, {"builder": "denied"},
    {"create_status": 7}, {"compose_supported": False},
    {"plugin_status": 8}, {"info_status": 9},
])
def test_uncertain_recovery_setup_stops_without_another_build(fake_docker, options):
    status, report, calls = fake_docker(["lock", "lock"], **options)
    assert status != 0 and report["status"] == "failed"
    assert len(report["attempts"]) == 2
    assert not report["application_runtime_changed"]
    assert calls[-1]["args"][:4] != ["compose", "--env-file", ".env", "build"]


def test_build_helper_help_does_not_access_docker():
    result = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)
    assert result.returncode == 0 and "Never prune" in result.stdout
