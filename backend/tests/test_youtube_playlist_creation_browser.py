"""Exercise the observed Studio create/search/select sequence in Chromium."""
import shutil

import pytest
import youtube_uploader as uploader


@pytest.fixture
def studio_page(monkeypatch, tmp_path):
    from playwright.sync_api import sync_playwright
    executable = shutil.which('google-chrome') or shutil.which('chromium')
    if not executable:
        pytest.skip('Native Chromium unavailable')
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=executable, headless=True, args=['--no-sandbox'])
        page = browser.new_page()
        page.set_content('''
        <ytcp-video-metadata-playlists><button role="button" id="dropdown" onclick="dialog.hidden=false">Pilih</button></ytcp-video-metadata-playlists>
        <ytcp-playlist-dialog><tp-yt-paper-dialog id="dialog" hidden>
          <ytcp-search-bar id="search-input"><input id="search-input" placeholder="Telusuri playlist" oninput="syncNewButton()"></ytcp-search-bar>
          <div id="playlists-list"><div id="items"></div></div>
          <ytcp-button class="new-playlist-button" aria-disabled="false"><button onclick="menu.hidden=false">Playlist baru</button></ytcp-button>
          <div id="action-menu" hidden><button role="menuitem" test-id="new_playlist" onclick="creation.hidden=false;menu.hidden=true">Playlist baru</button></div>
          <ytcp-button class="done-button"><button onclick="dialog.hidden=true;dropdown.textContent=chosen">Selesai</button></ytcp-button>
        </tp-yt-paper-dialog></ytcp-playlist-dialog>
        <ytcp-playlist-creation-dialog id="creation" hidden>
          <div id="title-textarea"><div contenteditable="true"></div></div>
          <ytcp-button id="create-button"><button onclick="createPlaylist()">Buat</button></ytcp-button>
        </ytcp-playlist-creation-dialog>
        <script>
        const dialog=document.querySelector('tp-yt-paper-dialog');
        const menu=document.querySelector('#action-menu');
        let creates=0, chosen='', nextId=0;
        function syncNewButton() {
          const query=document.querySelector('ytcp-search-bar input#search-input').value.trim();
          const host=document.querySelector('.new-playlist-button');
          const button=host.querySelector('button');
          const disabled=query.length>0;
          button.disabled=disabled;
          button.setAttribute('aria-disabled', disabled?'true':'false');
          host.setAttribute('aria-disabled', disabled?'true':'false');
        }
        function addPlaylist(name) {
          const row=document.createElement('div');row.className='row';row.setAttribute('role','listitem');
          const label=document.createElement('label');label.className='ytcp-checkbox-label';
          const outer=document.createElement('span');outer.className='checkbox-label';
          const text=document.createElement('span');text.className='label label-text';text.textContent=name;
          outer.append(text);
          const check=document.createElement('input');check.type='checkbox';
          check.onchange=()=>{if(check.checked)chosen=name};label.append(outer,check);row.append(label);
          document.querySelector('#playlists-list #items').append(row);
        }
        function createPlaylist() {
          creates++;addPlaylist(document.querySelector('#title-textarea [contenteditable]').innerText);
          creation.hidden=true;
        }
        </script>''')
        monkeypatch.setattr(uploader.time, 'sleep', lambda _seconds: None)
        monkeypatch.setattr(uploader, 'dismiss_reload_prompt', lambda *_args, **_kwargs: None)
        monkeypatch.setattr(uploader, 'DEBUG_DIR', tmp_path / 'youtube_debug')
        yield page
        browser.close()


def test_missing_niche_is_created_selected_and_confirmed_once(studio_page):
    uploader.select_playlist(studio_page, 'Drama China', create_missing=True)
    assert studio_page.evaluate('creates') == 1
    assert studio_page.evaluate('chosen') == 'Drama China'
    assert not studio_page.locator('tp-yt-paper-dialog').is_visible()
    uploader.select_playlist(studio_page, 'Drama China', create_missing=True)
    assert studio_page.evaluate('creates') == 1


def test_portalled_menu_item_creates_missing_playlist(studio_page):
    # Studio renders the "New playlist" item in a global ytcp-text-menu, not
    # inside ytcp-playlist-dialog. Creation must still open the form.
    studio_page.evaluate("() => document.body.appendChild(document.querySelector('#action-menu'))")
    uploader.select_playlist(studio_page, 'Keluarga dan Rumah Tangga')
    assert studio_page.evaluate('creates') == 1
    assert studio_page.evaluate('chosen') == 'Keluarga dan Rumah Tangga'


def test_owned_tab_marker_survives_navigation_and_never_marks_user_pages(studio_page):
    context = studio_page.context.browser.new_context()
    try:
        owned_page, user_page = context.new_page(), context.new_page()
        owned_page.route('https://owned-tab.test/**', lambda route: route.fulfill(
            status=200, content_type='text/html',
            body='<title>Owned upload tab</title><iframe name="studio-frame" srcdoc="Frame content"></iframe>'))
        uploader.mark_fendy_clipper_upload_tab(owned_page)
        owned_page.goto('https://owned-tab.test/upload')
        assert uploader.is_fendy_clipper_upload_tab(owned_page)
        owned_page.reload()
        assert uploader.is_fendy_clipper_upload_tab(owned_page)
        assert owned_page.frame_locator('iframe').locator('body').evaluate('() => window.name') == 'studio-frame'
        user_page.route('https://user-tab.test/**', lambda route: route.fulfill(
            status=200, content_type='text/html', body='<title>User tab</title>'))
        user_page.goto('https://user-tab.test/dashboard')
        assert user_page.evaluate('window.name') == ''
        assert uploader.close_idle_fendy_clipper_upload_tabs([owned_page, user_page]) == 1
        assert owned_page.is_closed() and not user_page.is_closed()
    finally:
        context.close()


def test_creation_host_without_geometry_uses_the_visible_title_field(studio_page):
    studio_page.add_style_tag(content='ytcp-playlist-creation-dialog:not([hidden]) {display:contents}')
    studio_page.evaluate("() => document.body.appendChild(document.querySelector('#action-menu'))")
    uploader.select_playlist(studio_page, 'Keluarga dan Rumah Tangga', create_missing=True)
    assert studio_page.evaluate('creates') == 1
    assert studio_page.evaluate('chosen') == 'Keluarga dan Rumah Tangga'
    uploader.select_playlist(studio_page, 'Keluarga dan Rumah Tangga', create_missing=True)
    assert studio_page.evaluate('creates') == 1


@pytest.mark.parametrize('native,expected', [('Tidak publik', False), ('Pribadi', False), ('Publik', True)])
def test_public_verification_uses_exact_native_visibility_not_description(studio_page, native, expected):
    studio_page.set_content(f'''<div id="title-textarea"><div contenteditable="true">Reviewed title</div></div>
        <p>Description mentions public, publik, private and scheduled, which are not the saved visibility.</p>
        <ytcp-video-metadata-visibility><div id="visibility-text">{native}</div></ytcp-video-metadata-visibility>''')
    snapshot = uploader.saved_video_edit_snapshot(studio_page, 'Reviewed title', 'public')
    assert snapshot['titleOk'] == 'True'
    assert snapshot['visibilityOk'] == str(expected)


def test_playlist_dialog_uses_inner_surface_before_contents_wrapper(studio_page):
    studio_page.evaluate('''() => {
      const surface=document.querySelector('ytcp-playlist-dialog tp-yt-paper-dialog');
      surface.setAttribute('role','dialog');
      const wrapper=document.createElement('ytcp-dialog');
      wrapper.id='dialog';wrapper.style.display='contents';
      surface.replaceWith(wrapper);wrapper.appendChild(surface);
      document.querySelector('#dropdown').onclick=()=>{surface.hidden=false};
      document.querySelector('.done-button button').onclick=()=>{
        surface.hidden=true;document.querySelector('#dropdown').textContent=chosen;
      };
      addPlaylist('Gaming');
    }''')
    uploader.select_playlist(studio_page, 'Gaming')
    assert studio_page.evaluate('chosen') == 'Gaming'
    assert studio_page.evaluate('creates') == 0


def test_existing_playlist_is_reused_without_creation(studio_page):
    studio_page.evaluate("addPlaylist('Gaming')")
    uploader.select_playlist(studio_page, 'Gaming')
    assert studio_page.evaluate('creates') == 0
    assert studio_page.evaluate('chosen') == 'Gaming'


def test_unknown_search_state_cannot_create_playlist(studio_page):
    studio_page.locator('#dropdown').click()
    studio_page.locator('#playlists-list').evaluate('(e)=>e.remove()')
    with pytest.raises(uploader.UploadError, match='belum terverifikasi'):
        uploader.create_missing_playlist(studio_page, 'Drama China')
    assert studio_page.evaluate('creates') == 0


def test_failed_selection_of_existing_row_does_not_create_a_duplicate(studio_page, monkeypatch):
    studio_page.evaluate("addPlaylist('Gaming')")
    monkeypatch.setenv('YOUTUBE_PLAYLIST_SELECT_ATTEMPTS', '1')
    monkeypatch.setattr(uploader, 'playlist_is_selected', lambda *_args, **_kwargs: False)
    monkeypatch.setattr(uploader, 'click_playlist_checkbox', lambda *_args, **_kwargs: False)
    monkeypatch.setattr(uploader, 'click_playlist_named', lambda *_args, **_kwargs: False)
    monkeypatch.setattr(uploader, 'save_debug_artifacts', lambda *_args, **_kwargs: None)
    with pytest.raises(uploader.UploadError, match='playlist tidak terlewati'):
        uploader.select_playlist(studio_page, 'Gaming', create_missing=True)
    assert studio_page.evaluate('creates') == 0


def test_creation_failure_stops_before_later_upload_steps(studio_page, monkeypatch):
    # No row appears after the Create response; never click Create twice.
    studio_page.evaluate("() => { window.createPlaylist=()=>{creates++;throw Error('connection lost')}; }")
    monkeypatch.setattr(uploader, 'save_debug_artifacts', lambda *_args, **_kwargs: None)
    with pytest.raises(uploader.UploadError, match='Tombol Buat tidak diulang'):
        uploader.select_playlist(studio_page, 'Drama China', create_missing=True)
    assert studio_page.evaluate('creates') == 1


def test_creation_can_be_explicitly_disabled(studio_page, monkeypatch):
    monkeypatch.setenv('YOUTUBE_PLAYLIST_SELECT_ATTEMPTS', '1')
    monkeypatch.setattr(uploader, 'save_debug_artifacts', lambda *_args, **_kwargs: None)
    with pytest.raises(uploader.UploadError, match='playlist tidak terlewati'):
        uploader.select_playlist(studio_page, 'Sejarah, Geografi & Budaya Nusantara', create_missing=False)
    assert studio_page.evaluate('creates') == 0


def test_manual_upload_creates_missing_playlist_by_default(studio_page):
    uploader.select_playlist(studio_page, 'Keluarga dan Rumah Tangga')
    assert studio_page.evaluate('creates') == 1
    assert studio_page.evaluate('chosen') == 'Keluarga dan Rumah Tangga'


def test_creation_accepts_native_textarea_title(studio_page):
    studio_page.locator('#title-textarea').evaluate("e => e.innerHTML='<textarea></textarea>'")
    studio_page.evaluate("""() => { window.createPlaylist=()=>{
        creates++;addPlaylist(document.querySelector('#title-textarea textarea').value);
        creation.hidden=true;
    }; }""")
    uploader.select_playlist(studio_page, 'Drama Korea')
    assert studio_page.evaluate('creates') == 1
    assert studio_page.evaluate('chosen') == 'Drama Korea'


@pytest.mark.parametrize('disabled_on_host', [False, True])
def test_disabled_create_button_stops_within_seconds(studio_page, monkeypatch, disabled_on_host):
    from types import SimpleNamespace
    if disabled_on_host:
        studio_page.locator('#create-button').evaluate("e => e.setAttribute('aria-disabled','true')")
    else:
        studio_page.locator('#create-button button').evaluate('e => e.disabled=true')
    studio_page.locator('#dropdown').click()
    # Keep the virtual clock local to the uploader; Playwright uses real time.
    now = [0.0]
    def tick():
        now[0] += 0.1
        return now[0]
    monkeypatch.setattr(uploader, 'time', SimpleNamespace(monotonic=tick, sleep=lambda _: None))
    with pytest.raises(uploader.UploadError, match='Tombol Buat playlist belum aktif'):
        uploader.create_missing_playlist(studio_page, 'Drama Korea')
    assert studio_page.evaluate('creates') == 0
    assert now[0] < 10


def test_history_cron_creates_playlist_and_resumes_selection(studio_page):
    name = 'Sejarah, Geografi & Budaya Nusantara'
    uploader.select_playlist(studio_page, name, create_missing=True)
    uploader.select_playlist(studio_page, name, create_missing=True)
    assert studio_page.evaluate('creates') == 1
    assert studio_page.evaluate('chosen') == name


@pytest.mark.parametrize('scenario', ['missing', 'existing', 'lost_after_save', 'save_rejected'])
def test_recovery_verifies_playlist_after_saving_exact_video(studio_page, monkeypatch, scenario):
    import json
    html = studio_page.content()
    state = {'saved': scenario == 'existing', 'saves': 0}
    name = 'Keluarga dan Rumah Tangga'
    def editor(route):
        selected = state['saved'] and scenario != 'lost_after_save'
        setup = f'''<script>
        {'addPlaylist(' + json.dumps(name) + ');' if state['saved'] else ''}
        {'document.querySelector("input[type=checkbox]").checked=true;' if selected else ''}
        </script><button onclick="fetch('/youtubei/v1/video_manager/metadata_update', {{method:'POST'}})">Simpan</button>'''
        route.fulfill(status=200, content_type='text/html', body=html + setup)
    def save(route):
        state['saves'] += 1
        state['saved'] = True
        route.fulfill(status=403 if scenario == 'save_rejected' else 200,
                      content_type='application/json', body='{}')
    studio_page.route('https://studio.youtube.com/video/abcDEF12345/edit', editor)
    studio_page.route('**/video_manager/metadata_update', save)
    monkeypatch.setattr(uploader, 'ensure_logged_in', lambda page: None)
    messages = []
    monkeypatch.setattr(uploader, 'log', messages.append)
    if scenario in {'lost_after_save', 'save_rejected'}:
        with pytest.raises(uploader.UploadError, match='belum tersimpan|ditolak Studio'):
            uploader.ensure_saved_video_playlist(studio_page, 'https://youtu.be/abcDEF12345', name)
        assert not any(line.startswith('SAVED_PLAYLIST_CONFIRMED:') for line in messages)
    else:
        uploader.ensure_saved_video_playlist(studio_page, 'https://youtu.be/abcDEF12345', name)
        assert f'SAVED_PLAYLIST_CONFIRMED: {name}' in messages
    assert state['saves'] == (0 if scenario == 'existing' else 1)
    assert studio_page.url == 'https://studio.youtube.com/video/abcDEF12345/edit'
