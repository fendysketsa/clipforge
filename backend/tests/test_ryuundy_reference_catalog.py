"""Owner references reach discovery and editing without becoming upload permissions."""
import pytest

import api
import cron_long_strategy
import ryuundy_editorial_themes as themes
import ryuundy_reference_catalog as catalog
from youtube_playlists import classify_youtube_playlist


def test_all_four_references_have_explicit_evidence_and_no_automatic_reupload():
    report = api.get_ryuundy_references()
    assert report['reference_count'] == 4
    assert {r['key'] for r in report['references']} == {
        'kartun_acing_moral_story', 'uah_contextual_sermon_short',
        'zamanemas_indonesia_1980', 'dunia_sjr_history_reference',
    }
    for key in ['transcripts_verified', 'full_audiovisual_review_verified',
                'retention_verified', 'grants_source_rights', 'automatic_reference_reupload']:
        assert report[key] is False
    report['references'][0]['channel_id'] = 'tampered'
    assert catalog.reference_catalog()['references'][0]['channel_id'] != 'tampered'


def test_unresolved_external_handle_is_not_invented_as_a_youtube_channel():
    row = next(r for r in catalog.REFERENCES if r['handle'] == '@dunia.sjr')
    assert not row['youtube_channel_verified'] and not row['channel_search_enabled']
    assert row['channel_id'] == '' and row['url'] == ''
    assert catalog.channel_search_specs('nostalgia_indonesia') == [('', 'UCtou1nUKZ-hNxXK4HIhp-6w')]


def test_short_sermon_is_format_reference_and_cannot_supply_long_material():
    row = next(r for r in catalog.REFERENCES if r['theme_key'] == 'lecture_wisdom')
    assert row['duration_seconds'] == 35 and not row['channel_search_enabled']
    assert catalog.channel_search_specs('lecture_wisdom') == []
    assert not cron_long_strategy.source_profile({'duration':35, 'view_count':1778})['eligible']
    assert any('Adi Hidayat' in q for q in api.RYUUNDY_CRON_THEME_PROFILES['lecture_wisdom']['queries'])


@pytest.mark.parametrize('key', ['moral_animation_story', 'nostalgia_indonesia', 'lecture_wisdom'])
@pytest.mark.parametrize('long_form', [False, True])
def test_editorial_adaptation_reaches_each_format_and_keeps_manual_isolated(key, long_form):
    profile = api.RYUUNDY_CRON_THEME_PROFILES[key]
    request = api.AutoViralRequest(cron_theme_key=key, cron_editorial_tone=profile['tone'],
        cron_short_role=profile['short_role'], cron_long_role=profile['long_role'])
    prompt = api.auto_viral_format_perspective(request, long_form=long_form)
    assert catalog.editorial_brief(key) in prompt
    assert (profile['long_role'] if long_form else profile['short_role']) in prompt
    manual = api.AutoViralRequest(creator_perspective='Arahan manual asli')
    assert api.auto_viral_format_perspective(manual, long_form=long_form) == 'Arahan manual asli'


@pytest.mark.parametrize('key,expected', [
    ('moral_animation_story', 'Animasi Cerita Moral'),
    ('nostalgia_indonesia', 'Nostalgia & Indonesia Tempo Dulu'),
])
def test_persisted_theme_routes_playlist_without_unrelated_religious_labels(key, expected):
    assert classify_youtube_playlist('Judul generik', theme_key=key) == expected
    for long_form in [False, True]:
        tags = api.source_theme_hashtags({}, theme_key=key, long_form=long_form)
        assert not {'Islam', 'KisahIslami', 'KisahNyata', 'AzabNyata'} & set(tags)
    assert api.auto_viral_youtube_made_for_kids(api.AutoViralRequest(cron_theme_key=key)) is False


def test_real_world_accusation_cannot_enter_fictional_animation_lane():
    reason = api.cron_trend_candidate_rejection_reason({
        'title':'Pedagang curang menjual makanan busuk', 'default_language':'id',
    }, theme_key='moral_animation_story')
    assert 'animasi/kartun fiksi' in reason


@pytest.mark.parametrize('key,title', [
    ('moral_animation_story', 'Animasi cerita moral Indonesia pedagang curang dan kejujuran'),
    ('nostalgia_indonesia', 'Nostalgia Indonesia 1980 kehidupan sekolah dan permainan tempo dulu'),
])
def test_new_topics_have_real_trend_signals_without_mocking_quality_scores(key, title):
    assert not api.cron_trend_candidate_rejection_reason({
        'title':title, 'default_language':'id',
    }, theme_key=key)


@pytest.mark.parametrize('scheduled', [False, True])
def test_exact_channel_hints_are_exclusive_to_scheduled_discovery(monkeypatch, scheduled):
    monkeypatch.setattr(api, 'scheduled_auto_viral_discovery_active', lambda run: scheduled)
    request = api.AutoViralRequest(cron_theme_key='moral_animation_story')
    specs = api.cron_reference_channel_query_specs(request, 'run')
    assert specs == ([('', 'UCRsbWgKYa7WyhgogHzfZwTw')] if scheduled else [])


@pytest.mark.parametrize('budget,director', [(1, False), (2, False), (3, False), (2, True)])
def test_reference_search_keeps_budget_general_sources_and_director_isolation(monkeypatch, budget, director):
    monkeypatch.setenv('YOUTUBE_DATA_API_KEY', 'test-only-key')
    monkeypatch.setenv('VIRAL_CC_MAX_API_QUERIES', str(budget))
    monkeypatch.setattr(api, 'scheduled_auto_viral_discovery_active', lambda run: True)
    monkeypatch.setattr(api, 'cron_humor_discovery_active', lambda *a: False)
    monkeypatch.setattr(api, 'cron_trend_discovery_active', lambda *a: False)
    monkeypatch.setattr(api, 'director_source_discovery_active', lambda *a: director)
    monkeypatch.setattr(api, 'youtube_trend_signals', lambda *a, **k: ([], set()))
    queries = ['nostalgia indonesia tempo dulu', 'sejarah sekolah indonesia']
    monkeypatch.setattr(api, 'youtube_data_api_search_queries', lambda *a, **k: queries)
    monkeypatch.setattr(api, 'append_auto_viral_log', lambda *a: None)
    observed = []
    def get(path, params):
        assert path == 'search'
        observed.append(params)
        return {'items':[]}
    monkeypatch.setattr(api, 'youtube_data_api_get', get)
    request = api.AutoViralRequest(cron_theme_key='nostalgia_indonesia', queries=queries)
    assert api.search_youtube_data_api_viral_sources(request, 'run') == []
    assert len(observed) <= budget
    assert any('channelId' not in params for params in observed)
    if budget > 1 and not director:
        assert observed[0]['channelId'] == 'UCtou1nUKZ-hNxXK4HIhp-6w'
        assert observed[1]['q'] == queries[0]
    else:
        assert all('channelId' not in params for params in observed)


def test_new_profiles_do_not_enqueue_reference_urls_or_grant_rights(monkeypatch):
    monkeypatch.setattr(api, 'scheduled_news_hot_due', lambda: False)
    monkeypatch.setattr(api, 'scheduled_ryuundy_theme_profile', lambda:
        ('nostalgia_indonesia', themes.PROFILES['nostalgia_indonesia']))
    monkeypatch.setenv('AUTO_VIRAL_SCHEDULE_SOURCE_RIGHTS_CONFIRMED', 'false')
    monkeypatch.setenv('AUTO_VIRAL_SCHEDULE_AUTO_UPLOAD_YOUTUBE', 'false')
    request = api.scheduled_auto_viral_request()
    assert request.source_urls == [] and not request.source_rights_confirmed
    assert request.queries and set(request.queries) <= set(themes.PROFILES['nostalgia_indonesia']['queries'])
    restored = api.AutoViralRequest.model_validate(request.model_dump())
    assert restored.cron_theme_key == 'nostalgia_indonesia'


def test_capability_contract_exposes_reference_version_and_new_niches():
    contract = api.get_cron_long_strategy()
    assert contract['reference_catalog_version'] == 1 and contract['reference_count'] == 4
    assert {'moral_animation_story', 'nostalgia_indonesia'} <= {r['key'] for r in contract['themes']}
