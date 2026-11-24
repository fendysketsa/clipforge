"""Append-only episodic ledger for the AI Office (CompanyOS 'Learn' phase).

One rule per incident, timestamped, with an enforcement gate. `MEMORY.md` is a
generated index and `check()` fails when it drifts. Nothing here publishes,
changes operator settings or fabricates QC evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re
import tempfile

VERSION = 1
FIELDS = ('rule', 'trigger_surface', 'incident', 'enforcement')

SEED = (
    dict(rule='Pass an ordered recent-style sequence to choose_topic, never a set.',
         trigger_surface='Scheduling Facebook topic stories or requesting series=topik without a topic.',
         incident='24 Nov 2026 — a set reached recent_styles[-3:], raising TypeError; topic stories never ran and /api/facebook/originals returned 500.',
         enforcement='backend/tests/test_facebook_recovery.py::test_topic_series_request_accepts_recent_styles_without_type_error'),
    dict(rule='Exclude recovery_status=skipped from the story_blocked gate.',
         trigger_surface='Planning a new Story while an expired, never-dispatched Story remains in the ledger.',
         incident='24 Nov 2026 — a skipped terminal Story kept its message, so every later Story slot was blocked.',
         enforcement='backend/tests/test_facebook_recovery.py::test_skipped_expired_story_does_not_block_future_story_slot'),
    dict(rule='Fingerprint every runtime scene module before calling an image source-verified.',
         trigger_surface='Adding a Motlab .mjs used by render or startup verification.',
         incident='24 Nov 2026 — story-scene.mjs affected rendering but was absent from the deployment manifest.',
         enforcement='backend/tests/test_compose_deployment.py::test_image_manifest_covers_bot_backend_and_renderer'),
    dict(rule='Never hold the shared browser turn while waiting out an upload cooldown.',
         trigger_surface='Changing execute_social_upload cooldown or browser-turn ordering.',
         incident='24 Nov 2026 — the cooldown slept inside the turn, so other platforms could not upload.',
         enforcement='backend/tests/test_social_upload_spacing.py::test_cooldown_wait_releases_the_shared_browser_turn'),
    dict(rule='Update stale fixtures when an owner signature or snapshot shape changes.',
         trigger_surface='Changing request_original, office_snapshot keys, module lists or rendered UI text.',
         incident='24 Nov 2026 — 13 full-suite failures came from fixtures, not production behaviour.',
         enforcement='backend/.venv/bin/python -m pytest tests -q (full suite must stay green)'),
    dict(rule='Publish strategic directives without creating a parallel production owner.',
         trigger_surface='Extending the digital leader or adding a new coordinator capability.',
         incident='24 Nov 2026 — directives were added as read-only guidance; workers keep QC and publishing ownership.',
         enforcement='backend/tests/test_ai_office_director.py::test_coordinator_publishes_director_without_new_tasks'),
    dict(rule='A skill may read evidence but must never invent QC approval or remote publication.',
         trigger_surface='Implementing or calling any /yt-* content skill.',
         incident='24 Nov 2026 — yt-audit returns hold unless every required proof is supplied by the caller.',
         enforcement='backend/tests/test_yt_skills.py::test_edit_retention_chapters_and_audit_are_bounded_and_do_not_fabricate'),
)


def ledger_path(root=None):
    base = Path(root) if root is not None else Path(__file__).resolve().parent
    return base / 'data' / 'ai-office-learnings'


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.learning-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _entry_path(entries: Path, rule: str, recorded: str) -> Path:
    slug = re.sub(r'[^a-z0-9]+', '-', rule.casefold()).strip('-')[:72].rstrip('-')
    return entries / (recorded + '-' + (slug or 'rule') + '.md')


def _render(entry: dict) -> str:
    front = '\n'.join(f'{key}: {entry[key]}' for key in ('recorded', 'incident_date', 'rule') if entry.get(key))
    body = '\n\n'.join(f'## {label}\n\n{entry[key]}' for label, key in (
        ('Rule', 'rule'), ('Trigger surface', 'trigger_surface'),
        ('Incident', 'incident'), ('Enforcement', 'enforcement')))
    return '---\n' + front + '\n---\n\n' + body + '\n'


def _parse(path: Path) -> dict | None:
    text = path.read_text()
    if not text.startswith('---\n'):
        return None
    head, _, body = text[4:].partition('\n---\n')
    meta = dict(line.split(': ', 1) for line in head.splitlines() if ': ' in line)
    sections = {}
    for block in re.split(r'\n## ', body):
        name, _, value = block.partition('\n\n')
        if name in ('Rule', 'Trigger surface', 'Incident', 'Enforcement'):
            sections[name] = value.strip()
    if not all(sections.get(name) for name in ('Rule', 'Trigger surface', 'Incident', 'Enforcement')):
        return None
    return dict(recorded=meta.get('recorded', path.stem[:20]), incident_date=meta.get('incident_date', ''),
                rule=sections['Rule'], trigger_surface=sections['Trigger surface'],
                incident=sections['Incident'], enforcement=sections['Enforcement'])


def entries(root=None):
    folder = ledger_path(root) / 'entries'
    rows = []
    if folder.exists():
        for path in sorted(folder.glob('*.md'), reverse=True):
            row = _parse(path)
            if row:
                rows.append(dict(row, file=path.name))
    return rows


def rebuild_index(root=None):
    base = ledger_path(root)
    rows = entries(root)
    lines = ['# AI Office learning ledger', '',
             'Generated from `entries/`. Add entries with POST /api/ai-office/learning.', '']
    lines += [f"- {row['recorded']} — {row['rule']}" for row in rows]
    _write(base / 'MEMORY.md', '\n'.join(lines) + '\n')
    return len(rows)


def check(root=None):
    base = ledger_path(root)
    index = base / 'MEMORY.md'
    if not index.exists():
        return False
    expected = [f"- {row['recorded']} — {row['rule']}" for row in entries(root)]
    actual = [line for line in index.read_text().splitlines() if line.startswith('- ')]
    return actual == expected


def ensure_seed(root=None):
    base = ledger_path(root)
    wrote = False
    for item in SEED:
        recorded = '2026-11-24T000000Z'
        path = _entry_path(base / 'entries', item['rule'], recorded)
        if not path.exists():
            _write(path, _render(dict(item, recorded=recorded, incident_date='2026-11-24')))
            wrote = True
    if wrote or not (base / 'MEMORY.md').exists():
        rebuild_index(root)
    return len(entries(root))


def record(payload, root=None):
    if not isinstance(payload, dict):
        raise ValueError('Catatan pembelajaran wajib berupa objek.')
    values = {}
    for key in FIELDS:
        value = payload.get(key)
        if not isinstance(value, str) or not 8 <= len(value.strip()) <= 600:
            raise ValueError(f'{key} wajib berupa teks 8–600 karakter.')
        values[key] = re.sub(r'\s+', ' ', value).strip()
    if payload.get('incident_date') and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(payload['incident_date'])):
        raise ValueError('Tanggal insiden tidak valid.')
    recorded = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H%M%SZ')
    base = ledger_path(root)
    entry = dict(values, recorded=recorded, incident_date=str(payload.get('incident_date') or ''))
    path = _entry_path(base / 'entries', entry['rule'], recorded)
    if path.exists():
        raise ValueError('Catatan dengan aturan ini sudah ada.')
    _write(path, _render(entry))
    rebuild_index(root)
    return dict(entry, file=path.name)


def snapshot(root=None):
    rows = entries(root)
    return dict(version=VERSION, total=len(rows),
                last_recorded_at=rows[0]['recorded'] if rows else None,
                index_fresh=check(root),
                rules=[row['rule'] for row in rows[:12]])
