import copy
import json
from types import SimpleNamespace

import pytest

import facebook_creative as creative
import facebook_motion as motion
import facebook_originals as originals


def plan(topic='copy'):
    result=originals.plan('motion-tests-v1',topic=topic)
    for i,stage in enumerate(result['stages']):stage.update(start=i*8.,end=(i+1)*8.)
    result['motion_timeline']=motion.timeline(result)
    return result


def at(p,fraction):
    c=p['motion_timeline']
    return c['departure']+(c['arrival']-c['departure'])*fraction


def test_verb_anchor_and_sound_events_share_measured_narration_clock():
    p=plan();cues=[SimpleNamespace(start=16,end=19,text='Saat disalin, salinannya bergerak.')]
    clock=motion.timeline(p,cues);p['motion_timeline']=clock
    events=creative.sound_plan(p,32)['events']
    assert 16<=clock['select']<clock['departure']<clock['arrival']<24
    assert events[1]['start']==clock['select']
    assert events[2]['start']==clock['departure'] and events[3]['start']==clock['arrival']
    assert clock['alignment']=='measured_tts_phrase_with_estimated_verb_position'


def test_copy_keeps_original_and_moves_only_distinct_clone():
    p=plan();before=motion.scene(p,2,originals.state)
    middle=motion.scene(p,at(p,.5),originals.state);end=motion.scene(p,31.9,originals.state)
    assert before['source_count']==1 and before['stored_count']==1
    assert len(middle['items'])==2 and {r['key'] for r in middle['items']}=={'a','a:copy'}
    original=next(r for r in middle['items'] if r['role']=='original')
    clone=next(r for r in middle['items'] if r['role']=='copy')
    assert (original['x'],original['y'])==(165,675)
    assert 165<clone['x']<635 and 540<clone['y']<675
    assert end['stored_count']==2 and [f['count'] for f in end['folders']]==[1,1]
    assert next(r for r in end['items'] if r['role']=='copy')['x']==635


def test_result_inspection_animates_the_same_copy_without_creating_another_file():
    p=plan();t=p['motion_timeline']['inspect']+.55
    pose=motion.scene(p,t,originals.state)
    assert pose['stored_count']==2 and len(pose['items'])==2
    clone=next(r for r in pose['items'] if r['role']=='copy')
    assert clone['w']>250 and clone['y']<620 and clone['key']=='a:copy'
    end=next(r for r in motion.scene(p,31.9,originals.state)['items'] if r['role']=='copy')
    assert end['w']==200 and end['y']==675


@pytest.mark.parametrize('topic',['restore','group'])
def test_move_and_restore_never_invent_a_copy(topic):
    p=plan(topic);source=motion.scene(p,2,originals.state);end=motion.scene(p,25,originals.state)
    assert source['stored_count']==end['stored_count']
    assert {r['key'] for r in source['items']}=={r['key'] for r in end['items']}
    assert all(r['role']=='original' for r in end['items'])
    assert [f['count'] for f in end['folders']]==([0,1] if topic=='restore' else [1,2])


@pytest.mark.parametrize('topic',['date','size','number'])
def test_sort_uses_disjoint_lanes_and_ends_in_actual_operation_order(topic):
    p=plan(topic)
    for index in range(101):
        pose=motion.scene(p,at(p,index/100),originals.state)
        rows=pose['items']
        for i,a in enumerate(rows):
            assert 80<=a['x']<=650 and 520<=a['y']<=1030
            for b in rows[i+1:]:
                overlap_x=a['x']<b['x']+b['w'] and b['x']<a['x']+a['w']
                overlap_y=a['y']<b['y']+b['h'] and b['y']<a['y']+a['h']
                assert not (overlap_x and overlap_y), (topic,index,a,b)
    final=sorted(motion.scene(p,25,originals.state)['items'],key=lambda r:r['x'])
    assert [r['label'] for r in final]==[r['label'] for r in originals.state(p,2)[0]]


def test_search_hides_only_matches_then_restores_without_deleting():
    p=plan('search');filtered=motion.scene(p,23,originals.state);restored=motion.scene(p,31,originals.state)
    assert filtered['query']=='kegiatan' and filtered['stored_count']==3
    assert sum(r['visible'] for r in filtered['items'])==1
    assert restored['query']=='' and sum(r['visible'] for r in restored['items'])==3
    assert restored['stored_count']==3


def test_paths_show_two_distinct_contents_without_a_transfer():
    p=plan('paths');pose=motion.scene(p,25,originals.state)
    a,b=pose['items'];assert a['label']==b['label'] and a['detail']!=b['detail']
    assert all(r['role']=='original' for r in pose['items'])
    assert [r['label'] for r in pose['folders']]==['Rumah','Kerja']


@pytest.mark.parametrize('topic',[r[0] for r in originals.TOPICS])
def test_all_topics_render_without_mutating_source_or_losing_final_identity(topic):
    p=plan(topic);snapshot=copy.deepcopy(p)
    for t in (0,1,9,at(p,.5),25,31.5):
        image=originals.frame(p,t,[(0,32,'Contoh jelas. Narasi tetap terbaca.')])
        assert image.size==(1080,1920)
    assert p==snapshot
    state=motion.scene(p,31.5,originals.state)
    assert state['complete'] and len({r['key'] for r in state['items']})==len(state['items'])


def test_motion_is_actual_object_travel_not_only_caption_or_background_change():
    p=plan();a=motion.scene(p,at(p,.25),originals.state);b=motion.scene(p,at(p,.75),originals.state)
    ca=next(r for r in a['items'] if r['role']=='copy');cb=next(r for r in b['items'] if r['role']=='copy')
    assert cb['x']-ca['x']>250
    assert a['clock']==b['clock'] and ca['label']==cb['label']


def test_unmeasured_or_too_short_timeline_cannot_produce_fabricated_actions():
    p=plan();p['stages'][2]['end']=17
    with pytest.raises(ValueError,match='window'):motion.timeline(p)


def test_new_jobs_choose_motion_and_legacy_checkpoint_keeps_legacy_renderer(monkeypatch):
    p=plan();assert p['motion_version']==1 and p['creative_policy']['first_result_preview'] is None
    p.pop('motion_version');calls=[]
    monkeypatch.setattr(originals,'legacy_frame',lambda *args:calls.append('legacy') or 'old')
    assert originals.frame(p,2,[])=='old' and calls==['legacy']
