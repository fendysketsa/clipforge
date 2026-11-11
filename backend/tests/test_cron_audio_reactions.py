from types import SimpleNamespace as NS
import hashlib
import json
import shutil
import subprocess
import wave

import numpy as np
import pytest
import cron_director_effects as fx


def candidate(text="Kita sedang berjalan. Awas! Kita kembali lagi."):
    return NS(start=0., end=8., text=text, score=90)


def write_audio(path, kind="voice_rise"):
    rate=16000
    t=np.arange(rate*8)/rate
    amplitude=np.full(len(t),.045)
    peak=(t>=3)&(t<3.48)
    amplitude[peak]=.48
    if kind=="noise":
        samples=np.random.default_rng(3).normal(0,1,len(t))*amplitude
    elif kind=="impulse":
        samples=np.sin(2*np.pi*190*t)*.04
        samples[rate*3:rate*3+80]=.8
    elif kind=="silence":
        samples=np.zeros(len(t))
    else:
        if kind=="constant":amplitude[:]=.42
        samples=amplitude*(np.sin(2*np.pi*190*t)+.35*np.sin(2*np.pi*380*t))
    with wave.open(str(path),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate)
        f.writeframes((np.clip(samples,-1,1)*32767).astype('<i2').tobytes())
    return path


def segments(text="Awas!"):
    return [NS(start=2.8,end=3.8,text=text)]


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='FFmpeg required')
def test_source_voiced_rise_is_measured_and_prioritized_without_editing_audio(tmp_path):
    source=write_audio(tmp_path/'source.wav')
    before=(hashlib.sha256(source.read_bytes()).hexdigest(),source.stat().st_mtime_ns)
    c=candidate()
    analysis=fx.analyze_reactions(source,c,segments(),enabled=True)
    assert len(analysis['events'])==1
    event=analysis['events'][0]
    assert 2.9<=event['start']<=3.05 and 3<=event['peak']<=3.5
    assert event['rise_db']>15 and event['confidence']=='heuristic'
    plan=fx.build_plan(c,segments(),enabled=True,audio_reactions=analysis)
    cue=plan['cues'][0]
    assert cue['mood']=='shout' and cue['kind'] in fx.MOODS['shout']
    assert cue['timing_method']=='measured_source_audio_onset' and cue['start']==event['start']
    assert cue['sound']=='none' and not cue['statement']
    assert before==(hashlib.sha256(source.read_bytes()).hexdigest(),source.stat().st_mtime_ns)


@pytest.mark.parametrize('kind',['noise','impulse','silence','constant'])
def test_noise_impulse_silence_and_constant_loud_audio_do_not_claim_a_shout(tmp_path,kind):
    source=write_audio(tmp_path/'source.wav',kind)
    assert not fx.analyze_reactions(source,candidate(),segments(),enabled=True)['events']


def test_no_timed_dialogue_or_only_non_reaction_wording_abstains(tmp_path):
    source=write_audio(tmp_path/'source.wav')
    c=candidate('Kita sedang berjalan. Kita kembali lagi.')
    assert not fx.analyze_reactions(source,c,[],enabled=True)['events']
    assert not fx.analyze_reactions(source,c,segments('Kita kembali lagi.'),enabled=True)['events']
    assert not fx.analyze_reactions(source,c,segments('Awas!'),enabled=True)['events']


@pytest.mark.parametrize('enabled,text,sensitive',[(False,'Awas!',False),(True,'Keluarga sedang berduka.',False),(True,'Awas!',True)])
def test_manual_and_sensitive_sources_never_decode_audio(monkeypatch,enabled,text,sensitive):
    monkeypatch.setattr(fx.subprocess,'run',lambda *a,**k:pytest.fail('Must not decode'))
    assert not fx.analyze_reactions('missing',candidate(text),segments(),enabled=enabled,sensitive=sensitive)['events']


def test_missing_audio_is_optional_and_does_not_remove_other_required_accents(tmp_path):
    c=candidate()
    analysis=fx.analyze_reactions(tmp_path/'missing.mp4',c,segments(),enabled=True)
    assert not analysis['events'] and analysis['reason']=='audio_analysis_unavailable'
    assert fx.build_plan(c,segments(),enabled=True,audio_reactions=analysis)['required']


def test_measured_reactions_stay_inside_existing_budget_and_spacing():
    c=NS(start=100.,end=136.,text='Awas! Wow! Kita akhirnya kembali.',score=90)
    analysis=dict(enabled=True,events=[dict(start=4.,peak=4.2,quote='Awas!'),dict(start=12.,peak=12.2,quote='Wow!')])
    rows=[NS(start=104,end=105,text='Awas!'),NS(start=112,end=113,text='Wow!'),NS(start=125,end=128,text='Kita akhirnya kembali.')]
    plan=fx.build_plan(c,rows,enabled=True,audio_reactions=analysis)
    assert len(plan['cues'])==2 and all(c['mood']=='shout' for c in plan['cues'])
    assert all(c['end']-c['start']<=.63 for c in plan['cues'])
    assert len(fx.build_plan(c,rows,enabled=True,budget=1,audio_reactions=analysis)['cues'])==1
    assert not fx.build_plan(c,rows,audio_reactions=analysis)['cues']
    c.text+=' Keluarga berduka.'
    assert all(cue['mood']=='calm' for cue in fx.build_plan(c,rows,enabled=True,audio_reactions=analysis)['cues'])


def test_model_cannot_invent_a_shout_from_transcript_without_audio_evidence():
    c=candidate()
    hints={'accent_beats':[dict(quote='Awas!',mood='shout')]}
    plan=fx.build_plan(c,segments(),hints,enabled=True)
    assert all(cue['mood']!='shout' for cue in plan['cues'])


@pytest.mark.parametrize('kind',fx.MOODS['shout'])
def test_reaction_marks_are_open_center_and_fade_once(kind):
    first=fx.effect_frame(kind,200,0,(255,255,255))
    middle=fx.effect_frame(kind,200,.4,(255,255,255))
    last=fx.effect_frame(kind,200,1,(255,255,255))
    assert first.getchannel('A').getbbox() is None
    assert last.getchannel('A').getbbox() is None
    assert middle.getchannel('A').getbbox() is not None
    assert middle.getpixel((100,100))[3]==0


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='FFmpeg required')
def test_real_encoding_reaction_preserves_clock_and_audio_packets(tmp_path):
    source=tmp_path/'render.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=0x334455:s=360x640:r=30:d=8',
        '-i',str(write_audio(tmp_path/'voice.wav')),'-c:v','libx264','-preset','ultrafast','-threads','1','-c:a','aac',str(source)],check=True)
    def audio_hash():
        return subprocess.check_output(['ffmpeg','-v','error','-i',str(source),'-map','0:a','-c:a','copy','-f','md5','-'])
    before=fx._probe(source);audio_before=audio_hash()
    c=candidate();analysis=fx.analyze_reactions(source,c,segments(),enabled=True)
    plan=fx.build_plan(c,segments(),enabled=True,audio_reactions=analysis)
    assert plan['cues'][0]['mood']=='shout'
    fx.render_effects(source,plan,preset='ultrafast',threads=1)
    after=fx._probe(source)
    assert before==after and audio_before==audio_hash()
    assert plan['rendered'] and plan['renderer']=='procedural_rgba_accents'
    assert plan['cues'][0]['kind'] in fx.MOODS['shout']
    assert all(not fx._overlaps(cue['box'],g) for cue in plan['cues'] for g in cue['protected_regions'])


def singing_audio(path):
    rate=16000;t=np.arange(rate*8)/rate
    frequency=np.full(len(t),180.)
    for start,end,hz in [(2,2.7,220),(2.7,3.4,294),(3.4,4.1,247),(4.1,4.8,330)]:
        frequency[(t>=start)&(t<end)]=hz
    phase=np.cumsum(frequency)*2*np.pi/rate
    samples=.12*(np.sin(phase)+.35*np.sin(phase*2))
    with wave.open(str(path),'wb') as file:
        file.setnchannels(1);file.setsampwidth(2);file.setframerate(rate)
        file.writeframes((samples*32767).astype('<i2').tobytes())
    return path


def test_sustained_melodic_vocal_evidence_gets_silent_music_notes(tmp_path):
    text='[menyanyi] Lalala lalala lalala.'
    c=candidate(text)
    rows=[NS(start=2,end=4.8,text=text)]
    source=singing_audio(tmp_path/'melody.wav')
    before=source.read_bytes()
    analysis=fx.analyze_reactions(source,c,rows,enabled=True)
    assert len(analysis['events'])==1 and analysis['events'][0]['mood']=='singing'
    assert analysis['events'][0]['stable_note_count']>=3
    plan=fx.build_plan(c,rows,enabled=True,audio_reactions=analysis)
    cue=plan['cues'][0]
    assert cue['kind'] in fx.MOODS['singing'] and cue['end']-cue['start']==pytest.approx(1.5)
    assert cue['sound']=='none' and not cue['statement'] and source.read_bytes()==before
    # Mere mention of singing over a constant voice does not prove singing.
    flat=write_audio(tmp_path/'speech.wav','constant')
    assert not fx.analyze_reactions(flat,candidate('Dia sedang menyanyi di rumah.'),
        [NS(start=2,end=4.8,text='Dia sedang menyanyi di rumah.')],enabled=True)['events']
    # Instrumental audio without timed source vocal text cannot get notes.
    assert not fx.analyze_reactions(source,c,[],enabled=True)['events']


@pytest.mark.parametrize('kind',fx.MOODS['singing'])
def test_music_note_art_has_colored_middle_and_transparent_ends(kind):
    first=fx.effect_frame(kind,180,0,(255,255,255))
    middle=fx.effect_frame(kind,180,.5,(255,255,255))
    last=fx.effect_frame(kind,180,1,(255,255,255))
    assert first.getchannel('A').getbbox() is None and last.getchannel('A').getbbox() is None
    assert middle.getchannel('A').getbbox() is not None
    assert len({pixel[:3] for pixel in middle.getdata() if pixel[3]>200})>3


def test_singing_and_shouting_evidence_cannot_be_fabricated_by_director():
    c=candidate('[menyanyi] Lalala lalala lalala.')
    hints={'accent_beats':[dict(quote='Lalala lalala lalala',mood='singing')]}
    assert all(cue['mood']!='singing' for cue in fx.build_plan(c,[NS(start=2,end=5,text=c.text)],hints,enabled=True)['cues'])
