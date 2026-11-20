"""Authored educational scenes: persistent objects, actions and visible results.

This is a labelled simulation, not a capture of a real phone application.
The pure scene model is shared by frame drawing, sound timing and QC evidence.
"""
from functools import lru_cache
import math
import re

from PIL import Image,ImageDraw,ImageFont

VERSION=1
FPS=30
INK='#173B45';MUTED='#54767B';TEAL='#168F85';GOLD='#F8C262';CORAL='#E9947D'


def ease(value):
    p=max(0.,min(1.,value));return p*p*(3-2*p)


def mix(a,b,p):return a+(b-a)*p


@lru_cache(maxsize=32)
def face(size,bold=False):
    return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans'+('-Bold' if bold else '')+'.ttf',size)


def anchor(stages,segments,index,words,default):
    stage=stages[index]
    for cue in segments:
        if cue.end<=stage['start'] or cue.start>=stage['end']:continue
        match=re.search(words,cue.text,re.I)
        if match:
            # TTS phrase timing is measured; the position inside a phrase is
            # estimated explicitly, not presented as word-level alignment.
            value=cue.start+(cue.end-cue.start)*match.start()/max(1,len(cue.text))
            return max(stage['start'],min(stage['end']-.6,value))
    return default


def timeline(plan,segments=()):
    stages=plan['stages'];begin=stages[2]['start'];end=stages[2]['end']
    if end-begin<2.1:raise ValueError('Narration leaves no readable demonstration window')
    selected=anchor(stages,segments,2,r'\b(?:salin|disalin|pindah\w*|pulih\w*|urut\w*|ketik|ubah|ganti|perhatikan)\b',begin+.25)
    selected=min(selected,end-1.8)
    departure=selected+.35;arrival=min(end-.25,departure+3.2)
    if arrival-departure<1:raise ValueError('Narration leaves no time to demonstrate the operation')
    reset=anchor(stages,segments,3,r'\b(?:kosongkan|semuanya)\b',stages[3]['start']+.35)
    compare=anchor(stages,segments,2,r'\b(?:file di asal|lihat dua|perhatikan)\b',arrival+.1)
    inspect=anchor(stages,segments,3,r'\b(?:periksa|setelah menyalin)\b',stages[3]['start']+.4)
    return dict(version=VERSION,fps=FPS,alignment='measured_tts_phrase_with_estimated_verb_position',
        select=round(selected,3),departure=round(departure,3),arrival=round(arrival,3),
        search_reset=round(reset,3),complete=round(arrival+.2,3),
        compare=max(round(arrival+.05,3),round(compare,3)),
        inspect=round(min(inspect,stages[3]['end']-1.5),3),
        phase_order=['recognize','select','demonstrate','inspect_result'],
        label='SIMULASI EDUKASI',source_clock_changed=False)


def progress(plan,t):
    clock=plan.get('motion_timeline') or timeline(plan)
    return clock,ease((t-clock['departure'])/(clock['arrival']-clock['departure']))


def scene(plan,t,state):
    """Return semantic identities and poses without changing the source plan."""
    clock,q=progress(plan,t);topic=plan['topic']
    before,right,left_name,right_name=state(plan,1)
    after,after_right,_,_=state(plan,2)
    items=[];folders=[];editing=None;query='';focus=(480.,760.)
    complete=t>=clock['arrival'];select=t>=clock['select']
    if topic in {'copy','group','restore','paths'}:
        folders=[dict(x=90,y=835,w=350,label=left_name,open=1.,color=TEAL),
                 dict(x=560,y=835,w=350,label=right_name,open=.18+.82*ease(q*2),color=CORAL)]
        tiny=topic=='group';size=(108,150) if tiny else (200,255)
        left=[(115+i*112,715-i*8) for i in range(len(before))] if tiny else [(165,675)]
        right_poses=[(590+i*125,715-i*8) for i in range(2)] if tiny else [(635,675)]
        moving={r['id'] for r in after_right} if topic!='paths' else set()
        for index,row in enumerate(before):
            x,y=left[index];destination=next((i for i,r in enumerate(after_right) if r['id']==row['id']),0)
            p=ease((q-destination*.16)/max(.1,1-destination*.16))
            if row['id'] in moving and topic!='copy':
                tx,ty=right_poses[destination]
                x=mix(x,tx,p);y=mix(y,ty,p)-165*math.sin(math.pi*p)
            items.append(dict(**row,key=row['id'],x=x,y=y,w=size[0],h=size[1],scale=1.,visible=True,
                              role='original',highlight=select and row['id'] in moving))
        if topic=='copy' and q>0:
            row=before[0];tx,ty=right_poses[0]
            items.append(dict(**row,key=row['id']+':copy',x=mix(165,tx,q),y=mix(675,ty,q)-110*math.sin(math.pi*q),
                w=200,h=255,scale=1.,visible=True,role='copy',highlight=True))
        if topic=='paths':
            items.extend(dict(**r,key=r['id'],x=635,y=675,w=200,h=255,scale=1.,visible=True,
                              role='original',highlight=select and q>.5) for r in right)
        for item in items:item['folder_item']=True
        if topic=='copy' and complete:
            # Inspect the two existing objects in turn, then lift the same
            # destination document for the narrated final check. No extra file
            # is created by inspecting it, and labels do not rotate or change.
            compare=clock.get('compare',clock['arrival']+.4)
            for item in items:
                offset=0 if item['role']=='original' else 1.8
                phase=(t-compare-offset)/1.2
                peek=math.sin(math.pi*phase)**2 if 0<phase<1 else 0
                item['y']-=32*peek
                if item['role']=='copy' and 'inspect' in clock:
                    inspect=clock['inspect'];window=max(.8,min(3.,plan['stages'][3]['end']-inspect-.3))
                    lift=ease((t-inspect)/.5)*(1-ease((t-inspect-window+.6)/.6))
                    item.update(x=item['x']-35*lift,y=item['y']-90*lift,
                                w=200+80*lift,h=255+95*lift)
        moving_item=next((r for r in reversed(items) if r['highlight']),items[0])
        focus=(moving_item['x']+moving_item['w']*.65,moving_item['y']+moving_item['h']*.5)
        counts=(len(before),len(right)) if not complete else (len(after),len(after_right))
        if topic=='paths':counts=(1,1)
        folders[0]['count'],folders[1]['count']=counts
        # Stage the actual starting objects during the hook, then point from
        # the source to the empty destination while explaining the setup.
        left_shift=-480*(1-ease(t/.7));right_shift=480*(1-ease((t-.2)/.8))
        folders[0]['x']+=left_shift;folders[1]['x']+=right_shift
        for item in items:
            if topic=='paths' and item['id'] in {r['id'] for r in right}:item['x']+=right_shift
            else:item['x']+=left_shift
            item['y']-=90*(1-ease((t-.35)/.85))
        if not select:
            setup=ease((t-plan['stages'][1]['start'])/max(.1,plan['stages'][1]['end']-plan['stages'][1]['start']))
            focus=(mix(275,735,setup),mix(790,930,setup))
    elif topic in {'size','date','number'}:
        target={row['id']:i for i,row in enumerate(after)}
        # Fan into independent lanes before reordering, then settle. Objects
        # never cross through each other's labels while exchanging positions.
        spread=ease(q/.22) if q<.22 else 1-ease((q-.78)/.22) if q>.78 else 1
        travel=ease((q-.22)/.56)
        for index,row in enumerate(before):
            x=mix(95+index*270,95+target[row['id']]*270,travel)
            y=780+(index-1)*245*spread
            result=next(r for r in after if r['id']==row['id'])
            display=result if topic=='number' and q>.05 else row
            items.append(dict(**display,key=row['id'],x=x,y=y,w=240,h=220,scale=1.,visible=True,
                              role='original',highlight=select))
        focus=(items[0]['x']+120,items[0]['y']+90)
    elif topic=='search':
        query='kegiatan'[:round(8*q)] if t<clock['search_reset'] else ''
        restored=ease((t-clock['search_reset'])/.65) if t>=clock['search_reset'] else 0
        for index,row in enumerate(before):
            matches='kegiatan' in row['label'].casefold()
            shift=0 if matches else ease((q-.15)/.85)*(1-restored)
            items.append(dict(**row,key=row['id'],x=155+1000*shift,y=675+index*165,w=650,h=130,
                scale=1.,visible=shift<.8,role='original',highlight=select and matches))
        focus=(360,590)
    else:
        row=before[0];result=after[0]
        items=[dict(**(result if complete else row),key=row['id'],x=305,y=620,w=350,h=360,
                    scale=1.,visible=True,role='original',highlight=select)]
        old,new=row['label'],result['label']
        editing=(new[:round(len(new)*q)] if q else old)
        focus=(160+min(650,len(editing)*16),1100)
    source_ids=list(dict.fromkeys(r['id'] for r in before+right))
    return dict(topic=topic,items=items,folders=folders,query=query,editing=editing,
        focus=focus,operation_progress=q,selected=select,complete=complete,
        source_ids=source_ids,source_count=len(source_ids),
        stored_count=len(source_ids)+(1 if topic=='copy' and q>0 else 0),clock=clock)


def text(draw,value,x,y,width,size=32,*,color=INK,bold=False,lines=3):
    """Wrap words and long filenames within an explicit box; labels stay upright."""
    font=face(size,bold);result=[];line=''
    for word in str(value).replace('_','_ ').split():
        for token in ([word] if draw.textlength(word,font=font)<=width else list(word)):
            trial=(line+(' ' if len(token)>1 and line else '')+token)
            if line and draw.textlength(trial,font=font)>width:
                result.append(line);line=token
            else:line=trial
    if line:result.append(line)
    for index,line in enumerate(result[:lines]):
        if index==lines-1 and len(result)>lines:
            while line and draw.textlength(line+'…',font=font)>width:line=line[:-1]
            line+='…'
        draw.text((round(x),round(y+index*(size+9))),line,font=font,fill=color)
    return len(result[:lines])*(size+9)


@lru_cache(maxsize=1)
def background():
    image=Image.new('RGB',(1080,1920),'#F6F4E9');d=ImageDraw.Draw(image)
    d.ellipse((-260,310,670,1240),fill='#E4EFE5')
    d.ellipse((650,400,1420,1150),fill='#F4E2CD')
    d.rounded_rectangle((125,480,875,1210),radius=145,fill='#EDF1E4')
    d.ellipse((48,1135,940,1270),fill='#DDE4D6')
    d.rounded_rectangle((65,1220,935,1232),radius=6,fill='#B8CEC1')
    return image


def folder_back(d,row):
    x,y,w=row['x'],row['y'],row['w']
    d.rounded_rectangle((x+10,y-45,x+w*.5,y+15),radius=20,fill=row['color'])
    d.rounded_rectangle((x,y,x+w,y+245),radius=26,fill=row['color'])
    d.rounded_rectangle((x+16,y+20,x+w-16,y+225),radius=18,fill='#FAF7ED')


def folder_front(d,row):
    x,y,w=row['x'],row['y'],row['w'];lift=24*row['open']
    d.polygon([(x,y+90-lift),(x+w,y+112-lift),(x+w-12,y+245),(x+12,y+245)],fill=row['color'])
    d.line((x+16,y+112-lift,x+w-16,y+132-lift),fill='#FFFFFF',width=3)
    text(d,row['label'],x+24,y+156,w-48,30,color='white',bold=True,lines=1)
    count=row.get('count',0)
    text(d,f'{count} berkas',x+16,y+265,w-32,28,color=MUTED,lines=1)


def document(d,item):
    if not item['visible']:return
    x,y,w,h=map(round,(item['x'],item['y'],item['w'],item['h']))
    selected=item['highlight'];edge=TEAL if selected else '#A8C3BE'
    d.rounded_rectangle((x+7,y+12,x+w+7,y+h+12),radius=18,fill='#C7D5C9')
    d.rounded_rectangle((x,y,x+w,y+h),radius=18,fill='#FFFFFF',outline=edge,width=4 if selected else 2)
    tiny=w<150;size=18 if tiny else 24 if w<300 else 34
    kind=item['type'];accent=CORAL if kind=='photo' else '#8F9CC3' if kind=='video' else TEAL
    label='FOTO' if kind=='photo' else 'VIDEO' if kind=='video' else 'TXT'
    if w>h*2:
        d.rounded_rectangle((x+16,y+18,x+85,y+h-18),radius=10,fill=accent)
        d.text((x+24,y+45),label,font=face(18,True),fill='white')
        text(d,item['label'],x+110,y+27,w-135,27,bold=True,lines=2)
        return
    d.rounded_rectangle((x+12,y+13,x+w-12,y+44),radius=8,fill=accent)
    d.text((x+20,y+18),label,font=face(15 if tiny else 18,True),fill='white')
    if kind in {'photo','video'}:
        d.rectangle((x+14,y+56,x+w-14,y+h*.6),fill='#D8ECE6')
        d.ellipse((x+w*.62,y+65,x+w*.82,y+85),fill=GOLD)
        d.polygon([(x+14,y+h*.6),(x+w*.43,y+65),(x+w-14,y+h*.6)],fill='#72B5A0')
    else:
        for index in range(3):
            yy=y+60+index*(15 if tiny else 22)
            d.rounded_rectangle((x+17,yy,x+w-20-(index%2)*18,yy+5),radius=2,fill='#B6D7CE')
    value=item.get('detail') or item['label']
    if tiny:value='Foto' if kind=='photo' else 'Video' if kind=='video' else 'Catatan'
    elif item.get('folder_item'):
        if item.get('detail'):
            text(d,item['label'],x+14,y+125,w-28,18,color=MUTED,lines=1)
            text(d,item['detail'],x+14,y+154,w-28,22,bold=True,lines=2)
            value=None
        else:value='Catatan' if kind=='document' else 'Foto' if kind=='photo' else 'Video'
    if value is not None:
        text(d,value,x+14,y+max(100,h*.59),w-28,size,bold=True,lines=2 if w<=240 else 3)
    if item['role']=='copy':
        d.rounded_rectangle((x+25,y-42,x+w-25,y-8),radius=12,fill=TEAL)
        text(d,'SALINAN',x+36,y-36,w-60,20,color='white',bold=True,lines=1)


def guide(d,t,target,active):
    # A small helper physically points at the current object; it is not a
    # talking likeness of a real person or a lip-synced substitute narrator.
    x,y=780,1300;hand=(x-95,y+7 if active else y+35)
    if active:
        d.line((hand,target),fill='#789D91',width=4)
        d.ellipse((target[0]-7,target[1]-7,target[0]+7,target[1]+7),fill=GOLD)
    d.line([(x-25,y+45),(x-80,y+45),hand],fill=TEAL,width=14,joint='curve')
    hx,hy=hand;d.ellipse((hx-15,hy-15,hx+15,hy+15),fill='#F0C59C',outline=INK,width=2)
    d.rounded_rectangle((x-44,y,x+44,y+100),radius=28,fill=TEAL)
    d.ellipse((x-47,y-72,x+47,y+18),fill='#A9DCC7',outline=INK,width=3)
    blink=(t%4.7)<.12
    for eye in (x-17,x+17):
        d.ellipse((eye-4,y-39,eye+4,y-37 if blink else y-26),fill=INK)
    d.arc((x-18,y-29,x+18,y-6),0,180,fill=INK,width=3)
    d.line((x-23,y+94,x-28,y+119),fill=INK,width=7)
    d.line((x+23,y+94,x+28,y+119),fill=INK,width=7)


def draw(plan,t,cues,state):
    model=scene(plan,t,state);image=background().copy();d=ImageDraw.Draw(image)
    text(d,'RYUUNDY  /  DIGITAL SEHARI-HARI',85,95,820,23,color=TEAL,bold=True,lines=1)
    text(d,plan['title'],85,155,790,57,bold=True,lines=3)
    text(d,'SIMULASI EDUKASI · DATA CONTOH',85,402,790,22,color=MUTED,lines=1)
    inspecting=plan['topic']=='copy' and model['clock'].get('inspect',float('inf'))<=t<model['clock'].get('inspect',0)+3
    status=('PERIKSA SALINANNYA' if inspecting else 'HASILNYA TERLIHAT' if model['complete'] else 'IKUTI PERGERAKANNYA' if model['selected'] else 'PERHATIKAN OBJEKNYA')
    text(d,status,95,470,790,23,color=TEAL,bold=True,lines=1)
    if plan['topic'] not in {'size','date','number'}:
        guide(d,t,model['focus'],inspecting or not model['complete'])
    for folder in model['folders']:folder_back(d,folder)
    if model['selected'] and plan['topic'] in {'copy','group','restore'}:
        for index in range(14):
            x=260+index*36;y=620-70*math.sin(index/13*math.pi)
            d.ellipse((x,y,x+5,y+5),fill='#8FBEB1')
    if plan['topic']=='search':
        d.rounded_rectangle((130,545,850,635),radius=28,fill='white',outline=TEAL,width=3)
        d.ellipse((155,570,180,595),outline=TEAL,width=4);d.line((178,593,191,607),fill=TEAL,width=4)
        text(d,model['query'] or 'Cari nama berkas…',215,568,600,31,color=TEAL if model['query'] else MUTED,lines=1)
    for item in model['items']:document(d,item)
    for folder in model['folders']:folder_front(d,folder)
    if model['editing'] is not None:
        d.rounded_rectangle((115,1060,870,1175),radius=24,fill='white',outline=TEAL,width=3)
        text(d,model['editing'],140,1080,700,29,color=INK,bold=True,lines=2)
    if model['complete']:
        d.ellipse((110,1250,160,1300),fill=TEAL)
        d.line([(121,1274),(132,1285),(149,1264)],fill='white',width=5)
        captions={'copy':'Asal tetap ada. Salinan masuk tujuan.','group':'Jenis berkas terpisah. Jumlah tetap.',
            'restore':'Berkas keluar dari Sampah.','search':'Filter bukan penghapusan.',
            'paths':'Periksa lokasi dan isi.','extension':'Nama berubah. Format tetap.',
            'rename':'Nama lebih jelas. Isi tetap sama.','size':'Urut ukuran. Belum ada yang dihapus.',
            'date':'Pola tanggal konsisten.','number':'Dua digit, urutan lebih jelas.'}
        text(d,captions[plan['topic']],180,1254,530,27,color=TEAL,bold=True,lines=2)
    cue=next((c for c in cues if c[0]<=t<c[1]),None)
    if cue:
        for index,line in enumerate(cue[2].splitlines()):
            font=face(plan.get('caption_font_size',48),True);width=d.textlength(line,font=font)
            d.text(((960-width)/2,1435+index*69),line,font=font,fill=INK)
    for index,label in enumerate(('KENALI','LAKUKAN','PERIKSA')):
        active=index==2 if model['complete'] else index==1 if model['selected'] else index==0
        x=100+index*270
        d.rounded_rectangle((x,1660,x+225,1666),radius=3,fill=TEAL if active else '#C8D9D0')
        text(d,label,x,1683,240,21,color=TEAL if active else MUTED,bold=active,lines=1)
    return image
