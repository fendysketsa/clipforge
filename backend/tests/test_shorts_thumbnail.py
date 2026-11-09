import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw
import pytest

import shorts_thumbnail as thumb


TEXT = ('Nisa menyusun semua ini dari siang sampai malam. Bukan Nisa yang merusak keluarga ini. '
        'Tapi mungkin saya yang nggak pernah mau berubah. Ternyata bukan semua orang yang harus berubah.')


def test_curiosity_copy_preserves_negation_and_complete_words():
    options = thumb.headline_options({'text':TEXT})
    assert options[0]['headline'] == 'BUKAN NISA YANG MERUSAK KELUARGA'
    for row in options:
        assert 3 <= len(row['headline'].split()) <= 6
        assert thumb.words(row['headline'])[-1] not in thumb.DANGLING
        if 'merusak' in thumb.words(row['headline']):
            assert 'bukan' in thumb.words(row['headline'])
        assert all(word in thumb.words(row['evidence']) for word in thumb.words(row['headline']))


def test_attribution_cannot_be_trimmed_into_an_assertion():
    for row in thumb.headline_options({'text':'Menurut warga dia diduga mengambil uang keluarga itu.'}):
        if 'mengambil' in thumb.words(row['headline']):
            assert set(thumb.words(row['headline'])) & {'menurut','diduga'}


def test_photo_bounds_ignores_black_bands_and_small_header_text():
    image = Image.new('RGB',(540,960))
    draw = ImageDraw.Draw(image)
    draw.text((20,50),'SMALL HEADER',fill='white')
    for x in range(540):
        draw.line((x,340,x,630),fill=(70+x%140,90,120))
    bounds = thumb.photo_bounds(image)
    assert 300 <= bounds[1] <= 360
    assert 600 <= bounds[3] <= 660


@pytest.fixture
def video(tmp_path):
    path = tmp_path / 'clip.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=540x960:rate=8:duration=3',
        '-c:v','libx264','-threads','1','-pix_fmt','yuv420p',str(path)],check=True)
    return path


def test_real_pack_has_distinct_readable_variants_and_preserves_mp4(video):
    before = hashlib.sha256(video.read_bytes()).hexdigest()
    sidecar = {'text':TEXT,'duration':3,'output_duration_seconds':3}
    installed = thumb.install_pack(video,sidecar)
    assert installed['policy_version'] == thumb.VERSION
    assert hashlib.sha256(video.read_bytes()).hexdigest() == before
    manifest = json.loads(video.with_name('clip_thumbnail_ideas.json').read_text())
    assert len(manifest['variants']) == 3
    assert len({tuple(v['composition']['headline_zone']) for v in manifest['variants']}) == 3
    for row in manifest['variants']:
        image = video.parent / row['filename']
        assert Image.open(image).size == (1080,1920)
        assert image.stat().st_size <= 2*1024*1024
        assert len(row['composition']['headline_lines']) <= 2
        assert row['score'] == sum(row['score_breakdown'].values())
        assert row['composition']['headline_zone'][3] <= 1600
    winner = next(row for row in manifest['variants'] if row['id']==manifest['winner'])
    assert winner['filename']=='clip_thumb.jpg'
    assert 'HOOK: ' + winner['headline'] in video.with_name('clip_thumb.txt').read_text()


def test_staging_cannot_replace_a_thumbnail_after_transfer_starts(video):
    old = video.with_name('clip_thumb.jpg');old.write_bytes(b'original asset')
    result = thumb.install_pack(video,{'text':TEXT,'duration':3},may_publish=lambda:False)
    assert result is None and old.read_bytes()==b'original asset'
    assert not video.with_suffix('.json').exists()


def test_operator_preserves_already_transferred_or_confirmed_thumbnails():
    script = Path(__file__).resolve().parents[2]/'scripts/shorts-thumbnail-operator.py'
    spec=importlib.util.spec_from_file_location('shorts_thumb_operator_test',script)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    row=dict(source_job_id='job',clip_url='/outputs/job/clip.mp4',status='running',logs=[])
    assert module.transfer_not_started('job',row['clip_url'],[row])
    row['logs']=['Transfer thumbnail dimulai satu kali; menunggu konfirmasi']
    assert not module.transfer_not_started('job',row['clip_url'],[row])
    row['logs']=[];row['upload_confirmed']=True
    assert not module.transfer_not_started('job',row['clip_url'],[row])
