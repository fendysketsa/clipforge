"""Terminal local history can finish without manufacturing publication approval."""
from copy import deepcopy
import json
import stat

import pytest

import autonomous_history as policy


def job(identity='job', **changes):
    row = dict(id=identity, status='failed', created_at='2026-11-21T00:00:00Z',
        finished_at='2026-11-21T00:10:00Z', source_url='https://www.youtube.com/watch?v=abcdefghijk',
        request=dict(url='https://www.youtube.com/watch?v=abcdefghijk', target_platform='standard',
            scheduled_public_source_credit=True, publication_review_required=True, review_only=False,
            scheduled_news_hot=False, clip_mode='highlight_5m', cron_daily_lane='long',
            cron_production_day='2026-11-21', paired_short_job_id='paired-short'),
        error='RuntimeError: insufficient_or_excessive_compilation_material', clips=[], candidates=[], logs=[])
    row.update(changes)
    return row


def clip(name='unapproved', approved=False):
    return dict(name=name + '.mp4', url='/outputs/job/clips/' + name + '.mp4',
                size_bytes=100, is_correct=approved, render_qc_passed=True,
                render_qc_blocking=False, youtube_upload_ready=False)


def news(identity='news'):
    row = job(identity, status='completed', error=None, clips=[clip()], candidates=[{'source': 'fixture'}])
    row['request'].update(scheduled_news_hot=True, clip_mode='short', publication_review_required=False)
    return row


def decide(row, **evidence):
    return policy.decision(row, workspace_exists=False, **evidence)


def test_current_five_backlog_shapes_have_explicit_terminal_decisions():
    material = job('long-material')
    anchor = job('long-anchor', error='clipper.py exited with code 1', logs=[
        'Long Story dibatalkan karena momen Short wajib tidak dapat dipertahankan dengan',
        'batas kalimat yang aman.'])
    selection = job('selection', error=policy._SELECTION_EXHAUSTED + ' Window 105 detik sudah dicoba.')
    first_news, second_news = news('first-news'), news('second-news')
    rows = [material, anchor, selection, first_news, second_news]
    before = deepcopy(rows)
    plans = [decide(row) for row in rows]
    assert [plan['action'] for plan in plans] == ['archive_empty_failure'] * 3 + ['drop_source'] * 2
    assert [plan['reason'] for plan in plans[:3]] == [
        'long_material_rejected', 'long_anchor_context_rejected', 'selection_recovery_exhausted']
    assert all(plan['decision'] == 'DROP_SOURCE' and not plan['upload_allowed'] for plan in plans)
    assert rows == before  # The old publication/review flags remain evidence, never approval.


@pytest.mark.parametrize('flag', ['review_only', 'manual', 'facebook', 'facebook_protected',
                                  'process', 'checkpoint', 'recovery', 'evidence'])
def test_active_manual_or_unproven_work_is_retained(flag):
    row = job(); evidence = {}
    if flag == 'review_only': row['request']['review_only'] = True
    elif flag == 'manual': row['request']['scheduled_public_source_credit'] = False
    elif flag == 'facebook': row['request']['target_platform'] = 'facebook'
    elif flag == 'facebook_protected': evidence['facebook_protected'] = True
    elif flag == 'process': evidence['process_active'] = True
    elif flag == 'checkpoint': evidence['checkpoint_busy'] = True
    elif flag == 'evidence': evidence['evidence_complete'] = False
    elif flag == 'recovery':
        evidence['jobs'] = [dict(id='child', status='queued', repair_source_job_id='job')]
    assert decide(row, **evidence)['action'] == 'retain'


@pytest.mark.parametrize('status', ['queued', 'running', 'cancelled', 'completed'])
def test_only_proven_terminal_failed_empty_job_is_archived(status):
    assert decide(job(status=status))['action'] == 'retain'


@pytest.mark.parametrize('artifact', ['clip', 'candidate', 'workspace'])
def test_empty_failure_requires_no_remaining_artifacts(artifact):
    row = job()
    if artifact == 'clip': row['clips'] = [clip()]
    if artifact == 'candidate': row['candidates'] = [{'source': 'fixture'}]
    assert policy.decision(row, workspace_exists=artifact == 'workspace')['action'] == 'retain'


@pytest.mark.parametrize('platform', ['youtube', 'tiktok'])
@pytest.mark.parametrize('kind', ['queued', 'running', 'unknown', 'confirmed', 'preselection_failure'])
def test_platform_record_stays_with_its_recovery_owner(platform, kind):
    row = dict(source_job_id='job', id='upload', status='failed', dry_run=False, logs=[])
    if kind in {'queued', 'running'}: row['status'] = kind
    elif kind == 'unknown':
        if platform == 'youtube': row['video_url'] = 'https://www.youtube.com/watch?v=abcdefghijk'
        else: row['submission_started'] = True
    elif kind == 'confirmed':
        row.update(status='completed', upload_confirmed=True,
            video_url='https://www.youtube.com/watch?v=abcdefghijk',
            profile_url='https://www.tiktok.com/@fixture/video/1234567890123456789')
    elif kind == 'preselection_failure': row['logs'] = ['UPLOAD_FAILED_BEFORE_FILE_SELECTION: setup failed']
    assert decide(job(), **{platform: [row]})['action'] == 'retain'


def test_dry_run_and_unrelated_upload_do_not_strand_an_empty_failure():
    assert decide(job(), youtube=[dict(source_job_id='other', status='running'),
        dict(source_job_id='job', status='running', dry_run=True)])['action'] == 'archive_empty_failure'


@pytest.mark.parametrize('error', ['Connection reset by peer', 'Temporary failure in name resolution',
                                  'clipper.py exited with code 1', 'QC provider returned HTTP 429'])
def test_generic_or_transient_failure_is_not_falsely_treated_as_exhausted(error):
    assert decide(job(error=error))['action'] == 'retain'


def test_news_drop_keeps_approved_sibling_and_does_not_change_signoff():
    row = news(); row['clips'].append(clip('approved', approved=True))
    before = deepcopy(row)
    plan = decide(row)
    assert plan['action'] == 'drop_source' and plan['clip_urls'] == [row['clips'][0]['url']]
    assert row == before and not row['clips'][0]['is_correct']
    row['clips'][0]['is_correct'] = True
    assert decide(row)['action'] == 'retain'


def test_non_news_review_hold_is_preserved_and_not_used_as_fake_approval():
    row = news(); row['request']['scheduled_news_hot'] = False
    assert decide(row)['action'] == 'retain'
    assert not row['clips'][0]['is_correct']


@pytest.mark.parametrize('url', ['https://example.test/video.mp4', '/outputs/../secrets',
                               '/outputs/%2E%2E/secret', '/outputs/job/clip.mp4?token=secret'])
def test_invalid_local_artifact_namespace_is_retained(url):
    row = news(); row['clips'][0]['url'] = url
    assert decide(row)['reason'] == 'invalid_artifact_identity'


def test_new_approval_or_artifact_identity_invalidates_old_plan(tmp_path):
    row = news(); plan = decide(row)
    row['clips'][0]['is_correct'] = True
    with pytest.raises(ValueError, match='evidence changed'):
        policy.archive(tmp_path, row, plan, checkpoint_refs=[], now='2026-11-21T01:00:00Z')
    assert not list(tmp_path.iterdir())


def test_private_receipt_retains_holds_cooldown_refs_and_remote_non_action(tmp_path):
    row = job(); row['request']['ai_api_key'] = 'secret-key'
    row['logs'] = ['Cookie: SID=credential', 'failed https://user:pass@cdn.test/media?token=signature']
    refs = [dict(run_id='parent', status='failed', selection_rejected_at='2026-11-21T00:10:00Z',
                 long_job_id=row['id'], source_url=row['source_url'], api_key='hidden')]
    target = policy.archive(tmp_path, row, decide(row), checkpoint_refs=refs, now='2026-11-21T01:00:00Z')
    audit = json.loads(target.read_text())
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert audit['original_request']['publication_review_required'] is True
    assert audit['original_request']['cron_production_day'] == '2026-11-21'
    assert audit['checkpoint_refs'][0]['selection_rejected_at'] == '2026-11-21T00:10:00Z'
    assert audit['source_id'] == 'abcdefghijk'
    assert audit['original_request']['url'] == 'https://www.youtube.com/watch?v=abcdefghijk'
    assert audit['remote_action'] == 'none' and audit['manual_hold_released'] is False
    assert all(value not in target.read_text() for value in ('secret-key', 'credential', 'signature', 'user:pass', 'hidden'))


def test_write_failure_does_not_replace_prior_receipt_or_leave_temporary_files(tmp_path, monkeypatch):
    row = job(); plan = decide(row)
    target = policy.archive(tmp_path, row, plan, checkpoint_refs=[], now='first')
    original = target.read_bytes()
    def unavailable(*args): raise OSError('disk unavailable')
    monkeypatch.setattr(policy.os, 'replace', unavailable)
    with pytest.raises(OSError): policy.archive(tmp_path, row, plan, checkpoint_refs=[], now='second')
    assert target.read_bytes() == original
    assert list(tmp_path.iterdir()) == [target]


def test_planning_snapshot_distinguishes_processing_waiting_and_archiving():
    assert policy.planning_snapshot(decide(job()))['state'] == 'archiving'
    assert policy.planning_snapshot(decide(job(status='running')))['state'] == 'processing'
    assert policy.planning_snapshot(decide(job(error='timeout')))['state'] == 'waiting'
    assert policy.planning_snapshot(decide(job()), archived=True)['state'] == 'archived'
    metadata = policy.planning_snapshot(dict(action='retain', reason='remote_or_submission_evidence', urgent=True))
    assert metadata['state'] == 'urgent' and metadata['urgent'] is True
