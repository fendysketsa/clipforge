import os
from pathlib import Path
import subprocess
import sys
import time

import pytest
import render_process

pytestmark=pytest.mark.skipif(os.name!='posix',reason='Owned Linux renderer sessions')


def alive(pid):
    try:
        # A reparented zombie cannot consume CPU/RAM and is reaped by init.
        return Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1].split()[0]!='Z'
    except FileNotFoundError:
        return False


def test_cancel_releases_encoder_child_even_when_parent_exits_first():
    script='''import subprocess,sys,time
child=subprocess.Popen([sys.executable,'-c','import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);print("ready",flush=True);time.sleep(60)'],stdout=subprocess.PIPE,text=True)
child.stdout.readline()
print(child.pid,flush=True)
time.sleep(60)
'''
    process=subprocess.Popen([sys.executable,'-c',script],start_new_session=True,
        stdout=subprocess.PIPE,text=True)
    unrelated=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
    render_process.track_session(process)
    child=int(process.stdout.readline().strip())
    try:
        render_process.terminate(process,.3)
        end=time.monotonic()+2
        while alive(child) and time.monotonic()<end:time.sleep(.01)
        assert process.poll() is not None and not alive(child)
        assert unrelated.poll() is None
        render_process.terminate(process,.3)  # idempotent after reaping
    finally:
        if process.poll() is None:render_process.terminate(process,.3)
        unrelated.terminate();unrelated.wait(timeout=3)
        process.stdout.close()


def test_term_ignoring_worker_is_killed_with_a_bounded_wait():
    process=subprocess.Popen([sys.executable,'-c',
        'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);print("ready",flush=True);time.sleep(60)'],
        start_new_session=True,stdout=subprocess.PIPE,text=True)
    process.stdout.readline();render_process.track_session(process)
    start=time.monotonic()
    try:
        render_process.terminate(process,.2)
        assert process.poll() is not None and time.monotonic()-start<2
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=3)
        process.stdout.close()


def test_legacy_worker_does_not_signal_shared_process_group(monkeypatch):
    process=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
    monkeypatch.setattr(os,'killpg',lambda *a:pytest.fail('Never kill a shared group'))
    try:
        render_process.terminate(process,.3)
        assert process.poll() is not None
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=3)
