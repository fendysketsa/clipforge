from types import SimpleNamespace as NS

import pytest

from browser_page_activity import start_background_page_activity, stop_background_page_activity


def test_activation_is_scoped_to_page_and_reverts_focus_before_detaching():
    calls=[];page=NS()
    session=NS(send=lambda name,args:calls.append((name,args)),detach=lambda:calls.append(('detach',None)))
    page.context=NS(new_cdp_session=lambda target:session if target is page else pytest.fail('Wrong page'))
    active=start_background_page_activity(page)
    stop_background_page_activity(active)
    assert calls==[('Page.setWebLifecycleState',{'state':'active'}),
        ('Emulation.setFocusEmulationEnabled',{'enabled':True}),
        ('Emulation.setFocusEmulationEnabled',{'enabled':False}),('detach',None)]


def test_failure_before_upload_detaches_and_does_not_continue():
    calls=[]
    def send(name,args):
        calls.append((name,args))
        if args.get('enabled') is True:raise RuntimeError('CDP unsupported')
    session=NS(send=send,detach=lambda:calls.append(('detach',None)))
    page=NS(context=NS(new_cdp_session=lambda target:session))
    with pytest.raises(RuntimeError,match='belum ada transfer atau Post'):
        start_background_page_activity(page)
    assert calls[-2:]==[('Emulation.setFocusEmulationEnabled',{'enabled':False}),('detach',None)]


def test_cleanup_after_closed_page_remains_safe():
    def closed(*a,**k):raise RuntimeError('Target page closed')
    stop_background_page_activity(NS(send=closed,detach=closed))
    stop_background_page_activity(None)
