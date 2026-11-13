"""Exercise discovery, persisted cron requests and both format creation paths."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import api
from cron_drama import DRAMA_THEME_PROFILES, drama_source_rejection_reason


@pytest.fixture(params=['chinese_drama_story','korean_drama_story'])
def lane(request,monkeypatch):
    monkeypatch.setenv('AUTO_VIRAL_SCHEDULE_KOREAN_DRAMA_ENABLED','true')
    return request.param


def source(lane):
    origin='drama china' if lane=='chinese_drama_story' else 'drama korea'
    return dict(url='https://www.youtube.com/watch?v=abcdefghijk',
      title=f'Ulasan {origin}: pilihan keluarga dan konsekuensi pengkhianatan',
      description='Narasi bahasa Indonesia tentang cerita fiksi, pilihan tokoh dan pelajaran hidup.',
      tags=['bahasa indonesia'],license='Creative Commons Attribution license',duration=1800,
      definition='hd',height=1080,upload_date=datetime.now(timezone.utc).strftime('%Y%m%d'),
      language='id',view_count=5000,uploader='Narator Cerita',channel_id='creator-one')


def request_for(lane):
    profile=DRAMA_THEME_PROFILES[lane]
    return api.AutoViralRequest(cron_theme_key=lane,cron_trend_lane=True,
      cron_editorial_tone=profile['tone'],cron_short_role=profile['short_role'],cron_long_role=profile['long_role'],
      creator_perspective='Saling mengingatkan dalam kebaikan dengan lembut sesuai agama Islam.',
      create_paired_long_video=True,paired_long_video_count=1,paired_long_duration=300)


def test_both_drama_lanes_enter_rotation_and_preserve_pairing(monkeypatch,lane):
    monkeypatch.setattr(api,'scheduled_news_hot_due',lambda:False)
    monkeypatch.setattr(api,'scheduled_ryuundy_theme_profile',lambda:(lane,DRAMA_THEME_PROFILES[lane]))
    monkeypatch.setattr(api,'auto_viral_daily_youtube_content_counts',lambda:{'short':0,'long':0})
    monkeypatch.setenv('AUTO_VIRAL_SCHEDULE_PAIRED_LONG_ENABLED','true')
    monkeypatch.setenv('AUTO_VIRAL_SCHEDULE_PAIRED_LONG_COUNT','1')
    monkeypatch.setenv('AUTO_VIRAL_SCHEDULE_AUTO_UPLOAD_YOUTUBE','false')
    for trend in ('true','false'):
        monkeypatch.setenv('AUTO_VIRAL_SCHEDULE_TREND_EXPANSION_ENABLED',trend)
        req=api.scheduled_auto_viral_request()
        restored=api.AutoViralRequest.model_validate(req.model_dump())
        assert restored.cron_theme_key==lane and restored.create_paired_long_video
        assert restored.paired_long_video_count>=1
        assert restored.queries[:len(DRAMA_THEME_PROFILES[lane]['queries'])+1]==req.queries[:len(DRAMA_THEME_PROFILES[lane]['queries'])+1]
        assert req.theme_focus in DRAMA_THEME_PROFILES[lane]['queries']
        for long_form in (False,True):
            direction=api.auto_viral_format_perspective(req,long_form=long_form)
            assert 'satu momen, satu makna' in direction
            assert 'fiksi/dramatisasi' in direction
            assert 'jangan menebak terjemahan' in direction
            assert (req.cron_long_role if long_form else req.cron_short_role) in direction


def test_language_and_story_fit_remain_required(lane):
    info=source(lane)
    assert api.cron_trend_candidate_rejection_reason(info,theme_key=lane)==''
    assert api.viral_search_hard_filter_rejection_reason(info,request_for(lane))==''
    other='korean_drama_story' if lane=='chinese_drama_story' else 'chinese_drama_story'
    assert 'asal drama' in api.cron_trend_candidate_rejection_reason(info,theme_key=other)
    origin='Chinese drama' if lane=='chinese_drama_story' else 'Korean drama'
    foreign=dict(title=f'{origin} family betrayal analysis',description='A character makes a choice.',language='en')
    assert 'Bahasa Indonesia' in api.cron_trend_candidate_rejection_reason(foreign,theme_key=lane)


@pytest.mark.parametrize('case',['raw_scenes','celebrity_news','unrelated','url_noise'])
def test_popularity_cannot_override_drama_story_contract(lane,case):
    origin='dracin' if lane=='chinese_drama_story' else 'drakor'
    info={
      'raw_scenes':{'title':f'{origin} cinta keluarga adegan terbaik'},
      'celebrity_news':{'title':f'Review {origin} aktor terbaru jadwal rilis'},
      'unrelated':{'title':'Ulasan idol Korea dan China memilih menu keluarga'},
      'url_noise':{'title':'Cerita keluarga','description':'https://example.org/drama-korea/drama-china/ulasan/keluarga'},
    }[case]
    info.update(view_count=100_000_000,language='id')
    assert drama_source_rejection_reason(info,lane)
    assert api.cron_trend_candidate_rejection_reason(info,theme_key=lane)
    assert api.viral_search_hard_filter_rejection_reason(info,request_for(lane))


def test_rights_and_content_id_preflight_is_not_overridden(lane):
    info=source(lane)
    assert api.viral_source_rejection_reason(info,require_creative_commons=True) is None
    assert api.viral_source_rejection_reason({**info,'license':'Standard YouTube License'},require_creative_commons=True)
    assert api.viral_source_rejection_reason({**info,'title':info['title']+' Full episode 12'},require_creative_commons=False)


def test_studio_demand_keeps_origin_and_ignores_other_niches(lane):
    query='indo korean drama' if lane=='korean_drama_story' else 'dracin'
    result=api.ryuundy_studio_trend_query(query,lane)
    assert ('drama korea' if lane=='korean_drama_story' else 'drama china') in result
    assert 'ulasan' in result and 'bahasa indonesia' in result
    assert not api.ryuundy_studio_trend_query('roblox gameplay lucu',lane)
    assert not api.ryuundy_studio_trend_query('dracin' if lane=='korean_drama_story' else 'drakor',lane)


def test_real_short_and_long_requests_carry_truthful_drama_metadata(monkeypatch,lane):
    captured=[]
    monkeypatch.setattr(api,'wait_for_no_active_clipping_job',lambda:None)
    monkeypatch.setattr(api,'normalize_job_request',lambda request:request)
    monkeypatch.setattr(api,'queue_auto_viral_clip_job',lambda request:captured.append(request) or SimpleNamespace(id='short-fixture',request=request))
    req=request_for(lane)
    short=api.create_auto_viral_clip_job(source(lane),req,scheduled=True)
    short.candidates=[SimpleNamespace(start=20,end=55)]
    api.create_auto_viral_paired_long_job(source(lane),req,short,wait_for_slot=False)
    assert len(captured)==2
    assert captured[0].clip_mode=='short' and captured[1].clip_mode=='highlight_5m'
    for job in captured:
        assert api.ClipJobRequest.model_validate(job.model_dump()).scheduled_theme_key == lane
        assert 'CeritaFiksi' in job.required_hashtags
        assert not any(tag in job.required_hashtags for tag in ('KisahNyata','KisahIslami'))
        assert 'sesuai agama Islam' not in job.creator_perspective
        assert job.scheduled_director_effects
    assert captured[1].compilation_anchor_ranges==[(20.0,55.0)]
    assert api.auto_viral_youtube_playlist(req)==''
    assert not api.auto_viral_youtube_made_for_kids(req)


def test_manual_search_and_non_drama_hashtags_keep_their_behavior():
    info={'title':'Review drama Korea terbaru'}
    req=api.ViralVideoSearchRequest(duration_filter='any',definition_filter='any')
    # This would fail the drama story guard, but manual search never gets it.
    assert drama_source_rejection_reason(info,'')==''
    dated={**info,'upload_date':datetime.now(timezone.utc).strftime('%Y%m%d')}
    assert api.viral_search_hard_filter_rejection_reason(dated,req)==''
    assert api.source_theme_hashtags({'title':'Ceramah Islam tentang sabar'})==api.source_theme_hashtags({'title':'Ceramah Islam tentang sabar'},theme_key='')


def test_actual_rotation_explores_unused_drama_lane(monkeypatch,lane):
    monkeypatch.setattr(api,'scheduled_islamic_animation_trial_profile',lambda:None)
    monkeypatch.setattr(api,'scheduled_performance_winner_profile',lambda:None)
    monkeypatch.setattr(api,'scheduled_search_term_winner_profile',lambda:None)
    now=datetime.now(timezone.utc).isoformat()
    runs={key:SimpleNamespace(trigger='schedule',created_at=now,
        request=SimpleNamespace(cron_theme_key=key)) for key in api.RYUUNDY_CRON_THEME_PROFILES if key!=lane}
    monkeypatch.setattr(api,'auto_viral_runs',runs)
    assert api.scheduled_ryuundy_theme_profile()[0]==lane


def test_off_theme_live_trends_do_not_spend_drama_search_budget(monkeypatch,lane):
    monkeypatch.setenv('YOUTUBE_DATA_API_KEY','offline-test-key')
    monkeypatch.setenv('VIRAL_CC_MAX_API_QUERIES','1')
    monkeypatch.setattr(api,'cron_humor_discovery_active',lambda *a:False)
    monkeypatch.setattr(api,'cron_trend_discovery_active',lambda *a:True)
    monkeypatch.setattr(api,'director_source_discovery_active',lambda *a:False)
    monkeypatch.setattr(api,'youtube_channel_search_term_signals',lambda *a:(['roblox gameplay lucu'],set()))
    monkeypatch.setattr(api,'youtube_studio_trend_reference_signals',lambda *a:[])
    monkeypatch.setattr(api,'youtube_trend_signals',lambda *a,**k:(['roblox gameplay lucu','berita politik indonesia'],set()))
    monkeypatch.setattr(api,'append_auto_viral_log',lambda *a:None)
    monkeypatch.setattr(api,'append_auto_viral_error',lambda *a:None)
    queries=[]
    def get(resource,params):
        assert resource=='search';queries.append(params['q']);return {'items':[]}
    monkeypatch.setattr(api,'youtube_data_api_get',get)
    req=request_for(lane)
    req.theme_focus=DRAMA_THEME_PROFILES[lane]['queries'][0]
    assert api.search_youtube_data_api_viral_sources(req,'fixture-run')==[]
    assert queries and all('roblox' not in query and 'politik' not in query for query in queries)
    assert req.theme_focus==queries[0]


def test_korea_is_excluded_by_default_even_when_performance_or_demand_wins(monkeypatch):
    monkeypatch.delenv('AUTO_VIRAL_SCHEDULE_KOREAN_DRAMA_ENABLED',raising=False)
    winner=('korean_drama_story',DRAMA_THEME_PROFILES['korean_drama_story'])
    monkeypatch.setattr(api,'scheduled_islamic_animation_trial_profile',lambda:None)
    monkeypatch.setattr(api,'scheduled_performance_winner_profile',lambda:winner)
    monkeypatch.setattr(api,'scheduled_search_term_winner_profile',lambda:winner)
    for _ in range(8):assert api.scheduled_ryuundy_theme_profile()[0]!='korean_drama_story'
    labels=api.AutoViralScheduleStatus.model_fields['cron_drama_lanes'].get_default(call_default_factory=True)
    assert 'chinese_drama_story' in labels and 'korean_drama_story' not in labels
    monkeypatch.setenv('AUTO_VIRAL_SCHEDULE_KOREAN_DRAMA_ENABLED','true')
    assert api.scheduled_ryuundy_theme_profile()[0]=='korean_drama_story'
