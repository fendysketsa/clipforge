"""Narration-timed Motlab canvas assembly using the same approved story assets."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

from remotion_story_renderer import RemotionRenderError, prepare_story_manifest, _browser_executable, _link_asset

RENDERER_DIR = Path(__file__).resolve().parent / "motlab"
MOTION_POLICY_VERSION = 1


def rendering_capabilities() -> dict:
    package = RENDERER_DIR / 'node_modules/@motlab/cli/package.json'
    try:
        installed = json.loads(package.read_text()).get('version') == '0.3.0'
    except (OSError, ValueError):
        installed = False
    return {'version':1, 'default_engine':os.environ.get('LONG_ANIMATE_RENDER_ENGINE', 'motlab'),
        'engines':['motlab', 'remotion', 'ffmpeg'], 'motlab_version':'0.3.0',
        'motlab_installed':installed, 'motion_policy_version':MOTION_POLICY_VERSION,
        'caption_timing':'measured_tts_frames', 'caption_plane':'outside_picture_transitions',
        'grounded_diagrams':True, 'existing_assets_reused':True,
        'render_failure_blocks_completion':True, 'untrusted_scene_code_executed':False}


def story_render_experiment(engine: str, width: int, height: int, captions: bool) -> dict:
    """Attach a stable rendering cohort to existing upload performance records."""
    recipe = {'engine':engine, 'motion_policy_version':MOTION_POLICY_VERSION,
        'width':width, 'height':height, 'fps':30, 'captions':captions,
        'planner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    if engine == 'motlab':
        recipe['canvas_sha256'] = hashlib.sha256((RENDERER_DIR / 'scene.mjs').read_bytes()).hexdigest()
    return {'experiment_id':'generated_story_motion_v1', 'variant':f'{engine}_motion_v1',
        'recipe_hash':hashlib.sha256(json.dumps(recipe,sort_keys=True).encode()).hexdigest(),
        'comparison_scope':'same_format_and_series',
        'measure_after_publish':['first_30_second_retention','average_view_duration','ctr','subscribers_gained'],
        'actual_performance_verified':False, 'view_or_subscriber_guarantee':False}


class MotlabRenderError(RuntimeError):
    pass


def require_motlab_runtime() -> str:
    """Fail before TTS/image production when the selected renderer is unavailable."""
    node = shutil.which('node')
    if not node or not (RENDERER_DIR / 'node_modules/@motlab/cli/package.json').is_file():
        raise MotlabRenderError('Runtime Motlab belum terpasang; rebuild backend melalui Compose standar.')
    check = subprocess.run([node, str(RENDERER_DIR / 'render.mjs'), '--check'],
        capture_output=True, text=True, timeout=15, check=False)
    if check.returncode:
        raise MotlabRenderError('Runtime Motlab belum siap: ' + (check.stderr or check.stdout)[-1000:])
    if not _browser_executable():
        raise MotlabRenderError('Chromium untuk Motlab belum tersedia di image backend.')
    return node


def grounded_diagram(shot: dict, cues: list[dict], fps: int) -> list[dict]:
    """Only animate an explicitly authored flow whose labels occur in narration."""
    labels = [part.strip() for part in re.split(r'\s*(?:→|->)\s*', shot['onScreenText'])]
    narration = shot['narration'].casefold()
    if (not 2 <= len(labels) <= 3 or any(not label or len(label) > 22 for label in labels)
            or re.search(r'\b(?:tidak|bukan|belum|jangan)\b', narration)):
        return []
    cursor, nodes = 0, []
    for index, label in enumerate(labels):
        match = re.search(r'(?<!\w)' + re.escape(label.casefold()) + r'(?!\w)', narration[cursor:])
        if not match:
            return []
        cursor += match.end()
        earliest = nodes[-1]['atFrame'] if nodes else shot['startFrame']
        at = next((cue['startFrame'] for cue in cues if
            earliest <= cue['startFrame'] < shot['startFrame'] + shot['bodyDurationInFrames']
            and re.search(r'(?<!\w)' + re.escape(label.casefold()) + r'(?!\w)', cue['text'].casefold())),
            shot['startFrame'] + min(shot['bodyDurationInFrames'] - 1, round(index * .65 * fps)))
        nodes.append({'label':label, 'atFrame':max(earliest, at)})
    return nodes


def build_motion_design(composition: dict) -> list[dict]:
    """Direct camera and reveals from scene roles and real caption boundaries."""
    width, height, fps = composition['width'], composition['height'], composition['fps']
    total = round(composition['durationSeconds'] * fps)
    if (not composition['shots'] or min(width, height) < 2 or width % 2 or height % 2
            or total < 1 or fps != 30):
        raise MotlabRenderError("Timeline atau ukuran canvas Motlab tidak valid.")
    plans, cursor = [], 0
    for index, shot in enumerate(composition['shots']):
        start, body = shot['startFrame'], shot['bodyDurationInFrames']
        if start != cursor or body < 1:
            raise MotlabRenderError("Batas frame shot tidak berurutan; sinkronisasi narasi ditahan.")
        cursor += body
        role = shot['narrativeRole']
        close = shot['framing'] in {'close_up', 'extreme_close_up'}
        reveal = next((cue['startFrame'] for cue in composition['captionCues']
                       if start + body * .35 <= cue['startFrame'] < start + body * .75),
                      start + round(body * .48))
        plans.append({
            'shotId': shot['id'], 'layout': 'editorial_split' if width > height
                and shot['onScreenText'] and index % 3 == 1 else 'cinematic',
            'camera': shot['cameraMotion'], 'maxZoom': 1.035 if close else 1.075,
            'revealFrame': reveal, 'settleFrames': min(round(.65 * fps), max(1, body // 5)),
            'accentColor': shot['motionDesign']['accentColor'],
            'quietEnding': role == 'payoff_conclusion',
            'transition': 'cross_dissolve' if shot.get('transitionInFrames', 0) else 'cut',
            'title': shot['onScreenText'], 'captionAnimation': 'none',
            'focusX': .34 if 'left' in shot['subjectPlacement'] else .66
                if 'right' in shot['subjectPlacement'] else .5,
            'diagram': grounded_diagram(shot, composition.get('wordCues') or composition['captionCues'], fps),
        })
    if cursor != total:
        raise MotlabRenderError("Durasi frame Motlab berbeda dari audio terukur.")
    return plans


def write_motlab_project(manifest_path: Path, project_dir: Path) -> Path:
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    composition = manifest['composition']
    composition['motlabMotion'] = build_motion_design(composition)
    project_dir.mkdir(parents=True, exist_ok=True)
    source_assets = Path(manifest['publicDir']) / 'assets'
    for shot in composition['shots']:
        name = shot['asset']
        if Path(name).name != name or not (source_assets / name).is_file():
            raise MotlabRenderError("Aset Motlab tidak tersedia di dalam proyek.")
        _link_asset(source_assets / name, project_dir / 'assets' / name)
    _link_asset(RENDERER_DIR / 'scene.mjs', project_dir / 'scene.mjs')
    (project_dir / 'film.json').write_text(json.dumps(composition, ensure_ascii=False, indent=2), encoding='utf-8')
    (project_dir / 'project.json').write_text(json.dumps({'fps':30, 'scenes':['film.html'], 'audio':[]}), encoding='utf-8')
    (project_dir / 'film.html').write_text(
        '<!doctype html><html lang="id"><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'self\' data: blob:; '
        'script-src \'self\'; style-src \'unsafe-inline\'; img-src \'self\' data: blob:">'
        '<title>RYUUNDY</title><style>html,body{margin:0;background:#090d16}canvas{display:block}</style>'
        f'<canvas id="c" width="{composition["width"]}" height="{composition["height"]}"></canvas>'
        '<script type="module" src="scene.mjs"></script></html>', encoding='utf-8')
    (project_dir / 'motion-policy.json').write_text(json.dumps({
        'version':MOTION_POLICY_VERSION, 'engine':'motlab_webcodecs', 'package_version':'0.3.0',
        'timeline_source':'measured_tts_frames', 'captions_outside_picture_transitions':True,
        'deterministic':True, 'caption_flicker_allowed':False,
        'motion_plan':composition['motlabMotion'],
        'source_manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    return project_dir / 'film.html'


def render_story_with_motlab(**kwargs: Any) -> tuple[Path, Path]:
    require_motlab_runtime()
    try:
        output, manifest_path = prepare_story_manifest(**kwargs)
        page = write_motlab_project(manifest_path, kwargs['scene_dir'] / 'motlab_project')
    except RemotionRenderError as exc:
        raise MotlabRenderError(str(exc)) from exc
    render_canvas_with_motlab(page=page, output=output, duration=kwargs['duration'],
        width=kwargs['width'], height=kwargs['height'], scene_dir=kwargs['scene_dir'],
        video_quality=kwargs['video_quality'], progress=kwargs.get('progress'))
    return output, page.parent / 'project.json'


def render_canvas_with_motlab(*, page: Path, output: Path, duration: float, width: int,
                             height: int, scene_dir: Path, video_quality='high', progress=None) -> Path:
    """Shared checked canvas export for story and Facebook production."""
    node = require_motlab_runtime()
    env = os.environ.copy()
    browser = _browser_executable()
    if browser:
        env['CHROME'] = browser
    env['MOTLAB_CACHE_DIR'] = str(scene_dir / 'motlab_cache')
    env['MOTLAB_QP'] = {'standard':'21', 'high':'18', 'max':'16'}.get(video_quality, '18')
    if progress:
        progress(82, 'render', 'Motlab merakit kamera dinamis, reveal visual, dan caption stabil')
    lines = []
    process = subprocess.Popen([node, str(RENDERER_DIR / 'render.mjs'), str(page.resolve()), str(output.resolve())],
        cwd=str(RENDERER_DIR), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding='utf-8', errors='replace', bufsize=1)
    try:
        for line in process.stdout:
            lines.append(line.strip())
            lines = lines[-40:]
            match = re.search(r'(\d+(?:\.\d+)?)%', line)
            if progress and match:
                value = min(100, max(0, float(match.group(1))))
                progress(82 + round(value * .06), 'render', f'Motlab merender frame {value:g}%')
            elif progress and line.startswith('MOTLAB_HEARTBEAT:'):
                seconds = line.partition(':')[2].strip()
                progress(82, 'render', f'Merender animasi canvas dan caption, {seconds} detik berjalan')
        code = process.wait()
    except BaseException:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        raise
    if code != 0 or not output.is_file() or output.stat().st_size == 0:
        raise MotlabRenderError('Render Motlab gagal: ' + '\n'.join(lines)[-2000:])
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
        'stream=width,height,codec_type:format=duration', '-of', 'json', str(output)],
        capture_output=True, text=True, timeout=30, check=False)
    try:
        info = json.loads(probe.stdout)
        video = next(row for row in info['streams'] if row['codec_type'] == 'video')
        seconds = float(info['format']['duration'])
        if (probe.returncode or not math.isfinite(seconds) or abs(seconds - duration) > 1 / 30 + .01
                or (video['width'], video['height']) != (width, height)):
            raise ValueError('geometry or duration mismatch')
    except (ValueError, KeyError, StopIteration) as exc:
        raise MotlabRenderError('Output Motlab belum cocok dengan ukuran dan durasi narasi.') from exc
    return output
