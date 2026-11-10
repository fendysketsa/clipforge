import json
import subprocess
from types import SimpleNamespace

import numpy as np
import pytest

import cron_short_director as director
from portrait_framing import landscape_portrait_plan


def clip(text='Sumpah kakak pahli. Kak Yuta bisa borong motor GP.'):
    return SimpleNamespace(start=10.,end=42.,title='Sumpah kakak pahli.',hook='Sumpah kakak pahli.',text=text)


def test_hook_uses_complete_actual_phrase_and_keeps_modality():
    rows=[SimpleNamespace(start=10,end=12,text='Sumpah kakak pahli.'),
          SimpleNamespace(start=26,end=29,text='Kak Yuta bisa borong motor GP.')]
    result=director.grounded_opening(clip(),rows,enabled=True)
    assert result['text']=='Kak Yuta bisa borong motor GP.'
    assert result['source_start']==26 and result['source_end']==29
    assert result['audio_reordered'] is False
    assert ' '.join(result['display_text'].split())==result['text'].upper().rstrip(' ,.!;:')


@pytest.mark.parametrize('text',[
    'Kak Yuta tidak bisa borong motor GP.',
    'Kalau harga naik, jangan beli motor.',
])
def test_hook_preserves_negation_and_conditional_context(text):
    c=clip(text)
    result=director.grounded_opening(c,[SimpleNamespace(start=12,end=18,text=text)],enabled=True)
    assert result['enabled'] and result['text']==text


@pytest.mark.parametrize('case',['foreign_text','partial_word','outside_time','numeric','sensitive','manual','unfinished'])
def test_hook_does_not_promote_unsupported_or_unsafe_copy(case):
    text='Kak Yuta bisa borong motor GP.'
    row=SimpleNamespace(start=12,end=18,text=text)
    c=clip()
    if case=='foreign_text':c.text='Ucapan lain yang tidak berhubungan.'
    if case=='partial_word':c.text='Kak Yuta bisa borong motor GPO.'
    if case=='outside_time':row.start=43;row.end=48
    if case=='numeric':row.text=c.text='Uang Rp1.78 juta untuk beli motor.'
    if case=='unfinished':row.text=c.text='Uang untuk beli motor dengan'
    result=director.grounded_opening(c,[row],enabled=case!='manual',sensitive=case=='sensitive')
    assert not result['enabled']


def test_caption_docking_changes_geometry_without_retiming_speech(tmp_path):
    from clipper import CaptionStyle, TranscriptSegment, write_dynamic_ass
    rows=[TranscriptSegment(10.5,12,'Kak Yuta bisa beli motor.'),
          TranscriptSegment(13,15,'Akhirnya motor pilihan berhasil dibeli.')]
    ordinary=tmp_path/'ordinary.ass';docked=tmp_path/'docked.ass'
    write_dynamic_ass(ordinary,rows,10,10,CaptionStyle())
    write_dynamic_ass(docked,rows,10,10,CaptionStyle(baseline_y=1336))
    events=lambda path:[line for line in path.read_text().splitlines() if line.startswith('Dialogue:')]
    assert events(ordinary)==events(docked)
    assert ',110,230,584,1' in docked.read_text()


def test_follow_invitation_uses_known_series_and_keeps_sensitive_restraint():
    from cron_director_effects import follow_copy
    c=clip('Kak Yuta bisa borong motor GP.')
    assert 'GAMEPLAY' in follow_copy(c,topic_hint='gaming')['support']
    c.text='Korban kecelakaan sedang dibantu petugas.'
    assert follow_copy(c,topic_hint='gaming')['support']=='TERIMA KASIH SUDAH MENYIMAK'


def plan(**changes):
    settings=dict(enabled=True,genre='gaming',focus={'available':True,'center':[.72,.5]})
    settings.update(changes)
    return director.presentation_plan(landscape_portrait_plan((1280,720)),**settings)


def test_gameplay_context_stays_whole_and_detail_uses_same_clock():
    p=plan()
    assert p['layout']=='source_context_detail'
    assert p['full_source_frame_visible'] and p['all_panels_synchronized']
    assert not p['uses_other_timeline_clips'] and p['audio_unchanged']
    w,h,x,y=p['detail_crop']
    assert 0<=x<=1280-w and 0<=y<=720-h
    assert p['detail_y']>=p['panel_y']+p['panel_height']
    assert p['detail_y']+p['detail_height']<p['caption_baseline']<=1552
    assert p['detail_x']+p['detail_width']<=900
    assert not any(token in director.source_filter(p) for token in ('movie=','setpts=','trim=','concat='))


@pytest.mark.parametrize('center',[None,[],[float('nan'),.5],[2,.5],['x',.5]])
def test_uncertain_focus_uses_complete_context_instead_of_a_guessed_crop(center):
    p=plan(focus={'available':True,'center':center})
    assert p['layout']=='source_context_stage' and 'detail_crop' not in p


def test_manual_conversation_evidence_and_sensitive_sources_keep_appropriate_layout():
    base=landscape_portrait_plan((1280,720))
    assert director.presentation_plan(base,enabled=False,genre='gaming') is base
    split=dict(base,layout='synchronized_conversation_split')
    assert director.presentation_plan(split,enabled=True,genre='gaming') is split
    assert plan(sensitive=True)['layout']=='source_context_stage'
    assert plan(genre='conversation')['layout']=='source_context_stage'


def test_clear_gameplay_can_use_neutral_detail_without_claiming_object_tracking():
    focus={'available':False,'readable_detail':True,'sample_count':5,'reason':'focus_not_stable'}
    p=plan(focus=focus)
    assert p['layout']=='source_context_detail'
    assert p['focus_selection']=='neutral_center_without_object_tracking'
    assert p['focus_analysis']['available'] is False
    assert p['full_source_frame_visible'] and p['all_panels_synchronized']
    assert plan(focus=dict(focus,readable_detail=False))['layout']=='source_context_stage'


@pytest.mark.parametrize('detail',[False,True])
def test_encoded_context_and_detail_remain_synchronized(detail):
    source=('color=red:s=1280x720:r=4:d=1,'
        'drawbox=x=640:y=0:w=640:h=720:color=blue:t=fill,'
        "drawbox=x=0:y=0:w=640:h=720:color=lime:t=fill:enable='gte(t,0.5)',"
        "drawbox=x=640:y=0:w=640:h=720:color=yellow:t=fill:enable='gte(t,0.5)'")
    p=plan(focus={'available':detail,'center':[.72,.5]})
    rendered=subprocess.run(['ffmpeg','-v','error','-filter_threads','1','-f','lavfi','-i',source,
        '-vf',director.source_filter(p),'-pix_fmt','rgb24','-f','rawvideo','-'],
        capture_output=True,check=True,timeout=25)
    frames=np.frombuffer(rendered.stdout,dtype=np.uint8).reshape(-1,1920,1080,3)
    assert len(frames)==4
    cy=p['panel_y']+p['panel_height']//2
    assert frames[0,cy,50,0]>180 and frames[0,cy,1030,2]>180
    assert frames[-1,cy,50,1]>180 and frames[-1,cy,1030,0]>180
    if detail:
        dy=p['detail_y']+p['detail_height']//2
        assert frames[0,dy,480,2]>180 and frames[-1,dy,480,0]>180


def test_focus_is_measured_from_real_source_frames_and_file_is_unchanged(tmp_path):
    path=tmp_path/'source.mp4'
    subprocess.run(['ffmpeg','-v','error','-filter_complex_threads','1',
        '-f','lavfi','-i','color=0x101010:s=1280x720:r=10:d=1',
        '-f','lavfi','-i','testsrc2=s=320x240:r=10:d=1','-filter_complex','[0:v][1:v]overlay=880:240',
        '-c:v','libx264','-preset','ultrafast','-threads','1','-t','1',str(path)],
        check=True,capture_output=True,timeout=15)
    before=path.stat()
    result=director.measure_focus(path,0,1)
    assert result['available'] and result['sample_count']==5
    assert result['center'][0]==.72 and result['temporal_agreement']>=.6
    assert (path.stat().st_size,path.stat().st_mtime_ns)==(before.st_size,before.st_mtime_ns)


def test_cron_export_includes_measured_layout_readable_caption_and_no_unrelated_outro(monkeypatch,tmp_path):
    import clipper
    source=tmp_path/'roblox.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=s=1280x720:r=8:d=2',
        '-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=2',
        '-c:v','libx264','-preset','ultrafast','-threads','1','-c:a','aac','-t','2',str(source)],
        check=True,capture_output=True,timeout=15)
    for name in ['SHORTS_RENDER_QC_ENABLED','SHORTS_ADAPTIVE_COLOR_ENABLED','SHORTS_CINEMATIC_FINISH_ENABLED',
                 'SHORTS_CINEMATIC_SMOKE_ENABLED','SHORTS_EVIDENCE_RESEARCH_ENABLED','CTA_VOICEOVER_ENABLED',
                 'SHORTS_BACKGROUND_MUSIC_ENABLED','SHORTS_PROCEDURAL_MUSIC_ENABLED','SHORTS_SCHEDULED_SUBSCRIBE_PULSE_ENABLED']:
        monkeypatch.setenv(name,'false')
    monkeypatch.setenv('CLIPFORGE_CRON_DIRECTOR_EFFECTS','true')
    monkeypatch.setenv('QURAN_OUTRO_ENABLED','true')
    monkeypatch.setattr(clipper,'FENDY_CLIPPER_SHORTS_MIN_SECONDS',1)
    monkeypatch.setattr(clipper,'detect_active_speaker_split_profile',lambda *a:None)
    monkeypatch.setattr(director,'measure_focus',lambda *a:{'available':True,'center':[.72,.5]})
    c=clipper.ClipCandidate(1,0,2,2,85,'Sumpah kakak pahli.','test','Kak Yuta bisa borong motor GP.')
    rows=[clipper.TranscriptSegment(0,2,c.text)]
    before=source.stat()
    output=clipper.export_clip(source,c,rows,tmp_path/'clips',True,'person',generate_assets=False,enforce_size=False)
    data=json.loads(output.with_suffix('.json').read_text())
    assert data['layout']=='source_context_detail'
    assert data['cron_short_presentation']['opening']['text']==c.text
    assert data['dynamic_captions']['baseline_y']<=1552
    assert not data['quran_outro']['enabled'] and data['quran_outro']['disabled_reason']=='cron_topic_not_religious'
    assert not data['ryuundy_motion']['enabled']
    assert data['output_width']==1080 and data['output_height']==1920
    assert abs(data['output_duration_seconds']-2)<.2
    assert (source.stat().st_size,source.stat().st_mtime_ns)==(before.st_size,before.st_mtime_ns)
