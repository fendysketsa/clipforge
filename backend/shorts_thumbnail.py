"""Source-frame Shorts posters: grounded curiosity, readable type and real subjects."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import os


VERSION = 1
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
STOP = set('yang dan di ke dari untuk dengan ini itu saya aku kamu dia kita mereka ada adalah jadi si nya lah pun'.split())
NEGATIONS = {'bukan', 'tidak', 'nggak', 'gak', 'jangan', 'belum', 'tanpa'}
QUALIFIERS = NEGATIONS | {'diduga', 'dituduh', 'katanya', 'konon', 'menurut', 'kabarnya', 'mitos', 'mengaku'}
TENSION = {'bukan': 20, 'ternyata': 18, 'padahal': 17, 'kenapa': 15, 'kok': 14,
           'malah': 14, 'akhirnya': 13, 'jangan': 12, 'nggak': 10, 'tidak': 9, 'tapi': 8}
DANGLING = STOP | NEGATIONS | set(TENSION) | set('harus mau akan bisa pernah selalu paling sampai sudah cuma hanya semua setiap karena kalau bahwa saat'.split())


def words(text):
    return re.findall(r'[\w]+', str(text).casefold())


def headline_options(sidecar):
    """Pick verbatim excerpts, preserving nearby negation and avoiding chopped connectors."""
    text = str(sidecar.get('text') or '').strip()
    sentences = re.split(r'(?<=[.!?,;:])\s+|\n+', text)
    options = []
    for sentence in sentences:
        tokens = words(sentence)
        for start in range(len(tokens)):
            for count in range(3, 7):
                excerpt = tokens[start:start + count]
                if len(excerpt) != count or excerpt[-1] in DANGLING:
                    continue
                if len(set(excerpt) - STOP) < 2 or len(' '.join(excerpt)) > 48:
                    continue
                # Do not turn "bukan Nisa yang merusak keluarga" into the
                # opposite claim by trimming off the negation.
                if any(t in QUALIFIERS for t in tokens[:start]) and not any(t in QUALIFIERS for t in excerpt):
                    continue
                if excerpt[0] in {'yang', 'dan', 'dari', 'di', 'ke', 'dengan', 'atau'}:
                    continue
                if start > 0 and excerpt[0] not in (NEGATIONS | set(TENSION)):
                    continue
                score = sum(TENSION.get(t, 0) for t in set(excerpt))
                score += min(8, len(set(excerpt) - STOP) * 2)
                score += 4 if start == 0 else 0
                score -= abs(count - 5)
                if start + count == len(tokens) or all(t in STOP for t in tokens[start+count:]):
                    score += 15
                else:
                    score -= 10
                options.append((score, ' '.join(excerpt).upper(), sentence.strip()))
    if not options:
        # A provisional cover must not invent a new promise when evidence is sparse.
        fallback = ' '.join(words(sidecar.get('hook') or sidecar.get('title') or text)[:6]).upper()
        return [{'headline': fallback or 'LIHAT KONTEKSNYA', 'evidence': text,
                 'curiosity_score': 0, 'needs_frame_review': True}]
    options.sort(key=lambda item: item[0], reverse=True)
    selected = []
    for score, headline, sentence in options:
        tokens = set(words(headline)) - STOP
        if any(len(tokens & (set(words(row['headline'])) - STOP)) / max(1, len(tokens)) > .70 for row in selected):
            continue
        selected.append(dict(headline=headline, evidence=sentence, curiosity_score=score,
                             needs_frame_review=False))
        if len(selected) == 3:
            break
    return selected


def photo_bounds(image):
    """Locate the dominant moving-picture band, ignoring letterbox text and black cards."""
    from PIL import ImageStat
    small = image.convert('RGB').resize((120, 240))
    runs, start = [], None
    for y in range(240):
        stat = ImageStat.Stat(small.crop((8, y, 112, y + 1)))
        active = sum(stat.mean) / 3 > 20 and max(stat.stddev) > 18
        if active and start is None:
            start = y
        if (not active or y == 239) and start is not None:
            end = y if not active else y + 1
            if end - start >= 20:
                runs.append((start, end))
            start = None
    if not runs:
        return (0, 0, image.width, image.height)
    top, bottom = max(runs, key=lambda row: row[1] - row[0])
    return (0, int(top / 240 * image.height), image.width,
            min(image.height, int(bottom / 240 * image.height)))


def face_boxes(image):
    try:
        try:
            import cv2
        except ModuleNotFoundError:
            local = Path(__file__).resolve().parent / 'data/shorts_thumbnail_python'
            if local.is_dir():
                sys.path.insert(0, str(local))
            import cv2
        import numpy as np
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        gray = cv2.cvtColor(np.asarray(image.convert('RGB')), cv2.COLOR_RGB2GRAY)
        return [tuple(int(v) for v in box) for box in cascade.detectMultiScale(gray, 1.1, 5, minSize=(28, 28))]
    except Exception:
        return []


def sample_frames(video, sidecar, *, source_video=None, source_start=0):
    from PIL import Image, ImageFilter, ImageStat
    duration = float(sidecar.get('output_duration_seconds') or sidecar.get('duration') or 0)
    if duration <= 0:
        duration = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries',
            'format=duration', '-of', 'csv=p=0', str(video)], text=True).strip())
    # Avoid appended quote/CTA cards, which contain no subject to promise.
    useful = min(duration, max(0.5, float(sidecar.get('duration') or duration)))
    times = sorted({round(max(.05, min(useful - .05, useful * ratio)), 3)
                    for ratio in (.04, .18, .35, .52, .70, .83, .92)})
    rows = []
    for timestamp in times:
        result = subprocess.run(['ffmpeg', '-v', 'error', '-threads', '1', '-ss', str(timestamp + (source_start if source_video else 0)),
            '-i', str(source_video or video), '-frames:v', '1', '-vf', 'scale=1080:-2', '-threads', '1',
            '-f', 'image2pipe', '-vcodec', 'mjpeg', '-'], capture_output=True, check=True, timeout=30)
        image = Image.open(io.BytesIO(result.stdout)).convert('RGB')
        bounds = photo_bounds(image)
        photo = image.crop(bounds)
        brightness = sum(ImageStat.Stat(photo).mean) / 3
        edges = sum(ImageStat.Stat(photo.filter(ImageFilter.FIND_EDGES)).mean) / 3
        faces = face_boxes(photo)
        largest = max(faces, key=lambda b: b[2] * b[3]) if faces else None
        face_area = largest[2] * largest[3] / max(1, photo.width * photo.height) if largest else 0
        score = min(25, edges) + min(35, face_area * 150) + (15 if faces else 0)
        score += 15 if 45 <= brightness <= 210 else 0
        score -= 25 if photo.height < image.height * .15 else 0
        rows.append(dict(timestamp=timestamp, photo=photo, faces=faces, largest_face=largest,
                         score=round(score, 2), photo_bounds=bounds, brightness=round(brightness, 1)))
    return sorted(rows, key=lambda row: row['score'], reverse=True)


def fit_headline(text, width=870):
    from PIL import ImageFont
    tokens = text.split()
    for size in range(106, 51, -2):
        font = ImageFont.truetype(FONT, size)
        choices = []
        for split in range(1, len(tokens)):
            lines = [' '.join(tokens[:split]), ' '.join(tokens[split:])]
            widths = [font.getlength(line) for line in lines]
            if max(widths) <= width:
                choices.append((abs(widths[0] - widths[1]), lines))
        if choices:
            return min(choices, key=lambda row: row[0])[1], font
        if font.getlength(text) <= width:
            return [text], font
    raise ValueError('Headline cannot fit the mobile-safe cover')


def poster(frame, headline, variation):
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps
    photo = frame['photo']
    accent = ('#FFCF32', '#4BE4D4', '#FF8E48')[variation]
    canvas = ImageOps.fit(photo, (1080, 1920)).filter(ImageFilter.GaussianBlur(42))
    canvas = ImageEnhance.Brightness(canvas).enhance(.36)
    face = frame['largest_face']
    center = ((face[0] + face[2] / 2) / photo.width, (face[1] + face[3] / 2) / photo.height) if face else (.5, .45)
    if variation == 0:
        # A: one real face/gesture leads; native source crop supplies all identity.
        hero = ImageOps.fit(photo, (1080, 1170), centering=center)
        canvas.paste(hero, (0, 220))
        title_y = 1300
    elif variation == 1:
        # B: preserve the full scene and its actual context/evidence.
        hero = ImageOps.contain(photo, (1010, 1100))
        canvas.paste(hero, ((1080 - hero.width) // 2, 470 + (900 - hero.height) // 2))
        title_y = 1240
    else:
        # C: wider story scene at the top; a bold typographic lower third.
        hero = ImageOps.fit(photo, (1080, 1020), centering=(.5, .4))
        canvas.paste(hero, (0, 330))
        title_y = 1260
    veil = Image.new('RGBA', canvas.size)
    draw = ImageDraw.Draw(veil)
    for y in range(1920):
        bottom = min(235, max(0, int((y - 1040) * .40)))
        top = min(150, max(0, int((340 - y) * .45)))
        if bottom or top:
            draw.line((0, y, 1080, y), fill=(0, 0, 0, max(top, bottom)))
    canvas = Image.alpha_composite(canvas.convert('RGBA'), veil)
    draw = ImageDraw.Draw(canvas)
    lines, font = fit_headline(headline)
    draw.rounded_rectangle((78, title_y - 45, 220, title_y - 32), radius=6, fill=accent)
    line_height = font.size + 22
    for i, line in enumerate(lines):
        draw.text((82, title_y + i * line_height), line, font=font,
            fill=accent if i == len(lines) - 1 else 'white', stroke_width=4, stroke_fill='#111111')
    return canvas.convert('RGB'), dict(font_size=font.size, headline_lines=lines,
        headline_zone=[78, title_y, 960, title_y + len(lines)*line_height], subject_crop='face_anchored' if face and variation == 0 else 'real_scene')


def build_pack(video: Path, sidecar: dict, destination: Path, *, source_video=None, source_start=0):
    """Build a reviewable pack in a staging directory; caller controls activation."""
    destination.mkdir(parents=True, exist_ok=True)
    frames = sample_frames(video, sidecar, source_video=source_video, source_start=source_start)
    options = headline_options(sidecar)
    if not frames:
        raise ValueError('No readable real frame')
    if max(frame['score'] for frame in frames) < 10:
        raise ValueError('No usable subject frame; preserve the existing cover')
    variants = []
    context_frame = max(frames, key=lambda row: (len(row['faces']), row['photo'].width / max(1,row['photo'].height), row['score']))
    story_frame = min(frames, key=lambda row: abs(row['timestamp'] - frames[0]['timestamp'] * .55) - row['score'] * .02)
    choices = [frames[0], context_frame, story_frame]
    for index, angle in enumerate(('human_tension', 'source_context', 'cinematic_story')):
        frame = choices[index]
        copy = options[min(index, len(options)-1)]
        artwork, geometry = poster(frame, copy['headline'], index)
        filename = f"{video.stem}_thumb{('', '_b', '_c')[index]}.jpg"
        artwork.save(destination / filename, quality=90, optimize=True)
        breakdown = dict(readability=25 if geometry['font_size'] >= 76 else 20,
            truthful_curiosity=min(20, 10 + max(0, copy['curiosity_score']) // 5),
            subject_hierarchy=20 if frame['largest_face'] and index == 0 else 13,
            emotional_specificity=10 if frame['largest_face'] else 5,
            cinematic_craft=8, brand_distinction=5, production_feasibility=5)
        variants.append(dict(id='ABC'[index], angle=angle, eyebrow='', headline=copy['headline'], support='',
            keyframe_direction={'timestamp_seconds': frame['timestamp'],
                'source_timestamp_seconds':frame['timestamp'] + (source_start if source_video else 0),
                'observed_faces':len(frame['faces'])},
            composition=geometry, palette=['#111111', '#FFFFFF', ('#FFCF32','#4BE4D4','#FF8E48')[index]],
            image_prompt=f"Use the real 9:16 cover source frame at {frame['timestamp']}s. Preserve the subject identity and actual expression. Add only the exact copy {copy['headline']!r}; keep eyes clear and headline in the central UI-safe zone.",
            negative_prompt='No invented expressions, people, events, claims, fake quotes, fake evidence, copied branding or extra badges.',
            evidence=[copy['evidence']], filename=filename, score=sum(breakdown.values()), score_breakdown=breakdown))
    winner = max(variants, key=lambda row: row['score'])
    # The existing uploader owns _thumb.jpg; make the actual winner its default.
    if winner['id'] != 'A':
        original_a = (destination / variants[0]['filename']).read_bytes()
        (destination / variants[0]['filename']).write_bytes((destination / winner['filename']).read_bytes())
        (destination / winner['filename']).write_bytes(original_a)
        winner['filename'], variants[0]['filename'] = variants[0]['filename'], winner['filename']
    with video.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    manifest = dict(schema_version=1, schema='clipforge-thumbnail-ideas-v2', policy_version=VERSION,
        source_clip=video.name, format='shorts_9_16', status='READY_FOR_DESIGN', winner=winner['id'],
        selection_reason='Highest editorial design score from actual clip frames and verbatim speech; not a CTR prediction.',
        needs_frame_review=any(row.get('needs_frame_review') for row in options), variants=variants,
        keyframe_source='original_source_before_overlays' if source_video else 'finished_short',
        source_video_sha256=digest,
        shorts_custom_thumbnail_guaranteed=False)
    (destination / f'{video.stem}_thumbnail_ideas.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    (destination / f'{video.stem}_thumb.txt').write_text(
        f"HOOK: {winner['headline']}\nWINNER: {winner['id']}\n"
        f"FRAME: {winner['keyframe_direction']['timestamp_seconds']}s\n\n"
        + winner['image_prompt'] + '\n', encoding='utf-8')
    return manifest


def install_pack(video: Path, sidecar: dict, *, may_publish=None, source_video=None, source_start=0):
    """Atomically activate a staged cover pack while preserving all MP4 bytes."""
    previous = sidecar.get('thumbnail_curiosity') or {}
    if previous.get('policy_version') == VERSION and all(
        (video.parent / f'{video.stem}_thumb{suffix}.jpg').is_file() for suffix in ('', '_b', '_c')
    ):
        return previous
    with tempfile.TemporaryDirectory(prefix='.thumbnail-stage-', dir=video.parent) as temp:
        staging = Path(temp)
        manifest = build_pack(video, sidecar, staging, source_video=source_video, source_start=source_start)
        if manifest['needs_frame_review']:
            raise ValueError('Transcript evidence is insufficient for automatic cover replacement')
        if may_publish is not None and not may_publish():
            return None
        for path in staging.iterdir():
            os.replace(path, video.parent / path.name)
    winner = next(row for row in manifest['variants'] if row['id'] == manifest['winner'])
    sidecar.update(thumbnail_headline=winner['headline'], thumbnail_eyebrow='', thumbnail_support='',
        thumbnail_frame_seconds=winner['keyframe_direction']['timestamp_seconds'],
        thumbnail_variants=manifest['variants'],
        thumbnail_ideas_manifest=f'{video.stem}_thumbnail_ideas.json',
        thumbnail_curiosity={'policy_version':VERSION, 'winner':manifest['winner'],
            'headline':winner['headline'], 'source_video_sha256':manifest['source_video_sha256'],
            'method':'real_frame_selection_and_verbatim_curiosity', 'ctr_guarantee':False})
    path = video.with_suffix('.json')
    temporary = path.with_suffix('.json.thumbnail-tmp')
    temporary.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2)+'\n')
    os.replace(temporary, path)
    return sidecar['thumbnail_curiosity']
