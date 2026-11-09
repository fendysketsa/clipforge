"""Small, source-timed accents for cron exports only; no retiming or audio edits."""
from __future__ import annotations
import hashlib
from functools import lru_cache
import json
import math
from pathlib import Path
import re
import subprocess

POLICY_VERSION = 2
MOODS = {
    'surprise': ('impact_burst', 'ripple'),
    'delight': ('sparkle', 'ripple'),
    'action': ('speed_streak', 'impact_burst'),
    'question': ('orbit', 'focus_brackets'),
    'realization': ('swoosh', 'sparkle'),
    'celebration': ('sparkle', 'comic_rays'),
    'humor': ('comic_rays', 'orbit'),
    'emphasis': ('focus_brackets', 'ripple'),
    'calm': ('edge_focus', 'focus_brackets'),
}
SIGNALS = (
    ('surprise', r'\b(wah|waduh|astaga|kaget|terkejut|meledak|kena|pukul|gawat)\b'),
    ('delight', r'\b(enak|lezat|nikmat|cantik|indah|mantap|gurih|renyah)\b'),
    ('action', r'\b(lari|kejar|cepat|lompat|loncat|hindari|menyerang|gerak|belok)\b'),
    ('realization', r'\b(ternyata|rupanya|akhirnya|padahal|berubah|ketahuan)\b'),
    ('celebration', r'\b(berhasil|menang|selamat|lolos|juara)\b'),
    ('humor', r'\b(haha|hahaha|tertawa|lucu|kocak|ngakak)\b'),
    ('question', r'\b(kenapa|mengapa|bagaimana|gimana|apakah|kok)\b'),
    ('emphasis', r'\b(ingat|penting|perhatikan|lihat|kuncinya|jadi|sebab|karena)\b'),
)
SENSITIVE = re.compile(r'\b(ayat|hadis|hadits|quran|al.?qur.?an|doa|allah|ustaz|ustadz|salat|shalat|ibadah|duka|meninggal|korban|tragedi|kecelakaan|tewas|bencana|terluka|kanker|pengungsi|pemerkosaan|bunuh diri|tuduhan|korupsi|fatwa)\b', re.I)
PALETTES = [(255, 245, 220), (125, 240, 217), (255, 210, 100), (157, 208, 255)]
QUALIFIERS = re.compile(r'\b(tidak|bukan|belum|jangan|kurang|enggak|nggak|gak|tak|hanya|cuma|diduga|menurut|menurutnya|menurutku|katanya|kataku|kata|bilang|ujar|mungkin|sepertinya|konon|kalau|jika|seandainya|misalnya|seolah|bisa|akan|ingin|mau)\b', re.I)
STATEMENT_SIGNAL = re.compile(r'\b(takut|jangan|harus|bukan|tidak|belum|ingat|penting|kuncinya|ternyata|rupanya|akhirnya|enak|lezat|gurih|mantap|berhasil|menang|gagal|bahaya|numpuk)\b', re.I)


def _text(value):
    return ' '.join(re.findall(r'\w+', str(value).casefold()))


def _seed(*values):
    return int.from_bytes(hashlib.sha256('|'.join(map(str, values)).encode()).digest()[:8], 'big')


def validate_beats(raw):
    """A model chooses a mood and exact phrase, never coordinates/filter code."""
    if not isinstance(raw, list):
        return []
    return [dict(quote=row['quote'].strip()[:180], mood=row['mood'],
        statement=row.get('statement', '').strip()[:100] if isinstance(row.get('statement'), str) else '')
        for row in raw[:4] if isinstance(row, dict)
        and isinstance(row.get('quote'), str) and 2 <= len(_text(row['quote']).split()) <= 24
        and isinstance(row.get('mood'), str) and row['mood'] in MOODS]


def statement_phrase(quote, proposed='', *, sensitive=False):
    """Emphasize a source phrase without dropping denial, attribution or conditions."""
    if sensitive or '?' in quote or re.search(r'\b(kenapa|mengapa|apakah|bagaimana|gimana)\b', quote, re.I):
        return ''
    words = re.findall(r'\w+', quote)
    proposed_words = _text(proposed).split() if proposed else words
    if not proposed and not STATEMENT_SIGNAL.search(quote):
        return ''
    if not proposed and (quote.rstrip().endswith('...') or (len(words)>4 and not re.search(r'[.!]\s*$',quote))):
        return ''  # A short subtitle fragment is not automatically a complete statement.
    if not 2 <= len(proposed_words) <= 8 or len(' '.join(proposed_words)) > 58:
        return ''
    normalized = [word.casefold() for word in words]
    wanted = [word.casefold() for word in proposed_words]
    start = next((i for i in range(len(words)-len(wanted)+1) if normalized[i:i+len(wanted)] == wanted), None)
    if start is None:
        return ''
    phrase = ' '.join(words[start:start+len(wanted)])
    if len(set(wanted)) < 2 or wanted[-1] in {'bukan','tidak','belum','jangan','yang','dan','atau','karena',
            'kalau','jika','kepada','dengan','sebagai','menurut','diduga','kak','si','sang'}:
        return ''
    # Retain a source's qualification even when the director prefers a shorter hook.
    if set(_text(token) for token in QUALIFIERS.findall(quote)) - set(_text(phrase).split()):
        return ''
    return phrase


def build_plan(clip, segments, direction=None, *, enabled=False, budget=2, seed=''):
    plan = dict(version=POLICY_VERSION, cron_only=True, enabled=bool(enabled), required=bool(enabled and budget),
        rendered=False, cues=[], source_clock_unchanged=True, captions_clock_unchanged=True,
        audio_unchanged=True, inserted_timeline_seconds=0, reason='manual_job' if not enabled else 'chapter_not_selected')
    if not enabled or budget <= 0:
        return plan
    duration = float(clip.end - clip.start)
    if not math.isfinite(duration) or duration < .8:
        raise ValueError('Cron accent requires a finite source interval')
    direction = direction or {}
    sensitive = bool(SENSITIVE.search(clip.text) or direction.get('safety_override_applied'))
    limit = 1 if sensitive or duration < 25 else min(2, int(budget))
    salt = _seed(seed, clip.start, clip.end, clip.text)
    proposals = validate_beats(direction.get('accent_beats'))
    rows = []
    for row in segments:
        start, end = float(row.start), float(row.end)
        if not math.isfinite(start + end) or end <= start or end <= clip.start or start >= clip.end:
            continue
        if start < clip.start - .05 or end > clip.end + .05:
            continue
        quote = str(row.text).strip()
        anchor = ''
        proposed_statement = ''
        mood, weight, owner = 'emphasis', 1, 'source_sentence'
        for proposed in proposals:
            if _text(proposed['quote']) in _text(quote):
                mood, weight, owner = proposed['mood'], 15, 'creative_director_exact_quote'
                anchor = proposed['quote']
                proposed_statement = proposed['statement']
                break
        else:
            for category, pattern in SIGNALS:
                match = re.search(pattern, quote, re.I)
                if match:
                    mood, weight = category, 8
                    anchor = match.group()
                    break
        if mood in {'delight','celebration','humor','action'} and re.search(r'\b(tidak|belum|gagal|jangan|kurang|enggak|nggak|gak)\b(?:\W+\w+){0,3}\W+(enak|lezat|nikmat|berhasil|menang|lolos|tertawa|lucu|lari|kejar)', quote, re.I):
            mood = 'emphasis'
        offset = max(0, _text(quote).find(_text(anchor))) / max(1, len(_text(quote))) if anchor else 0
        relative = max(0., start - clip.start + (end-start)*offset)
        # Keep the cover and final syllable clear; align within the utterance.
        at = min(max(1.6, relative + min(.22, (end-start)*.12)), duration - .85)
        at = max(.12, at)
        statement = statement_phrase(quote, proposed_statement, sensitive=sensitive)
        rows.append((max(weight,8)+2 if statement else weight, _seed(salt, quote), at, quote, 'calm' if sensitive else mood, owner, statement))
    if not rows:
        rows = [(0, salt, max(.12, min(duration-.8, duration*(.30+(salt%20)/100))), '', 'calm' if sensitive else 'emphasis', 'quiet_fallback_no_timed_dialogue', '')]
    selected = []
    for _, _, at, quote, mood, owner, statement in sorted(rows, key=lambda row: (-row[0], row[1])):
        if any(abs(at-c['start']) < 5 for c in selected):
            continue
        variants = MOODS[mood]
        used = {c['kind'] for c in selected}
        options = [kind for kind in variants if kind not in used] or list(variants)
        kind = options[_seed(salt, quote, len(selected)) % len(options)]
        span = .95 if mood == 'calm' else .68 if kind in {'impact_burst', 'speed_streak'} else .82
        end = min(duration-.04, at+span)
        if statement and not any(c.get('statement') for c in selected) and duration-at >= 1.2:
            end = min(duration-.04, at+min(2., 1.2+len(statement.split())*.09))
        else:
            statement = ''
        selected.append(dict(kind=kind, mood=mood, start=round(at,3), end=round(end,3), quote=quote[:220],
            statement=statement, statement_rendered=False,
            directed_by=owner, timing_method='estimated_phrase_offset_within_timed_source_segment', palette=list(PALETTES[_seed(salt, quote)%len(PALETTES)]),
            variation=_seed(salt, quote)%360, source_grounded=bool(quote), sound='none'))
        if len(selected) >= limit:
            break
    selected.sort(key=lambda cue: cue['start'])
    plan.update(cues=selected, reason='source_timed_director_accents', required_min_count=1,
        cue_count=len(selected), sensitive_context=sensitive, seeded_variation=True)
    return plan


def compilation_parts(candidates, roles):
    """Spend the Long's two accents across at most two meaningful chapters."""
    if not candidates:
        return set()
    ranked = []
    for i, clip in enumerate(candidates):
        weight = sum(bool(re.search(pattern, clip.text, re.I)) for _, pattern in SIGNALS)
        weight += 3 if i < len(roles) and roles[i] in {'payoff','reveal','climax','resolution'} else 0
        ranked.append((weight, float(clip.score), _seed(clip.text, clip.start), i+1))
    return {row[-1] for row in sorted(ranked, reverse=True)[:min(2, len(ranked))]}


def follow_copy(clip):
    """An honest topical invitation, without promising a nonexistent sequel."""
    text=f'{clip.text} {getattr(clip,"title","")}'.casefold()
    choices=[
        (r'\b(roblox|gameplay|mabar|obby|minecraft)\b','CERITA & GAMEPLAY LAINNYA','Ikuti untuk cerita dan gameplay lain'),
        (r'\b(makanan|kuliner|warung|masakan|gurih|lezat|restoran)\b','ULASAN KULINER LAINNYA','Ikuti untuk ulasan kuliner lainnya'),
        (r'\b(kajian|allah|quran|ibadah|ustaz|ustadz|hikmah)\b','HIKMAH & PENGINGAT LAINNYA','Ikuti untuk hikmah dan pengingat lain'),
        (r'\b(berita|kebijakan|pemerintah|pemilu)\b','KONTEKS & PEMBAHASAN LAINNYA','Ikuti untuk konteks dan pembahasan lain'),
        (r'\b(tips|cara|langkah|tutorial)\b','TIPS & PENJELASAN LAINNYA','Ikuti untuk tips dan penjelasan lain'),
    ]
    for pattern,support,prompt in choices:
        if re.search(pattern,text):break
    else:
        support,prompt='CERITA & KLIP LAINNYA','Ikuti untuk cerita dan klip lainnya'
    if SENSITIVE.search(text) and not re.search(r'\b(kajian|allah|quran|ibadah|ustaz|ustadz|hikmah)\b',text):
        support,prompt='TERIMA KASIH SUDAH MENYIMAK','Ikuti untuk pembahasan lainnya'
    return dict(action='FOLLOW',headline='SUKA KLIP SEPERTI INI?',support=support,prompt=prompt)


def follow_plan(clip, segments, accents, *, enabled=False, protected_layout=False, protect_ending=True):
    plan=dict(enabled=False,cron_only=True,repeat_count=0,silent=True,extends_video_duration=False)
    if not enabled or protected_layout or clip.end-clip.start<12:
        return dict(plan,reason='manual_disabled_protected_layout_or_too_short')
    duration=float(clip.end-clip.start)
    windows=[(cue['start']-.35,cue['end']+.35) for cue in accents.get('cues',[])]
    def clear(at,end):
        return all(end<=a or at>=b for a,b in windows)
    if not protect_ending and clear(duration-2.05,duration-.30):
        at=duration-2.05;position='ending';owner='after_complete_source_value'
    else:
        low,high=max(4.2,duration*.28),duration*.64
        boundaries=[float(row.end)-clip.start+.12 for row in segments
                    if clip.start<=float(row.start)<float(row.end)<=clip.end]
        candidates=[(t,'source_sentence_boundary') for t in boundaries if low<=t<=high]
        candidates.extend((low+(high-low)*i/8,'safe_time_after_initial_value') for i in range(9))
        candidates.sort(key=lambda row: (row[1]!='source_sentence_boundary',abs(row[0]-duration*.43)))
        chosen=next(((t,method) for t,method in candidates if t+1.75<=duration-2.4 and clear(t,t+1.75)),None)
        if not chosen:return dict(plan,reason='no_clear_window_without_covering_statement_or_payoff')
        at,owner=chosen;position='middle'
    return dict(plan,enabled=True,version=1,repeat_count=1,start=round(at,3),end=round(at+1.75,3),
                position=position,timing_method=owner,copy=follow_copy(clip),avoids_director_accents=True)


def _probe(path, ffprobe='ffprobe'):
    result = subprocess.run([ffprobe,'-v','error','-show_entries','format=duration:stream=codec_type,width,height,nb_frames,r_frame_rate,duration','-of','json',str(path)],check=True,capture_output=True,text=True,timeout=30)
    data = json.loads(result.stdout)
    video = next(s for s in data['streams'] if s['codec_type']=='video')
    fps = video['r_frame_rate'].split('/')
    return dict(width=video['width'], height=video['height'], duration=float(video.get('duration') or data['format']['duration']),
        frames=int(video['nb_frames']) if video.get('nb_frames','N/A') != 'N/A' else None,
        fps=float(fps[0])/max(1.,float(fps[1])))


def _overlaps(a,b):
    return a[0]<b[0]+b[2] and b[0]<a[0]+a[2] and a[1]<b[1]+b[3] and b[1]<a[1]+a[3]


def place_cues(plan, video, *, ffmpeg='ffmpeg', layout=None):
    """Look at the FINAL framing, not guessed coordinates in the raw source."""
    from PIL import Image, ImageChops, ImageFilter, ImageStat
    import io
    layout = layout or {}
    meta = _probe(video)
    w,h = meta['width'],meta['height']
    portrait = h>w
    panel = layout.get('portrait') or {}
    rect = ((panel.get('canvas_width',1080)-panel.get('panel_width',1024))/2/panel.get('canvas_width',1080), panel['panel_y']/panel.get('canvas_height',1920), panel.get('panel_width',1024)/panel.get('canvas_width',1080), panel['panel_height']/panel.get('canvas_height',1920)) if panel.get('layout')=='landscape_in_portrait' else (0.,0.,1.,1.)
    protected = [(0.,0.,1.,.18),(.82,.70,.18,.30),(.08,.72,.84,.28)] if portrait else [(0.,0.,1.,.16),(.05,.77,.90,.23)]
    if layout.get('caption_position')=='upper': protected.append((.08,.13,.84,.20))
    if layout.get('caption_position')=='center': protected.append((.08,.36,.84,.28))
    complex_layout = any(layout.get(key) for key in ('evidence','social_card','reaction_avatar','multi_split')) or panel.get('layout')=='synchronized_conversation_split'
    for cue in plan['cues']:
        samples=[]
        for t in [max(0.,cue['start']-.10), (cue['start']+cue['end'])/2, cue['end']]:
            raw=subprocess.run([ffmpeg,'-v','error','-threads','1','-ss',str(t),'-i',str(video),'-frames:v','1','-vf','scale=540:-2','-threads','1','-f','image2pipe','-vcodec','mjpeg','-'],check=True,capture_output=True,timeout=30).stdout
            samples.append(Image.open(io.BytesIO(raw)).convert('RGB'))
        guards=list(protected)
        face_count=0
        try:
            import cv2
            import numpy as np
            detector=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
            for frame in samples:
                faces=detector.detectMultiScale(cv2.cvtColor(np.asarray(frame),cv2.COLOR_RGB2GRAY),scaleFactor=1.1,minNeighbors=4,minSize=(24,24))
                for x,y,fw,fh in faces:
                    guards.append((max(0,x/frame.width-.035),max(0,y/frame.height-.035),fw/frame.width+.07,fh/frame.height+.07));face_count+=1
        except Exception as exc:
            # Face detection is optional; a conservative geometric guard remains.
            cue['face_detector_fallback']=type(exc).__name__
        if not face_count:
            guards.append((rect[0]+rect[2]*.28, rect[1]+rect[3]*.05, rect[2]*.44, rect[3]*.51))
        radius=max(18,round(min(w*rect[2],h*rect[3])*(.14 if cue['kind']=='impact_burst' else .11)))
        side=radius*2+12
        candidates=[]
        for j,(rx,ry) in enumerate([(.17,.58),(.80,.57),(.18,.78),(.78,.78),(.13,.30),(.85,.31),(.20,.48),(.76,.48),(.17,.64),(.79,.64)]):
            cx,cy=rect[0]+rect[2]*rx,rect[1]+rect[3]*ry
            box=(cx-side/2/w,cy-side/2/h,side/w,side/h)
            if box[0]<.015 or box[0]+box[2]>.95 or box[1]<.18 or (portrait and box[1]+box[3]>.72) or any(_overlaps(box,g) for g in guards):
                continue
            a,b=samples[0],samples[-1]
            crop=(int(box[0]*a.width),int(box[1]*a.height),int((box[0]+box[2])*a.width),int((box[1]+box[3])*a.height))
            motion=ImageStat.Stat(ImageChops.difference(a.crop(crop),b.crop(crop)).convert('L')).mean[0]
            detail=ImageStat.Stat(a.crop(crop).filter(ImageFilter.FIND_EDGES).convert('L')).mean[0]
            candidates.append((motion+detail*.2+((_seed(cue['variation'],j)%100)/1000),box))
        if complex_layout or not candidates or cue['kind']=='edge_focus':
            cue.update(kind='edge_focus',box=[.012,.28,.035,.14],radius=radius,placement_reason='quiet_outer_margin_keeps_faces_captions_evidence_clear')
        else:
            box=max(candidates,key=lambda item:item[0])[1]
            cue.update(box=[round(v,6) for v in box],radius=radius,placement_reason='measured_motion_detail_outside_protected_regions')
        cue['protected_regions']=[list(g) for g in guards]
        cue['face_samples']=face_count
        if cue.get('statement') and not complex_layout:
            # Wide typography has its own clearance check, separate from the small accent.
            bw, bh = (.76, .14) if portrait else (.50, .19)
            positions = [(.10,.56),(.10,.58),(.10,.19)] if portrait else [(.25,.57),(.25,.20)]
            boxes = [(x,y,bw,bh) for x,y in positions
                if not any(_overlaps((x,y,bw,bh), guard) for guard in guards)]
            if boxes:
                cue.update(accent_kind=cue['kind'],kind='statement_focus',box=list(boxes[0]),
                    placement_reason='source_statement_outside_faces_and_caption_guards',
                    statement_style='comic' if cue['mood'] in {'surprise','action','humor','celebration'} else 'clean')
            else:
                cue['statement_skip_reason']='no_clear_typography_area'
        elif cue.get('statement'):
            cue['statement_skip_reason']='protected_evidence_or_split_layout'
    plan['canvas']=[w,h]
    return meta


def effect_frame(kind, side, progress, color, variation=0):
    """Authored vector-like poses with transparent centers and soft entry/exit."""
    from PIL import Image,ImageDraw,ImageFilter
    size=side*2
    im=Image.new('RGBA',(size,size),(0,0,0,0));d=ImageDraw.Draw(im)
    p=max(0.,min(1.,progress));alpha=round(235*min(1.,p/.13,(1-p)/.25))
    rgba=tuple(color)+(max(0,alpha),);white=(255,255,249,max(0,alpha))
    c=size/2;r=size*.34;ease=1-(1-p)**3;rot=math.radians(variation%45)
    if kind=='impact_burst':
        rr=r*(.32+.68*ease)
        for part in range(3):
            d.arc((c-rr,c-rr,c+rr,c+rr),start=part*120+variation%25,end=part*120+100+variation%25,fill=white,width=max(2,round(size*.019*(1-p*.4))))
        for i in range(10):
            a=i*math.tau/10+rot;inner=rr*(.93+.08*math.sin(i*3));outer=rr*(1.15+.18*((i*7)%3)/2)
            d.line((c+math.cos(a)*inner,c+math.sin(a)*inner,c+math.cos(a)*outer,c+math.sin(a)*outer),fill=white,width=max(2,round(size*.019*(1-p*.4))))
            if i%3==0:
                d.polygon([(c+math.cos(a-.06)*inner,c+math.sin(a-.06)*inner),(c+math.cos(a)*outer,c+math.sin(a)*outer),(c+math.cos(a+.06)*inner,c+math.sin(a+.06)*inner)],fill=white)
    elif kind in {'ripple','orbit'}:
        for i in range(2 if kind=='ripple' else 3):
            rr=r*(.25+.7*ease)*(1-i*.22)
            if kind=='ripple': d.arc((c-rr,c-rr,c+rr,c+rr),start=15+i*80,end=270+i*45,fill=rgba,width=max(2,size//90))
            else:
                a=rot+i*math.tau/3+p*1.4
                x,y=c+math.cos(a)*rr,c+math.sin(a)*rr;q=size*.022
                d.ellipse((x-q,y-q,x+q,y+q),fill=rgba)
                d.arc((c-rr,c-rr,c+rr,c+rr),start=i*120+p*70,end=i*120+55+p*70,fill=rgba,width=max(2,size//120))
    elif kind=='sparkle':
        for i,(dx,dy,scale) in enumerate([(-.42,-.2,.52),(.34,-.37,.32),(.12,.38,.26)]):
            q=r*scale*math.sin(math.pi*p)**.5;x,y=c+r*dx,c+r*dy
            d.polygon([(x,y-q),(x+q*.20,y-q*.20),(x+q,y),(x+q*.20,y+q*.20),(x,y+q),(x-q*.20,y+q*.20),(x-q,y),(x-q*.20,y-q*.20)],fill=white if i==0 else rgba)
    elif kind=='speed_streak':
        for i in range(3):
            y=c+(i-1)*r*.34;x=c-r*.85+r*.4*ease
            d.line((x,y,x+r*(1.2-i*.12),y-r*.30),fill=rgba,width=max(2,round(size*.013)))
    elif kind=='swoosh':
        rr=r*(.55+.3*ease)
        d.arc((c-rr,c-rr*.65,c+rr,c+rr*.65),start=185+p*70,end=340+p*40,fill=white,width=max(2,size//75))
        d.arc((c-rr*.8,c-rr*.8,c+rr*.8,c+rr*.8),start=8+p*45,end=95+p*60,fill=rgba,width=max(2,size//120))
    elif kind=='comic_rays':
        for i in range(5):
            a=rot+(i/5)*math.tau;rr=r*(.4+.6*ease)
            d.line((c+math.cos(a)*rr*.6,c+math.sin(a)*rr*.6,c+math.cos(a)*rr,c+math.sin(a)*rr),fill=rgba,width=max(2,size//65))
    else:
        # Open corner brackets; never a solid card over the object or face.
        q=r*(.8-.12*ease);arm=r*.3
        for sx in [-1,1]:
            for sy in [-1,1]:
                x,y=c+sx*q,c+sy*q
                d.line((x-sx*arm,y,x,y,x,y-sy*arm),fill=rgba,width=max(2,size//110))
    # A narrow dark keyline keeps light accents readable on bright footage.
    keyline=im.getchannel('A').filter(ImageFilter.MaxFilter(7)).point(lambda value:round(value*.65))
    shadow=Image.new('RGBA',(size,size),(7,20,25,0));shadow.putalpha(keyline)
    shadow.alpha_composite(im)
    return shadow.resize((side,side),Image.Resampling.LANCZOS)


@lru_cache(maxsize=4)
def _statement_artwork(text, width, height, color, style):
    """Fit and draw each statement once, rather than repeating font search per frame."""
    from PIL import Image, ImageDraw, ImageFont
    w,h=width*2,height*2
    image=Image.new('RGBA',(w,h),(0,0,0,0));draw=ImageDraw.Draw(image)
    alpha=255
    words=text.upper().split()
    font_path='/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf'
    chosen=None
    for size in range(max(12,round(h*.48)),11,-2):
        font=ImageFont.truetype(font_path,size)
        options=[' '.join(words)] + [' '.join(words[:i])+'\n'+' '.join(words[i:]) for i in range(1,len(words))]
        fits=[]
        for candidate in options:
            bounds=draw.multiline_textbbox((0,0),candidate,font=font,spacing=2,stroke_width=max(2,size//16))
            tw,th=bounds[2]-bounds[0],bounds[3]-bounds[1]
            if tw<=w*.84 and th<=h*.78:
                fits.append((tw,candidate,bounds))
        if fits:
            _,label,bounds=min(fits,key=lambda row:row[0])
            chosen=(font,label,bounds,size);break
    if chosen is None:
        raise ValueError('Statement cannot fit without losing its source words')
    font,label,bounds,size=chosen
    x=(w-(bounds[2]-bounds[0]))/2-bounds[0];y=(h-(bounds[3]-bounds[1]))/2-bounds[1]
    if style=='comic':
        for sx in (-1,1):
            for sy in (-1,1):
                # Local inward rays stay entirely inside the checked text rectangle.
                edge_x=w*.5+sx*w*.48;edge_y=h*.5+sy*h*.45
                draw.polygon([(edge_x-sx*w*.05,edge_y),(edge_x+sx*w*.015,edge_y-sy*h*.08),
                    (w*.5+sx*w*.36,h*.5+sy*h*.26)],fill=(255,255,249,alpha))
    stroke=max(2,size//16)
    draw.multiline_text((x+size*.035,y+size*.065),label,font=font,spacing=2,align='center',
        fill=(4,15,20,alpha),stroke_width=stroke*2,stroke_fill=(4,15,20,alpha))
    draw.multiline_text((x,y),label,font=font,spacing=2,align='center',fill=tuple(color)+(alpha,),
        stroke_width=stroke,stroke_fill=(4,15,20,alpha))
    return image


def statement_frame(text, width, height, progress, color, *, style='clean'):
    """A brief pop then stable readable hold, with the whole source qualifier visible."""
    from PIL import Image
    image=_statement_artwork(text,width,height,tuple(color),style).copy()
    w,h=image.size
    p=max(0.,min(1.,progress))
    opacity=max(0.,min(1.,p/.10,(1-p)/.18))
    image.putalpha(image.getchannel('A').point(lambda value:round(value*opacity)))
    # One arrival, no repeated pulsing or individual-word flashing.
    scale=.94+.06*min(1.,p/.16)
    result=Image.new('RGBA',(w,h),(0,0,0,0))
    resized=image.resize((max(1,round(w*scale)),max(1,round(h*scale))),Image.Resampling.LANCZOS)
    result.alpha_composite(resized,((w-resized.width)//2,(h-resized.height)//2))
    return result.resize((width,height),Image.Resampling.LANCZOS)


def _encode(video, target, graph, *, ffmpeg, crf, preset, threads):
    subprocess.run([ffmpeg,'-v','error','-y','-filter_complex_threads','1','-i',str(video),'-filter_complex',graph,
        '-map','[accent_out]','-map','0:a?','-c:v','libx264','-preset',preset,'-crf',str(crf),'-threads',str(threads),
        '-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',str(target)],check=True,capture_output=True,timeout=1800)


def render_effects(video, plan, *, ffmpeg='ffmpeg', layout=None, crf=18, preset='fast', threads=2):
    """Replace this video temp atomically only after unchanged-clock verification."""
    if not plan.get('enabled') or not plan.get('required'):
        return plan
    video=Path(video).resolve();assets=video.parent/'.cron-director';assets.mkdir(exist_ok=True)
    target=video.with_name(video.stem+'.cron_tmp.mp4')
    before=_probe(video)
    try:
        place_cues(plan,video,ffmpeg=ffmpeg,layout=layout)
        graph=['[0:v]setpts=PTS-STARTPTS[accent_base]'];previous='accent_base'
        stem=re.sub(r'[^a-zA-Z0-9_-]','_',video.stem)[:70]
        for i,cue in enumerate(plan['cues']):
            x,y,bw,bh=cue['box'];w,h=before['width'],before['height']
            if cue['kind']=='edge_focus':
                graph.append(f'[{previous}]drawbox=x={round(w*x)}:y={round(h*y)}:w={max(3,round(w*bw))}:h={round(h*bh)}:color=0x8EDBCE@0.30:t=3:enable=\'between(t,{cue["start"]},{cue["end"]})\'[accent_{i}]')
            else:
                side=max(32,round(bw*w));span=cue['end']-cue['start'];count=max(3,math.ceil(span*30))
                prefix=assets/f'{stem}_{i}'
                frames=[]
                try:
                    for n in range(count):
                        path=Path(str(prefix)+f'_{n:03}.png');frames.append(path)
                        if cue['kind']=='statement_focus':
                            statement_frame(cue['statement'],side,max(24,round(bh*h)),n/(count-1),
                                cue['palette'],style=cue['statement_style']).save(path)
                        else:
                            effect_frame(cue['kind'],side,n/(count-1),cue['palette'],cue['variation']).save(path)
                    movie=Path(str(prefix)+'.mkv')
                    subprocess.run([ffmpeg,'-v','error','-y','-framerate','30','-i',str(prefix)+'_%03d.png','-c:v','ffv1','-pix_fmt','bgra','-threads','1',str(movie)],check=True,capture_output=True,timeout=60)
                    # The generated filename is sanitized; no model data enters a filter.
                    movie_path=str(movie).replace('\\','\\\\').replace(':','\\:').replace("'", "'\\''")
                    graph.append(f"movie='{movie_path}',format=rgba,setpts=PTS-STARTPTS+{cue['start']}/TB[fx_{i}]")
                    graph.append(f"[{previous}][fx_{i}]overlay=x={round(w*x)}:y={round(h*y)}:eof_action=pass:repeatlast=0:enable='between(t,{cue['start']},{cue['end']})'[accent_{i}]")
                    cue['statement_rendered']=cue['kind']=='statement_focus'
                finally:
                    for path in frames:path.unlink(missing_ok=True)
            previous=f'accent_{i}'
        graph.append(f'[{previous}]null[accent_out]')
        _encode(video,target,';'.join(graph),ffmpeg=ffmpeg,crf=crf,preset=preset,threads=threads)
        plan['renderer']='procedural_rgba_accents'
    except (OSError, ValueError, ImportError, subprocess.SubprocessError) as exc:
        # Mandatory quiet fallback uses only the standard drawbox filter.
        cue=dict(plan['cues'][0]);cue.update(kind='edge_focus',box=[.012,.28,.035,.14],statement_rendered=False,placement_reason='required_quiet_renderer_fallback')
        plan.update(cues=[cue],cue_count=1,fallback_reason=type(exc).__name__,renderer='drawbox_edge_focus')
        w,h=before['width'],before['height'];x,y,bw,bh=cue['box']
        graph=f"[0:v]drawbox=x={round(w*x)}:y={round(h*y)}:w={max(3,round(w*bw))}:h={round(h*bh)}:color=0x8EDBCE@0.30:t=3:enable='between(t,{cue['start']},{cue['end']})'[accent_out]"
        _encode(video,target,graph,ffmpeg=ffmpeg,crf=crf,preset=preset,threads=threads)
    after=_probe(target)
    if abs(after['duration']-before['duration'])>max(.05,1.1/before['fps']) or (before['frames'] and after['frames']!=before['frames']) or (before['width'],before['height'])!=(after['width'],after['height']):
        target.unlink(missing_ok=True)
        raise RuntimeError('Required cron effects changed the video clock or geometry')
    target.replace(video)
    plan.update(rendered=True,cue_count=len(plan['cues']),verification='duration_frame_count_and_geometry_preserved')
    return plan


def aggregate_parts(audits):
    cues=[];offset=0.;required=False
    for row in audits:
        plan=row.get('cron_director_effects') or {}
        required=required or plan.get('required',False)
        if plan.get('required') and not plan.get('rendered'):
            raise RuntimeError('A required Long chapter accent was not rendered')
        for cue in plan.get('cues',[]):
            cues.append(dict(cue,part=row['part'],start=round(offset+cue['start'],3),end=round(offset+cue['end'],3)))
        offset+=float(row.get('output_duration_seconds') or 0)
    return dict(version=POLICY_VERSION,cron_only=True,enabled=required,required=required,rendered=required and bool(cues),
        cue_count=len(cues),cues=cues,source_clock_unchanged=True,captions_clock_unchanged=True,audio_unchanged=True,
        verification='duration_frame_count_and_geometry_preserved' if required and cues else 'not_required')
