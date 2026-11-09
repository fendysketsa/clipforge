from pathlib import Path
from types import SimpleNamespace as NS
import importlib.util
import json
import os
import shutil
import subprocess
import pytest
import cron_director_effects as fx


def clip(text='Wah ternyata hasilnya sangat bagus. Perhatikan bagian ini lalu kita selesai.', duration=36, start=100):
    return NS(start=start,end=start+duration,text=text,score=90)


def rows(c):
    return [NS(start=c.start+5,end=c.start+8,text=c.text.split('.')[0]),
        NS(start=c.start+22,end=c.start+25,text='Perhatikan bagian ini lalu kita selesai.')]


def test_cron_is_explicit_and_manual_jobs_have_no_accents():
    c=clip()
    assert not fx.build_plan(c,rows(c))['enabled']
    p=fx.build_plan(c,rows(c),enabled=True)
    assert 1<=len(p['cues'])<=2 and p['required'] and not p['rendered']
    assert all(p[k] for k in ['source_clock_unchanged','captions_clock_unchanged','audio_unchanged'])
    assert p['inserted_timeline_seconds']==0


@pytest.mark.parametrize('text,mood', [('Wah astaga itu jatuh!','surprise'),('Enak dan gurih sekali makanan ini.','delight'),
    ('Lari cepat jangan sampai kena!','surprise'),('Kenapa hasilnya bisa seperti ini?','question'),('Ternyata pintunya sudah terbuka.','realization')])
def test_real_utterance_selects_content_specific_mood(text,mood):
    c=clip(text)
    p=fx.build_plan(c,[NS(start=105,end=108,text=text)],enabled=True)
    assert p['cues'][0]['mood']==mood
    assert p['cues'][0]['quote']==text and 105<c.start+p['cues'][0]['start']<108


def test_no_semantic_hit_still_gets_one_measured_source_sentence_accent():
    c=clip('Kita sedang berada di halaman rumah dengan suasana tenang.')
    assert len(fx.build_plan(c,rows(c),enabled=True)['cues'])>=1
    p=fx.build_plan(c,[],enabled=True)
    assert len(p['cues'])==1 and p['cues'][0]['directed_by']=='quiet_fallback_no_timed_dialogue'


def test_ai_quote_must_exist_in_the_timed_source_and_cannot_supply_code():
    c=clip('Lihat pintu ini rupanya sudah terbuka.')
    r=[NS(start=105,end=108,text=c.text)]
    direction={'accent_beats':[{'quote':'pintu ini rupanya','mood':'action','x':999,'filter':'bad code'}]}
    p=fx.build_plan(c,r,direction,enabled=True)
    assert p['cues'][0]['directed_by']=='creative_director_exact_quote'
    assert p['cues'][0]['mood']=='action' and 'x' not in p['cues'][0]
    direction['accent_beats'][0]['quote']='kalimat yang tidak ada'
    assert fx.build_plan(c,r,direction,enabled=True)['cues'][0]['directed_by']=='source_sentence'


@pytest.mark.parametrize('text', ['Inilah ayat yang dibacakan dengan perlahan.', 'Keluarga sedang berduka atas korban tragedi.', 'Tuduhan itu harus diperiksa sebelum disimpulkan.'])
def test_required_effect_on_sensitive_context_is_quiet_and_silent(text):
    c=clip(text)
    p=fx.build_plan(c,rows(c),enabled=True)
    assert len(p['cues'])==1 and p['sensitive_context']
    assert p['cues'][0]['kind'] in fx.MOODS['calm'] and p['cues'][0]['sound']=='none'


def test_variation_is_repeatable_within_clip_and_diverse_between_clips():
    variants=set()
    for i in range(12):
        c=clip('Wah hasilnya berubah menjadi lebih besar.',start=100+i*10)
        p=fx.build_plan(c,rows(c),enabled=True,seed=str(i))
        assert p==fx.build_plan(c,rows(c),enabled=True,seed=str(i))
        variants.add((p['cues'][0]['kind'],p['cues'][0]['variation']))
    assert len(variants)>=8


def test_long_budget_spends_at_most_two_accents_and_aggregates_output_time():
    candidates=[clip('Ternyata hasil akhirnya sudah berubah.',start=i*60) for i in range(8)]
    selected=fx.compilation_parts(candidates,['context']*6+['reveal','payoff'])
    assert selected=={7,8}
    audits=[]
    for i,c in enumerate(candidates,1):
        p=fx.build_plan(c,rows(c),enabled=True,budget=1 if i in selected else 0)
        if p['required']:p['rendered']=True
        audits.append(dict(part=i,output_duration_seconds=36,cron_director_effects=p))
    result=fx.aggregate_parts(audits)
    assert result['cue_count']==2 and result['cues'][0]['start']>=6*36


@pytest.mark.parametrize('kind',sorted({k for v in fx.MOODS.values() for k in v} - {'edge_focus'}))
def test_each_effect_has_finite_transparent_entry_and_visible_middle(kind):
    first=fx.effect_frame(kind,180,0,(255,240,220))
    middle=fx.effect_frame(kind,180,.45,(255,240,220))
    last=fx.effect_frame(kind,180,1,(255,240,220))
    assert first.getchannel('A').getbbox() is None
    assert middle.getchannel('A').getbbox() is not None
    assert last.getchannel('A').getbbox() is None


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='FFmpeg required')
@pytest.mark.parametrize('fps', ['30', '30000/1001'])
def test_encoded_effects_preserve_frame_count_duration_and_audio(tmp_path, fps):
    def run(args):
        r=subprocess.run(args,capture_output=True,text=True,timeout=90)
        assert r.returncode==0,r.stderr[-1600:]
        return r.stdout
    media=tmp_path/'source.mp4'
    run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'testsrc2=s=320x180:r={fps}:d=9',
        '-f','lavfi','-i','sine=frequency=330:sample_rate=48000:duration=9','-c:v','libx264','-preset','ultrafast',
        '-threads','1','-vf','pad=360:640:20:230:black','-pix_fmt','yuv420p','-c:a','aac',str(media)])
    before=fx._probe(media)
    audio_before=run(['ffmpeg','-v','error','-i',str(media),'-map','0:a','-c:a','copy','-f','md5','-'])
    c=clip('Wah ternyata hasilnya sudah berubah.',duration=9,start=0)
    p=fx.build_plan(c,[NS(start=3,end=5,text=c.text)],enabled=True)
    fx.render_effects(media,p,layout={'portrait':dict(layout='landscape_in_portrait',canvas_width=360,canvas_height=640,panel_width=320,panel_height=180,panel_y=230)},crf=20,preset='ultrafast',threads=1)
    after=fx._probe(media)
    audio_after=run(['ffmpeg','-v','error','-i',str(media),'-map','0:a','-c:a','copy','-f','md5','-'])
    assert before['frames']==after['frames']==270
    assert abs(before['duration']-after['duration'])<.04 and audio_before==audio_after
    assert p['rendered'] and p['cue_count']>=1
    assert p['renderer']=='procedural_rgba_accents'
    assert all(cue['placement_reason'] in {'measured_motion_detail_outside_protected_regions',
        'source_statement_outside_faces_and_caption_guards'} for cue in p['cues'])
    assert any(cue['statement_rendered'] and cue['kind']=='statement_focus' for cue in p['cues'])
    assert all(not fx._overlaps(cue['box'], guard) for cue in p['cues'] for guard in cue['protected_regions'])
    assert not list(tmp_path.glob('*.cron_tmp.mp4')) and not list((tmp_path/'.cron-director').glob('*.png'))


def test_worker_environment_does_not_leak_cron_flag(monkeypatch):
    import api
    monkeypatch.setenv('CLIPFORGE_CRON_DIRECTOR_EFFECTS','true')
    assert 'CLIPFORGE_CRON_DIRECTOR_EFFECTS' not in api.clipper_worker_environment(api.ClipJobRequest())
    assert api.clipper_worker_environment(api.ClipJobRequest(scheduled_director_effects=True))['CLIPFORGE_CRON_DIRECTOR_EFFECTS']=='true'


def test_upload_preflight_rejects_a_cron_result_without_rendered_effect(monkeypatch):
    import api
    c=api.ClipFile(name='clip_01.mp4',url='/outputs/job/clip_01.mp4',size_bytes=1)
    j=api.ClipJob(id='job',status='completed',created_at=api.now_iso(),updated_at=api.now_iso(),
        request=api.ClipJobRequest(scheduled_director_effects=True),clips=[c])
    monkeypatch.setattr(api,'clip_sidecar_payload',lambda c:{})
    assert 'aksen sutradara wajib' in api.youtube_monetization_preflight_issue(j,c)


@pytest.mark.parametrize('text', ['Makanannya tidak enak sama sekali.', 'Kita belum berhasil menang pertandingan ini.', 'Jangan lari ke sana dahulu.'])
def test_negated_sentiment_is_not_decorated_as_joy_or_success(text):
    c=clip(text)
    p=fx.build_plan(c,[NS(start=105,end=109,text=text)],enabled=True)
    assert p['cues'][0]['mood']=='emphasis'


def test_effect_cannot_use_a_phrase_outside_the_clipped_source_boundary():
    c=clip('Kalimat yang masih menyambung.',duration=20)
    p=fx.build_plan(c,[NS(start=118,end=128,text='Ternyata hasilnya berubah di akhir kalimat.')],enabled=True)
    assert p['cues'][0]['directed_by']=='quiet_fallback_no_timed_dialogue'


def test_effect_renderer_has_a_required_standard_filter_fallback(tmp_path, monkeypatch):
    if not shutil.which('ffmpeg'):pytest.skip('FFmpeg required')
    media=tmp_path/'video.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=blue:s=320x568:r=30:d=4','-c:v','libx264','-threads','1','-preset','ultrafast',str(media)],check=True)
    c=clip('Lihat hasilnya sekarang.',duration=4,start=0)
    p=fx.build_plan(c,[NS(start=1,end=3,text=c.text)],enabled=True)
    monkeypatch.setattr(fx,'place_cues',lambda *a,**k: (_ for _ in ()).throw(ValueError('No optional detector/assets')))
    fx.render_effects(media,p,preset='ultrafast',threads=1)
    assert p['rendered'] and p['cue_count']==1 and p['renderer']=='drawbox_edge_focus'


def test_scheduler_sets_mandatory_accents_even_if_optional_editor_is_disabled(monkeypatch):
    import api
    monkeypatch.setenv('AUTO_VIRAL_SCHEDULE_HUMAN_EDITOR_ENABLED','false')
    monkeypatch.setattr(api,'viral_source_rejection_reason',lambda *a,**k:'')
    monkeypatch.setattr(api,'wait_for_no_active_clipping_job',lambda:None)
    monkeypatch.setattr(api,'queue_auto_viral_clip_job',lambda req:req)
    source=dict(url='https://www.youtube.com/watch?v=abcDEF12345')
    cron=api.create_auto_viral_clip_job(source,api.AutoViralRequest(),scheduled=True)
    manual=api.create_auto_viral_clip_job(source,api.AutoViralRequest(),scheduled=False)
    assert cron.scheduled_director_effects and not cron.scheduled_human_editor
    assert not manual.scheduled_director_effects


def test_public_manual_endpoint_strips_internal_effect_flag(monkeypatch):
    import api
    captured=[]
    def stop_after_sanitization(req):
        captured.append(req)
        raise RuntimeError('observed sanitized request')
    monkeypatch.setattr(api,'ensure_source_rights_attestation',stop_after_sanitization)
    with pytest.raises(RuntimeError,match='observed sanitized request'):
        api.create_job(api.ClipJobRequest(scheduled_director_effects=True))
    assert not captured[0].scheduled_director_effects


def test_malformed_ai_hints_cannot_remove_the_required_fallback():
    c=clip('Kita mulai dari bagian ini dahulu.')
    for raw in [None, 'not json', [None], [{'quote':'bagian ini','mood':[]}], [{'quote':None,'mood':'surprise'}]]:
        p=fx.build_plan(c,rows(c),{'accent_beats':raw},enabled=True)
        assert p['required'] and len(p['cues'])>=1


def test_valid_effect_proof_does_not_bypass_source_rights_gate(monkeypatch):
    import api
    c=api.ClipFile(name='clip_01.mp4',url='/outputs/job/clip_01.mp4',size_bytes=1)
    j=api.ClipJob(id='job',status='completed',created_at=api.now_iso(),updated_at=api.now_iso(),
        request=api.ClipJobRequest(url='https://www.youtube.com/watch?v=abcDEF12345',scheduled_director_effects=True),clips=[c])
    monkeypatch.setattr(api,'clip_sidecar_payload',lambda c:{'cron_director_effects':dict(rendered=True,cue_count=1,verification='duration_frame_count_and_geometry_preserved')})
    monkeypatch.setattr(api,'metadata_for_job',lambda j:{'license':'youtube'})
    issue=api.youtube_monetization_preflight_issue(j,c)
    assert issue and 'lisensi' in issue.casefold() and 'aksen' not in issue.casefold()


@pytest.mark.parametrize('source,phrase,expected', [
    ('Takut numpuk.', '', 'Takut numpuk'),
    ('Ini bukan makanan enak.', 'makanan enak', ''),
    ('Ini belum berhasil.', 'Ini berhasil', ''),
    ('Makanannya tidak enak.', '', 'Makanannya tidak enak'),
    ('Menurut dia ini enak.', 'ini enak', ''),
    ('Menurut dia ini enak.', 'Menurut dia ini enak', 'Menurut dia ini enak'),
    ('Kalau berhasil kita pulang.', 'kita pulang', ''),
    ('Apakah ini benar benar enak?', 'benar benar enak', ''),
    ('Ini makanan biasa.', 'Ini makanan paling enak', ''),
    ('Hari ini kita duduk di rumah.', '', ''),
    ('Jangan sampai numpuk lagi.', '', 'Jangan sampai numpuk lagi'),
    ('Katanya ini diduga bukan milik dia.', 'ini bukan milik dia', ''),
    ('Astaga itu aspal yang kamu cium bukan', '', ''),
    ('Bukan bukan.', '', ''),
    ('Kalau bisa jangan sampai kelihatan kalau', '', ''),
    ('Ini bisa berhasil nanti.', 'berhasil nanti', ''),
    ('Dia bilang makanan ini enak.', 'makanan ini enak', ''),
    ('Ternyata makanan yang di sebelah itu', '', ''),
])
def test_statement_preserves_source_words_and_qualifiers(source,phrase,expected):
    assert fx.statement_phrase(source,phrase)==expected


def test_statement_is_optional_within_existing_budget_and_manual_stays_off():
    c=clip('Takut numpuk. Ternyata hasilnya enak sekali.')
    segments=[NS(start=104,end=107,text='Takut numpuk.'),NS(start=122,end=125,text='Ternyata hasilnya enak sekali.')]
    p=fx.build_plan(c,segments,enabled=True)
    assert len(p['cues'])==2
    assert sum(bool(c['statement']) for c in p['cues'])==1
    assert fx.build_plan(c,segments)['cues']==[]
    assert fx.statement_phrase('Jangan takut numpuk.',sensitive=True)==''


def test_ai_statement_is_validated_against_source_not_trusted_as_new_headline():
    c=clip('Ternyata ini bukan milik dia.')
    s=[NS(start=105,end=109,text=c.text)]
    p=fx.build_plan(c,s,{'accent_beats':[dict(quote='bukan milik dia',mood='emphasis',statement='milik dia')]},enabled=True)
    assert p['cues'][0]['statement']==''
    p=fx.build_plan(c,s,{'accent_beats':[dict(quote='bukan milik dia',mood='emphasis',statement='bukan milik dia')]},enabled=True)
    assert p['cues'][0]['statement']=='bukan milik dia'


def test_statement_animation_has_single_arrival_stable_hold_and_transparent_ends():
    args=('BUKAN MILIK DIA',420,170)
    first=fx.statement_frame(*args,0,(125,240,217),style='comic')
    a=fx.statement_frame(*args,.4,(125,240,217),style='comic')
    b=fx.statement_frame(*args,.6,(125,240,217),style='comic')
    last=fx.statement_frame(*args,1,(125,240,217),style='comic')
    assert first.getchannel('A').getbbox() is None and last.getchannel('A').getbbox() is None
    assert a.getchannel('A').getbbox() is not None and a.tobytes()==b.tobytes()


@pytest.mark.parametrize('text,expected',[
    ('Cerita Roblox gameplay hari ini.','GAMEPLAY'),
    ('Makanan di warung ini gurih sekali.','KULINER'),
    ('Kajian tentang ibadah dan hikmah.','HIKMAH'),
    ('Langkah tutorial merawat tanaman.','TIPS'),
    ('Keluarga berduka karena kecelakaan.','TERIMA KASIH'),
])
def test_follow_invitation_is_topical_without_fake_sequel_or_engagement_promise(text,expected):
    copy=fx.follow_copy(clip(text))
    assert expected in copy['support'] and copy['action']=='FOLLOW'
    assert not any(word in str(copy).casefold() for word in ['part 2','viral','pasti','jutaan'])


def test_follow_invitation_uses_one_source_boundary_and_avoids_accent_windows():
    c=clip('Ternyata hasilnya sudah berubah. Perhatikan bagian ini.')
    accents=fx.build_plan(c,rows(c),enabled=True)
    plan=fx.follow_plan(c,rows(c),accents,enabled=True)
    assert plan['enabled'] and plan['repeat_count']==1 and plan['silent']
    assert plan['position']=='middle' and plan['start']>=4.2 and plan['end']<c.end-c.start-2.4
    assert all(plan['end']<=cue['start']-.35 or plan['start']>=cue['end']+.35 for cue in accents['cues'])
    assert not fx.follow_plan(c,rows(c),accents)['enabled']
    assert not fx.follow_plan(c,rows(c),accents,enabled=True,protected_layout=True)['enabled']


def test_follow_can_use_ending_after_complete_value_or_skip_when_every_window_is_occupied():
    c=clip(duration=50)
    plan=fx.follow_plan(c,rows(c),{'cues':[]},enabled=True,protect_ending=False)
    assert plan['position']=='ending' and plan['end']<50
    busy={'cues':[dict(start=0,end=50)]}
    assert not fx.follow_plan(c,rows(c),busy,enabled=True)['enabled']


def test_adaptive_follow_filter_uses_measured_window_and_topic_copy():
    from clipper import shorts_mid_subscribe_pulse_filter
    c=clip('Makanan di warung ini enak.',duration=30)
    plan=fx.follow_plan(c,rows(c),{'cues':[]},enabled=True)
    value=shorts_mid_subscribe_pulse_filter(30,follow_plan=plan)
    assert "text='FOLLOW'" in value and 'ULASAN KULINER LAINNYA' in value
    assert f"between(t,{plan['start']:.3f},{plan['end']:.3f})" in value
