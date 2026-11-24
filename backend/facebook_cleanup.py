"""Delete published or proven undispatched terminal artifacts, keeping receipts.

No remote delete, no source-input cleanup, and no cleanup of ambiguous uploads.
The persisted deletion checkpoint makes interruptions safe to resume at startup.
"""
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
import re
import threading

import facebook_browser as browser

VERSION = 1
TERMINAL_VERSION = 1
_lock = threading.Lock()


def now():
    return datetime.now(timezone.utc).isoformat()


def confirmed(row):
    if (row.get('status') != 'completed' or row.get('upload_confirmed') is not True
            or row.get('submission_started') is not True
            or row.get('target_email') != browser.TARGET_EMAIL
            or row.get('kind', 'reel') not in {'reel','story'}
            or not re.fullmatch(r'\d+', str(row.get('profile_id', '')))
            or not re.fullmatch(r'[a-f0-9]{64}', str(row.get('sha256', '')))):
        return False
    url = row.get('video_url') or ''
    if row.get('kind', 'reel') == 'story':
        return bool(browser.story_url(url, row['profile_id']) == url == row.get('remote_story_url'))
    return bool(browser.reel_url(url) == url)


def terminal(row):
    """A skipped badge alone never authorizes deleting an unconfirmed file."""
    if (row.get('status')!='failed' or row.get('kind')!='story'
            or row.get('recovery_status')!='skipped' or row.get('recovery_action')!='skip_expired_story'
            or row.get('recovery_version')!=1
            or row.get('submission_started') is not False or row.get('upload_confirmed') is not False
            or row.get('submission_accepted') or row.get('video_url') or row.get('remote_story_url')
            or row.get('candidate_video_urls')
            or row.get('target_email')!=browser.TARGET_EMAIL
            or not re.fullmatch(r'\d+',str(row.get('profile_id','')))
            or not re.fullmatch(r'[a-f0-9]{64}',str(row.get('sha256','')))):
        return False
    try:
        created=datetime.fromisoformat(row['created_at'])
        receipt=datetime.fromisoformat(row['recovery_at'])
        current=datetime.now(timezone.utc)
        return (current-created).total_seconds()>=86400 and created<=receipt<=current
    except (ValueError,TypeError,KeyError):return False


def retire_terminal_clip(api,job,clip_url):
    """Persist removal of a terminal card; roll back memory if persistence fails."""
    remaining=[clip for clip in job.clips if clip.url!=clip_url]
    if remaining:
        api.jobs[job.id]=job.model_copy(update=dict(clips=remaining,updated_at=now()))
    else:api.jobs.pop(job.id,None)
    try:api.save_jobs_unlocked()
    except Exception:
        api.jobs[job.id]=job
        raise


def cleanup_once(api, store):
    result = dict(cleaned_uploads=0, removed_files=0, freed_bytes=0, deferred=0, errors=[])
    # Match upload-admission order. Nonblocking acquisition also prevents a
    # lock-order inversion with API readers or a concurrently finishing worker.
    locks = [_lock, api.youtube_upload_creation_lock, api.tiktok_upload_creation_lock,
             api.long_qc_lock, api.process_lock, api.jobs_lock, store.lock,
             api.youtube_uploads_lock, api.tiktok_uploads_lock]
    with ExitStack() as stack:
        for lock in locks:
            if not lock.acquire(blocking=False):
                result['deferred'] += 1
                return result
            stack.callback(lock.release)
        uploads = store.data['uploads']
        root = api.OUTPUTS_DIR.resolve()
        for row in uploads.values():
            prior = row.get('local_cleanup') or {}
            discard=terminal(row)
            if not (confirmed(row) or discard) or prior.get('state') in {'deleted', 'missing'}:
                continue
            disposition='discarded' if discard else 'published'
            job = api.jobs.get(row.get('job_id'))
            media = api.output_path_from_url(row['clip_url'])
            if not job and media is not None and not media.exists():
                # Older operator cleanup can remove a local job while the
                # durable upload ledger remains. No file deletion is inferred.
                row['local_cleanup'] = dict(state='missing',completed_at=now(),freed_bytes=0,
                    removed_files=0,remote_url=row.get('video_url'),disposition=disposition)
                store.save()
                continue
            if (not job or job.request.target_platform != 'facebook' or job.status != 'completed'
                    or job.request.publication_review_required or job.request.review_only
                    or job.id in api.job_processes
                    or (job.id + '\n' + row['clip_url']) in api.long_qc_active
                    or any(child.status in {'queued', 'running'} and
                           (child.repair_source_job_id == job.id or child.repair_source_clip_url == row['clip_url'])
                           for child in api.jobs.values())):
                result['deferred'] += 1
                continue
            clip = next((c for c in job.clips if c.url == row['clip_url']), None)
            if not clip or media is None or not media.is_relative_to(root) or media == root:
                result['deferred'] += 1
                continue
            # Preserve any cross-platform dependency, including an existing
            # completed post: this policy owns the Facebook lane only.
            foreign = [*api.youtube_uploads.values(), *api.tiktok_uploads.values()]
            if any(r.clip_url == row['clip_url'] or api.output_path_from_url(r.clip_url) == media for r in foreign):
                result['deferred'] += 1
                continue
            if any(r['id'] != row['id'] and
                   (r.get('clip_url') == row['clip_url'] or api.output_path_from_url(r.get('clip_url')) == media)
                   and not confirmed(r) for r in uploads.values()):
                result['deferred'] += 1
                continue
            try:
                if media.exists() and api.file_sha256(media) != row['sha256']:
                    result['deferred'] += 1
                    continue
                if not media.exists() and prior.get('state') not in {'deleting', 'error'}:
                    if discard:retire_terminal_clip(api,job,row['clip_url'])
                    row['local_cleanup'] = dict(state='missing', completed_at=now(), freed_bytes=0,
                        removed_files=0, remote_url=row.get('video_url'),disposition=disposition)
                    store.save()
                    continue
                paths = set(api.clip_artifact_paths(clip))
                paths.update({media.with_name(media.stem + '_facebook_caption.txt'),
                              media.with_suffix('.auto-qc.json')})
                owned = root / 'facebook_autopilot' / job.id
                # Only the exact, single-output, generated workspace owns its
                # intermediate neural audio and source-plan files as well.
                whole = bool(job.request.facebook_autopilot_key and len(job.clips) == 1
                             and media.parent == owned and not owned.is_symlink())
                if whole and owned.exists():
                    paths.update(p for p in owned.rglob('*') if p.is_file() or p.is_symlink())
                # Resolve every dependency, including siblings, thumbnails,
                # nested jobs, and upload records, before unlinking anything.
                protected = set()
                for other in api.jobs.values():
                    for sibling in other.clips:
                        if other.id != job.id or sibling.url != clip.url:
                            protected.update(api.clip_artifact_paths(sibling))
                    source = api.output_path_from_url(other.request.source_file)
                    if source:
                        protected.add(source)
                for upload in foreign:
                    path = api.output_path_from_url(upload.clip_url)
                    if path:
                        protected.add(path)
                for upload in uploads.values():
                    path = api.output_path_from_url(upload.get('clip_url'))
                    if path and path != media:
                        protected.add(path)
                protected = {p.resolve() for p in protected}
                if (any(p.is_symlink() or not p.resolve().is_relative_to(root) or p.resolve() == root for p in paths)
                        or any(p.resolve() in protected for p in paths)):
                    result['deferred'] += 1
                    continue
                # A reference inside a generated workspace preserves that
                # workspace as a unit (including unlisted sibling intermediates).
                if whole and any(p.is_relative_to(owned) for p in protected):
                    result['deferred'] += 1
                    continue
                existing = sorted((p for p in paths if p.is_file()), key=str)
                checkpoint = dict(state='deleting', started_at=prior.get('started_at') or now(),
                    remote_url=row.get('video_url'), sha256=row['sha256'],disposition=disposition,
                    reason=row.get('recovery_action') if discard else 'remote_confirmed',
                    removed_files=prior.get('removed_files', 0), freed_bytes=prior.get('freed_bytes', 0))
                row['local_cleanup'] = checkpoint
                row.setdefault('title',clip.title or job.source_title or clip.name)
                store.save()  # Persist remote identity and intent before unlink.
                for path in existing:
                    size = path.stat().st_size
                    path.unlink()
                    checkpoint['removed_files'] += 1
                    checkpoint['freed_bytes'] += size
                    result['removed_files'] += 1
                    result['freed_bytes'] += size
                if whole and owned.exists():
                    for folder in sorted((p for p in owned.rglob('*') if p.is_dir()),
                                         key=lambda p: len(p.parts), reverse=True):
                        folder.rmdir()
                    owned.rmdir()
                if discard:retire_terminal_clip(api,job,row['clip_url'])
                checkpoint.update(state='deleted', completed_at=now())
                store.save()
                result['cleaned_uploads'] += 1
            except OSError as exc:
                checkpoint = row.setdefault('local_cleanup', {})
                checkpoint.update(state='error', error=type(exc).__name__, checked_at=now())
                store.save()
                result['errors'].append(dict(upload_id=row['id'], error=type(exc).__name__))
        return result
