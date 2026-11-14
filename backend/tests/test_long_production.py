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
    source = {'url': short.request.url, 'title': 'Original', 'license': 'youtube',
              'duration': 1200, 'views': 5000}
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
    assert long.request.cron_long_strategy
    assert long.request.compilation_target_seconds == 300
    assert long.request.compilation_anchor_ranges == [(10, 40)]
    assert long.request.paired_short_job_id == short.id
    assert long.request.source_rights_evidence == run.request.source_rights_evidence
    assert not long.request.auto_upload_youtube
    assert started[0][0] == long.id
    assert api.queue_review_long_once()['status'] == 'waiting_for_render'
    assert len(api.long_production_state()['attempts']) == 1


def test_cron_skips_popular_short_sources_without_spending_render_attempts(setup_long):
    _, run, started = setup_long
    run.processed[0]['source'].update(duration=45, views=1000000)
    result = api.queue_review_long_once()
    assert result['status'] == 'waiting_for_eligible_short'
    assert result['long_source_candidates'][0]['reasons'] == ['source_long_duration_missing_or_under_300s']
    assert api.long_production_state()['attempts'] == []
    assert not started


def test_cron_ranks_long_demand_across_campaign_recency(setup_long):
    short, run, _ = setup_long
    other = short.model_copy(deep=True, update={'id': 'stronger-long-source'})
    other.request.url = 'https://www.youtube.com/watch?v=otherABC123'
    api.jobs[other.id] = other
    run.processed.append({'job_id': other.id, 'source': dict(
        url=other.request.url, title='Complete Long source', duration=1800, views=50000)})
    assert api.queue_review_long_once()['short_job_id'] == other.id


def test_political_long_renders_but_waits_for_human_review_before_automatic_qc(setup_long):
    short, run, started = setup_long
    run.request.cron_theme_key = 'domestic_politics'
    short.request.scheduled_theme_key = 'domestic_politics'
    short.request.scheduled_public_source_credit = True
    result = api.queue_review_long_once()
    assert result['status'] == 'queued'
    long = api.jobs[result['job_id']]
    assert long.request.publication_review_required
    long.status = 'completed'
    clip = api.ClipFile(name='resume_cerita_test.mp4', url='/outputs/test.mp4', size_bytes=123)
    long.clips = [clip]
    state = api.long_production_state()
    state['auto_qc_enabled'] = True
    api.save_long_production_state(state)
    assert api.queue_review_long_qc_once() == 0
    assert len(started) == 1
    assert 'review manusia' in api.long_upload_review_hold(long, clip)
    assert api.get_long_production()['manual_review_holds'][0]['job_id'] == long.id


def test_long_skips_source_at_lifetime_cap_and_uses_another_short(setup_long):
    short,run,_=setup_long
    prior=short.model_copy(deep=True,update={'id':'previous-process'})
    api.jobs[prior.id]=prior
    other=short.model_copy(deep=True,update={'id':'other-short'})
    other.request.url='https://www.youtube.com/watch?v=otherABC123'
    api.jobs[other.id]=other
    run.processed.append({'job_id':other.id,'source':dict(url=other.request.url,title='Other source',duration=1200,views=5000)})
    result=api.queue_review_long_once()
    assert result['status']=='queued' and result['short_job_id']==other.id


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


@pytest.mark.parametrize('confirmed', [True, False])
def test_remote_confirmation_settles_cleaned_render_without_approving_qc(setup_long, confirmed):
    result = api.queue_review_long_once()
    state = api.long_production_state()
    state['auto_qc_enabled'] = True
    api.save_long_production_state(state)
    api.jobs.clear()
    row = api.YouTubeUploadJob(id='uploaded-long', source_job_id=result['job_id'],
        clip_url='/outputs/long/resume_cerita_test.mp4', clip_name='resume_cerita_test.mp4',
        title='Existing Long', status='completed', created_at=api.now_iso(), updated_at=api.now_iso(),
        upload_confirmed=confirmed, video_url='https://www.youtube.com/watch?v=abcdefghijk')
    api.youtube_uploads[row.id] = row
    outcome = api.queue_review_long_once()
    assert outcome['status'] == ('daily_target_reached' if confirmed else 'reserved')
    attempt = api.long_production_state()['attempts'][0]
    assert attempt.get('qc_decision') is None  # remote success never invents PASS_UPLOAD
    if confirmed:
        assert attempt['status'] == 'completed'
        assert attempt['confirmed_upload_id'] == row.id
        assert attempt['confirmed_video_url'] == row.video_url
    else:
        assert 'confirmed_upload_id' not in attempt


def test_restart_completed_job_repairs_queued_checkpoint_before_cleanup(setup_long):
    result = api.queue_review_long_once()
    api.jobs[result['job_id']].status = 'completed'
    assert api.queue_review_long_once()['status'] == 'daily_target_reached'
    assert api.long_production_state()['attempts'][0]['status'] == 'completed'
    api.jobs.clear()
    assert api.queue_review_long_once()['status'] == 'daily_target_reached'


@pytest.mark.parametrize('decision', ['DROP_SOURCE', 'REPAIR_ONCE'])
def test_cleaned_rejected_render_does_not_leave_an_eternal_reservation(setup_long, decision):
    day = datetime.now(api.ZoneInfo('Asia/Jakarta')).date().isoformat()
    state = api.long_production_state()
    state.update(auto_qc_enabled=True, attempts=[dict(day=day, job_id='old-long',
        short_job_id='old-short', status='queued', qc_decision=decision)])
    api.save_long_production_state(state)
    result = api.queue_review_long_once()
    assert result['status'] == 'queued'
    restored = api.long_production_state()['attempts'][0]
    assert restored['status'] == 'completed' and restored['qc_decision'] == decision


def test_long_production_read_reports_live_render_progress_without_mutating_checkpoint(setup_long):
    result = api.queue_review_long_once()
    job = api.jobs[result['job_id']]
    job.status = 'running'; job.progress_percent = 80
    job.progress_detail = 'bagian cerita 6 dari 10'
    view = api.get_long_production()
    assert view['attempts'][0]['status'] == 'running'
    assert view['active_jobs'][0]['progress_percent'] == 80
    assert view['active_jobs'][0]['progress_detail'] == 'bagian cerita 6 dari 10'
    assert api.long_production_state()['attempts'][0]['status'] == 'queued'


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


def test_failed_story_review_is_durable_even_without_rendered_clips(setup_long, monkeypatch, tmp_path):
    short, _, _ = setup_long
    result = api.queue_review_long_once()
    job = api.jobs[result['job_id']]
    monkeypatch.setattr(api, 'OUTPUTS_DIR', tmp_path / 'outputs')
    path = api.OUTPUTS_DIR / job.id / 'story' / 'cron_long_story_review.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'passed': False, 'reasons': ['resolved_ending']}))
    def render(job_id):
        job.status = 'failed'
        job.error = 'Long story incomplete'
    monkeypatch.setattr(api, 'run_job', render)
    api.run_review_long_job(job.id, short)
    attempt = api.long_production_state()['attempts'][0]
    assert attempt['status'] == 'failed'
    assert attempt['long_story_review']['passed'] is False
    assert 'relevance' not in attempt


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


def test_qc_rejection_does_not_consume_daily_success_target(setup_long):
    short, run, _ = setup_long
    stamp = api.now_iso()
    rejected = short.model_copy(deep=True, update={'id': 'rejected'})
    rejected.request.clip_mode = 'highlight_5m'
    # A failed Long from another source must not consume today's success quota.
    rejected.request.url = 'https://www.youtube.com/watch?v=otherABC123'
    api.jobs[rejected.id] = rejected
    state = api.long_production_state()
    state.update(auto_qc_enabled=True, attempts=[dict(day=datetime.now(api.ZoneInfo('Asia/Jakarta')).date().isoformat(),
        job_id='rejected', short_job_id='old-short', status='completed', qc_decision='DROP_SOURCE')])
    api.save_long_production_state(state)
    assert api.queue_review_long_once()['status'] == 'queued'


@pytest.mark.parametrize('attempt_count,expected', [(1, 'queued'), (3, 'daily_attempt_limit')])
def test_deleted_unreviewable_long_releases_qc_wait_but_preserves_attempt_cap(setup_long, attempt_count, expected):
    day = datetime.now(api.ZoneInfo('Asia/Jakarta')).date().isoformat()
    state = api.long_production_state()
    state.update(auto_qc_enabled=True, attempts=[dict(day=day, job_id=f'old-{index}',
        short_job_id=f'old-short-{index}', status='completed', disposition='deleted_terminal_output',
        cleanup_reason='long_qc_unavailable_exhausted') for index in range(attempt_count)])
    api.save_long_production_state(state)
    assert api.queue_review_long_once()['status'] == expected
    assert all('qc_decision' not in row for row in api.long_production_state()['attempts'][:attempt_count])


def test_long_full_analysis_is_not_replaced_with_short_prefix(monkeypatch):
    monkeypatch.setattr(api, 'fetch_video_duration', lambda url: 7200)
    request = api.ClipJobRequest(url='https://www.youtube.com/watch?v=MtoYogBMyII',
        clip_mode='highlight_5m', ai_enabled=False)
    assert api.normalize_job_request(request).analyze_seconds is None
    short = request.model_copy(update={'clip_mode': 'short'})
    assert api.normalize_job_request(short).analyze_seconds == 1200
