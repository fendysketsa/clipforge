import pytest
import api
import upload_attention as policy
from upload_attention_runtime import AttentionService


def row(**changes):
    values=dict(id='one',source_job_id='source',clip_url='/outputs/source/clips/clip.mp4',clip_name='clip.mp4',
        title='Judul lengkap',description='Deskripsi sumber.',target_channel='ryuundyofficial',
        status='failed',created_at='2026-11-20T01:00:00Z',updated_at='2026-11-20T01:01:00Z')
    return api.YouTubeUploadJob(**{**values,**changes})


@pytest.fixture
def service(monkeypatch,tmp_path):
    monkeypatch.setenv('UPLOAD_ATTENTION_AUTOMATIC_ENABLED','true')
    monkeypatch.setenv('YOUTUBE_TARGET_CHANNEL_ID',api.DEFAULT_YOUTUBE_TARGET_CHANNEL_ID)
    monkeypatch.setattr(api,'YOUTUBE_UPLOADS_PATH',tmp_path/'uploads.json')
    monkeypatch.setattr(api,'youtube_uploads',{})
    monkeypatch.setattr(api,'tiktok_uploads',{})
    monkeypatch.setattr(api,'save_youtube_uploads_unlocked',lambda:None)
    monkeypatch.setattr(api,'save_tiktok_uploads_unlocked',lambda:None)
    monkeypatch.setattr(api,'output_path_from_url',lambda _:None)
    return AttentionService(api)


def proof(upload):
    return dict(confirmed=True,video_url=upload.video_url,title=upload.title,
        target_channel_id=api.DEFAULT_YOUTUBE_TARGET_CHANNEL_ID,visibility='public',
        description_sha256=policy.text_hash(upload.description),source='authenticated_studio_exact_video')


def decide(upload,others=None,media=False,retry=False):
    return policy.decision('youtube',upload.model_dump(),[x.model_dump() for x in others or []],
                           media_exists=media,retry_allowed=retry)


@pytest.mark.parametrize('url',['https://www.youtube.com/watch?v=AbCdEfGh123',
    'https://youtu.be/AbCdEfGh123','https://www.youtube.com/shorts/AbCdEfGh123'])
def test_exact_platform_identity(url):
    assert policy.youtube_id(url)=='AbCdEfGh123'
    assert not policy.youtube_id('https://attacker.test/watch?v=AbCdEfGh123')
    assert not policy.youtube_id('https://www.youtube.com.attacker.test/watch?v=AbCdEfGh123')


def test_missing_file_never_authorizes_retry_but_submission_evidence_requires_verification():
    assert decide(row(logs=['Video dipilih: clip.mp4']),retry=True)['action']=='verify_remote'
    assert decide(row())['action']=='hold'
    assert decide(row(logs=['UPLOAD_FAILED_BEFORE_FILE_SELECTION: setup']),retry=True)['action']=='hold'


def test_claim_rejection_wins_over_retry_and_duplicate():
    upload=row(logs=['CLAIMED_UPLOAD_ABORTED: claim'])
    done=row(id='done',status='completed',upload_confirmed=True,video_url='https://youtu.be/AbCdEfGh123')
    assert decide(upload,[done],media=True,retry=True)['action']=='drop_source'


def test_duplicate_requires_verified_remote_post_and_same_account():
    upload=row(clip_sha256='hash')
    done=row(id='done',clip_sha256='hash',status='completed',upload_confirmed=True,video_url='https://youtu.be/AbCdEfGh123')
    assert decide(upload,[done])['action']=='reconcile_duplicate'
    assert decide(upload,[done.model_copy(update={'target_channel':'other'})])['action']=='hold'
    assert decide(upload,[done.model_copy(update={'upload_confirmed':False})])['action']=='hold'


def test_ledger_preserves_budget_across_restart_and_refuses_corruption(tmp_path):
    path=tmp_path/'ledger.json';policy.StateStore(path).update('youtube-one',attempts=3)
    assert policy.StateStore(path).read()['items']['youtube-one']['attempts']==3
    path.write_text('{')
    with pytest.raises(ValueError):policy.StateStore(path).update('youtube-one',attempts=0)
    assert path.read_text()=='{'


def test_error_changes_do_not_reset_retry_budget():
    item=decide(row());item['action']='retry_upload'
    assert policy.status(item,{'revision':'old','attempts':3},100)['state']=='held'


def test_round_robin_and_backoff_do_not_starve_unseen_records():
    items=[dict(id='old',state='waiting',next_check_at=0,checked_at=99,action='verify_remote'),
        dict(id='unseen',state='waiting',next_check_at=0,checked_at=None,action='verify_remote'),
        dict(id='later',state='waiting',next_check_at=200,checked_at=None,action='verify_remote')]
    assert [item['id'] for item in policy.due(items,100)]==['unseen','old']


def test_private_local_record_matches_public_remote_without_upload_or_privacy_change(service,monkeypatch):
    upload=row(video_url='https://www.youtube.com/watch?v=AbCdEfGh123',visibility='private',logs=['original evidence'])
    api.youtube_uploads[upload.id]=upload
    monkeypatch.setattr(api,'queue_youtube_upload_jobs',lambda *_:pytest.fail('No transfer'))
    assert service.apply_proof(service.snapshot()['items'][0],proof(upload))
    result=api.youtube_uploads[upload.id]
    assert result.status=='completed' and result.upload_confirmed and result.visibility=='public'
    assert result.logs[0]=='original evidence' and result.clip_url==upload.clip_url


@pytest.mark.parametrize('field,value',[('video_url','https://www.youtube.com/watch?v=ZyXwVuTs987'),
    ('title','Other'),('target_channel_id','other'),('visibility','scheduled'),
    ('description_sha256','wrong'),('source','public_page')])
def test_partial_mismatched_evidence_is_rejected(service,field,value):
    upload=row(video_url='https://www.youtube.com/watch?v=AbCdEfGh123');api.youtube_uploads[upload.id]=upload
    evidence=proof(upload);evidence[field]=value
    assert not service.apply_proof(service.snapshot()['items'][0],evidence)
    assert api.youtube_uploads[upload.id] is upload


def test_changed_record_rejects_late_browser_response(service):
    upload=row(video_url='https://www.youtube.com/watch?v=AbCdEfGh123');api.youtube_uploads[upload.id]=upload
    item=service.snapshot()['items'][0];api.youtube_uploads[upload.id]=upload.model_copy(update={'status':'queued'})
    assert not service.apply_proof(item,proof(upload))
    assert api.youtube_uploads[upload.id].status=='queued'


def test_discovery_without_checkpoint_requires_original_filename(service):
    upload=row(logs=['Video dipilih: clip.mp4']);api.youtube_uploads[upload.id]=upload
    item=service.snapshot()['items'][0];evidence=proof(upload);evidence['video_url']='https://youtu.be/AbCdEfGh123'
    assert not service.apply_proof(item,evidence)
    evidence['file_name_matched']=True
    assert service.apply_proof(item,evidence)


def test_verified_duplicate_is_reconciled_without_browser_and_preserves_logs(service,monkeypatch):
    api.youtube_uploads['one']=row(logs=['original evidence'])
    api.youtube_uploads['done']=row(id='done',status='completed',upload_confirmed=True,video_url='https://youtu.be/AbCdEfGh123')
    monkeypatch.setattr(service,'observe',lambda *_:pytest.fail('No browser needed'))
    assert service.run_once()==1
    assert api.youtube_uploads['one'].upload_confirmed and api.youtube_uploads['one'].logs[0]=='original evidence'


def test_unknown_outcome_backs_off_and_never_submits_again(service,monkeypatch):
    upload=row(video_url='https://www.youtube.com/watch?v=AbCdEfGh123');api.youtube_uploads[upload.id]=upload
    calls=[];monkeypatch.setattr(service,'observe',lambda *_:calls.append(True) or {'confirmed':False})
    monkeypatch.setattr(service,'retry',lambda *_:pytest.fail('No new submission'))
    assert service.run_once()==0 and service.run_once()==0 and calls==[True]
    assert api.youtube_uploads[upload.id] is upload
    item=service.snapshot()['items'][0];assert item['next_check_at']>item['checked_at']


def test_active_uploads_and_disabled_setting_take_priority(service,monkeypatch):
    api.youtube_uploads['one']=row(video_url='https://www.youtube.com/watch?v=AbCdEfGh123')
    api.youtube_uploads['active']=row(id='active',status='running')
    monkeypatch.setattr(service,'observe',lambda *_:pytest.fail('Deferred'))
    api.social_upload_execution_lock.acquire()
    try:assert service.run_once()==0
    finally:api.social_upload_execution_lock.release()
    api.youtube_uploads.pop('active');monkeypatch.setenv('UPLOAD_ATTENTION_AUTOMATIC_ENABLED','false')
    assert service.run_once()==0


def test_stale_unrelated_running_record_does_not_starve_an_available_browser(service,monkeypatch):
    api.youtube_uploads['one']=row(video_url='https://www.youtube.com/watch?v=AbCdEfGh123')
    api.youtube_uploads['stale']=row(id='stale',status='running',clip_url='/outputs/other.mp4')
    calls=[]
    monkeypatch.setattr(service,'observe',lambda *_:calls.append(True) or {'confirmed':False})
    assert service.run_once()==0
    assert calls==[True] and api.youtube_uploads['stale'].status=='running'


def test_busy_social_browser_does_not_spend_budget(service):
    api.youtube_uploads['one']=row(video_url='https://www.youtube.com/watch?v=AbCdEfGh123')
    api.social_upload_execution_lock.acquire()
    try:assert service.run_once()==0
    finally:api.social_upload_execution_lock.release()
    assert not service.store.path.exists()


def test_tiktok_profile_link_and_post_intent_cannot_be_retried(service):
    upload=api.TikTokUploadJob(id='tt',source_job_id='job',clip_url='/outputs/clip.mp4',clip_name='clip.mp4',
        created_at='2026-11-20T01:00:00Z',updated_at='2026-11-20T01:00:00Z',status='completed',
        upload_confirmed=True,profile_url='https://www.tiktok.com/@titikbalikislami',
        caption='Caption lengkap',target_handle='titikbalikislami',submission_started=True)
    api.tiktok_uploads[upload.id]=upload
    assert not policy.confirmed('tiktok',upload.model_dump())
    assert service.snapshot()['items'][0]['action']=='verify_remote'
    assert not service.retry_allowed('tiktok',upload.model_dump())


def test_regenerated_file_at_same_path_does_not_match_old_hash():
    left=row(clip_sha256='original');right=row(id='other',clip_sha256='replacement')
    assert not policy.same_media(left.model_dump(),right.model_dump())


def test_claim_added_while_audit_runs_blocks_late_success(service):
    upload=row(video_url='https://www.youtube.com/watch?v=AbCdEfGh123');api.youtube_uploads[upload.id]=upload
    item=service.snapshot()['items'][0]
    api.youtube_uploads[upload.id]=upload.model_copy(update={'logs':['CLAIMED_UPLOAD_ABORTED: new claim']})
    assert not service.apply_proof(item,proof(upload))


@pytest.mark.parametrize('upload_failed',['True','False'])
def test_remote_reader_observes_actual_privacy_and_never_calls_upload_controls(monkeypatch,upload_failed):
    import upload_attention_remote as remote
    import youtube_uploader as studio
    upload=row(video_url='https://www.youtube.com/watch?v=AbCdEfGh123')
    class Field:
        def __init__(self,text):self.text=text;self.first=self
        def wait_for(self,**kwargs):pass
        def count(self):return 1
        def inner_text(self,**kwargs):return self.text
    class Page:
        url='https://studio.youtube.com/video/AbCdEfGh123/edit'
        def goto(self,*args,**kwargs):pass
        def locator(self,selector):
            return Field(upload.title if 'title-textarea' in selector else upload.description if 'description-textarea' in selector else 'Publik')
        def get_by_text(self,*args,**kwargs):return Field(upload.clip_name)
    monkeypatch.setattr(studio,'ensure_target_identity',lambda *_:None)
    monkeypatch.setattr(studio,'saved_video_edit_snapshot',lambda *_:{'uploading':'False','uploadFailed':upload_failed})
    result=remote.read_youtube(Page(),upload.model_dump(),api.DEFAULT_YOUTUBE_TARGET_CHANNEL_ID)
    assert result['confirmed']==(upload_failed=='False')
    if result['confirmed']:assert result['visibility']=='public' and result['original_visibility']=='private'


def test_private_observation_cannot_erase_pending_schedule(service):
    upload=row(video_url='https://www.youtube.com/watch?v=AbCdEfGh123',visibility='public',publish_at='2099-01-01T00:00:00Z')
    api.youtube_uploads[upload.id]=upload
    evidence=proof(upload);evidence['visibility']='private'
    assert not service.apply_proof(service.snapshot()['items'][0],evidence)
    assert api.youtube_uploads[upload.id].publish_at==upload.publish_at


def test_tiktok_reconciles_observed_privacy_without_publishing(service,monkeypatch):
    monkeypatch.setattr(api,'tiktok_target_handle',lambda:'titikbalikislami')
    upload=api.TikTokUploadJob(id='tt',source_job_id='job',clip_url='/outputs/clip.mp4',clip_name='clip.mp4',
        created_at='2026-11-20T01:00:00Z',updated_at='2026-11-20T01:00:00Z',status='failed',visibility='only_you',
        caption='Caption lengkap',target_handle='titikbalikislami',submission_started=True)
    api.tiktok_uploads[upload.id]=upload
    evidence=dict(confirmed=True,video_url='https://www.tiktok.com/@titikbalikislami/video/1234567890123456789',
        visibility='public',caption_sha256=policy.caption_hash(upload.caption),source='authenticated_studio_exact_post')
    assert service.apply_proof(service.snapshot()['items'][0],evidence)
    assert api.tiktok_uploads[upload.id].visibility=='public' and api.tiktok_uploads[upload.id].upload_confirmed


@pytest.mark.parametrize('stubborn',[False,True])
def test_reader_timeout_terminates_owned_process_with_cleanup_grace(service,monkeypatch,stubborn):
    import upload_attention_runtime as runtime
    class Process:
        returncode=143
        def __init__(self):self.calls=0;self.terminated=False;self.killed=False
        def communicate(self,timeout=None):
            self.calls+=1
            if self.calls==1 or (stubborn and self.calls==2):
                raise runtime.subprocess.TimeoutExpired('reader',timeout)
            return ('','')
        def terminate(self):self.terminated=True
        def kill(self):self.killed=True
    process=Process();monkeypatch.setattr(runtime.subprocess,'Popen',lambda *args,**kwargs:process)
    result=service.observe('youtube',row())
    assert not result['confirmed'] and process.terminated
    assert process.killed==stubborn


def test_check_now_advances_due_time_without_resetting_budget_or_releasing_holds(service,monkeypatch):
    api.youtube_uploads['one']=row(video_url='https://www.youtube.com/watch?v=AbCdEfGh123')
    api.youtube_uploads['held']=row(id='held',error='Menunggu pemeriksaan content safety')
    item=next(item for item in service.snapshot()['items'] if item['upload_id']=='one')
    service.store.update(item['id'],revision=item['revision'],state='waiting',attempts=2,next_check_at=9999999999)
    monkeypatch.setattr(service,'start',lambda:None)
    assert service.request_check()==1 and service.wakeup.is_set()
    saved=service.store.read()['items'][item['id']]
    assert saved['attempts']==2 and saved['next_check_at']<9999999999
    assert not api.youtube_uploads['held'].upload_confirmed
