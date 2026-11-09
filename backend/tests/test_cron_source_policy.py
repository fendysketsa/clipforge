from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace as NS

import pytest
import api
import cron_source_policy as policy

URL='https://www.youtube.com/watch?v=abcDEF12345'


@pytest.fixture(autouse=True)
def isolated_sources(monkeypatch):
    monkeypatch.setattr(api,'source_usage_history',{})
    monkeypatch.setattr(api,'processed_source_history',set())
    monkeypatch.setattr(api,'SOURCE_USAGE_ARCHIVE_DIR_OVERRIDE','')


def job(key, *, status='completed', review=False, started=True, cron=True):
    old=(datetime.now(timezone.utc)-timedelta(days=90)).isoformat()
    return api.ClipJob(id=key,status=status,created_at=old,updated_at=old,started_at=old if started else None,
        request=api.ClipJobRequest(url=URL,review_only=review,scheduled_director_effects=cron))


def test_second_process_allowed_third_blocked_and_same_job_resume_idempotent(tmp_path):
    path=tmp_path/'ledger.json'
    policy.merge_attempts(path,{},source=URL,job_id='first',enforce=True)
    policy.merge_attempts(path,{},source=URL,job_id='second',enforce=True)
    assert len(policy.merge_attempts(path,{},source=URL,job_id='second',enforce=True)[URL])==2
    with pytest.raises(policy.SourceProcessLimitReached):
        policy.merge_attempts(path,{},source=URL,job_id='third',enforce=True)
    assert json.loads(path.read_text())[URL]==['first','second']


def test_concurrent_last_slot_admits_only_one_new_processing_job(tmp_path):
    path=tmp_path/'ledger.json'
    policy.merge_attempts(path,{},source=URL,job_id='first')
    def reserve(key):
        try:
            policy.merge_attempts(path,{},source=URL,job_id=key,enforce=True)
            return 'admitted'
        except policy.SourceProcessLimitReached:return 'skipped'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reserve,['second','third']))==['admitted','skipped']


@pytest.mark.parametrize('raw',['{','[]','{"url": 2}','{"url": [null]}'])
def test_corrupt_ledger_does_not_reset_the_limit(tmp_path,raw):
    path=tmp_path/'ledger.json';path.write_text(raw)
    with pytest.raises(RuntimeError):policy.merge_attempts(path,{})
    assert path.read_text()==raw


def test_old_sources_at_cap_do_not_reenter_after_cooldown_or_card_deletion(monkeypatch):
    monkeypatch.setattr(api,'jobs',{'first':job('first'),'second':job('second')})
    assert URL in api.recently_processed_job_source_urls(7)
    monkeypatch.setattr(api,'jobs',{})
    assert URL in api.recently_processed_job_source_urls(7)


def test_same_job_in_usage_jobs_and_campaign_is_counted_once(monkeypatch):
    monkeypatch.setattr(api,'jobs',{'first':job('first')})
    monkeypatch.setattr(api,'source_usage_history',{URL:{'events':[dict(job_id='first',clip_count=1)]}})
    monkeypatch.setattr(api,'auto_viral_runs',{'run':NS(processed=[dict(url=URL,job_id='first',job_status='completed')])})
    assert api.source_processing_counts()[URL]==1


def test_failed_attempts_survive_cleanup_and_url_aliases_are_unified(monkeypatch):
    req=api.ClipJobRequest(url='https://youtu.be/abcDEF12345?t=10',scheduled_director_effects=True)
    api.remember_source_processing_attempt('failed-first',req)
    api.remember_source_processing_attempt('failed-second',req)
    assert api.cron_source_process_limit_reached(URL+'&list=PLAYLIST')
    with pytest.raises(policy.SourceProcessLimitReached):api.remember_source_processing_attempt('third',req)


def test_review_and_unstarted_cancelled_jobs_are_not_consumed(monkeypatch):
    cancelled=job('cancelled',status='cancelled')
    cancelled.error='Proses dibatalkan sebelum worker berjalan.'
    monkeypatch.setattr(api,'jobs',{'review':job('review',review=True),'queued':job('queued',status='queued',started=False),'cancelled':cancelled})
    assert api.source_processing_counts().get(URL,0)==0


def test_legacy_monthly_archives_bootstrap_before_display_history_is_pruned(tmp_path):
    path=api.source_usage_archive_root()/'2025'/'01'/'source_usage.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'items':[dict(job_id=key,source_url=URL,clip_count=1) for key in ['first','second']]}))
    assert api.cron_source_process_limit_reached(URL)
    path.unlink()
    assert api.cron_source_process_limit_reached(URL)


def test_manual_processing_can_be_explicit_while_cron_still_skips(monkeypatch):
    req=api.ClipJobRequest(url=URL)
    for key in ['first','second','manual-third']:api.remember_source_processing_attempt(key,req)
    assert api.source_processing_counts()[URL]==3
    monkeypatch.setattr(api,'save_jobs_unlocked',lambda:None)
    with pytest.raises(policy.SourceProcessLimitReached):
        api.queue_auto_viral_clip_job(req.model_copy(update={'scheduled_director_effects':True}))
    assert api.queue_auto_viral_clip_job(req).status=='queued'


def test_queued_legacy_cron_cannot_bypass_worker_start_gate(monkeypatch):
    req=api.ClipJobRequest(url=URL,scheduled_public_source_credit=True)
    for key in ['first','second']:api.remember_source_processing_attempt(key,req)
    queued=job('third',status='queued',started=False)
    queued.request=req
    monkeypatch.setattr(api,'jobs',{'third':queued})
    monkeypatch.setattr(api,'save_jobs_unlocked',lambda:None)
    monkeypatch.setattr(api,'ensure_python_subprocess_integrity',lambda:False)
    monkeypatch.setattr(api,'build_clipper_command',lambda *a:['python','unused.py'])
    monkeypatch.setattr(api,'cleanup_failed_job_artifacts',lambda *a:(0,'clean'))
    monkeypatch.setattr(api,'discard_failed_targeted_repair_job',lambda *a:False)
    monkeypatch.setattr(api.subprocess,'Popen',lambda *a,**k:pytest.fail('Source at cap must not start a subprocess'))
    api.run_job('third')
    assert api.jobs['third'].status=='cancelled' and api.jobs['third'].error is None
    assert api.jobs['third'].progress_stage=='skipped_source_limit'
    assert api.source_processing_counts()[URL]==2


def test_campaign_skips_capped_candidate_and_processes_next_source(monkeypatch):
    req=api.ClipJobRequest(url=URL)
    for key in ['first','second']:api.remember_source_processing_attempt(key,req)
    other='https://www.youtube.com/watch?v=otherABC123'
    run=api.AutoViralRun(id='run',status='queued',trigger='schedule',created_at=api.now_iso(),updated_at=api.now_iso(),
        request=api.AutoViralRequest(video_count=1,auto_upload_youtube=False,auto_upload_tiktok=False,create_paired_long_video=False))
    api.auto_viral_runs[run.id]=run
    finished=job('other')
    finished.request.url=other
    finished.clips=[api.ClipFile(name='clip.mp4',url='/outputs/other/clip.mp4',size_bytes=10)]
    selected=[]
    monkeypatch.setattr(api,'save_auto_viral_runs_unlocked',lambda:None)
    monkeypatch.setattr(api,'discover_auto_viral_campaign_sources',lambda *a:[dict(url=URL,title='Capped'),dict(url=other,title='Fresh')])
    def create(source,*a):
        selected.append(source['url']);api.jobs[finished.id]=finished;return finished
    monkeypatch.setattr(api,'create_auto_viral_clip_job',create)
    monkeypatch.setattr(api,'run_clip_job_with_campaign_progress',lambda *a:None)
    api.run_auto_viral_campaign(run.id)
    assert selected==[other]
    assert api.auto_viral_runs[run.id].status=='completed'
    assert any('batas dua proses' in text for text in api.auto_viral_runs[run.id].logs)
