"""No filename titles or missing descriptions on initial or recovered uploads."""
from types import SimpleNamespace
import pytest

import api
import youtube_uploader as uploader


@pytest.mark.parametrize('title', ['clip 01 judul video lucu', 'clip_01_judul-video.mp4', 'Klip-2: cerita', ''])
def test_internal_title_cannot_enter_publication(title):
    with pytest.raises(uploader.UploadError, match='judul'):
        uploader.require_reviewed_upload_metadata(title, 'A source grounded description')


def test_missing_description_cannot_enter_publication():
    with pytest.raises(uploader.UploadError, match='deskripsi'):
        uploader.require_reviewed_upload_metadata('Mau Main Drum Malah Mencari Sumber Bunyinya', '  ')


def test_invalid_recovery_metadata_stops_before_navigating_or_mutating_a_draft():
    with pytest.raises(uploader.UploadError, match='deskripsi'):
        uploader.resume_saved_draft_and_finalize(object(), 'Reviewed title', 'public',
            video_url='https://youtu.be/abcDEF12345')


@pytest.mark.parametrize('reset_title', [True, False])
def test_recovery_fills_both_fields_and_detects_rerender_reset(monkeypatch, reset_title):
    fields = {'title':'clip 01 default', 'description':''}
    edits = []
    def contains(page, value, patterns, *, field_kind, **kwargs):
        return fields[field_kind] == value
    def fill(page, value, label, patterns, **kwargs):
        kind = 'description' if label == 'deskripsi' else 'title'
        fields[kind] = value; edits.append(kind)
        if kind == 'description' and reset_title: fields['title'] = 'clip 01 default'
    monkeypatch.setattr(uploader, 'upload_text_field_contains', contains)
    monkeypatch.setattr(uploader, 'set_upload_text_field', fill)
    if reset_title:
        with pytest.raises(uploader.UploadError, match='judul belum terverifikasi'):
            uploader.ensure_upload_metadata_fields(object(), 'Reviewed title', 'Reviewed description')
    else:
        uploader.ensure_upload_metadata_fields(object(), 'Reviewed title', 'Reviewed description')
        assert fields == {'title':'Reviewed title', 'description':'Reviewed description'}
    assert edits == ['title','description']


@pytest.mark.parametrize('actual_title,actual_description,wrong_id', [
    ('Reviewed title','Reviewed description',False),
    ('clip 01 reviewed title','Reviewed description',False),
    ('Reviewed title','',False),
    ('Reviewed title','Wrong text',False),
    ('Reviewed title','Reviewed description',True),
])
def test_only_persisted_metadata_on_exact_id_can_be_confirmed(monkeypatch, actual_title, actual_description, wrong_id):
    class Page:
        url = ''
        def goto(self, url, **kwargs): self.url = url.replace('abcDEF12345','wrongID1234') if wrong_id else url
        def locator(self, selector):
            return SimpleNamespace(first=SimpleNamespace(wait_for=lambda **kwargs:None,
                inner_text=lambda: actual_title if 'title-textarea' in selector else actual_description))
    monkeypatch.setattr(uploader, 'ensure_logged_in', lambda page: None)
    if actual_title == 'Reviewed title' and actual_description == 'Reviewed description' and not wrong_id:
        uploader.verify_saved_video_metadata(Page(), 'https://youtu.be/abcDEF12345', 'Reviewed title', 'Reviewed description')
    else:
        with pytest.raises(uploader.UploadError):
            uploader.verify_saved_video_metadata(Page(), 'https://youtu.be/abcDEF12345', 'Reviewed title', 'Reviewed description')


def test_restart_command_carries_both_reviewed_fields_without_local_file():
    row = api.YouTubeUploadJob(id='metadata-check', source_job_id='removed',
        clip_url='/outputs/removed/clip_01.mp4',clip_name='clip_01.mp4',status='failed',
        created_at=api.now_iso(),updated_at=api.now_iso(),title='Reviewed title',
        description='Reviewed source-grounded description',video_url='https://youtu.be/abcDEF12345')
    command = api.build_youtube_restart_verification_command(row)
    parsed = uploader.build_parser().parse_args(command[2:])
    assert parsed.command == 'verify-upload'
    assert parsed.description == row.description and parsed.title == row.title
    assert row.clip_url not in command
