from collections import Counter
import hashlib
from pathlib import Path
from types import SimpleNamespace
import wave

import numpy as np
import pytest

import facebook_browser as browser
import facebook_creative as creative
import facebook_originals as originals


def timed_plan(topic='size'):
    plan=originals.plan('fb-research-fixture',topic=topic)
    for index,stage in enumerate(plan['stages']):stage.update(start=index*8,end=(index+1)*8)
    return plan


def test_all_editorial_pillars_are_experiments_not_invented_winners():
    topics=[r[0] for r in originals.TOPICS]
    counts=Counter()
    for index in range(500):
        topic=creative.choose_topic(str(index),topics)
        brief=creative.policy(topic,str(index));counts[brief['pillar']]+=1
        assert brief['basis']=='editorial_hypothesis_not_measured_winner'
        assert not brief['views_guaranteed']
    assert 150<counts['storage']<250 and 150<counts['everyday']<250
    assert 50<counts['mistakes']<150
    recent=topics[:7]
    assert all(creative.choose_topic(str(i),topics,recent) not in recent for i in range(30))


def test_new_topics_demonstrate_real_state_without_changing_source():
    plan=timed_plan('number');before=[r['label'] for r in plan['files']]
    after=originals.state(plan,2)[0]
    assert [r['label'] for r in after]==['Catatan_01.txt','Catatan_02.txt','Catatan_10.txt']
    assert [r['label'] for r in plan['files']]==before
    paths=timed_plan('paths');left,right,a,b=originals.state(paths,2)
    assert a=='Rumah' and b=='Kerja'
    assert left[0]['label']==right[0]['label'] and left[0]['detail']!=right[0]['detail']
    assert len(paths['files'])==2


def test_sort_transition_never_hides_one_filename_under_another(monkeypatch):
    original_draw=originals.ImageDraw.Draw
    boxes=[]
    class Drawing:
        def __init__(self,*args,**kwargs):self.actual=original_draw(*args,**kwargs)
        def __getattr__(self,key):return getattr(self.actual,key)
        def rounded_rectangle(self,xy,*args,**kwargs):
            if xy[3]-xy[1]==105 and xy[2]-xy[0]==730:boxes.append(xy)
            return self.actual.rounded_rectangle(xy,*args,**kwargs)
    monkeypatch.setattr(originals.ImageDraw,'Draw',Drawing)
    plan=timed_plan('number')
    plan.pop('motion_version')  # Persisted legacy renders keep their old safe layout.
    for offset in (.05,.5,.8,1.2,1.5,2):
        boxes.clear();originals.frame(plan,16+offset,[])
        ordered=sorted(boxes,key=lambda row:row[1])
        assert len(ordered)==3
        assert all(ordered[i][3]<ordered[i+1][1] for i in range(2))
        assert all(95<=row[0]<row[2]<=900 for row in ordered)


def test_sound_is_measured_timed_original_quiet_and_deterministic(tmp_path):
    plan=timed_plan();design=creative.sound_plan(plan,32)
    one=tmp_path/'one.wav';two=tmp_path/'two.wav'
    record=creative.synthesize_sounds(one,design,32)
    creative.synthesize_sounds(two,design,32)
    assert one.read_bytes()==two.read_bytes()
    assert not record['third_party_audio'] and record['ducked_under_voice']
    assert -26<record['generated_peak_dbfs']<-20
    assert record['sha256']==hashlib.sha256(one.read_bytes()).hexdigest()
    with wave.open(str(one)) as stream:
        assert stream.getframerate()==48000 and stream.getnchannels()==1
        assert stream.getnframes()==32*48000
        samples=np.frombuffer(stream.readframes(stream.getnframes()),dtype='<i2')
    assert not samples[:int(.35*48000)].any()
    assert samples[int(.35*48000):int(.415*48000)].any()
    assert not samples[int(2*48000):int(10*48000)].any()
    assert design['events'][1]['start']==16.08 and design['events'][-1]['start']==24.12


@pytest.mark.parametrize('duration',[float('nan'),0,-1,56])
def test_invalid_sound_timeline_is_rejected(tmp_path,duration):
    with pytest.raises(ValueError):creative.synthesize_sounds(tmp_path/'bad.wav',{'events':[]},duration)


class Region:
    def __init__(self,caption,complete=True):self.caption=caption;self.expanded=False;self.complete=complete;self.presses=0
    def inner_text(self,**kwargs):return self.caption if self.expanded and self.complete else self.caption.split('\n')[0]+'… Lihat selengkapnya'
    def get_by_role(self,*args,**kwargs):
        def press(*args,**kwargs):self.expanded=True;self.presses+=1
        return SimpleNamespace(all=lambda:[SimpleNamespace(is_visible=lambda:True,press=press)])


@pytest.mark.parametrize('complete',[True,False])
def test_caption_expansion_requires_the_entire_post_copy(complete):
    caption='Mengganti nama berkas tidak mengubah isi atau formatnya. Ekstensi tetap sama dalam contoh ini.\n\n#TipsDigital #TeknologiSehariHari'
    region=Region(caption,complete)
    page=SimpleNamespace(locator=lambda _:SimpleNamespace(all=lambda:[region]),wait_for_timeout=lambda _:None)
    assert browser.exact_caption_visible(page,caption) is complete
    assert region.presses==1


def test_another_post_prefix_is_not_expanded_or_accepted():
    region=Region('Caption lain yang sama sekali tidak terkait dengan Reel ini.')
    page=SimpleNamespace(locator=lambda _:SimpleNamespace(all=lambda:[region]),wait_for_timeout=lambda _:None)
    assert not browser.exact_caption_visible(page,'Tujuan caption berbeda yang harus benar-benar cocok dengan posting lengkap.')
    assert region.presses==0


def test_short_caption_line_can_expand_hidden_hashtags():
    caption='Periksa ukuran file sebelum merapikan.\n\n#TipsDigital #TeknologiSehariHari'
    region=Region(caption)
    page=SimpleNamespace(locator=lambda _:SimpleNamespace(all=lambda:[region]),wait_for_timeout=lambda _:None)
    assert browser.exact_caption_visible(page,caption)
    assert region.presses==1


@pytest.mark.parametrize('duration',[26,28.4,30.667,31.999,32.667,55])
def test_audio_samples_cover_the_ending_without_a_subsecond_tail(duration):
    windows=originals.audio_windows(duration)
    assert windows[0][0]==0 and windows[-1][0]+windows[-1][1]==duration
    assert all(span>=2 for _,span in windows)
    assert all(a+span==b for (a,span),(b,_) in zip(windows,windows[1:]))
    assert sum(span for _,span in windows)==pytest.approx(duration)
