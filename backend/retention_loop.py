"""Evidence-based editing loop from measured YouTube retention.

Reads real analytics only. When a metric is missing it returns a neutral
directive and never predicts, invents or guarantees audience behaviour.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path

VERSION = 1
TEASER_MIN, TEASER_DEFAULT, TEASER_MAX = 12.0, 16.0, 20.0


def _root() -> Path:
    return Path(os.environ.get('CLIPFORGE_RETENTION_DIR',
                               str(Path(__file__).resolve().parent / 'data')))


def path() -> Path:
    return _root() / 'retention_directives.json'


def number(value) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) \
        and math.isfinite(value) and value > 0 else None


def directive(measured_30, median_30, *, views=None) -> dict:
    measured = number(measured_30)
    baseline = number(median_30)
    if measured is None or baseline is None:
        return dict(version=VERSION, measured=False, action='keep', teaser_seconds=TEASER_DEFAULT,
                    payoff='steady', beat_hint='insufficient_measured_data',
                    reason='Belum ada retensi 30 detik terukur dan baseline seri sejenis.')
    ratio = measured / baseline
    if ratio < .8:
        action, teaser, payoff, hint = 'front_load', TEASER_MIN, 'earlier', 'put_new_information_first'
        reason = f'Retensi 30 detik {measured:.1f}% di bawah 80% median seri {baseline:.1f}%.'
    elif ratio > 1.15:
        action, teaser, payoff, hint = 'hold_pace', TEASER_MAX, 'steady', 'keep_current_pacing'
        reason = f'Retensi 30 detik {measured:.1f}% di atas median seri {baseline:.1f}%.'
    else:
        action, teaser, payoff, hint = 'keep', TEASER_DEFAULT, 'steady', 'change_one_variable_only'
        reason = f'Retensi 30 detik {measured:.1f}% sejajar median seri {baseline:.1f}%.'
    return dict(version=VERSION, measured=True, action=action, teaser_seconds=teaser,
                payoff=payoff, beat_hint=hint, ratio=round(ratio, 4), reason=reason,
                sample_views=number(views))


def _read() -> dict:
    file = path()
    if not file.exists():
        return {}
    try:
        data = json.loads(file.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save(series: str, row: dict) -> dict:
    if not isinstance(series, str) or not series.strip() or not isinstance(row, dict):
        raise ValueError('Seri dan arahan retensi wajib valid.')
    data = _read()
    data[series.strip()[:80]] = dict(row, recorded_at=row.get('recorded_at') or '')
    folder = path().parent
    folder.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.retention-', dir=folder)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(data, stream, ensure_ascii=False, sort_keys=True)
        os.replace(temporary, path())
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return row


def load(series: str = '') -> dict:
    data = _read()
    if series and series in data:
        return data[series]
    latest = None
    for row in data.values():
        if isinstance(row, dict) and (latest is None or str(row.get('recorded_at', '')) > str(latest.get('recorded_at', ''))):
            latest = row
    return latest or directive(None, None)


def snapshot() -> dict:
    data = _read()
    return dict(version=VERSION, series=len(data), directives=data)
