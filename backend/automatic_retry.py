"""Conservative retries for proven pre-submission failures, never unknown posts."""
from __future__ import annotations
from tiktok_dialogs import is_cancel_upload_confirmation

MAX_RETRIES = 3
BACKOFF_SECONDS = (60, 180, 600)
TIKTOK_BROWSER_UNAVAILABLE = (
    'Chrome TikTok belum tersedia. Sesi login tersimpan dipertahankan; '
    'menunggu koneksi browser pulih. File belum dipilih dan Post belum dikirim.'
)


def tiktok_submission_possible(logs, *, started=False, accepted=False):
    if started or accepted:
        return True
    return any((str(line).startswith('POST_') and not str(line).startswith('POST_BASELINE_'))
        or str(line).startswith(('UPLOAD_CONFIRMED:', 'VIDEO_URL:'))
        or 'tombol post diklik' in str(line).casefold() for line in logs)


def tiktok_retry_reason(error, logs, *, started=False, accepted=False):
    if tiktok_submission_possible(logs,started=started,accepted=accepted):
        return ''
    if error == TIKTOK_BROWSER_UNAVAILABLE:
        return 'browser_connection_before_post'
    message=str(error or '').casefold()
    if any(word in message for word in ('captcha','wrong_account','akun browser bukan','content safety',
            'copyright','hak cipta','content id','community guideline','pelanggaran','batas harian',
            'daily limit','login ulang','belum login','session tidak valid')):
        return ''
    if 'kolom caption tiktok' in message and 'belum diposting' in message:
        return 'caption_not_ready'
    if 'kolom caption tiktok tidak ditemukan setelah video dipilih' in message:
        return 'caption_editor_not_ready'
    if 'caption tiktok tidak dapat menggantikan judul otomatis' in message and 'video tidak diposting' in message:
        return 'caption_replacement_not_ready'
    if ('transfer file cdp tiktok gagal sebelum posting' in message
            or ('tidak dapat menerima file video' in message and 'tidak ada posting yang dibuat' in message)):
        return 'file_transfer_before_post'
    if 'tombol post tiktok' in message and ('video tidak diterbitkan' in message or 'belum diposting' in message):
        return 'post_button_not_ready'
    if 'input upload tiktok tidak ditemukan' in message:
        return 'upload_form_not_ready'
    if 'daftar posting tiktok belum siap diverifikasi' in message and 'file belum dipilih' in message:
        return 'post_baseline_not_ready'
    if 'draft tiktok belum dapat dibuang' in message and 'belum diposting' in message:
        return 'draft_discard_not_ready'
    prefix = 'dialog tiktok menghalangi form upload: '
    suffix = '. video belum diposting.'
    if message.startswith(prefix) and message.endswith(suffix):
        if is_cancel_upload_confirmation(message[len(prefix):-len(suffix)]):
            return 'upload_cancel_dialog_before_post'
    if ('kontrol privasi tiktok' in message or 'pilihan privasi tiktok' in message) and 'belum diposting' in message:
        return 'privacy_control_not_ready'
    if 'pengaturan privasi tiktok belum selesai' in message and 'post belum dikirim' in message:
        return 'privacy_control_not_ready'
    if ('pilihan only you/' in message or 'pilihan everyone/' in message) and 'upload tidak diterbitkan' in message:
        return 'privacy_control_not_ready'
    if 'locator.inner_text' in message and 'timeout' in message:
        if any('button:has-text' in str(line).casefold() and any(
                label in str(line).casefold() for label in ('everyone','only you','semua orang','hanya anda'))
                for line in logs):
            return 'privacy_control_not_ready'
    if 'kontrol tiktok tidak dapat diklik' in message and 'belum diposting' in message:
        # Older workers wrapped the Playwright error. Only an exact privacy
        # picker locator makes that legacy generic control failure retryable.
        if any('button:has-text' in str(line).casefold() and any(
                label in str(line).casefold() for label in ('everyone','only you','semua orang','hanya anda'))
                for line in logs):
            return 'privacy_control_not_ready'
    if 'identitas akun' in message and 'halaman profil belum selesai' in message:
        return 'identity_still_loading'
    if 'connect_over_cdp' in message and any(word in message for word in ('timeout','econnrefused','connection refused')):
        return 'browser_connection_before_post'
    return ''


def retry_count(upload):
    # Migrate the older one-shot caption reservation without resetting budget.
    return max(upload.auto_retry_count, int('CAPTION_READY_RETRY_ONCE' in upload.logs))


def tiktok_verified_session_recovery_reason(error, logs, *, started=False, accepted=False):
    """An old isolated-browser rejection is recoverable only after live validation."""
    if tiktok_submission_possible(logs, started=started, accepted=accepted):
        return ''
    if str(error or '') == 'Backend restart saat upload TikTok berlangsung. Periksa TikTok Studio sebelum retry agar tidak membuat posting duplikat.':
        if (any(str(line).startswith('TARGET_ACCOUNT_CONFIRMED:') for line in logs)
                and any(str(line).startswith('POST_BASELINE_VISIBLE_IDS:')
                        and not str(line).endswith('unavailable') for line in logs)):
            return 'restart_before_post_revalidated'
        return ''
    if str(error or '') != 'Sesi TikTok belum login. Klik Login TikTok lalu lanjutkan dengan Google di Chrome.':
        return ''
    if (any(str(line).startswith('TARGET_ACCOUNT_CONFIRMED:') for line in logs)
            and any(str(line).startswith('Storage-state TikTok ditolak;') for line in logs)
            and any(str(line).startswith('Recovery Chrome TikTok belum tersedia:') for line in logs)):
        return 'live_session_revalidated_before_post'
    return ''


def backoff_seconds(count):
    return BACKOFF_SECONDS[min(max(0,count),len(BACKOFF_SECONDS)-1)]
