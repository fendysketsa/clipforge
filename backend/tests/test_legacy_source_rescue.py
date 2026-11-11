import json
from types import SimpleNamespace as NS

import pytest
import api


@pytest.fixture
def rescue(monkeypatch,tmp_path):
    monkeypatch.setattr(api,'SOURCE_USAGE_HISTORY_PATH',tmp_path/'source_usage.json')
    parent=api.ClipJob(id='failed-source',status='failed',created_at=api.now_iso(),updated_at=api.now_iso(),
        error=api.SHORT_SELECTION_REJECTION_PREFIX+' lengkap.',
        request=api.ClipJobRequest(url='https://www.youtube.com/watch?v=abcDEF12345',
            scheduled_director_effects=True,scheduled_public_source_credit=True,confirm_source_rights=True,
            source_rights_evidence='Izin sumber telah dikonfirmasi pengguna.'))
    api.jobs[parent.id]=parent
    (tmp_path/'legacy_source_rescue_requests.json').write_text(json.dumps({'schema_version':1,'requests':[
        {'job_id':parent.id,'source_url':parent.request.url}]}))
    monkeypatch.setattr(api,'auto_viral_schedule_enabled',lambda:True)
    monkeypatch.setattr(api,'scheduled_upload_recovery_source_ids',lambda platform:{parent.id})
    monkeypatch.setattr(api,'cron_source_process_limit_reached',lambda url:False)
    monkeypatch.setattr(api,'normalize_job_request',lambda request:request)
    monkeypatch.setattr(api,'save_jobs_unlocked',lambda:None)
    started=[]
    class Thread:
        def __init__(self,**kwargs):self.args=kwargs['args']
        def start(self):started.extend(self.args)
    monkeypatch.setattr(api.threading,'Thread',Thread)
    return parent,started


def test_requested_legacy_failure_gets_one_durable_child_and_preserves_cron_and_rights(rescue):
    parent,started=rescue
    assert api.queue_requested_source_rescues_once()['source']==1
    child=api.jobs[started[0]]
    assert child.source_recovery_parent_job_id==parent.id and child.request.url==parent.request.url
    assert child.request.confirm_source_rights and child.request.source_rights_evidence==parent.request.source_rights_evidence
    assert child.request.scheduled_director_effects and child.request.allow_reprocess_source
    assert api.queue_requested_source_rescues_once()['source']==0
    api.set_job(child.id,status='failed',error='Still no complete moment')
    assert api.queue_requested_source_rescues_once()['source']==0 and len(started)==1


@pytest.mark.parametrize('blocker',['limit','manual','news','no_rights','already_directed','busy','disabled','wrong_source'])
def test_rescue_cannot_bypass_existing_gates(rescue,monkeypatch,blocker):
    parent,started=rescue
    if blocker=='limit':monkeypatch.setattr(api,'cron_source_process_limit_reached',lambda url:True)
    if blocker=='manual':monkeypatch.setattr(api,'scheduled_upload_recovery_source_ids',lambda p:set())
    if blocker=='news':parent.request.scheduled_news_hot=True
    if blocker=='no_rights':parent.request.confirm_source_rights=False
    if blocker=='already_directed':parent.director_recovery={'attempted':True}
    if blocker=='busy':api.jobs['busy']=parent.model_copy(update={'id':'busy','status':'running'})
    if blocker=='disabled':monkeypatch.setattr(api,'auto_viral_schedule_enabled',lambda:False)
    if blocker=='wrong_source':parent.request.url='https://www.youtube.com/watch?v=otherID1234'
    assert api.queue_requested_source_rescues_once()['source']==0 and not started


def test_recovered_output_uses_quality_gate_and_platform_failures_are_isolated(rescue,monkeypatch):
    parent,started=rescue
    api.queue_requested_source_rescues_once()
    child=api.jobs[started[0]]
    clip=api.ClipFile(name='clip.mp4',url='/outputs/child/clip.mp4',size_bytes=10,title='Judul sumber')
    api.set_job(child.id,status='completed',clips=[clip])
    monkeypatch.setenv('AUTO_VIRAL_SCHEDULE_AUTO_UPLOAD_YOUTUBE','true')
    monkeypatch.setenv('AUTO_VIRAL_SCHEDULE_AUTO_UPLOAD_TIKTOK','true')
    monkeypatch.setattr(api,'best_automatic_upload_clip_urls',lambda *a,**k:[])
    monkeypatch.setattr(api,'pending_completed_job_upload_urls',lambda job,urls,**k:urls)
    monkeypatch.setattr(api,'require_youtube_ready',lambda:(_ for _ in ()).throw(api.HTTPException(503,'Temporary browser issue')))
    monkeypatch.setattr(api,'require_tiktok_ready',lambda:None)
    monkeypatch.setattr(api,'create_tiktok_upload_batch_records',lambda *a,**k:[NS(status='queued')])
    queued=[]
    monkeypatch.setattr(api,'queue_tiktok_upload_jobs',lambda rows:queued.extend(rows))
    assert api.queue_missing_scheduled_uploads_once()=={'youtube':0,'tiktok':0}
    assert not queued
    monkeypatch.setattr(api,'best_automatic_upload_clip_urls',lambda *a,**k:[clip.url])
    monkeypatch.setattr(api,'scheduled_upload_recovery_source_ids',lambda platform:{parent.id,child.id})
    assert api.queue_missing_scheduled_uploads_once()=={'youtube':0,'tiktok':1}
    assert len(queued)==1
    # An existing uncertain Post must never become a new first upload.
    api.tiktok_uploads['uncertain']=NS(source_job_id=child.id,clip_url=clip.url,dry_run=False)
    assert api.queue_missing_scheduled_uploads_once()['tiktok']==0
    api.tiktok_uploads.clear()
    api.auto_viral_runs['active']=NS(status='running',processed=[{'job_id':child.id}])
    assert api.queue_missing_scheduled_uploads_once()=={'youtube':0,'tiktok':0}
