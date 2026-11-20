"""Review-only revisions of already rendered video with dated source context.

Publication metadata proves publication time, never recording time or another
person's reaction. Keep original pictures, speech, watermark, and source clock.
This module never uploads or changes an existing remote post.
"""
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import subprocess
from urllib.parse import parse_qs,urlparse
import wave
from zoneinfo import ZoneInfo

import numpy as np
from audio_mix import normalize_narration

MONTHS=('Januari','Februari','Maret','April','Mei','Juni','Juli','Agustus',
        'September','Oktober','November','Desember')
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_publication(path,expected_sha256,expected_channel_id):
    if sha(path)!=expected_sha256:
        raise ValueError('Primary source proof changed')
    rows=json.loads(Path(path).read_text())
    source=next((r for r in rows if r.get('key')=='official-statement'),None)
    if not source or source.get('channel_id')!=expected_channel_id:
        raise ValueError('Primary source channel does not match')
    url=urlparse(source['source_url'])
    if (url.scheme!='https' or url.hostname!='www.youtube.com' or url.username or url.password
            or url.path!='/watch' or parse_qs(url.query).get('v')!=[source.get('video_id')]):
        raise ValueError('Primary source video identity does not match')
    timestamp=datetime.fromisoformat(source['publish_timestamp'])
    checked=datetime.fromisoformat(source['checked_at'])
    if timestamp.tzinfo is None or checked.tzinfo is None or timestamp>checked:
        raise ValueError('Publication timestamp is not independently dated')
    local=timestamp.astimezone(ZoneInfo('Asia/Jakarta'))
    return dict(source_url=source['source_url'],channel_id=source['channel_id'],
        publisher=source['author'],title=source['title'],checked_at=source['checked_at'],
        published_at=local.isoformat(),date_label=f'{local.day} {MONTHS[local.month-1]} {local.year}',
        date_basis='video_publication',recording_date=None,facts_verified=False,
        reaction_verified=False,primary_metadata_sha256=expected_sha256)


def accents(path,duration,start):
    if (not all(math.isfinite(t) for t in (duration,start)) or not 0<duration<=180
            or not 0<=start<duration-.5):
        raise ValueError('Accent is outside the source timeline')
    rate=48000;samples=np.zeros(math.ceil(duration*rate),dtype=np.float64)
    # One short attention accent, without a fake scream/reaction or copied audio.
    t=np.arange(int(.32*rate))/rate
    attack=np.minimum(1,t/.008);release=np.exp(-12*t)
    pulse=(np.sin(2*np.pi*(260*t+1900*t*t))+.45*np.sin(2*np.pi*115*t))*attack*release
    pulse/=max(1e-9,float(np.max(np.abs(pulse))))
    pulse*=10**(-20/20)
    offset=int(start*rate);samples[offset:offset+len(pulse)]+=pulse
    with wave.open(str(path),'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(rate)
        stream.writeframes((samples*32767).astype('<i2').tobytes())
    return dict(kind='authored_information_accent',start_seconds=start,duration_seconds=.32,
        peak_dbfs=-20,sample_rate=rate,third_party_audio=False,ducked_under_voice=True,
        timeline_inserted_seconds=0,sha256=sha(path))


def overlay(output,source,start,end,*,show_reaction_warning=True):
    """Use only the reserved top/bottom bars of a 1080x1920 source canvas."""
    if not 0<=start<end or end-start<5:
        raise ValueError('Dated source context needs at least five readable seconds')
    output.mkdir(parents=True,exist_ok=True)
    enabled=f"enable='between(t,{start:.3f},{end:.3f})'"
    filters=[f'drawbox=x=55:y=26:w=860:h=230:color=0x0C1C2B@0.98:t=fill:{enabled}',
        f'drawbox=x=55:y=26:w=7:h=230:color=0xFFE18B:t=fill:{enabled}',
        'drawbox=x=55:y=26:w=860:h=230:color=0xFFE18B:t=4:'
        f"enable='between(t,{start:.3f},{start+.28:.3f})'"]
    rows=[('VIDEO RUJUKAN | TANGGAL PUBLIKASI',27,90,47,'0x7FD7CF',enabled),
          (source['date_label'].upper(),60,90,93,'0xFFE18B',enabled),
          (source['publisher']+' | kanal YouTube',24,90,163,'white',enabled),
          (source['source_url'].removeprefix('https://www.'),21,90,197,'0xA8C0D4',enabled),
          ('Tanggal rekaman tidak disebutkan.',22,90,228,'0xC2CED9',enabled)]
    if show_reaction_warning:
        filters.extend(['drawbox=x=55:y=1635:w=860:h=150:color=0x0C1C2B@0.98:t=fill',
                        'drawbox=x=55:y=1635:w=5:h=150:color=0xD9AA60:t=fill'])
        rows.extend([('OPINI PEMBICARA',26,90,1656,'0xFFE18B',''),
                     ('Reaksi DPR yang disebut pembicara',29,90,1700,'white',''),
                     ('belum diverifikasi dalam revisi ini.',29,90,1740,'white','')])
    for index,(text,size,x,y,color,active) in enumerate(rows):
        name=f'context_{index}.txt';(output/name).write_text(text)
        filters.append(f"drawtext=fontfile={FONT}:textfile='{name}':expansion=none:"
                       f'fontcolor={color}:fontsize={size}:x={x}:y={y}'+(':'+active if active else ''))
    return ','.join(filters)


def check_reserved_bars(media,start,duration,end=None,*,replace_editorial_header=False):
    """Refuse to put a card on faces, source graphics, or existing subtitles."""
    graph=('fps=2,scale=540:960,format=gray,split[t][b];'
           '[t]crop=430:115:27:13[top];[b]crop=430:75:27:817[bottom];'
           '[top][bottom]vstack')
    raw=subprocess.check_output(['ffmpeg','-v','error','-threads','1','-i',str(media),
        '-filter_complex_threads','1','-filter_complex',graph,'-threads','1','-f','rawvideo','-'],timeout=90)
    frames=np.frombuffer(raw,dtype=np.uint8).reshape(-1,190,430)
    if not len(frames):raise ValueError('No source frames available for placement verification')
    for index,frame in enumerate(frames):
        at=index/2
        for name,area in [('top',frame[:115]),('bottom',frame[115:])]:
            if name=='top' and not start<=at<=(duration if end is None else end):
                continue
            # An explicitly reviewed existing editorial heading may be
            # replaced in its black bar; source pictures and captions may not.
            minimum=.85 if name=='top' and replace_editorial_header else .95
            if float(np.mean(area<34))<minimum:
                raise ValueError(f'No empty {name} bar at {at:.2f}s; choose a reviewed placement')


def render(media,output,source,*,start,end,replace_editorial_header=False):
    media=Path(media).resolve();output=Path(output).resolve()
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(media)]))
    duration=float(probe['format']['duration'])
    if not 5<=duration<=180 or not 0<=start<end<=duration:
        raise ValueError('Invalid review timeline')
    if not all(any(s['codec_type']==kind for s in probe['streams']) for kind in ('video','audio')):
        raise ValueError('Missing original video or speech')
    video=next(s for s in probe['streams'] if s['codec_type']=='video')
    if abs(video['width']/video['height']-9/16)>.02:
        raise ValueError('Review placement requires the existing portrait canvas')
    check_reserved_bars(media,start,duration,end,replace_editorial_header=replace_editorial_header)
    vf=overlay(output,source,start,end)
    narration=normalize_narration(media,output/'context-voice.wav',duration)
    sfx=output/'context-accent.wav';sound=accents(sfx,duration,start)
    target=output/'gibran-context-review.mp4'
    temporary=output/'.gibran-context-review.rendering.mp4'
    graph=(f'[0:v]fps=30,scale=1080:1920,setsar=1,{vf}[v];'
        '[1:a]anull[voice];'
        '[2:a][3:a]sidechaincompress=threshold=0.12:ratio=3:attack=5:release=120[accent];'
        '[voice][accent]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,'
        'alimiter=limit=0.84:level=false[a]')
    subprocess.run(['ffmpeg','-v','error','-y','-filter_complex_threads','1','-threads','1',
        '-i',str(media),'-i',str(narration),'-i',str(sfx),'-i',str(narration),
        '-filter_complex',graph,'-map','[v]','-map','[a]',
        '-c:v','libx264','-preset','fast','-crf','20','-threads','2','-pix_fmt','yuv420p',
        '-c:a','aac','-b:a','160k','-ar','48000','-t',f'{duration:.3f}',
        '-movflags','+faststart',str(temporary)],
        cwd=output,check=True,capture_output=True,timeout=240)
    subprocess.run(['ffmpeg','-v','error','-xerror','-threads','1','-i',str(temporary),'-f','null','-'],
        check=True,capture_output=True,timeout=90)
    temporary.replace(target)
    sidecar=dict(schema_version=1,source_media_sha256=sha(media),media_sha256=sha(target),
        source=source,source_duration_seconds=duration,source_clock_changed=False,
        original_watermark_preserved=True,overlay=dict(start_seconds=start,end_seconds=end,
        label='TANGGAL PUBLIKASI VIDEO',flashes=False,enter_accent_seconds=.28,
        placement='reserved_black_bars',replaced_prior_editorial_header=replace_editorial_header),sound=sound,
        manual_publication_review=True,upload_allowed=False,qc_decision='HOLD',
        title='Gibran dan RUU Perampasan Aset: konteks tanggal pernyataan',
        limitations=['Publication time is not recording time.',
                     'This statement does not establish the claimed reaction of DPR.',
                     'Retrieved published copy is not a lossless camera original.',
                     'Existing remote posts were not changed.'])
    target.with_suffix('.json').write_text(json.dumps(sidecar,ensure_ascii=False,indent=2))
    return target
