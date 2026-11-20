from datetime import date, datetime, timedelta, timezone
import json
from types import SimpleNamespace as NS

from hijridate import Hijri
import pytest

import api
import cron_editorial as policy


NORMAL = datetime(2026, 11, 20, 12, tzinfo=policy.ZONE)


def state(slot=0, plan=None):
    return dict(version=1, selection_count=slot, monthly_plan=plan or {}, reserved_runs=[])


def pick(slot, when=NORMAL, plan=None):
    key = "gaming_story"
    return policy.select_profile(state(slot, plan), key, api.RYUUNDY_CRON_THEME_PROFILES[key],
        api.RYUUNDY_CRON_THEME_PROFILES, when)


@pytest.mark.parametrize("day,expected", [
    (date(2026,11,20),""),
    (date(2027,1,15),"approaching_ramadan"),
    (date(2027,2,10),"ramadan"),
    (date(2027,2,28),"ramadan_last_ten"),
    (date(2027,3,10),"eid"),
    (date(2027,5,18),"hajj_qurban"),
    (date(2027,8,10),"independence"),
    (date(2026,12,20),"year_end"),
])
def test_seasons_follow_hijri_and_local_calendar(day, expected):
    context = policy.season_context(day)
    assert context["key"] == expected
    assert context["timezone"] == "Asia/Jakarta"
    assert context["official_religious_date_confirmed"] is False


def test_ramadan_moves_each_year_and_is_not_fixed_to_a_gregorian_month():
    first = Hijri(1448,9,1).to_gregorian()
    second = Hijri(1449,9,1).to_gregorian()
    assert first.month != second.month
    assert policy.season_context(date(first.year,first.month,first.day))["key"] == "ramadan"
    assert policy.season_context(date(second.year,second.month,second.day))["key"] == "ramadan"


def test_jakarta_date_boundary_controls_the_phase():
    assert policy.season_context(datetime(2027,2,7,18,tzinfo=timezone.utc))["key"] == "ramadan"
    assert policy.season_context(datetime(2027,2,7,16,tzinfo=timezone.utc))["key"] == "approaching_ramadan"


def test_ramadan_priority_preserves_other_subjects_and_changes_after_season():
    assert sum(pick(i, date(2027,2,10))[0] == "ramadan_season" for i in range(40)) == 30
    assert sum(pick(i, date(2027,1,15))[0] == "ramadan_season" for i in range(40)) == 16
    assert all(pick(i, date(2027,4,15))[0] != "ramadan_season" for i in range(40))


def test_speaker_search_seeds_rotate_and_include_generic_discovery():
    names = [pick(i*4)[2]["speaker_seed"] for i in range(len(policy.SPEAKERS)+1)]
    assert set(names) == {*policy.SPEAKERS, ""}
    assert all(pick(i*4)[0] == "lecture_wisdom" for i in range(len(names)))
    assert len(policy.SPEAKERS) >= 18


def test_preview_does_not_consume_slots_and_state_survives_pruned_history(tmp_path):
    path = tmp_path/"editorial.json"
    assert not path.exists()
    for _ in range(3):
        assert policy.read_state(path)["selection_count"] == 0
    assert not path.exists()
    policy.record_selection(path, "run-199", 199)
    policy.record_selection(path, "run-199", 199)
    assert policy.read_state(path)["selection_count"] == 200
    policy.record_selection(path, "run-200", 200)
    assert policy.read_state(path)["selection_count"] == 201


@pytest.mark.parametrize("raw", ["{", "[]", '{"version":1,"selection_count":-1}', '{"version":2,"selection_count":0}',
    '{"version":1,"selection_count":0,"monthly_plan":[]}'])
def test_corrupt_state_cannot_be_reset_or_overwritten(raw, tmp_path):
    path=tmp_path/"editorial.json";path.write_text(raw)
    with pytest.raises((ValueError, TypeError)):
        policy.record_selection(path,"run",0)
    assert path.read_text() == raw


def build_plan(now=NORMAL):
    records=[
        dict(text="Kajian ustadz tentang sabar menghadapi ujian kehidupan",source="youtube_most_popular_id",weight=3000),
        dict(text="Teknologi kecerdasan buatan inovasi Indonesia",source="google_trends_rss",weight=1),
        dict(text="Teknologi kecerdasan buatan inovasi Indonesia",source="youtube_channel_search_terms",weight=2),
        dict(text="Judi online teknologi tipu orang",source="google_trends_rss",weight=100000),
        dict(text="XYZ tidak berkaitan",source="google_trends_rss"),
    ]
    return policy.build_monthly_plan(records,api.RYUUNDY_CRON_THEME_PROFILES,
        api.RYUUNDY_CRON_THEME_SIGNALS,api.CRON_TREND_UNSAFE_SIGNALS,now)


def test_monthly_plan_uses_live_subjects_not_random_static_topic_names():
    plan=build_plan()
    assert plan["month_key"]=="2026-11" and plan["status"]=="ready"
    assert len(plan["niches"])==2
    assert {r["theme_key"] for r in plan["niches"]}=={"lecture_wisdom","practical_knowledge"}
    assert all(not r["verified_facts"] and not r["grants_source_rights"] for r in plan["niches"])
    assert all(r["evidence"]["source"] for r in plan["niches"])
    assert not plan["automatic_publication_authorized"]


def test_monthly_subject_must_be_in_title_and_avoids_music_or_live_charts():
    records=[
        dict(text="Judul lagu romantis populer",supporting_text="sejarah teknologi keluarga"),
        dict(text="Keluarga bahagia official music video"),
        dict(text="Cerita keluarga populer",category_id="10"),
        dict(text="Roblox misteri petualangan live",live_broadcast_content="live"),
        dict(text="Roblox misteri baru",live_broadcast_content="upcoming"),
        dict(text="Cerita keluarga Indonesia tentang saling peduli",category_id="22"),
    ]
    plan=policy.build_monthly_plan(records,api.RYUUNDY_CRON_THEME_PROFILES,
        api.RYUUNDY_CRON_THEME_SIGNALS,api.CRON_TREND_UNSAFE_SIGNALS,NORMAL)
    assert len(plan["niches"])==1
    assert plan["niches"][0]["topic"]==records[-1]["text"]


def test_monthly_diversity_reserves_smaller_themes_before_more_chart_subjects():
    profiles={f"theme{i}":{} for i in range(5)}
    signals={key:{key} for key in profiles}
    records=[dict(text=f"{key} topic {j} has original question and example",
        source="test",weight=100000 if key!="theme4" else 1)
        for key in profiles for j in range(3)]
    plan=policy.build_monthly_plan(records,profiles,signals,set(),NORMAL)
    assert len(plan["niches"])==12
    assert {row["theme_key"] for row in plan["niches"]}==set(profiles)
    assert len({row["theme_key"] for row in plan["niches"][:5]})==5


def test_mixed_lecture_and_politics_keeps_the_existing_review_theme():
    plan=policy.build_monthly_plan([dict(
        text="Ustadz Das&#39;ad Latif menjawab politik negeri dalam kajian ceramah nasihat kehidupan",
        source="youtube_monthly_kajian_id")],api.RYUUNDY_CRON_THEME_PROFILES,
        api.RYUUNDY_CRON_THEME_SIGNALS,api.CRON_TREND_UNSAFE_SIGNALS,NORMAL)
    assert plan["niches"][0]["theme_key"]=="domestic_politics"
    assert "Das'ad" in plan["niches"][0]["topic"]


def test_monthly_selection_and_stale_month_rejection():
    plan=build_plan()
    key,profile,meta=pick(2,plan=plan)
    assert meta["monthly_niche_id"].startswith("monthly_202611_")
    assert key in {"lecture_wisdom","practical_knowledge"}
    assert profile["queries"] == plan["niches"][0]["queries"]
    _,_,nextmeta=pick(2,datetime(2026,12,10,tzinfo=policy.ZONE),plan)
    assert nextmeta["monthly_niche_id"]==""


def test_refresh_retries_unavailable_sources_and_rolls_over_month(tmp_path):
    path=tmp_path/"editorial.json"
    when=datetime(2026,11,30,23,tzinfo=policy.ZONE)
    assert policy.claim_refresh(path,when)
    assert not policy.claim_refresh(path,when+timedelta(minutes=1))
    assert policy.claim_refresh(path,when+timedelta(hours=1))  # Jakarta December boundary
    plan=build_plan(datetime(2026,12,1,tzinfo=policy.ZONE))
    policy.finish_refresh(path,plan)
    assert not policy.refresh_due(policy.read_state(path),datetime(2026,12,20,tzinfo=policy.ZONE))
    assert policy.refresh_due(policy.read_state(path),datetime(2027,1,1,tzinfo=policy.ZONE))


@pytest.fixture
def adaptive(monkeypatch):
    monkeypatch.setenv("AUTO_VIRAL_SCHEDULE_DYNAMIC_EDITORIAL_ENABLED","true")
    monkeypatch.setattr(api,"scheduled_news_hot_due",lambda:False)
    monkeypatch.setattr(api,"scheduled_ryuundy_theme_profile",lambda:
        ("gaming_story",dict(api.RYUUNDY_CRON_THEME_PROFILES["gaming_story"])))
    monkeypatch.setenv("AUTO_VIRAL_SCHEDULE_AUTO_UPLOAD_YOUTUBE","false")
    monkeypatch.setenv("AUTO_VIRAL_SCHEDULE_AUTO_UPLOAD_TIKTOK","false")
    return monkeypatch


def test_cron_factory_applies_policy_but_manual_constructor_does_not(adaptive):
    cron=api.scheduled_auto_viral_request()
    assert cron.cron_theme_key=="lecture_wisdom"
    assert cron.cron_editorial_slot==0 and cron.cron_editorial_month
    assert cron.source_urls==[]
    restored=api.AutoViralRequest.model_validate(cron.model_dump())
    assert restored.cron_speaker_seed==cron.cron_speaker_seed
    assert restored.queries[0]==cron.theme_focus
    assert set(restored.queries) <= set(cron.cron_editorial_queries)
    manual=api.AutoViralRequest(queries=["pilihan saya sendiri"],theme_focus="pilihan saya sendiri")
    assert manual.cron_theme_key=="" and manual.cron_editorial_slot==-1
    assert not manual.cron_season_key and not manual.cron_speaker_seed


def test_manual_discovery_cannot_disable_or_inherit_channel_preferences(adaptive):
    adaptive.setattr(api,"scheduled_auto_viral_discovery_active",lambda run:False)
    assert not (api.cron_editorial_enabled() and api.scheduled_auto_viral_discovery_active("manual"))


def test_cron_search_never_calls_exact_channel_helpers(adaptive):
    adaptive.setenv("YOUTUBE_DATA_API_KEY","test-only-key")
    adaptive.setenv("VIRAL_CC_MAX_API_QUERIES","3")
    adaptive.setattr(api,"scheduled_auto_viral_discovery_active",lambda run:True)
    adaptive.setattr(api,"cron_trend_discovery_active",lambda *a:False)
    adaptive.setattr(api,"cron_humor_discovery_active",lambda *a:False)
    adaptive.setattr(api,"director_source_discovery_active",lambda *a:False)
    adaptive.setattr(api,"youtube_trend_signals",lambda *a,**k:([],set()))
    adaptive.setattr(api,"cron_gaming_channel_query_specs",lambda *a:pytest.fail("No channel ID restriction"))
    adaptive.setattr(api,"cron_reference_channel_query_specs",lambda *a:pytest.fail("No reference channel priority"))
    adaptive.setattr(api,"youtube_data_api_search_queries",lambda *a,**k:["game cerita indonesia"])
    calls=[]
    adaptive.setattr(api,"youtube_data_api_get",lambda path,params:calls.append(params) or {"items":[]})
    api.search_youtube_data_api_viral_sources(api.AutoViralRequest(cron_theme_key="gaming_story"),"cron")
    assert calls and all("channelId" not in params for params in calls)


def test_monthly_maintenance_runs_once_with_local_retry_state(adaptive):
    adaptive.setattr(api,"collect_cron_editorial_signals",lambda:([
        dict(text="Teknologi kecerdasan buatan inovasi Indonesia",source="test_live_feed")],[]))
    assert api.refresh_cron_editorial_once(NORMAL)
    assert not api.refresh_cron_editorial_once(NORMAL+timedelta(days=1))
    current=policy.status(api.cron_editorial_state_path(),NORMAL)
    assert current["monthly_plan_current"] and current["scope"]=="cron_only"
    assert current["monthly_plan"]["niches"][0]["theme_key"]=="practical_knowledge"


def test_live_monthly_research_adds_open_current_month_kajian_and_knowledge(adaptive):
    adaptive.setenv("YOUTUBE_DATA_API_KEY","test-only-key")
    adaptive.setattr(policy,"local_now",lambda now=None:NORMAL)
    adaptive.setattr(api,"load_youtube_search_term_cache",lambda **k:[])
    adaptive.setattr(api,"load_youtube_studio_trend_cache",lambda **k:[])
    adaptive.setattr(api,"google_trends_rss_signals",lambda *a:([],set()))
    calls=[]
    def feed(resource, options):
        calls.append((resource,options))
        return {"items":[dict(id={"videoId":"abcdefghijk"} if resource=="search" else "abcdefghijk",
            snippet={"title":"Kajian ustadz sabar menghadapi ujian kehidupan", "liveBroadcastContent":"none"})]}
    adaptive.setattr(api,"youtube_data_api_get",feed)
    records, errors=api.collect_cron_editorial_signals()
    assert not errors and len(records)==3
    searches=[options for resource,options in calls if resource=="search"]
    assert len(searches)==2
    assert all("channelId" not in options for _,options in calls)
    assert all(options["publishedAfter"]=="2026-10-31T17:00:00Z" for options in searches)
    assert any("kajian" in options["q"] for options in searches)
    assert any("sains" in options["q"] for options in searches)
    assert records[-1]["url"]=="https://www.youtube.com/watch?v=abcdefghijk"


def test_monthly_political_discovery_preserves_publication_hold(adaptive):
    profile=api.RYUUNDY_CRON_THEME_PROFILES["domestic_politics"]
    adaptive.setattr(api,"scheduled_ryuundy_theme_profile",lambda:("domestic_politics",profile))
    adaptive.setenv("AUTO_VIRAL_SCHEDULE_AUTO_UPLOAD_YOUTUBE","true")
    adaptive.setattr(api,"scheduled_auto_viral_youtube_browser_ready",lambda:True)
    adaptive.setattr(api,"scheduled_auto_viral_rights_profile_ready",lambda:True)
    path=api.cron_editorial_state_path()
    plan=dict(month_key=policy.local_now().strftime("%Y-%m"),status="ready",niches=[dict(
        id="monthly_political_test",theme_key="domestic_politics",topic="Kebijakan publik terbaru",
        queries=["kebijakan publik indonesia pembahasan sumber"])])
    policy.save_state(path,state(2,plan))
    request=api.scheduled_auto_viral_request()
    assert request.cron_monthly_niche_id=="monthly_political_test"
    assert not request.auto_upload_youtube
    assert not request.auto_publish_paired_long_video


def test_disabled_policy_starts_no_worker_or_network(monkeypatch):
    monkeypatch.setattr(api,"collect_cron_editorial_signals",lambda:pytest.fail("Policy disabled"))
    assert not api.refresh_cron_editorial_once(NORMAL)
    api.start_cron_editorial_refresh_if_due()


def test_policy_status_is_read_only_and_does_not_spawn_refresh(adaptive):
    path=api.cron_editorial_state_path()
    assert not path.exists()
    status=api.get_cron_editorial_policy()
    assert status["scope"]=="cron_only" and status["all_channel_search"]
    assert not status["manual_requests_modified"] and not status["speaker_whitelist"]
    assert not path.exists()


def test_seasonal_source_gate_and_hashtags_do_not_accept_unrelated_gameplay():
    assert "tema tidak cocok" in api.cron_trend_candidate_rejection_reason(
        {"title":"Roblox gameplay Indonesia lucu"},theme_key="ramadan_season")
    for key in policy.SEASONAL_PROFILES:
        assert key in api.CRON_ISLAMIC_THEME_KEYS
        assert api.source_theme_hashtags({},theme_key=key)
        assert not api.auto_viral_youtube_made_for_kids(api.AutoViralRequest(cron_theme_key=key))


def test_slot_advances_only_when_a_cron_campaign_is_created(adaptive):
    adaptive.setattr(api,"auto_viral_active_run_id",None)
    adaptive.setattr(api,"save_auto_viral_runs_unlocked",lambda:None)
    adaptive.setattr(api.threading,"Thread",lambda *a,**k:NS(start=lambda:None))
    first=api.scheduled_auto_viral_request()
    assert not api.cron_editorial_state_path().exists()
    run=api.create_and_start_auto_viral_campaign(first,trigger="schedule")
    assert run.request.cron_editorial_slot==0
    assert policy.read_state(api.cron_editorial_state_path())["selection_count"]==1
    adaptive.setattr(api,"auto_viral_active_run_id",None)
    api.create_and_start_auto_viral_campaign(first,trigger="manual")
    assert policy.read_state(api.cron_editorial_state_path())["selection_count"]==1


def test_both_formats_keep_cron_provenance_and_manual_job_is_unchanged(adaptive):
    captured=[]
    adaptive.setattr(api,"wait_for_no_active_clipping_job",lambda:None)
    adaptive.setattr(api,"normalize_job_request",lambda request:request)
    adaptive.setattr(api,"queue_auto_viral_clip_job",lambda request:
        captured.append(request) or NS(id="short",request=request))
    # Synthetic rights evidence for this isolated source fixture only.
    source=dict(url="https://www.youtube.com/watch?v=abcdefghijk",
        title="Kajian ramadan puasa Indonesia",duration=1200,view_count=5000,
        license="Creative Commons Attribution license")
    request=api.AutoViralRequest(cron_theme_key="ramadan_season",cron_editorial_slot=4,
        cron_editorial_month="2027-02",cron_season_key="ramadan",
        cron_speaker_seed="Ustadz Adi Hidayat",create_paired_long_video=True,paired_long_video_count=1)
    short=api.create_auto_viral_clip_job(source,request,scheduled=True)
    short.candidates=[NS(start=10,end=45)]
    api.create_auto_viral_paired_long_job(source,request,short,wait_for_slot=False)
    for row in captured:
        context=api.ClipJobRequest.model_validate(row.model_dump()).scheduled_editorial_context
        assert context["month"]=="2027-02" and context["season"]=="ramadan"
        assert row.scheduled_theme_key=="ramadan_season"
        assert not row.scheduled_contextual_audio
    api.create_auto_viral_clip_job(source,request,scheduled=False)
    assert captured[-1].scheduled_editorial_context=={}
    assert captured[-1].scheduled_theme_key==""


def test_empty_monthly_feed_does_not_fabricate_discovery_success(adaptive):
    adaptive.setattr(api,"collect_cron_editorial_signals",lambda:([],[
        {"source":"youtube_most_popular_id","status":"unavailable"}]))
    assert api.refresh_cron_editorial_once(NORMAL)
    report=policy.status(api.cron_editorial_state_path(),NORMAL)
    assert not report["monthly_plan_current"]
    assert report["monthly_plan"]["niches"]==[]
    assert report["monthly_plan"]["status"]=="no_matching_live_signals"
    assert not api.refresh_cron_editorial_once(NORMAL+timedelta(hours=1))


