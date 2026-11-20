from copy import deepcopy
import json
from urllib.error import HTTPError

import pytest
import api
import clipper
import cron_long_strategy as policy
from llm import AIConfig


@pytest.fixture
def source():
    texts = ['Pemain membuka pintu pertama dan menemukan ruangan kosong.',
             'Di lantai berikutnya pemain berhasil menemukan kunci biru.',
             'Temannya menunjukkan jalan menuju taman yang lebih terang.',
             'Keduanya memutuskan beristirahat di rumah dekat jembatan.']
    transcript=[clipper.TranscriptSegment(i*80,i*80+60,text) for i,text in enumerate(texts)]
    candidates=[clipper.ClipCandidate(index=i+1,start=row.start,end=row.end,duration=60,score=80+i,
        title=f'Momen {i+1}',reason='Momen utuh',text=row.text,boundary_quality='utuh',key_point_score=70)
        for i,row in enumerate(transcript)]
    return candidates,transcript


def test_failed_story_uses_original_chronology_without_teaser_duplication(source):
    candidates,transcript=source
    original=deepcopy(candidates)
    sequence,roles,director,audit=clipper.build_long_compilation_fallback(list(reversed(candidates)),transcript,[(0,25)])
    assert audit['passed'] and audit['output_seconds']==240
    assert [row.start for row in sequence]==[0,80,160,240]
    assert all(role=='compilation_moment' for role in roles)
    assert director['quality_gate_passed'] is False
    assert director['compilation_quality_gate_passed'] is True
    assert director['duplicated_teaser_content'] is False
    assert candidates==original


@pytest.mark.parametrize('damage',['too_short','overlap','reordered','duplicate','nan','missing_text','mostly_short','missing_anchor','too_long'])
def test_invalid_compilation_cannot_be_a_fallback(source,damage):
    candidates,transcript=source
    material=policy.story_material(candidates,transcript);anchors=[]
    if damage=='too_short':material=material[:2]
    if damage=='overlap':material[1]['start']=40
    if damage=='reordered':material=list(reversed(material))
    if damage=='duplicate':material[1]['text']=material[0]['text']
    if damage=='nan':material[1]['end']=float('nan')
    if damage=='missing_text':material[0]['text']=''
    if damage=='mostly_short':anchors=[(0,300)]
    if damage=='missing_anchor':anchors=[(600,630)]
    if damage=='too_long':material[-1]['end']=1000
    assert not policy.validate_compilation(material,anchors)['passed']


def test_saved_compilation_audit_is_bound_to_source_cut_identity(source):
    candidates,transcript=source
    material=policy.story_material(candidates,transcript)
    sidecar={'long_format':'compilation','parts':material,
             'cron_long_story_review':{'passed':False,'reasons':['resolved_ending']},
             'cron_long_compilation_review':policy.validate_compilation(material,[(0,25)])}
    assert policy.long_evidence_issue(sidecar,[(0,25)]) is None
    sidecar['parts'][0]['text']='Bukti lain yang tidak terkait dengan audit sebelumnya.'
    assert policy.long_evidence_issue(sidecar,[(0,25)])=='compilation_material_changed'


def test_compilation_label_cannot_reuse_a_story_pass_without_its_own_evidence(source):
    candidates,transcript=source
    sidecar={'long_format':'compilation','parts':policy.story_material(candidates,transcript),
             'cron_long_story_review':{'passed':True}}
    assert policy.long_evidence_issue(sidecar)


@pytest.mark.parametrize('provider',['disabled','unavailable','malformed','bad_arc'])
def test_rejected_story_reaches_compilation_render_in_same_worker(source,tmp_path,monkeypatch,provider):
    candidates,transcript=source
    monkeypatch.setattr(clipper,'build_long_form_story_sequence',lambda *args:(list(reversed(candidates)),[],{}))
    def completion(*args,**kwargs):
        if provider=='unavailable':raise ConnectionError('offline')
        return 'bad JSON' if provider=='malformed' else '{"checks":{"resolved_ending":false}}'
    monkeypatch.setattr(clipper,'chat_completion',completion)
    reached=[]
    class RenderReached(Exception):pass
    def render(*args,**kwargs):
        reached.append((args[1],kwargs))
        raise RenderReached()
    monkeypatch.setattr(clipper,'export_clip',render)
    with pytest.raises(RenderReached):
        clipper.export_compilation(tmp_path/'source.mp4',candidates,transcript,tmp_path/'clips',True,
            'center',clipper.CaptionStyle(),AIConfig(enabled=provider!='disabled'),'auto',[],'standard',
            cron_long_strategy_required=True,short_anchor_ranges=[(0,25)])
    assert reached[0][0].start==0
    assert reached[0][1]['compilation_narrative_role']=='compilation_moment'
    assert json.loads((tmp_path/'cron_long_story_review.json').read_text())['passed'] is False
    assert json.loads((tmp_path/'cron_long_compilation_review.json').read_text())['passed'] is True


def test_provider_content_rejection_is_not_reinterpreted_as_a_story_failure(source,tmp_path,monkeypatch):
    candidates,transcript=source
    def reject(*args,**kwargs):raise HTTPError('https://provider.test',422,'rejected',{},None)
    monkeypatch.setattr(clipper,'chat_completion',reject)
    monkeypatch.setattr(clipper,'export_clip',lambda *args,**kwargs:pytest.fail('No media after provider refusal'))
    with pytest.raises(RuntimeError,match='provider'):
        clipper.export_compilation(tmp_path/'source.mp4',candidates,transcript,tmp_path/'clips',True,
            'center',clipper.CaptionStyle(),AIConfig(enabled=True),'auto',[],'standard',cron_long_strategy_required=True)
    assert not (tmp_path/'cron_long_compilation_review.json').exists()


def test_compilation_upload_still_requires_independent_long_qc(source,tmp_path,monkeypatch):
    candidates,transcript=source
    material=policy.story_material(candidates,transcript)
    sidecar={'long_format':'compilation','parts':material,'cron_long_story_review':{'passed':False},
             'cron_long_compilation_review':policy.validate_compilation(material,[(0,25)])}
    request=api.ClipJobRequest(clip_mode='highlight_5m',cron_long_strategy=True,
                               publication_review_required=True,compilation_anchor_ranges=[(0,25)])
    job=api.ClipJob(id='long',request=request,status='completed',created_at=api.now_iso(),updated_at=api.now_iso())
    clip=api.ClipFile(name='resume_cerita_test.mp4',url='/outputs/test.mp4',size_bytes=100)
    monkeypatch.setattr(api,'clip_sidecar_payload',lambda _:sidecar)
    monkeypatch.setattr(api,'long_qc_path',lambda *args:tmp_path/'qc.json')
    assert 'QC' in api.long_upload_review_hold(job,clip)
    (tmp_path/'qc.json').write_text(json.dumps({'audit':{'decision':'PASS_UPLOAD','upload_allowed':True}}))
    assert api.long_upload_review_hold(job,clip) is None
    sidecar['parts'][0]['end']=10
    assert api.long_upload_review_hold(job,clip)


def test_compilation_growth_label_never_claims_story_arc_passed(source):
    candidates,transcript=source
    _,_,director,_=clipper.build_long_compilation_fallback(candidates,transcript)
    result=clipper.one_k_long_form_readiness(candidates[0],director)
    assert result['quality_gate_passed']
    assert result['compilation_structure_gate']
    assert not result['story_director_quality_gate']


def test_capability_declares_fallback_and_preserved_qc():
    data=api.get_cron_long_strategy()
    assert data['compilation_fallback_enabled'] and data['compilation_review_required']
    assert data['fallback_preserves_long_qc'] and data['compilation_fallback_policy_version']==1
