"""Grounded creative recovery, source identity and bounded cron replacements."""
import copy
import json
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

import api
import clipper
from llm import AIConfig


URL = 'https://www.youtube.com/watch?v=abcdefghijk'
OTHER = 'https://www.youtube.com/watch?v=lmnopqrstuv'
TEXTS = [
    'Tahukah kamu kenapa pintu Minecraft ini tidak terbuka?',
    'Awalnya pemain ingin keluar rumah, tetapi pintunya terkunci dan jalan utama tertutup.',
    'Masalahnya ada tuas tersembunyi di belakang lemari yang belum diperiksa.',
    'Setelah itu pemain memindahkan lemari dan menekan tuas tersebut.',
    'Ternyata tuas itu membuka pintu rahasia sehingga pemain bisa keluar dengan aman.',
    'Jadi jawabannya adalah memeriksa petunjuk dan membuka tuas sebelum keluar rumah.',
]


def transcript():
    return [clipper.TranscriptSegment(i * 7, (i + 1) * 7, text) for i, text in enumerate(TEXTS)]


def idea(**changes):
    return dict(recipe='goal_obstacle_outcome', first=0, last=5, setup=0, payoff=5,
        setup_quote=TEXTS[0], payoff_quote=TEXTS[5]) | changes


def recover(monkeypatch, ideas=None, rows=None, title='Minecraft Indonesia', config=None):
    monkeypatch.setattr(clipper, 'chat_completion', lambda *a: json.dumps({'ideas': [idea()] if ideas is None else ideas}))
    return clipper.director_recover_short_candidates(rows or transcript(),
        config or AIConfig(True, 'http://example.test/v1', 'demo'), source_title=title,
        source_url=URL, min_duration=25, max_duration=45, limit=1)


def test_director_selects_original_contiguous_story_with_native_metrics(monkeypatch):
    original = transcript()
    snapshot = copy.deepcopy(original)
    selected, audit, review = recover(monkeypatch, rows=original)
    assert len(selected) == 1 and not review
    assert selected[0].start == 0 and selected[0].end == 42
    assert selected[0].text == ' '.join(TEXTS)
    assert selected[0].narrative_arc_complete and selected[0].religious_context_safe
    assert audit['outcome'] == 'recovered' and audit['attempted']
    assert audit['proposals'][0]['setup_quote'] == TEXTS[0]
    assert original == snapshot
    assert selected[0].score == clipper.score_window(original, 42)[0]


def test_raw_candidate_gets_boundary_repair_before_structural_gate():
    c = clipper.ClipCandidate(index=0,start=0,end=35,duration=35,score=88,
        title='Pintu terkunci',text=' '.join(TEXTS[:5]),reason='native',
        boundary_quality='menggantung',narrative_arc_complete=False)
    assert not clipper.select_candidates([c],1)
    selected=clipper.select_and_repair_short_candidates([c],transcript(),limit=1,
        min_duration=25,max_duration=45)
    assert len(selected)==1 and selected[0].narrative_arc_complete
    assert selected[0].text.endswith(TEXTS[-1])
    assert c.end==35 and not c.narrative_arc_complete


def test_raw_boundary_repair_does_not_override_editorial_veto():
    c = clipper.ClipCandidate(index=0,start=0,end=35,duration=35,score=95,
        title='Pintu terkunci',text=' '.join(TEXTS[:5]),reason='native',
        boundary_quality='menggantung',religious_context_safe=False)
    assert not clipper.select_and_repair_short_candidates([c],transcript(),limit=1,
        min_duration=25,max_duration=45,allow_manual_review_quality=True)


@pytest.mark.parametrize('changes', [
    {'first': True}, {'last': 999}, {'first': -1}, {'setup': 2}, {'payoff': 0},
    {'recipe': 'invent_a_story'}, {'setup_quote': 'Pintu meledak dan pemain tewas.'},
    {'payoff_quote': 'Jawaban palsu yang tidak ada di sumber.'},
    {'setup_quote': 'a'}, {'last': 2}, {'first': 5, 'last': 0},
])
def test_director_rejects_unobserved_or_misplaced_story_evidence(monkeypatch, changes):
    selected, audit, _ = recover(monkeypatch, [idea(**changes)])
    assert not selected and not audit['selected'] and audit['outcome'] == 'replace_source'


def test_director_cannot_bridge_unsupplied_excerpt_gap(monkeypatch):
    rows = [clipper.TranscriptSegment(i * .1, (i + 1) * .1, TEXTS[i % 6]) for i in range(600)]
    selected, audit, _ = recover(monkeypatch, [idea(last=599, payoff=599, payoff_quote=rows[-1].text)], rows)
    assert len(audit['transcript_excerpt']) <= 156 and not selected


def test_director_rejects_long_pause_and_religious_chapter_boundary(monkeypatch):
    rows = transcript()
    rows[2].start += 4
    assert not recover(monkeypatch, rows=rows)[0]
    rows = transcript()
    rows[3].text = 'Sekarang kita bahas hukum yang lain.'
    assert not recover(monkeypatch, [idea(recipe='question_answer')], rows, title='Ceramah ustadz')[0]


def test_director_does_not_override_native_context_gate(monkeypatch):
    monkeypatch.setattr(clipper, 'refresh_candidate_export_context', lambda *a: False)
    assert not recover(monkeypatch)[0]


def test_director_weak_native_score_is_never_automatic_upload_approval(monkeypatch):
    monkeypatch.setattr(clipper, 'score_window', lambda *a: (40, ['weak']))
    selected, _, _ = recover(monkeypatch)
    assert all(c.score <= 40 for c in selected)
    exported, review = clipper.select_short_export_candidates(selected, 1)
    assert not exported or review


def test_director_does_not_call_disabled_provider(monkeypatch):
    monkeypatch.setattr(clipper, 'chat_completion', lambda *a: pytest.fail('disabled provider called'))
    _, audit, _ = clipper.director_recover_short_candidates(transcript(), AIConfig(),
        source_title='Minecraft', source_url=URL, min_duration=25, max_duration=45, limit=1)
    assert not audit['attempted']


@pytest.mark.parametrize('status', [401, 403, 422])
def test_terminal_provider_rejection_is_not_retried_by_director(monkeypatch, status):
    calls = []
    def reject(*args):
        calls.append(args)
        raise HTTPError('http://example.test', status, 'rejected', {}, None)
    monkeypatch.setattr(clipper, 'chat_completion', reject)
    config = AIConfig(True, 'http://example.test/v1', 'demo')
    c = clipper.ClipCandidate(index=0,start=0,end=42,duration=42,score=80,
        title='Pintu rahasia',text=' '.join(TEXTS),reason='native')
    clipper.ai_rescore_candidates([c], config, target_count=1)
    _, audit, _ = clipper.director_recover_short_candidates(transcript(),config,
        source_title='Minecraft',source_url=URL,min_duration=25,max_duration=45,limit=1)
    assert len(calls) == 1 and audit['reason'] == 'provider_rejected' and not audit['attempted']


@pytest.mark.parametrize('second_valid', [True, False])
def test_truncated_ranking_has_one_compact_format_retry(monkeypatch, second_valid):
    calls = []
    def chat(config, messages):
        calls.append(messages)
        if len(calls) == 2 and second_valid:
            return json.dumps({'clips':[{'id':0,'score':90,'title':'Pintu Rahasia Akhirnya Terbuka'}]})
        return '{"clips":[{"id":0,"reason":"terpotong'
    monkeypatch.setattr(clipper,'chat_completion',chat)
    c = clipper.ClipCandidate(index=0,start=0,end=42,duration=42,score=80,
        title='Pintu rahasia',text=' '.join(TEXTS),reason='native')
    clipper.ai_rescore_candidates([c],AIConfig(True,'http://example.test/v1','demo'),target_count=1)
    assert len(calls) == 2 and c.start == 0 and c.end == 42
    assert c.title == ('Pintu Rahasia Akhirnya Terbuka' if second_valid else 'Pintu rahasia')


def job(key='failed-job', **updates):
    return api.ClipJob(id=key,status='failed',created_at=api.now_iso(),updated_at=api.now_iso(),
        request=api.ClipJobRequest(url=URL),error=api.SHORT_SELECTION_REJECTION_PREFIX,
        **updates)


def failed_item(**updates):
    return dict(job_id='failed-job',job_status='failed',status='failed',clip_count=0,
        source={'url':URL,'title':'Minecraft Indonesia'},error=api.SHORT_SELECTION_REJECTION_PREFIX) | updates


def test_failure_evidence_survives_media_cleanup_and_public_record_omits_transcript(monkeypatch,tmp_path):
    monkeypatch.setattr(api,'OUTPUTS_DIR',tmp_path/'outputs')
    root = api.OUTPUTS_DIR/'failed-job'; root.mkdir(parents=True)
    (root/'metadata.json').write_text(json.dumps({'title':'Sumber Minecraft','webpage_url':URL}))
    audit = dict(schema_version=1,source_url='https://youtu.be/abcdefghijk?t=4',attempted=True,
        outcome='replace_source',summary='Tidak ada alur utuh.',transcript_excerpt=[{'text':'source evidence'}])
    (root/'director_recovery.json').write_text(json.dumps(audit))
    api.jobs['failed-job'] = job()
    api.preserve_director_recovery_evidence('failed-job',root)
    api.cleanup_failed_job_artifacts(root)
    archived = api.SOURCE_USAGE_HISTORY_PATH.parent/'director_recovery/failed-job.json'
    assert json.loads(archived.read_text()) == audit
    assert archived.stat().st_mode & 0o777 == 0o600
    assert api.jobs['failed-job'].source_title == 'Sumber Minecraft'
    assert 'transcript_excerpt' not in api.jobs['failed-job'].director_recovery
    assert not root.exists()


@pytest.mark.parametrize('source_url', ['', OTHER])
def test_failure_evidence_with_wrong_identity_is_not_archived(tmp_path, source_url):
    root=tmp_path/'output';root.mkdir()
    (root/'director_recovery.json').write_text(json.dumps({'source_url':source_url,'summary':'wrong'}))
    api.jobs['failed-job']=job()
    api.preserve_director_recovery_evidence('failed-job',root)
    assert api.jobs['failed-job'].director_recovery['outcome']=='evidence_unavailable'
    assert not (api.SOURCE_USAGE_HISTORY_PATH.parent/'director_recovery/failed-job.json').exists()


@pytest.mark.parametrize('job_status,status',[('running','running'),('completed','failed')])
def test_deleted_failed_workspace_uses_exact_campaign_source_and_actual_next_job(job_status,status):
    api.auto_viral_runs['run']=SimpleNamespace(processed=[failed_item(),dict(job_id='next-job',
        job_status=job_status,status=status,source={'title':'Minecraft petunjuk baru','url':OTHER})])
    enriched=api.enrich_job_director_recovery(api.enrich_job_source_metadata(job()))
    assert enriched.source_title=='Minecraft Indonesia'
    assert enriched.status=='failed' and enriched.director_recovery['next_job_id']=='next-job'


def test_replacement_brief_preserves_rights_and_upload_policies():
    request=api.AutoViralRequest(source_rights_confirmed=True,source_rights_evidence='written permission')
    updated=api.director_replacement_request(request,failed_item())
    assert 'Minecraft' in updated.queries[0] and 'hasil' in updated.queries[0]
    before=request.model_dump();after=updated.model_dump()
    for key in ('queries','cron_short_role','director_source_recovery'):before.pop(key);after.pop(key)
    assert before==after


def test_long_existing_director_brief_is_not_truncated():
    request=api.AutoViralRequest(cron_short_role='a' * 800)
    assert api.director_replacement_request(request,failed_item()).cron_short_role==request.cron_short_role


@pytest.mark.parametrize('changes', [
    {'error':'Network timeout'}, {'job_status':'completed'}, {'clip_count':1},
    {'director_recovery':{'reason':'provider_rejected'}},
])
def test_replacement_does_not_reinterpret_unrelated_or_terminal_failures(changes):
    assert api.director_replacement_request(api.AutoViralRequest(),failed_item(**changes)) is None


def test_replacement_respects_news_and_explicit_source_scope():
    for request in (api.AutoViralRequest(cron_theme_key=api.NEWS_HOT_THEME),
                    api.AutoViralRequest(source_urls=[URL])):
        assert api.director_replacement_request(request,failed_item()) is None


def test_replacement_filters_duplicates_and_process_cap(monkeypatch):
    capped='https://www.youtube.com/watch?v=zyxwvutsrqp'
    monkeypatch.setattr(api,'append_auto_viral_log',lambda *a:None)
    monkeypatch.setattr(api,'discover_auto_viral_campaign_sources',lambda *a:[
        {'url':'https://youtu.be/abcdefghijk'}, {'url':capped}, {'url':OTHER}, {'url':OTHER}])
    monkeypatch.setattr(api,'cron_source_process_limit_reached',lambda url:url==capped)
    selected=api.discover_director_replacement(api.AutoViralRequest(),'run',failed_item(),{URL})
    assert len(selected)==1 and selected[0]['url']==OTHER
    assert 'Sudut pengganti' in selected[0]['director_short_role']


def test_director_search_really_uses_new_brief_instead_of_old_trend_or_channel_seed(monkeypatch):
    request=api.AutoViralRequest(cron_trend_lane=True,theme_focus='Tema lama')
    run=api.AutoViralRun(id='run',status='running',trigger='schedule',created_at=api.now_iso(),
        updated_at=api.now_iso(),request=request,director_source_search_attempted=True)
    api.auto_viral_runs[run.id]=run
    updated=api.director_replacement_request(request,failed_item())
    monkeypatch.setenv('YOUTUBE_DATA_API_KEY','test-only-key')
    monkeypatch.setenv('VIRAL_CC_MAX_API_QUERIES','1')
    monkeypatch.setattr(api,'youtube_trend_signals',lambda *a,**k:pytest.fail('old trend replaced new brief'))
    monkeypatch.setattr(api,'cron_gaming_channel_query_specs',lambda *a:pytest.fail('old channel query replaced new brief'))
    queries=[]
    def search(endpoint, params):
        assert endpoint=='search'
        queries.append(params['q'])
        assert params['safeSearch']=='strict'
        return {'items':[]}
    monkeypatch.setattr(api,'youtube_data_api_get',search)
    assert api.search_youtube_data_api_viral_sources(updated,run.id,exclude_urls={URL},stop_after=1)==[]
    assert queries==[updated.queries[0]] and 'Minecraft' in queries[0]


@pytest.mark.parametrize('trigger,budget,expected', [('manual',True,False),('schedule',False,False),('schedule',True,True)])
def test_director_search_flag_requires_reserved_scheduler_owner(trigger,budget,expected):
    request=api.AutoViralRequest(director_source_recovery=True)
    api.auto_viral_runs['run']=api.AutoViralRun(id='run',status='running',trigger=trigger,
        created_at=api.now_iso(),updated_at=api.now_iso(),request=request,director_source_search_attempted=budget)
    assert api.director_source_discovery_active('run',request) is expected


@pytest.mark.parametrize('previously_attempted', [False, True])
def test_campaign_adds_at_most_one_directed_replacement_and_does_not_restart_old_source(monkeypatch, previously_attempted):
    run=api.AutoViralRun(id='run',status='queued',trigger='schedule',created_at=api.now_iso(),
        updated_at=api.now_iso(),director_source_search_attempted=previously_attempted,request=api.AutoViralRequest(video_count=1,
            auto_upload_youtube=False,auto_upload_tiktok=False,create_paired_long_video=False))
    api.auto_viral_runs[run.id]=run
    searches=[];created=[];roles=[]
    def discover(request,*args):
        searches.append(request.queries)
        return [{'url':URL if len(searches)==1 else OTHER,'title':'Minecraft Indonesia'}]
    def create(source,request,*args):
        roles.append(request.cron_short_role)
        key=f'job-{len(created)}';created.append(source['url'])
        failed=job(key);failed.request.url=source['url'];api.jobs[key]=failed;return failed
    monkeypatch.setattr(api,'discover_auto_viral_campaign_sources',discover)
    monkeypatch.setattr(api,'create_auto_viral_clip_job',create)
    monkeypatch.setattr(api,'run_clip_job_with_campaign_progress',lambda *a:None)
    api.run_auto_viral_campaign(run.id)
    assert len(searches)==(1 if previously_attempted else 2)
    assert created==([URL] if previously_attempted else [URL,OTHER])
    assert api.auto_viral_runs[run.id].status=='failed'
    assert len(api.auto_viral_runs[run.id].processed)==len(created)
    assert api.AutoViralRun.model_validate_json(api.auto_viral_runs[run.id].model_dump_json()).director_source_search_attempted
    assert roles[0]==''
    if not previously_attempted:assert 'Sudut pengganti' in roles[1]
