from types import SimpleNamespace as NS

import pytest

import api
import tiktok_uploader as uploader
from test_tiktok_caption_recovery import failed_caption


@pytest.fixture
def privacy_failure(failed_caption):
    path, upload, started = failed_caption
    api.jobs[upload.source_job_id].clips[0].is_correct = True
    upload.auto_retry_count = 3
    upload.logs += ['PRIVACY_REQUESTED:Only you']
    upload.error = 'Pengaturan privasi TikTok belum selesai: diminta Only you, terbaca belum terbaca. File sudah ditransfer; Post belum dikirim. Detail: Kontrol privasi TikTok belum siap. Video belum diposting.'
    return path, upload, started


def test_draft_repair_reuses_record_without_resetting_retry_budget(privacy_failure):
    _, upload, _ = privacy_failure
    repaired = api.resume_tiktok_privacy_draft(upload.id)
    assert repaired.id == upload.id and repaired.status == 'queued'
    assert repaired.auto_retry_count == 3 and repaired.resume_existing_draft_only
    assert repaired.caption == upload.caption and repaired.clip_sha256 == upload.clip_sha256
    assert repaired.visibility == 'only_you'
    assert api.resume_tiktok_privacy_draft(upload.id).id == upload.id
    assert repaired.logs.count('DRAFT_PRIVACY_REPAIR_RESERVED') == 1


@pytest.mark.parametrize('risk', ['intent', 'started', 'accepted', 'url', 'public', 'wrong_account',
                                 'digest', 'changed_file', 'review', 'rights', 'other_failure', 'sibling'])
def test_draft_repair_keeps_all_post_identity_and_preflight_guards(privacy_failure, monkeypatch, risk):
    path, upload, _ = privacy_failure
    if risk == 'intent': upload.logs.append('POST_SUBMIT_INTENT: issued')
    if risk == 'started': upload.submission_started = True
    if risk == 'accepted': upload.submission_accepted = True
    if risk == 'url': upload.profile_url = 'https://www.tiktok.com/@target/video/123'
    if risk == 'public': upload.visibility = 'public'
    if risk == 'wrong_account': upload.target_handle = 'different'
    if risk == 'digest': upload.clip_sha256 = ''
    if risk == 'changed_file': path.write_bytes(b'changed')
    if risk == 'review': api.jobs[upload.source_job_id].clips[0].is_correct = False
    if risk == 'rights': monkeypatch.setattr(api, 'youtube_monetization_preflight_issue', lambda *_: 'held')
    if risk == 'other_failure': upload.error = 'CAPTCHA required'
    if risk == 'sibling': api.tiktok_uploads['other'] = upload.model_copy(update={'id':'other','submission_accepted':True})
    with pytest.raises(api.HTTPException): api.resume_tiktok_privacy_draft(upload.id)
    assert api.tiktok_uploads[upload.id].status == 'failed'


def test_draft_only_upload_never_acquires_file_input_or_discards_draft(monkeypatch, tmp_path, capsys):
    media = tmp_path/'source.mp4';media.write_bytes(b'original')
    page = NS(url=uploader.UPLOAD_URL, wait_for_timeout=lambda _:None,
              locator=lambda *_:pytest.fail('File input acquired'))
    monkeypatch.setattr(uploader,'tiktok_content_snapshot',lambda *_:(0,set()))
    monkeypatch.setattr(uploader,'exact_existing_tiktok_post',lambda *_:None)
    monkeypatch.setattr(uploader,'goto',lambda *_:None)
    monkeypatch.setattr(uploader,'recover_interrupted_upload_draft',lambda *_:True)
    monkeypatch.setattr(uploader,'discard_cron_upload_draft',lambda *_:pytest.fail('Draft discarded'))
    monkeypatch.setattr(uploader,'upload_editor_has_requested_file',lambda *_:True)
    monkeypatch.setattr(uploader,'dismiss_upload_overlays',lambda *_:None)
    monkeypatch.setattr(uploader,'set_caption',lambda *_:None)
    monkeypatch.setattr(uploader,'configure_requested_privacy',lambda *_:None)
    uploader.upload_video(page,media,'Caption',True,'target',cron_fresh_upload=True,resume_existing_draft_only=True)
    assert 'DRAFT_RESUME_ONLY:' in capsys.readouterr().out
    assert media.read_bytes() == b'original'


def test_draft_only_missing_identity_stops_before_transfer(monkeypatch, tmp_path):
    media = tmp_path/'source.mp4';media.write_bytes(b'original')
    page=NS(url=uploader.UPLOAD_URL,wait_for_timeout=lambda _:None,
            locator=lambda *_:pytest.fail('New file transfer'))
    monkeypatch.setattr(uploader,'tiktok_content_snapshot',lambda *_:(0,set()))
    monkeypatch.setattr(uploader,'exact_existing_tiktok_post',lambda *_:None)
    monkeypatch.setattr(uploader,'goto',lambda *_:None)
    monkeypatch.setattr(uploader,'recover_interrupted_upload_draft',lambda *_:False)
    monkeypatch.setattr(uploader,'upload_editor_has_requested_file',lambda *_:False)
    with pytest.raises(uploader.UploadError,match='tanpa transfer atau Post'):
        uploader.upload_video(page,media,'Caption',False,'target',resume_existing_draft_only=True)


@pytest.mark.parametrize('prompt,should_continue', [
    ('A video you were editing wasn’t saved. Continue editing?',True),
    ("A video you were editing wasn't saved. Continue editing?",True),
    ('Continue posting publicly?',False),
    ('A different draft. Continue?',False),
])
def test_plain_continue_requires_exact_interrupted_upload_prompt(monkeypatch, tmp_path, prompt, should_continue):
    clicked=[]
    button=NS(click=lambda **_:clicked.append(True))
    page=NS(locator=lambda _:NS(inner_text=lambda **_:prompt),wait_for_timeout=lambda _:None)
    def visible(_page, selectors, **_):
        return button if selectors == ['button:is(:text-is("Continue"), :has(:text-is("Continue")))'] else None
    monkeypatch.setattr(uploader,'first_visible',visible)
    monkeypatch.setattr(uploader,'upload_editor_has_requested_file',lambda *_:True)
    assert uploader.recover_interrupted_upload_draft(page,tmp_path/'clip.mp4') == should_continue
    assert bool(clicked) == should_continue


def test_resume_mode_is_in_command_and_survives_restart(privacy_failure, monkeypatch):
    _, upload, _ = privacy_failure
    upload.resume_existing_draft_only=True
    restored=api.TikTokUploadJob.model_validate_json(upload.model_dump_json())
    monkeypatch.setattr(api,'tiktok_source_is_cron',lambda _:True)
    monkeypatch.setattr(api,'tiktok_cdp_ready',lambda:True)
    command=api.build_tiktok_upload_command(restored)
    assert '--resume-existing-draft-only' in command and '--cron-fresh-upload' in command


def test_failed_draft_repair_never_reserves_another_automatic_attempt(privacy_failure):
    _, upload, _ = privacy_failure
    repaired=api.resume_tiktok_privacy_draft(upload.id)
    repaired.status='failed';repaired.error=upload.error;repaired.auto_retry_count=1
    api.schedule_tiktok_upload_retry(upload.id)
    assert repaired.auto_retry_at is None
    assert api.queue_retryable_tiktok_uploads_once() == 0


def test_explicit_banner_selector_repair_is_bounded_and_never_resets_count(privacy_failure):
    _, upload, _ = privacy_failure
    repaired=api.resume_tiktok_privacy_draft(upload.id)
    repaired.status='failed'
    repaired.error='Draf file yang sama tidak tersedia; pemulihan ditahan tanpa transfer atau Post baru.'
    assert api.resume_tiktok_privacy_draft(upload.id).status == 'failed'
    corrected=api.resume_tiktok_privacy_draft(upload.id,repair_banner=True)
    assert corrected.status == 'queued' and corrected.auto_retry_count == 3
    assert corrected.logs.count('DRAFT_BANNER_SELECTOR_REPAIR_RESERVED') == 1
    corrected.status='failed';corrected.error=repaired.error
    assert api.resume_tiktok_privacy_draft(upload.id,repair_banner=True).status == 'failed'


@pytest.mark.parametrize('risk',['intent','accepted','other_failure','hash'])
def test_banner_selector_repair_keeps_post_and_media_guards(privacy_failure,risk):
    path,upload,_=privacy_failure
    repaired=api.resume_tiktok_privacy_draft(upload.id)
    repaired.status='failed';repaired.error='Draf file yang sama tidak tersedia; pemulihan ditahan tanpa transfer atau Post baru.'
    if risk=='intent':repaired.logs.append('POST_SUBMIT_INTENT: issued')
    if risk=='accepted':repaired.submission_accepted=True
    if risk=='other_failure':repaired.error='Other failure'
    if risk=='hash':path.write_bytes(b'changed')
    if risk=='hash':
        with pytest.raises(api.HTTPException):api.resume_tiktok_privacy_draft(upload.id,repair_banner=True)
    else:assert api.resume_tiktok_privacy_draft(upload.id,repair_banner=True).status=='failed'
