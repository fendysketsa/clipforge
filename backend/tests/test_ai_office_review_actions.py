"""Human review buttons: retry differently or remove, never auto-approve."""
import json
from datetime import datetime, timezone

import pytest

import api


def held_job(job_id='review-job'):
    now = datetime.now(timezone.utc).isoformat()
    return api.ClipJob(
        id=job_id, source_job_id=job_id, clip_url='/clip.mp4', clip_name='clip.mp4',
        status='completed', created_at=now, updated_at=now, title='Review',
        source_title='Review', request=api.ClipJobRequest(url='https://www.youtube.com/watch?v=' + 'a' * 11),
        clips=[api.ClipFile(name='clip.mp4', size_bytes=1024, url='/clip.mp4', path='/clip.mp4')],
    )


def test_retry_passes_an_alternate_variant_to_the_owner(monkeypatch):
    job = held_job()
    monkeypatch.setattr(api, 'jobs', {job.id: job})
    captured = {}
    def fake(job_id, repair):
        captured.update(job_id=job_id, variant=repair.variant, url=repair.url)
        return type('R', (), {'id': 'new-repair'})()
    monkeypatch.setattr(api, 'repair_job_clip_context', fake)
    result = api.ai_office_retry_review(job.id)
    assert result['job_id'] == 'new-repair'
    assert captured['job_id'] == job.id and captured['url'] == '/clip.mp4'
    assert captured['variant'].startswith('alternate_')


def test_delete_removes_only_held_job_and_keeps_a_receipt(tmp_path, monkeypatch):
    job = held_job()
    monkeypatch.setattr(api, 'jobs', {job.id: job})
    monkeypatch.setattr(api, 'JOBS_PATH', tmp_path / 'jobs.json')
    monkeypatch.setattr(api, 'save_jobs_unlocked', lambda: None)
    result = api.ai_office_delete_review(job.id)
    assert result['removed'] == 1 and job.id not in api.jobs
    receipt = json.loads((tmp_path / 'review_decisions' / (job.id + '.json')).read_text())
    assert receipt['decision'] == 'operator_removed' and receipt['remote_action'] == 'none'
