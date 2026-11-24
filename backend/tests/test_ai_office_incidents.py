"""The director observes outcomes and delegates only to existing guarded owners."""
import json
from types import SimpleNamespace as NS

import pytest

from ai_office import OfficeService
from test_ai_office import office, upload, Worker


def job(**changes):
    return NS(**(dict(status='failed', source_title='Sumber belum menghasilkan video',
        error='Koneksi jalur unduh YouTube terputus saat mengunduh video. password=secret Workspace dan seluruh file sementara proses gagal telah dihapus.',
        progress_detail='Proses gagal; tidak ada hasil final yang dapat dipertahankan',
        clips=[], candidates=[], request=NS(target_platform='standard',scheduled_public_source_credit=True,review_only=False)) | changes))


def test_empty_failure_is_delegated_and_does_not_close_until_observed_absent(office):
    service, api=office
    api.jobs['failed']=job()
    api.process_autonomous_history_once=lambda:api.calls.append('guarded-cleanup') or 0
    assert service.run_once()==1
    row=service.snapshot()['incidents'][0]
    assert row['department']=='cleanup' and row['state']=='waiting'
    assert row['id']=='job:failed' and row['first_seen_at']
    assert 'secret' not in json.dumps(service.snapshot())
    assert service.run_once()==0 and api.calls==['guarded-cleanup']
    del api.jobs['failed']
    service.run_once()
    result=service.snapshot()
    assert result['incidents']==[] and result['resolved_incidents'][0]['state']=='resolved'
    restored=OfficeService(api);restored._load()
    assert restored.incidents['job:failed']['state']=='resolved'


def test_access_failure_requires_action_without_automatically_repeating_source(office):
    service, api=office
    api.jobs['login']=job(error='YouTube meminta login atau verifikasi dan sesi tersimpan belum diterima')
    api.process_autonomous_history_once=lambda:pytest.fail('Access failures are not blindly repeated or cleaned')
    assert service.run_once()==0
    row=service.snapshot()['incidents'][0]
    assert row['state']=='needs_operator' and row['destination']=='settings' and not row['automatic']


@pytest.mark.parametrize('kind',['review','facebook','manual','cleanup_paused'])
def test_ownership_and_operator_holds_are_preserved(office,kind):
    service, api=office
    row=job()
    if kind=='review':row.status='completed';row.clips=[NS(render_qc_blocking=False)];row.request.publication_review_required=True
    if kind=='facebook':row.request.target_platform='facebook'
    if kind=='manual':row.request.scheduled_public_source_credit=False
    if kind=='cleanup_paused':api.flags['AUTO_UPLOAD_TERMINAL_CLEANUP_ENABLED']=False
    api.jobs['keep']=row
    api.process_autonomous_history_once=lambda:pytest.fail('Unapproved cleanup')
    assert service.run_once()==0 and api.jobs['keep'] is row


def test_unknown_tiktok_post_only_wakes_verification_without_touching_upload_identity(office):
    service, api=office
    api.flags['UPLOAD_ATTENTION_AUTOMATIC_ENABLED']=True
    api.upload_attention_service.thread=Worker()
    record=upload(status='failed')
    record.logs=['POST_SUBMIT_INTENT: before click'];record.id='same-upload';record.source_job_id='source'
    record.caption='Keep complete caption';record.visibility='only_you';record.error='network problem'
    api.tiktok_uploads[record.id]=record
    before=dict(vars(record))
    assert service.run_once()==1
    assert api.upload_attention_service.wakeup.is_set()
    assert vars(api.tiktok_uploads[record.id])==before
    row=service.snapshot()['incidents'][0]
    assert row['action']=='verify_upload' and row['state']=='waiting'
    assert not api.tiktok_retry_sweeper_wakeup.is_set()


def test_director_requests_pre_file_retry_through_original_owner_only(office):
    service, api=office
    api.flags['TIKTOK_AUTOMATIC_RETRY_ENABLED']=True;api.tiktok_retry_sweeper_thread=Worker()
    record=upload(status='failed');record.logs=[]
    record.error='TikTok tidak dapat dibuka: Page.goto: net::ERR_ADDRESS_UNREACHABLE at https://www.tiktok.com/@target'
    api.tiktok_uploads['same']=record
    assert service.run_once()==1 and api.tiktok_retry_sweeper_wakeup.is_set()
    assert api.tiktok_uploads['same'] is record and record.status=='failed'


def test_missing_scheduled_upload_is_rechecked_by_existing_quota_aware_owner(office):
    service, api=office
    api.cron_enabled=True;api.auto_viral_scheduler_thread=Worker()
    api.jobs['ready']=job(status='completed',error=None,clips=[NS(render_qc_blocking=False)])
    api.queue_missing_scheduled_uploads_once=lambda:api.calls.append('missing-upload-check') or {}
    assert service.run_once()==1 and api.calls==['missing-upload-check']
    assert service.snapshot()['incidents'][0]['state']=='waiting'
    assert service.run_once()==0
    assert not api.youtube_uploads and not api.tiktok_uploads


def test_missing_provider_evidence_routes_to_existing_cron_without_automatic_approval(office):
    service, api=office
    api.cron_life_story_status=lambda:dict(enabled=True,state='waiting_for_provider_rights')
    assert service.run_once()==0
    row=service.snapshot()['incidents'][0]
    assert row['id']=='policy:story-rights' and row['state']=='waiting' and not row['automatic']
    assert row['action']=='use_supported_cron'
    assert service.snapshot()['director']['needs_operator']==0
    api.cron_enabled=True;api.auto_viral_scheduler_thread=Worker()
    assert service.run_once()==1 and api.auto_viral_scheduler_wakeup.is_set()
    assert service.snapshot()['incidents'][0]['automatic'] is True


def test_facebook_recovery_is_delegated_once_without_replaying_uploads(office):
    service,api=office
    api.facebook.update(enabled=True,worker_running=True,qc_wait_count=1,failed_upload_count=3)
    api.request_facebook_recovery=lambda:api.calls.append('facebook-recovery') or True
    assert service.run_once()==1 and api.calls==['facebook-recovery']
    assert all(r['automatic'] for r in service.snapshot()['incidents'])
    assert service.run_once()==0


def test_unavailable_observation_cannot_resolve_known_blockers(office,monkeypatch):
    service, api=office
    api.jobs['failed']=job();service.run_once()
    saved=dict(service.incidents['job:failed'])
    def unavailable():raise OSError('secret-key')
    monkeypatch.setattr(service,'context',unavailable)
    service.run_once()
    assert service.incidents['job:failed']==saved
    assert service.snapshot()['incident_observation_available'] is False


def test_bad_incident_journal_cannot_dispatch_and_is_preserved(office):
    service, api=office
    contents='{"version":1,"tasks":[],"assignments":{},"incidents":{"x":{"id":"x","state":"approved"}}}'
    service.path.write_text(contents);api.cron_enabled=True
    assert service.run_once()==0 and not api.calls
    assert service.path.read_text()==contents


def test_board_limit_does_not_mark_unshown_incidents_resolved(office):
    service, api=office
    for index in range(105):api.jobs[str(index)]=job(request=NS(target_platform='standard'))
    service.run_once()
    snapshot=service.snapshot()
    assert snapshot['director']['open_incidents']==105 and len(snapshot['incidents'])==100
    assert not snapshot['resolved_incidents']
    service.run_once()
    assert not service.snapshot()['resolved_incidents']


def test_one_owner_signal_covers_the_entire_backlog_without_repeating_for_every_card(office):
    service, api=office
    for index in range(30):api.jobs[str(index)]=job()
    api.process_autonomous_history_once=lambda:api.calls.append('cleanup-owner') or 0
    assert service.run_once()==1 and api.calls==['cleanup-owner']
    assert service.snapshot()['director']['open_incidents']==30
    assert service.run_once()==0 and api.calls==['cleanup-owner']


def test_facebook_qc_and_unknown_posts_stay_with_their_platform_owner(office):
    service, api=office
    api.facebook.update(qc_wait_count=2, failed_upload_count=1, unknown_post_count=1)
    assert service.run_once()==0
    rows=service.snapshot()['incidents']
    assert len(rows)==2 and all(row['destination']=='facebook' for row in rows)
    assert all(not row['automatic'] for row in rows)
    assert not api.calls


def test_unknown_source_failure_cannot_promise_automatic_cleanup(office):
    service, api=office
    api.jobs['unknown']=job(error='Unknown worker error')
    api.process_autonomous_history_once=lambda:pytest.fail('No terminal cleanup proof')
    assert service.run_once()==0
    assert service.snapshot()['incidents'][0]['automatic'] is False


def test_exhausted_tiktok_budget_cannot_be_restarted_by_the_director(office):
    service, api=office
    api.flags['TIKTOK_AUTOMATIC_RETRY_ENABLED']=True;api.tiktok_retry_sweeper_thread=Worker()
    record=upload(status='failed');record.logs=[];record.auto_retry_count=3
    record.error='TikTok tidak dapat dibuka: Page.goto: net::ERR_ADDRESS_UNREACHABLE at https://www.tiktok.com/@target'
    api.tiktok_uploads['exhausted']=record
    assert service.run_once()==0 and not api.tiktok_retry_sweeper_wakeup.is_set()
    assert service.snapshot()['incidents'][0]['automatic'] is False


def test_facebook_office_observation_reports_real_qc_and_upload_counters(tmp_path,monkeypatch):
    import api as runtime
    monkeypatch.setattr(runtime,'JOBS_PATH',tmp_path/'jobs.json')
    state=dict(schema=1,session={},autopilot={'enabled':False},
        autopilot_runs={'qc':{'status':'qc_wait','message':'Review belum lengkap'}},uploads={
        'unknown':{'status':'failed','submission_started':True,'upload_confirmed':False},
        'confirmed':{'status':'completed','submission_started':True,'upload_confirmed':True},
        'preflight':{'status':'failed','submission_started':False,'upload_confirmed':False}})
    path=tmp_path/'facebook_workspace.json';path.write_text(json.dumps(state))
    result=runtime.facebook_office_snapshot()
    assert result['qc_wait_count']==1 and result['failed_upload_count']==2 and result['unknown_post_count']==1
    assert result['activity_available'] is True
    assert len(result['activity_work'])==1 and result['activity_work'][0]['state']=='blocked'
    assert json.loads(path.read_text())==state
