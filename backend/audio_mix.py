"""Prepare narration before branching it into an effect-ducking graph.

Loudnorm has lookahead. Running it immediately before asplit/sidechaincompress
can leave its last buffered speech unconsumed when the finite SFX stem ends.
Normalize to a complete PCM stem first, then read independent voice and key
inputs so a finite effect consumer cannot stop the narration's EOF flush.
"""
import math
from pathlib import Path
import subprocess
import wave


def normalize_narration(media,output,duration,*,ffmpeg='ffmpeg'):
    media,output=Path(media).resolve(),Path(output).resolve()
    if media==output or not math.isfinite(duration) or not 0<duration<=180:
        raise ValueError('Invalid narration normalization target or duration')
    output.parent.mkdir(parents=True,exist_ok=True)
    samples=round(duration*48000)
    subprocess.run([ffmpeg,'-v','error','-y','-threads','1','-i',str(media),'-map','0:a:0',
        '-af',f'aresample=48000:first_pts=0,loudnorm=I=-16:TP=-2:LRA=7,'
              f'aresample=48000,apad=whole_len={samples},atrim=end_sample={samples},asetpts=N/SR/TB',
        '-ar','48000','-c:a','pcm_s16le',str(output)],
        check=True,capture_output=True,timeout=90)
    with wave.open(str(output),'rb') as stream:
        if stream.getframerate()!=48000 or stream.getnframes()!=samples:
            raise ValueError('Normalized narration did not preserve the full sample timeline')
    return output
