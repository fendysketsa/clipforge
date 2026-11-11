import hashlib
import json
from types import SimpleNamespace as NS

import pytest

import api
import automatic_retry
from test_tiktok_caption_recovery import failed_caption


RESTART='Backend restart saat upload TikTok berlangsung. Periksa TikTok Studio sebelum retry agar tidak membuat posting duplikat.'
URL='https://www.tiktok.com/@titikbalikislami/video/7706778926332251393'


@pytest.fixture
def restarted_short(failed_caption,monkeypatch):
    path,upload,started=failed_caption
    upload.error=RESTART;upload.auto_retry_count=1
    upload.logs=['TARGET_ACCOUNT_CONFIRMED:@titikbalikislami','POST_BASELINE_VISIBLE_IDS:5']
    clip=api.jobs[upload.source_job_id].clips[0];clip.render_qc_passed=True
    monkeypatch.setattr(api,'check_tiktok_session',lambda:NS(ok=True))
    return path,upload,started


def test_restart_recovery_reuses_id_and_remaining_budget_after_live_validation(restarted_short):
    _,upload,_=restarted_short
    recovered=api.retry_failed_tiktok_short(upload.id)
    assert recovered.status=='queued' and recovered.id==upload.id and recovered.auto_retry_count==2
    assert recovered.caption==upload.caption and recovered.visibility==upload.visibility
    assert recovered.auto_retry_reason=='restart_before_post_revalidated'
    assert api.retry_failed_tiktok_short(upload.id).auto_retry_count==2


@pytest.mark.parametrize('risk',['started','accepted','intent','url','budget','qc','review_hold','long','wrong_account','hash','rights','session'])
def test_short_retry_keeps_post_budget_review_and_file_guards(restarted_short,monkeypatch,risk):
    path,upload,_=restarted_short;job=api.jobs[upload.source_job_id];clip=job.clips[0]
    if risk=='started':upload.submission_started=True
    if risk=='accepted':upload.submission_accepted=True
    if risk=='intent':upload.logs+=['POST_SUBMIT_INTENT: issued']
    if risk=='url':upload.profile_url=URL
    if risk=='budget':upload.auto_retry_count=3
    if risk=='qc':clip.render_qc_passed=False
    if risk=='review_hold':job.request.publication_review_required=True
    if risk=='long':job.request.clip_mode='highlight_5m'
    if risk=='wrong_account':upload.target_handle='different'
    if risk=='hash':path.write_bytes(b'changed')
    if risk=='rights':monkeypatch.setattr(api,'youtube_monetization_preflight_issue',lambda *_:'held')
    if risk=='session':monkeypatch.setattr(api,'check_tiktok_session',lambda:NS(ok=False,error='not ready',message=''))
    with pytest.raises(api.HTTPException):api.retry_failed_tiktok_short(upload.id)
    assert api.tiktok_uploads[upload.id].status=='failed'


def test_restart_needs_actual_prior_account_and_baseline_evidence():
    assert automatic_retry.tiktok_verified_session_recovery_reason(RESTART,[])==''
    assert automatic_retry.tiktok_verified_session_recovery_reason(RESTART,['TARGET_ACCOUNT_CONFIRMED:@target','POST_BASELINE_VISIBLE_IDS:unavailable'])==''
    assert automatic_retry.tiktok_verified_session_recovery_reason(RESTART,['TARGET_ACCOUNT_CONFIRMED:@target','POST_BASELINE_VISIBLE_IDS:0'])=='restart_before_post_revalidated'


@pytest.fixture
def remote_verification(failed_caption,monkeypatch):
    _,upload,_=failed_caption
    # Remote reconciliation must not depend on deleted local source/media.
    api.jobs.clear()
    monkeypatch.setattr(api,'tiktok_cdp_ready',lambda:True)
    monkeypatch.setattr(api,'output_path_from_url',lambda *_:pytest.fail('Verifier inspected media'))
    canonical=' '.join(upload.caption.split())
    proof={'video_url':URL,'visibility':upload.visibility,'caption_sha256':hashlib.sha256(canonical.encode()).hexdigest()}
    commands=[]
    def run(command,**_):
        commands.append(command)
        return NS(returncode=0,stdout='REMOTE_POST_CONFIRMED:'+json.dumps(proof),stderr='')
    monkeypatch.setattr(api.subprocess,'run',run)
    return upload,proof,commands


def test_exact_remote_post_can_reconcile_record_after_local_cleanup(remote_verification):
    upload,_,commands=remote_verification
    recovered=api.reconcile_tiktok_remote_post(upload.id,api.TikTokRemoteVerifyRequest(video_url=URL))
    assert recovered.status=='completed' and recovered.upload_confirmed and recovered.profile_url==URL
    assert recovered.auto_retry_count==upload.auto_retry_count
    assert len(commands)==1 and 'verify-post' in commands[0] and 'upload' not in commands[0]
    assert not api.social_upload_execution_lock.locked()


@pytest.mark.parametrize('risk',['caption','visibility','url','malformed','failure','state_changed'])
def test_remote_mismatch_cannot_confirm_or_clear_failed_record(remote_verification,monkeypatch,risk):
    upload,proof,_=remote_verification
    if risk=='caption':proof['caption_sha256']='wrong'
    if risk=='visibility':proof['visibility']='public'
    if risk=='url':proof['video_url']=URL.replace('7706778926332251393','7706778926332251394')
    if risk=='malformed':monkeypatch.setattr(api.subprocess,'run',lambda *a,**k:NS(returncode=0,stdout='REMOTE_POST_CONFIRMED:bad-json',stderr=''))
    if risk=='failure':monkeypatch.setattr(api.subprocess,'run',lambda *a,**k:NS(returncode=2,stdout='USER_ERROR:No match',stderr=''))
    if risk=='state_changed':
        def changed(*a,**k):
            api.tiktok_uploads[upload.id]=upload.model_copy(update={'updated_at':'changed'})
            return NS(returncode=0,stdout='REMOTE_POST_CONFIRMED:'+json.dumps(proof),stderr='')
        monkeypatch.setattr(api.subprocess,'run',changed)
    with pytest.raises(api.HTTPException):api.reconcile_tiktok_remote_post(upload.id,api.TikTokRemoteVerifyRequest(video_url=URL))
    assert not api.tiktok_uploads[upload.id].upload_confirmed
    assert not api.social_upload_execution_lock.locked()


@pytest.mark.parametrize('risk',['foreign_url','wrong_account','long','active','busy','browser_down'])
def test_remote_verification_rejects_wrong_scope_or_busy_browser(remote_verification,monkeypatch,risk):
    upload,_,commands=remote_verification;url=URL
    if risk=='foreign_url':url='https://example.com/'+URL
    if risk=='wrong_account':upload.target_handle='different'
    if risk=='long':upload.clip_name='resume_cerita_5menit_example.mp4'
    if risk=='active':upload.status='running'
    if risk=='browser_down':monkeypatch.setattr(api,'tiktok_cdp_ready',lambda:False)
    if risk=='busy':api.social_upload_execution_lock.acquire()
    try:
        with pytest.raises(api.HTTPException):api.reconcile_tiktok_remote_post(upload.id,api.TikTokRemoteVerifyRequest(video_url=url))
    finally:
        if risk=='busy':api.social_upload_execution_lock.release()
    assert not commands
