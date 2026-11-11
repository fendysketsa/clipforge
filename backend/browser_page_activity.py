"""Keep one automated CDP page responsive without raising the user's window."""


def start_background_page_activity(page):
    context = getattr(page, 'context', None)
    create_session = getattr(context, 'new_cdp_session', None)
    if create_session is None:
        return None
    session = create_session(page)
    try:
        session.send('Page.setWebLifecycleState', {'state': 'active'})
        session.send('Emulation.setFocusEmulationEnabled', {'enabled': True})
        return session
    except Exception:
        stop_background_page_activity(session)
        raise RuntimeError('Tab upload belum dapat diaktifkan di background; belum ada transfer atau Post.')


def stop_background_page_activity(session):
    if session is None:
        return
    try:
        session.send('Emulation.setFocusEmulationEnabled', {'enabled': False})
    except Exception:
        pass
    finally:
        try:
            session.detach()
        except Exception:
            pass
