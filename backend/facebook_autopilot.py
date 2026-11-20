"""Facebook-only durable schedule. No fake engagement and no catch-up bursts."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import hashlib
import re

VERSION = 1
ZONE = ZoneInfo('Asia/Jakarta')
DEFAULTS = dict(enabled=True, weekly_posts=13, weekly_stories=7,
                timezone='Asia/Jakarta', reel_times=['11:30', '18:30'], story_time='15:00')
ACTIVE = {'reserved', 'rendering', 'qc', 'qc_wait', 'ready', 'queued', 'running', 'needs_review'}


def local_now(current=None):
    return (current or datetime.now(timezone.utc)).astimezone(ZONE)


def config(saved=None):
    saved=saved or {}
    if not isinstance(saved,dict) or type(saved.get('enabled',True)) is not bool:
        raise ValueError('Pengaturan otomasi Facebook tidak valid; publikasi ditahan.')
    return {**DEFAULTS, 'enabled':saved.get('enabled',True), 'version':VERSION}


def week(current=None):
    day = local_now(current).date()
    start = day - timedelta(days=day.weekday())
    return start.isoformat(), (start+timedelta(days=6)).isoformat()


def bonus_plan(snapshot=None,uploads=(),current=None):
    """Prioritize the first real Reels, never equate uploads with a bonus award."""
    snapshot=snapshot or {};bonus=snapshot.get('bonus') or {}
    current=local_now(current)
    result=dict(state='unknown',priority=False,amount_usd=bonus.get('amount_usd'),
        required_reels=bonus.get('required_reels'),facebook_completed_reels=bonus.get('completed_reels'),
        minimum_duration_seconds=bonus.get('minimum_duration_seconds'),
        minimum_qualified_views=bonus.get('minimum_qualified_views'),
        minimum_reels_with_qualified_views=bonus.get('minimum_reels_with_qualified_views'),
        period_label=bonus.get('period_label'),checked_at=snapshot.get('checked_at'),
        locally_confirmed_reels=0,awarded=False,
        note='Bonus hanya tercapai setelah Facebook mengonfirmasi. Tayangan yang memenuhi syarat harus berasal dari penonton nyata.')
    if not snapshot.get('account_verified') or not bonus:return result
    if bonus.get('awarded') is True:return {**result,'state':'awarded','awarded':True}
    try:
        checked=datetime.fromisoformat(snapshot['checked_at'])
        if not 0<=(current-checked).total_seconds()<=86400:return {**result,'state':'refresh_required'}
        months={'jan':1,'feb':2,'mar':3,'apr':4,'mei':5,'jun':6,'jul':7,'agu':8,'ags':8,'sep':9,'okt':10,'nov':11,'des':12}
        label=bonus.get('period_label') or ''
        match=re.fullmatch(r'(\d{1,2})\s+([A-Za-z]+)\s*[-–]\s*(\d{1,2})\s+([A-Za-z]+)',label.strip())
        if not match:return {**result,'state':'refresh_required'}
        start_month,end_month=months[match[2].casefold()[:3]],months[match[4].casefold()[:3]]
        year=checked.astimezone(ZONE).year
        start_year=year-1 if start_month>end_month and checked.astimezone(ZONE).month<=end_month else year
        start=datetime(start_year,start_month,int(match[1]),tzinfo=ZONE).date()
        end=datetime(start_year+(end_month<start_month),end_month,int(match[3]),tzinfo=ZONE).date()
        if not start<=current.date()<=end:return {**result,'state':'outside_period'}
        required=bonus['required_reels'];minimum=bonus['minimum_duration_seconds']
        if type(required) is not int or not 1<=required<=10 or type(minimum) is not int or minimum<=0:return result
        if minimum>55:return {**result,'state':'duration_not_supported'}
        confirmed=0
        for row in uploads:
            length=row.get('duration_seconds')
            if (row.get('kind','reel')=='reel' and row.get('upload_confirmed') is True and row.get('video_url')
                    and type(length) in (int,float) and minimum<=length<=55
                    and start<=local_now(datetime.fromisoformat(row['created_at'])).date()<=end):
                confirmed+=1
        native=bonus.get('completed_reels')
        if type(native) is not int or native<0:return result
        remaining=max(0,required-max(native,confirmed))
        return {**result,'locally_confirmed_reels':confirmed,'remaining_reels_to_publish':remaining,
                'state':'produce_reels' if remaining else 'await_facebook_confirmation','priority':remaining>0}
    except (ValueError,TypeError,KeyError,OverflowError):return result


def slots(current=None, settings=None, *, bonus_priority=False):
    """Only today's slots are eligible: missed days never become a posting flood."""
    current = local_now(current)
    settings = config(settings)
    day = current.date()
    start, end = week(current)
    rows = []
    # 2 x Monday-Saturday + 1 Sunday = 13. One independent Story daily.
    for kind,times in [('reel', settings['reel_times'][:1] if day.weekday()==6 and not bonus_priority else settings['reel_times']),
                       ('story', [] if bonus_priority else [settings['story_time']])]:
        for position,clock in enumerate(times):
            hour,minute = map(int,clock.split(':'))
            due = datetime.combine(day,datetime.min.time(),ZONE).replace(hour=hour,minute=minute)
            key = f'{day.isoformat()}:{kind}:{position}'
            rows.append(dict(key=key, kind=kind, due_at=due.isoformat(), day=day.isoformat(),
                week_start=start, week_end=end, due=due<=current,
                content_seed=hashlib.sha256(key.encode()).hexdigest()))
    return sorted(rows,key=lambda row:row['due_at'])


def eligible(current, settings, runs, uploads, monetization=None):
    settings = config(settings)
    if not settings['enabled']:
        return None
    current = local_now(current)
    # All platforms share a browser, but this bound also spaces Facebook slots.
    for upload in uploads:
        value = upload.get('created_at')
        if value:
            age = (current-datetime.fromisoformat(value)).total_seconds()
            if 0<=age<3*3600:
                return None
    if any(row.get('status') in ACTIVE for row in runs.values()):
        return None
    for slot in slots(current,settings,bonus_priority=bonus_plan(monetization,uploads,current)['priority']):
        if slot['due'] and slot['key'] not in runs:
            return slot
    return None


def snapshot(settings, runs, uploads, activity=None, current=None, monetization=None):
    settings = config(settings)
    start,end = week(current)
    relevant = [row for row in runs.values() if row.get('week_start')==start]
    counts = {kind:sum(row.get('upload_confirmed') is True and bool(row.get('video_url')) and row.get('kind','reel')==kind
                      and start <= local_now(datetime.fromisoformat(row['created_at'])).date().isoformat() <= end
                      for row in uploads) for kind in ('reel','story')}
    pending = sorted([row for row in runs.values() if row.get('status') in ACTIVE],key=lambda r:r.get('created_at',''))
    bonus=bonus_plan(monetization,uploads,current)
    upcoming = [row for row in slots(current,settings,bonus_priority=bonus['priority']) if row['key'] not in runs]
    return dict(version=VERSION, config=settings, week_start=start, week_end=end,
                runtime_state='paused' if not settings['enabled'] else 'working' if pending else 'waiting',
                confirmed_posts=counts['reel'], confirmed_stories=counts['story'],
                produced=sum(bool(row.get('rendered_at')) for row in relevant),
                active=pending[0] if pending else None,
                runs=sorted(relevant,key=lambda r:r.get('created_at',''),reverse=True)[:30],
                next_slot=upcoming[0] if upcoming else None, activity=activity,bonus_priority=bonus,
                plan_note='Rencana Senin–Minggu: 13 Reel dan 7 cerita. Slot terlewat tidak ditumpuk. '
                          'Hasil terkonfirmasi dihitung terpisah dari kredit tugas Facebook.')
