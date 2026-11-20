"""Read Facebook's current weekly tasks without treating local uploads as credit."""
from datetime import datetime, timezone
import re

import facebook_browser as browser
from browser_page_activity import start_background_page_activity, stop_background_page_activity

VERSION = 1
URL = 'https://www.facebook.com/professional_dashboard/status/'


def parse(text: str, *, account_verified=False, checked_at=None) -> dict:
    tasks = []
    patterns = (
        ('public_posts', r'Buat\s+(\d+)\s+postingan publik baru\s+(\d+)\s*/\s*(\d+)\s+selesai'),
        ('reels', r'Buat\s+(\d+)\s+reel publik baru\s+(\d+)\s*/\s*(\d+)\s+selesai'),
        ('followers', r'Dapatkan\s+(\d+)\s+pengikut baru\s+(\d+)\s*/\s*(\d+)\s+pengikut'),
        ('views', r'Dapatkan\s+(\d+)\s+tayangan lagi pada konten Anda\s+(\d+)\s*/\s*(\d+)\s+selesai'),
    )
    labels = dict(public_posts='Postingan publik', reels='Reel publik', followers='Pengikut baru', views='Tayangan')
    if account_verified:
        for key, pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match and int(match[1]) == int(match[3]):
                tasks.append(dict(key=key, label=labels[key], completed=int(match[2]), target=int(match[3])))
    period = re.search(r'Minggu pada\s+([^\n]+)', text, re.I)
    percent = re.search(r'(\d+)\s*%\s*selesai', text, re.I)
    stories = re.search(r'(\d+)\s*/\s*(\d+)\s*\n?\s*Cerita\b', text, re.I)
    return dict(version=VERSION, account_verified=account_verified,
                checked_at=checked_at or datetime.now(timezone.utc).isoformat(),
                period_label=period[1].strip() if period and account_verified else None,
                percent=int(percent[1]) if percent and account_verified else None,
                tasks=tasks, stories=({'completed':int(stories[1]), 'target':int(stories[2])}
                    if stories and account_verified else None),
                source='facebook_live', href=URL,
                note='Facebook menentukan progres tugas. Unggahan lokal tidak dihitung sebagai kredit tugas atau bonus.')


def collect(expected_profile: str) -> dict:
    if not expected_profile:
        raise ValueError('Akun target belum terikat.')
    with browser.connection() as context:
        if browser.active_user(context) != expected_profile or browser.logged_user(context) != expected_profile:
            raise ValueError('Profil Facebook berubah.')
        page = context.new_page()
        activity = start_background_page_activity(page)
        try:
            page.goto(URL, wait_until='domcontentloaded', timeout=45000)
            page.wait_for_timeout(2500)
            main = page.get_by_role('main').first
            text = main.inner_text(timeout=10000)
            if browser.active_user(context) != expected_profile:
                raise ValueError('Profil berubah saat membaca tugas.')
            result = parse(text, account_verified=True)
            if not result['tasks']:
                raise ValueError('Tugas mingguan belum dapat dibaca; bukti sebelumnya dipertahankan.')
            return result
        finally:
            stop_background_page_activity(activity)
            page.close()
