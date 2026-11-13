"""Validate the encoded watermark, including alpha and complete timeline."""
import json
import shutil
import subprocess

from PIL import Image, ImageChops, ImageStat
import pytest

from channel_branding import WATERMARK_ASSET, watermark_filter, watermark_size


@pytest.mark.parametrize('mode,width,height', [
    ('vertical_short', 1080, 1920), ('landscape_compilation', 1920, 1080),
])
def test_encoded_emblem_is_transparent_stable_and_does_not_truncate_video(tmp_path, mode, width, height):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        pytest.skip('FFmpeg unavailable')
    video = tmp_path / 'watermarked.mp4'
    subprocess.run([
        ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
        '-f', 'lavfi', '-i', f'color=c=0x303030:s={width}x{height}:r=5:d=1.4',
        '-vf', watermark_filter(mode), '-an', '-c:v', 'libx264',
        '-preset', 'ultrafast', '-crf', '0', '-pix_fmt', 'yuv420p', str(video),
    ], check=True, timeout=30, capture_output=True)
    probe = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_entries', 'stream=nb_frames',
        '-show_entries', 'format=duration', '-of', 'json', str(video),
    ], timeout=10))
    assert float(probe['format']['duration']) == pytest.approx(1.4, abs=.01)
    assert int(probe['streams'][0]['nb_frames']) == 7
    raw = subprocess.check_output([
        ffmpeg, '-v', 'error', '-i', str(video), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-',
    ], timeout=15)
    stride = width * height * 3
    first = Image.frombytes('RGB', (width, height), raw[:stride])
    last = Image.frombytes('RGB', (width, height), raw[-stride:])
    assert ImageChops.difference(first, last).getbbox() is None
    size = watermark_size(mode)
    x, y = (width - size) // 2, round((height - size) * .46)
    background = first.getpixel((0, 0))
    expected = Image.new('RGB', first.size, background)
    changed = ImageChops.difference(first, expected).getbbox()
    assert changed is not None
    assert x - 2 <= changed[0] < changed[2] <= x + size + 2
    assert y - 2 <= changed[1] < changed[3] <= y + size + 2
    # Ivory ink must brighten the picture. A premultiplied SVG rendered as
    # straight alpha darkens this region instead, producing a muddy stamp.
    mark = first.crop((x, y, x + size, y + size))
    assert sum(ImageStat.Stat(mark).mean) > sum(background) + 3
    # The square surrounding the circular emblem stays transparent.
    assert first.getpixel((x + 3, y + 3)) == background


def test_local_asset_keeps_real_monogram_and_has_no_animated_or_remote_dependencies():
    source = WATERMARK_ASSET.read_text()
    assert 'data:image/jpeg;base64,' in source
    assert 'RYUUNDY' in source
    assert '<animate' not in source and '<script' not in source
    assert 'https://yt3.' not in source
