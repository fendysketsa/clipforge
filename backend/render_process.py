"""Release subprocesses owned by one renderer without touching shared browsers."""
from __future__ import annotations

import os
import signal
import subprocess


def track_session(process) -> None:
    """Only call immediately after Popen(start_new_session=True)."""
    process._clipforge_process_group = None
    pid = getattr(process, "pid", None)
    if os.name != "posix" or not isinstance(pid, int) or pid <= 1:
        return
    try:
        if pid not in {os.getpid(), os.getpgrp()} and os.getpgid(pid) == pid:
            process._clipforge_process_group = pid
    except ProcessLookupError:
        pass


def terminate(process, grace_seconds: float = 5) -> None:
    group = getattr(process, "_clipforge_process_group", None)
    if group is not None:
        try:
            os.killpg(group, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            pass
        finally:
            # The parent can exit before its encoder/Chromium children. Release
            # those too, including a child which ignores SIGTERM.
            try:
                os.killpg(group, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=grace_seconds)
        process._clipforge_process_group = None
        return
    # Legacy workers/shared services were not launched in an owned session.
    # Never signal their process group.
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=grace_seconds)
