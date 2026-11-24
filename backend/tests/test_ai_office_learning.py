"""CompanyOS-style episodic ledger: append-only rules with an enforced index."""
import pytest

import ai_office_learning as learning
from test_ai_office import office  # noqa: F401  (shared coordinator fixture)


def test_seed_ledger_is_complete_and_index_is_fresh(tmp_path):
    assert learning.ensure_seed(tmp_path) == 7
    result = learning.snapshot(tmp_path)
    assert result['version'] == learning.VERSION
    assert result['total'] == 7
    assert result['index_fresh'] is True
    assert result['last_recorded_at']
    assert len(result['rules']) == 7


def test_entries_carry_rule_surface_incident_and_enforcement(tmp_path):
    learning.ensure_seed(tmp_path)
    for row in learning.entries(tmp_path):
        assert all(row[key] for key in learning.FIELDS)
        assert row['enforcement'].startswith('backend/')
        assert row['rule'] in (tmp_path / 'data/ai-office-learnings/MEMORY.md').read_text()


def test_record_appends_and_rebuilds_index(tmp_path):
    learning.ensure_seed(tmp_path)
    before = learning.snapshot(tmp_path)['total']
    entry = learning.record(dict(
        rule='Every new browser turn owner must release the turn on failure.',
        trigger_surface='Adding a publish worker that shares social_upload_turn.',
        incident='24 Nov 2026 — a failed worker left the turn reserved for other platforms.',
        enforcement='backend/tests/test_social_upload_spacing.py::test_failed_upload_releases_turn_for_other_platform',
        incident_date='2026-11-24'), tmp_path)
    after = learning.snapshot(tmp_path)
    assert after['total'] == before + 1
    assert after['index_fresh'] is True
    assert entry['file'].startswith(entry['recorded'])
    assert entry['rule'] in (tmp_path / 'data/ai-office-learnings/MEMORY.md').read_text()


def test_index_drift_is_detected(tmp_path):
    learning.ensure_seed(tmp_path)
    index = tmp_path / 'data/ai-office-learnings/MEMORY.md'
    index.write_text(index.read_text() + '- stale line\n')
    assert learning.check(tmp_path) is False
    learning.rebuild_index(tmp_path)
    assert learning.check(tmp_path) is True


@pytest.mark.parametrize('payload', [
    {}, {'rule': 'short', 'trigger_surface': 'x' * 20, 'incident': 'y' * 20, 'enforcement': 'z' * 20},
    dict(rule='a' * 40, trigger_surface='b' * 40, incident='c' * 40, enforcement='d' * 40, incident_date='24-11-2026'),
])
def test_invalid_entries_are_rejected_without_touching_ledger(tmp_path, payload):
    learning.ensure_seed(tmp_path)
    before = learning.snapshot(tmp_path)
    with pytest.raises(ValueError):
        learning.record(payload, tmp_path)
    assert learning.snapshot(tmp_path) == before


def test_director_exposes_learning_without_new_owner(office):
    service, _ = office
    learning.ensure_seed(service._learning_root())
    snap = service.snapshot()
    assert snap['capabilities']['organizational_learning'] is True
    assert snap['director']['learning']['total'] == 7
    assert snap['director']['learning']['index_fresh'] is True
    assert not any(task['department'] == 'learning' for task in snap['tasks'])
