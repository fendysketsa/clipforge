"""Useful structure must survive noisy references without loosening export gates."""
import json

import pytest

from ryuundy_reference_learning import (
    RYUUNDY_REFERENCE_EDITOR_BRIEF, meaningful_trend_tokens,
    practical_payoff_profile, source_trend_matches,
)


PRACTICAL = (
    "Kenapa subtitle terasa susah dibaca ketika kalimat panjang muncul di layar? "
    "Coba pisahkan subtitle menjadi dua baris dan atur jeda sesuai akhir kalimat pembicara. "
    "Hasilnya subtitle lebih mudah dibaca karena kalimat tetap utuh dan layar tidak terlalu penuh."
)


def test_problem_action_and_specific_result_preserve_exact_evidence():
    profile = practical_payoff_profile(PRACTICAL, 32)
    assert profile['qualified']
    assert all(quote in PRACTICAL for quote in profile['evidence'].values())
    assert not profile['visual_demonstration_verified']
    assert not profile['claims_verified']
    assert not profile['actual_retention_prediction']


@pytest.mark.parametrize('duration', [0, 2, 17.9, 65.1, 180, float('nan'), float('inf'), True])
def test_reference_length_is_not_permission_to_extend_every_short(duration):
    assert not practical_payoff_profile(PRACTICAL, duration)['qualified']


@pytest.mark.parametrize('text', [
    'Kenapa susah viral? Coba klik tombol ini. Hasilnya pasti viral dan dijamin cuan.',
    'Kenapa subtitle sulit dibaca? Coba pilih template dan atur warna yang cocok dengan sumber. Hasilnya bagus.',
    'Kenapa subtitle sulit dibaca? Tonton sampai akhir untuk mengetahui trik yang dipakai semua editor profesional. Hasilnya subtitle bisa dibaca dengan lebih mudah oleh semua penonton.',
    'Coba pisahkan subtitle menjadi dua baris. Kenapa subtitle sulit dibaca ketika kalimatnya panjang? Hasilnya subtitle lebih mudah dibaca karena teks tetap utuh dan layar tidak penuh.',
    PRACTICAL.rsplit('Hasilnya', 1)[0],
])
def test_teasers_reversed_structure_and_vague_results_are_not_useful_payoff(text):
    assert not practical_payoff_profile(text, 32)['qualified']


def test_url_footers_and_generic_words_cannot_manufacture_topic_demand():
    info = {'title': 'Cerita pemain Roblox', 'description': (
        'Jangan lupa subscribe dan follow!\nhttps://www.example.com/football/champions\n'
        'Follow minecraft di https://youtube.com/@minecraft\nContact: hello@example.net'
    )}
    demand = {'com', 'www', 'jangan', 'sampai', 'minecraft', 'football', 'champions'}
    assert source_trend_matches(info, demand) == []
    assert source_trend_matches(info, demand | {'roblox'}) == ['roblox']


def test_actual_subject_and_person_names_remain_available():
    assert {'raditya', 'dika', 'subtitle', 'roblox'} <= meaningful_trend_tokens(
        'Raditya Dika menjelaskan subtitle untuk Roblox'
    )


def test_source_trend_bonus_uses_meaningful_tokens_only():
    import api

    source = {'title': 'Roblox survival cerita', 'description': 'Jangan sampai lupa https://www.youtube.com/watch?v=abcdefghijk'}
    base, _ = api.cron_trend_score(source)
    noisy, matches = api.cron_trend_score(source, {'jangan', 'sampai', 'com', 'www', 'youtube'})
    assert noisy == base and matches == []
    real, matches = api.cron_trend_score(source, {'roblox', 'jangan', 'com'})
    assert real == base + 6 and matches == ['roblox']


def test_link_paths_and_promotion_cannot_supply_supporting_topic_points():
    import api

    source = {'title': 'Cerita Roblox survival'}
    clean_score, _ = api.cron_trend_score(source)
    promoted = source | {'description': (
        'https://example.com/football/minecraft/podcast\n'
        'Follow podcast dan minecraft untuk informasi lainnya'
    )}
    assert api.cron_trend_score(promoted)[0] == clean_score


def test_editor_brief_keeps_manual_and_news_context_separate():
    import api

    manual = api.AutoViralRequest(creator_perspective='Analisis saya tentang keputusan tokoh dalam cerita ini.')
    assert api.auto_viral_format_perspective(manual, long_form=False) == manual.creator_perspective
    scheduled = manual.model_copy(update={'cron_theme_key': 'gaming_story', 'cron_short_role': 'satu keputusan dan konsekuensinya'})
    assert RYUUNDY_REFERENCE_EDITOR_BRIEF in api.auto_viral_format_perspective(scheduled, long_form=False)
    news = scheduled.model_copy(update={'cron_theme_key': api.NEWS_HOT_THEME})
    assert RYUUNDY_REFERENCE_EDITOR_BRIEF not in api.auto_viral_format_perspective(news, long_form=False)


def candidate(score=85, **overrides):
    import clipper

    return clipper.ClipCandidate(**(dict(
        index=1, start=0, end=32, duration=32, score=score,
        title='Subtitle panjang tetap terbaca', text=PRACTICAL,
        reason='test fixture', key_point_score=85, retention_score=80,
        narrative_arc_score=85, narrative_arc_complete=True,
        boundary_quality='kalimat_tuntas', religious_context_safe=True,
    ) | overrides))


@pytest.mark.parametrize('overrides', [
    {'score': 79}, {'retention_score': 40},
    {'religious_context_safe': False}, {'narrative_arc_complete': False},
    {'boundary_quality': 'menggantung'},
])
def test_practical_pattern_cannot_bypass_existing_export_requirements(overrides):
    import clipper

    clip = candidate(**overrides)
    assert practical_payoff_profile(clip.text, clip.duration)['qualified']
    assert clipper.select_candidates([clip], 1, minimum_score=80) == []


def test_growth_plan_records_practical_series_without_relabelling_faith(monkeypatch):
    import clipper

    clip = candidate()
    monkeypatch.setattr(clipper, 'detect_visual_theme', lambda _: 'knowledge')
    plan = clipper.codex_growth_blueprint(clip, 'vertical_short')
    assert plan['series']['name'] == 'Satu Masalah, Satu Langkah'
    assert plan['retention']['practical_payoff_strategy']['qualified']
    assert not plan['view_or_subscriber_guarantee']
    monkeypatch.setattr(clipper, 'detect_visual_theme', lambda _: 'islamic')
    faith = clipper.codex_growth_blueprint(clip, 'vertical_short')
    assert faith['series']['name'] == 'Hikmah Praktis'


def test_ai_receives_source_evidence_and_scheduler_identity(monkeypatch):
    import clipper
    from llm import AIConfig

    captured = []
    monkeypatch.setenv('SHORTS_SCHEDULED_HUMAN_EDITOR_ENABLED', 'true')
    def capture(_config, messages):
        captured.extend(messages)
        return '{"clips": []}'
    monkeypatch.setattr(clipper, 'chat_completion', capture)
    clipper.ai_rescore_candidates([candidate()], AIConfig(
        enabled=True, base_url='http://invalid.test', model='test',
    ), target_count=1)
    data = json.loads(captured[-1]['content'].split('Candidates:\n', 1)[1])
    assert data[0]['practical_payoff']['qualified']
    assert data[0]['practical_payoff']['evidence']['action'] in PRACTICAL
    assert RYUUNDY_REFERENCE_EDITOR_BRIEF in captured[0]['content']
    monkeypatch.delenv('SHORTS_SCHEDULED_HUMAN_EDITOR_ENABLED')
    assert clipper.candidate_editor_system_prompt() == clipper.AI_SYSTEM_PROMPT
