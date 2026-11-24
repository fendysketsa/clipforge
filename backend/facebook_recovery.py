"""Bounded recovery decisions. Never approve QC or erase a Post checkpoint."""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import math

QC_DELAYS=(300,900,3600,21600)
VERSION=1


def retry_after_seconds(headers):
    raw=(headers or {}).get('Retry-After','')
    try:
        value=float(raw)
    except (TypeError,ValueError):
        try:value=(parsedate_to_datetime(raw)-datetime.now(timezone.utc)).total_seconds()
        except (TypeError,ValueError,OverflowError):return 0
    return min(86400,max(0,int(value))) if math.isfinite(value) else 0


def qc_wait_changes(row,record,current=None):
    current=current or datetime.now(timezone.utc)
    count=max(1,int(row.get('qc_attempts',1)))
    delay=max(QC_DELAYS[min(count-1,len(QC_DELAYS)-1)],record.get('retry_after_seconds',0))
    return dict(next_qc_at=(current+timedelta(seconds=delay)).isoformat(),
        recovery_action='retry_qc_with_backoff',recovery_version=VERSION)


def qc_due(row,current=None):
    current=current or datetime.now(timezone.utc)
    value=row.get('next_qc_at')
    try:
        # Legacy rows are checked once after a ten-minute quiet period.
        due=datetime.fromisoformat(value) if value else datetime.fromisoformat(row['last_qc_at'])+timedelta(seconds=600)
        return current>=due
    except (ValueError,TypeError,KeyError):return not value


def upload_plan(row,current=None):
    current=current or datetime.now(timezone.utc)
    if row.get('status') not in {'failed','needs_review'} or row.get('upload_confirmed'):
        return 'none'
    if (row.get('status')=='needs_review' or row.get('submission_started')
            or row.get('video_url') or row.get('remote_story_url')):
        return 'verify_remote'
    if row.get('submission_started') is not False:return 'inspect_failure'
    if row.get('recovery_status')=='skipped':return 'none'
    message=str(row.get('message') or '').casefold()
    audience=row.get('kind')=='story' and 'audiens publik story belum terbukti' in message
    if audience:
        try:
            if (current-datetime.fromisoformat(row['created_at'])).total_seconds()>=86400:
                return 'skip_expired_story'
        except (ValueError,TypeError,KeyError):pass
        return 'wait_story_audience'
    if row.get('attempts',1)>=3:return 'retry_exhausted'
    if any(word in message for word in ('timeout','timed out','err_address_unreachable','err_connection','koneksi','network')):
        return 'retry_transfer'
    return 'inspect_failure'
