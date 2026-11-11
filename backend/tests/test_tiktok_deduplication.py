import hashlib
from pathlib import Path

import pytest

import api
import tiktok_uploader as uploader


@pytest.fixture
def media(monkeypatch,tmp_path):
    path=tmp_path/'clip.mp4';path.write_bytes(b'the same encoded clip')
    clip=api.ClipFile(name=path.name,url='/outputs/job/clip.mp4',size_bytes=path.stat().st_size,
        title='Adegan yang didukung sumber.',is_correct=True)
    job=api.ClipJob(id='job',status='completed',request=api.ClipJobRequest(),
        clips=[clip],created_at=api.now_iso(),updated_at=api.now_iso())
    monkeypatch.setattr(api,'find_job_clip',lambda *a:(job,clip,1))
    monkeypatch.setattr(api,'output_path_from_url',lambda *a:path)
    monkeypatch.setattr(api,'youtube_monetization_preflight_issue',lambda *a:None)
    monkeypatch.setattr(api,'upload_media_duration_issue',lambda *a:None)
    monkeypatch.setattr(api,'tiktok_target_handle',lambda:'owner')
    row=api.TikTokUploadJob(id='old',source_job_id='job',clip_url=clip.url,clip_name=path.name,
        status='failed',created_at='2026-11-10T00:00:00+00:00',updated_at=api.now_iso(),
        caption='Caption lama.',target_handle='owner',clip_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    api.tiktok_uploads[row.id]=row
    return path,clip,row


@pytest.mark.parametrize('checkpoint',['intent','accepted','compacted','remote_url','pre_post'])
def test_manual_request_cannot_mint_another_id_for_identical_media(media,checkpoint):
    _,clip,old=media
    if checkpoint=='intent':old.logs=['POST_SUBMIT_INTENT: before activation']
    if checkpoint=='accepted':old.submission_accepted=True
    if checkpoint=='compacted':old.submission_started=True;old.logs=[]
    if checkpoint=='remote_url':old.profile_url='https://www.tiktok.com/@owner/video/7706778926332251393'
    old.auto_retry_count=3
    result=api.create_tiktok_upload_record('job',api.TikTokUploadRequest(clip_url=clip.url,
        caption='Caption baru tidak berarti video baru.',visibility='only_you'))
    assert result.id==old.id and result.auto_retry_count==3


def test_changed_job_and_filename_still_reuses_accepted_same_hash(media):
    _,_,old=media;old.submission_accepted=True
    old.source_job_id='another-job';old.clip_url='/outputs/other/renamed.mp4'
    assert api.reusable_tiktok_upload('job','/outputs/job/clip.mp4',old.clip_sha256).id==old.id


@pytest.mark.parametrize('kind',['dry_run','other_account'])
def test_test_transfer_or_other_account_does_not_reserve_target_account(media,kind):
    _,_,old=media;old.submission_accepted=True
    if kind=='dry_run':old.dry_run=True
    else:old.target_handle='another_owner'
    assert api.reusable_tiktok_upload('job',old.clip_url,old.clip_sha256) is None


@pytest.mark.parametrize('confirmed',[False,True])
def test_legacy_queued_duplicate_is_stopped_before_browser_or_transfer(media,monkeypatch,confirmed):
    _,_,old=media
    old.submission_accepted=not confirmed
    old.upload_confirmed=confirmed
    if confirmed:old.profile_url='https://www.tiktok.com/@owner/video/7706778926332251393'
    new=old.model_copy(update={'id':'legacy-queued','status':'queued','submission_accepted':False,
        'upload_confirmed':False,'profile_url':None,'created_at':'2026-11-11T00:00:00+00:00'})
    api.tiktok_uploads[new.id]=new
    monkeypatch.setattr(api.subprocess,'Popen',lambda *a,**k:pytest.fail('Duplicate may not start a browser'))
    api.run_tiktok_upload(new.id)
    result=api.tiktok_uploads[new.id]
    assert result.status==('completed' if confirmed else 'failed')
    assert result.upload_confirmed==confirmed and result.auto_retry_at is None
    assert any(line.startswith('TIKTOK_DUPLICATE_GUARD:old:') for line in result.logs)


def test_file_identity_uses_bytes_not_reused_basename(tmp_path):
    first=tmp_path/'a'/'clip_01.mp4';second=tmp_path/'b'/'clip_01.mp4'
    first.parent.mkdir();second.parent.mkdir();first.write_bytes(b'first clip');second.write_bytes(b'other clip')
    original=first.stat()
    assert uploader.upload_source_identity(first)!=uploader.upload_source_identity(second)
    second.write_bytes(first.read_bytes())
    assert uploader.upload_source_identity(first)==uploader.upload_source_identity(second)
    assert (first.stat().st_mtime_ns,first.read_bytes())==(original.st_mtime_ns,b'first clip')


def test_ready_editor_for_another_file_is_never_draft_identity(monkeypatch):
    from types import SimpleNamespace as NS
    body=NS(inner_text=lambda **k:'another-clip.mp4\nCaption\nPost')
    page=NS(locator=lambda selector:body)
    monkeypatch.setattr(uploader,'first_visible',lambda page,selectors,**k:
        None if selectors[0].startswith('text=') else object())
    assert not uploader.upload_editor_has_requested_file(page,Path('requested-clip.mp4'))
