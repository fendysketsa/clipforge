from contextlib import nullcontext
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

import api
import facebook_api
import facebook_cleanup as cleanup


@pytest.fixture
def uploaded(tmp_path,monkeypatch):
    root=tmp_path/'outputs';folder=root/'facebook_autopilot'/'fb-owned'
    folder.mkdir(parents=True)
    media=folder/'facebook_original.mp4';media.write_bytes(b'exact published video')
    for name in ('voice_0.wav','narration.wav','authored_ui_sounds.wav','source-plan.json',
                 'facebook_original.json','facebook_original.srt','facebook_original_thumb.jpg'):
        (folder/name).write_bytes(b'generated intermediary')
    monkeypatch.setattr(api,'OUTPUTS_DIR',root)
    monkeypatch.setattr(api,'job_processes',{})
    monkeypatch.setattr(api,'long_qc_active',set())
    request=api.ClipJobRequest(target_platform='facebook',facebook_autopilot_key='slot')
    clip=api.ClipFile(name=media.name,url='/outputs/facebook_autopilot/fb-owned/'+media.name,
        size_bytes=media.stat().st_size,title='Nama sama, periksa folder')
    job=api.ClipJob(id='fb-owned',request=request,status='completed',clips=[clip],
        source_title=clip.title,created_at=api.now_iso(),updated_at=api.now_iso())
    api.jobs[job.id]=job
    store=facebook_api.Store(api.JOBS_PATH.parent/'facebook_workspace.json')
    row=dict(id='published',job_id=job.id,clip_url=clip.url,clip_name=clip.name,
        status='completed',submission_started=True,upload_confirmed=True,kind='reel',
        target_email='fendysketsa@gmail.com',profile_id='1234',sha256=api.file_sha256(media),
        video_url='https://www.facebook.com/reel/12345/',caption='Periksa nama dan lokasi.',
        created_at=api.now_iso(),updated_at=api.now_iso(),message='Remote confirmed')
    store.data['uploads']['published']=row;store.save()
    return store,row,job,media


def test_confirmed_generated_upload_frees_workspace_preserves_history_and_source(uploaded,tmp_path):
    store,row,job,media=uploaded
    source=tmp_path/'uploads'/'owned-input.mp4';source.parent.mkdir();source.write_bytes(b'original input')
    job.request.source_file=source.name
    expected=sum(p.stat().st_size for p in media.parent.iterdir())
    result=cleanup.cleanup_once(api,store)
    assert result==dict(cleaned_uploads=1,removed_files=8,freed_bytes=expected,deferred=0,errors=[])
    assert not media.parent.exists() and source.read_bytes()==b'original input'
    assert api.jobs[job.id].clips[0].url==row['clip_url']
    saved=facebook_api.Store(store.path).data['uploads'][row['id']]
    assert saved['upload_confirmed'] and saved['video_url']==row['video_url']
    assert saved['sha256']==row['sha256'] and saved['caption']==row['caption']
    assert saved['local_cleanup']['state']=='deleted'
    assert cleanup.cleanup_once(api,store)['removed_files']==0


@pytest.mark.parametrize('change',[
    {'status':'needs_review'},{'status':'queued'},{'status':'running'},
    {'status':'failed'},{'upload_confirmed':False},{'submission_started':False},
    {'video_url':None},{'video_url':'https://evil.invalid/reel/12345/'},
    {'target_email':'someone-else@example.com'},{'profile_id':''},{'sha256':'unknown'},
])
def test_unconfirmed_or_untrusted_remote_never_deletes(uploaded,change):
    store,row,_,media=uploaded;row.update(change)
    assert cleanup.cleanup_once(api,store)['removed_files']==0
    assert media.exists() and not row.get('local_cleanup')


@pytest.mark.parametrize('guard',['hash','active','review','repair','qc','shared','youtube','tiktok','ambiguous_sibling'])
def test_changed_active_held_or_shared_files_are_protected(uploaded,guard):
    store,row,job,media=uploaded
    if guard=='hash':media.write_bytes(b'changed since upload')
    if guard=='active':api.job_processes[job.id]=object()
    if guard=='review':job.request.publication_review_required=True
    if guard=='repair':api.jobs['repair']=job.model_copy(update=dict(id='repair',status='running',clips=[],repair_source_job_id=job.id))
    if guard=='qc':api.long_qc_active.add(job.id+'\n'+row['clip_url'])
    if guard=='shared':api.jobs['shared']=job.model_copy(update=dict(id='shared'))
    if guard in {'youtube','tiktok'}:getattr(api,guard+'_uploads')['foreign']=SimpleNamespace(clip_url=row['clip_url'])
    if guard=='ambiguous_sibling':store.data['uploads']['other']={**row,'id':'other','status':'needs_review','upload_confirmed':False}
    assert cleanup.cleanup_once(api,store)['removed_files']==0
    assert media.exists()


def test_manual_clip_cleanup_preserves_sibling_video_and_input_workspace(uploaded):
    store,row,job,media=uploaded
    job.request.facebook_autopilot_key=''
    sibling=media.with_name('second.mp4');sibling.write_bytes(b'not published')
    job.clips.append(job.clips[0].model_copy(update=dict(url=row['clip_url'].replace(media.name,sibling.name),name=sibling.name)))
    result=cleanup.cleanup_once(api,store)
    assert result['cleaned_uploads']==1 and not media.exists()
    assert sibling.read_bytes()==b'not published' and (media.parent/'source-plan.json').exists()


def test_symlink_and_nested_job_dependencies_preserve_entire_workspace(uploaded):
    store,row,job,media=uploaded
    nested=media.parent/'nested';nested.mkdir()
    other=nested/'other.mp4';other.write_bytes(b'keep')
    clip=job.clips[0].model_copy(update=dict(url='/outputs/facebook_autopilot/fb-owned/nested/other.mp4'))
    api.jobs['nested']=job.model_copy(update=dict(id='nested',clips=[clip]))
    assert cleanup.cleanup_once(api,store)['removed_files']==0 and media.exists()
    api.jobs.pop('nested')
    link=media.parent/'linked.wav';link.symlink_to(other)
    assert cleanup.cleanup_once(api,store)['removed_files']==0 and other.exists()


def test_cleanup_failure_does_not_lose_remote_success_and_resumes(uploaded,monkeypatch):
    store,row,_,media=uploaded
    unlink=Path.unlink
    def blocked(path,*args,**kwargs):
        if path==media:raise PermissionError('container owned')
        return unlink(path,*args,**kwargs)
    monkeypatch.setattr(Path,'unlink',blocked)
    result=cleanup.cleanup_once(api,store)
    assert result['errors'] and row['local_cleanup']['state']=='error'
    assert row['status']=='completed' and row['upload_confirmed'] and media.exists()
    monkeypatch.setattr(Path,'unlink',unlink)
    assert cleanup.cleanup_once(api,store)['cleaned_uploads']==1
    assert row['local_cleanup']['state']=='deleted' and not media.exists()


def test_startup_resume_can_finish_checkpoint_after_mp4_already_deleted(uploaded):
    store,row,_,media=uploaded
    row['local_cleanup']=dict(state='deleting',removed_files=1,freed_bytes=media.stat().st_size)
    media.unlink();store.save()
    result=cleanup.cleanup_once(api,facebook_api.Store(store.path))
    assert result['cleaned_uploads']==1 and not media.parent.exists()


def test_legacy_deleted_job_keeps_a_link_and_caption_without_a_broken_preview(uploaded):
    store,row,job,media=uploaded
    cleanup.cleanup_once(api,store)
    row.pop('local_cleanup');row.pop('title',None);api.jobs.pop(job.id)
    store.data['autopilot_runs']={'slot':{'job_id':job.id,'title':job.source_title}}
    store.save()
    cleanup.cleanup_once(api,store)
    assert row['local_cleanup']['state']=='missing'
    result=TestClient(api.app).get('/api/facebook/uploads').json()[0]
    assert result['title']==job.source_title and result['caption']==row['caption']
    assert result['video_url']==row['video_url'] and not media.exists()


def test_upload_request_after_cleanup_returns_existing_remote_without_file_qc(uploaded,monkeypatch):
    store,row,_,_=uploaded
    cleanup.cleanup_once(api,store)
    monkeypatch.setattr(facebook_api,'start_background',lambda *args:pytest.fail('No duplicate Post'))
    monkeypatch.setattr(api,'find_job_clip',lambda *args:pytest.fail('No local media required'))
    response=TestClient(api.app).post('/api/facebook/uploads',json=dict(job_id=row['job_id'],clip_url=row['clip_url']))
    assert response.status_code==200 and response.json()['id']==row['id']
    assert response.json()['local_cleanup']['state']=='deleted'


def test_cleanup_route_and_paused_worker_can_clean_without_new_publication(uploaded,monkeypatch):
    store,row,_,media=uploaded
    response=TestClient(api.app).post('/api/facebook/storage/cleanup')
    assert response.status_code==200 and response.json()['cleaned_uploads']==1
    assert not media.exists()


def test_admission_lock_defers_cleanup_without_waiting(uploaded):
    store,_,_,media=uploaded
    api.youtube_upload_creation_lock.acquire()
    try:assert cleanup.cleanup_once(api,store)['deferred']==1 and media.exists()
    finally:api.youtube_upload_creation_lock.release()


def test_story_requires_exact_stored_owner_and_created_remote_identity(uploaded):
    store,row,_,media=uploaded
    row.update(kind='story',video_url='https://www.facebook.com/stories/1234/5678/')
    assert cleanup.cleanup_once(api,store)['removed_files']==0 and media.exists()
    row['remote_story_url']=row['video_url']
    assert cleanup.cleanup_once(api,store)['cleaned_uploads']==1


@pytest.fixture
def skipped(uploaded):
    store,row,job,media=uploaded
    row.update(kind='story',status='failed',submission_started=False,upload_confirmed=False,video_url=None,
        recovery_status='skipped',recovery_action='skip_expired_story',recovery_version=1,
        created_at=(datetime.now(timezone.utc)-timedelta(days=3)).isoformat(),recovery_at=api.now_iso())
    store.save()
    return store,row,job,media


def test_terminal_story_deletes_files_and_card_without_fabricating_publication(skipped):
    store,row,job,media=skipped
    before=dict(row);expected=sum(p.stat().st_size for p in media.parent.iterdir())
    result=cleanup.cleanup_once(api,store)
    assert result['cleaned_uploads']==1 and result['freed_bytes']==expected
    assert not media.parent.exists() and job.id not in api.jobs
    assert all(row[key]==value for key,value in before.items())
    assert row['local_cleanup']['disposition']=='discarded'
    assert row['local_cleanup']['reason']=='skip_expired_story'
    assert row['status']=='failed' and row['upload_confirmed'] is False
    assert json.loads(api.JOBS_PATH.read_text())==[]
    assert TestClient(api.app).get('/api/facebook/jobs').json()==[]
    assert cleanup.cleanup_once(api,store)['removed_files']==0


@pytest.mark.parametrize('changes',[
    {'submission_started':True},{'submission_started':None},{'submission_accepted':True},
    {'upload_confirmed':True},{'remote_story_url':'https://www.facebook.com/stories/1234/5678/'},
    {'video_url':'https://www.facebook.com/stories/1234/5678/'},{'candidate_video_urls':['possible-post']},
    {'status':'needs_review'},{'status':'running'},{'kind':'reel'},{'recovery_status':None},
    {'recovery_action':'unknown'},{'recovery_version':None},{'created_at':'broken'},
    {'recovery_at':'broken'},{'created_at':datetime.now(timezone.utc).isoformat()},
    {'recovery_at':'2099-01-01T00:00:00+00:00'},{'profile_id':''},{'sha256':'unknown'},
])
def test_terminal_label_never_overrides_missing_or_remote_evidence(skipped,changes):
    store,row,job,media=skipped;row.update(changes)
    assert cleanup.cleanup_once(api,store)['removed_files']==0
    assert media.is_file() and api.jobs[job.id] is job


@pytest.mark.parametrize('guard',['held','active','repair','qc','shared','foreign','changed'])
def test_terminal_disposal_preserves_active_held_and_shared_dependencies(skipped,guard):
    store,row,job,media=skipped
    if guard=='held':job.request.publication_review_required=True
    if guard=='active':api.job_processes[job.id]=object()
    if guard=='repair':api.jobs['repair']=job.model_copy(update=dict(id='repair',status='running',clips=[],repair_source_job_id=job.id))
    if guard=='qc':api.long_qc_active.add(job.id+'\n'+row['clip_url'])
    if guard=='shared':api.jobs['shared']=job.model_copy(update=dict(id='shared'))
    if guard=='foreign':api.youtube_uploads['keep']=SimpleNamespace(clip_url=row['clip_url'])
    if guard=='changed':media.write_bytes(b'changed after failure')
    assert cleanup.cleanup_once(api,store)['removed_files']==0
    assert media.exists() and job.id in api.jobs


def test_terminal_job_save_failure_preserves_memory_and_resumes_checkpoint(skipped,monkeypatch):
    store,row,job,media=skipped
    save=api.save_jobs_unlocked
    def unavailable():raise OSError('disk temporarily unavailable')
    monkeypatch.setattr(api,'save_jobs_unlocked',unavailable)
    assert cleanup.cleanup_once(api,store)['errors']
    assert api.jobs[job.id] is job and row['local_cleanup']['state']=='error'
    assert not media.exists() and row['submission_started'] is False
    monkeypatch.setattr(api,'save_jobs_unlocked',save)
    assert cleanup.cleanup_once(api,store)['cleaned_uploads']==1
    assert job.id not in api.jobs and row['local_cleanup']['state']=='deleted'


def test_terminal_orphan_without_media_gets_receipt_without_deleting_another_job(skipped):
    store,row,job,media=skipped
    media.unlink();api.jobs.pop(job.id)
    cleanup.cleanup_once(api,store)
    assert row['local_cleanup']['state']=='missing' and row['local_cleanup']['disposition']=='discarded'
    assert not row['upload_confirmed'] and row['video_url'] is None
