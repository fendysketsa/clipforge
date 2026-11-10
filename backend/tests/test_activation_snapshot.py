"""Reproduce editing an activation file while Bash is blocked in a wait."""
import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
ACTIVATORS = (
    'activate-youtube-quiet-check.sh',
    'activate-cron-director-effects.sh',
    'activate-long-tiktok-upload.sh',
    'activate-history-card-layout.sh',
    'activate-upload-queue-ui.sh',
    'activate-upload-submission-recovery.sh',
)


def snapshot_header(name):
    source = (ROOT / 'scripts' / name).read_text()
    before, marker, _ = source.partition('unset CLIPFORGE_ACTIVATION_SNAPSHOT\n')
    assert marker
    return before + marker


def mutate_while_waiting(path, header):
    # Larger than Bash's read buffer so an unfrozen interpreter must read the
    # modified file after its blocking command, matching the production error.
    body = "printf 'READY\\n'\nIFS= read -r proceed\n" + '# padding\n' * 4000
    body += "printf 'FINISHED:%s\\n' \"$1\"\n"
    path.write_text(header + body)
    env = dict(os.environ)
    env.pop('CLIPFORGE_ACTIVATION_SNAPSHOT', None)
    process = subprocess.Popen(['bash', str(path), 'argument with spaces'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    try:
        assert process.stdout.readline() == 'READY\n'
        path.write_text(') # intentionally invalid replacement\n' * 4000)
        output, error = process.communicate('continue\n', timeout=10)
        return process.returncode, output, error
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def test_reproduces_original_live_edit_syntax_error(tmp_path):
    status, _, error = mutate_while_waiting(tmp_path / 'old.sh', '#!/usr/bin/env bash\nset -euo pipefail\n')
    assert status != 0 and 'syntax error' in error


@pytest.mark.parametrize('name', ACTIVATORS)
def test_activation_uses_original_in_memory_source_even_after_file_edit(tmp_path, name):
    status, output, error = mutate_while_waiting(tmp_path / 'activation.sh', snapshot_header(name))
    assert status == 0, error
    assert output == 'FINISHED:argument with spaces\n' and not error


def test_invalid_snapshot_is_rejected_before_side_effects(tmp_path):
    script = tmp_path / 'invalid.sh'
    marker = tmp_path / 'must-not-exist'
    script.write_text(snapshot_header(ACTIVATORS[0]) + f'touch "{marker}"\n)\n')
    result = subprocess.run(['bash', str(script)], capture_output=True, text=True)
    assert result.returncode != 0 and 'syntax error' in result.stderr
    assert not marker.exists()
