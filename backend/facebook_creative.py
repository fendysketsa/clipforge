"""Research-informed FB-only editorial experiments and authored, quiet UI sounds.

Weights are editorial starting points, not predictions or measured Facebook wins.
References remain private; no reference URL is appended to a public caption.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import wave

import numpy as np

VERSION = 2
NICHE = 'Digital sehari-hari untuk keluarga'
REFERENCES = {
    'meta_original': 'https://about.fb.com/news/2026/03/rewarding-original-creators-on-facebook/',
    'meta_performance': 'https://about.fb.com/news/2026/03/creator-fast-track-grow-your-audience-earn-money-on-facebook/',
    'meta_relevance': 'https://about.fb.com/news/2025/04/cracking-down-spammy-content-facebook/',
    'android_storage': 'https://support.google.com/android/answer/7431795?hl=id',
    'drive_search': 'https://support.google.com/drive/answer/2375114?hl=id',
}
PILLARS = {
    'storage': {'label':'File dan foto lebih rapi','weight':4,'topics':('size','group','search')},
    'everyday': {'label':'Langkah digital yang memudahkan','weight':4,'topics':('copy','rename','date','number')},
    'mistakes': {'label':'Hindari salah langkah','weight':2,'topics':('extension','restore','paths')},
}
HOOKS = {
    'size':'File besar tersembunyi? Urutkan dulu ukurannya.',
    'group':'Foto dan dokumen bercampur? Pisahkan tempatnya.',
    'search':'File belum terlihat? Coba kata yang spesifik.',
    'copy':'File disalin, aslinya masih di mana?',
    'rename':'Nama cuma angka? Tambahkan konteks yang jelas.',
    'date':'Tanggal rapi membuat urutan mudah dibaca.',
    'number':'Kenapa nomor sepuluh menyelip di tengah?',
    'extension':'Ganti nama belum berarti ganti format.',
    'restore':'Salah hapus? Periksa Sampah sebelum panik.',
    'paths':'Nama sama, folder berbeda. Periksa lokasinya.',
}
SETUPS = {
    'size':'Contoh ini memuat tiga file. Perhatikan ukuran, bukan panjang namanya.',
    'group':'Dalam contoh ini, satu catatan bercampur dengan dua foto kegiatan.',
    'search':'Pada contoh ini, kita mencari catatan kegiatan di antara tiga dokumen.',
    'copy':'Folder Asal memiliki satu catatan. Folder Cadangan masih kosong.',
    'rename':'Catatan contoh ini bernama umum, sehingga sulit dikenali dari daftar.',
    'date':'Tiga catatan contoh memiliki tanggal berbeda, tetapi urutan awalnya berantakan.',
    'number':'Nama contoh bernomor satu, sepuluh, dan dua tersusun sebagai teks.',
    'extension':'Berkas contoh bernama Catatan titik t x t berisi tulisan sederhana.',
    'restore':'Satu catatan contoh berada di Sampah, sementara folder Dokumen masih kosong.',
    'paths':'Contoh ini memiliki dua Catatan titik t x t pada folder berbeda.',
}


def hash_number(value):
    return int(hashlib.sha256(value.encode()).hexdigest()[:12],16)


def choose_topic(seed,available,recent=()):
    """Weighted exploration with topic diversity, without invented analytics."""
    allowed=set(available)-set(recent)
    if not allowed:allowed=set(available)
    bucket=hash_number(seed)%10
    pillar='storage' if bucket<4 else 'everyday' if bucket<8 else 'mistakes'
    pool=sorted(allowed.intersection(PILLARS[pillar]['topics'])) or sorted(allowed)
    return pool[hash_number(seed+':topic')%len(pool)]


def policy(topic,seed):
    pillar=next(key for key,value in PILLARS.items() if topic in value['topics'])
    return dict(version=VERSION,niche=NICHE,pillar=pillar,pillar_label=PILLARS[pillar]['label'],
        basis='editorial_hypothesis_not_measured_winner',
        format=('before_after','one_mistake_one_fix','one_question_one_demonstration')[hash_number(seed+':format')%3],
        reference_keys=['meta_original','meta_performance','meta_relevance',
                        'android_storage' if topic in {'size','group','restore'} else 'drive_search'],
        first_result_preview={'start':.35,'end':1.85,'label':'HASIL CONTOH'},
        captions_stable=True,source_clock_changed=False,views_guaranteed=False)


def brief():
    return dict(version=VERSION,niche=NICHE,pillars=[{'key':key,**value} for key,value in PILLARS.items()],
                evidence='Hipotesis editorial berbasis referensi; belum ada pemenang terukur dari akun FB ini.',
                references=REFERENCES,first_visual_seconds=2,animation='Objek 2D memperagakan tindakan dan hasil.',
                sound='Klik pemilihan, gerak objek, dan konfirmasi kedatangan di bawah narasi.')


def sound_plan(plan,duration):
    """Four accents tied to measured speech stages and visible UI events."""
    stages=plan['stages'];operation=stages[2]['start'];ending=stages[3]['start']
    events=[dict(kind='tap',start=.35,duration=.065,gain_db=-23,event='opening_result_preview'),
            dict(kind='tap',start=operation+.08,duration=.065,gain_db=-23,event='operation_selected'),
            dict(kind='swoosh',start=operation+.18,duration=.24,gain_db=-25,event='objects_change'),
            dict(kind='chime',start=ending+.12,duration=.38,gain_db=-24,event='complete_result_explained')]
    clock=plan.get('motion_timeline')
    if clock:
        events=[dict(kind='tap',start=.35,duration=.065,gain_db=-23,event='opening_question'),
                dict(kind='tap',start=clock['select'],duration=.065,gain_db=-23,event='object_selected'),
                dict(kind='swoosh',start=clock['departure'],duration=.24,gain_db=-25,event='object_travels'),
                dict(kind='chime',start=clock['arrival'],duration=.38,gain_db=-24,event='object_arrives')]
        if plan['topic']=='copy':
            events.append(dict(kind='tap',start=clock['inspect'],duration=.065,gain_db=-25,event='inspect_existing_copy'))
    events=[row for row in events if row['start']+row['duration']<duration-.1]
    return dict(version=1,author='ClipForge procedural UI synthesis',third_party_audio=False,
        attribution_required=False,music=False,narration_priority=True,ducked_under_voice=True,
        limiter_peak_dbfs=-1.5,inserted_timeline_seconds=0,
        events=[{**row,'start':round(row['start'],3)} for row in events])


def synthesize_sounds(path:Path,design:dict,duration:float):
    if not math.isfinite(duration) or not 0<duration<=55:raise ValueError('Invalid sound timeline')
    rate=48000;output=np.zeros(math.ceil(duration*rate),dtype=np.float64)
    for position,cue in enumerate(design['events']):
        start=int(cue['start']*rate);count=int(cue['duration']*rate)
        if start<0 or start+count>len(output):raise ValueError('Sound cue exceeds media timeline')
        t=np.arange(count,dtype=np.float64)/rate
        window=np.sin(np.linspace(0,np.pi,count))**2
        if cue['kind']=='tap':
            sample=(np.sin(2*np.pi*1450*t)+.3*np.sin(2*np.pi*2300*t))*np.exp(-65*t)
        elif cue['kind']=='swoosh':
            rng=np.random.default_rng(position)
            noise=rng.standard_normal(count)
            sample=np.convolve(noise,np.ones(16)/16,mode='same')*window
        elif cue['kind']=='chime':
            sample=(np.sin(2*np.pi*660*t)+.45*np.sin(2*np.pi*880*t))*np.exp(-9*t)
        else:raise ValueError('Unknown authored sound cue')
        sample*=window
        sample/=max(1e-9,float(np.max(np.abs(sample))))
        output[start:start+count]+=sample*10**(cue['gain_db']/20)
    if not np.isfinite(output).all() or np.max(np.abs(output))>.15:
        raise ValueError('UI sound exceeds narration-safe gain')
    with wave.open(str(path),'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(rate)
        stream.writeframes((np.clip(output,-1,1)*32767).astype('<i2').tobytes())
    return dict(**design,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),sample_rate=rate,
                generated_peak_dbfs=round(20*math.log10(max(1e-9,float(np.max(np.abs(output))))),2))
