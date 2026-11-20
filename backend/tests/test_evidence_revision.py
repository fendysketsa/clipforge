import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np

import pytest

import evidence_revision as revision


@pytest.fixture
def primary(tmp_path):
    source=dict(key='official-statement',video_id='UYd82JiEfkE',channel_id='verified-channel',
        author='Gibran Rakabuming',title='RUU Perampasan Aset: Instrumen Kuat Melawan Korupsi',
        source_url='https://www.youtube.com/watch?v=UYd82JiEfkE',
        publish_timestamp='2026-02-12T22:30:59-08:00',checked_at='2026-11-15T09:30:34+00:00')
    path=tmp_path/'primary.json';path.write_text(json.dumps([source]))
    return path,source


def test_publication_day_uses_indonesia_timezone_without_inventing_recording_date(primary):
    path,_=primary
    result=revision.checked_publication(path,revision.sha(path),'verified-channel')
    assert result['date_label']=='13 Februari 2026'
    assert result['published_at']=='2026-02-13T13:30:59+07:00'
    assert result['date_basis']=='video_publication' and result['recording_date'] is None
    assert not result['facts_verified'] and not result['reaction_verified']


@pytest.mark.parametrize('change',[
    {'channel_id':'different-channel'},{'video_id':'different-id'},
    {'source_url':'https://evil.invalid/watch?v=UYd82JiEfkE'},
    {'source_url':'https://secret@www.youtube.com/watch?v=UYd82JiEfkE'},
    {'publish_timestamp':'2026-02-13'},
    {'publish_timestamp':'2026-12-13T12:00:00+07:00'},
])
def test_changed_identity_or_unverified_time_cannot_become_dated_evidence(primary,change):
    path,source=primary;source.update(change);path.write_text(json.dumps([source]))
    with pytest.raises(ValueError):revision.checked_publication(path,revision.sha(path),'verified-channel')


def test_changed_proof_asset_requires_another_review(primary):
    path,_=primary;digest=revision.sha(path);path.write_text('[]')
    with pytest.raises(ValueError,match='changed'):revision.checked_publication(path,digest,'verified-channel')


def test_caption_and_attribution_text_cannot_inject_ffmpeg_filters(tmp_path,primary):
    path,_=primary;source=revision.checked_publication(path,revision.sha(path),'verified-channel')
    source['publisher']="A: 'text'; movie=secret"
    filters=revision.overlay(tmp_path,source,1,7)
    assert 'movie=secret' not in filters
    assert any('movie=secret' in p.read_text() for p in tmp_path.glob('context_*.txt'))
    assert 'Tanggal rekaman tidak disebutkan.' in (tmp_path/'context_4.txt').read_text()
    assert 'OPINI PEMBICARA' in (tmp_path/'context_5.txt').read_text()
    assert 'fade' not in filters and 'blink' not in filters


@pytest.mark.parametrize('start,end',[(5,4),(0,3),(-1,8)])
def test_short_or_invalid_evidence_holds_are_rejected(tmp_path,start,end):
    with pytest.raises(ValueError):revision.overlay(tmp_path,{},start,end)


def test_real_revision_keeps_clock_and_review_hold_with_authored_sound(tmp_path,primary):
    path,_=primary;source=revision.checked_publication(path,revision.sha(path),'verified-channel')
    media=tmp_path/'original.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=black:s=360x640:r=10:d=8',
        '-f','lavfi','-i','sine=frequency=350:duration=8','-c:v','libx264','-threads','1',
        '-c:a','aac','-shortest',str(media)],check=True,capture_output=True,timeout=20)
    target=revision.render(media,tmp_path/'revision',source,start=1,end=7)
    sidecar=json.loads(target.with_suffix('.json').read_text())
    assert sidecar['manual_publication_review'] and not sidecar['upload_allowed']
    assert sidecar['source_media_sha256']==revision.sha(media)
    assert not sidecar['source_clock_changed'] and not sidecar['sound']['third_party_audio']
    result=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(target)]))
    assert abs(float(result['format']['duration'])-8)<.2
    video=next(s for s in result['streams'] if s['codec_type']=='video')
    assert (video['width'],video['height'])==(1080,1920)
    assert video['avg_frame_rate']=='30/1'
    audio=next(s for s in result['streams'] if s['codec_type']=='audio')
    assert float(audio['duration'])>=7.95  # Lookahead must not truncate the last three seconds.
    tail=subprocess.check_output(['ffmpeg','-v','error','-ss','7.4','-i',str(target),'-t','0.4',
        '-vn','-ar','16000','-ac','1','-f','f32le','-'])
    samples=np.frombuffer(tail,dtype='<f4')
    assert len(samples)>=6000 and float(np.sqrt(np.mean(samples**2)))>.02
    assert not target.with_name('.gibran-context-review.rendering.mp4').exists()


def test_reserved_bar_rejects_source_content_instead_of_covering_a_face(tmp_path):
    media=tmp_path/'filled.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=white:s=360x640:r=2:d=6',
        '-c:v','libx264','-threads','1',str(media)],check=True,capture_output=True,timeout=15)
    with pytest.raises(ValueError,match='No empty'):revision.check_reserved_bars(media,1,6)
    with pytest.raises(ValueError,match='No empty'):revision.check_reserved_bars(media,1,6,replace_editorial_header=True)


def test_explicit_editorial_header_replacement_does_not_allow_covering_source_pictures(tmp_path):
    media=tmp_path/'heading.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',
        'color=black:s=360x640:r=2:d=6,drawbox=x=30:y=20:w=25:h=60:color=white:t=fill',
        '-c:v','libx264','-threads','1',str(media)],check=True,capture_output=True,timeout=15)
    with pytest.raises(ValueError,match='No empty top'):revision.check_reserved_bars(media,1,6)
    revision.check_reserved_bars(media,1,6,replace_editorial_header=True)
