"""An office occupant may claim work only from an observed queue or execution lock."""
import json
from types import SimpleNamespace as NS
from copy import deepcopy

from test_ai_office import office, upload


def job(status='running', stage='render', **changes):
    return NS(**(dict(status=status,progress_stage=stage,progress_percent=37,repair_source_job_id=None,
        source_title='Video uji',progress_detail='password=private-secret',request=NS(target_platform='standard',
        scheduled_public_source_credit=False,review_only=False,publication_review_required=False),clips=[],candidates=[])
        | changes))


def departments(service):
    return {row['id']:row for row in service.snapshot()['activity']['departments']}


def test_queued_work_is_not_running_and_completed_work_leaves_the_office(office):
    service,api=office
    api.cron_enabled=True
    api.jobs['source']=job('queued')
    row=departments(service)['production']
    assert row['state']=='queued' and row['running_count']==0 and row['queued_count']==1
    assert row['work'][0]['progress_percent'] is None
    assert next(r for r in service.snapshot()['departments'] if r['id']=='production')['active_count']==0
    api.jobs['source'].status='running'
    assert departments(service)['production']['work'][0]['progress_percent']==37
    api.jobs['source'].status='completed'
    assert departments(service)['production']['state']=='idle'
    assert not departments(service)['production']['work']
    assert not api.calls and not service.path.exists()


def test_the_same_job_moves_from_production_to_qc_without_double_counting(office):
    service,api=office
    api.cron_enabled=True
    api.jobs['one']=job()
    assert departments(service)['production']['running_count']==1
    api.jobs['one'].progress_stage='qc'
    rows=departments(service)
    assert rows['quality']['running_count']==1 and rows['production']['running_count']==0
    assert rows['quality']['work'][0]['job_id']=='one'
    api.jobs['one'].status='completed'
    api.long_qc_active.add('one\n/clip.mp4')
    assert departments(service)['quality']['running_count']==1
    api.long_qc_active.clear()
    assert departments(service)['quality']['running_count']==0


def test_upload_queues_are_distinct_and_parent_waiting_is_not_counted_twice(office):
    service,api=office
    api.jobs['one']=job(stage='waiting_upload')
    record=upload();record.source_job_id='one';record.clip_name='Klip uji'
    api.youtube_uploads['yt']=record
    dry=upload(dry_run=True);api.tiktok_uploads['dry']=dry
    before=deepcopy(vars(record))
    row=departments(service)['distribution']
    assert row['state']=='queued' and row['queued_count']==1 and row['running_count']==0
    assert row['work'][0]['upload_id']=='yt'
    record.status='running'
    assert departments(service)['distribution']['running_count']==1
    assert vars(record)=={**before,'status':'running'}
    assert not api.calls and not service.path.exists()


def test_render_can_continue_while_coordinator_is_paused_without_changing_settings(office):
    service,api=office
    api.flags['AI_OFFICE_ENABLED']=False
    api.jobs['manual']=job()
    snapshot=service.snapshot()
    assert snapshot['state']=='disabled'
    assert next(r for r in snapshot['activity']['departments'] if r['id']=='production')['state']=='running'
    assert api.flags['AI_OFFICE_ENABLED'] is False and api.cron_enabled is False


def test_pending_cleanup_and_retry_are_not_presented_as_executing(office):
    service,api=office
    api.claimed_clip_cleanup_scheduled.add('pending')
    assert departments(service)['cleanup']['state']=='queued'
    assert departments(service)['recovery']['running_count']==0
    api.upload_attention_service.execution.acquire()
    api.terminal_output_cleanup_lock.acquire()
    try:
        rows=departments(service)
        assert rows['recovery']['running_count']==1 and rows['cleanup']['running_count']==1
    finally:
        api.upload_attention_service.execution.release();api.terminal_output_cleanup_lock.release()


def test_facebook_jobs_and_uploads_use_real_owners_without_duplicate_runs(office):
    service,api=office
    api.jobs['fb']=job(request=NS(target_platform='facebook'))
    api.facebook.update(enabled=True,activity_available=True,activity_work=[
        dict(id='fb-run',kind='production',state='queued',title='FB',job_id='fb',stage='Menunggu produksi'),
        dict(id='fb-upload',kind='upload',state='running',title='Reel',job_id='older',upload_id='upload',stage='Mengirim ke Facebook')])
    rows=departments(service)
    assert rows['production']['running_count']==0
    assert rows['facebook']['running_count']==2 and rows['facebook']['queued_count']==0
    api.jobs['fb'].progress_stage='qc'
    rows=departments(service)
    assert rows['facebook']['running_count']==1 and rows['quality']['running_count']==1


def test_projection_is_bounded_redacted_and_cannot_expose_completed_uploads(office):
    service,api=office
    for index in range(15):api.jobs[str(index)]=job(source_title='Judul token=private-secret')
    record=upload(status='completed',confirmed=True);api.youtube_uploads['sent']=record
    result=service.snapshot()['activity'];row=next(r for r in result['departments'] if r['id']=='production')
    assert row['running_count']==15 and row['total_count']==15 and len(row['work'])==8
    assert 'private-secret' not in json.dumps(result)
    assert not next(r for r in result['departments'] if r['id']=='distribution')['work']


def test_read_failure_is_explicit_instead_of_an_empty_success(office,monkeypatch):
    service,api=office
    def broken():raise RuntimeError('private-secret')
    monkeypatch.setattr(service,'context',broken)
    result=service.snapshot()
    assert result['activity']['available'] is False and result['activity']['departments']==[]
    assert 'private-secret' not in json.dumps(result)


def test_informational_fallback_policy_is_not_a_fictitious_blocked_job(office):
    service,api=office
    api.cron_enabled=True
    api.cron_life_story_status=lambda:dict(enabled=True,state='waiting_for_provider_rights')
    result=service.snapshot()
    assert result['incidents']
    assert not next(row for row in result['activity']['departments'] if row['id']=='quality')['work']
