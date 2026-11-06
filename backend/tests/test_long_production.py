"""Long review production must survive Short capacity waits and cleanup."""
from datetime import datetime, timezone
import json

import pytest
import api


@pytest.fixture
def setup_long(monkeypatch):
    stamp = datetime.now(timezone.utc).isoformat()
    short = api.ClipJob(
        id='short', status='completed', created_at=stamp, updated_at=stamp,
        request=api.ClipJobRequest(url='https://www.youtube.com/watch?v=MtoYogBMyII'),
        candidates=[api.ClipCandidate(index=1, start=10, end=40, duration=30,
            score=85, title='Test', reason='complete', text='A complete moment')],
    )
    source = {'url': short.request.url, 'title': 'Original', 'license': 'youtube'}
    run = api.AutoViralRun(id='parent', status='completed', trigger='schedule',
        created_at=stamp, updated_at=stamp,
        request=api.AutoViralRequest(source_rights_confirmed=True,
            source_rights_evidence='Operator documented permission', require_creative_commons=False),
        processed=[{'job_id': short.id, 'source': source}],
    )
    monkeypatch.setattr(api, 'jobs', {short.id: short})
    monkeypatch.setattr(api, 'auto_viral_runs', {run.id: run})
    monkeypatch.setattr(api, 'auto_viral_active_run_id', None)
    monkeypatch.setattr(api, 'normalize_job_request', lambda request: request)
    monkeypatch.setattr(api, 'viral_source_rejection_reason', lambda *a, **k: '')
    monkeypatch.setattr(api, 'source_theme_hashtags', lambda *a, **k: [])
    monkeypatch.setattr(api, 'auto_viral_format_perspective', lambda *a, **k: 'Original commentary')
    started = []
    class Thread:
        def __init__(self, *, target, args, daemon):
            self.args = args
        def start(self):
            started.append(self.args)
    monkeypatch.setattr(api.threading, 'Thread', Thread)
    api.save_long_production_state({'enabled': True, 'daily_target': 1, 'attempts': []})
    return short, run, started


def test_long_queues_even_with_full_short_buffers_and_zero_upload_quota(setup_long, monkeypatch):
    short, run, started = setup_long
    monkeypatch.setattr(api, 'youtube_cron_capacity_room', lambda: False)
    monkeypatch.setattr(api, 'auto_viral_daily_long_upload_target', lambda: 0)
    result = api.queue_review_long_once()
    assert result['status'] == 'queued'
    long = api.jobs[result['job_id']]
    assert long.request.clip_mode == 'highlight_5m'
    assert long.request.compilation_target_seconds == 300
    assert long.request.compilation_anchor_ranges == [(10, 40)]
    assert long.request.paired_short_job_id == short.id
    assert long.request.source_rights_evidence == run.request.source_rights_evidence
    assert not long.request.auto_upload_youtube
    assert started[0][0] == long.id
    assert api.queue_review_long_once()['status'] == 'waiting_for_render'
    assert len(api.long_production_state()['attempts']) == 1


def test_cleaned_short_uses_persisted_authoritative_snapshot(setup_long):
    short, run, _ = setup_long
    run.processed[0]['paired_short_snapshot'] = api.paired_short_snapshot(short)
    api.jobs.clear()
    assert api.queue_review_long_once()['status'] == 'queued'


def test_completed_checkpoint_counts_after_job_cleanup(setup_long):
    result = api.queue_review_long_once()
    state = api.long_production_state()
    state['attempts'][0]['status'] = 'completed'
    api.save_long_production_state(state)
    api.jobs.clear()
    assert api.queue_review_long_once()['status'] == 'daily_target_reached'


def test_reservation_survives_restart_without_duplicate(setup_long):
    api.queue_review_long_once()
    api.jobs.clear()
    assert api.queue_review_long_once()['status'] == 'reserved'


@pytest.mark.parametrize('change', ['no_rights', 'no_evidence', 'no_candidates', 'existing_pair', 'news'])
def test_ineligible_sources_are_never_queued(setup_long, change):
    short, run, started = setup_long
    if change == 'no_rights': run.request.source_rights_confirmed = False
    if change == 'no_evidence': run.request.source_rights_evidence = ''
    if change == 'no_candidates': short.candidates.clear()
    if change == 'existing_pair': run.processed[0]['long_job_id'] = 'prior-long'
    if change == 'news': run.request.cron_theme_key = api.NEWS_HOT_THEME
    assert api.queue_review_long_once()['status'] == 'waiting_for_eligible_short'
    assert not started


def test_campaign_and_disabled_policy_do_not_start_work(setup_long, monkeypatch):
    monkeypatch.setattr(api, 'auto_viral_active_run_id', 'active')
    assert api.queue_review_long_once()['status'] == 'waiting_for_campaign'
    state = api.long_production_state()
    state['enabled'] = False
    api.save_long_production_state(state)
    assert api.queue_review_long_once()['status'] == 'disabled'


def test_gate_rejection_is_durable_and_not_retried(setup_long, monkeypatch):
    monkeypatch.setattr(api, 'viral_source_rejection_reason', lambda *a, **k: 'Content ID')
    assert api.queue_review_long_once()['status'] == 'source_rejected'
    assert api.queue_review_long_once()['status'] == 'waiting_for_eligible_short'
    assert len(api.long_production_state()['attempts']) == 1


def test_corrupt_checkpoint_fails_closed(setup_long):
    api.long_production_path().write_text('{broken')
    with pytest.raises(json.JSONDecodeError):
        api.queue_review_long_once()


def test_worker_persists_relevance_and_review_requirement(setup_long, monkeypatch):
    short, _, _ = setup_long
    result = api.queue_review_long_once()
    job = api.jobs[result['job_id']]
    def render(job_id):
        job.status = 'completed'
        job.candidates = short.candidates
    monkeypatch.setattr(api, 'run_job', render)
    api.run_review_long_job(job.id, short)
    attempt = api.long_production_state()['attempts'][0]
    assert attempt['status'] == 'completed'
    assert attempt['relevance']['passed']
    assert attempt['review_required']


def test_attempt_cap_and_other_long_count(setup_long):
    short, _, _ = setup_long
    day = datetime.now(api.ZoneInfo('Asia/Jakarta')).date().isoformat()
    state = api.long_production_state()
    state['attempts'] = [dict(day=day, short_job_id=str(i), status='failed') for i in range(3)]
    api.save_long_production_state(state)
    assert api.queue_review_long_once()['status'] == 'daily_attempt_limit'
    state['attempts'] = []
    api.save_long_production_state(state)
    api.jobs['other-long'] = short.model_copy(deep=True, update={'id': 'other-long'})
    api.jobs['other-long'].request.clip_mode = 'highlight_5m'
    assert api.queue_review_long_once()['status'] == 'daily_target_reached'


def test_review_hold_excludes_generic_upload_and_repair_sweeper(setup_long, monkeypatch):
    result = api.queue_review_long_once()
    job = api.jobs[result['job_id']]
    job.status = 'completed'
    job.clips = [api.ClipFile(name='resume_cerita_1.mp4', url='/outputs/test.mp4', size_bytes=123)]
    assert job.request.publication_review_required
    assert api.best_automatic_upload_clip_urls(job, 1) == []
    def forbidden(*a, **k):
        pytest.fail('Review-only Long entered the automated upload/repair path')
    monkeypatch.setattr(api, 'best_automatic_upload_clip_urls', forbidden)
    api.jobs = {job.id: job}
    assert api.queue_completed_job_uploads_once() == {'youtube': 0, 'tiktok': 0, 'repair': 0}


def test_control_persists_policy_and_starts_real_queue(setup_long):
    result = api.set_long_production(api.LongProductionControlRequest(enabled=True, daily_target=1))
    assert result['enabled']
    assert result['production']['status'] == 'queued'
    assert api.get_long_production()['attempts'][0]['job_id'] == result['production']['job_id']
