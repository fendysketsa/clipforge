"""A rejected source must not waste every cron run after its job is cleaned up."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

import api


URL = 'https://www.youtube.com/watch?v=9FOhn2EOVsE'
NOW = datetime(2026, 11, 6, 5, 0, tzinfo=timezone.utc)


def campaign(*, age_hours=2, trigger='schedule', **item_changes):
    when = (NOW - timedelta(hours=age_hours)).isoformat()
    return api.AutoViralRun(
        id='prior-campaign', status='completed', trigger=trigger,
        created_at=when, updated_at=when, finished_at=when,
        request=api.AutoViralRequest(),
        processed=[dict(
            url=URL, status='failed', job_status='failed', job_id='deleted-failed-job',
            clip_count=0, error=api.SHORT_SELECTION_REJECTION_PREFIX + ' Gunakan sumber lain.',
        ) | item_changes],
    )


def install(monkeypatch, run):
    monkeypatch.setattr(api, 'auto_viral_runs', {run.id: run})
    monkeypatch.setattr(api, 'jobs', {})
    monkeypatch.setattr(api, 'source_usage_history', {})
    monkeypatch.setenv('AUTO_VIRAL_REJECTED_SOURCE_COOLDOWN_HOURS', '24')


def test_failed_selection_remains_excluded_after_job_cleanup_without_marking_success(monkeypatch):
    run = campaign()
    install(monkeypatch, run)
    before = deepcopy(run.model_dump())
    assert api.recently_rejected_scheduled_source_urls(NOW) == {URL}
    assert run.model_dump() == before
    assert api.source_usage_history == {}
    assert api.jobs == {}


@pytest.mark.parametrize('age', [24, 25, 200])
def test_no_candidate_rejection_expires_instead_of_banning_source_forever(monkeypatch, age):
    install(monkeypatch, campaign(age_hours=age))
    assert api.recently_rejected_scheduled_source_urls(NOW) == set()


@pytest.mark.parametrize('changes', [
    {'error': 'Network timeout during download'},
    {'error': 'AI provider unavailable'},
    {'error': 'FFmpeg render failed'},
    {'error': 'Upload belum terkonfirmasi'},
    {'error': 'Tidak ada clip yang lolos seluruh gate kualitas dan upload YouTube'},
    {'status': 'cancelled'}, {'status': 'manual_review_required'},
    {'job_status': 'completed'}, {'clip_count': 1},
    {'error': ''}, {'selection_rejected_at': 'invalid'},
    {'selection_rejected_at': (NOW + timedelta(hours=1)).isoformat()},
])
def test_unrelated_failures_successes_and_uncertain_dates_do_not_enter_selection_cooldown(monkeypatch, changes):
    install(monkeypatch, campaign(**changes))
    assert api.recently_rejected_scheduled_source_urls(NOW) == set()


def test_manual_campaign_does_not_create_automatic_source_rejection(monkeypatch):
    install(monkeypatch, campaign(trigger='manual'))
    assert api.recently_rejected_scheduled_source_urls(NOW) == set()


def test_exact_rejection_time_survives_later_parent_campaign_updates(monkeypatch):
    install(monkeypatch, campaign(
        selection_rejected_at=(NOW - timedelta(hours=25)).isoformat(),
    ))
    assert api.recently_rejected_scheduled_source_urls(NOW) == set()


def test_source_metadata_url_is_normalized_when_top_level_url_is_missing(monkeypatch):
    install(monkeypatch, campaign(url='', source={'url': 'https://youtu.be/9FOhn2EOVsE?t=4'}))
    assert api.recently_rejected_scheduled_source_urls(NOW) == {URL}


def test_cron_exclusions_include_rejection_without_mutating_manual_history(monkeypatch):
    current = datetime.now(timezone.utc)
    run = campaign(selection_rejected_at=(current - timedelta(minutes=30)).isoformat())
    install(monkeypatch, run)
    monkeypatch.setattr(api, 'processed_source_history', set())
    assert URL in api.recently_processed_job_source_urls(7)
    assert URL not in api.processed_job_source_urls()


def test_inflight_campaign_failed_source_is_already_protected(monkeypatch):
    run = campaign()
    run.status = 'running'
    run.finished_at = None
    install(monkeypatch, run)
    assert api.recently_rejected_scheduled_source_urls(NOW) == {URL}
