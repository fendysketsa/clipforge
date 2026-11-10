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
    controls=iter([trigger,option])
    monkeypatch.setattr(uploader,'first_visible',lambda *a,**k:next(controls))
    def activate(page,control):
        if control is option:state['value']=target
    monkeypatch.setattr(uploader,'activate_privacy_control',activate)
    setter(SimpleNamespace(wait_for_timeout=lambda value:None))
    assert state['value']==target
