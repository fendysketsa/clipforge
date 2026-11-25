"""Digital leader publishes strategy-driven assignments without owning production."""
import pytest

import ai_office_director as director
import yt_skills
from test_ai_office import office  # noqa: F401  (shared coordinator fixture)


BASE = dict(
    cron_enabled=True, generic_enabled=True, attention_enabled=True,
    jobs=0, quality=0, uploads=0, youtube_queued=0, tiktok_queued=0,
    unverified=0, cron_alive=True, generic_alive=True, retry_alive=True,
    attention_alive=True,
    facebook=dict(enabled=True, worker_running=True, active_count=0, state='waiting',
                  detail='', qc_wait_count=0, failed_upload_count=0,
                  unknown_post_count=0, skipped_upload_count=0,
                  autonomous_recovery_version=1),
    incidents=[],
)


def test_default_strategy_sets_education_and_moral_focus():
    strategy = director.validate_strategy({})
    assert strategy['version'] == director.VERSION
    assert strategy['model'] == 'supervised_existing_workers'
    assert 'anak sekolah' in strategy['mission']
    assert {'pendidikan_moral', 'kehidupan_sehari_hari', 'anak_sekolah'} <= set(strategy['focus'])
    assert set(strategy['priority_platforms']) == {'facebook', 'youtube', 'tiktok'}
    assert any('QC' in row for row in strategy['content_standard'])


@pytest.mark.parametrize('change', [
    {'name': ''}, {'focus': []}, {'focus': ['x' * 80]},
    {'priority_platforms': ['instagram']}, {'priority_platforms': ['youtube', 'youtube']},
    {'content_standard': ['x']},
])
def test_invalid_strategy_is_rejected_without_mutating_defaults(change):
    with pytest.raises(ValueError):
        director.validate_strategy(change)
    assert director.validate_strategy({}) == director.DEFAULT_STRATEGY


def test_operator_can_refine_strategy_without_new_permissions():
    strategy = director.validate_strategy(dict(
        mission='Cerita moral untuk anak sekolah dasar.', focus=['pendidikan_moral'],
        priority_platforms=['facebook', 'youtube']))
    assert strategy['mission'] == 'Cerita moral untuk anak sekolah dasar.'
    assert strategy['priority_platforms'] == ['facebook', 'youtube']
    assert 'capabilities' not in strategy and 'publish' not in strategy


def test_directives_cover_every_department_and_are_bounded():
    rows = director.build_directives(director.DEFAULT_STRATEGY, BASE)
    assert len(rows) == 6
    assert {row['department'] for row in rows} == {
        'production', 'facebook', 'distribution', 'quality', 'recovery', 'cleanup'}
    assert {row['key']: row['status'] for row in rows} == {
        'education_first': 'active', 'facebook_education': 'active',
        'all_platforms': 'active', 'education_qc': 'active',
        'delivery_proof': 'blocked', 'terminal_hygiene': 'blocked'}
    assert all(row['action'] in {
        'use_supported_cron', 'recover_facebook', 'recover_scheduled_uploads',
        'review_quality', 'verify_upload', 'cleanup_history'} for row in rows)
    assert all(set(row['evidence']) == {
        'jobs', 'quality', 'uploads', 'queued', 'unverified', 'facebook_active',
        'facebook_qc_wait', 'facebook_failed', 'open_incidents'} for row in rows)
    assert all(row['title'] and row['reason'] and row['id'] for row in rows)
    assert {skill for row in rows for skill in row['skills']} == set(yt_skills.SKILL_IDS)


def test_operator_pause_and_qc_hold_block_directives_without_inventing_work():
    state = dict(BASE, cron_enabled=False, generic_enabled=False, attention_enabled=False,
                 jobs=3, quality=1, unverified=2,
                 facebook=dict(BASE['facebook'], enabled=False, qc_wait_count=2))
    rows = director.build_directives(director.DEFAULT_STRATEGY, state)
    assert {row['key']: row['status'] for row in rows} == {
        'education_first': 'blocked', 'facebook_education': 'blocked',
        'all_platforms': 'blocked', 'education_qc': 'blocked',
        'delivery_proof': 'blocked', 'terminal_hygiene': 'blocked'}
    assert not any(row['automatic'] for row in rows)


def test_repair_permissions_fail_closed_like_a_tool_allowlist():
    assert director.repair_permission('verify_upload') == 'owner_wake'
    assert director.repair_permission('recover_facebook') == 'owner_wake'
    assert director.repair_permission('restore_access') == 'operator'
    assert director.repair_permission('new_unknown_action') == 'operator'
    assert director.repair_permission(None) == 'operator'


def test_goal_checklist_is_bounded_and_driven_by_observed_incidents():
    incident = dict(id='recovery:x', department='recovery', title='Verifikasi',
                    action='verify_upload', automatic=True, state='waiting')
    goal = director.goal_checklist(director.DEFAULT_STRATEGY,
                                   dict(BASE, incidents=[incident, dict(incident, id='other')]))
    assert goal['goal'] == director.DEFAULT_STRATEGY['mission']
    assert goal['total'] == 2 and len(goal['steps']) == 2
    assert goal['steps'][0]['permission'] == 'owner_wake'
    assert goal['steps'][0]['status'] == 'waiting_owner'
    assert goal['steps'][0]['evidence']['jobs'] == BASE['jobs']
    assert goal['bounded'] is True and 'observasi' in goal['completion']
    assert director.goal_checklist({}, None)['steps'] == []


def test_strategy_revision_changes_with_strategy_only():
    first = director.revision(director.DEFAULT_STRATEGY)
    changed = director.validate_strategy(dict(focus=['pendidikan_moral']))
    assert first != director.revision(changed)
    assert first == director.revision(director.DEFAULT_STRATEGY)


def test_strategy_endpoint_refines_focus_without_publication_permissions(office):
    import ai_office
    _, api = office
    routes = {}
    class App:
        def get(self, path):
            return lambda callback: routes.setdefault(('GET', path), callback)
        def post(self, path):
            return lambda callback: routes.setdefault(('POST', path), callback)
        def add_event_handler(self, event, callback):
            pass
    installed = ai_office.install(App(), api)
    result = routes['POST', '/api/ai-office/strategy'](dict(
        mission='Cerita moral untuk anak sekolah dasar.', focus=['pendidikan_moral']))
    assert result['accepted'] is True
    assert result['strategy']['mission'] == 'Cerita moral untuk anak sekolah dasar.'
    assert installed.strategy['focus'] == ['pendidikan_moral']
    assert installed.strategy['model'] == 'supervised_existing_workers'
    assert 'publish' not in installed.strategy and 'capabilities' not in installed.strategy
    assert installed.path.exists()
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        routes['POST', '/api/ai-office/strategy'](dict(priority_platforms=['instagram']))


def test_coordinator_publishes_director_without_new_tasks(office):
    service, api = office
    service.run_once()
    snapshot = service.snapshot()
    assert snapshot['control_version'] == 2
    assert snapshot['capabilities']['digital_director'] is True
    assert snapshot['director']['model'] == 'digital_leader'
    assert len(snapshot['director']['directives']) == 6
    assert snapshot['director']['strategy']['name'] == director.DEFAULT_STRATEGY['name']
    assert not any(task['department'] == 'direktur' for task in snapshot['tasks'])
