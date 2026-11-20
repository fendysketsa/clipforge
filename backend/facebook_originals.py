"""Authored digital demonstrations: original objects, measured neural voice, QC.

No stock/reused video, third-party music, fake device capture, or claimed Meta approval.
Each output retains its exact source plan and a hash-bound independent QC record.
"""
from __future__ import annotations

import base64
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback
from urllib.error import HTTPError
from types import SimpleNamespace

from PIL import Image, ImageDraw, ImageFont

import facebook_strategy as strategy
import facebook_creative as creative
import facebook_motion as motion
import facebook_motlab as motlab
import facebook_education as education
from audio_mix import normalize_narration
import long_video_qc as qc
from llm import AIConfig,chat_completion,extract_json
from channel_branding import watermark_filter, watermark_metadata

VERSION = 1
AUTO_CONFIDENCE_MIN = .9
FPS = 15
ROOT = Path(__file__).resolve().parent
PROVIDER_CONFIG_PATH = ROOT/'data/facebook_qc_provider.json'
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


class SourceRejected(ValueError):
    """A provider refusal is terminal for this source, not an outage."""


def provider_config():
    """Facebook may select its own model; credentials/export policy stay shared."""
    config=dict(qc.provider_config())
    if PROVIDER_CONFIG_PATH.is_file():
        saved=json.loads(PROVIDER_CONFIG_PATH.read_text())
        model=saved.get('model')
        if not isinstance(model,str) or not model.strip():raise ValueError('Model QC Facebook belum valid.')
        config['model']=model.strip()
        tokens=saved.get('max_output_tokens',4096)
        if type(tokens) is not int or not 4096<=tokens<=16384:
            raise ValueError('Batas output QC Facebook belum valid.')
        config['max_output_tokens']=tokens
    return config


def audit_fingerprint(media,context):
    return qc.fingerprint(media,context,provider=provider_config())

# These illustrate stable file operations in an explicitly authored simulator.
# Version-dependent phone menus and unverified security/health claims are excluded.
TOPICS = (
    ('group', 'Folder sesuai keperluan', 'Dokumen bercampur dengan foto? Pisahkan tempatnya.',
     'Pada simulasi ini, satu folder berisi catatan dan dua foto kegiatan. Nama yang mirip membuat pencarian lebih lama.',
     'Pilih kedua foto, lalu pindahkan ke folder Foto kegiatan. Catatan tetap berada di folder Dokumen, tanpa ikut berpindah.',
     'Sekarang jenis file terpisah dan jumlahnya tetap tiga. Gunakan nama folder yang menjelaskan isinya, lalu periksa tujuan sebelum memindahkan.'),
    ('rename', 'Nama file yang mudah dikenali', 'Nama file cuma angka? Tambahkan konteks yang jelas.',
     'Di simulasi ini, sebuah catatan memakai nama umum. Dari daftar file saja, isi catatan sulit dibedakan.',
     'Ubah bagian nama menjadi Catatan kegiatan, lalu tambahkan tanggal contoh. Pertahankan ekstensi file di bagian paling akhir.',
     'Hasilnya lebih mudah dikenali sebelum dibuka. Ini hanya mengganti nama, bukan mengubah isi atau format dokumennya.'),
    ('date', 'Tanggal yang mudah diurutkan', 'Urutan nama file berantakan? Coba susunan tanggal ini.',
     'Tiga catatan contoh memakai tanggal berbeda. Urutan daftar awal belum menunjukkan catatan yang lebih dahulu dibuat.',
     'Tulis tahun, bulan, lalu tanggal dengan jumlah digit konsisten. Sekarang urutkan nama file dari kecil ke besar.',
     'Pada contoh ini, nama tersusun mengikuti tanggal. Gunakan pola yang sama pada semua file agar urutannya tetap mudah dibaca.'),
    ('size', 'Periksa file besar sebelum merapikan', 'Ruang file terasa penuh? Periksa ukurannya dulu.',
     'Daftar contoh ini berisi satu dokumen kecil dan dua video dengan ukuran berbeda. Semua ukuran ditampilkan di samping nama.',
     'Urutkan ukuran dari besar ke kecil. Video terbesar naik ke atas, sehingga mudah diperiksa sebelum memutuskan tindakan.',
     'Mengurutkan belum menghapus apa pun. Periksa file yang masih diperlukan dan salin yang penting sebelum merapikan penyimpanan.'),
    ('search', 'Cari dengan kata yang spesifik', 'File sulit ditemukan? Coba kata yang ada di namanya.',
     'Simulasi ini memiliki beberapa nama file yang berbeda. Kita hanya ingin melihat catatan yang berkaitan dengan kegiatan.',
     'Ketik kata kegiatan pada kolom pencarian. Daftar menyaring nama yang cocok, sementara file lain tidak ditampilkan.',
     'File yang tidak tampil tetap ada. Kosongkan pencarian untuk melihat semuanya lagi; hasil pencarian bukan tanda bahwa file lain terhapus.'),
    ('copy', 'Salin dan pindah itu berbeda', 'Mau membuat salinan? Periksa dua lokasi ini.',
     'Pada contoh ini, catatan masih ada di folder Asal. Folder Cadangan di sebelah kanan belum memiliki catatan tersebut.',
     'Gunakan operasi salin ke folder Cadangan. Perhatikan bahwa catatan tetap ada di folder Asal, dan satu salinan muncul di tujuan.',
     'Kedua lokasi sekarang memiliki file. Setelah menyalin, periksa bahwa salinan bisa dibuka; jangan menganggap proses berhasil hanya karena sudah menekan tombol.'),
    ('restore', 'Periksa sampah sebelum menghapus permanen', 'Salah menghapus file? Periksa tempat sampah dulu.',
     'Di simulasi ini, satu catatan berada di folder Sampah. Folder Dokumen belum menampilkan catatan tersebut.',
     'Pilih catatan di Sampah, lalu gunakan Pulihkan. Catatan kembali terlihat di Dokumen dan tidak lagi berada di daftar Sampah.',
     'Ini contoh aplikasi yang menyediakan pemulihan. Fitur dan batas waktunya bisa berbeda; periksa sebelum menghapus file secara permanen.'),
    ('extension', 'Mengganti nama bukan mengubah format', 'Mengganti akhiran file belum berarti mengubah formatnya.',
     'Dalam contoh ini, kita punya berkas teks bernama Catatan titik t x t. Isinya tetap berupa tulisan sederhana.',
     'Bagian nama dapat diganti agar lebih jelas. Namun, mengganti nama saja tidak membuat isi berkas berubah menjadi gambar atau dokumen jenis lain.',
     'Pertahankan ekstensi yang sesuai. Jika perlu format berbeda, gunakan fitur ekspor atau konversi yang benar pada aplikasi pembuatnya.'),
    ('number', 'Nomor file agar mudah diurutkan', 'Kenapa nomor sepuluh menyelip di tengah?',
     'Pada contoh ini, nama Catatan satu, Catatan sepuluh, dan Catatan dua sedang diurutkan sebagai teks. Perhatikan posisi nomor sepuluh.',
     'Gunakan dua digit yang konsisten, yaitu nol satu, nol dua, dan sepuluh. Urutkan lagi berdasarkan nama; posisi file sekarang lebih mudah diikuti.',
     'Dalam contoh ini, angka pada nama menjadi rapi. Ini hanya pola penamaan; aplikasi lain dapat memiliki cara pengurutan yang berbeda.'),
    ('paths', 'Nama sama belum tentu file yang sama', 'Nama sama, folder berbeda. Periksa lokasinya.',
     'Dalam simulasi ini, dua file bernama Catatan berada pada folder Rumah dan Kerja. Keterangan isi yang terlihat juga berbeda.',
     'Perhatikan nama folder sebelum memilih file. Catatan di Rumah berisi daftar belanja, sementara catatan di Kerja berisi agenda rapat.',
     'Nama yang sama saja belum cukup untuk menyebut file duplikat. Periksa lokasi dan isi terlebih dahulu sebelum menghapus atau mengganti file.'),
)


def topic_keys(series='digital'):
    return [row[0] for row in TOPICS] if series=='digital' else education.topic_keys(series)


def series_catalogue():
    return education.catalogue([dict(key=key,title=title) for key,title,*_ in TOPICS])


def plan(seed: str, kind='reel', *, topic=None, series='digital') -> dict:
    if series!='digital':return education.plan(seed,kind,topic,series)
    digest = hashlib.sha256(seed.encode()).hexdigest()
    selected=topic or creative.choose_topic(seed,[row[0] for row in TOPICS])
    index=next(i for i,row in enumerate(TOPICS) if row[0]==selected)
    action,title,*lines = TOPICS[index]
    number = 1+int(digest[8:12],16)%28
    example = f'Kegiatan_{number:02}'
    rows = [dict(id='a', label=f'Catatan_{example}.txt', size=2, type='document'),
            dict(id='b', label=f'Foto_{example}.jpg', size=8, type='photo'),
            dict(id='c', label=f'Foto_taman_{number:02}.jpg', size=5, type='photo')]
    if action=='size':
        rows[1].update(label=f'Video_{example}.mp4',size=120,type='video')
        rows[2].update(label=f'Video_taman_{number:02}.mp4',size=48,type='video')
    if action=='date':
        for row,day in zip(rows,(23,4,15)):
            row.update(label=f'2026-10-{day:02}_catatan.txt',type='document')
    if action=='rename':rows[0]['label']='Dokumen_001.txt'
    if action=='extension':rows[0]['label']='Catatan.txt'
    if action=='search':
        for row,label in zip(rows,(f'Catatan_kegiatan_{number:02}.txt','Jadwal_taman.txt','Catatan_belanja.txt')):
            row.update(label=label,type='document')
    if action=='number':
        for row,num in zip(rows,(1,10,2)):row.update(label=f'Catatan_{num}.txt',type='document')
    if action=='paths':
        rows[0].update(label='Catatan.txt',detail='Daftar belanja')
        rows[1].update(label='Catatan.txt',detail='Agenda rapat',type='document')
        rows=rows[:2]
    lines[0]=creative.HOOKS[action]
    stages=[dict(title=name,text=text) for name,text in zip(('Masalahnya','Perhatikan contoh','Coba langkahnya','Lihat hasilnya'),lines)]
    caption=strategy.public_caption(title+'. '+lines[-1])+'\n\n#TipsDigital #TeknologiSehariHari'
    result=dict(version=VERSION,seed=seed,kind=kind,topic=action,title=title,stages=stages,
                files=rows,caption=caption,visual_type='authored_animated_simulation',
                third_party_footage=False,third_party_music=False,synthetic_voice=True,
                narration_provider='edge_neural_id-ID-ArdiNeural',example=example)
    result['creative_policy']=creative.policy(action,seed)
    result['motion_version']=motion.VERSION
    result['render_engine']=motlab.ENGINE
    result['creative_policy'].update(first_result_preview=None,format='persistent_object_demonstration')
    result['plan_sha256']=hashlib.sha256(json.dumps(result,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return result


def script_identity(plan):
    text=' '.join(stage['text'] for stage in plan['stages']).casefold()
    return hashlib.sha256(re.sub(r'\W+',' ',text).strip().encode()).hexdigest()


def author(source_plan,previous=()):
    """Author new narration grounded in the executable demonstration, then QC it.

    The finite source catalog is not an endless carousel of identical scripts.
    Missing author access may use an unused reviewed baseline, never replay it.
    """
    previous=set(previous)
    if source_plan.get('education'):
        education.verify_plan(source_plan)
        result=json.loads(json.dumps(source_plan))
        result['script_sha256']=script_identity(result)
        if result['script_sha256'] in previous:
            raise ValueError('Naskah edukasi identik sudah pernah diproduksi; pilih topik lain.')
        result['authoring']='curated_education_script'
        return result
    config=provider_config()
    plan=json.loads(json.dumps(source_plan))
    if config.get('base_url') and config.get('model'):
        try:
            raw=extract_json(chat_completion(AIConfig(enabled=True,base_url=config['base_url'],
                model=config['model'],api_key=config['api_key'],timeout=90),[
                {'role':'system','content':'Anda penulis tutorial digital Indonesia untuk FB Pro. '
                 'Buat satu penjelasan orisinal 65–90 kata dengan empat tahap: hook singkat, konteks, langkah simulasi, hasil dan batasan. '
                 'Hanya jelaskan operasi dan objek pada simulasi yang disediakan. Jangan mengaku merekam perangkat sungguhan, '
                 'menambahkan menu aplikasi nyata, fakta eksternal, harga, klaim kesehatan/keamanan, atau janji penghasilan. '
                 'Sebut bahwa ini simulasi atau contoh. Jangan mengarang hasil yang tidak ditampilkan. '
                 'Buka langsung dengan masalah yang akrab bagi keluarga atau hasil yang terlihat; hindari pembuka "lihat simulasi", '
                 '"di video ini" dan kalimat pengisi. Hook maksimal 9 kata; konteks tahap kedua maksimal 14 kata; '
                 'dua tahap lainnya maksimal 32 kata. Penonton harus memahami satu tindakan dan akibatnya. '
                 'Caption dua kalimat harus didukung demonstrasi, '
                 'tanpa sumber, URL, ajakan engagement, atau hashtag. Jawab JSON {"title":"...","narration":["...","...","...","..."],"caption":"..."}.'},
                {'role':'user','content':json.dumps({'basis':source_plan,
                    'states':[state(source_plan,i) for i in (1,2,3)],'edition':source_plan['seed']},ensure_ascii=False)}
            ],temperature=.65))
            lines=raw.get('narration') if isinstance(raw,dict) else None
            if not isinstance(lines,list) or len(lines)!=4 or not all(isinstance(s,str) and s.strip() for s in lines):
                raise ValueError('Empat tahap naskah wajib lengkap.')
            count=sum(len(s.split()) for s in lines)
            if not 65<=count<=95 or len(lines[0].split())>9 or len(lines[1].split())>14 or any(len(s.split())>32 for s in lines[2:]):
                raise ValueError('Panjang naskah FB belum sesuai.')
            if not re.search(r'\b(?:simulasi|contoh)\b',' '.join(lines),re.I):
                raise ValueError('Demonstrasi harus dinyatakan sebagai simulasi.')
            title=strategy.public_caption(raw.get('title',''))
            caption=strategy.public_caption(raw.get('caption',''))
            if not title or len(title)>80 or not caption:raise ValueError('Kemasan naskah belum valid.')
            plan['title']=title
            for stage,text in zip(plan['stages'],lines):stage['text']=text.strip()
            plan['caption']=caption+'\n\n#TipsDigital #TeknologiSehariHari'
            plan['authoring']='fresh_grounded_ai_script_pending_independent_qc'
        except Exception as exc:
            if getattr(exc,'code',None)==422:
                raise SourceRejected('Provider menolak naskah; produksi ditahan tanpa mengalihkan pemeriksaan.') from None
            if script_identity(source_plan) in previous:
                raise ValueError('Naskah segar belum tersedia; pengulangan naskah lama ditahan.') from None
            plan=source_plan
    if script_identity(plan) in previous:
        raise ValueError('Naskah identik sudah pernah diproduksi; slot ditahan untuk bahan baru.')
    plan['script_sha256']=script_identity(plan)
    return plan


def srt_time(seconds):
    value=round(seconds*1000)
    return f'{value//3600000:02}:{value//60000%60:02}:{value//1000%60:02},{value%1000:03}'


def parse_srt(text):
    rows=[]
    for block in re.split(r'\n\s*\n',text.strip()):
        found=re.search(r'(\d\d):(\d\d):(\d\d),(\d{3}) --> (\d\d):(\d\d):(\d\d),(\d{3})\s+(.+)',block,re.S)
        if found:
            v=list(map(int,found.groups()[:8]))
            rows.append(SimpleNamespace(start=v[0]*3600+v[1]*60+v[2]+v[3]/1000,
                end=v[4]*3600+v[5]*60+v[6]+v[7]/1000,text=re.sub(r'\s+',' ',found[9]).strip()))
    return rows


def duration(path):
    return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(path)],timeout=20))


def audio_windows(length):
    """Cover the whole audio without asking Whisper to judge a tiny last word."""
    if not math.isfinite(length) or length<=0:raise ValueError('Invalid audio duration')
    rows=[]
    for start in range(0,math.ceil(length),6):
        span=min(6.0,length-start)
        if span<=0:continue
        if span<2 and rows:
            previous,_=rows[-1];rows[-1]=(previous,length-previous)
        else:rows.append((float(start),span))
    return rows


def voice(stages,folder,progress,*,voice_name='id-ID-ArdiNeural',rate='+3%'):
    rows=[];audio=[];cursor=0.0
    for i,stage in enumerate(stages):
        progress(12+i*7,'voice',f'Membuat narasi asli {i+1}/{len(stages)}')
        path=folder/f'voice_{i}.mp3';subtitle=folder/f'voice_{i}.srt'
        subprocess.run([sys.executable,'-m','edge_tts','--voice',voice_name,'--rate='+rate,
            '--text',stage['text'],'--write-media',str(path),'--write-subtitles',str(subtitle)],
            check=True,capture_output=True,timeout=150)
        decoded=folder/f'voice_{i}.wav'
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(path),'-ar','48000','-ac','1',
            '-c:a','pcm_s16le',str(decoded)],check=True,capture_output=True,timeout=30)
        length=duration(decoded)
        cues=parse_srt(subtitle.read_text())
        if not cues or length<=0:raise ValueError('Timing narasi neural tidak tersedia.')
        for cue in cues:
            cue.start+=cursor;cue.end=min(cursor+length,cue.end+cursor);rows.append(cue)
        stage.update(start=cursor,end=cursor+length)
        cursor+=length;audio.append(decoded)
    tempo=max(.85,cursor/28) if cursor<26 else 1.0
    if not 26<=cursor/tempo<=55:
        raise ValueError(f'Narasi {cursor:.1f} detik di luar 26–55 detik; tidak dipotong paksa.')
    listing=folder/'voices.txt'
    listing.write_text(''.join(f"file '{p.name}'\n" for p in audio))
    combined=folder/'narration.wav'
    command=['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',str(listing)]
    if tempo!=1:command+=['-af',f'atempo={tempo:.8f}']
    subprocess.run([*command,
        '-ar','48000','-ac','1','-c:a','pcm_s16le',str(combined)],check=True,timeout=60)
    if tempo!=1:
        for row in rows:row.start/=tempo;row.end/=tempo
        for stage in stages:stage['start']/=tempo;stage['end']/=tempo
    measured=duration(combined)
    if not 26<=measured<=55:raise ValueError('Durasi narasi encoded belum memenuhi profil Facebook.')
    return combined,rows,measured


@lru_cache(maxsize=24)
def font(size,bold=False):return ImageFont.truetype(BOLD if bold else FONT,size)


def wrapped(draw,text,x,y,width,size=50,fill='#e8f1fc',bold=False,line_height=None):
    face=font(size,bold);line=''
    for word in text.split():
        trial=(line+' '+word).strip()
        if line and draw.textlength(trial,font=face)>width:
            draw.text((x,y),line,font=face,fill=fill);y+=line_height or round(size*1.35);line=word
        else:line=trial
    if line:draw.text((x,y),line,font=face,fill=fill)
    return y+(line_height or round(size*1.35))


def heading_size(draw,text):
    for size in (64,60,56,52,48,44):
        lines=1;line=''
        for word in text.split():
            proposal=(line+' '+word).strip()
            if line and draw.textlength(proposal,font=font(size,True))>720:
                lines+=1;line=word
            else:line=proposal
        if lines*round(size*1.25)<=175:return size
    return 44


def state(plan,phase):
    """Return actual object state demonstrated at each measured narration stage."""
    rows=[dict(row) for row in plan['files']]
    action=plan['topic']
    before,after='Semua file','Hasil langkah'
    right=[]
    if action=='group':
        before,after='Dokumen','Foto kegiatan'
        if phase>=2:right=[r for r in rows if r['type']=='photo'];rows=[r for r in rows if r['type']!='photo']
    elif action in {'rename','extension'}:
        if phase>=2:
            rows[0]['label']=(f'Catatan_2026-10-{int(plan["example"].rsplit("_",1)[1]):02}.txt'
                              if action=='rename' else f'Catatan_{plan["example"]}.txt')
        before='Nama file';after='Isi tetap sama'
    elif action=='date':
        before='Urut nama A → Z';after='Tahun → bulan → tanggal'
        if phase>=2:rows=sorted(rows,key=lambda r:r['label'])
    elif action=='size':
        before='Ukuran besar → kecil';after='Belum ada file dihapus'
        if phase>=2:rows=sorted(rows,key=lambda r:r['size'],reverse=True)
    elif action=='search':
        before='Cari: kegiatan' if phase>=2 else 'Semua file';after='Pencarian tidak menghapus'
        if phase==2:rows=[r for r in rows if 'kegiatan' in r['label'].casefold()]
    elif action=='copy':
        rows=rows[:1];before,after='Asal','Cadangan'
        if phase>=2:right=[dict(rows[0])]
    elif action=='restore':
        rows=rows[:1];before,after='Sampah','Dokumen'
        if phase>=2:right=rows;rows=[]
    elif action=='number':
        before,after='Urut nama sebagai teks','01 → 02 → 10'
        if phase>=2:
            for row,num in zip(rows,(1,10,2)):row['label']=f'Catatan_{num:02}.txt'
            rows=sorted(rows,key=lambda row:row['label'])
    elif action=='paths':
        before,after='Rumah','Kerja';right=[rows[1]];rows=rows[:1]
    return rows,right,before,after


def legacy_frame(plan,t,cues):
    image=Image.new('RGB',(1080,1920),'#0b1728');draw=ImageDraw.Draw(image)
    stage_index=next((i for i,s in enumerate(plan['stages']) if s['start']<=t<s['end']),3)
    stage=plan['stages'][stage_index]
    part=max(0,min(1,(t-stage['start'])/max(.01,stage['end']-stage['start'])))
    draw.text((110,160),'RYUUNDY  /  DIGITAL SEHARI-HARI',font=font(25,True),fill='#70b9ff')
    title_size=heading_size(draw,plan['title'])
    wrapped(draw,plan['title'],110,230,720,title_size,bold=True,line_height=round(title_size*1.25))
    draw.text((110,420),'SIMULASI EDUKASI · DATA CONTOH',font=font(23),fill='#90a6c1')
    preview=.35<=t<1.85 and (plan.get('creative_policy') or {}).get('version')==creative.VERSION
    rows,right,left_label,right_label=state(plan,2 if preview else stage_index)
    both=plan['topic'] in {'group','copy','restore','paths'}
    draw.rounded_rectangle((95,535,900,1275),radius=32,fill='#162940',outline='#31506c',width=2)
    draw.text((130,575),'HASIL CONTOH' if preview else stage['title'].upper(),font=font(27,True),fill='#98e4d0')
    draw.line((130,640,865,640),fill='#31506c',width=2)
    panels=[(130,700,350,left_label,rows),(530,700,330,right_label,right)] if both else [(130,700,730,left_label,rows)]
    # Move icons and row order along actual state transitions instead of slides.
    for x,y,width,label,files in panels:
        wrapped(draw,label,x,y,width,28,fill='#a8bdd3',bold=True)
        if not files:
            draw.rounded_rectangle((x,y+90,x+width,y+275),radius=16,outline='#31506c',width=2)
            draw.text((x+25,y+155),'Kosong',font=font(29),fill='#7590aa')
        for index,row in enumerate(files):
            row_y=y+85+index*125
            row_x=x
            if stage_index==2 and part<.22 and not both:
                # Keep independent vertical lanes: interpolating old/new y
                # coordinates made crossing rows hide each other's names.
                elapsed=t-stage['start']-index*.08
                p=max(0,min(1,elapsed/.45));p=p*p*(3-2*p)
                row_x+=round(12*(1-p))
            selected=stage_index>=2 and (index==0 or plan['topic']=='group')
            color='#1f4855' if selected else '#203751'
            draw.rounded_rectangle((row_x,row_y,row_x+width,row_y+105),radius=14,fill=color)
            draw.rounded_rectangle((row_x+14,row_y+19,row_x+45,row_y+67),radius=4,
                fill={'photo':'#d7ab7d','video':'#b29be6','document':'#7db7d9'}[row['type']])
            label=row['label']
            if both:
                label=label.replace('_',' ').replace('.',' .')
                wrapped(draw,label,row_x+61,row_y+13,width-70,23,line_height=29)
                if row.get('detail'):
                    wrapped(draw,row['detail'],row_x+14,row_y+72,width-25,20,fill='#98e4d0',line_height=23)
            else:
                size_text=f'{row["size"]} MB'
                wrapped(draw,label,row_x+65,row_y+18,width-190,29,line_height=35)
                draw.text((row_x+width-100,row_y+37),size_text,font=font(24),fill='#a8bdd3')
    if both and stage_index>=2 and plan['topic']!='paths':
        arrow_x=476+9*math.sin(min(part/.3,1)*math.pi)
        draw.line((arrow_x,1045,arrow_x+40,1045),fill='#98e4d0',width=5)
        draw.polygon([(arrow_x+40,1045),(arrow_x+27,1034),(arrow_x+27,1056)],fill='#98e4d0')
    if plan['topic']=='paths':
        draw.text((477,1040),'≠',font=font(35,True),fill='#98e4d0')
    if not both:
        wrapped(draw,right_label,135,1160,700,27,fill='#98e4d0')
    cue=next((c for c in cues if c[0]<=t<c[1]),None)
    if cue:
        lines=cue[2].splitlines()
        y=1390
        for line in lines:
            face=font(plan.get('caption_font_size',52),True);width=draw.textlength(line,font=face)
            draw.text(((960-width)/2,y),line,font=face,fill='white',stroke_width=3,stroke_fill='#0b1728');y+=72
    for i in range(4):
        x=110+i*192
        draw.rounded_rectangle((x,1620,x+164,1626),radius=3,fill='#77d7bd' if i<=stage_index else '#2a4058')
    draw.text((110,1665),'Satu contoh. Satu langkah yang jelas.',font=font(26),fill='#8fa5be')
    return image


def frame(plan,t,cues):
    if plan.get('motion_version')==motion.VERSION:
        return motion.draw(plan,t,cues,state)
    return legacy_frame(plan,t,cues)


def render(plan,folder: Path,progress=lambda *args:None) -> Path:
    # Persisted legacy plans keep their renderer. New plans select Motlab and
    # stop before paid narration if its runtime is unavailable; no fallback.
    use_motlab=plan.get('render_engine')==motlab.ENGINE
    if plan.get('render_engine') not in (None,motlab.ENGINE):
        raise ValueError('Engine render Facebook tidak dikenal.')
    if use_motlab:motlab.require_motlab_runtime()
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'source-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2))
    if plan.get('education'):
        education.verify_plan(plan)
        narration,segments,length=voice(plan['stages'],folder,progress,
            voice_name=plan['narration_voice'],rate='-5%')
    else:narration,segments,length=voice(plan['stages'],folder,progress)
    if plan.get('motion_version')==motion.VERSION:
        plan['motion_timeline']=education.timeline(plan,segments) if plan.get('education') else motion.timeline(plan,segments)
    fps=motion.FPS if plan.get('motion_version')==motion.VERSION else FPS
    audio_design=None;sounds=None
    if (plan.get('creative_policy') or {}).get('version')==creative.VERSION:
        narration=normalize_narration(narration,folder/'narration-mix.wav',length)
        sounds=folder/'authored_ui_sounds.wav'
        audio_design=creative.synthesize_sounds(sounds,creative.sound_plan(plan,length),length)
        plan['sound_design']=audio_design
    # The executed timings are persisted as part of the exact generated source.
    (folder/'source-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2))
    cues=strategy.phrase_cues(segments,0,length)
    if not cues or any(b-a<.6 for a,b,_ in cues):
        raise ValueError('Caption terlalu cepat; hasil ditahan untuk perbaikan.')
    media=folder/'facebook_original.mp4'
    subtitle=media.with_suffix('.srt')
    subtitle.write_text('\n\n'.join(f'{i}\n{srt_time(a)} --> {srt_time(b)}\n{text}' for i,(a,b,text) in enumerate(cues,1))+'\n')
    renderer_stamp=None
    if use_motlab:
        silent,renderer_stamp=motlab.render(plan,cues,length,folder,state,progress)
        command=['ffmpeg','-v','error','-y','-i',str(silent),'-i',str(narration)]
    else:
        command=['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1080x1920','-r',str(fps),
            '-i','pipe:0','-i',str(narration)]
    graph=f'[0:v]{watermark_filter("vertical_short")}[v]'
    if sounds:
        command+=['-i',str(sounds),'-i',str(narration)]
        graph+=(';[1:a]anull[voice];'
                '[2:a][3:a]sidechaincompress=threshold=0.12:ratio=3:attack=5:release=120[ducked];'
                '[voice][ducked]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,'
                'alimiter=limit=0.84:level=false[a]')
    else:graph+=';[1:a]loudnorm=I=-16:TP=-1.5:LRA=9[a]'
    command+=['-filter_complex',graph,'-map','[v]','-map','[a]',
        '-c:v','libx264','-preset','fast','-crf','21','-threads','2','-pix_fmt','yuv420p',
        '-c:a','aac','-b:a','128k','-ar','48000','-t',str(length),'-movflags','+faststart',str(media)]
    log=folder/'render.log'
    try:
        with log.open('wb') as errors:
            process=subprocess.Popen(command,stdin=subprocess.DEVNULL if use_motlab else subprocess.PIPE,
                stdout=subprocess.DEVNULL,stderr=errors)
            try:
                if not use_motlab:
                    for index in range(math.ceil(length*fps)):
                        if index%fps==0:progress(40+int(index/(length*fps)*40),'render',f'Menggerakkan objek contoh · {index//fps}/{math.ceil(length)} detik')
                        process.stdin.write(frame(plan,index/fps,cues).tobytes())
                    process.stdin.close()
                if process.wait(timeout=180):raise ValueError('Encoding FB gagal; lihat log render lokal.')
            finally:
                if process.poll() is None:process.kill();process.wait()
    except BrokenPipeError:
        raise ValueError('Encoder FB berhenti sebelum selesai; file tidak diunggah.') from None
    progress(85,'qc','Memeriksa seluruh audio-video dan menyiapkan bukti QC')
    subprocess.run(['ffmpeg','-v','error','-xerror','-threads','1','-i',str(media),'-f','null','-'],
        capture_output=True,check=True,timeout=180)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(media)],timeout=30))
    issues=strategy.media_issues(probe)
    if issues:raise ValueError('; '.join(issues))
    thumbnail=media.with_name(media.stem+'_thumb.jpg')
    subprocess.run(['ffmpeg','-v','error','-y','-ss','1.8','-i',str(media),'-frames:v','1',str(thumbnail)],check=True,timeout=30)
    sidecar=dict(title=plan['title'],text=' '.join(s['text'] for s in plan['stages']),
        source_identity=plan['seed'],narrative_arc_complete=True,original_demo=plan,
        sound_design=audio_design,renderer=renderer_stamp,
        facebook={'version':strategy.VERSION,'caption':plan['caption'],'watermark':watermark_metadata('vertical_short')},
        render_quality_qc={'quality_gate_passed':True,'blocking':False,'full_decode_passed':True,
                           'frame_timestamps_seconds':[s['start']+.5 for s in plan['stages']]},
        render_source_sha256=qc.sha256(folder/'source-plan.json'),media_sha256=qc.sha256(media),
        output_duration_seconds=float(probe['format']['duration']),
        source_provenance={'kind':'authored_educational_animation' if plan.get('education') else 'authored_original_simulation','original_script_and_visuals':True,
                           'third_party_video':False,'music':False,'neural_narration':True,
                           'original_sound_effects':audio_design is not None},
        growth_readiness={'measured_retention':None,'predicted_score':None,'not_a_monetization_approval':True})
    if audio_design:
        sidecar['render_quality_qc']['frame_timestamps_seconds']=sorted({
            *sidecar['render_quality_qc']['frame_timestamps_seconds'],1.75,
            *[plan['stages'][2]['start']+shift for shift in (.8,1.5,2.0)],
            *[cue['start']+.1 for cue in audio_design['events']]})
    if plan.get('motion_version')==motion.VERSION:
        clock=plan['motion_timeline']
        scene=lambda t:education.scene(plan,t) if plan.get('education') else motion.scene(plan,t,state)
        sidecar['educational_motion']=dict(version=motion.VERSION,fps=fps,clock=clock,
            component='character_led_education' if plan.get('education') else 'persistent_objects_2d',labels_upright=True,
            initial=scene(plan['stages'][1]['start']+.5),
            result=scene(min(length-.5,plan['stages'][3]['start']+.4)))
        sidecar['render_quality_qc']['frame_timestamps_seconds']=sorted({
            *sidecar['render_quality_qc']['frame_timestamps_seconds'],.5,1.1,clock['select'],
            *[clock['departure']+(clock['arrival']-clock['departure'])*q for q in (.11,.22,.5,.78,.9)],
            clock['arrival']+.2,clock['inspect']+.5})
    media.with_suffix('.json').write_text(json.dumps(sidecar,ensure_ascii=False,indent=2))
    return media


def local_audio_review_cached(media,samples,subtitles):
    cache_path=media.with_suffix('.audio-qc.json')
    identity=dict(media_sha256=qc.sha256(media),subtitles_sha256=qc.sha256(media.with_suffix('.srt')),
                  windows=[{k:s[k] for k in ('start_seconds','duration_seconds')} for s in samples])
    cached={}
    try:cached=json.loads(cache_path.read_text())
    except (OSError,ValueError):pass
    if (cached.get('identity')==identity and isinstance(cached.get('review'),list)
            and len(cached['review'])==len(samples)
            and all(isinstance(row,dict) and row.get('method')=='local_whisper_medium_cpu_int8_actual_output_audio'
                    and row.get('recognized_text') and type(row.get('caption_overlap_f1')) in (int,float)
                    and row['caption_overlap_f1']>=.30 for row in cached['review'])):
        review=cached['review']
    else:
        review=qc.local_audio_evidence(samples,subtitles)
        # Evidence only, never an approval. Exact encoded media,
        # captions and windows must match before reusing recognition.
        from deployment_runtime import write_json
        write_json(cache_path,dict(identity=identity,review=review))
    return review


def audit(media: Path,job_id: str,clip_url: str,*,reviewer=None,repair_attempted=False) -> dict:
    """Independent semantic/visual/audio audit; unavailable services stay pending."""
    context=dict(source_job_id=job_id,source_clip_url=clip_url,repair_attempted=repair_attempted,score_floor_met=False)
    gates={key:False for key in qc.GATES}
    phase='deterministic'
    try:
        saved_path=media.with_suffix('.auto-qc.json')
        if saved_path.is_file():
            saved=json.loads(saved_path.read_text());previous=saved.get('audit') or {}
            if (saved.get('provider_http_status')==422 and previous.get('decision')=='DROP_SOURCE'
                    and previous.get('hard_gates',{}).get('context_safe') is False):
                return saved
        sidecar=json.loads(media.with_suffix('.json').read_text())
        source=media.parent/'source-plan.json'
        plan=json.loads(source.read_text())
        if sidecar.get('render_source_sha256')!=qc.sha256(source) or sidecar.get('media_sha256')!=qc.sha256(media):
            raise ValueError('Identitas media/rencana sumber berubah.')
        if plan!=sidecar.get('original_demo') or plan.get('version')!=VERSION or not plan.get('seed'):
            raise ValueError('Bukti sumber asli tidak lengkap.')
        if plan.get('render_engine')==motlab.ENGINE:
            motlab.verify_evidence(media.parent,sidecar.get('renderer'))
        gates['rights']=plan.get('third_party_footage') is False and plan.get('third_party_music') is False
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(media)],timeout=30))
        if strategy.media_issues(probe):raise ValueError('Format atau durasi FB tidak valid.')
        subprocess.run(['ffmpeg','-v','error','-xerror','-threads','1','-i',str(media),'-f','null','-'],capture_output=True,check=True,timeout=180)
        gates['media_integrity']=True
        if plan.get('education'):education.verify_plan(plan)
        gates['meaning_preserved']=plan['topic'] in topic_keys(plan.get('series','digital'))
        gates['context_safe']=True
        if not all(gates.values()):raise ValueError('Gerbang bukti sumber gagal.')
        if plan.get('motion_version')==motion.VERSION:
            stamp=sidecar.get('educational_motion') or {}
            if stamp.get('version')!=motion.VERSION or stamp.get('clock')!=plan.get('motion_timeline'):
                raise ValueError('Bukti timeline animasi objek belum cocok dengan sumber.')
        length=float(probe['format']['duration'])
        design=sidecar.get('sound_design')
        if (plan.get('creative_policy') or {}).get('version')==creative.VERSION:
            expected=creative.sound_plan(plan,length)
            if (not isinstance(design,dict) or design.get('version')!=1
                    or design.get('events')!=expected['events']
                    or design.get('sha256')!=qc.sha256(media.parent/'authored_ui_sounds.wav')
                    or design.get('ducked_under_voice') is not True):
                raise ValueError('Bukti sound effect belum cocok dengan timeline demonstrasi.')
        subtitles=media.with_suffix('.srt').read_text()
        cues=parse_srt(subtitles)
        # A semantic/visual audit is also mandatory. This is a measured format
        # suitability floor, not an invented viral/monetization prediction.
        context['score_floor_met']=bool(cues and len(plan['stages'])==4 and 26<=length<=55)
        frames=[]
        timestamps={.5,1.8,length/2,length-.8,*[s['start']+.5 for s in plan['stages']],
                    *(sidecar.get('render_quality_qc') or {}).get('frame_timestamps_seconds',[])}
        if len(timestamps)>48:raise ValueError('Terlalu banyak timestamp peringatan untuk satu audit.')
        for t in sorted(timestamps):
            output=subprocess.check_output(['ffmpeg','-v','error','-threads','1','-ss',str(t),'-i',str(media),
                '-frames:v','1','-vf','scale=540:-2','-threads','1','-f','image2pipe','-vcodec','mjpeg','-'],timeout=30)
            if not output:raise ValueError('Bingkai bukti hilang.')
            frames.append(dict(timestamp_seconds=round(t,3),data_url='data:image/jpeg;base64,'+base64.b64encode(output).decode()))
        samples=[]
        for t,span in audio_windows(length):
            output=subprocess.check_output(['ffmpeg','-v','error','-threads','1','-ss',str(t),'-i',str(media),
                '-t',str(span),'-vn','-ar','16000','-ac','1','-c:a','pcm_s16le','-f','wav','-'],timeout=30)
            samples.append(dict(start_seconds=t,duration_seconds=span,data=base64.b64encode(output).decode()))
        evidence=dict(target_platform='facebook',original_demo=True,job=context,plan=plan,
            media={'duration_seconds':length},output_subtitles=subtitles,audio_samples=samples,
            sound_design=design,
            education=plan.get('education'),
            originality_scope='Original educational cartoon, vector characters and synthetic narration.' if plan.get('education') else
                'Original script and animated demonstration; labelled simulation with synthetic narration.')
        phase='provider'
        config=provider_config()
        if config['audio_review_mode']=='local_whisper' and reviewer is None:
            evidence['local_audio_review']=local_audio_review_cached(media,samples,subtitles)
            evidence['audio_samples']=[]
        result=reviewer(evidence,frames) if reviewer else qc.vision_review(evidence,frames,config=config)
        decision=qc.validate_ai_result(result,context,gates,['Full media decode and generated source identity verified.'])
        if decision['decision']=='PASS_UPLOAD' and decision['confidence']<AUTO_CONFIDENCE_MIN:
            return dict(status='pending',message='Keyakinan QC belum mencapai ambang FB Pro 0.90.',audit=None)
        return dict(status='reviewed',fingerprint=audit_fingerprint(media,context),media_sha256=qc.sha256(media),
                    frame_timestamps_seconds=sorted(timestamps),audit=decision)
    except HTTPError as exc:
        detail=exc.read(1500).decode('utf-8',errors='replace')
        try:
            error=json.loads(detail).get('error',{})
            summary=error.get('message','') if isinstance(error,dict) else str(error)
            metadata=(error.get('metadata') or {}) if isinstance(error,dict) else {}
            if metadata.get('raw'):summary+=' '+str(metadata['raw'])[:600]
        except (ValueError,TypeError,AttributeError):summary=detail
        diagnostics=dict(provider_http_status=exc.code,
                         provider_error=qc.safe_error_detail(RuntimeError(summary)))
        if exc.code==422 and 'content safety screening' in detail.casefold():
            gates['context_safe']=False
            return dict(**diagnostics,status='reviewed',audit=qc._decision(context,gates=gates,
                evidence=['QC provider declined this source during content safety screening; no retry or publication.']))
        return dict(**diagnostics,status='pending',message=f'Layanan QC belum tersedia (HTTP {exc.code}); bukti tetap disimpan.',audit=None)
    except (ConnectionError,TimeoutError,PermissionError) as exc:
        return dict(status='pending',message=qc.safe_error_detail(exc),audit=None)
    except Exception as exc:
        if isinstance(exc,qc.ProviderRefusal):gates['context_safe']=False
        if isinstance(exc,qc.AudioCaptionMismatch):gates['media_integrity']=False
        if phase=='deterministic' or isinstance(exc,(qc.AudioCaptionMismatch,qc.ProviderRefusal)):
            return dict(status='reviewed',audit=qc._decision(context,gates=gates,evidence=[qc.safe_error_detail(exc)]))
        return dict(status='pending',message=qc.safe_error_detail(exc),audit=None,
                    error_type=type(exc).__name__,phase=phase,
                    trace=[dict(file=Path(f.filename).name,line=f.lineno,function=f.name)
                           for f in traceback.extract_tb(exc.__traceback__)])


def automatic_pass(media: Path,job_id: str,clip_url: str) -> bool:
    """No human-review flag is synthesized; only this exact generated media can pass."""
    path=media.with_suffix('.auto-qc.json')
    if not path.is_file():return False
    try:
        saved=json.loads(path.read_text())
        audit=saved.get('audit') or {}
        context=dict(source_job_id=job_id,source_clip_url=clip_url,repair_attempted=audit.get('repair_attempted') is True,score_floor_met=True)
        sidecar=json.loads(media.with_suffix('.json').read_text())
        if (sidecar.get('original_demo') or {}).get('render_engine')==motlab.ENGINE:
            motlab.verify_evidence(media.parent,sidecar.get('renderer'))
        return bool(saved.get('fingerprint')==audit_fingerprint(media,context)
            and saved.get('media_sha256')==qc.sha256(media) and audit.get('source_job_id')==job_id
            and sidecar.get('render_source_sha256')==qc.sha256(media.parent/'source-plan.json')
            and audit.get('source_clip_url')==clip_url and audit.get('decision')=='PASS_UPLOAD'
            and type(audit.get('confidence')) in (int,float) and AUTO_CONFIDENCE_MIN<=audit['confidence']<=1
            and audit.get('upload_allowed') is True and all(audit.get('hard_gates',{}).get(k) is True for k in qc.GATES)
            and all(audit.get('ai_checks',{}).get(k) is True for k in qc.CHECKS))
    except (OSError,ValueError,KeyError,TypeError):return False
