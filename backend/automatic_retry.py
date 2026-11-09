"""Conservative retries for proven pre-submission failures, never unknown posts."""
from __future__ import annotations

MAX_RETRIES = 3
BACKOFF_SECONDS = (60, 180, 600)


def tiktok_submission_possible(logs, *, started=False, accepted=False):
    if started or accepted:
        return True
    return any((str(line).startswith('POST_') and not str(line).startswith('POST_BASELINE_'))
        or str(line).startswith(('UPLOAD_CONFIRMED:', 'VIDEO_URL:'))
        or 'tombol post diklik' in str(line).casefold() for line in logs)


def tiktok_retry_reason(error, logs, *, started=False, accepted=False):
    if tiktok_submission_possible(logs,started=started,accepted=accepted):
        return ''
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
    if 'identitas akun' in message and 'halaman profil belum selesai' in message:
        return 'identity_still_loading'
    if 'connect_over_cdp' in message and any(word in message for word in ('timeout','econnrefused','connection refused')):
        return 'browser_connection_before_post'
    return ''


def retry_count(upload):
    # Migrate the older one-shot caption reservation without resetting budget.
    return max(upload.auto_retry_count, int('CAPTION_READY_RETRY_ONCE' in upload.logs))


def backoff_seconds(count):
    return BACKOFF_SECONDS[min(max(0,count),len(BACKOFF_SECONDS)-1)]
