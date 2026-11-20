"""Read-only Facebook earnings evidence and a conservative production plan.

Facebook's UI is authoritative for program access, qualified views and bonus
progress. Upload completion and local QC never constitute monetization approval.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re

import facebook_browser as browser
from browser_page_activity import start_background_page_activity, stop_background_page_activity

VERSION = 1
URLS = {
    'overview': 'https://www.facebook.com/professional_dashboard/monetization/',
    'content': 'https://www.facebook.com/professional_dashboard/monetization/content_monetization/',
    'rate': 'https://www.facebook.com/professional_dashboard/earnings/earnings_rate/',
    'health': 'https://www.facebook.com/profile_status/?referrer=monetization_transparency_home',
    'payout': 'https://www.facebook.com/payout/overview/?entry_point=PRODASH',
    'insights': 'https://www.facebook.com/professional_dashboard/profile_insights/views/',
}
ORIGINALITY_URL = 'https://about.fb.com/news/2026/03/rewarding-original-creators-on-facebook/'


def amount(value):
    try:
        value = value.strip()
        if ',' in value and ('.' not in value or value.rfind(',') > value.rfind('.')):
            if len(value.rsplit(',', 1)[1]) == 2:
                value = value.replace('.', '').replace(',', '.')
            else:
                value = value.replace(',', '')
        else:
            value = value.replace(',', '')
        return float(value)
    except (ValueError, AttributeError):
        return None


def integer(value):
    value = value.strip()
    if re.fullmatch(r'\d+', value):
        return int(value)
    if re.fullmatch(r'\d{1,3}(?:[.,]\d{3})+', value):
        return int(value.replace('.', '').replace(',', ''))
    return None


def match_number(pattern, text):
    match = re.search(pattern, text, re.I)
    return int(match.group(1)) if match else None


def payout_status(text: str) -> dict:
    # Do not return the page body, bank details, tax IDs, names or payment IDs.
    issues = []
    patterns = {
        'setup_required': r'siapkan pembayaran|atur pembayaran|set up payouts|tambahkan metode pembayaran|add payout method',
        'identity_action': r'verifikasi identitas Anda|verify your identity|identity verification required|konfirmasi identitas Anda',
        'tax_action': r'lengkapi informasi pajak|add tax information|tax information required',
        'payment_issue': r'pembayaran ditahan|payouts? (?:on hold|disabled)|masalah pembayaran',
    }
    for name, pattern in patterns.items():
        if re.search(pattern, text, re.I):
            issues.append(name)
    ready = bool(re.search(r'pembayaran (?:sudah siap|telah disiapkan)|payouts? (?:are )?(?:set up|enabled|active)', text, re.I))
    return {'state': 'action_required' if issues else 'ready' if ready else 'unknown', 'issues': issues,
            'message': 'Ada tindakan pembayaran yang perlu diselesaikan di Facebook.' if issues else
            'Facebook menampilkan status pembayaran siap.' if ready else
            'Kesiapan pencairan belum terverifikasi. Buka pembayaran dan periksa metode, identitas, serta pajak bila diminta.'}


def parse_pages(pages: dict[str, str], *, account_verified=False, checked_at=None) -> dict:
    """Parse only explicit observations. Unknown values remain null/unknown."""
    checked_at = checked_at or datetime.now(timezone.utc).isoformat()
    overview, content, rate, health, insights = (pages.get(key, '') for key in ('overview','content','rate','health','insights'))
    status_section = overview.split('Status monetisasi', 1)[-1][:500] if 'Status monetisasi' in overview else ''
    active = bool(re.search(r'Profil Anda (?:aktif dan )?menghasilkan uang', status_section, re.I))
    restricted = bool(re.search(r'monetisasi (?:dinonaktifkan|ditangguhkan|dibatasi)|monetization (?:disabled|suspended|restricted)', health + status_section, re.I))
    program_state = ('restricted' if restricted else 'active' if active else 'unknown') if account_verified else 'unknown'
    period = re.search(r'Pendapatan\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)', content, re.I)
    estimated = re.search(r'Pendapatan\s+\w+\s+\$(\d[\d,.]*)\s+Perkiraan pendapatan', content, re.I)
    qualified_match = re.search(r'(?:^|\n)([\d.,]+)\s*\nTayangan yang memenuhi syarat', rate)
    qualified = integer(qualified_match.group(1)) if qualified_match else None
    earning_rate = re.search(r'\$([\d,.]+)\s*\nTingkat pendapatan\s*\nPer 1[.,]000 tayangan', rate, re.I)
    reasons = []
    for label in ('Durasi tayangan terlalu singkat', 'Durasi konten kurang dari 10 detik'):
        found = re.search(re.escape(label) + r'\s+(\d+(?:[.,]\d+)?)%', rate, re.I)
        if found:
            reasons.append({'label': label, 'percent': float(found.group(1).replace(',', '.'))})
    bonus_match = re.search(r'Dapatkan bonus US\$([\d,.]+)', content, re.I)
    progress = re.search(r'(\d+)\s*/\s*(\d+)\s*reel yang memenuhi syarat', content, re.I)
    bonus = None
    if bonus_match:
        detail = pages.get('bonus_detail', '')
        date_range = re.search(r'Detail bonus\s*\n([^\n]+)', detail, re.I)
        bonus = {
            'amount_usd': amount(bonus_match.group(1)),
            'required_reels': match_number(r'Buat\s+(\d+)\s+reel', content),
            'minimum_duration_seconds': match_number(r'berdurasi\s+(\d+)\s+detik', content),
            'minimum_qualified_views': match_number(r'capai\s+(\d+)\s+tayangan yang memenuhi syarat', content),
            'minimum_reels_with_qualified_views': match_number(r'setidaknya\s+(\d+)\s+reel', content),
            'completed_reels': int(progress.group(1)) if progress else None,
            'days_remaining_at_check': match_number(r'(\d+)\s+hari tersisa', content),
            'period_label': date_range.group(1).strip() if date_range else None,
            'awarded': bool(re.search(r'bonus (?:telah diperoleh|berhasil didapatkan)', content, re.I)),
        }
    views = re.search(r'(?:^|\n)(\d[\d.]*)\s*\n[^\n]*%\s*\nTayangan\s*(?:\n|$)', insights)
    three_second = re.search(r'(?:^|\n)(\d[\d.]*)\s*\n[^\n]*%\s*\nTayangan 3 detik', insights)
    insight_period = re.search(r'28 hari terakhir:\s*([^\n]+)', insights)
    no_restrictions = bool(re.search(r'Tidak ada batasan|No restrictions', health, re.I))
    payout = payout_status(pages.get('payout', ''))
    result = {
        'version': VERSION, 'checked_at': checked_at, 'account_verified': account_verified,
        'program': {'state': program_state, 'evidence': 'Profil Anda menghasilkan uang' if active and account_verified else None},
        'policy': {'state': ('restricted' if restricted else 'clear' if no_restrictions else 'unknown') if account_verified else 'unknown'},
        'earnings': {'estimated_usd': amount(estimated.group(1)) if estimated and account_verified else None,
                     'period': period.group(1) if period else None,
                     'qualified_views': qualified if account_verified else None,
                     'rate_usd_per_1000': amount(earning_rate.group(1)) if earning_rate and account_verified else None,
                     'non_qualified_reasons': reasons if account_verified else []},
        'bonus': bonus if account_verified else None,
        'payout': payout if account_verified else payout_status(''),
        'insights': {'period': insight_period.group(1) if insight_period else None,
                     'views': int(views.group(1).replace('.', '')) if views and account_verified else None,
                     'three_second_views': int(three_second.group(1).replace('.', '')) if three_second and account_verified else None},
        'links': URLS, 'originality_policy_url': ORIGINALITY_URL,
        'limits': 'Status program, kelayakan setiap konten, bonus, dan pencairan adalah pemeriksaan berbeda. '
                  'Facebook menentukan kelayakan dan pendapatan aktual; tidak ada jaminan penghasilan atau waktu pencairan.',
    }
    result['actions'] = actions(result)
    result['production_briefs'] = briefs()
    return result


def actions(snapshot: dict) -> list[dict]:
    rows = []
    program, payout = snapshot['program']['state'], snapshot['payout']['state']
    if program != 'active':
        rows.append({'key':'program', 'priority':'Pertama', 'title':'Pastikan akses monetisasi akun',
                     'detail':'Periksa kelayakan dan pembatasan di Facebook. Tidak ada ambang pengikut generik yang diasumsikan oleh ClipForge.',
                     'href':URLS['overview']})
    rows.append({'key':'payout', 'priority':'Hari ini', 'title':'Verifikasi kesiapan pencairan',
                 'detail':'Periksa metode pembayaran, verifikasi identitas dan pajak bila diminta. Saldo nol belum membuktikan pembayaran siap.',
                 'href':URLS['payout'], 'state':payout})
    reasons = snapshot['earnings']['non_qualified_reasons']
    rows.append({'key':'retention', 'priority':'Fokus produksi', 'title':'Perbaiki dua detik pertama',
                 'detail':('Durasi tayangan terlalu singkat terdeteksi pada laporan akun. ' if reasons else '') +
                 'Tampilkan masalah atau hasil sejak awal, langsung demonstrasikan langkah. Hindari pembuka logo dan kalimat berputar; pertahankan batas 30–55 detik.',
                 'href':URLS['rate']})
    bonus = snapshot.get('bonus')
    rows.append({'key':'original_reels', 'priority':'Produksi otomatis',
                 'title':'Jalankan demonstrasi asli yang berbeda',
                 'detail':('Ikuti syarat bonus yang ditampilkan Facebook; unggahan lokal belum berarti bonus tercapai. ' if bonus else '') +
                 'FB Pro menyiapkan naskah dan demonstrasi digital asli sesuai jadwal, kemudian memeriksa hasil sebelum publikasi. '
                 'Rekaman sendiri dapat ditambahkan sebagai bahan opsional.',
                 'href':URLS['content']})
    rows.append({'key':'measure', 'priority':'Setelah 24–48 jam', 'title':'Pilih topik dari hasil nyata',
                 'detail':'Bandingkan tayangan yang memenuhi syarat, retensi/waktu tonton yang tersedia, serta alasan penolakan. Ulangi masalah yang diminati dengan contoh baru; jangan mengunggah salinan yang sama.',
                 'href':URLS['insights']})
    return rows


def briefs() -> list[dict]:
    items = [
        ('notifications', 'Notifikasi grup yang terlalu ramai',
         'Grup ramai, tapi belum ingin keluar?',
         'Rekam langkah membisukan notifikasi pada aplikasi yang Anda gunakan. Perlihatkan pengaturan sebelum dan sesudah; gunakan percakapan demo.',
         'Notifikasi grup bisa diatur sesuai kebutuhan. Periksa pengaturannya di HP Anda; nama menu dapat berbeda menurut versi aplikasi.\n\n#TipsHP #TeknologiSehariHari'),
        ('storage', 'Temukan file yang memakan ruang',
         'HP mulai penuh? Periksa file besarnya dulu.',
         'Rekam pemeriksaan penyimpanan pada HP sendiri, tunjukkan kategori atau file terbesar. Jangan menghapus data pribadi untuk kebutuhan rekaman.',
         'Periksa penggunaan penyimpanan sebelum merapikan file. Tinjau mana yang masih dibutuhkan agar data penting tetap tersimpan.\n\n#TipsHP #TeknologiSehariHari'),
        ('focus', 'Waktu fokus dengan notifikasi terkontrol',
         'Perlu fokus tanpa mematikan HP?',
         'Demonstrasikan fitur jangan ganggu/fokus yang benar-benar tersedia di HP Anda. Tunjukkan pengecualian panggilan penting dan cara mengembalikan pengaturan.',
         'Atur waktu fokus sesuai kebutuhan, termasuk panggilan yang tetap ingin diterima. Periksa pengecualiannya sebelum memakai mode ini.\n\n#TipsHP #TeknologiSehariHari'),
    ]
    return [{'key':key, 'title':title, 'hook':hook, 'recording':recording, 'caption':caption,
             'target_seconds':30, 'max_seconds':55, 'state':'needs_original_recording',
             'sequence':['0–2 dtk: masalah atau hasil', '2–5 dtk: konteks singkat', '5–23 dtk: langkah nyata', '23–30 dtk: hasil dan batasan'],
             'proof':'Butuh rekaman asli dan penjelasan sendiri; sembunyikan data pribadi. Ini brief, bukan video yang sudah diproduksi.'}
            for key,title,hook,recording,caption in items]


def clip_assessment(job) -> dict:
    owned = job.request.facebook_source_rights == 'owned' and job.request.confirm_source_rights
    return {'state':'original_candidate' if owned else 'facebook_review_required',
            'label':'Kandidat rekaman milik sendiri' if owned else 'Materi pihak lain perlu nilai tambah nyata',
            'message':'Klaim kepemilikan, QC teknis dan upload tidak menjamin monetisasi. Facebook menilai orisinalitas, kelayakan konten, serta tayangan yang memenuhi syarat.' if owned else
            'Izin penggunaan tidak otomatis memenuhi orisinalitas Facebook. Watermark, subtitle, crop dan perubahan kecepatan saja belum cukup; utamakan demonstrasi atau analisis asli Anda.'}


def collect(expected_profile: str) -> dict:
    """Read only authenticated pages; persist sanitized facts, never payout data."""
    pages, failures = {}, []
    with browser.connection() as context:
        identity = browser.session(context, expected_profile=expected_profile)
        if not identity.get('account_verified') or not expected_profile:
            raise RuntimeError('Periksa sesi dan identitas Facebook target sebelum analisis monetisasi.')
        for key,url in URLS.items():
            page = context.new_page()
            activity = None
            try:
                activity = start_background_page_activity(page)
                page.goto(url, wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(3000 if key != 'payout' else 6000)
                body = page.locator('body').inner_text(timeout=10000)
                if browser.active_user(context) != expected_profile:
                    raise RuntimeError('Profil Facebook berubah saat analisis.')
                if re.search(r'Halaman Ini Tidak Tersedia|This page isn.t available', body, re.I):
                    failures.append(key)
                    continue
                if key == 'payout':
                    # Convert sensitive page text immediately to status-only data.
                    pages['payout_status'] = payout_status(body)
                else:
                    pages[key] = body
                    if key == 'content' and re.search(r'Dapatkan bonus US\$', body):
                        try:
                            card = page.get_by_role('button', name=re.compile(r'^Dapatkan bonus US\$'))
                            if card.count() == 1:
                                card.first.press('Enter', timeout=5000)
                                page.get_by_text('Detail bonus', exact=True).wait_for(state='visible', timeout=5000)
                                pages['bonus_detail'] = page.locator('body').inner_text(timeout=5000)
                        except Exception:
                            pass
            except RuntimeError:
                raise
            except Exception:
                failures.append(key)
            finally:
                stop_background_page_activity(activity)
                page.close()
    result = parse_pages(pages, account_verified=True)
    result['payout'] = pages.get('payout_status') or payout_status('')
    result['actions'] = actions(result)
    result['unavailable_sections'] = failures
    return result
