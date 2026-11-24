from datetime import datetime,timedelta,timezone
import io
import json
from urllib.error import HTTPError

import pytest
import facebook_recovery as recovery
import facebook_originals as originals
import facebook_autopilot as policy
from test_facebook_autopilot import runner


NOW=datetime(2026,11,24,7,tzinfo=timezone.utc)


@pytest.mark.parametrize('header,expected',[('120',120),('-1',0),('NaN',0),('Infinity',0),('999999',86400),('bad',0)])
def test_retry_after_is_finite_and_bounded(header,expected):
    assert recovery.retry_after_seconds({'Retry-After':header})==expected


def test_qc_quiet_period_and_provider_retry_after_survive_restart():
    changes=recovery.qc_wait_changes({'qc_attempts':2},{'retry_after_seconds':1800},NOW)
    assert not recovery.qc_due(changes,NOW+timedelta(seconds=1799))
    assert recovery.qc_due(changes,NOW+timedelta(seconds=1800))
    assert recovery.qc_wait_changes({'qc_attempts':99},{},NOW)['next_qc_at']==(NOW+timedelta(hours=6)).isoformat()
    assert not recovery.qc_due({'next_qc_at':'corrupt'},NOW)


def providers(monkeypatch):
    primary=dict(model='facebook-configured',base_url='https://same-project-provider',api_key='private',
        media_export_authorized=True,audio_review_mode='local_whisper')
    monkeypatch.setattr(originals,'provider_config',lambda:dict(primary))
    monkeypatch.setattr(originals.qc,'provider_config',lambda:{**primary,'model':'shared-configured'})
    return primary


def test_rate_limit_switches_once_to_configured_same_endpoint_without_mutating_settings(monkeypatch):
    primary=providers(monkeypatch);calls=[]
    def review(evidence,frames,*,config):
        calls.append(dict(config))
        if len(calls)==1:raise HTTPError('url',429,'limited',{},io.BytesIO(b''))
        return {'decision':'REPAIR_ONCE'}
    monkeypatch.setattr(originals.qc,'vision_review',review)
    result,config=originals.review_with_recovery({},[])
    assert result['decision']=='REPAIR_ONCE' and config['model']=='shared-configured'
    assert [c['model'] for c in calls]==['facebook-configured','shared-configured']
    assert all(c['base_url']==primary['base_url'] and c['api_key']==primary['api_key'] for c in calls)
    assert originals.provider_config()['model']=='facebook-configured'


@pytest.mark.parametrize('code',[400,401,403,422])
def test_auth_or_safety_rejection_never_tries_another_model(monkeypatch,code):
    providers(monkeypatch);calls=[]
    def review(*args,**kwargs):calls.append(1);raise HTTPError('url',code,'refused',{},io.BytesIO(b''))
    monkeypatch.setattr(originals.qc,'vision_review',review)
    with pytest.raises(HTTPError):originals.review_with_recovery({},[])
    assert len(calls)==1


def test_no_new_endpoint_or_unconfigured_model_can_be_selected(monkeypatch):
    primary=providers(monkeypatch)
    monkeypatch.setattr(originals.qc,'provider_config',lambda:{**primary,'base_url':'https://different','model':'other'})
    assert originals.recovery_providers()==[primary]


def test_fallback_qc_pass_still_requires_exact_media_and_current_configured_model(monkeypatch,tmp_path):
    providers(monkeypatch)
    media=tmp_path/'clip.mp4';media.write_bytes(b'audited encoded fixture')
    source=tmp_path/'source-plan.json';source.write_text('{}')
    media.with_suffix('.json').write_text(json.dumps({'render_source_sha256':originals.qc.sha256(source)}))
    context=dict(source_job_id='job',source_clip_url='/clip.mp4',repair_attempted=False,score_floor_met=True)
    provider=originals.recovery_providers()[1]
    audit={**context,'decision':'PASS_UPLOAD','upload_allowed':True,'confidence':.95,
        'hard_gates':dict.fromkeys(originals.qc.GATES,True),'ai_checks':dict.fromkeys(originals.qc.CHECKS,True)}
    record=dict(provider_model=provider['model'],media_sha256=originals.qc.sha256(media),audit=audit,
        fingerprint=originals.audit_fingerprint(media,context,provider=provider))
    path=media.with_suffix('.auto-qc.json');path.write_text(json.dumps(record))
    assert originals.automatic_pass(media,'job','/clip.mp4')
    record['provider_model']='unconfigured-model';path.write_text(json.dumps(record))
    assert not originals.automatic_pass(media,'job','/clip.mp4')
    record['provider_model']=provider['model'];path.write_text(json.dumps(record))
    media.write_bytes(b'changed encoded fixture')
    assert not originals.automatic_pass(media,'job','/clip.mp4')


def story(**changes):
    return dict(id='same-id',kind='story',status='failed',attempts=3,submission_started=False,
        upload_confirmed=False,created_at=(NOW-timedelta(days=2)).isoformat(),
        message='Audiens publik Story belum terbukti; ditahan sebelum Bagikan.',**changes)


def test_expired_story_is_skipped_only_with_pre_submission_proof():
    row=story()
    assert recovery.upload_plan(row,NOW)=='skip_expired_story'
    for key in ('submission_started','video_url','remote_story_url'):
        assert recovery.upload_plan({**row,key:True},NOW)=='verify_remote'
    assert recovery.upload_plan({**row,'upload_confirmed':True},NOW)=='none'
    assert recovery.upload_plan({**row,'status':'needs_review'},NOW)=='verify_remote'
    assert recovery.upload_plan({**row,'submission_started':None},NOW)=='inspect_failure'
    assert recovery.upload_plan({**row,'created_at':NOW.isoformat()},NOW)=='wait_story_audience'


def test_retry_budget_unknown_errors_and_possible_posts_never_get_transfer_retry():
    row=story();row['message']='network timed out'
    assert recovery.upload_plan(row,NOW)=='retry_exhausted'
    row['attempts']=2
    assert recovery.upload_plan(row,NOW)=='retry_transfer'
    row['message']='unknown error'
    assert recovery.upload_plan(row,NOW)=='inspect_failure'
    row['submission_started']=True
    assert recovery.upload_plan(row,NOW)=='verify_remote'


def test_all_uploads_are_examined_without_autopilot_run_and_preserve_remote_identity(runner):
    worker,store,key,queued=runner
    row=story();row['created_at']='2020-01-01T00:00:00+00:00'
    store.data['uploads'][row['id']]=dict(row)
    worker.recover_uploads()
    saved=store.data['uploads'][row['id']]
    assert saved['recovery_status']=='skipped' and saved['recovery_action']=='skip_expired_story'
    assert all(saved[k]==v for k,v in row.items())
    assert saved['attempts']==3 and not queued
    assert worker.recover_uploads() is False


def test_manual_ambiguous_post_uses_exact_remote_candidate_and_keeps_retry_budget(runner):
    worker,store,key,_=runner
    row=story();row.update(status='needs_review',submission_started=True,
        remote_story_url='https://www.facebook.com/stories/123/456/')
    store.data['uploads'][row['id']]=dict(row)
    verified=[]
    worker.reconcile=lambda identifier,url:verified.append((identifier,url))
    worker.retry=lambda *args:pytest.fail('Never replay an uncertain Post')
    assert worker.recover_uploads() is True
    assert verified==[(row['id'],row['remote_story_url'])]
    assert store.data['uploads'][row['id']]['attempts']==3
    assert worker.recover_uploads() is False


def test_failed_retry_dispatch_has_its_own_durable_cooldown(runner):
    worker,store,key,_=runner
    row=story();row.update(attempts=1,message='network timed out',finished_at='2020-01-01T00:00:00+00:00')
    store.data['uploads'][row['id']]=dict(row)
    calls=[]
    def unavailable(identifier):calls.append(identifier);raise ConnectionError('session check unavailable')
    worker.retry=unavailable
    with pytest.raises(ConnectionError):worker.recover_uploads()
    assert worker.recover_uploads() is False and calls==[row['id']]
    assert store.data['uploads'][row['id']]['attempts']==1


def test_autonomous_recovery_never_runs_while_paused(runner,monkeypatch):
    worker,store,key,queued=runner
    store.data['autopilot']['enabled']=False
    monkeypatch.setattr(worker,'recover_uploads',lambda:pytest.fail('Paused recovery'))
    worker.tick()
    assert not queued


def test_qc_pending_keeps_render_and_uses_persisted_backoff(runner,monkeypatch):
    worker,store,key,queued=runner
    monkeypatch.setattr(originals,'audit',lambda *a,**kw:dict(status='pending',audit=None,
        provider_http_status=429,retry_after_seconds=7200))
    worker.process(key)
    row=store.data['autopilot_runs'][key]
    assert row['status']=='qc_wait' and row['qc_attempts']==1
    assert not recovery.qc_due(row) and row['recovery_action']=='retry_qc_with_backoff'
    assert (worker.api.OUTPUTS_DIR/'facebook_autopilot'/row['job_id']/'facebook_original.mp4').exists()
    assert not queued


def test_interrupted_qc_does_not_ignore_persisted_quiet_period(runner,monkeypatch):
    worker,store,key,_=runner
    store.data['autopilot_runs'][key].update(status='qc',
        next_qc_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())
    store.data['session']={'account_verified':True,'checked_at':datetime.now(timezone.utc).isoformat()}
    store.data['activity_attempt_at']=datetime.now(timezone.utc).isoformat()
    store.data['autopilot_monetization_attempt_at']=datetime.now(timezone.utc).isoformat()
    monkeypatch.setattr(worker,'process',lambda *args:pytest.fail('QC lease must survive restart'))
    worker.tick()


def test_independent_story_lane_does_not_bypass_reel_qc_or_make_repeated_reels():
    current=datetime(2026,11,24,20,tzinfo=policy.ZONE)
    pending={'held':dict(status='qc_wait',kind='reel')}
    result=policy.eligible(current,{},pending,[])
    assert result['kind']=='story'
    assert policy.eligible(current,{},pending,[],blocked_kinds={'story'}) is None
    assert policy.eligible(current,{}, {'busy':dict(status='rendering',kind='reel')},[]) is None


def test_story_probe_cache_is_account_specific_and_never_changes_privacy(runner,monkeypatch):
    import facebook_browser as browser
    worker,store,key,_=runner
    from contextlib import nullcontext
    store.data['session']={'verified_profile_id':'expected'}
    monkeypatch.setattr(worker.api,'social_upload_turn',nullcontext)
    calls=[]
    monkeypatch.setattr(browser,'probe_story_audience',lambda profile:calls.append(profile) or True)
    assert worker.story_lane_ready() and worker.story_lane_ready()
    assert calls==['expected']
    store.data['session']['verified_profile_id']='other'
    assert worker.story_lane_ready() and calls==['expected','other']


def test_choose_topic_takes_ordered_recent_styles():
    import facebook_stories as stories
    styles=[row['style'] for row in stories.DEFAULT_TOPICS[:3]]
    picked=stories.choose_topic('seed',(),styles)
    assert picked['text'] and picked['style'] not in styles


def test_topic_series_request_accepts_recent_styles_without_type_error(runner):
    import facebook_stories as stories
    worker,store,key,_=runner
    store.data['autopilot_runs'][key]['status']='dropped'
    store.data['autopilot_runs'][key]['custom_topic']='Topik lama'
    store.data['autopilot_runs'][key]['style']=stories.DEFAULT_TOPICS[0]['style']
    row=worker.request_original('f'*32,series=stories.SERIES_KEY)
    assert row['key']=='requested:'+'f'*32
    assert store.data['autopilot_runs'][row['key']]['custom_topic'] in {
        item['text'] for item in stories.DEFAULT_TOPICS}


def test_skipped_expired_story_does_not_block_future_story_slot(runner,monkeypatch):
    worker,store,key,_=runner
    current=datetime.now(timezone.utc).isoformat()
    store.data['autopilot_runs'][key]['status']='dropped'
    store.data['session']={'account_verified':True,'checked_at':current}
    store.data['activity_attempt_at']=current
    store.data['autopilot_monetization_attempt_at']=current
    store.data['uploads']={'old':dict(id='old',kind='story',status='failed',upload_confirmed=False,
        message='Audiens publik Story belum terbukti; pengiriman ditahan.',
        recovery_status='skipped',recovery_action='skip_expired_story')}
    monkeypatch.setattr(worker,'story_lane_ready',lambda:False)
    seen=[]
    monkeypatch.setattr(policy,'eligible',lambda *args,**kwargs:seen.append(kwargs.get('blocked_kinds')) or None)
    worker.tick()
    assert seen and seen[-1]==set()
