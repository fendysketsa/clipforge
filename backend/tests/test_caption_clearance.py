from pathlib import Path

import cv2
import numpy as np
import pytest

import caption_clearance as clearance
import clipper


def test_embedded_source_text_and_face_get_separate_added_caption_area():
    result=clearance.plan([[96,1360,1010,1620],[94,1368,998,1626]],[1058],font_size=53)
    assert result['enabled'] and result['caption_baseline']==1552
    assert result['caption_bounds'][0]>result['source_panel']['y']+result['source_panel']['height']+40
    assert result['caption_bounds'][0]>result['source_text_bounds'][1]
    assert not result['source_text_removed'] and not result['source_clock_changed']


def test_face_that_fills_source_picture_stays_inside_its_own_panel():
    result=clearance.plan([[96,1360,1010,1620]]*2,[1250],font_size=53)
    assert result['enabled'] and not result['requires_review'] and result['full_source_frame_visible']


def test_clear_source_stays_unchanged_and_single_observation_is_uncertain():
    assert not clearance.plan([])['enabled']
    assert not clearance.plan([])['requires_review']
    assert clearance.plan([[96,1360,1010,1620]])['requires_review']


def test_detector_finds_embedded_white_outline_glyphs_but_not_plain_background():
    frame=np.full((960,540,3),100,np.uint8)
    assert not clearance.text_rows(frame)
    cv2.putText(frame,'INI TEKS SUMBER',(90,750),cv2.FONT_HERSHEY_SIMPLEX,.8,(0,0,0),5,cv2.LINE_AA)
    cv2.putText(frame,'INI TEKS SUMBER',(90,750),cv2.FONT_HERSHEY_SIMPLEX,.8,(255,255,255),2,cv2.LINE_AA)
    assert clearance.text_rows(frame)


@pytest.mark.parametrize('facebook',[False,True])
def test_ass_keeps_reserved_baseline_in_standard_and_facebook_mode(tmp_path,monkeypatch,facebook):
    if facebook:monkeypatch.setenv('CLIPFORGE_FACEBOOK_NICHE','digital_simple')
    else:monkeypatch.delenv('CLIPFORGE_FACEBOOK_NICHE',raising=False)
    path=tmp_path/'caption.ass'
    clipper.write_dynamic_ass(path,[clipper.TranscriptSegment(0,3,'Tulisan tambahan berada di ruang yang terpisah.')],0,3,
                              clipper.CaptionStyle(font_size=8,baseline_y=1280))
    style=next(line for line in path.read_text().splitlines() if line.startswith('Style: Caption'))
    assert style.endswith(',640,1')


def test_source_caption_layout_keeps_editorial_card_above_face_and_caption_lane():
    vf=clipper.clean_detail_edit_filter(43,'hook.txt',cover_text_filename='cover.txt',
        editorial_text_filename='context.txt',preserve_source_geometry=True,
        portrait_presentation={'layout':'source_caption_clearance','hook_y':320})
    assert 'y=320' in vf and 'cover.txt' not in vf
    assert 'crop=1080:1920' not in vf


def test_qc_exposure_measures_picture_instead_of_intentional_caption_padding(monkeypatch):
    frame=np.zeros((1920,1080,3),np.uint8)
    frame[40:1320,180:900]=150
    class Capture:
        def isOpened(self):return True
        def set(self,*args):pass
        def read(self):return True,frame.copy()
        def release(self):pass
    monkeypatch.setattr(cv2,'VideoCapture',lambda *args:Capture())
    monkeypatch.setattr(clipper,'probe_media_duration_seconds',lambda _:3.)
    monkeypatch.setattr(clipper,'make_cv2_cascade',lambda *args:None)
    common=dict(output_format='vertical_short',subtitles_rendered=True,caption_position='bottom')
    full=clipper.analyze_render_quality(Path('fixture.mp4'),**common)
    picture=clipper.analyze_render_quality(Path('fixture.mp4'),content_region={'x':180,'y':40,'width':720,'height':1280},**common)
    assert not full['exposure']['passed'] and picture['exposure']['passed']
    assert picture['exposure']['median_luminance']==150
