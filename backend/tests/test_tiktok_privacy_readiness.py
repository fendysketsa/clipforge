from types import SimpleNamespace

import pytest

import tiktok_uploader as uploader
from automatic_retry import tiktok_retry_reason


class Control:
    def __init__(self, *, visible=True, enabled=True, expanded=False):
        self.visible=visible;self.enabled=enabled;self.expanded=expanded;self.keys=[];self.focused=False
    def click(self, **kwargs):
        raise TimeoutError('element is not stable')
    def is_visible(self):return self.visible
    def is_enabled(self):return self.enabled
    def get_attribute(self, name):return 'true' if self.expanded else 'false'
    def focus(self, **kwargs):self.focused=True
    def press(self, key, **kwargs):self.keys.append(key)


def test_background_privacy_button_uses_native_keyboard_after_modal_check(monkeypatch):
    control=Control()
    monkeypatch.setattr(uploader,'dismiss_blocking_modal',lambda p:(True,''))
    uploader.activate_privacy_control(object(),control)
    assert control.focused and control.keys==['Enter']


@pytest.mark.parametrize('kind', ['modal','hidden','disabled','already_open'])
def test_picker_recovery_never_interacts_through_blocker_or_closes_open_menu(monkeypatch,kind):
    control=Control(visible=kind!='hidden',enabled=kind!='disabled',expanded=kind=='already_open')
    monkeypatch.setattr(uploader,'dismiss_blocking_modal',lambda p:(kind!='modal','blocking dialog'))
    if kind=='already_open':uploader.activate_privacy_control(object(),control)
    else:
        with pytest.raises(uploader.UploadError,match='belum diposting'):
            uploader.activate_privacy_control(object(),control)
    assert not control.focused and not control.keys


def test_selected_value_must_be_on_control_not_elsewhere_on_page():
    trigger=SimpleNamespace(inner_text=lambda **kwargs:'Everyone')
    with pytest.raises(uploader.UploadError,match='belum terverifikasi'):
        uploader.verify_privacy_selection(trigger,r'only you|hanya anda')
    uploader.verify_privacy_selection(trigger,r'everyone|semua orang')


def test_legacy_click_failure_requires_privacy_locator_and_no_post_checkpoint():
    error='Kontrol TikTok tidak dapat diklik karena halaman belum siap. Video belum diposting.'
    logs=['waiting for locator("button:has-text(\\\"Everyone\\\")").first']
    assert tiktok_retry_reason(error,logs)=='privacy_control_not_ready'
    assert tiktok_retry_reason(error,[])==''
    assert tiktok_retry_reason(error,['waiting for button:has-text("Post")'])==''
    assert tiktok_retry_reason(error,logs+['POST_SUBMIT_INTENT: issued'])==''


@pytest.mark.parametrize('setter,current,target',[(uploader.set_only_you,'Everyone','Only you'),
                                              (uploader.set_public,'Only you','Everyone')])
def test_privacy_picker_reads_back_real_selected_value(monkeypatch,setter,current,target):
    state={'value':current}
    trigger=SimpleNamespace(inner_text=lambda **kwargs:state['value'])
    option=object()
    controls=iter([trigger,option,trigger])
    monkeypatch.setattr(uploader,'first_visible',lambda *a,**k:next(controls))
    def activate(page,control):
        if control is option:state['value']=target
    monkeypatch.setattr(uploader,'activate_privacy_control',activate)
    setter(SimpleNamespace(wait_for_timeout=lambda value:None))
    assert state['value']==target


@pytest.mark.parametrize('visibility,value', [('public', '  Everyone\n'), ('only_you', 'Only\n you')])
def test_requested_privacy_already_selected_never_opens_menu(monkeypatch,visibility,value):
    trigger=SimpleNamespace(inner_text=lambda **kwargs:value)
    monkeypatch.setattr(uploader,'first_visible',lambda *a,**k:trigger)
    monkeypatch.setattr(uploader,'activate_privacy_control',lambda *a:pytest.fail('Already selected privacy must not toggle'))
    uploader.configure_requested_privacy(object(),visibility)


@pytest.mark.parametrize('cause,retry', [('Kontrol privasi TikTok belum siap.','privacy_control_not_ready'),
                                        ('CAPTCHA required','')])
def test_privacy_failure_reports_target_and_observation_preserving_safety(monkeypatch,cause,retry):
    def fail(page):raise uploader.UploadError(cause)
    monkeypatch.setattr(uploader,'set_only_you',fail)
    monkeypatch.setattr(uploader,'current_privacy_trigger',lambda page:SimpleNamespace(inner_text=lambda **k:'Everyone'))
    with pytest.raises(uploader.UploadError,match='diminta Only you, terbaca Everyone') as exc:
        uploader.configure_requested_privacy(object(),'only_you')
    assert 'Post belum dikirim' in str(exc.value)
    assert tiktok_retry_reason(str(exc.value),[])==retry
    assert tiktok_retry_reason(str(exc.value),[],accepted=True)==''


def test_processing_privacy_recheck_failure_holds_actual_upload_before_post(monkeypatch,tmp_path,capsys):
    video=tmp_path/'clip.mp4';video.write_bytes(b'original video')
    page=SimpleNamespace(url=uploader.UPLOAD_URL,wait_for_timeout=lambda *a:None)
    clicks=[]
    button=SimpleNamespace(click=lambda **k:clicks.append(True),press=lambda *a,**k:clicks.append(True))
    monkeypatch.setattr(uploader,'tiktok_content_snapshot',lambda *a:(0,set()))
    monkeypatch.setattr(uploader,'exact_existing_tiktok_post',lambda *a:None)
    monkeypatch.setattr(uploader,'goto',lambda *a:None)
    monkeypatch.setattr(uploader,'recover_interrupted_upload_draft',lambda *a:True)
    monkeypatch.setattr(uploader,'dismiss_upload_overlays',lambda *a:None)
    monkeypatch.setattr(uploader,'upload_editor_has_requested_file',lambda *a:True)
    monkeypatch.setattr(uploader,'set_caption',lambda *a:None)
    monkeypatch.setattr(uploader,'wait_for_post_button',lambda *a,**k:button)
    selections=[]
    def select(page):
        selections.append(True)
        if len(selections)==2:raise uploader.UploadError('Kontrol privasi TikTok belum siap.')
    monkeypatch.setattr(uploader,'set_only_you',select)
    monkeypatch.setattr(uploader,'current_privacy_trigger',lambda *a:None)
    with pytest.raises(uploader.UploadError,match='Post belum dikirim'):
        uploader.upload_video(page,video,'Caption',False,'owner')
    assert len(selections)==2 and not clicks
    assert 'POST_SUBMIT_INTENT:' not in capsys.readouterr().out
    assert video.read_bytes()==b'original video'
