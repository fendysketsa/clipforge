from types import SimpleNamespace as NS

import pytest

import api
import tiktok_uploader as uploader
from test_tiktok_caption_recovery import failed_caption


OPENING='Kalau di tempat kerja: Menurutmu, siapa yang perlu memulai komunikasi lebih dulu dalam situasi ini?'
CAPTION=OPENING+'\n\nSimak konteks. Sumber: BANGJBLOX https://www.youtube.com/watch?v=B3anNkNUqrg'
OTHER=OPENING+' Simak konteks. Sumber: Nadia Omara https://www.youtube.com/watch?v=Jr2AVxsP3Vk'
ERROR='Caption serupa sudah ada di TikTok, tetapi ID, caption lengkap, dan privasi belum cocok; transfer ulang ditahan.'


def page_with_captions(captions,owner='owner'):
    links=[NS(inner_text=lambda text=text,**_:text,
        get_attribute=lambda *_,**k:f'/@{owner}/video/7706894101328809217') for text in captions]
    return NS(locator=lambda _:NS(all=lambda:links))


def test_observed_template_collision_is_another_explicit_source():
    assert uploader.caption_prefix_matches_are_other_sources(page_with_captions([OTHER]),CAPTION,'owner',1)


@pytest.mark.parametrize('case',['same_source','same_caption','no_credit','truncated','wrong_owner','missing_row','extra_row','one_ambiguous','no_target_credit'])
def test_source_collision_exception_never_weakens_uncertain_duplicate_guard(case):
    rows=[OTHER];caption=CAPTION;owner='owner';count=1
    if case=='same_source':rows=[OTHER.replace('Jr2AVxsP3Vk','B3anNkNUqrg')]
    if case=='same_caption':rows=[CAPTION]
    if case=='no_credit':rows=[OPENING+' https://www.youtube.com/watch?v=Jr2AVxsP3Vk']
    if case=='truncated':rows=[OPENING+' Sumber: Nadia Omara']
    if case=='wrong_owner':owner='different'
    if case=='missing_row':rows=[]
    if case=='extra_row':rows=[OTHER,OTHER]
    if case=='one_ambiguous':rows=[OTHER,CAPTION];count=2
    if case=='no_target_credit':caption=OPENING
    assert not uploader.caption_prefix_matches_are_other_sources(page_with_captions(rows,owner),caption,'owner',count)


def test_initial_posts_zero_is_not_an_authoritative_empty_account(monkeypatch):
    clock=iter([0,1,2]);monkeypatch.setattr(uploader.time,'monotonic',lambda:next(clock))
    ids=iter([set(),{'7706894101328809217'}]);monkeypatch.setattr(uploader,'visible_tiktok_post_ids',lambda _:next(ids))
    bodies=iter(['Posts 0','Posts 1 '+OTHER]);waits=[]
    page=NS(goto=lambda *a,**k:None,locator=lambda _:NS(inner_text=lambda **_:next(bodies)),wait_for_timeout=lambda ms:waits.append(ms))
    count,baseline=uploader.tiktok_content_snapshot(page,CAPTION)
    assert baseline=={'7706894101328809217'} and count==1 and waits==[500]


def test_source_collision_draft_repair_is_explicit_and_bounded(failed_caption):
    _,upload,_=failed_caption
    api.jobs[upload.source_job_id].clips[0].is_correct=True
    upload.resume_existing_draft_only=True;upload.auto_retry_count=3;upload.error=ERROR
    upload.logs+=['PRIVACY_REQUESTED:Only you']
    assert api.resume_tiktok_privacy_draft(upload.id).status=='failed'
    repaired=api.resume_tiktok_privacy_draft(upload.id,repair_caption_collision=True)
    assert repaired.status=='queued' and repaired.auto_retry_count==3
    assert repaired.logs.count('DRAFT_CAPTION_SOURCE_REPAIR_RESERVED')==1
    repaired.status='failed';repaired.error=ERROR
    assert api.resume_tiktok_privacy_draft(upload.id,repair_caption_collision=True).status=='failed'


@pytest.mark.parametrize('risk',['started','accepted','intent','changed_file','other_failure'])
def test_source_collision_repair_keeps_checkpoint_and_media_guards(failed_caption,risk):
    path,upload,_=failed_caption
    api.jobs[upload.source_job_id].clips[0].is_correct=True
    upload.resume_existing_draft_only=True;upload.auto_retry_count=3;upload.error=ERROR
    upload.logs+=['PRIVACY_REQUESTED:Only you']
    if risk=='started':upload.submission_started=True
    if risk=='accepted':upload.submission_accepted=True
    if risk=='intent':upload.logs+=['POST_SUBMIT_INTENT: issued']
    if risk=='changed_file':path.write_bytes(b'changed')
    if risk=='other_failure':upload.error='Unknown failure'
    if risk=='changed_file':
        with pytest.raises(api.HTTPException):api.resume_tiktok_privacy_draft(upload.id,repair_caption_collision=True)
    else:assert api.resume_tiktok_privacy_draft(upload.id,repair_caption_collision=True).status=='failed'
