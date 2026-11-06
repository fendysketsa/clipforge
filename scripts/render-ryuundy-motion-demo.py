#!/usr/bin/env python3
"""Render an original silent motion study using the same inserts as the clip worker."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from ryuundy_motion import build_motion_plan, motion_overlay_filter, prepare_motion_assets


def command(args, cwd):
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError(result.stderr[-2500:])
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/ryuundy-motion-demo-20261106.mp4')
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ryuundy-motion-demo-') as folder:
        work = Path(folder)
        (work / 'scene.svg').write_text('''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920">
<defs><linearGradient id="bg" x2="0.7" y2="1"><stop stop-color="#102f32"/><stop offset="1" stop-color="#061317"/></linearGradient></defs>
<rect width="1080" height="1920" fill="url(#bg)"/>
<g font-family="DejaVu Sans"><text x="70" y="90" font-size="28" letter-spacing="7" fill="#62d6bd">RYUUNDY</text>
<text x="70" y="145" font-size="44" font-weight="bold" fill="#f2ebda">Satu momen, satu makna.</text>
<text x="70" y="195" font-size="22" fill="#9cb3a9">STUDI GERAK / TANPA NARASI</text>
<ellipse cx="550" cy="1270" rx="390" ry="70" fill="#000" opacity=".25"/>
<path d="M120 1090 L875 1030 L1030 1310 L60 1390 Z" fill="#234547" stroke="#4e6962" stroke-width="3"/>
<g transform="translate(370 940) rotate(-7 180 200)">
<rect x="13" y="18" width="360" height="440" rx="28" fill="#000" opacity=".3"/>
<rect width="360" height="440" rx="28" fill="#eee5cc"/>
<rect x="24" y="25" width="312" height="386" rx="16" fill="#173436"/>
<circle cx="180" cy="48" r="7" fill="#76a396"/>
<path d="M60 130 H280 M60 168 H260 M60 206 H210" stroke="#e4cf92" stroke-width="12"/>
<rect x="60" y="285" width="225" height="54" rx="10" fill="#399e8c"/>
<text x="172" y="320" text-anchor="middle" font-size="22" fill="#eff5e5">SATU LANGKAH</text></g>
<text x="75" y="1725" font-size="20" fill="#9db7ad">Penanda bergerak di bawah menjaga bukti waktu sumber.</text>
<path d="M75 1822 H1005" stroke="#305652" stroke-width="3"/>
<text x="75" y="1890" font-size="19" fill="#718e86">Ilustrasi asli untuk uji visual. Tidak memakai klip kreator lain.</text></g></svg>''')
        source = work / 'source.mp4'
        command(['ffmpeg', '-v', 'error', '-y', '-threads', '1', '-loop', '1', '-framerate', '30',
                 '-i', str(work / 'scene.svg'), '-f', 'lavfi', '-i', 'color=c=0x43e4c1:s=36x36:r=30:d=18',
                 '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
                 '-filter_complex_threads', '1', '-filter_complex',
                 '[0:v][1:v]overlay=x=75+900*t/18:y=1804:shortest=1[v]',
                 '-map', '[v]', '-map', '2:a:0', '-t', '18', '-c:v', 'libx264', '-threads', '2',
                 '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(source)], work)
        text = [
            'Kenapa subtitle terasa sulit dibaca ketika kalimatnya terlalu panjang?',
            'Perhatikan satu momen ini sebelum mengambil keputusan berikutnya.',
            'Pisahkan subtitle menjadi dua baris sesuai akhir kalimat pembicara.',
            'Bagian gambar ini tetap diambil dari frame sumber yang sama.',
            'Hasilnya subtitle tetap utuh, lebih mudah dibaca, dan layar tidak terlalu penuh.',
        ]
        rows = [SimpleNamespace(start=a, end=b, text=t) for (a, b), t in zip(
            [(0., 3.), (3., 6.), (7., 10.), (12., 15.), (15., 18.)], text)]
        clip = SimpleNamespace(start=0., end=18., text=' '.join(text), title='Studi visual RYUUNDY')
        plans, cues = [], []
        for kind, quote in [('freeze_inset', text[1]), ('step_diagram', text[2]), ('cutout_stop_motion', text[3])]:
            manifest = {'review_status': 'source_checked', 'reviewed_by': 'authored_demo',
                        'clip_start': 0., 'kind': kind, 'quote': quote,
                        'region': [.33, .48, .36, .25]}
            plan = build_motion_plan(clip, rows, {'accent': 'cinematic_clean'}, manifest=manifest)
            if not plan['enabled']:
                raise RuntimeError('Demo cue failed: ' + plan['reason'])
            prepare_motion_assets(plan, source, work, kind, source_size=(1080, 1920),
                                  run_command=lambda cmd: command(cmd, work))
            plans.append(plan)
            cues.extend(plan['cues'])
        combined = {'cues': cues}
        (work / 'captions.ass').write_text(r'''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,DejaVu Sans,43,&H00F4F0E7,&H00F4F0E7,&H00121718,&H00121718,0,0,0,0,100,100,0,0,1,2,1,2,110,110,280,1
[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
Dialogue: 0,0:00:00.00,0:00:03.00,Default,,0,0,0,,Kenapa subtitle terasa sulit dibaca?\NKalimatnya terlalu panjang.
Dialogue: 0,0:00:03.00,0:00:06.00,Default,,0,0,0,,Perhatikan satu momen ini\Nsebelum mengambil keputusan berikutnya.
Dialogue: 0,0:00:07.00,0:00:10.00,Default,,0,0,0,,Pisahkan subtitle menjadi dua baris\Nsesuai akhir kalimat pembicara.
Dialogue: 0,0:00:12.00,0:00:15.00,Default,,0,0,0,,Bagian gambar ini tetap diambil\Ndari frame sumber yang sama.
Dialogue: 0,0:00:15.00,0:00:18.00,Default,,0,0,0,,Subtitle tetap utuh dan mudah dibaca.\NLayar tidak terlalu penuh.
''')
        chain = motion_overlay_filter(combined)
        command(['ffmpeg', '-v', 'error', '-y', '-threads', '1', '-filter_threads', '1',
                 '-i', str(source), '-vf', chain + ",subtitles=filename='captions.ass'",
                 '-map', '0:v:0', '-map', '0:a:0', '-t', '18', '-c:v', 'libx264', '-threads', '2',
                 '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'copy',
                 '-movflags', '+faststart', str(output)], work)
        for index, timestamp in enumerate((4.3, 8.7, 13.4)):
            command(['ffmpeg', '-v', 'error', '-y', '-ss', str(timestamp), '-i', str(output),
                     '-frames:v', '1', str(output.with_name(output.stem + f'-frame-{index}.png'))], work)
        audio_hashes = [command(['ffmpeg', '-v', 'error', '-i', str(p), '-map', '0:a:0',
                                '-f', 'hash', '-hash', 'sha256', '-'], work).strip() for p in (source, output)]
        probe = json.loads(command(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                                    '-of', 'json', str(output)], work))
        video = next(x for x in probe['streams'] if x['codec_type'] == 'video')
        review = {'video': str(output), 'duration': float(probe['format']['duration']),
                  'width': video['width'], 'height': video['height'], 'fps': video['avg_frame_rate'],
                  'audio_stream_preserved': audio_hashes[0] == audio_hashes[1],
                  'silent_visual_study': True, 'narration_produced': False,
                  'source': 'Original vector scene and authored example text; no external footage.',
                  'plans': plans, 'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}
        output.with_suffix('.json').write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({k: v for k, v in review.items() if k != 'plans'}))


if __name__ == '__main__':
    main()
