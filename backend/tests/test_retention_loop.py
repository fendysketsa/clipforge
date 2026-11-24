"""Retention loop reads measured data only and never predicts an outcome."""
import retention_loop


def test_missing_measurement_is_neutral():
    row = retention_loop.directive(None, None)
    assert row['measured'] is False and row['action'] == 'keep'
    assert row['teaser_seconds'] == retention_loop.TEASER_DEFAULT
    assert 'insufficient' in row['beat_hint']


def test_below_baseline_front_loads_and_shortens_teaser():
    row = retention_loop.directive(40, 60, views=1200)
    assert row['measured'] is True and row['action'] == 'front_load'
    assert row['teaser_seconds'] == retention_loop.TEASER_MIN
    assert row['payoff'] == 'earlier'
    assert row['ratio'] < .8


def test_above_baseline_holds_pace():
    row = retention_loop.directive(90, 60)
    assert row['action'] == 'hold_pace'
    assert row['teaser_seconds'] == retention_loop.TEASER_MAX


def test_bad_values_are_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv('CLIPFORGE_RETENTION_DIR', str(tmp_path))
    for value in (float('nan'), float('inf'), -1, 0, True, '84'):
        assert retention_loop.directive(value, 60)['measured'] is False


def test_directive_persists_per_series(tmp_path, monkeypatch):
    monkeypatch.setenv('CLIPFORGE_RETENTION_DIR', str(tmp_path))
    row = dict(retention_loop.directive(40, 60), recorded_at='2026-11-24T20:00:00+00:00')
    retention_loop.save('RYUUNDY Long', row)
    assert retention_loop.load('RYUUNDY Long')['action'] == 'front_load'
    other = dict(retention_loop.directive(90, 60, views=800), recorded_at='2026-11-24T20:05:00+00:00')
    retention_loop.save('Other', other)
    assert retention_loop.load('RYUUNDY Long')['action'] == 'front_load'
    assert retention_loop.load()['action'] == 'hold_pace'
    assert retention_loop.snapshot()['series'] == 2
