"""Read-only Studio observations in owned tabs; no upload or publication controls."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import signal
import time

from upload_attention import READER_VERSION, caption_hash, text_hash, normalized_text, tiktok_url, youtube_id
from browser_page_activity import start_background_page_activity, stop_background_page_activity


def youtube_candidates(page, title: str, channel_id: str, deadline: float) -> set[str]:
    """Only exact full titles in real video rows, never neighboring card text."""
    candidates = set()
    for tab in ('short', 'upload'):
        page.goto(f'https://studio.youtube.com/channel/{channel_id}/videos/{tab}',
                  wait_until='domcontentloaded', timeout=25000)
        page.locator('ytcp-video-row').first.wait_for(timeout=20000)
        for _ in range(4):
            found = page.evaluate('''title => [...document.querySelectorAll('ytcp-video-row')].flatMap(row=>{
              const norm=s=>String(s||'').replace(/\\s+/g,' ').trim();
              const a=row.querySelector('a#video-title');
              return a&&norm(a.textContent)===norm(title)?[a.getAttribute('href')]:[];
            })''', title)
            for value in found:
                match = re.search(r'/video/([A-Za-z0-9_-]{11})/', value or '')
                if match:
                    candidates.add(match[1])
            if len(candidates) > 1 or time.monotonic() > deadline:
                return candidates
            next_button = page.locator('#navigate-after').first
            if not next_button.count() or next_button.get_attribute('disabled') is not None:
                break
            first = page.locator('a#video-title').first.get_attribute('href')
            next_button.click(timeout=3000)
            page.wait_for_function('(previous)=>document.querySelector("a#video-title")?.getAttribute("href")!==previous', arg=first, timeout=10000)
    return candidates


def read_youtube(page, row: dict, target_channel_id: str) -> dict:
    import youtube_uploader as studio
    checkpoint = youtube_id(row.get('video_url'))
    deadline = time.monotonic() + 80
    if not checkpoint:
        studio.goto_studio(page, studio_url=f'https://studio.youtube.com/channel/{target_channel_id}')
        studio.ensure_target_identity(page, row.get('target_channel', ''), '', target_channel_id)
        candidates = youtube_candidates(page, row['title'], target_channel_id, deadline)
        if len(candidates) != 1:
            return {'confirmed': False, 'message': 'Posting dengan metadata yang unik belum ditemukan; pemeriksaan diulang otomatis.'}
        checkpoint = next(iter(candidates))
    page.goto(f'https://studio.youtube.com/video/{checkpoint}/edit', wait_until='domcontentloaded', timeout=25000)
    title_field = page.locator('#title-textarea #textbox').first
    title_field.wait_for(state='visible', timeout=25000)
    studio.ensure_target_identity(page, row.get('target_channel', ''), '', target_channel_id)
    actual_title = title_field.inner_text(timeout=3000)
    description = page.locator('#description-textarea #textbox').first
    actual_description = description.inner_text(timeout=3000) if description.count() else None
    title_matched = normalized_text(actual_title) == normalized_text(row['title'])
    description_matched = actual_description is not None and normalized_text(actual_description) == normalized_text(row.get('description', ''))
    # Discovery without an assigned ID also needs the exact original filename.
    filename = page.get_by_text(row['clip_name'], exact=True)
    original_filename = filename.first.inner_text(timeout=3000).strip() if filename.count() else None
    filename_matched = original_filename == row['clip_name']
    assigned_id = youtube_id(row.get('video_url'))
    # An exact assigned ID plus the original rendered filename survives a
    # legitimate metadata edit. Discovery still requires full exact metadata.
    from upload_attention import distinctive_filename
    exact_original = bool(assigned_id and filename_matched and distinctive_filename(row['clip_name']))
    if not title_matched and not exact_original:
        return {'confirmed': False, 'observation_complete': True,
                'message': 'Judul pada ID tersimpan berbeda; video dipertahankan dan tidak dikirim ulang.'}
    if not description_matched and not exact_original:
        return {'confirmed': False, 'observation_complete': True,
                'message': 'Metadata video belum cocok lengkap; sistem mempertahankan posting yang sudah ada.'}
    if not assigned_id and not filename_matched:
        return {'confirmed': False, 'observation_complete': True,
                'message': 'Nama file sumber pada posting belum terbukti cocok; tidak ada upload ulang.'}
    visibility_field = page.locator('ytcp-video-metadata-visibility #visibility-text').first
    visibility_field.wait_for(state='visible', timeout=10000)
    label = normalized_text(visibility_field.inner_text()).casefold()
    actual = {'public': 'public', 'publik': 'public', 'private': 'private', 'pribadi': 'private',
              'unlisted': 'unlisted', 'tidak publik': 'unlisted', 'scheduled': 'scheduled',
              'dijadwalkan': 'scheduled', 'terjadwal': 'scheduled'}.get(label, '')
    if not actual:
        return {'confirmed': False, 'message': 'Visibilitas final belum terbaca; pemeriksaan akan dilanjutkan otomatis.'}
    snapshot = studio.saved_video_edit_snapshot(page, actual_title, actual)
    if snapshot.get('uploading') != 'False' or snapshot.get('uploadFailed') != 'False':
        return {'confirmed': False, 'message': 'YouTube masih memproses video; menunggu konfirmasi final.'}
    if '/video/' + checkpoint + '/edit' not in page.url:
        return {'confirmed': False, 'message': 'Halaman video berpindah; identitas belum dapat dipastikan.'}
    return {'confirmed': True, 'video_url': f'https://www.youtube.com/watch?v={checkpoint}',
            'target_channel_id': target_channel_id, 'title': actual_title,
            'description_sha256': text_hash(actual_description) if actual_description is not None else None,
            'visibility': actual, 'original_visibility': row.get('visibility'),
            'source': 'authenticated_studio_exact_video', 'file_name_matched': filename_matched,
            'original_filename': original_filename if filename_matched else None,
            'remote_processing_complete': True, 'reader_version': READER_VERSION}


def read_tiktok(page, row: dict, target_handle: str) -> dict:
    import tiktok_uploader as studio
    studio.validate_target_account(page, target_handle)
    exact = tiktok_url(row.get('profile_url'), target_handle)
    if exact:
        proof = studio.verify_remote_post(page, exact, row['caption'], target_handle, None)
        return {'confirmed': True, **proof, 'original_visibility': row['visibility'], 'source': 'authenticated_studio_exact_post'}
    studio.goto(page, studio.TIKTOK_CONTENT_URL)
    deadline = time.monotonic() + 75
    matches = {}; previous = set(); settled = 0
    while time.monotonic() < deadline:
        page.wait_for_timeout(1000)
        # Collect every matching ID, including duplicates visible together.
        for link in page.locator('a[href*="/video/"]').all():
            href = str(link.get_attribute('href', timeout=750) or '')
            if href.startswith('/'):
                href = 'https://www.tiktok.com' + href
            url = tiktok_url(href, target_handle)
            if not url or normalized_text(link.inner_text(timeout=1000)) != normalized_text(row.get('caption', '')[:2200]):
                continue
            row_text = link.evaluate("a=>(a.closest('[data-tt=components_RowLayout_FlexRow]')||a.closest('tr,[role=row]'))?.innerText||''")
            labels = {line.strip().casefold() for line in row_text.splitlines()}
            private = bool(labels & {'only me', 'only you', 'hanya saya', 'hanya anda', 'hanya kamu'})
            public = bool(labels & {'everyone', 'semua orang'})
            matches[url] = 'only_you' if private and not public else 'public' if public and not private else ''
        if len(matches) > 1:
            return {'confirmed': False, 'message': 'Beberapa posting memakai caption yang sama; sistem menahan pengiriman ulang.'}
        ids = studio.visible_tiktok_post_ids(page)
        settled = settled + 1 if ids and ids == previous else 0
        previous = ids
        position = page.evaluate('''()=>{const e=[...document.querySelectorAll('div')].find(e=>e.clientHeight>200&&
            e.scrollHeight>e.clientHeight+100&&e.querySelector('a[href*="/video/"]'));
            if(e){const bottom=e.scrollTop+e.clientHeight>=e.scrollHeight-3;e.scrollTop+=e.clientHeight*.85;return bottom}
            const bottom=scrollY+innerHeight>=document.documentElement.scrollHeight-3;scrollBy(0,innerHeight*.85);return bottom}''')
        if settled >= 3 and position:
            break
    if len(matches) != 1 or not (settled >= 3 and position):
        return {'confirmed': False, 'message': 'Posting dengan caption lengkap dan identitas unik belum terbukti; tidak ada Post ulang.'}
    video_url, visibility = next(iter(matches.items()))
    if visibility not in {'public', 'only_you'}:
        return {'confirmed': False, 'message': 'Privasi posting TikTok belum terbaca; pemeriksaan ditunda otomatis.'}
    return {'confirmed': True, 'video_url': video_url, 'visibility': visibility,
            'caption_sha256': caption_hash(row['caption']), 'original_visibility': row['visibility'], 'source': 'authenticated_studio_exact_post'}


def observe(payload: dict, cdp_url: str) -> dict:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(cdp_url, no_defaults=True, timeout=15000)
        if not browser.contexts:
            raise RuntimeError('Browser login belum tersedia; pemeriksaan ditunda otomatis.')
        page = browser.contexts[0].new_page()
        activity = None
        try:
            activity = start_background_page_activity(page)
            page.set_default_timeout(5000)
            if payload['platform'] == 'youtube':
                return read_youtube(page, payload['upload'], payload['target_channel_id'])
            return read_tiktok(page, payload['upload'], payload['target_handle'])
        finally:
            stop_background_page_activity(activity)
            try:
                page.close()
            except Exception:
                pass
            # The borrowed browser and its other tabs belong to the operator.


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--cdp-url', required=True)
    args = parser.parse_args()
    def terminate(_signum, _frame):
        raise SystemExit(143)
    signal.signal(signal.SIGTERM, terminate)
    try:
        result = observe(json.loads(Path(args.input).read_text()), args.cdp_url)
    except Exception as error:
        result = {'confirmed': False, 'message': 'Studio belum siap diverifikasi; sistem akan mencoba lagi dengan jeda.',
                  'error_type': type(error).__name__}
    print('ATTENTION_PROOF:' + json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
