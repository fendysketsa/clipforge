import hashlib,json
import pytest
import api

URL='https://www.youtube.com/watch?v=abcDEF12345'

@pytest.fixture
def recovery(monkeypatch,tmp_path):
    media=tmp_path/'recovery'/'clips'/'clip_01.mp4';media.parent.mkdir(parents=True);media.write_bytes(b'verified media')
    digest=hashlib.sha256(media.read_bytes()).hexdigest()
    url='/outputs/manual-rescue/test/clips/clip_01.mp4'
    stamp=api.now_iso()
    job=api.ClipJob(id='failed',status='failed',request=api.ClipJobRequest(url=URL,confirm_source_rights=True,source_rights_evidence='Existing permission'),created_at=stamp,updated_at=stamp,error='No candidates')
    api.jobs[job.id]=job
    clip=api.ClipFile(name=media.name,url=url,size_bytes=media.stat().st_size)
    side=dict(recovery_source_job_id=job.id,source_url=URL,source_original_start=30,source_original_end=60,
              recovery_ai_qc=dict(decision='PASS_UPLOAD',upload_allowed=True,output_sha256=digest))
    sidepath=media.with_suffix('.json');sidepath.write_text(json.dumps(side))
    manifest=api.SOURCE_USAGE_HISTORY_PATH.with_name('reviewed_recovery_outputs.json')
    manifest.write_text(json.dumps([dict(source_job_id=job.id,clip_url=url,sha256=digest,candidate=dict(index=1,start=30,end=60,duration=30,score=85,title='A complete scene',reason='Source-backed',text='Complete source transcript'))]))
    monkeypatch.setattr(api,'output_path_from_url',lambda _:media)
    monkeypatch.setattr(api,'discover_clips',lambda *a:[clip])
    monkeypatch.setattr(api,'upload_media_duration_issue',lambda *a:None)
    monkeypatch.setattr(api,'partition_completed_clips_by_integrity',lambda req,clips:(clips,[]))
    monkeypatch.setattr(api,'save_jobs_unlocked',lambda:None)
    return media,sidepath,manifest,job


def test_reviewed_output_attaches_to_exact_failed_job_once(recovery):
    _,_,manifest,job=recovery
    assert api.adopt_reviewed_recovery_outputs_once()==1
    recovered=api.jobs[job.id]
    assert recovered.status=='completed' and recovered.error is None
    assert len(recovered.clips)==1 and recovered.source_url==URL
    assert recovered.request.source_rights_evidence==job.request.source_rights_evidence
    assert api.adopt_reviewed_recovery_outputs_once()==0
    assert json.loads(manifest.read_text())[0]['status']=='adopted'


@pytest.mark.parametrize('risk',['hash','source','job','qc','permission','active','candidate_clock','existing_output','media'])
def test_recovery_cannot_bypass_identity_integrity_review_or_active_job(recovery,monkeypatch,risk):
    media,sidepath,_,job=recovery
    side=json.loads(sidepath.read_text())
    if risk=='hash':media.write_bytes(b'changed media')
    if risk=='source':side['source_url']='https://www.youtube.com/watch?v=otherABC123'
    if risk=='job':side['recovery_source_job_id']='another-job'
    if risk=='qc':side['recovery_ai_qc']['decision']='REPAIR_ONCE'
    if risk=='permission':job.request.confirm_source_rights=False
    if risk=='active':job.status='running'
    if risk=='candidate_clock':side['source_original_end']=90
    if risk=='existing_output':job.clips=[api.ClipFile(name='existing.mp4',url='/outputs/existing.mp4',size_bytes=10)]
    if risk=='media':monkeypatch.setattr(api,'partition_completed_clips_by_integrity',lambda *a:([],[('clip','corrupt')]))
    sidepath.write_text(json.dumps(side))
    assert api.adopt_reviewed_recovery_outputs_once()==0
    assert api.jobs[job.id].status==('running' if risk=='active' else 'failed')
