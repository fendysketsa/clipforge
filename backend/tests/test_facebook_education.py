import copy
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import api
import facebook_api
import facebook_autopilot as policy
import facebook_education as education
import facebook_motlab as motlab
import facebook_originals as originals


def measured(topic='count_objects'):
    series=education.TOPICS[topic]['series']
    plan=originals.plan('education-test',topic=topic,series=series)
    for i,stage in enumerate(plan['stages']):stage.update(start=i*8.,end=(i+1)*8.)
    plan['motion_timeline']=education.timeline(plan)
    return plan


def test_catalogue_is_complete_and_new_settings_default_to_character_stories():
    catalogue=originals.series_catalogue()
    assert {r['key'] for r in catalogue}==set(education.SERIES)|{originals.stories.SERIES_KEY}
    assert {t['key'] for row in catalogue if row['key'] not in ('digital',originals.stories.SERIES_KEY)
            for t in row['topics']}==set(education.TOPICS)
    assert next(r for r in catalogue if r['key']==originals.stories.SERIES_KEY)['topics']==[]
    assert policy.config({'enabled':False})['series']==originals.stories.SERIES_KEY
    assert not policy.config({'enabled':False,'series':'nature'})['enabled']
    with pytest.raises(ValueError):policy.config({'series':'unknown'})
    with pytest.raises(ValueError):originals.plan('s',series='kids_basics',topic='group')


@pytest.mark.parametrize('topic',list(education.TOPICS))
def test_education_is_original_curated_and_bound_to_the_on_screen_concept(topic,monkeypatch):
    p=measured(topic);before=copy.deepcopy(p)
    monkeypatch.setattr(originals,'provider_config',lambda:pytest.fail('Curated education needs no author provider'))
    authored=originals.author(p)
    assert p==before and authored['render_engine']=='motlab'
    assert authored['education']['original_characters']
    assert 65<=sum(len(s['text'].split()) for s in authored['stages'])<=95
    assert authored['authoring']=='curated_education_script'
    education.verify_plan(authored)
    with pytest.raises(ValueError,match='identik'):originals.author(p,[authored['script_sha256']])
    p['stages'][2]['text']='Klaim baru yang tidak didemonstrasikan.'
    with pytest.raises(ValueError,match='konsep'):education.verify_plan(p)


def test_count_reveals_match_measured_spoken_numbers_without_duplicating_apples():
    p=measured()
    cues=[SimpleNamespace(start=16+i,end=16.5+i,text=w) for i,w in enumerate(('Satu.','Dua.','Tiga.'))]
    p['motion_timeline']=education.timeline(p,cues)
    assert p['motion_timeline']['reveals']==[16,17,18]
    for t,wanted in ((15,0),(16.5,1),(17.5,2),(18.5,3),(31,3)):
        s=education.scene(p,t)
        assert s['learning']['count']==wanted
        assert sum(x['active'] for x in s['props'])==wanted
        assert len(s['props'])==3 and len({x['id'] for x in s['props']})==3


def test_shapes_land_in_matching_slots_and_stay_visible():
    p=measured('shape_match')
    s=education.scene(p,31)
    assert s['learning']=={'matched':3,'total':3}
    assert [(x['kind'],x['y']) for x in s['props']]==[('circle',590),('triangle',590),('square',590)]


def test_toy_cleanup_conserves_all_three_objects_throughout_motion():
    p=measured('tidy_toys')
    for frame in range(960):
        s=education.scene(p,frame/30)
        assert s['learning']['floor']+s['learning']['box']==3
        assert len({x['id'] for x in s['props']})==3
    assert education.scene(p,31)['learning']['box']==3


def test_turn_taking_moves_one_car_between_the_named_characters():
    p=measured('take_turns');start=education.scene(p,3);end=education.scene(p,31)
    assert start['learning']['owner']==p['education']['characters'][0]
    assert end['learning']['owner']==p['education']['characters'][1]
    assert start['props'][0]['id']==end['props'][0]['id']=='shared-car'
    assert len(end['props'])==1 and end['props'][0]['x']==730


def test_science_models_show_causes_and_explicit_time_compression():
    p=measured('plant_growth');rows=[education.scene(p,t)['learning'] for t in (3,16,19,24)]
    assert p['education']['scientific_time_compressed']
    assert rows[0]['root']==rows[0]['stem']==rows[0]['leaves']==0
    assert rows[-1]['root']==rows[-1]['stem']==rows[-1]['leaves']==1
    p=measured('shadow_light')
    assert not education.scene(p,3)['learning']['shadow']
    assert education.scene(p,22)['learning']['shadow']
    assert not education.scene(p,31)['learning']['shadow']


@pytest.mark.parametrize('topic',list(education.TOPICS))
def test_native_education_project_retains_its_module_hash_and_semantic_frames(tmp_path,topic):
    p=measured(topic)
    page,stamp=motlab.write_project(p,[(0,32,'Mari belajar bersama.')],32,tmp_path,originals.state)
    data=json.loads(page.with_name('film.json').read_text())
    assert data['education']==p['education']
    assert data['frames'][750]==json.loads(json.dumps(education.scene(p,25)))
    motlab.verify_evidence(tmp_path,stamp)
    page.with_name('education-scene.mjs').write_text('// tampered module')
    with pytest.raises(ValueError,match='edukasi'):motlab.verify_evidence(tmp_path,stamp)


def test_setting_education_series_preserves_pause_upload_identity_and_qc_holds():
    ledger=api.JOBS_PATH.parent/'facebook_workspace.json'
    source={'schema':1,'uploads':{'u':{'id':'u','submission_started':True,'video_url':'https://www.facebook.com/reel/123/'}},
        'session':{},'autopilot':{'enabled':False},'autopilot_runs':{'held':{'status':'qc_wait','authored_plan':{'seed':'keep'}}}}
    ledger.write_text(json.dumps(source))
    client=TestClient(api.app)
    result=client.post('/api/facebook/autopilot',json={'enabled':False,'series':'kids_basics'})
    assert result.status_code==200 and result.json()['config']['series']=='kids_basics'
    persisted=json.loads(ledger.read_text())
    assert not persisted['autopilot']['enabled']
    assert persisted['uploads']==source['uploads'] and persisted['autopilot_runs']==source['autopilot_runs']
    assert facebook_api.Store(ledger).data['autopilot']['series']=='kids_basics'
    before=ledger.read_text()
    assert client.post('/api/facebook/autopilot',json={'enabled':False,'series':'unknown'}).status_code==422
    assert ledger.read_text()==before
