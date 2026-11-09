#!/usr/bin/env python3
"""Build the backend, recovering only a recognized containerd export lock.

The caller holds the deployment lock. Never prune storage, restart Docker, or
touch application containers here. Image/source verification stays in the
activation script, before cron is paused.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]


def export_writer_locked(output):
    # Do not retry compiler errors, ENOSPC, permissions, or generic RPC failures.
    return bool(re.search(
        r"failed to open writer:\s*ref\s+\S+\s+locked for\b[^\n]*:\s*unavailable\b",
        output, re.IGNORECASE,
    )) and bool(re.search(r"exporting (?:to image|layers)|mount callback failed", output, re.IGNORECASE))


class BuildFailure(Exception):
    def __init__(self, message, status=1):
        super().__init__(message)
        self.status = status if 0 < status < 126 else 1


def capture(command, root):
    result = subprocess.run(command, cwd=root, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, errors="replace")
    return result.returncode, result.stdout


def run_build(command, root, log_path, env):
    tail = ""
    # Logs can include private registry URLs; do not make them world-readable.
    with log_path.open("x", encoding="utf-8") as log:
        log_path.chmod(0o600)
        process = subprocess.Popen(command, cwd=root, env=env, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   errors="replace", bufsize=1)
        try:
            for line in process.stdout:
                print(line, end="", flush=True)
                log.write(line)
                tail = (tail + line)[-262144:]
            return process.wait(), tail
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise
        finally:
            process.stdout.close()


def recovery_builder(root, compose):
    status, help_text = capture([*compose, "build", "--help"], root)
    if status or "--builder" not in help_text:
        raise BuildFailure("Export recovery requires Docker Compose with --builder support.")
    status, output = capture(["docker", "buildx", "version"], root)
    if status:
        raise BuildFailure("Export recovery requires the Docker Buildx plugin: " + output.strip(), status)
    # Scope the persistent recovery cache to this daemon, without selecting a
    # new global builder or borrowing another project's BuildKit state.
    status, daemon_id = capture(["docker", "info", "--format", "{{.ID}}"], root)
    if status or not daemon_id.strip():
        raise BuildFailure("Cannot identify the Docker daemon for export recovery: " + daemon_id.strip(), status)
    suffix = hashlib.sha256(daemon_id.strip().encode()).hexdigest()[:12]
    name = "clipforge-export-recovery-" + suffix
    status, details = capture(["docker", "buildx", "inspect", name], root)
    if status:
        if not re.search(r"no builder [^\n]*(?:found|exists)|builder [^\n]*not found", details, re.IGNORECASE):
            raise BuildFailure("Cannot inspect recovery builder: " + details.strip(), status)
        status, output = capture([
            "docker", "buildx", "create", "--name", name,
            "--driver", "docker-container", "--driver-opt", "default-load=true",
        ], root)
        if status:
            raise BuildFailure("Cannot create recovery builder: " + output.strip(), status)
    elif not re.search(r"^Driver:\s+docker-container\s*$", details, re.MULTILINE):
        raise BuildFailure("Recovery builder has an unexpected driver; leaving it untouched.")
    return name


def build_backend(root=ROOT, retry_delay=10):
    root = Path(root)
    reports = root / "reports"
    reports.mkdir(exist_ok=True)
    log_dir = Path(tempfile.mkdtemp(prefix="backend-build-", dir=reports))
    report_path = reports / "backend-image-build.json"
    report = {"status": "building", "attempts": [], "log_directory": str(log_dir),
              "application_runtime_changed": False, "recovery_builder": None}

    def save():
        # Atomic replacement keeps a partial report from appearing successful.
        temporary = log_dir / "report.json.tmp"
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        temporary.replace(report_path)

    save()
    try:
        status, _ = capture(["docker", "compose", "version"], root)
        compose = ["docker", "compose"] if status == 0 else ["docker-compose"]
        env = {**os.environ, "BUILDKIT_PROGRESS": "plain"}
        command = [*compose, "--env-file", ".env", "build", "backend"]
        for attempt in range(1, 4):
            mode = "isolated-builder" if attempt == 3 else "compose"
            log_path = log_dir / f"attempt-{attempt}.log"
            print(f"Backend image build {attempt}/3 ({mode}). Log: {log_path}", flush=True)
            status, output = run_build(command, root, log_path, env)
            report["attempts"].append({"attempt": attempt, "mode": mode,
                                       "exit_code": status, "log": str(log_path),
                                       "export_writer_lock": export_writer_locked(output)})
            save()
            if status == 0:
                report["status"] = "build_succeeded"
                save()
                print("Image built; activation must still verify image hashes and wait for idle work.")
                return 0
            if not export_writer_locked(output) or attempt == 3:
                raise BuildFailure(f"Backend image build failed; runtime untouched. Log: {log_path}", status)
            if attempt == 1:
                print(f"Containerd export writer is locked; retrying from cache in {retry_delay}s.", flush=True)
                time.sleep(retry_delay)
            else:
                name = recovery_builder(root, compose)
                report["recovery_builder"] = name
                save()
                print("Export lock persists. Using an isolated BuildKit cache; its first build may take longer.", flush=True)
                command = [*compose, "--env-file", ".env", "build", "--builder", name, "backend"]
                env = {**env, "COMPOSE_BAKE": "false"}
    except (BuildFailure, OSError) as error:
        report.update(status="failed", error=str(error))
        save()
        print(str(error), file=sys.stderr)
        return getattr(error, "status", 1)
    except KeyboardInterrupt:
        report["status"] = "interrupted"
        save()
        return 130


if __name__ == "__main__":
    if sys.argv[1:]:
        print(__doc__.strip())
        raise SystemExit(0 if sys.argv[1:] in (["--help"], ["-h"]) else 2)
    raise SystemExit(build_backend())
