"""Browser regressions for the actual Studio Select/DraftJS failure shapes."""
import pytest

import tiktok_uploader as uploader


@pytest.fixture
def studio_page(tmp_path, monkeypatch):
    from playwright.sync_api import sync_playwright
    import shutil

    executable = shutil.which('google-chrome') or shutil.which('chromium')
    if not executable:
        pytest.skip('Native Chromium is unavailable')
    monkeypatch.setattr(uploader, 'DEBUG_DIR', tmp_path)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=executable, headless=True,
            args=['--no-sandbox'])
        page = browser.new_page()
        page.route('**/*', lambda route: route.abort())
        page.set_content('''
            <style>@keyframes drift{from{transform:translateX(0)}to{transform:translateX(20px)}}
            .moving{animation:drift .2s linear infinite alternate}</style>
            <div id="privacy"></div>
            <div class="public-DraftEditor-content" contenteditable="true" role="combobox">clip_01_filename</div>
            <script>
            window.visibilityValue='Everyone';
            function renderPrivacy(){
                document.querySelector('#privacy').innerHTML=`
                  <button id="privacy-trigger" role="combobox" aria-haspopup="dialog"
                    aria-controls="privacy-menu" aria-expanded="false">${window.visibilityValue}</button>
                  <div role="dialog" id="privacy-menu" hidden>
                    <button role="option">Everyone</button>
                    <button role="option">Friends<span> Followers you follow back</span></button>
                    <button role="option">Only you</button>
                  </div>`;
                const trigger=document.querySelector('#privacy-trigger');
                const menu=document.querySelector('#privacy-menu');
                trigger.onclick=()=>{menu.hidden=!menu.hidden;trigger.setAttribute('aria-expanded',String(!menu.hidden))};
                menu.querySelectorAll('button').forEach(button=>button.onclick=()=>{
                    window.visibilityValue=button.firstChild.textContent;
                    renderPrivacy(); // React replaces the old trigger during selection.
                });
            }
            renderPrivacy();
            window.escapes=0;
            document.addEventListener('keydown',e=>{if(e.key==='Escape')window.escapes++});
            </script>
        ''')
        yield page
        browser.close()


def test_native_privacy_reacquires_trigger_after_label_and_element_change(studio_page):
    uploader.set_only_you(studio_page)
    assert studio_page.locator('#privacy-trigger').inner_text() == 'Only you'
    uploader.set_public(studio_page)
    assert studio_page.locator('#privacy-trigger').inner_text() == 'Everyone'


def test_animated_option_uses_native_key_without_escaping_its_own_menu(studio_page):
    studio_page.locator('#privacy-trigger').click()
    studio_page.locator('[role="option"]').last.evaluate("el=>el.classList.add('moving')")
    assert uploader.visible_blocking_modal(studio_page) is None
    uploader.activate_privacy_control(studio_page, studio_page.locator('[role="option"]').last)
    uploader.verify_privacy_selection(uploader.current_privacy_trigger(studio_page), r'only you')
    assert studio_page.evaluate('window.escapes') == 0


@pytest.mark.parametrize('expanded', [False, True])
def test_safety_dialog_is_not_exempted_by_open_picker_or_privacy_words(studio_page, expanded):
    if expanded:
        studio_page.locator('#privacy-trigger').click()
    studio_page.evaluate('''() => {
        const modal=document.createElement('div');modal.role='dialog';modal.id='warning';
        modal.textContent='Content may be restricted. Everyone Friends Only you';
        document.body.appendChild(modal);
    }''')
    modal = uploader.visible_blocking_modal(studio_page)
    assert modal is not None and modal.get_attribute('id') == 'warning'


def test_privacy_words_without_expanded_associated_trigger_still_block(studio_page):
    studio_page.locator('#privacy-menu').evaluate('el=>el.hidden=false')
    assert uploader.visible_blocking_modal(studio_page) is not None


def test_native_caption_clear_recovers_selected_text_when_click_and_fill_timeout(studio_page, monkeypatch):
    actual = studio_page.locator('.public-DraftEditor-content')
    class UnstableEditor:
        def __getattr__(self, name):return getattr(actual, name)
        def click(self, **kwargs):raise TimeoutError('background stability timeout')
        def fill(self, value, **kwargs):
            actual.select_text()
            raise TimeoutError('background fill timeout')
    uploader.clear_caption_editor(studio_page, UnstableEditor())
    assert actual.inner_text().strip() == ''
    actual.fill('Judul sesuai isi sumber, tanpa nama file.')
    assert uploader.caption_editor_text(actual) == 'Judul sesuai isi sumber, tanpa nama file.'


@pytest.mark.parametrize('case,expected',[
    ('exact',('https://www.tiktok.com/@owner/video/7706778926332251393','only_you')),
    ('other_owner',None),('prefix_only',None),('duplicate_ids',None),
    ('unknown_privacy',('https://www.tiktok.com/@owner/video/7706778926332251393','')),
])
def test_existing_post_requires_full_caption_owner_and_one_associated_id(studio_page,case,expected):
    owner='other' if case=='other_owner' else 'owner'
    caption='Judul dari sumber. Sumber: kanal https://youtu.be/abcdefghijk'
    text='Judul dari sumber.' if case=='prefix_only' else caption
    privacy='Friends' if case=='unknown_privacy' else 'Only me'
    studio_page.set_content(f'''<div data-tt="components_RowLayout_FlexRow">
        <a href="/@{owner}/video/7706778926332251393">{text}</a><div>{privacy}</div></div>''')
    if case=='duplicate_ids':
        studio_page.evaluate('''() => {const row=document.querySelector('[data-tt]').cloneNode(true);
            row.querySelector('a').href='/@owner/video/7706778926332251394';document.body.appendChild(row)}''')
    assert uploader.exact_existing_tiktok_post(studio_page,caption,'owner') == expected


def test_existing_post_is_confirmed_before_file_input_or_upload_navigation(studio_page,monkeypatch,tmp_path,capsys):
    caption='Klip sumber yang sama dengan caption lengkap.'
    studio_page.set_content(f'''<div data-tt="components_RowLayout_FlexRow">
        <a href="/@owner/video/7706778926332251393">{caption}</a><div>Only me</div></div>''')
    monkeypatch.setattr(uploader,'tiktok_content_snapshot',lambda *a:(1,{'7706778926332251393'}))
    monkeypatch.setattr(uploader,'goto',lambda *a:pytest.fail('An existing post must never enter the upload form'))
    uploader.upload_video(studio_page,tmp_path/'missing-file.mp4',caption,False,'owner',visibility='only_you')
    logs=capsys.readouterr().out
    assert 'VIDEO_URL:https://www.tiktok.com/@owner/video/7706778926332251393' in logs
    assert 'UPLOAD_CONFIRMED:private' in logs


def test_unloaded_post_list_never_selects_a_file(monkeypatch,tmp_path):
    monkeypatch.setattr(uploader,'tiktok_content_snapshot',lambda *a:(0,None))
    monkeypatch.setattr(uploader,'goto',lambda *a:pytest.fail('Missing baseline must hold before transfer'))
    with pytest.raises(uploader.UploadError,match='file belum dipilih'):
        uploader.upload_video(object(),tmp_path/'missing.mp4','Caption',False,'owner')


@pytest.mark.parametrize('matches', [False, True])
def test_confirmation_requires_matching_new_row_not_an_unrelated_new_id(studio_page,monkeypatch,matches):
    caption='Caption lengkap dari sumber yang dipilih.'
    text=caption if matches else 'Video lain yang baru diposting di akun sama.'
    studio_page.set_content(f'''<div data-tt="components_RowLayout_FlexRow">
        <a href="/@owner/video/7706778926332251393">{text}</a><div>Only me</div></div>''')
    # This test owns its document; no navigation or timing waits are needed.
    from types import SimpleNamespace
    clock=iter(range(100))
    # Patch the uploader clock, keeping Playwright's event loop on real time.
    monkeypatch.setattr(uploader,'time',SimpleNamespace(monotonic=lambda:next(clock)))
    monkeypatch.setattr(studio_page,'goto',lambda *a,**k:None)
    monkeypatch.setattr(studio_page,'wait_for_timeout',lambda *a:None)
    result=uploader.wait_for_new_tiktok_post(studio_page,caption,0,timeout_ms=5000,
        previous_post_ids={'7706000000000000000'},target_handle='owner',visibility='only_you')
    assert result == ('https://www.tiktok.com/@owner/video/7706778926332251393' if matches else False)


def test_native_file_input_cannot_reuse_another_jobs_ready_draft(studio_page,tmp_path):
    first=tmp_path/'a'/'clip_01.mp4';second=tmp_path/'b'/'clip_01.mp4'
    first.parent.mkdir();second.parent.mkdir();first.write_bytes(b'clip A');second.write_bytes(b'clip B')
    first_id=uploader.upload_source_identity(first);second_id=uploader.upload_source_identity(second)
    staging=tmp_path/second_id.name;staging.write_bytes(second.read_bytes())
    studio_page.set_content('''<input type="file" onchange="document.querySelector('#name').textContent=this.files[0].name">
        <span id="name"></span><div contenteditable="true">Caption editor ready</div><button>Post</button>''')
    studio_page.locator('input[type="file"]').set_input_files(str(staging))
    assert studio_page.locator('#name').inner_text()==second_id.name
    assert not uploader.upload_editor_has_requested_file(studio_page,first_id)
    assert uploader.upload_editor_has_requested_file(studio_page,second_id)


@pytest.mark.parametrize('confirmation',[False,True])
def test_cron_draft_prompt_discards_and_proves_empty_picker_without_continue(studio_page,confirmation):
    studio_page.set_content('''<div id="picker" hidden>Select video to upload<input type="file"></div>
        <div role="dialog" id="draft"><p>Continue editing your draft?</p>
        <button onclick="window.continued++">Continue editing</button><button id="discard">Discard</button></div>
        <script>window.continued=0;</script>''')
    studio_page.locator('#discard').evaluate('''(button,confirm)=>button.onclick=()=>{
        if(confirm){document.querySelector('#draft').innerHTML='<p>Discard changes?</p><button>Cancel</button><button id="yes">Discard</button>';
            document.querySelector('#yes').onclick=()=>{document.querySelector('#draft').remove();document.querySelector('#picker').hidden=false;};}
        else{document.querySelector('#draft').remove();document.querySelector('#picker').hidden=false;}
    }''',confirmation)
    assert uploader.discard_cron_upload_draft(studio_page)
    assert studio_page.evaluate('window.continued')==0
    assert studio_page.locator('#picker').is_visible()
    assert studio_page.locator('input[type="file"]').input_value()==''


def test_cron_discard_never_operates_on_delete_published_post_dialog(studio_page):
    studio_page.set_content('''<div role="dialog">Delete post?
        <button onclick="window.deleted=true">Delete</button><button>Cancel</button></div>''')
    assert not uploader.discard_cron_upload_draft(studio_page)
    assert not studio_page.evaluate('!!window.deleted')


def test_cron_discard_cannot_activate_through_another_overlay(studio_page):
    studio_page.set_content('''<div role="dialog">Continue editing your draft?
        <button>Continue editing</button><button onclick="window.discarded=true">Discard</button></div>
        <div style="position:fixed;inset:0;z-index:999;background:white">A different blocking modal</div>''')
    with pytest.raises(uploader.UploadError,match='belum dapat dibuang'):
        uploader.discard_cron_upload_draft(studio_page)
    assert not studio_page.evaluate('!!window.discarded')


def test_requested_everyone_stays_selected_without_opening_or_dismissing_picker(studio_page):
    uploader.configure_requested_privacy(studio_page,'public')
    assert studio_page.locator('#privacy-trigger').inner_text()=='Everyone'
    assert studio_page.locator('#privacy-trigger').get_attribute('aria-expanded')=='false'
    assert studio_page.evaluate('window.escapes')==0


def test_privacy_reset_during_processing_is_corrected_before_submission(studio_page):
    uploader.configure_requested_privacy(studio_page,'only_you')
    studio_page.evaluate("window.visibilityValue='Everyone';renderPrivacy()")
    uploader.configure_requested_privacy(studio_page,'only_you')
    assert studio_page.locator('#privacy-trigger').inner_text()=='Only you'
    assert studio_page.evaluate('window.escapes')==0


CANCEL_UPLOAD_TEXT='Sure you want to cancel your upload? Any edits to your current upload will not be saved.'


def cancel_upload_document(page, *, show_dialog=True, text=CANCEL_UPLOAD_TEXT):
    page.set_content('''<style>button{display:block}</style><input type="file"><div class="public-DraftEditor-content" contenteditable="true">Caption</div>
      <button id="cancel">Cancel</button><button id="post" onclick="window.posted++">Post</button>
      <script>
      window.cancelOpened=0;window.yes=0;window.no=0;window.posted=0;
      window.openCancel=()=>{
        window.cancelOpened++;
        const modal=document.createElement('div');modal.role='dialog';modal.id='cancel-dialog';
        const p=document.createElement('p');p.textContent=window.promptText;modal.appendChild(p);
        const no=document.createElement('button');no.textContent='No';no.id='no';
        no.onclick=()=>{window.no++;modal.remove()};modal.appendChild(no);
        const yes=document.createElement('button');yes.textContent='Yes';yes.id='yes';
        yes.onclick=()=>{window.yes++;document.querySelector('input').value='';modal.remove()};modal.appendChild(yes);
        document.body.appendChild(modal);
      };
      document.querySelector('#cancel').onclick=window.openCancel;
      </script>''')
    page.evaluate('(text)=>window.promptText=text',text)
    page.locator('input[type=file]').set_input_files({'name':'clipforge-correct.mp4','mimeType':'video/mp4','buffer':b'correct reviewed media'})
    if show_dialog:page.evaluate('window.openCancel()')


def test_overlay_cleanup_does_not_click_the_real_upload_cancel_control(studio_page):
    cancel_upload_document(studio_page,show_dialog=False)
    uploader.dismiss_upload_overlays(studio_page)
    assert studio_page.evaluate('[window.cancelOpened,window.yes,window.no,window.posted]')==[0,0,0,0]
    assert studio_page.locator('input').evaluate('el=>el.files[0].name')=='clipforge-correct.mp4'


@pytest.mark.parametrize('title',[CANCEL_UPLOAD_TEXT,'Are you sure you want to cancel your upload? Any edits to your current upload will not be saved.'])
def test_exact_cancel_upload_dialog_chooses_no_and_preserves_transferred_file(studio_page,title):
    cancel_upload_document(studio_page,text=title)
    uploader.dismiss_upload_overlays(studio_page)
    assert studio_page.evaluate('[window.yes,window.no,window.posted]')==[0,1,0]
    assert studio_page.locator('input').evaluate('el=>el.files[0].name')=='clipforge-correct.mp4'
    assert uploader.visible_blocking_modal(studio_page) is None


@pytest.mark.parametrize('text',['Delete this published post?', 'Content may be restricted. Continue to post?',
                               CANCEL_UPLOAD_TEXT+' Review copyright restriction first.'])
def test_no_yes_on_other_dialogs_never_gets_cancel_upload_semantics(studio_page,text):
    cancel_upload_document(studio_page,text=text)
    assert not uploader.dismiss_blocking_modal(studio_page)[0]
    assert studio_page.evaluate('[window.yes,window.no,window.posted]')==[0,0,0]


def test_background_no_click_timeout_uses_scoped_native_keyboard(studio_page,monkeypatch):
    cancel_upload_document(studio_page)
    from playwright.sync_api import Locator
    original=Locator.click
    def click(control,**kwargs):
        if control.get_attribute('id')=='no':raise TimeoutError('element is not stable')
        return original(control,**kwargs)
    monkeypatch.setattr(Locator,'click',click)
    assert uploader.dismiss_blocking_modal(studio_page)[0]
    assert studio_page.evaluate('[window.yes,window.no,window.posted]')==[0,1,0]


def test_cancel_dialog_no_fallback_never_types_through_an_overlay(studio_page):
    cancel_upload_document(studio_page)
    studio_page.evaluate('''()=>{const blocker=document.createElement('div');
        blocker.style='position:fixed;inset:0;z-index:999;background:white';document.body.appendChild(blocker)}''')
    assert not uploader.dismiss_blocking_modal(studio_page)[0]
    assert studio_page.evaluate('[window.yes,window.no,window.posted]')==[0,0,0]


def test_click_that_succeeded_before_timeout_does_not_press_another_no_button(studio_page,monkeypatch):
    cancel_upload_document(studio_page)
    from playwright.sync_api import Locator
    original=Locator.click
    def click_then_error(control,**kwargs):
        target=control.inner_text()=='No'
        result=original(control,**kwargs)
        if target:raise TimeoutError('late click acknowledgement')
        return result
    monkeypatch.setattr(Locator,'click',click_then_error)
    assert uploader.dismiss_blocking_modal(studio_page)[0]
    assert studio_page.evaluate('[window.yes,window.no,window.posted]')==[0,1,0]
