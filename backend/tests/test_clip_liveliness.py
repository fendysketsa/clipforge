from pathlib import Path
from types import SimpleNamespace as NS
import hashlib
import subprocess

import pytest

import clip_liveliness as live
import cron_director_effects as fx


def clip(text='Wah astaga, ternyata berhasil! Lari cepat lalu selesai.', duration=12, start=100):
    return NS(start=start, end=start + duration, text=text, score=90)


def rows(c):
    return [
        NS(start=c.start + 1, end=c.start + 3, text='Wah astaga, ternyata berhasil!'),
        NS(start=c.start + 5, end=c.start + 7, text='Lari cepat lalu selesai.'),
    ]


def test_default_manual_plan_is_completely_inert():
    c = clip()
    plan = live.build_plan(c, rows(c))
    assert not plan['enabled'] and not plan['cues'] and not plan['rendered']
    assert plan['reason'] == 'opt_in_disabled'
    assert plan['source_clock_unchanged'] and plan['audio_unchanged']
    assert plan['inserted_timeline_seconds'] == 0


def test_opt_in_uses_timed_source_dialogue_and_stays_inside_clip():
    c = clip()
    plan = live.build_plan(c, rows(c), enabled=True)
    assert plan['enabled'] and 1 <= plan['cue_count'] <= 2
    assert {cue['kind'] for cue in plan['cues']} <= set(live.KINDS)
    for cue in plan['cues']:
        assert 0 <= cue['start'] < cue['end'] < (c.end - c.start)
        assert cue['quote'] in c.text
        assert 0 <= cue['box'][0] and cue['box'][0] + cue['box'][2] <= 1
        assert 0 <= cue['box'][1] and cue['box'][1] + cue['box'][3] <= 1


@pytest.mark.parametrize('text', [
    'Ayat ini dibacakan perlahan.',
    'Keluarga berduka atas korban tragedi.',
    'Tuduhan korupsi harus diperiksa.',
])
def test_sensitive_context_never_gets_optional_accents(text):
    c = clip(text)
    plan = live.build_plan(c, rows(c), enabled=True)
    assert plan['reason'] == 'protected_or_sensitive_context'
    assert not plan['cues']


def test_protected_and_complex_layouts_are_skipped():
    c = clip()
    assert not live.build_plan(c, rows(c), enabled=True, protected=True)['cues']
    for key in ('evidence', 'social_card', 'reaction_avatar', 'multi_split'):
        plan = live.build_plan(c, rows(c), enabled=True, layout={key: True})
        assert not plan['cues'] and plan['reason'] == 'protected_complex_layout'


def test_no_grounded_dialogue_produces_no_accent():
    c = clip('Kita sedang berada di halaman rumah dengan suasana tenang.')
    plan = live.build_plan(c, rows(c), enabled=True)
    assert not plan['cues'] and plan['reason'] == 'no_grounded_dialogue_cue'


def test_plan_is_deterministic_and_varies_between_clips():
    c = clip()
    a = live.build_plan(c, rows(c), enabled=True, seed='job-1')
    assert a == live.build_plan(c, rows(c), enabled=True, seed='job-1')
    variants = {
        (plan['cues'][0]['kind'], plan['cues'][0]['variation'])
        for plan in (live.build_plan(c, rows(c), enabled=True, seed=str(i)) for i in range(12))
    }
    assert len(variants) >= 2


@pytest.mark.parametrize('kind', live.KINDS)
def test_accent_frame_has_transparent_entry_and_visible_middle(kind):
    first = live.accent_frame(kind, 160, 0, (255, 220, 120), 2)
    middle = live.accent_frame(kind, 160, .5, (255, 220, 120), 2)
    assert first.mode == middle.mode == 'RGBA'
    assert first.getpixel((0, 0))[3] == 0
    assert max(middle.getchannel('A').getdata()) > 20


def _synthetic_video(path: Path, seconds=8):
    subprocess.run([
        'ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
        f'testsrc=size=1080x1920:rate=24:duration={seconds}',
        '-f', 'lavfi', '-i', f'sine=frequency=440:duration={seconds}',
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '32', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-shortest', str(path),
    ], check=True, capture_output=True)


@pytest.mark.skipif(not Path('/usr/bin/ffmpeg').exists(), reason='ffmpeg required')
def test_optional_render_preserves_clock_geometry_and_audio(tmp_path):
    video = tmp_path / 'source.mp4'
    _synthetic_video(video)
    before = fx._probe(video)
    audio_before = hashlib.sha256(subprocess.run(
        ['ffmpeg', '-v', 'error', '-i', str(video), '-map', '0:a', '-c', 'copy', '-f', 'md5', '-'],
        check=True, capture_output=True, text=True).stdout.encode()).hexdigest()

    inert = live.build_plan(clip(), rows(clip()))
    assert live.render_overlays(video, inert) is inert

    plan = live.build_plan(clip(), rows(clip()), enabled=True, seed='render-test')
    result = live.render_overlays(video, plan, threads=1)
    assert result['rendered'] and result['verification'] == 'duration_frame_count_and_geometry_preserved'
    after = fx._probe(video)
    assert abs(after['duration'] - before['duration']) <= max(.05, 1.1 / before['fps'])
    assert after['frames'] == before['frames']
    assert (after['width'], after['height']) == (before['width'], before['height'])
    audio_after = hashlib.sha256(subprocess.run(
        ['ffmpeg', '-v', 'error', '-i', str(video), '-map', '0:a', '-c', 'copy', '-f', 'md5', '-'],
        check=True, capture_output=True, text=True).stdout.encode()).hexdigest()
    assert audio_after == audio_before
    assert not list((tmp_path / '.clip-liveliness').glob('*.mkv'))
