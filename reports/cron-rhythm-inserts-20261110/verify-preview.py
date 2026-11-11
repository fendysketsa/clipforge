"""Inspect encoded frames and speech alignment; do not publish the preview."""
import hashlib
import io
import json
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

folder=Path('reports/cron-rhythm-inserts-20261110')
before=json.loads(Path('reports/cron-short-presentation-20261110/source-before.json').read_text())
old=Path(before['path'])
new=folder/'preview/cron-rhythm-preview.mp4'
preview=json.loads((folder/'preview-verification.json').read_text())

probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries',
    'stream=codec_type,codec_name,width,height:format=duration','-of','json',str(new)],text=True))
video=next(row for row in probe['streams'] if row['codec_type']=='video')
assert (video['width'],video['height'],video['codec_name'])==(1080,1920,'h264')
assert any(row['codec_type']=='audio' for row in probe['streams'])
assert abs(float(probe['format']['duration'])-preview['retained_source_duration'])<.1

def audio(path):
    raw=subprocess.check_output(['ffmpeg','-v','error','-threads','1','-i',str(path),
        '-t',str(preview['retained_source_duration']),'-vn','-ac','1','-ar','2000','-f','f32le','-'])
    return np.frombuffer(raw,dtype=np.float32)

left,right=audio(old),audio(new)
length=min(len(left),len(right))
start,end=6000,min(length-250,56000)
scores=[]
for shift in range(-200,201):
    a,b=left[start:end],right[start+shift:end+shift]
    scores.append(float(np.corrcoef(a,b)[0,1]))
winner=int(np.nanargmax(scores));lag=(winner-200)/2000
assert abs(lag)<.08 and scores[winner]>.85,(lag,scores[winner])

canvas=Image.new('RGB',(810,1030),'#0b1715')
draw=ImageDraw.Draw(canvas)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',18)
for row,(label,path) in enumerate([('SEBELUM',old),('PRATINJAU CRON',new)]):
    y=row*515
    draw.text((12,y+7),label,font=font,fill='#b4f4de')
    for col,timestamp in enumerate((preview['rhythm_insert']['start']-.35,preview['rhythm_insert']['beats'][1]+.13,preview['rhythm_insert']['end']+.3)):
        data=subprocess.check_output(['ffmpeg','-v','error','-threads','1','-ss',str(timestamp),
            '-i',str(path),'-frames:v','1','-vf','scale=270:480','-threads','1',
            '-f','image2pipe','-vcodec','png','-'])
        canvas.paste(Image.open(io.BytesIO(data)).convert('RGB'),(col*270,y+35))
canvas.save(folder/'comparison.png')

assert hashlib.sha256(old.read_bytes()).hexdigest()==before['sha256']
assert old.stat().st_mtime_ns==before['mtime_ns']
record=dict(preview_only=True,upload_queued=False,original_unchanged=True,
    video=video,duration=float(probe['format']['duration']),source_audio_lag_seconds=lag,
    source_audio_correlation=round(scores[winner],5),caption_clock_unchanged=True,
    layout=preview['layout']['layout'],technical_render_qc=preview['render_quality_qc']['status'],
    publication_review_required=True,source_rights_verified=False,
    comparison=str(folder/'comparison.png'))
(folder/'encoded-verification.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
