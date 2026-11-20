from pathlib import Path
import os,json,subprocess,hashlib
os.environ.update(IMAGEIO_FFMPEG_EXE='/usr/bin/ffmpeg',FENDY_CLIPPER_CPU_THREADS_PER_JOB='2',SHORTS_BACKGROUND_MUSIC_ENABLED='false',SHORTS_ALLOW_THIRD_PARTY_MUSIC='false')
import clipper
import cron_long_strategy
from llm import AIConfig
root=Path('/www/wwwroot/clipper/clipforge/reports/long-compilation-fallback-20261115')
source=root/'synthetic-source.mp4'
subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=0x284452:s=640x360:r=6:d=300',
 '-f','lavfi','-i','sine=frequency=330:sample_rate=48000:duration=300',
 '-vf',"drawbox=x=35:y=45:w=565:h=260:color=0x8dadbf:t=3,drawtext=text='UJI KOMPILASI SUMBER ASLI':fontsize=22:fontcolor=white:x=(w-tw)/2:y=100,drawtext=text='%{pts\\:hms}':fontsize=26:fontcolor=white:x=(w-tw)/2:y=175",
 '-c:v','libx264','-preset','ultrafast','-crf','25','-threads','2','-pix_fmt','yuv420p','-c:a','aac','-b:a','64k',str(source)],check=True,timeout=120)
texts=['Pemain membuka pintu pertama dan menemukan ruangan kosong.',
       'Di lantai berikutnya pemain berhasil menemukan kunci biru.',
       'Temannya menunjukkan jalan menuju taman yang lebih terang.',
       'Keduanya memutuskan beristirahat di rumah dekat jembatan.']
transcript=[clipper.TranscriptSegment(i*80,i*80+60,text) for i,text in enumerate(texts)]
candidates=[clipper.ClipCandidate(index=i+1,start=row.start,end=row.end,duration=60,score=85,
 title=f'Momen sumber {i+1}',reason='Momen uji yang berdiri sendiri',text=row.text,boundary_quality='utuh',key_point_score=75)
 for i,row in enumerate(transcript)]
before=hashlib.sha256(source.read_bytes()).hexdigest()
output=clipper.export_compilation(source,candidates,transcript,root/'rendered',True,'center',
 clipper.CaptionStyle(),AIConfig(enabled=False),'auto',[],'standard',cron_long_strategy_required=True,short_anchor_ranges=[(0,25)])
sidecar=json.loads(output.with_suffix('.json').read_text())
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(output)]))
assert sidecar['long_format']=='compilation'
assert sidecar['cron_long_story_review']['passed'] is False
assert sidecar['cron_long_compilation_review']['passed'] is True
assert cron_long_strategy.long_evidence_issue(sidecar,[(0,25)]) is None
assert sidecar['story_director']['quality_gate_passed'] is False
assert 239<=float(probe['format']['duration'])<=241
assert hashlib.sha256(source.read_bytes()).hexdigest()==before
video=next(s for s in probe['streams'] if s['codec_type']=='video')
assert (video['width'],video['height'])==(1920,1080)
subprocess.run(['ffmpeg','-v','error','-xerror','-threads','1','-i',str(output),'-map','0:v:0','-map','0:a:0','-f','null','-'],check=True,timeout=240)
subprocess.run(['ffmpeg','-v','error','-y','-ss','80','-i',str(output),'-frames:v','1',str(root/'compiled-frame.png')],check=True)
result={'fixture_only':True,'full_export_pipeline':True,'output':str(output.relative_to(root)),
 'duration':probe['format']['duration'],'resolution':f"{video['width']}x{video['height']}",
 'source_sha256_preserved':True,'full_media_decode_passed':True,'long_format':sidecar['long_format'],
 'story_review_passed':False,'compilation_review':sidecar['cron_long_compilation_review'],
 'independent_publication_qc_not_granted':True}
(root/'render-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False))
