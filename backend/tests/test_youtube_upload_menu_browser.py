import shutil

import pytest

import youtube_uploader as uploader


@pytest.fixture
def upload_page():
    from playwright.sync_api import sync_playwright
    executable=shutil.which('google-chrome') or shutil.which('chromium')
    if not executable:pytest.skip('Native Chromium is unavailable')
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=executable,headless=True,args=['--no-sandbox'])
        page=browser.new_page()
        page.route('**/*',lambda route:route.abort())
        yield page
        browser.close()


def test_exact_menu_item_opens_file_input_instead_of_clicking_upload_container(upload_page):
    upload_page.set_content('''<div id="upload-menu">Upload video Live streaming
        <button id="real-upload" onclick="document.querySelector('#picker').hidden=false">Upload video</button>
        <div id="picker" hidden><input type="file"></div></div>''')
    assert uploader.click_upload_menu_item(upload_page,timeout_ms=1000)
    assert upload_page.locator('#picker').is_visible()
    assert upload_page.locator('input[type="file"]').input_value() == ''


def test_dom_click_return_without_upload_surface_is_never_reported_as_open(upload_page):
    upload_page.set_content('<div id="upload-menu">Upload video Live streaming</div>')
    assert not uploader.click_upload_menu_item(upload_page,timeout_ms=300)
