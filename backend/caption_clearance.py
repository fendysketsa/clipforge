"""Keep added captions away from text already embedded in native portrait video.

This measures glyph-like high-contrast rows, not their meaning or accuracy.
Source pixels and source timestamps are never changed by this policy.
"""
from pathlib import Path
import math

VERSION=1


def text_rows(frame):
    import cv2
    import numpy as np
    gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
    h,w=gray.shape
    dark=cv2.dilate((gray<85).astype('uint8'),np.ones((7,7),'uint8'))
    mask=((gray>200)&(dark>0)).astype('uint8')*255
    _,_,stats,_=cv2.connectedComponentsWithStats(mask)
    boxes=[(int(x),int(y),int(bw),int(bh)) for x,y,bw,bh,area in stats[1:]
           if .70*h<y<.84*h and .06*w<x<.94*w and 4<=bh<=34 and 2<=bw<=50
           and area>=9 and area/(bw*bh)>.12]
    rows=[]
    for y in range(int(.70*h),int(.84*h),8):
        letters=[b for b in boxes if abs(b[1]+b[3]/2-y)<8]
        if len(letters)>=7 and max(b[0]+b[2] for b in letters)-min(b[0] for b in letters)>.23*w:
            rows.append([min(b[0] for b in letters),min(b[1] for b in letters),
                         max(b[0]+b[2] for b in letters),max(b[1]+b[3] for b in letters)])
    return rows


def plan(regions,face_bottoms=(),*,font_size=58,default_baseline=1555):
    base=dict(version=VERSION,enabled=False,detected=bool(regions),
              source_text_removed=False,source_attribution_preserved=True,source_clock_changed=False,
              method='multi_frame_high_contrast_glyph_rows_not_ocr',requires_review=False)
    if len(regions)<2:
        return {**base,'reason':'insufficient_persistent_source_text_evidence','requires_review':bool(regions)}
    top=min(r[1] for r in regions);bottom=max(r[3] for r in regions)
    height=math.ceil(2*font_size*1.3+24)
    if top>default_baseline+32 or bottom<default_baseline-height-32:
        return {**base,'reason':'source_text_outside_caption_area'}
    # A dedicated band also protects transient source lower-thirds and name
    # badges that are absent from some samples. The complete source picture
    # stays above the added caption for the entire clip, at every timestamp.
    baseline=1552
    panel_bottom=1320
    return {**base,'enabled':True,'reason':'separate_source_picture_from_added_caption_band',
            'layout':'source_with_caption_band','caption_baseline':baseline,
            'caption_bounds':[baseline-height,baseline],
            'source_text_bounds':[40+top*2/3,40+bottom*2/3],
            'source_panel':{'x':180,'y':40,'width':720,'height':1280},
            'full_source_frame_visible':True,'minimum_gap':baseline-height-panel_bottom}



def analyze(video:Path,start:float,duration:float,*,font_size=58):
    import cv2
    cap=cv2.VideoCapture(str(video));regions=[];faces=[];samples=[]
    detector=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
    try:
        for fraction in (.04,.24,.5,.74,.96):
            t=start+max(0,min(duration-.1,duration*fraction))
            cap.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,frame=cap.read()
            if not ok:continue
            frame=cv2.resize(frame,(540,960),interpolation=cv2.INTER_AREA)
            rows=text_rows(frame)
            if rows:
                regions.append([2*min(r[0] for r in rows),2*min(r[1] for r in rows),
                                2*max(r[2] for r in rows),2*max(r[3] for r in rows)])
            if not detector.empty():
                gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
                faces.extend(2*int(y+h) for x,y,w,h in detector.detectMultiScale(
                    gray,scaleFactor=1.1,minNeighbors=4,minSize=(50,50)))
            samples.append(round(t,3))
    finally:cap.release()
    result=plan(regions,faces,font_size=font_size)
    if len(samples)<2:result.update(requires_review=True,reason='source_frames_unavailable')
    result.update(sample_timestamps=samples,regions=regions)
    return result
