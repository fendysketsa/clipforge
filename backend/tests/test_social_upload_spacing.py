from datetime import datetime,timedelta,timezone
import threading
import time
from types import SimpleNamespace as NS

import api
import tiktok_uploader as tt
import youtube_uploader as yt
import pytest


def row(key='upload',status='completed',finished=None,dry=False):
    return api.YouTubeUploadJob(id=key,source_job_id='job',status=status,created_at=api.now_iso(),updated_at=api.now_iso(),
        clip_url='/outputs/job/a.mp4',clip_name='a.mp4',title='Judul sumber',description='Deskripsi sumber.',
        started_at=api.now_iso(),finished_at=finished,dry_run=dry)


def test_shared_gap_uses_durable_finish_and_longer_failure_delay(monkeypatch):
    now=datetime.now(timezone.utc)
    monkeypatch.delenv('SOCIAL_UPLOAD_MIN_GAP_SECONDS',raising=False)
    monkeypatch.delenv('SOCIAL_UPLOAD_FAILURE_GAP_SECONDS',raising=False)
    api.youtube_uploads['yt']=row(finished=(now-timedelta(seconds=15)).isoformat())
    assert api.social_upload_cooldown_remaining(now)==30
    api.tiktok_uploads['tt']=NS(status='failed',dry_run=False,started_at=now.isoformat(),finished_at=(now-timedelta(seconds=10)).isoformat())
    assert api.social_upload_cooldown_remaining(now)==80
    api.tiktok_uploads['tt'].dry_run=True
    assert api.social_upload_cooldown_remaining(now)==30
    api.youtube_uploads.clear()
    assert api.social_upload_cooldown_remaining(now)==0


def test_two_platform_workers_never_run_browser_uploads_concurrently(monkeypatch):
    api.youtube_uploads['yt']=row('yt',status='queued')
    api.tiktok_uploads['tt']=NS(id='tt',status='queued',logs=[])
    entered=threading.Event();release=threading.Event();second=threading.Event()
    monkeypatch.setattr(api,'social_upload_cooldown_remaining',lambda:0)
    def first(_):
        entered.set();assert release.wait(2)
    monkeypatch.setattr(api,'run_youtube_upload',first)
    monkeypatch.setattr(api,'run_tiktok_upload',lambda _:second.set())
    a=threading.Thread(target=api.execute_social_upload,args=('youtube','yt'))
    b=threading.Thread(target=api.execute_social_upload,args=('tiktok','tt'))
    a.start();assert entered.wait(1)
    b.start()
    try:assert not second.wait(.05)
    finally:release.set();a.join(2);b.join(2)
    assert second.is_set() and not a.is_alive() and not b.is_alive()


def test_cancelled_or_deleted_queue_entry_never_starts_after_cooldown(monkeypatch):
    api.youtube_uploads['yt']=row('yt',status='queued')
    monkeypatch.setattr(api,'social_upload_cooldown_remaining',lambda:30)
    monkeypatch.setattr(api,'save_youtube_uploads_unlocked',lambda:None)
    monkeypatch.setattr(api.time,'sleep',lambda _:api.youtube_uploads.pop('yt',None))
    monkeypatch.setattr(api,'run_youtube_upload',lambda _:pytest.fail('Deleted entry executed'))
    api.execute_social_upload('youtube','yt')


def test_waiting_platform_gets_next_turn_before_busy_worker_can_reacquire(monkeypatch):
    order=[];first_entered=threading.Event();release=threading.Event();waiting=threading.Event()
    def busy_platform():
        with api.social_upload_turn():
            order.append('tt-first');first_entered.set();assert release.wait(2)
        with api.social_upload_turn():order.append('tt-second')
    def waiting_platform():
        waiting.set()
        with api.social_upload_turn():order.append('yt')
    first=threading.Thread(target=busy_platform);second=threading.Thread(target=waiting_platform)
    first.start();assert first_entered.wait(1)
    second.start();assert waiting.wait(1)
    deadline=time.monotonic()+1
    while time.monotonic()<deadline:
        with api.social_upload_turn_condition:
            if len(api.social_upload_waiting_turns)==2:break
        time.sleep(.001)
    else:pytest.fail('Other platform never reserved its turn')
    release.set();first.join(2);second.join(2)
    assert order==['tt-first','yt','tt-second']
    assert not first.is_alive() and not second.is_alive() and not api.social_upload_waiting_turns


def test_failed_upload_releases_turn_for_other_platform():
    with pytest.raises(RuntimeError):
        with api.social_upload_turn():raise RuntimeError('browser disconnected')
    with api.social_upload_turn():assert len(api.social_upload_waiting_turns)==1
    assert not api.social_upload_waiting_turns


class Post:
    def __init__(self,stable=False,enabled=True,visible=True,focused=True):
        self.stable=stable;self.enabled=enabled;self.visible=visible;self.focused=focused;self.real_clicks=0;self.focus_calls=0
    def click(self,**kwargs):
        if not kwargs.get('trial'):self.real_clicks+=1
        if not self.stable:raise TimeoutError('stability timeout')
    def is_visible(self):return self.visible
    def is_enabled(self,**kwargs):return self.enabled
    def get_attribute(self,name,**kwargs):return 'false' if name in {'aria-disabled','data-disabled','data-loading'} else None
    def focus(self,**kwargs):self.focus_calls+=1
    def evaluate(self,script):return self.focused


def test_unstable_post_chooses_keyboard_before_intent_without_sending_a_click(monkeypatch):
    post=Post()
    monkeypatch.setattr(tt,'dismiss_blocking_modal',lambda _:(True,''))
    assert tt.prepare_post_activation(object(),post)=='keyboard'
    assert post.focus_calls==1 and post.real_clicks==0
    stable=Post(stable=True)
    assert tt.prepare_post_activation(object(),stable)=='click' and stable.real_clicks==0


def test_background_post_avoids_trial_to_real_click_stability_race(monkeypatch):
    post=Post(stable=True)
    def no_mouse(**kwargs):pytest.fail('Background post should choose native keyboard before intent')
    post.click=no_mouse
    monkeypatch.setattr(tt,'dismiss_blocking_modal',lambda _:(True,''))
    assert tt.prepare_post_activation(object(),post,prefer_keyboard=True)=='keyboard'
    assert post.focus_calls==1 and post.real_clicks==0


@pytest.mark.parametrize('kind',['modal','disabled','hidden','wrong_focus'])
def test_post_preparation_never_activates_through_blocker_or_wrong_focus(monkeypatch,kind):
    post=Post(enabled=kind!='disabled',visible=kind!='hidden',focused=kind!='wrong_focus')
    monkeypatch.setattr(tt,'dismiss_blocking_modal',lambda _:(kind!='modal','blocker'))
    with pytest.raises(tt.UploadError,match='belum diposting'):
        tt.prepare_post_activation(object(),post)
    assert post.real_clicks==0


def test_legacy_post_intent_error_is_never_labeled_not_posted_or_retryable():
    logs=['POST_SUBMIT_INTENT: attempting Post','USER_ERROR:Uploader TikTok gagal: Locator.click: Timeout 10000ms exceeded.',
          'waiting for locator("post_video_button")']
    error=api.tiktok_error_from_logs(logs)
    assert 'belum pasti' in error and 'belum diposting' not in error
    assert api.automatic_retry.tiktok_retry_reason(error,logs,started=True)==''


def test_exact_native_youtube_field_does_not_depend_on_global_keyboard_focus(monkeypatch):
    edits=[]
    hidden=NS(is_visible=lambda:False)
    active=NS(is_visible=lambda:True,fill=lambda text,**k:edits.append(text),press=lambda *a,**k:None)
    page=NS(locator=lambda selector:NS(all=lambda:[active,hidden]))
    monkeypatch.setattr(yt,'upload_text_field_contains',lambda *a,**k:edits==['Judul yang benar'])
    assert yt.fill_scoped_upload_text_field(page,'Judul yang benar','Judul yang benar',[],[],'title')
    assert edits==['Judul yang benar']
    monkeypatch.setattr(yt,'upload_text_field_contains',lambda *a,**k:False)
    assert not yt.fill_scoped_upload_text_field(page,'Judul yang benar','Judul yang benar',[],[],'title')


def test_future_corrupt_finish_timestamp_cannot_stall_queue_forever():
    now=datetime.now(timezone.utc)
    api.youtube_uploads['future']=row(finished=(now+timedelta(days=100)).isoformat())
    assert api.social_upload_cooldown_remaining(now)==0


def test_confirmed_public_exact_id_is_not_reopened_as_a_stale_scheduled_draft(monkeypatch,tmp_path):
    state=tmp_path/'state.json';state.write_text('{}')
    events=[]
    context=NS(new_page=lambda:NS(),storage_state=lambda **k:None,close=lambda:None)
    browser=NS(new_context=lambda **k:context,close=lambda:None)
    class Playwright:
        def __enter__(self):return NS(chromium=NS(launch=lambda **k:browser))
        def __exit__(self,*a):return False
    monkeypatch.setattr(yt,'import_playwright',lambda:(Playwright,TimeoutError))
    for name in ['install_context_dialog_guard','install_browser_dialog_guard','goto_studio','ensure_logged_in','ensure_target_identity']:
        monkeypatch.setattr(yt,name,lambda *a,**k:None)
    monkeypatch.setattr(yt,'verify_saved_video_in_studio',lambda page,title,visibility,**k:
        'https://www.youtube.com/watch?v=abcDEF12345' if visibility=='public' else pytest.fail('Should use confirmed public ID'))
    monkeypatch.setattr(yt,'verify_saved_video_metadata',lambda *a:events.append('exact metadata verified'))
    monkeypatch.setattr(yt,'resume_saved_draft_and_finalize',lambda *a,**k:pytest.fail('Already public must not resume draft'))
    monkeypatch.setattr(yt,'schedule_saved_video',lambda *a,**k:pytest.fail('Already public must not reschedule'))
    monkeypatch.setattr(yt,'log',events.append)
    args=NS(state=str(state),use_cdp=False,headless=True,timeout=30,title='Judul sumber yang benar',description='Deskripsi sumber utuh.',
        target_channel='channel',target_email='',target_channel_id='UCtarget',studio_url='https://studio.youtube.com',
        publish_at='2026-11-12T02:15:00+00:00',visibility='public',video_url='https://www.youtube.com/watch?v=abcDEF12345',
        schedule_existing=False,tags='',content_type='shorts')
    yt.run_verify_upload(args)
    assert events.index('exact metadata verified') < next(i for i,v in enumerate(events) if v.startswith('EXISTING_PUBLICATION_CONFIRMED:'))
    assert any(v.startswith('UPLOAD_CONFIRMED:') for v in events)
    assert not any(v.startswith('SCHEDULED_PUBLISH_AT:') for v in events)
