import copy
import json

import pytest

import facebook_motlab as renderer
import facebook_motion as motion
import facebook_originals as originals


def measured(topic='copy'):
    p=originals.plan('motlab-facebook-test',topic=topic)
    for i,stage in enumerate(p['stages']):stage.update(start=i*8.,end=(i+1)*8.)
    p['motion_timeline']=motion.timeline(p)
    return p


@pytest.mark.parametrize('topic',[row[0] for row in originals.TOPICS])
def test_native_project_uses_exact_semantic_poses_and_stable_caption_cues(tmp_path,topic):
    plan=measured(topic);before=copy.deepcopy(plan)
    cues=[(0,16,'Contoh yang jelas.'),(16,32,'Lihat hasilnya.')]
    page,stamp=renderer.write_project(plan,cues,32,tmp_path,originals.state)
    film=json.loads(page.with_name('film.json').read_text())
    assert plan==before and len(film['frames'])==960
    assert film['captionCues']==[dict(start=a,end=b,text=t) for a,b,t in cues]
    for index in (0,500,590,959):
        expected=json.loads(json.dumps(motion.scene(plan,index/30,originals.state)))
        assert film['frames'][index]==expected
    assert stamp['engine']=='motlab' and stamp['native_canvas']
    renderer.verify_evidence(tmp_path,stamp)
    assert json.loads(page.with_name('project.json').read_text())['audio']==[]


def test_moral_story_renders_a_character_scene_through_the_story_module(tmp_path):
    import facebook_stories as stories
    plan=stories.plan('motlab-character-test','reel','anak tersedak saat minum es dingin',style='moral_anak')
    for i,stage in enumerate(plan['stages']):stage.update(start=i*8.,end=(i+1)*8.)
    plan['motion_timeline']=stories.timeline(plan)
    cues=[(0,16,'Lihat apa yang terjadi.'),(16,32,'Minum pelan-pelan.')]
    page,stamp=renderer.write_project(plan,cues,32,tmp_path,originals.state)
    film=json.loads(page.with_name('film.json').read_text())
    assert film['frames'][30]['scene']=='drink_choking'
    assert film['frames'][30]['stage_starts']==[8.,16.,24.]
    assert (page.parent/'story-scene.mjs').exists()
    assert not (page.parent/'education-scene.mjs').exists()
    assert stamp['story_scene_sha256']
    renderer.verify_evidence(tmp_path,stamp)


def test_authored_text_never_becomes_executable_scene_code(tmp_path):
    plan=measured();plan['title']='</script><script>alert(1)</script>'
    page,stamp=renderer.write_project(plan,[(0,32,plan['title'])],32,tmp_path,originals.state)
    assert 'alert(1)' not in page.read_text()
    assert 'alert(1)' not in page.with_name('scene.mjs').read_text()
    for asset in ('film.json','scene.mjs'):
        saved=page.with_name(asset).read_text()
        page.with_name(asset).write_text(saved+' ')
        with pytest.raises(ValueError,match='Bukti render'):renderer.verify_evidence(tmp_path,stamp)
        page.with_name(asset).write_text(saved)


def test_new_plans_select_motlab_but_legacy_plans_keep_their_render_path(tmp_path,monkeypatch):
    plan=measured();assert plan['render_engine']=='motlab'
    legacy=copy.deepcopy(plan);legacy.pop('render_engine')
    monkeypatch.setattr(renderer,'require_motlab_runtime',lambda:pytest.fail('Legacy renderer changed'))
    def voice(*args):raise InterruptedError('Legacy voice reached')
    monkeypatch.setattr(originals,'voice',voice)
    with pytest.raises(InterruptedError,match='Legacy voice reached'):originals.render(legacy,tmp_path)
    assert 'render_engine' not in json.loads((tmp_path/'source-plan.json').read_text())


def test_missing_motlab_blocks_before_voice_and_never_calls_legacy_fallback(tmp_path,monkeypatch):
    def unavailable():raise RuntimeError('Runtime Motlab belum siap')
    monkeypatch.setattr(renderer,'require_motlab_runtime',unavailable)
    monkeypatch.setattr(originals,'voice',lambda *a:pytest.fail('Voice must not start'))
    monkeypatch.setattr(originals,'frame',lambda *a:pytest.fail('No legacy fallback'))
    with pytest.raises(RuntimeError,match='Runtime Motlab'):originals.render(measured(),tmp_path)
    assert not (tmp_path/'source-plan.json').exists()


def test_failed_canvas_export_never_becomes_completed_mp4(tmp_path,monkeypatch):
    def fail(**kwargs):raise RuntimeError('Export failed')
    monkeypatch.setattr(renderer,'render_canvas_with_motlab',fail)
    with pytest.raises(RuntimeError,match='Export failed'):
        renderer.render(measured(),[(0,32,'Caption tetap.')],32,tmp_path,originals.state,lambda *a:None)
    assert not (tmp_path/'facebook_original.mp4').exists()


@pytest.mark.parametrize('length',[0,56,float('nan')])
def test_invalid_duration_is_rejected(tmp_path,length):
    with pytest.raises(ValueError):renderer.write_project(measured(),[],length,tmp_path,originals.state)
