from contextlib import nullcontext
from datetime import datetime,timedelta,timezone
import base64
import json
import io
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

import api
import facebook_activity as activity
import facebook_autopilot as policy
import facebook_browser as browser
import facebook_originals as originals
from facebook_api import Store
from facebook_runner import Runner


def moment(value='2026-11-16T20:00:00+07:00'):return datetime.fromisoformat(value)


def test_thirteen_reels_seven_stories_without_catchup_burst():
    monday=moment()
    rows=[slot for day in range(7) for slot in policy.slots(monday+timedelta(days=day))]
    assert sum(row['kind']=='reel' for row in rows)==13
    assert sum(row['kind']=='story' for row in rows)==7
    assert len({row['key'] for row in rows})==20
    assert all(row['day']=='2026-11-16' for row in policy.slots(monday))
    assert policy.eligible(monday,{'enabled':False},{},[]) is None
    first=policy.eligible(monday,{}, {},[])
    assert first['kind']=='reel'
    assert policy.eligible(monday,{}, {first['key']:{**first,'status':'rendering'}},[]) is None
    assert policy.eligible(monday,{}, {},[{'created_at':monday.isoformat(),'status':'completed'}]) is None


def test_local_week_and_counters_require_confirmed_remote_identity():
    current=moment('2026-11-15T18:30:00+00:00') # Monday in Jakarta.
    assert policy.week(current)==('2026-11-16','2026-11-22')
    uploads=[{'created_at':current.isoformat(),'kind':'reel','upload_confirmed':True,'video_url':'https://www.facebook.com/reel/123/'},
             {'created_at':current.isoformat(),'kind':'story','upload_confirmed':False,'video_url':None},
             {'created_at':current.isoformat(),'kind':'reel','upload_confirmed':True,'video_url':None}]
    result=policy.snapshot({}, {'a':{'week_start':'2026-11-16','status':'cancelled','job_id':'x'}},uploads,current=current)
    assert result['confirmed_posts']==1 and result['confirmed_stories']==0 and result['produced']==0
    assert result['activity'] is None


@pytest.mark.parametrize('value',[{'enabled':'false'},{'enabled':0},['enabled']])
def test_corrupt_settings_never_enable_automation(value):
    with pytest.raises(ValueError):policy.config(value)


def test_native_activity_does_not_infer_bonus_or_local_upload_credit():
    text='Minggu pada 15 Nov - 21 Nov\n6% selesai\nBuat 7 postingan publik baru\n0/7 selesai\nBuat 2 reel publik baru\n0/2 selesai\nDapatkan 10 pengikut baru\n0/10 pengikut\nDapatkan 900 tayangan lagi pada konten Anda\n58/900 selesai'
    result=activity.parse(text,account_verified=True)
    assert result['percent']==6 and len(result['tasks'])==4
    assert result['tasks'][-1]['completed']==58
    assert result['stories'] is None
    assert not activity.parse(text)['tasks']
    assert activity.parse('Buat 7 postingan publik baru\n1/13 selesai',account_verified=True)['tasks']==[]


def find_plan(topic):
    return next(plan for index in range(200) if (plan:=originals.plan(f'fixture-{index}'))['topic']==topic)


@pytest.mark.parametrize('topic',['group','rename','date','size','search','copy','restore','extension'])
def test_generated_visual_objects_match_the_scripted_operation(topic):
    plan=find_plan(topic)
    before=originals.state(plan,1);after=originals.state(plan,2)
    assert plan['synthetic_voice'] and not plan['third_party_footage'] and not plan['third_party_music']
    assert len(plan['stages'])==4
    assert not any(word in plan['caption'].lower() for word in ['http://','https://','sumber:','credit:'])
    if topic=='group':assert len(after[0])==1 and len(after[1])==2
    if topic=='rename':assert after[0][0]['label'].startswith('Catatan_2026-10-')
    if topic=='date':assert [r['label'] for r in after[0]]==sorted(r['label'] for r in after[0])
    if topic=='size':assert [r['size'] for r in after[0]]==[120,48,2]
    if topic=='search':assert len(after[0])==1 and len(originals.state(plan,3)[0])==3
    if topic=='copy':assert after[0]==after[1] and len(after[0])==1
    if topic=='restore':assert not after[0] and len(after[1])==1
    if topic=='extension':assert before[0][0]['label'].endswith('.txt') and after[0][0]['label'].endswith('.txt')


def test_missing_original_media_is_a_drop_not_an_automatic_pass(tmp_path):
    result=originals.audit(tmp_path/'missing.mp4','job','/outputs/missing.mp4')
    assert result['audit']['decision']=='DROP_SOURCE' and not result['audit']['upload_allowed']
    assert not originals.automatic_pass(tmp_path/'missing.mp4','job','/outputs/missing.mp4')


def test_story_identity_must_come_from_matching_create_actor():
    node={'data':{'story_create':{'story':{'actors':[{'id':'123'}],
          'id':base64.b64encode(b'S:_I:123:456').decode()}}}}
    assert browser.created_story_url(node,'123')=='https://www.facebook.com/stories/123/456/'
    assert browser.created_story_url(node,'999') is None
    assert browser.created_story_url({'data':{'story':node['data']['story_create']['story']}},'123') is None
    assert browser.story_url('https://evil.test/stories/123/456/','123') is None
    assert browser.story_url('https://www.facebook.com/stories/999/456/','123') is None


@pytest.fixture
def runner(tmp_path,monkeypatch):
    monkeypatch.setattr(api,'jobs',{})
    monkeypatch.setattr(api,'JOBS_PATH',tmp_path/'jobs.json')
    monkeypatch.setattr(api,'OUTPUTS_DIR',tmp_path/'outputs')
    store=Store(tmp_path/'facebook.json')
    slot=policy.slots(moment())[0]
    plan=originals.plan(slot['content_seed'])
    store.data.update(autopilot=policy.config(),autopilot_runs={slot['key']:{**slot,
        'job_id':'autojob','title':plan['title'],'status':'reserved','created_at':moment().isoformat()}})
    queued=[]
    runner=Runner(api,lambda:store,lambda:{'account_verified':True},
        lambda job,url,kind:queued.append((job,url,kind)) or {'id':'u','status':'queued'},lambda _:None,lambda:None)
    def render(plan,folder,progress):
        folder.mkdir(parents=True,exist_ok=True)
        path=folder/'facebook_original.mp4';path.write_bytes(b'fixture only')
        path.with_suffix('.json').write_text(json.dumps({'title':plan['title'],'facebook':{'caption':plan['caption']},
            'media_sha256':originals.qc.sha256(path)}))
        return path
    monkeypatch.setattr(originals,'render',render)
    monkeypatch.setattr(originals,'author',lambda plan,previous=():{**plan,'script_sha256':originals.script_identity(plan)})
    return runner,store,slot['key'],queued


def test_worker_does_not_mark_human_review_complete_or_upload_pending_qc(runner,monkeypatch):
    worker,store,key,queued=runner
    monkeypatch.setattr(originals,'audit',lambda *args,**kwargs:{'status':'pending','message':'AI offline','audit':None})
    worker.process(key)
    assert store.data['autopilot_runs'][key]['status']=='qc_wait'
    assert not queued and api.jobs['autojob'].status=='completed'
    assert api.jobs['autojob'].clips[0].is_correct is False
    assert store.data['autopilot_runs'][key]['rendered_at']


def test_exact_generated_pass_reaches_facebook_only_without_manual_click(runner,monkeypatch):
    worker,store,key,queued=runner
    monkeypatch.setattr(originals,'audit',lambda *args,**kwargs:{'status':'reviewed','audit':{'decision':'PASS_UPLOAD'}})
    monkeypatch.setattr(originals,'automatic_pass',lambda media,*args:media.with_suffix('.auto-qc.json').is_file())
    worker.process(key)
    assert queued and queued[0][2]=='reel'
    assert not api.jobs['autojob'].request.auto_upload_youtube
    assert not api.jobs['autojob'].clips[0].is_correct
    assert store.data['autopilot_runs'][key]['upload_id']=='u'


def test_requested_original_is_idempotent_and_never_reopens_dropped_source(runner):
    worker,store,key,_=runner
    store.data['autopilot_runs'][key]['status']='dropped'
    first=worker.request_original('a'*32,'group')
    store.data['autopilot_runs'][first['key']]['status']='dropped'
    repeated=worker.request_original('a'*32,'copy')
    assert repeated['job_id']==first['job_id'] and repeated['topic']=='group'
    assert repeated['status']=='dropped'
    assert first['content_seed']!=store.data['autopilot_runs'][key]['content_seed']


def test_requested_original_preserves_active_and_recent_upload_holds(runner):
    worker,store,key,_=runner
    with pytest.raises(ValueError,match='produksi'):worker.request_original('b'*32)
    store.data['autopilot_runs'][key]['status']='dropped'
    store.data['uploads']['existing']={'created_at':datetime.now(timezone.utc).isoformat()}
    with pytest.raises(ValueError,match='tiga jam'):worker.request_original('b'*32)
    assert 'requested:'+'b'*32 not in store.data['autopilot_runs']


def test_requested_worker_and_cron_cannot_process_the_same_request_twice(runner,monkeypatch):
    worker,store,key,_=runner
    calls=[]
    def process(k):
        calls.append(k);store.data['autopilot_runs'][k].update(status='completed',attempts=1)
    monkeypatch.setattr(worker,'process',process)
    worker.process_requested(key);worker.process_requested(key)
    assert calls==[key]


def test_startup_consumes_durable_operator_request_once_without_new_post_on_rebuild(runner,monkeypatch):
    worker,store,key,_=runner
    store.data['autopilot_runs'][key]['status']='dropped'
    pending=api.JOBS_PATH.parent/'facebook_requests';pending.mkdir()
    request=pending/('c'*32+'.json');request.write_text(json.dumps({'topic':'group'}))
    calls=[]
    def process(k):
        calls.append(k);store.data['autopilot_runs'][k].update(status='completed',attempts=1)
    monkeypatch.setattr(worker,'process',process)
    worker.consume_requested();assert not request.exists()
    request.write_text(json.dumps({'topic':'group'}))
    worker.consume_requested()
    assert calls==['requested:'+'c'*32] and not request.exists()


def test_pending_operator_request_stays_on_disk_while_another_production_is_active(runner):
    worker,_,_,_=runner
    pending=api.JOBS_PATH.parent/'facebook_requests';pending.mkdir()
    request=pending/('d'*32+'.json');request.write_text(json.dumps({'topic':'group'}))
    worker.consume_requested();assert request.exists()


def test_requested_original_respects_shared_production_capacity(runner):
    worker,store,key,_=runner
    store.data['autopilot_runs'][key]['status']='dropped'
    api.jobs.update(one=SimpleNamespace(status='running'),two=SimpleNamespace(status='queued'))
    with pytest.raises(ValueError,match='kapasitas'):worker.request_original('e'*32,'group')


def test_original_endpoint_validates_identity_and_uses_owned_worker(monkeypatch):
    calls=[]
    monkeypatch.setattr(Runner,'request_original',lambda self,request,topic,series=None,custom_topic=None,style=None:
        calls.append((request,topic,series,custom_topic,style)) or {'key':'requested:'+request,'status':'reserved'})
    import facebook_api
    monkeypatch.setattr(facebook_api,'start_background',lambda *args:None)
    client=TestClient(api.app)
    assert client.post('/api/facebook/originals',json={'request_id':'../invalid'}).status_code==422
    result=client.post('/api/facebook/originals',json={'request_id':'a'*32,'topic':'group'})
    assert result.status_code==200 and calls==[('a'*32,'group',None,None,None)]
    result=client.post('/api/facebook/originals',json={'request_id':'b'*32,'custom_topic':'Kebun','style':'story'})
    assert result.status_code==200 and calls[-1]==('b'*32,None,None,'Kebun','story')


def test_facebook_model_override_keeps_shared_credentials_and_long_model(monkeypatch,tmp_path):
    shared={'base_url':'http://localhost:9999','model':'long-model','api_key':'fixture-key',
        'media_export_authorized':True,'audio_review_mode':'local_whisper'}
    monkeypatch.setattr(originals.qc,'provider_config',lambda:shared)
    path=tmp_path/'fb-model.json';path.write_text(json.dumps({'model':'facebook-model'}))
    monkeypatch.setattr(originals,'PROVIDER_CONFIG_PATH',path)
    facebook=originals.provider_config()
    assert facebook['model']=='facebook-model' and shared['model']=='long-model'
    assert {k:v for k,v in facebook.items() if k not in {'model','max_output_tokens'}}=={k:v for k,v in shared.items() if k!='model'}
    assert facebook['max_output_tokens']==4096
    media=tmp_path/'sample.mp4';media.write_bytes(b'identity fixture')
    assert originals.audit_fingerprint(media,{})!=originals.qc.fingerprint(media,{})


def test_terminal_provider_refusal_is_not_resubmitted_after_model_change(monkeypatch,tmp_path):
    media=tmp_path/'rejected.mp4'
    saved={'provider_http_status':422,'status':'reviewed','audit':{'decision':'DROP_SOURCE',
        'hard_gates':{'context_safe':False},'source_job_id':'old','source_clip_url':'old'}}
    media.with_suffix('.auto-qc.json').write_text(json.dumps(saved))
    monkeypatch.setattr(originals,'provider_config',lambda:pytest.fail('Rejected source must not reach another model'))
    assert originals.audit(media,'changed-job','changed-url')==saved


def test_audio_recognition_cache_is_bound_to_encoded_media_captions_and_windows(monkeypatch,tmp_path):
    media=tmp_path/'review.mp4';media.write_bytes(b'encoded output')
    srt=media.with_suffix('.srt');srt.write_text('actual captions')
    windows=[{'start_seconds':0.,'duration_seconds':3.,'data':'fixture'}];calls=[]
    evidence=[{'recognized_text':'Actual words','caption_overlap_f1':1.,
        'method':'local_whisper_medium_cpu_int8_actual_output_audio'}]
    monkeypatch.setattr(originals.qc,'local_audio_evidence',lambda *args:calls.append(args) or evidence)
    assert originals.local_audio_review_cached(media,windows,srt.read_text())==evidence
    assert originals.local_audio_review_cached(media,windows,srt.read_text())==evidence
    assert len(calls)==1
    media.write_bytes(b'changed output');originals.local_audio_review_cached(media,windows,srt.read_text())
    srt.write_text('changed captions');originals.local_audio_review_cached(media,windows,srt.read_text())
    windows[0]['duration_seconds']=4.;originals.local_audio_review_cached(media,windows,srt.read_text())
    assert len(calls)==4


def test_facebook_qc_output_budget_is_explicit_and_never_accepts_empty_review(monkeypatch):
    captured=[]
    def response(request,**kwargs):
        captured.append(json.loads(request.data))
        return io.StringIO(json.dumps({'choices':[{'finish_reason':'length','message':{'content':None}}]}))
    monkeypatch.setattr(originals.qc.urllib.request,'urlopen',response)
    config={'base_url':'http://127.0.0.1:9999','model':'fixture','api_key':'',
        'audio_review_mode':'local_whisper','max_output_tokens':16384}
    with pytest.raises(ConnectionError,match='finish_reason=length'):
        originals.qc.vision_review({},[],config=config)
    assert captured[0]['max_tokens']==16384


def test_stopped_autopilot_does_not_render_or_enqueue(runner,monkeypatch):
    worker,store,key,queued=runner
    store.data['autopilot']['enabled']=False
    cleanups=[]
    worker.cleanup=lambda:cleanups.append(True)
    monkeypatch.setattr(worker,'process',lambda _:pytest.fail('No production while paused'))
    worker.tick()
    assert not queued and worker.state()['runtime_state']=='paused'
    assert cleanups==[True]  # Confirmed local artifacts still clean while paused.


def test_api_exposes_dedicated_state_and_preserves_native_progress(tmp_path,monkeypatch):
    monkeypatch.setattr(api,'JOBS_PATH',tmp_path/'jobs.json')
    client=TestClient(api.app)
    assert client.get('/api/facebook/config').json()['autopilot_version']==1
    assert client.post('/api/facebook/autopilot',json={'enabled':False}).status_code==200
    state=client.get('/api/facebook/autopilot').json()
    assert state['runtime_state']=='paused' and not state['scheduler_running']
    assert state['confirmed_posts']==0 and state['activity'] is None
    stored=json.loads((tmp_path/'facebook_workspace.json').read_text())
    assert stored['autopilot']['enabled'] is False


def test_author_outage_never_recycles_an_already_used_script(monkeypatch):
    monkeypatch.setattr(originals.qc,'provider_config',lambda:{'base_url':'','model':''})
    plan=originals.plan('fresh-script-fixture')
    first=originals.author(plan,[])
    with pytest.raises(ValueError,match='identik'):
        originals.author(originals.plan('fresh-script-fixture'),[first['script_sha256']])


def test_empty_provider_response_is_retryable_without_guessing_a_pass(monkeypatch):
    monkeypatch.setattr(originals.qc,'provider_config',lambda:{'base_url':'http://127.0.0.1:9999',
        'model':'fixture','api_key':'','media_export_authorized':False})
    monkeypatch.setattr(originals.qc.urllib.request,'urlopen',lambda *args,**kwargs:
        io.StringIO(json.dumps({'choices':[{'message':{'content':None}}]})))
    with pytest.raises(ConnectionError,match='empty review'):
        originals.qc.vision_review({'target_platform':'facebook','original_demo':True},[])


def test_dropped_source_is_retired_and_concise_audit_is_preserved(runner,monkeypatch):
    worker,store,key,queued=runner
    monkeypatch.setattr(originals,'audit',lambda *args,**kwargs:{'status':'reviewed','audit':
        {'decision':'DROP_SOURCE','evidence':['Incomplete simulated action at 12 seconds.']}})
    worker.process(key)
    assert store.data['autopilot_runs'][key]['status']=='dropped'
    assert store.data['autopilot_runs'][key]['qc_evidence']
    assert not queued and api.jobs['autojob'].clips==[]
    assert not (api.OUTPUTS_DIR/'facebook_autopilot/autojob').exists()


def test_manual_checkbox_cannot_bypass_generated_content_independent_qc(runner,monkeypatch):
    worker,store,key,queued=runner
    monkeypatch.setattr(originals,'audit',lambda *args,**kwargs:{'status':'pending','audit':None})
    worker.process(key)
    job=api.jobs['autojob']
    api.jobs[job.id]=job.model_copy(update={'clips':[job.clips[0].model_copy(update={'is_correct':True})]})
    result=TestClient(api.app).post('/api/facebook/qc',json={'job_id':job.id,'clip_url':job.clips[0].url})
    assert result.status_code==200
    assert result.json()['decision']=='HOLD'
    assert any('QC independen' in issue for issue in result.json()['issues'])


def test_ambiguous_post_is_reconciled_read_only_without_retrying_post(runner,monkeypatch):
    worker,store,key,queued=runner
    store.data['autopilot_runs'][key].update(upload_id='u',status='needs_review')
    url='https://www.facebook.com/reel/123/'
    store.data['uploads']['u']=dict(id='u',status='needs_review',submission_started=True,
        upload_confirmed=False,candidate_video_urls=[url],created_at=moment().isoformat())
    calls=[]
    def reconcile(identifier,candidate):
        calls.append((identifier,candidate))
        store.data['uploads'][identifier].update(status='completed',upload_confirmed=True,video_url=candidate)
    worker.reconcile=reconcile
    worker.retry=lambda _:pytest.fail('Ambiguous Post must never be retried')
    worker.tick();worker.synchronize()
    assert calls==[('u',url)] and not queued
    assert store.data['autopilot_runs'][key]['status']=='completed'


def bonus_snapshot(current):
    return dict(account_verified=True,checked_at=current.isoformat(),bonus=dict(amount_usd=1,
        required_reels=3,completed_reels=0,minimum_duration_seconds=10,minimum_qualified_views=10,
        minimum_reels_with_qualified_views=1,period_label='12 Nov - 19 Nov',awarded=False))


def test_bonus_reels_precede_story_without_a_same_day_posting_burst():
    current=moment('2026-11-15T17:00:00+07:00')
    native=bonus_snapshot(current)
    rows=policy.slots(current,bonus_priority=True)
    assert len(rows)==2 and all(row['kind']=='reel' for row in rows)
    runs={rows[0]['key']:{**rows[0],'status':'completed'}}
    # The Story at 15:00 is deferred, and the second Reel is not due until 18:30.
    assert policy.eligible(current,{},runs,[],monetization=native) is None
    later=current+timedelta(hours=2)
    assert policy.eligible(later,{},runs,[],monetization=native)['kind']=='reel'


def test_three_local_reels_never_mark_bonus_awarded_or_views_qualified():
    current=moment('2026-11-16T20:00:00+07:00')
    native=bonus_snapshot(current)
    uploads=[dict(kind='reel',upload_confirmed=True,video_url=f'https://www.facebook.com/reel/{i}/',
        created_at=current.isoformat(),duration_seconds=30) for i in range(3)]
    result=policy.bonus_plan(native,uploads,current)
    assert result['locally_confirmed_reels']==3
    assert result['facebook_completed_reels']==0 and not result['awarded']
    assert not result['priority'] and result['state']=='await_facebook_confirmation'


def test_stories_and_unknown_duration_do_not_count_toward_reel_bonus():
    current=moment();native=bonus_snapshot(current)
    uploads=[dict(kind='story',upload_confirmed=True,video_url='https://www.facebook.com/stories/1/2/',created_at=current.isoformat(),duration_seconds=30),
             dict(kind='reel',upload_confirmed=True,video_url='https://www.facebook.com/reel/3/',created_at=current.isoformat())]
    result=policy.bonus_plan(native,uploads,current)
    assert result['locally_confirmed_reels']==0 and result['priority']


def test_expired_or_stale_bonus_is_never_presented_as_an_active_priority():
    current=moment();native=bonus_snapshot(current)
    assert not policy.bonus_plan(native,[],current+timedelta(days=5))['priority']
    native['checked_at']=(current-timedelta(days=2)).isoformat()
    assert policy.bonus_plan(native,[],current)['state']=='refresh_required'


def test_requested_education_series_reaches_owned_worker_without_replacing_qc_or_schedule(runner,monkeypatch):
    worker,store,key,queued=runner
    store.data['autopilot_runs'][key]['status']='dropped'
    record=worker.request_original('f'*32,'count_objects','kids_basics')
    assert record['series']=='kids_basics'
    repeated=worker.request_original('f'*32,'plant_growth','nature')
    assert repeated['job_id']==record['job_id'] and repeated['series']=='kids_basics'
    monkeypatch.setattr(originals,'audit',lambda *a,**k:dict(status='pending',message='QC unavailable',audit=None))
    worker.process(record['key'])
    saved=store.data['autopilot_runs'][record['key']]
    assert saved['authored_plan']['series']=='kids_basics'
    assert saved['authored_plan']['education']['original_characters']
    assert saved['status']=='qc_wait' and not queued
    assert not api.jobs[record['job_id']].clips[0].is_correct
    assert store.data['autopilot'].get('series','digital')=='digital'


def test_saved_series_is_used_for_a_new_request_and_cross_series_topics_are_rejected(runner):
    worker,store,key,_=runner
    store.data['autopilot_runs'][key]['status']='dropped'
    store.data['autopilot']['series']='nature'
    with pytest.raises(ValueError,match='Topik'):worker.request_original('a'*32,'group')
    with pytest.raises(ValueError,match='Seri'):worker.request_original('b'*32,series='unknown')
    record=worker.request_original('c'*32)
    assert record['series']=='nature' and record['topic'] in {'plant_growth','shadow_light'}
