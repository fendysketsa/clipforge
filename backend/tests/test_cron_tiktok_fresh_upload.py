from types import SimpleNamespace as NS
from pathlib import Path

import pytest

import api
import tiktok_uploader as uploader


@pytest.mark.parametrize('transfer_fails',[False,True])
def test_cron_attempt_never_calls_continue_even_when_transfer_errors(monkeypatch,tmp_path,transfer_fails):
    path=tmp_path/'clip.mp4';path.write_bytes(b'approved source file')
    events=[]
    class File:
        def wait_for(self,**k):pass
        def set_input_files(self,path,**k):
            events.append('transfer')
            if transfer_fails:raise TimeoutError('CDP upload timeout')
    page=NS(url=uploader.UPLOAD_URL,wait_for_timeout=lambda *a:None,
        locator=lambda selector:NS(first=File()))
    monkeypatch.setattr(uploader,'tiktok_content_snapshot',lambda *a:(0,set()))
    monkeypatch.setattr(uploader,'goto',lambda *a:None)
    monkeypatch.setattr(uploader,'discard_cron_upload_draft',lambda *a:events.append('discard') or True)
    monkeypatch.setattr(uploader,'recover_interrupted_upload_draft',lambda *a:pytest.fail('Cron cannot choose Continue'))
    monkeypatch.setattr(uploader,'dismiss_upload_overlays',lambda *a:None)
    monkeypatch.setattr(uploader,'upload_editor_has_requested_file',lambda *a:True)
    monkeypatch.setattr(uploader,'save_debug',lambda *a:None)
    monkeypatch.setattr(uploader,'set_caption',lambda *a:events.append('caption'))
    monkeypatch.setattr(uploader,'set_only_you',lambda *a:None)
    if transfer_fails:
        with pytest.raises(uploader.UploadError,match='gagal sebelum posting'):
            uploader.upload_video(page,path,'Approved caption',True,'owner',remote_browser=True,cron_fresh_upload=True)
        assert events==['discard','transfer','discard']
    else:
        uploader.upload_video(page,path,'Approved caption',True,'owner',remote_browser=True,cron_fresh_upload=True)
        assert events==['discard','transfer','caption']
    assert path.read_bytes()==b'approved source file'


@pytest.mark.parametrize('cron',[False,True])
def test_only_scheduler_owned_source_gets_discard_policy_command(monkeypatch,tmp_path,cron):
    path=tmp_path/'clip.mp4';path.write_bytes(b'media')
    job=api.ClipJob(id='job',status='completed',created_at=api.now_iso(),updated_at=api.now_iso(),
        request=api.ClipJobRequest(scheduled_public_source_credit=cron))
    api.jobs[job.id]=job
    monkeypatch.setattr(api,'output_path_from_url',lambda *a:path)
    monkeypatch.setattr(api,'build_tiktok_base_command',lambda **k:['uploader'])
    monkeypatch.setattr(api,'tiktok_cdp_ready',lambda:False)
    row=api.TikTokUploadJob(id='upload',source_job_id=job.id,clip_url='/outputs/clip.mp4',clip_name='clip.mp4',
        status='queued',created_at=api.now_iso(),updated_at=api.now_iso(),caption='Caption',target_handle='owner')
    command=api.build_tiktok_upload_command(row)
    assert ('--cron-fresh-upload' in command)==cron


def test_cron_worker_owns_and_closes_its_page_instead_of_selecting_user_tabs(monkeypatch,tmp_path):
    media=tmp_path/'clip.mp4';media.write_bytes(b'media')
    events=[]
    page=NS(set_default_timeout=lambda *a:None,close=lambda:events.append('own-page-closed'))
    context=NS(new_page=lambda:page)
    browser=NS(close=lambda:pytest.fail('Persistent Chrome must stay open'))
    class Playwright:
        def __enter__(self):return NS()
        def __exit__(self,*a):return False
    monkeypatch.setattr(uploader,'import_playwright',lambda:(Playwright,TimeoutError))
    monkeypatch.setattr(uploader,'open_context',lambda *a:(context,browser))
    monkeypatch.setattr(uploader,'select_tiktok_page',lambda *a:pytest.fail('Must not select user or audit tabs'))
    monkeypatch.setattr(uploader,'start_background_page_activity',lambda *a:None)
    monkeypatch.setattr(uploader,'validate_target_account',lambda p,*a:events.append('identity') if p is page else pytest.fail('Wrong page'))
    monkeypatch.setattr(uploader,'save_session_state',lambda *a:None)
    monkeypatch.setenv('TIKTOK_MINIMIZE_CDP_BROWSER','false')
    def upload(p,*a,**k):
        assert p is page and k['cron_fresh_upload'];events.append('upload')
    monkeypatch.setattr(uploader,'upload_video',upload)
    args=uploader.build_parser().parse_args(['--cdp-url','http://localhost:9444','upload',str(media),'--cron-fresh-upload'])
    assert uploader.run(args)==0
    assert events==['identity','upload','own-page-closed']
