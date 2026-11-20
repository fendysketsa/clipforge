"""Reproducible, original vector-film demo; no stock, paid generation or upload."""
import argparse
import json
from pathlib import Path
import re
import subprocess
from types import SimpleNamespace as NS

from motlab_story_renderer import render_story_with_motlab


def svg(width, height, palette):
    w,h=width,height
    blue,gold=palette
    houses=''.join(f'<g transform="translate({w*(.61+i*.10)} {h*.64})"><rect width="{w*.08}" height="{h*.13}" rx="5" fill="#182b48"/><path d="M {-w*.01} 0 L {w*.04} {-h*.055} L {w*.09} 0" fill="#415574"/><rect x="{w*.027}" y="{h*.035}" width="{w*.023}" height="{h*.04}" fill="{gold}"/></g>' for i in range(3))
    stars=''.join(f'<circle cx="{w*(.08+i*.073)}" cy="{h*(.08+(i%4)*.034)}" r="{w*.0022}" fill="#cfe6ff" opacity=".65"/>' for i in range(12))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">
    <defs><linearGradient id="sky" x2=".8" y2="1"><stop stop-color="#0a142b"/><stop offset="1" stop-color="#273c59"/></linearGradient><linearGradient id="water" x2="1" y2="1"><stop stop-color="{blue}"/><stop offset="1" stop-color="#134665"/></linearGradient></defs>
    <rect width="{w}" height="{h}" fill="url(#sky)"/>{stars}
    <circle cx="{w*.78}" cy="{h*.19}" r="{w*.065}" fill="#e8dcb6"/>
    <path d="M 0 {h*.46} L {w*.14} {h*.3} L {w*.37} {h*.5} L {w*.62} {h*.34} L {w} {h*.5} V {h} H 0" fill="#1b3446"/>
    <path d="M 0 {h*.59} Q {w*.23} {h*.47} {w*.45} {h*.62} T {w} {h*.6} V {h} H 0" fill="#1b4a48"/>
    <path d="M {-w*.1} {h*.68} Q {w*.2} {h*.48} {w*.44} {h*.67} T {w*.75} {h*1.1}" fill="none" stroke="url(#water)" stroke-width="{w*.29}"/>
    <path d="M {-w*.1} {h*.68} Q {w*.2} {h*.48} {w*.44} {h*.67} T {w*.75} {h*1.1}" fill="none" stroke="#b1ecff" opacity=".32" stroke-width="{w*.015}" stroke-dasharray="{w*.04} {w*.025}"/>
    <g transform="translate({w*.39} {h*.64})"><circle r="{w*.105}" fill="#0c2030" stroke="{gold}" stroke-width="{w*.012}"/>
    <path d="M {-w*.1} 0 H {w*.1} M 0 {-w*.1} V {w*.1} M {-w*.07} {-w*.07} L {w*.07} {w*.07} M {-w*.07} {w*.07} L {w*.07} {-w*.07}" stroke="{gold}" stroke-width="{w*.009}"/>
    <circle r="{w*.026}" fill="{gold}"/></g>{houses}
    <path d="M {w*.48} {h*.65} Q {w*.6} {h*.47} {w*.72} {h*.66}" fill="none" stroke="{gold}" stroke-width="{w*.004}" stroke-dasharray="{w*.009} {w*.01}"/>
    <path d="M 0 {h*.88} Q {w*.25} {h*.79} {w*.5} {h*.93} T {w} {h*.88} V {h} H 0" fill="#0a202a" opacity=".8"/>
    </svg>'''


def seconds(text):
    h,m,s=text.replace(',','.').split(':')
    return int(h)*3600+int(m)*60+float(s)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--width',type=int,default=540)
    parser.add_argument('--height',type=int,default=960)
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    name=f'{args.width}x{args.height}'
    work=root/name;work.mkdir(exist_ok=True)
    audio=root/'narration.mp3'
    chunks=[]
    for block in (root/'narration.srt').read_text().strip().split('\n\n'):
        parts=block.splitlines()
        if len(parts)<3:continue
        left,right=parts[1].split(' --> ')
        chunks.append((seconds(left),seconds(right),' '.join(parts[2:])))
    length=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration',
        '-of','default=nw=1:nk=1',str(audio)],text=True))
    duration=round(length*30)/30
    boundaries=[0, chunks[2][0], chunks[4][0], duration]
    groups=[chunks[:2],chunks[2:4],chunks[4:]]
    roles=['cold_open','evidence_and_answer','payoff_conclusion']
    titles=['Gerak Air, Cahaya Rumah','Air → Turbin → Listrik','Energi Berubah Bentuk']
    scenes=[];shots=[];assets=[]
    for index,group in enumerate(groups):
        start=round(boundaries[index]*30)/30
        end=round(boundaries[index+1]*30)/30
        narration=' '.join(c[2] for c in group)
        words=[]
        for a,b,text in group:
            tokens=text.split();weights=[max(1,len(re.sub(r'\\W','',token))) for token in tokens]
            total=sum(weights);cursor=a
            for token,weight in zip(tokens,weights):
                word_end=cursor+(b-a)*weight/total
                words.append({'text':token,'start':max(0,cursor-start),'end':min(end-start,word_end-start)})
                cursor=word_end
        scenes.append(NS(index=index+1,duration=end-start,voice_duration=end-start,
            narration=narration,narrative_role=roles[index],speech_words=words))
        shots.append(NS(index=index+1,scene_index=index+1,shot_index=1,duration=end-start+.3 if index<2 else end-start,
            camera_motion=['push_in','pan_left','pull_out'][index],framing=['wide','medium','wide'][index],
            subject_placement='center',on_screen_text=titles[index],title=titles[index],
            narration=narration,color_mood=['blue','blue','amber'][index],transition='cinematic_dissolve'))
        path=work/f'scene-{index+1}.svg'
        path.write_text(svg(args.width,args.height,('#59cafa','#f6c453')))
        assets.append(path)
    output,_=render_story_with_motlab(storyboard=NS(scenes=scenes),shots=shots,assets=assets,work_dir=work,
        scene_dir=work/'scenes',output_path=work/'picture.mp4',width=args.width,height=args.height,
        duration=duration,transition_seconds=.3,video_quality='high',burn_subtitles=True,
        progress=lambda *a:print(a,flush=True))
    final=root/f'ryuundy-motlab-{name}.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(output),'-i',str(audio),'-map','0:v','-map','1:a',
        '-c:v','copy','-c:a','aac','-b:a','160k','-ar','48000','-t',str(duration),'-movflags','+faststart',str(final)],check=True)
    (work/'demo-evidence.json').write_text(json.dumps({'duration_seconds':duration,'width':args.width,
        'height':args.height,'voice':'id-ID-ArdiNeural','narration_timing':'measured_edge_sentence_windows',
        'illustrations':'original_procedural_svg','output':str(final)},indent=2))
    print(final,flush=True)


if __name__=='__main__':main()

