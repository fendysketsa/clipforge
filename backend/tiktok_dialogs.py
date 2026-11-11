"""Recognize only the observed upload-cancellation prompt, never Post consent."""
import re


def is_cancel_upload_confirmation(text: str) -> bool:
    clean = ' '.join(str(text or '').split()).rstrip('.')
    return bool(re.fullmatch(
        r'(?:Are you sure|Sure) you want to cancel your upload\? '
        r'Any edits to your current upload will not be saved\. No Yes', clean, re.I))
