from pathlib import Path
from types import SimpleNamespace as NS
import hashlib
import json
import shutil
import subprocess

import numpy as np
import pytest
import cron_director_effects as fx


def source(text='Kita mulai dari sini. Wow mantap sekali! Kita lanjutkan sampai selesai.',duration=20):
    return NS(start=100.,end=100.+duration,text=text,score=95)


def segments(c):return [NS(start=104,end=106,text='Wow mantap sekali!')]


def test_cron_payoff_insert_reuses_budget_after_source_phrase_and_keeps_clocks():
    c=source();rows=segments(c)
    accents=fx.build_plan(c,rows,enabled=True)
    before=len(accents['cues'])
    plan=fx.plan_rhythm_insert(c,rows,accents,enabled=True,seed='one')
    assert plan['enabled'] and plan['start']==pytest.approx(6.04)
    assert len(accents['cues'])==before<=2
    assert plan['full_source_frame_visible'] and plan['source_clock_unchanged'] and plan['captions_clock_unchanged']
    assert plan['inserted_timeline_seconds']==0 and not plan['source_frame_frozen']
    assert plan['quote']=='Wow mantap sekali!' and plan['beats'][0]>=6
    assert all(6<=t<plan['end'] for t in plan['beats'])
    assert any(cue['kind']=='rhythm_depth' for cue in accents['cues'])


@pytest.mark.parametrize('blocker',['manual','protected','sensitive','out_of_range','no_reaction','last_syllable','vocal_budget'])
def test_rhythm_insert_does_not_force_a_template_on_incompatible_content(blocker):
    c=source();rows=segments(c)
    if blocker=='sensitive':c.text+=' Keluarga berduka.'
    if blocker=='out_of_range':rows=[NS(start=121,end=123,text='Wow mantap sekali!')]
    if blocker=='last_syllable':rows=[NS(start=118,end=119.8,text='Wow mantap sekali!')]
    if blocker=='no_reaction':rows=[NS(start=104,end=106,text='Kita lanjutkan sampai selesai.')]
    accents=fx.build_plan(c,rows,enabled=blocker!='manual')
    if blocker=='vocal_budget':
        for cue in accents['cues']:cue['mood']='shout'
    before=json.dumps(accents)
    plan=fx.plan_rhythm_insert(c,rows,accents,enabled=blocker!='manual',protected=blocker=='protected')
    assert not plan['enabled'] and before==json.dumps(accents)


@pytest.mark.parametrize('style',['depth_bounce','stack_snap'])
def test_encoded_depth_card_keeps_corner_markers_and_caption_stable(tmp_path,style):
    if not shutil.which('ffmpeg'):pytest.skip('FFmpeg required')
    from PIL import Image,ImageDraw
    image=Image.new('RGB',(360,640),'#476364');d=ImageDraw.Draw(image)
    for x,y,color in [(0,0,'red'),(330,0,'lime'),(0,610,'blue'),(330,610,'yellow')]:d.rectangle((x,y,x+29,y+29),fill=color)
    base=tmp_path/'source.png';image.save(base)
    plan=dict(enabled=True,start=2.,end=3.42,beats=[2.,2.4,2.8],style=style)
    vf=("drawbox=x=130:y=300:w=100:h=70:color=red:t=fill:enable='lt(t,2.5)',"
        "drawbox=x=130:y=300:w=100:h=70:color=blue:t=fill:enable='gte(t,2.5)',"
        +fx.rhythm_source_filter(plan,360,640))
    # A caption surrogate is applied AFTER source motion, as in export_clip.
    vf+=',drawbox=x=70:y=530:w=220:h=24:color=magenta:t=fill'
    target=tmp_path/'depth.mp4'
    proc=subprocess.run(['ffmpeg','-v','error','-y','-loop','1','-i',str(base),'-t','5','-r','30',
        '-filter_complex_threads','1','-filter_complex',vf,'-c:v','libx264','-crf','14','-threads','1','-pix_fmt','yuv420p',str(target)],capture_output=True,text=True,timeout=60)
    assert proc.returncode==0,proc.stderr[-3000:]
    probe=fx._probe(target);assert probe['frames']==150 and probe['duration']==5
    def frame(at):
        out=subprocess.check_output(['ffmpeg','-v','error','-ss',str(at),'-i',str(target),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
        return np.frombuffer(out,np.uint8).reshape(640,360,3)
    for at in [1,2.13,2.53,2.93,4.1]:
        f=frame(at)
        assert np.mean(f[534:549,75:285,0])>220 and np.mean(f[534:549,75:285,2])>220
        # All four source corners remain represented inside the canvas.
        masks=[(f[:,:,0]>180)&(f[:,:,1]<80)&(f[:,:,2]<80),
               (f[:,:,1]>180)&(f[:,:,0]<80)&(f[:,:,2]<80),
               (f[:,:,2]>180)&(f[:,:,0]<80)&(f[:,:,1]<80),
               (f[:,:,0]>180)&(f[:,:,1]>180)&(f[:,:,2]<80)]
        assert all(mask.sum()>180 for mask in masks)
    impact=frame(2.13);plain=frame(1)
    assert np.max(np.abs(impact.astype(float)-plain))>40  # The card actually appeared.
    # The inset remains live across the color change, not a frozen replay.
    assert np.mean(impact[315:340,160:190,0])>180
    assert np.mean(frame(2.93)[315:340,160:190,2])>180


def test_missing_audio_never_invents_bass_levels(tmp_path):
    c=source();plan=dict(enabled=True,start=6.,end=7.42,beats=[6.,6.4,6.8])
    assert fx.rhythm_bass_levels(tmp_path/'missing.mp4',c,plan)==[]
    assert plan['bass_skip_reason']=='source_audio_measurement_unavailable'


def test_procedural_bass_mix_keeps_speech_clock_and_no_clipping(tmp_path):
    if not shutil.which('ffmpeg'):pytest.skip('FFmpeg required')
    import clipper
    target=tmp_path/'mix.wav'
    cues=[clipper.SoundEffectCue('beat_thump',at,.18,58,.4,'source reaction') for at in [2.,2.4,2.8]]
    graph=clipper.contextual_audio_mix_filter('anull',cues,duration=5)
    proc=subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=600:sample_rate=48000:duration=5',
        '-filter_complex',graph,'-map','[audio_out]','-c:a','pcm_f32le',str(target)],capture_output=True,text=True,timeout=30)
    assert proc.returncode==0,proc.stderr
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(target),'-ac','1','-f','f32le','-'])
    samples=np.frombuffer(raw,dtype='<f4')
    assert len(samples)==5*48000 and np.max(np.abs(samples))<=.841
    t=np.arange(len(samples))/48000
    source_wave=np.sin(2*np.pi*600*t)*.125
    assert np.corrcoef(samples[:48000],source_wave[:48000])[0,1]>.999
    # Added bass energy is localized; the spoken-frequency component keeps time.
    difference=samples-source_wave
    assert np.sqrt(np.mean(difference[96000:104640]**2))>np.sqrt(np.mean(difference[:48000]**2))*10


def test_late_insert_does_not_buffer_all_preceding_source_frames():
    import re
    if not shutil.which('ffmpeg') or not Path('/usr/bin/time').exists():pytest.skip('FFmpeg and time required')
    peaks=[]
    for start in [2.,60.]:
        plan=dict(enabled=True,start=start,end=start+1.42,beats=[start,start+.4,start+.8],style='stack_snap')
        proc=subprocess.run(['/usr/bin/time','-f','MAXRSS_KB=%M','ffmpeg','-v','error','-f','lavfi','-i',
            'testsrc2=s=160x284:r=30:d=65','-filter_complex_threads','1','-filter_complex',
            fx.rhythm_source_filter(plan,160,284),'-an','-f','null','-'],capture_output=True,text=True,timeout=25)
        assert proc.returncode==0,proc.stderr
        peaks.append(int(re.search(r'MAXRSS_KB=(\d+)',proc.stderr)[1]))
    assert peaks[1]<=peaks[0]+30000
