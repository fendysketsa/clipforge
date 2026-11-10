"""Authored calibration scene; not footage of a person screaming, never upload."""
from pathlib import Path
from types import SimpleNamespace as NS
import hashlib,json,subprocess,wave
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import cron_director_effects as fx

folder=Path(__file__).resolve().parent
rate=16000;t=np.arange(rate*6)/rate
amp=np.full(len(t),.045);amp[(t>=2.2)&(t<2.68)]=.48
samples=amp*(np.sin(2*np.pi*190*t)+.35*np.sin(2*np.pi*380*t))
with wave.open(str(folder/'calibration.wav'),'wb') as f:
 f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate);f.writeframes((samples*32767).astype('<i2').tobytes())
font='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
paths=[];audits=[]
for index,(kind,title) in enumerate(zip(fx.MOODS['shout'],['GARIS REAKSI','SINAR KOMIK','CINCIN TEKANAN'])):
 im=Image.new('RGB',(360,640));d=ImageDraw.Draw(im)
 for y in range(640):d.line((0,y,360,y),fill=(12+int(y/70),25+int(y/50),31+int(y/45)))
 d.text((180,48),title,font=ImageFont.truetype(font,21),anchor='mm',fill='#d9fff1')
 d.text((180,85),'DEMO KALIBRASI AUDIO',font=ImageFont.truetype(font,14),anchor='mm',fill='#83b6ad')
 # A deliberately illustrated avatar, with no borrowed footage or identity.
 d.rounded_rectangle((93,291,267,506),radius=48,fill='#315a66',outline='#6da3b3',width=2)
 d.rounded_rectangle((127,173,233,310),radius=43,fill='#e5b79c')
 d.arc((120,147,242,250),180,360,fill='#10222c',width=30)
 d.ellipse((151,218,157,225),fill='#17272f');d.ellipse((204,218,210,225),fill='#17272f')
 d.arc((165,231,194,255),0,180,fill='#6e493a',width=3)
 d.text((180,551),'BUKAN TERIAKAN ORANG',font=ImageFont.truetype(font,14),anchor='mm',fill='#c2d0d3')
 d.text((180,578),'Efek hanya 0,62 detik',font=ImageFont.truetype(font,13),anchor='mm',fill='#8fb0b3')
 bg=folder/f'background-{index}.png';im.save(bg)
 source=folder/f'variant-{index}.mp4'
 subprocess.run(['ffmpeg','-v','error','-y','-loop','1','-i',str(bg),'-i',str(folder/'calibration.wav'),'-t','6','-r','30','-c:v','libx264','-preset','ultrafast','-threads','1','-pix_fmt','yuv420p','-c:a','aac',str(source)],check=True)
 c=NS(start=0.,end=6.,text='Awas!',score=90)
 rows=[NS(start=2.1,end=2.9,text='Awas!')]
 before=fx._probe(source)
 def audiohash():return subprocess.check_output(['ffmpeg','-v','error','-i',str(source),'-map','0:a','-c:a','copy','-f','md5','-']).decode().strip()
 audio_before=audiohash()
 analysis=fx.analyze_reactions(source,c,rows,enabled=True)
 assert analysis['events'],analysis
 plan=fx.build_plan(c,rows,enabled=True,audio_reactions=analysis)
 # Demonstrate the renderer's three possible poses, not three cues on one clip.
 plan['cues'][0]['kind']=kind
 fx.render_effects(source,plan,preset='fast',threads=1)
 assert fx._probe(source)==before and audiohash()==audio_before
 audits.append(dict(synthetic_calibration=True,never_upload=True,plan=plan,audio_packets_unchanged=True,geometry_clock_unchanged=True))
 paths.append(source)
cmd=['ffmpeg','-v','error','-y']
for source in paths:cmd+=['-i',str(source)]
cmd+=['-filter_complex_threads','1','-filter_complex','[0:v][1:v][2:v]hstack=inputs=3[v]','-map','[v]','-map','0:a','-c:v','libx264','-preset','fast','-crf','18','-threads','2','-c:a','copy','-movflags','+faststart',str(folder/'reaction-variants-demo.mp4')]
subprocess.run(cmd,check=True)
(folder/'demo-verification.json').write_text(json.dumps(dict(synthetic_scene=True,real_scream_detected=False,preview_only=True,upload_queued=False,variants=audits),indent=2)+'\n')
peak=audits[0]['plan']['cues'][0]['start']+.20
subprocess.run(['ffmpeg','-v','error','-y','-ss',str(peak),'-i',str(folder/'reaction-variants-demo.mp4'),'-frames:v','1',str(folder/'reaction-variants.png')],check=True)
print(json.dumps({'demo':str(folder/'reaction-variants-demo.mp4'),'frame':str(folder/'reaction-variants.png'),'all_clock_and_audio_checks_passed':True}))
