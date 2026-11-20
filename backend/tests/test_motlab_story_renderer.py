import json
from types import SimpleNamespace

import pytest

import motlab_story_renderer as renderer


@pytest.fixture
def manifest(tmp_path):
    assets = tmp_path / 'public' / 'assets'
    assets.mkdir(parents=True)
    (assets / 'image.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"/>')
    shot = dict(id='shot-001', startFrame=0, bodyDurationInFrames=60, durationInFrames=60,
        asset='image.svg', kind='image', cameraMotion='push_in', framing='close_up',
        subjectPlacement='center', narrativeRole='evidence_and_answer',
        onScreenText='Air → Turbin → Listrik', narration='Air mengalir. Turbin berputar. Listrik dihasilkan.',
        motionDesign={'accentColor':'#65B7FF'})
    composition = dict(width=1080, height=1920, fps=30, durationSeconds=2,
        shots=[shot], captionCues=[
            {'text':'Air mengalir.', 'startFrame':0, 'endFrame':20},
            {'text':'Turbin berputar.', 'startFrame':20, 'endFrame':40},
            {'text':'Listrik dihasilkan.', 'startFrame':40, 'endFrame':60},
        ])
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps({'publicDir':str(assets.parent), 'composition':composition}))
    return path, composition


def test_diagram_reveals_use_real_spoken_cue_boundaries(manifest):
    path, comp = manifest
    plan = renderer.build_motion_design(comp)[0]
    assert plan['diagram'] == [dict(label='Air', atFrame=0), dict(label='Turbin', atFrame=20),
                                dict(label='Listrik', atFrame=40)]
    assert plan['maxZoom'] <= 1.035 and plan['captionAnimation'] == 'none'


def test_repeated_words_cannot_move_the_last_reveal_before_its_cause(manifest):
    _, comp = manifest
    comp['shots'][0]['narration'] = 'Air tersedia saat listrik padam. Turbin berputar menghasilkan listrik.'
    comp['captionCues'] = [
        dict(text='Air tersedia saat listrik padam.', startFrame=0, endFrame=20),
        dict(text='Turbin berputar', startFrame=20, endFrame=40),
        dict(text='menghasilkan listrik.', startFrame=40, endFrame=60),
    ]
    nodes = renderer.build_motion_design(comp)[0]['diagram']
    assert [node['atFrame'] for node in nodes] == [0, 20, 40]


@pytest.mark.parametrize('text,narration', [
    ('Air → Turbin → Listrik', 'Air tidak menggerakkan turbin atau menghasilkan listrik.'),
    ('Air → Uang → Listrik', 'Air mengalir. Turbin berputar. Listrik dihasilkan.'),
    ('Air → Turbin → Listrik', 'Listrik menyalakan lampu. Turbin berhenti. Air mengalir.'),
    ('Hikmah dari kehidupan', 'Hikmah dari kehidupan.'),
])
def test_unsubstantiated_flow_cannot_become_a_graphic(manifest, text, narration):
    _, comp = manifest
    comp['shots'][0].update(onScreenText=text, narration=narration)
    assert renderer.build_motion_design(comp)[0]['diagram'] == []


@pytest.mark.parametrize('change', ['gap', 'duration', 'odd_size', 'empty'])
def test_timeline_mismatch_is_rejected_before_render(manifest, change):
    _, comp = manifest
    if change == 'gap':comp['shots'][0]['startFrame'] = 1
    if change == 'duration':comp['durationSeconds'] = 3
    if change == 'odd_size':comp['width'] = 1081
    if change == 'empty':comp['shots'] = []
    with pytest.raises(renderer.MotlabRenderError):renderer.build_motion_design(comp)


def test_project_keeps_assets_cues_and_authored_text_outside_executable_html(manifest, tmp_path):
    path, comp = manifest
    comp['shots'][0]['onScreenText'] = '</script><script>alert(1)</script>'
    doc = json.loads(path.read_text());doc['composition'] = comp;path.write_text(json.dumps(doc))
    page = renderer.write_motlab_project(path, tmp_path / 'project')
    data = json.loads(page.with_name('film.json').read_text())
    assert data['captionCues'] == comp['captionCues']
    assert '<script>alert(1)' not in page.read_text()
    assert page.with_name('assets').joinpath('image.svg').is_file()
    policy = json.loads(page.with_name('motion-policy.json').read_text())
    assert policy['captions_outside_picture_transitions']
    assert policy['timeline_source'] == 'measured_tts_frames'
    assert not policy['caption_flicker_allowed']


@pytest.mark.parametrize('bad_geometry', [False, True])
def test_render_checks_the_encoded_duration_and_geometry(manifest, tmp_path, monkeypatch, bad_geometry):
    path, _ = manifest
    output = tmp_path / 'movie.mp4'
    package = tmp_path / 'engine/node_modules/@motlab/cli/package.json'
    package.parent.mkdir(parents=True);package.write_text('{"version":"0.3.0"}')
    (package.parents[3] / 'scene.mjs').write_text('// test scene')
    monkeypatch.setattr(renderer, 'RENDERER_DIR', package.parents[3])
    monkeypatch.setattr(renderer.shutil, 'which', lambda _: '/usr/bin/node')
    monkeypatch.setattr(renderer, 'require_motlab_runtime', lambda: '/usr/bin/node')
    monkeypatch.setattr(renderer, '_browser_executable', lambda: '/usr/bin/chrome')
    monkeypatch.setattr(renderer, 'prepare_story_manifest', lambda **kwargs: (output, path))
    calls=[]
    def start(command, **kwargs):
        calls.append((command, kwargs));output.write_bytes(b'encoded video')
        return SimpleNamespace(stdout=['MOTLAB_HEARTBEAT:10\n'], wait=lambda:0)
    monkeypatch.setattr(renderer.subprocess, 'Popen', start)
    probe = {'streams':[{'codec_type':'video', 'width':720 if bad_geometry else 1080, 'height':1920}],
             'format':{'duration':'2.000'}}
    monkeypatch.setattr(renderer.subprocess, 'run', lambda *a, **k:
        SimpleNamespace(returncode=0, stdout=json.dumps(probe)))
    kwargs = dict(scene_dir=tmp_path / 'scenes', video_quality='high',
        duration=2.0, width=1080, height=1920, progress=lambda *a:None)
    if bad_geometry:
        with pytest.raises(renderer.MotlabRenderError, match='durasi narasi'):
            renderer.render_story_with_motlab(**kwargs)
    else:
        rendered, project=renderer.render_story_with_motlab(**kwargs)
        assert rendered == output and project.name == 'project.json'
        assert calls[0][1]['env']['CHROME'] == '/usr/bin/chrome'
        assert 'upload' not in ' '.join(calls[0][0])


def test_selected_runtime_failure_stops_before_generation(monkeypatch, tmp_path):
    import long_animate as story
    from llm import AIConfig
    monkeypatch.setenv('LONG_ANIMATE_RENDER_ENGINE', 'motlab')
    def unavailable():raise renderer.MotlabRenderError('Node 24 belum siap')
    monkeypatch.setattr(story, 'require_motlab_runtime', unavailable)
    monkeypatch.setattr(story, 'require_motion_video_provider', lambda:
        pytest.fail('Generation must not begin before renderer readiness'))
    with pytest.raises(story.LongAnimateVideoError, match='Node 24'):
        story.render_long_animate('Naskah contoh', tmp_path, AIConfig())


def test_explicit_operator_renderer_is_preserved(monkeypatch):
    monkeypatch.setenv('LONG_ANIMATE_RENDER_ENGINE', 'remotion')
    assert renderer.rendering_capabilities()['default_engine'] == 'remotion'
    monkeypatch.delenv('LONG_ANIMATE_RENDER_ENGINE')
    assert renderer.rendering_capabilities()['default_engine'] == 'motlab'


def test_renderer_experiment_is_stable_and_distinguishes_real_variants():
    first = renderer.story_render_experiment('motlab', 1080, 1920, True)
    assert first == renderer.story_render_experiment('motlab', 1080, 1920, True)
    assert first['recipe_hash'] != renderer.story_render_experiment('remotion', 1080, 1920, True)['recipe_hash']
    assert first['recipe_hash'] != renderer.story_render_experiment('motlab', 1920, 1080, True)['recipe_hash']
    assert not first['actual_performance_verified'] and not first['view_or_subscriber_guarantee']

