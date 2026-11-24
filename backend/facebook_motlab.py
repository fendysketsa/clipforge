"""Facebook's measured semantic object timeline exported through staryone Motlab."""
import hashlib
import json
import math
from pathlib import Path
import shutil

import facebook_motion as motion
import facebook_education as education
import facebook_stories as stories
from motlab_story_renderer import render_canvas_with_motlab, require_motlab_runtime

VERSION = 1
ENGINE = 'motlab'
SCENE = Path(__file__).resolve().parent / 'motlab/facebook-scene.mjs'
STORY_SCENE = SCENE.with_name('story-scene.mjs')


def capabilities():
    return dict(version=VERSION, engine=ENGINE, package='@motlab/cli', package_version='0.3.0',
                upstream='staryone/motlab', fps=30, native_canvas=True,
                timeline_source='measured_tts_frames', legacy_checkpoints_preserved=True)


def write_project(plan, cues, length, folder, state):
    if (not math.isfinite(length) or not 0 < length <= 55
            or plan.get('motion_version') != motion.VERSION):
        raise ValueError('Timeline animasi Facebook Motlab belum valid.')
    project = folder / 'motlab_project'
    project.mkdir(parents=True, exist_ok=True)
    # All poses come from the existing deterministic semantic model. The canvas
    # draws vectors directly; there are no raster slides or executable AI code.
    if plan.get('education'):
        scene_at = lambda index: education.scene(plan, index / motion.FPS)
    elif plan.get('story'):
        scene_at = lambda index: stories.scene(plan, index / motion.FPS)
    else:
        scene_at = lambda index: motion.scene(plan, index / motion.FPS, state)
    frames = [scene_at(i) for i in range(math.ceil(length * motion.FPS))]
    payload = dict(version=VERSION, width=1080, height=1920, fps=motion.FPS,
                   durationSeconds=length, title=plan['title'], topic=plan['topic'],
                   captionFontSize=plan.get('caption_font_size', 48),
                   captionCues=[dict(start=a, end=b, text=text) for a, b, text in cues],
                   frames=frames)
    if plan.get('education'):
        education.verify_plan(plan)
        payload['education']=plan['education']
        shutil.copyfile(SCENE.with_name('education-scene.mjs'),project/'education-scene.mjs')
    elif plan.get('story'):
        stories.verify_plan(plan)
        payload['story']=plan['story']
        shutil.copyfile(STORY_SCENE,project/'story-scene.mjs')
    manifest = project / 'film.json'
    manifest.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')))
    shutil.copyfile(SCENE, project / 'scene.mjs')
    page = project / 'film.html'
    page.write_text('<!doctype html><html lang="id"><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'self\' data: blob:; '
        'script-src \'self\'; style-src \'unsafe-inline\'">'
        '<title>Facebook original</title><style>html,body{margin:0}canvas{display:block}</style>'
        '<canvas id="c" width="1080" height="1920"></canvas>'
        '<script type="module" src="scene.mjs"></script></html>')
    (project / 'project.json').write_text(json.dumps(dict(fps=30, scenes=['film.html'], audio=[])))
    stamp={**capabilities(), 'manifest_sha256':sha(manifest),
                  'scene_sha256':sha(project / 'scene.mjs'), 'frame_count':len(frames),
                  'captions_stable':True, 'independent_qc_required':True}
    if plan.get('education'):stamp['education_scene_sha256']=sha(project/'education-scene.mjs')
    if plan.get('story'):stamp['story_scene_sha256']=sha(project/'story-scene.mjs')
    return page,stamp


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render(plan, cues, length, folder, state, progress):
    page, stamp = write_project(plan, cues, length, folder, state)
    output = folder / 'motlab_silent.mp4'
    def report(percent, stage, message):
        progress(40 + max(0, min(40, (percent - 82) * 6)), stage, message)
    render_canvas_with_motlab(page=page, output=output, duration=length,
        width=1080, height=1920, scene_dir=folder, progress=report)
    return output, stamp


def verify_evidence(folder, stamp):
    project = folder / 'motlab_project'
    if (not isinstance(stamp, dict) or any(stamp.get(k) != v for k, v in capabilities().items())
            or stamp.get('manifest_sha256') != sha(project / 'film.json')
            or stamp.get('scene_sha256') != sha(project / 'scene.mjs')
            or stamp.get('captions_stable') is not True):
        raise ValueError('Bukti render Motlab Facebook berubah atau belum lengkap.')
    manifest=json.loads((project/'film.json').read_text())
    if manifest.get('education') and stamp.get('education_scene_sha256')!=sha(project/'education-scene.mjs'):
        raise ValueError('Bukti render animasi edukasi berubah.')
    if manifest.get('story') and stamp.get('story_scene_sha256')!=sha(project/'story-scene.mjs'):
        raise ValueError('Bukti render cerita topik berubah.')
