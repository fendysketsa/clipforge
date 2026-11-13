"""Exercise the observed Studio create/search/select sequence in Chromium."""
import shutil

import pytest
import youtube_uploader as uploader


@pytest.fixture
def studio_page(monkeypatch):
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
          <input id="search-input" placeholder="Telusuri playlist">
          <div id="playlists-list"><ul></ul></div>
          <ytcp-button class="new-playlist-button"><button onclick="menu.hidden=false">Playlist baru</button></ytcp-button>
          <div id="action-menu" hidden><button role="menuitem" onclick="creation.hidden=false;menu.hidden=true">Playlist baru</button></div>
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
        function addPlaylist(name) {
          const row=document.createElement('li');row.className='row';
          const label=document.createElement('span');label.className='checkbox-label';label.textContent=name;
          const check=document.createElement('input');check.type='checkbox';
          check.onchange=()=>{if(check.checked)chosen=name};row.append(label,check);
          document.querySelector('#playlists-list ul').append(row);
        }
        function createPlaylist() {
          creates++;addPlaylist(document.querySelector('#title-textarea [contenteditable]').innerText);
          creation.hidden=true;
        }
        </script>''')
        monkeypatch.setattr(uploader.time, 'sleep', lambda _seconds: None)
        monkeypatch.setattr(uploader, 'dismiss_reload_prompt', lambda *_args, **_kwargs: None)
        yield page
        browser.close()


def test_missing_niche_is_created_selected_and_confirmed_once(studio_page):
    uploader.select_playlist(studio_page, 'Drama China', create_missing=True)
    assert studio_page.evaluate('creates') == 1
    assert studio_page.evaluate('chosen') == 'Drama China'
    assert not studio_page.locator('tp-yt-paper-dialog').is_visible()
    uploader.select_playlist(studio_page, 'Drama China', create_missing=True)
    assert studio_page.evaluate('creates') == 1


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


def test_manual_upload_cannot_create_missing_niche_playlist(studio_page, monkeypatch):
    monkeypatch.setenv('YOUTUBE_PLAYLIST_SELECT_ATTEMPTS', '1')
    monkeypatch.setattr(uploader, 'save_debug_artifacts', lambda *_args, **_kwargs: None)
    with pytest.raises(uploader.UploadError, match='playlist tidak terlewati'):
        uploader.select_playlist(studio_page, 'Sejarah, Geografi & Budaya Nusantara')
    assert studio_page.evaluate('creates') == 0


def test_history_cron_creates_playlist_and_resumes_selection(studio_page):
    name = 'Sejarah, Geografi & Budaya Nusantara'
    uploader.select_playlist(studio_page, name, create_missing=True)
    uploader.select_playlist(studio_page, name, create_missing=True)
    assert studio_page.evaluate('creates') == 1
    assert studio_page.evaluate('chosen') == name
