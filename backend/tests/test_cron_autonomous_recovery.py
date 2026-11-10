"""Scheduler recovery must operate without a UI or generic upload sweeper."""
from types import SimpleNamespace

import pytest

import api


def campaign(key='scheduled', *, trigger='schedule', youtube=True, tiktok=True, long=True, news=False):
    return api.AutoViralRun(id=key, status='completed', trigger=trigger,
        created_at=api.now_iso(), updated_at=api.now_iso(),
        request=api.AutoViralRequest(auto_upload_youtube=youtube, auto_upload_tiktok=tiktok,
            auto_publish_paired_long_video=long, cron_theme_key=api.NEWS_HOT_THEME if news else ''),
        processed=[{'job_id':key+'-short','repair_job_id':key+'-repair','long_job_id':key+'-long'}])


@pytest.fixture
def cron(monkeypatch):
    monkeypatch.setenv('AUTO_VIRAL_SCHEDULE_ENABLED','true')
    monkeypatch.setenv('AUTO_VIRAL_SCHEDULE_AUTO_UPLOAD_YOUTUBE','true')
    monkeypatch.setenv('AUTO_VIRAL_SCHEDULE_AUTO_UPLOAD_TIKTOK','true')
    monkeypatch.setenv('AUTO_VIRAL_SCHEDULE_PAIRED_LONG_AUTO_PUBLIC','true')
    monkeypatch.setenv('AUTO_UPLOAD_COMPLETED_JOBS','false')
    run=campaign()
    api.auto_viral_runs[run.id]=run
    return run


def test_source_ownership_excludes_manual_and_review_only_news(cron):
    for row in (campaign('manual',trigger='manual'),campaign('news',news=True),
                campaign('review',youtube=False,tiktok=False,long=False)):
        api.auto_viral_runs[row.id]=row
    for platform in ('youtube','tiktok'):
        assert api.scheduled_upload_recovery_source_ids(platform)=={'scheduled-short','scheduled-repair','scheduled-long'}


def test_each_format_and_platform_respects_original_upload_request(cron):
    api.auto_viral_runs[cron.id]=campaign(youtube=False,tiktok=True,long=False)
    assert api.scheduled_upload_recovery_source_ids('youtube')==set()
    assert api.scheduled_upload_recovery_source_ids('tiktok')=={'scheduled-short','scheduled-repair','scheduled-long'}
    api.auto_viral_runs[cron.id]=campaign(youtube=False,tiktok=False,long=True)
    assert api.scheduled_upload_recovery_source_ids('youtube')=={'scheduled-long'}
    assert api.scheduled_upload_recovery_source_ids('tiktok')==set()


def test_cron_tick_runs_both_recoveries_while_generic_operator_is_off(cron,monkeypatch):
    calls=[]
    def recover(platform):
        def run(*,source_job_ids):
            calls.append((platform,source_job_ids));return 1
        return run
    monkeypatch.setattr(api,'queue_youtube_draft_recoveries_once',recover('youtube'))
    monkeypatch.setattr(api,'queue_retryable_tiktok_uploads_once',recover('tiktok'))
    assert api.queue_scheduled_upload_recoveries_once()=={'youtube':1,'tiktok':1}
    assert [platform for platform,ids in calls]==['youtube','tiktok']
    assert all(ids=={'scheduled-short','scheduled-repair','scheduled-long'} for _,ids in calls)
    state=api.auto_viral_upload_recovery_status
    assert state['last_tick_at'] and state['errors']=={} and state['queued']=={'youtube':1,'tiktok':1}


def test_failure_in_youtube_does_not_stop_tiktok_or_next_tick(cron,monkeypatch):
    attempts=[]
    def youtube(**kwargs):
        attempts.append(1)
        if len(attempts)==1:raise OSError('temporary checkpoint read')
        return 1
    monkeypatch.setattr(api,'queue_youtube_draft_recoveries_once',youtube)
    monkeypatch.setattr(api,'queue_retryable_tiktok_uploads_once',lambda **kwargs:1)
    assert api.queue_scheduled_upload_recoveries_once()=={'youtube':0,'tiktok':1}
    assert api.auto_viral_upload_recovery_status['errors']=={'youtube':'OSError'}
    assert api.queue_scheduled_upload_recoveries_once()=={'youtube':1,'tiktok':1}
    assert api.auto_viral_upload_recovery_status['errors']=={}


def test_disabled_cron_or_no_requested_platform_cannot_start_recovery(cron,monkeypatch):
    monkeypatch.setattr(api,'queue_youtube_draft_recoveries_once',lambda **k:pytest.fail('YouTube recovery started'))
    monkeypatch.setattr(api,'queue_retryable_tiktok_uploads_once',lambda **k:pytest.fail('TikTok recovery started'))
    monkeypatch.setenv('AUTO_VIRAL_SCHEDULE_ENABLED','false')
    assert api.queue_scheduled_upload_recoveries_once()=={'youtube':0,'tiktok':0}
    monkeypatch.setenv('AUTO_VIRAL_SCHEDULE_ENABLED','true')
    for key in ('AUTO_VIRAL_SCHEDULE_AUTO_UPLOAD_YOUTUBE','AUTO_VIRAL_SCHEDULE_AUTO_UPLOAD_TIKTOK',
                'AUTO_VIRAL_SCHEDULE_PAIRED_LONG_AUTO_PUBLIC'):
        monkeypatch.setenv(key,'false')
    assert api.queue_scheduled_upload_recoveries_once()=={'youtube':0,'tiktok':0}


def test_real_scheduler_invokes_recovery_while_another_campaign_is_active(cron,monkeypatch):
    waits=[];recovery_calls=[]
    monkeypatch.setattr(api,'auto_viral_schedule_enabled',lambda:not waits)
    monkeypatch.setattr(api,'auto_viral_active_run_id','rendering-campaign')
    monkeypatch.setattr(api,'queue_scheduled_upload_recoveries_once',lambda:recovery_calls.append(1))
    for name in ('reconcile_stalled_scheduled_upload_runs','queue_youtube_private_buffer_promotions_once',
                 'reconcile_interrupted_scheduled_clip_runs','queue_review_long_qc_once','queue_review_long_once'):
        monkeypatch.setattr(api,name,lambda *a:0)
    monkeypatch.setattr(api,'latest_scheduled_auto_viral_run',lambda:None)
    monkeypatch.setattr(api,'pending_scheduled_auto_viral_upload_run',lambda:None)
    monkeypatch.setattr(api,'auto_viral_next_run_at',lambda *a:None)
    monkeypatch.setattr(api,'auto_viral_scheduler_wakeup',SimpleNamespace(wait=waits.append,clear=lambda:None))
    api.auto_viral_scheduler_loop()
    assert recovery_calls==[1] and waits==[15.0]


def test_actual_draft_is_automatically_requeued_with_same_id_and_saved_metadata(cron,monkeypatch):
    monkeypatch.setenv('YOUTUBE_AUTO_RECOVER_DRAFTS','true')
    monkeypatch.setenv('AUTO_VIRAL_SCHEDULE_AUTO_UPLOAD_TIKTOK','false')
    stamp=api.now_iso()
    template=api.YouTubeUploadJob(id='manual-draft',source_job_id='manual-job',
        clip_url='/outputs/manual-job/video.mp4',clip_name='video.mp4',title='Reviewed title',
        description='Reviewed description',visibility='private',status='failed',created_at=stamp,
        updated_at=stamp,video_url='https://www.youtube.com/watch?v=abcdefghijk',
        error='ID draft aktif berubah; perubahan metadata dihentikan.')
    target=template.model_copy(update={'id':'cron-draft','source_job_id':'scheduled-short',
        'clip_url':'/outputs/scheduled-short/video.mp4','video_url':'https://www.youtube.com/watch?v=lmnopqrstuv'})
    api.youtube_uploads.update({template.id:template,target.id:target})
    queued=[]
    monkeypatch.setattr(api,'queue_youtube_upload_jobs',lambda rows:queued.extend(rows))
    assert api.queue_scheduled_upload_recoveries_once()['youtube']==1
    assert [row.id for row in queued]==['cron-draft']
    assert queued[0].video_url==target.video_url and queued[0].description==target.description
    assert api.youtube_uploads['manual-draft'].status=='failed'
    command=api.build_youtube_restart_verification_command(queued[0])
    assert command[2]=='verify-upload' and target.video_url in command and target.clip_url not in command
