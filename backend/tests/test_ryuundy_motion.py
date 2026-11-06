from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import pytest

import ryuundy_motion as motion


def fixture():
    texts = [
        'Kenapa subtitle terasa susah dibaca ketika kalimat panjang muncul di layar?',
        'Coba pisahkan subtitle menjadi dua baris dan atur jeda sesuai akhir kalimat pembicara.',
        'Hasilnya subtitle lebih mudah dibaca karena kalimat tetap utuh dan layar tidak terlalu penuh.',
    ]
    rows = [SimpleNamespace(start=a, end=b, text=t) for (a, b), t in zip(
        [(100., 104.), (105., 112.), (121., 132.)], texts)]
    clip = SimpleNamespace(start=100., end=132., title='Subtitle yang mudah dibaca', text=' '.join(texts))
    return clip, rows


def manifest(clip, rows, **changes):
    return dict(kind='cutout_stop_motion', review_status='source_checked',
                reviewed_by='test-reviewer', clip_start=clip.start,
                quote=rows[1].text, region=[.2, .2, .3, .4]) | changes


def test_practical_diagram_is_timed_to_exact_action_and_keeps_source_clock():
    clip, rows = fixture()
    plan = motion.build_motion_plan(clip, rows, {'accent': 'cinematic_clean'})
    assert plan['enabled']
    cue = plan['cues'][0]
    assert cue['kind'] == 'step_diagram'
    assert cue['start'] == 5 and cue['source_frame_at'] == 105
    assert cue['quote'] == rows[1].text
    assert cue['inserted_timeline_seconds'] == 0
    assert all(plan[key] for key in ('source_clock_unchanged', 'source_audio_unchanged', 'captions_clock_unchanged'))
    assert plan['rendered'] is False


@pytest.mark.parametrize('accent', sorted(motion.PROTECTED_ACCENTS))
def test_sensitive_and_dialogue_context_cannot_be_overridden_by_authored_motion(accent):
    clip, rows = fixture()
    plan = motion.build_motion_plan(clip, rows, {'accent': accent}, manifest=manifest(clip, rows))
    assert not plan['enabled']


def test_existing_evidence_and_religious_context_take_priority():
    clip, rows = fixture()
    for base in [{'content_lane': 'quran_hadith_reference'}, {'evidence_direction': {'beats': [{}]}}]:
        assert not motion.build_motion_plan(clip, rows, base)['enabled']


def test_game_reveal_gets_a_source_inset_while_plain_gameplay_gets_no_random_effect():
    clip = SimpleNamespace(start=0., end=30., title='Cerita Roblox',
                           text='Pemain berjalan. Ternyata pilihan jalan ini membawa kita ke pintu lain.')
    rows = [SimpleNamespace(start=5., end=9., text='Ternyata pilihan jalan ini membawa kita ke pintu lain.')]
    plan = motion.build_motion_plan(clip, rows, {})
    assert plan['enabled'] and plan['cues'][0]['kind'] == 'freeze_inset'
    clip.title = 'Satu pilihan yang mengubah hasil'
    assert motion.build_motion_plan(clip, rows, {})['enabled']
    clip.text = 'Pemain berjalan lalu terus bermain sampai selesai.'
    rows = [SimpleNamespace(start=5., end=9., text=clip.text)]
    assert not motion.build_motion_plan(clip, rows, {})['enabled']


@pytest.mark.parametrize('changes', [
    {'review_status': 'ai_suggested'}, {'reviewed_by': ''}, {'clip_start': 0},
    {'quote': 'Kalimat ini tidak pernah diucapkan pembicara sumber.'},
    {'region': [0., 0., 2., .3]}, {'region': [True, .2, .2, .3]},
    {'region': [.2, float('nan'), .2, .3]}, {'region': 'center'},
])
def test_unreviewed_unrelated_or_invalid_crop_is_not_renderable(changes):
    clip, rows = fixture()
    assert not motion.build_motion_plan(clip, rows, {}, manifest=manifest(clip, rows, **changes))['enabled']


def test_reviewed_cutout_is_a_crop_not_a_claim_of_human_segmentation():
    clip, rows = fixture()
    plan = motion.build_motion_plan(clip, rows, {}, manifest=manifest(clip, rows))
    assert plan['enabled'] and plan['cues'][0]['region_reviewed']
    assert not plan['human_segmentation_claimed']


def test_exact_quote_can_cross_timed_transcript_rows():
    _, rows = fixture()
    quote = rows[0].text + ' ' + rows[1].text
    assert motion.quote_window(quote, rows, 100, 132) == (0, 12)
    assert motion.quote_window(quote + ' Tambahan palsu.', rows, 100, 132) is None


def test_arbitrary_manifest_cannot_force_a_subtitle_diagram_onto_other_subjects():
    clip, rows = fixture()
    clip.text = 'Pemain memilih jalan dalam permainan lalu melihat hasilnya.'
    request = manifest(clip, rows, kind='step_diagram')
    assert not motion.build_motion_plan(clip, rows, {}, manifest=request)['enabled']


def test_malformed_manifest_does_not_fall_back_to_an_automatic_insert(tmp_path):
    clip, _ = fixture()
    path = tmp_path / 'motion.json'
    path.write_text('broken')
    assert motion.load_motion_manifest(path, clip) == {}


def test_asset_path_cannot_escape_render_directory():
    cue = {'asset': "../../outside.mp4',null;movie=x", 'start': 2, 'end': 4}
    assert motion.motion_overlay_filter({'cues': [cue]}) == ''


def test_source_quote_is_xml_text_rather_than_executable_markup():
    cue = {'kind': 'freeze_inset', 'quote': '<script> x & y </script> sumber utuh'}
    svg = motion.motion_frame_svg(cue, 'data:image/jpeg;base64,', .5)
    assert '<script>' not in svg
    assert '&lt;script&gt;' in svg and '&amp;' in svg


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='FFmpeg required for encoded-clock regression')
def test_encoded_overlay_is_finite_and_preserves_every_uncovered_source_frame_and_audio(tmp_path):
    def run(args):
        result = subprocess.run(args, cwd=tmp_path, capture_output=True, text=True, timeout=45)
        assert result.returncode == 0, result.stderr[-2000:]
        return result.stdout
    decoders = run(['ffmpeg', '-hide_banner', '-decoders'])
    if 'librsvg' not in decoders:
        pytest.skip('SVG decoder unavailable')
    source = tmp_path / 'source.mkv'
    run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=360x640:r=30:d=10',
         '-f', 'lavfi', '-i', 'sine=frequency=330:sample_rate=48000:duration=10',
         '-c:v', 'ffv1', '-threads', '1', '-c:a', 'pcm_s16le', str(source)])
    cue = {'kind': 'freeze_inset', 'start': 3., 'end': 5.8, 'source_frame_at': 3.,
           'quote': 'Contoh kalimat sumber untuk pemeriksaan waktu.', 'region': None}
    plan = {'enabled': True, 'cues': [cue], 'placement': {'width': 250, 'y': 30}}
    assets = motion.prepare_motion_assets(plan, source, tmp_path, 'clock', source_size=(360, 640))
    assert assets[0].parent.name == '.ryuundy-motion'
    assert not list(tmp_path.glob('*.mp4'))  # an insert must never become an upload candidate
    output = tmp_path / 'result.mkv'
    # No output-side duration cap: a finite secondary movie must return the source EOF.
    run(['ffmpeg', '-v', 'error', '-y', '-filter_threads', '1', '-i', str(source),
         '-vf', motion.motion_overlay_filter(plan), '-map', '0:v:0', '-map', '0:a:0',
         '-c:v', 'ffv1', '-threads', '1', '-pix_fmt', 'yuv420p', '-c:a', 'copy', str(output)])
    def frames(path):
        text = run(['ffmpeg', '-v', 'error', '-i', str(path), '-an', '-vf', 'crop=360:210:0:430',
                    '-f', 'framemd5', '-'])
        return [row.split(',')[-1].strip() for row in text.splitlines() if not row.startswith('#')]
    original, rendered = frames(source), frames(output)
    assert len(rendered) == len(original) == 300
    assert rendered == original
    def audio(path):
        return run(['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:a:0', '-f', 'hash', '-'])
    assert audio(source) == audio(output)
