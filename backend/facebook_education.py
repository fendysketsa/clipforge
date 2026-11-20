"""Original educational animation catalogue and narration-bound scene semantics."""
from copy import deepcopy
import hashlib
import math
import re
import json

VERSION=1
SERIES={
 'digital':dict(label='Digital sehari-hari',description='Demonstrasi file dan kebiasaan digital.',audience='Keluarga'),
 'kids_basics':dict(label='Belajar sambil bermain',description='Berhitung, mengenal bentuk, dan meneruskan pola.',audience='Anak 4–7 tahun'),
 'life_skills':dict(label='Cerita kebiasaan baik',description='Nara dan Bimo belajar merapikan mainan dan bergiliran.',audience='Anak dan keluarga'),
 'nature':dict(label='Sains di sekitar kita',description='Sebab dan akibat melalui tanaman serta bayangan.',audience='Anak dan keluarga'),
}
TOPICS={
 'count_objects':dict(series='kids_basics',title='Hitung apel bersama Nara',concept='Menghitung satu benda satu kali',anchors=['satu','dua','tiga']),
 'shape_match':dict(series='kids_basics',title='Rumah untuk tiga bentuk',concept='Mencocokkan bentuk yang sama',anchors=['lingkaran','segitiga','persegi']),
 'color_pattern':dict(series='kids_basics',title='Warna apa setelah ini?',concept='Pola merah dan biru bergantian',anchors=['merah','biru']),
 'tidy_toys':dict(series='life_skills',title='Main selesai, yuk rapikan',concept='Mengembalikan mainan ke kotaknya',anchors=['masukkan','kotak']),
 'take_turns':dict(series='life_skills',title='Sekarang giliran siapa?',concept='Meminta izin dan bergiliran bermain',anchors=['nara','bimo']),
 'plant_growth':dict(series='nature',title='Dari biji menjadi tunas',concept='Perubahan pertumbuhan digambarkan dengan waktu dipercepat',anchors=['akar','tunas','daun']),
 'shadow_light':dict(series='nature',title='Dari mana datangnya bayangan?',concept='Benda menghalangi cahaya dan membentuk bayangan',anchors=['cahaya','benda','bayangan']),
}
SCRIPTS={
 'count_objects':[
  'Ada berapa apel di meja Nara?',
  'Nara ingin menghitung apel. Kita mulai dari sebelah kiri, sambil memperhatikan apel yang sedang disorot.',
  'Satu. Dua. Tiga. Setiap angka diucapkan saat satu apel ditandai. Apel yang sudah dihitung tetap di tempatnya, jadi kita tidak menghitungnya lagi.',
  'Ada tiga apel semuanya. Sekarang lihat tanda pada ketiga apel itu. Menghitung menjadi lebih mudah ketika setiap benda dihitung satu kali. Kamu boleh mencoba bersama pendamping dengan benda yang aman.'
 ],
 'shape_match':[
  'Bentuk ini masuk ke rumah yang mana?',
  'Nara menemukan tiga keping mainan. Di papan ada tiga tempat dengan bentuk yang berbeda. Perhatikan garis di tepinya.',
  'Lingkaran masuk ke tempat yang bulat. Segitiga masuk ke tempat dengan tiga sisi. Persegi masuk ke tempat dengan empat sisi yang sama panjang.',
  'Semua keping sekarang memiliki pasangan. Kita mencocokkan bentuknya, bukan hanya warnanya. Coba tunjuk keping yang bulat, lalu cari yang memiliki tiga sisi. Tidak perlu terburu-buru saat memperhatikan perbedaannya.'
 ],
 'color_pattern':[
  'Merah, biru. Warna apa setelah ini?',
  'Bimo sedang menyusun keping besar di papan. Dua warna dipakai bergantian, sehingga urutannya dapat kita perhatikan bersama.',
  'Merah, biru, merah, biru. Setelah keping biru, Bimo menambahkan keping merah. Lalu satu keping biru menyusul. Urutan dua warna tadi diulang lagi.',
  'Sekarang polanya menjadi lebih panjang. Aturannya tetap sama, yaitu merah dan biru bergantian. Perhatikan bagian yang berulang sebelum menebak keping berikutnya. Kamu bisa menunjukkan jawabannya sambil melihat susunan di papan.'
 ],
 'tidy_toys':[
  'Main selesai. Mainannya pulang ke mana?',
  'Nara dan Bimo selesai bermain. Tiga balok masih berada di lantai, sedangkan kotak mainan di samping mereka masih kosong.',
  'Nara mengambil balok yang pertama. Masukkan ke kotak, lalu susul dengan dua balok lainnya. Bimo ikut membantu. Mereka melihat setiap balok berpindah dari lantai ke dalam kotak.',
  'Lantainya sekarang rapi dan ketiga balok ada di kotak. Mainannya kembali ke tempatnya. Setelah bermain, kita bisa merapikan bersama. Mintalah bantuan pendamping untuk benda yang berat atau sulit dijangkau.'
 ],
 'take_turns':[
  'Satu mainan. Bagaimana bermain bersama?',
  'Nara sedang bermain dengan mobil mainan. Bimo juga ingin mencoba. Bimo mendekat dan meminta izin, lalu menunggu jawaban Nara.',
  'Nara menyelesaikan gilirannya. Setelah setuju, Nara menyerahkan mobil kepada Bimo. Sekarang Bimo bermain, dan Nara menunggu. Mobilnya tetap satu.',
  'Bergiliran memberi kesempatan untuk keduanya. Mintalah dengan sopan. Dengarkan jawaban teman, lalu sepakati giliran. Kalau belum sepakat, mintalah bantuan pendamping. Bermain bersama tidak perlu merebut mainan.'
 ],
 'plant_growth':[
  'Bagaimana biji berubah menjadi tanaman kecil?',
  'Nara mengamati biji yang tumbuh. Waktu pada animasi dipercepat, supaya perubahannya mudah terlihat.',
  'Akar tumbuh ke bawah. Tunas muncul ke atas. Kemudian daun mulai membuka. Tanah mendapat air secukupnya, dan bagian tanaman di atas tanah menerima cahaya.',
  'Tanaman kecil sekarang memiliki akar, batang, dan daun. Pertumbuhan aslinya memerlukan waktu. Kebutuhan setiap jenis tanaman bisa berbeda. Amati bersama pendamping, lalu catat perubahannya dari hari ke hari.'
 ],
 'shadow_light':[
  'Mengapa ada bayangan di belakang benda?',
  'Bimo melihat lampu menyala menuju layar putih. Sebuah balok akan dipindahkan ke jalur cahayanya.',
  'Cahaya bergerak menuju layar. Benda berupa balok masuk ke jalur cahaya. Di belakang balok, sebagian cahaya terhalang. Pada layar muncul daerah lebih gelap yang disebut bayangan.',
  'Saat balok digeser keluar, bayangan menghilang. Balok tadi menghalangi cahaya menuju layar. Perhatikan posisi lampu, benda, dan layar. Amati bersama pendamping, tanpa menatap lampu yang menyilaukan.'
 ],
}


def catalogue(digital_topics=()):
    return [dict(key=key,**series,topics=(list(digital_topics) if key=='digital' else
        [dict(key=topic,title=row['title']) for topic,row in TOPICS.items() if row['series']==key]))
        for key,series in SERIES.items()]


def topic_keys(series):
    if series not in SERIES:raise ValueError('Seri animasi tidak tersedia.')
    return [key for key,row in TOPICS.items() if row['series']==series]


def plan(seed,kind,topic,series):
    choices=topic_keys(series)
    if topic is None:topic=choices[int(hashlib.sha256(seed.encode()).hexdigest()[:8],16)%len(choices)]
    if topic not in choices:raise ValueError('Topik tidak sesuai dengan seri animasi.')
    spec=TOPICS[topic]
    # Vary the lead character while keeping narration and the on-screen cast in
    # agreement. All dialogue is curated source text, never executable AI code.
    swap=int(hashlib.sha256((seed+':cast').encode()).hexdigest()[:8],16)%2==1
    lines=deepcopy(SCRIPTS[topic]);title=spec['title']
    if swap:
        lines=[s.replace('Nara','TEMP_NAME').replace('Bimo','Nara').replace('TEMP_NAME','Bimo') for s in lines]
        title=title.replace('Nara','Bimo')
    result=dict(version=1,seed=seed,kind=kind,topic=topic,series=series,title=title,
        stages=[dict(title=title,text=text) for title,text in zip(('Pertanyaan','Kenali','Coba bersama','Lihat hasil'),lines)],
        files=[],caption=title+'. '+spec['concept']+'.\n\n#BelajarBersama #AnimasiEdukasi',
        visual_type='authored_educational_animation',third_party_footage=False,third_party_music=False,
        synthetic_voice=True,narration_provider='edge_neural_id-ID-GadisNeural',narration_voice='id-ID-GadisNeural',
        render_engine='motlab',motion_version=1,
        education=dict(version=VERSION,series=series,concept=spec['concept'],audience=SERIES[series]['audience'],
            characters=['Bimo','Nara'] if swap else ['Nara','Bimo'],original_characters=True,
            scientific_time_compressed=topic=='plant_growth',curated_script=True),
        creative_policy=dict(version=2,niche=SERIES[series]['label'],pillar=series,pillar_label=SERIES[series]['label'],
            basis='authored_learning_objective',format='character_led_object_demonstration',
            captions_stable=True,first_result_preview=None,source_clock_changed=False,views_guaranteed=False))
    result['plan_sha256']=hashlib.sha256(json.dumps(result,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return result


def verify_plan(value):
    expected=plan(value['seed'],value['kind'],value['topic'],value['series'])
    if (value.get('education')!=expected['education'] or value.get('title')!=expected['title']
            or [s['text'] for s in value['stages']]!=[s['text'] for s in expected['stages']]
            or value.get('third_party_footage') is not False or value.get('third_party_music') is not False
            or value.get('render_engine')!='motlab'):
        raise ValueError('Bukti naskah dan konsep edukasi belum sesuai dengan animasi.')


def timeline(plan,segments=()):
    import facebook_motion as motion
    clock=motion.timeline(plan,segments)
    start,end=plan['stages'][2]['start'],plan['stages'][2]['end']
    words=TOPICS[plan['topic']]['anchors']
    if plan['topic']=='take_turns':words=[plan['education']['characters'][0].casefold(),plan['education']['characters'][1].casefold()]
    found=[motion.anchor(plan['stages'],segments,2,r'\b'+re.escape(word)+r'\b',start+(end-start)*(.15+i*.65/max(1,len(words)-1))) for i,word in enumerate(words)]
    # Preserve measured order. The fixed script speaks labels in this order.
    clock['reveals']=[round(max(found[:i+1]),3) for i in range(len(found))]
    clock['select']=round(max(start,clock['reveals'][0]-.25),3)
    clock['departure']=clock['reveals'][0]
    clock['arrival']=round(min(end-.05,clock['reveals'][-1]+1.0),3)
    if plan['topic'] in {'tidy_toys','color_pattern','take_turns','shadow_light'}:
        clock['arrival']=round(end-.05,3)
    clock['complete']=round(end,3)
    if plan['topic']=='color_pattern':
        clock['pattern_add']=[motion.anchor(plan['stages'],segments,2,pattern,start+(end-start)*fallback)
            for pattern,fallback in ((r'\bmenambahkan\b',.48),(r'\bmenyusul\b',.72))]
    if plan['topic']=='take_turns':
        clock['handover_start']=motion.anchor(plan['stages'],segments,2,r'\bmenyerahkan\b',start+(end-start)*.3)
        clock['handover_end']=max(clock['handover_start']+.7,
            motion.anchor(plan['stages'],segments,2,r'\bsekarang\b',start+(end-start)*.85))
    if plan['topic']=='shadow_light':
        clock['block_enter']=motion.anchor(plan['stages'],segments,2,r'\bbenda\b',start+.6)
        clock['block_return']=motion.anchor(plan['stages'],segments,3,r'\bdigeser\b',plan['stages'][3]['start'])
    return clock


def scene(plan,t):
    import facebook_motion as motion
    clock=plan['motion_timeline'];start,end=plan['stages'][2]['start'],plan['stages'][2]['end']
    q=motion.ease((t-start)/max(.1,end-start));complete=t>=end
    reveals=clock['reveals'];n=sum(t>=at for at in reveals)
    topic=plan['topic'];props=[]
    if topic=='count_objects':
        props=[dict(id=f'apple-{i}',kind='apple',x=270+i*270,y=850,active=i<n) for i in range(3)]
        learning=dict(count=n,total=3)
    elif topic=='shape_match':
        kinds=['circle','triangle','square']
        for i,kind in enumerate(kinds):
            at=reveals[i];p=motion.ease((t-at)/1.0)
            props.append(dict(id=kind,kind=kind,x=270+i*270,y=760-170*p,active=t>=at,placed=p>=1))
        learning=dict(matched=sum(p['placed'] for p in props),total=3)
    elif topic=='color_pattern':
        # First four pieces stay visible; the last two arrive on the narrated
        # words "menambahkan keping merah" and "biru menyusul".
        for i in range(6):
            at=clock['pattern_add'][max(0,i-4)]
            p=1 if i<4 else motion.ease((t-at)/.8)
            props.append(dict(id=f'piece-{i}',kind='bead',x=200+(i%3)*330,y=720+(i//3)*180-160*(1-p),
                color='#ef7e73' if i%2==0 else '#65a9dc',active=p>=1,visible=i<4 or t>=at))
        learning=dict(pattern=['red','blue']*3)
    elif topic=='tidy_toys':
        for i in range(3):
            p=motion.ease((q-i*.2)/.55)
            props.append(dict(id=f'block-{i}',kind='block',x=320+i*160+(710-320-i*160)*p,
                y=1030-(i%2)*40-210*math.sin(math.pi*p)-140*p,placed=p>=1))
        learning=dict(floor=sum(not p['placed'] for p in props),box=sum(p['placed'] for p in props),total=3)
    elif topic=='take_turns':
        p=motion.ease((t-clock['handover_start'])/(clock['handover_end']-clock['handover_start']))
        props=[dict(id='shared-car',kind='car',x=350+380*p,y=920-80*math.sin(math.pi*p))]
        learning=dict(owner=plan['education']['characters'][int(p>=1)],total=1)
    elif topic=='plant_growth':
        learning=dict(root=motion.ease((t-reveals[0])/1.0),stem=motion.ease((t-reveals[1])/1.0),
            leaves=motion.ease((t-reveals[2])/1.0),time_compressed=True)
    else:
        p=motion.ease((t-clock['block_enter'])/1.5)*(1-motion.ease((t-clock['block_return'])/1.5))
        props=[dict(id='opaque-block',kind='block',x=540,y=1060-240*p)]
        learning=dict(blocking=p,shadow=p>.05)
    return dict(topic=topic,series=plan['series'],props=props,learning=learning,
        characters=plan['education']['characters'],phase=0 if t<start else 1 if not complete else 2,
        complete=complete,clock=clock)
