from contextlib import nullcontext
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

import api
import clipper
import facebook_api
import facebook_browser
import facebook_strategy as strategy
from llm import AIConfig


@pytest.fixture
def client():
    # Do not start production schedulers or recovery threads in unit tests.
    return TestClient(api.app)


def media(duration=30, **changes):
    video = {'codec_type':'video', 'codec_name':'h264', 'width':1080, 'height':1920, **changes}
    return {'format':{'duration':duration}, 'streams':[video, {'codec_type':'audio','codec_name':'aac'}]}


def test_facebook_policy_overrides_youtube_and_long_defaults(monkeypatch):
    monkeypatch.setenv('YOUTUBE_CHANNEL_RECOVERY_MODE','true')
    request = api.ClipJobRequest(target_platform='facebook', max_duration=180, top=40,
        clip_mode='highlight_5m', auto_upload_youtube=True, burn_subtitles=False, slow_motion_no_voice=True)
    assert (request.clip_mode,request.max_duration,request.min_duration,request.top)==('short',55,25,3)
    assert request.burn_subtitles and not request.auto_upload_youtube and not request.slow_motion_no_voice
    assert not request.auto_blur_watermarks


def test_worker_profile_is_isolated_and_disables_third_party_audio(monkeypatch):
    monkeypatch.setenv('CLIPFORGE_FACEBOOK_NICHE','digital_simple')
    normal = api.clipper_worker_environment(api.ClipJobRequest())
    facebook = api.clipper_worker_environment(api.ClipJobRequest(target_platform='facebook'))
    assert 'CLIPFORGE_FACEBOOK_NICHE' not in normal
    assert facebook['CLIPFORGE_FACEBOOK_NICHE']=='tech_daily'
    assert facebook['SHORTS_ALLOW_THIRD_PARTY_MUSIC']=='false'
    assert facebook['QURAN_OUTRO_ENABLED']=='false'
    assert api.os.environ['CLIPFORGE_FACEBOOK_NICHE']=='digital_simple'


def test_facebook_never_expands_beyond_requested_duration(monkeypatch):
    monkeypatch.setenv('CLIPFORGE_FACEBOOK_NICHE','tech_daily')
    assert clipper.short_auto_expand_max_duration(38)==38
    assert clipper.short_auto_expand_max_duration(55)==55
    assert clipper.short_auto_expand_max_duration(180)==55


@pytest.mark.parametrize('duration',[55.01,56,180,0,'NaN','Infinity',None,'oops'])
def test_encoded_duration_rejects_invalid_and_overlong_media(duration):
    assert strategy.media_issues(media(duration))


def test_media_requires_portrait_h264_audio():
    assert strategy.media_issues(media())==[]
    assert strategy.media_issues(media(width=1920,height=1080))
    assert strategy.media_issues(media(codec_name='hevc'))
    value=media();value['streams']=value['streams'][:1]
    assert strategy.media_issues(value)


def test_rank_prefers_niche_and_thirty_seconds():
    make=lambda duration,text: SimpleNamespace(start=0,end=duration,text=text,title='',score=80)
    assert strategy.candidate_score(make(30,'pengaturan HP aplikasi Android'),'tech_daily') > strategy.candidate_score(make(50,'pengaturan HP aplikasi Android'),'tech_daily')
    assert strategy.candidate_score(make(30,'cerita pertandingan sepak bola'),'tech_daily')==-1
    assert strategy.candidate_score(make(56,'pengaturan HP'),'tech_daily')==-1


def test_caption_omits_public_source_and_engagement():
    result=strategy.public_caption('Rapikan notifikasi HP.\nSumber: seseorang\nhttps://youtube.com/watch?v=abc\nLike share follow\n@creator\n#fyp')
    assert result=='Rapikan notifikasi HP.'
    clip=SimpleNamespace(title='Rapikan notifikasi HP',text='Buka pengaturan notifikasi.')
    caption=strategy.make_caption(clip,AIConfig())
    assert caption=='Rapikan notifikasi HP.\n\n#TipsHP #TeknologiSehariHari'


def test_captions_are_stable_phrases_and_do_not_overlap(tmp_path,monkeypatch):
    segments=[clipper.TranscriptSegment(start=0,end=6,text='Buka pengaturan HP lalu pilih aplikasi dan atur notifikasi sesuai kebutuhan.'),
              clipper.TranscriptSegment(start=5.8,end=9,text='Sekarang notifikasi lebih mudah diperiksa.')]
    cues=strategy.phrase_cues(segments,0,9)
    assert all(end-start>=.8 for start,end,_ in cues)
    assert all(len(text.splitlines())<=2 for _,_,text in cues)
    from PIL import ImageFont
    font=ImageFont.truetype('DejaVuSans-Bold.ttf',58)
    assert all(font.getlength(line)<=680 for _,_,text in cues for line in text.splitlines())
    assert all(cues[index][1]<=cues[index+1][0] for index in range(len(cues)-1))
    monkeypatch.setenv('CLIPFORGE_FACEBOOK_NICHE','tech_daily')
    path=tmp_path/'facebook.ass'
    clipper.write_dynamic_ass(path,segments,0,9,clipper.CaptionStyle())
    value=path.read_text()
    assert 'Style: Caption' in value and ',58,' in value
    assert not any(tag in value for tag in ['\\fad','\\k','\\fscx108','\\t('])
    assert '\\N' in value


def test_config_and_workspace_are_separate(client):
    result=client.get('/api/facebook/config').json()
    assert result['max_seconds']==55 and result['target_email']=='fendysketsa@gmail.com'
    assert result['niches'][0]['key']=='tech_daily'
    assert client.get('/api/facebook/jobs').json()==[]


def test_create_validates_rights_before_queuing(client,monkeypatch):
    captured=[]
    monkeypatch.setattr(api,'create_job',lambda request: captured.append(request) or {'queued':True})
    value={'url':'https://www.youtube.com/watch?v=abcdefghijk', 'rights':'permission_no_credit',
           'rights_evidence':'Pemilik video dan audio memberikan izin komersial tertulis tanpa atribusi.'}
    assert client.post('/api/facebook/jobs',json=value).status_code==200
    assert captured[0].target_platform=='facebook' and not captured[0].auto_upload_youtube
    assert captured[0].max_duration==38 and not captured[0].require_creative_commons
    value['rights_evidence']='kata'*7
    assert client.post('/api/facebook/jobs',json=value).status_code==400
    value['source_file']='upload.mp4'
    assert client.post('/api/facebook/jobs',json=value).status_code==400


@pytest.fixture
def rendered(monkeypatch,tmp_path):
    output=tmp_path/'outputs';output.mkdir()
    path=output/'clip_01.mp4';path.write_bytes(b'fixture-media')
    monkeypatch.setattr(api,'OUTPUTS_DIR',output)
    monkeypatch.setattr(api,'output_path_from_url',lambda _:path)
    monkeypatch.setattr(facebook_api.subprocess,'check_output',lambda *a,**k:json.dumps(media()).encode())
    request=api.ClipJobRequest(target_platform='facebook',confirm_source_rights=True,
        facebook_source_rights='owned',source_rights_evidence='Rekaman visual dan audio ini saya produksi sendiri sepenuhnya.')
    clip=api.ClipFile(name=path.name,url='/outputs/clip_01.mp4',size_bytes=13,is_correct=True,
                      narrative_arc_complete=True,context_recut_required=False)
    job=api.ClipJob(id='facebook-job',request=request,status='completed',created_at='2026-11-15T00:00:00+00:00',
                    updated_at='2026-11-15T00:00:00+00:00',clips=[clip])
    api.jobs[job.id]=job
    sidecar={'facebook':{'version':1,'watermark':{'style_version':2},'caption':'Rapikan notifikasi HP.\n\n#TipsHP'},
             'render_quality_qc':{'quality_gate_passed':True,'blocking':False}}
    monkeypatch.setattr(api,'clip_sidecar_payload',lambda _:sidecar)
    return job,clip,sidecar,path


def test_qc_requires_real_profile_review_and_no_hold(client,rendered):
    job,clip,sidecar,path=rendered
    value={'job_id':job.id,'clip_url':clip.url}
    assert client.post('/api/facebook/qc',json=value).json()['decision']=='PASS_UPLOAD'
    clip.is_correct=False
    assert client.post('/api/facebook/qc',json=value).json()['decision']=='HOLD'
    clip.is_correct=True;job.request.publication_review_required=True
    assert client.post('/api/facebook/qc',json=value).json()['decision']=='HOLD'
    job.request.publication_review_required=False;sidecar['render_quality_qc']['quality_gate_passed']=None
    assert client.post('/api/facebook/qc',json=value).json()['decision']=='HOLD'


def test_facebook_is_excluded_from_other_platforms(rendered):
    job,clip,_,_=rendered
    assert 'Facebook' in api.youtube_monetization_preflight_issue(job,clip)
    assert api.best_automatic_upload_clip_urls(job,1)==[]


def test_queue_deduplicates_hash_and_survives_restart_without_losing_checkpoint(client,rendered,monkeypatch,tmp_path):
    job,clip,_,_=rendered
    monkeypatch.setattr(facebook_api,'start_background',lambda *args:None)
    ledger=api.JOBS_PATH.parent/'facebook_workspace.json'
    ledger.write_text(json.dumps({'schema':1,'uploads':{},'session':{
        'account_verified':True,'verified_profile_id':'1234','checked_at':datetime.now(timezone.utc).isoformat()}}))
    value={'job_id':job.id,'clip_url':clip.url}
    first=client.post('/api/facebook/uploads',json=value)
    assert first.status_code==200,first.text
    second=client.post('/api/facebook/uploads',json=value)
    assert first.json()['id']==second.json()['id']
    store=facebook_api.Store(ledger)
    identifier=first.json()['id']
    store.update(identifier,submission_started=True,status='needs_review')
    restored=facebook_api.Store(ledger)
    assert restored.data['uploads'][identifier]['submission_started']
    assert restored.data['uploads'][identifier]['status']=='needs_review'
    assert ledger.stat().st_mode & 0o777 == 0o600


def test_upload_cannot_start_from_saved_cookie_presence(client,rendered):
    job,clip,_,_=rendered
    result=client.post('/api/facebook/uploads',json={'job_id':job.id,'clip_url':clip.url})
    assert result.status_code==409 and 'sesi' in result.json()['detail']


def test_cleanup_outage_never_demotes_a_confirmed_upload(client,rendered,monkeypatch):
    job,clip,_,_=rendered
    queued=[]
    monkeypatch.setattr(facebook_api,'start_background',lambda target,*args:queued.append((target,args)))
    monkeypatch.setattr(api,'social_upload_turn',lambda:nullcontext())
    monkeypatch.setattr(api,'social_upload_cooldown_remaining',lambda:0)
    ledger=api.JOBS_PATH.parent/'facebook_workspace.json'
    ledger.write_text(json.dumps({'schema':1,'uploads':{},'session':{
        'account_verified':True,'verified_profile_id':'1234','checked_at':datetime.now(timezone.utc).isoformat()}}))
    response=client.post('/api/facebook/uploads',json={'job_id':job.id,'clip_url':clip.url})
    assert response.status_code==200
    def publish(path,caption,profile_id,checkpoint):
        checkpoint(submission_started=True)
        return dict(status='completed',upload_confirmed=True,video_url='https://www.facebook.com/reel/12345/',message='Confirmed')
    monkeypatch.setattr(facebook_browser,'upload',publish)
    monkeypatch.setattr(facebook_api.facebook_cleanup,'cleanup_once',lambda *args:(_ for _ in ()).throw(OSError('offline disk')))
    target,args=queued[0];target(*args)
    row=client.get('/api/facebook/uploads').json()[0]
    assert row['status']=='completed' and row['upload_confirmed']
    assert row['video_url']=='https://www.facebook.com/reel/12345/'


def test_protects_pending_facebook_files_from_deletion(client,rendered,monkeypatch):
    job,clip,_,_=rendered
    monkeypatch.setattr(api,'facebook_upload_protected',lambda *args:True)
    with pytest.raises(api.HTTPException) as raised:
        api.delete_job_clips_by_url(job.id,{clip.url})
    assert raised.value.status_code==409


def test_corrupt_ledger_is_not_reset(tmp_path):
    path=tmp_path/'facebook.json';path.write_text('{broken')
    with pytest.raises(json.JSONDecodeError):facebook_api.Store(path)
    assert path.read_text()=='{broken'


@pytest.mark.parametrize('url',['http://facebook.com/reel/123/','https://evil.test/reel/123/',
                               'https://www.facebook.com.evil.test/reel/123/', 'https://facebook.com/reel/no-id/',
                               'https://facebook.com/reel/123/extra'])
def test_remote_identity_requires_exact_facebook_reel(url):
    assert facebook_browser.reel_url(url) is None


def test_browser_transport_outage_preserves_session_semantics(monkeypatch):
    monkeypatch.setattr(facebook_browser,'connection',lambda:(_ for _ in ()).throw(ConnectionError('offline')))
    result=facebook_browser.check_session()
    assert result['status']=='browser_unavailable' and result['logged_in'] is None


def test_page_switch_does_not_count_as_personal_professional_identity():
    context=SimpleNamespace(cookies=lambda _:[{'name':'c_user','value':'1234'},{'name':'i_user','value':'5678'}])
    assert facebook_browser.logged_user(context)=='1234'
    assert facebook_browser.active_user(context)=='5678'
    result=facebook_browser.session(context)
    assert not result['account_verified'] and result['status']=='account_unverified'


def test_read_only_reconcile_rejects_another_domain(client,tmp_path):
    ledger=api.JOBS_PATH.parent/'facebook_workspace.json'
    ledger.write_text(json.dumps({'schema':1,'uploads':{'u':{'id':'u','profile_id':'1234','caption':'Test'}},'session':{}}))
    result=client.post('/api/facebook/uploads/u/verify-remote',json={'video_url':'https://evil.test/reel/123/'})
    assert result.status_code==400


def test_retry_never_reposts_an_ambiguous_submission(client):
    ledger=api.JOBS_PATH.parent/'facebook_workspace.json'
    ledger.write_text(json.dumps({'schema':1,'uploads':{'u':{'id':'u','status':'failed',
        'submission_started':True,'upload_confirmed':False}},'session':{}}))
    result=client.post('/api/facebook/uploads/u/retry')
    assert result.status_code==409
    assert 'remote' in result.json()['detail']


@pytest.mark.parametrize('change,allowed',[
    ({'attempts':1},True),({'attempts':2},True),({'attempts':3},False),
    ({'submission_started':True},False),({'upload_confirmed':True},False),
    ({'video_url':'https://www.facebook.com/reel/123/'},False),({'status':'running'},False),
])
def test_upload_list_exposes_the_same_retry_policy_as_the_endpoint(client,change,allowed):
    row={'id':'u','job_id':'job','status':'failed','attempts':1,'submission_started':False,
         'upload_confirmed':False,'clip_name':'clip.mp4','created_at':api.now_iso(),**change}
    ledger=api.JOBS_PATH.parent/'facebook_workspace.json'
    ledger.write_text(json.dumps({'schema':1,'uploads':{'u':row},'session':{}}))
    shown=client.get('/api/facebook/uploads').json()[0]
    assert shown['can_retry'] is allowed
    assert bool(shown['retry_block_reason']) is not allowed
    if not allowed:
        response=client.post('/api/facebook/uploads/u/retry')
        assert response.status_code==409 and response.json()['detail']==shown['retry_block_reason']
