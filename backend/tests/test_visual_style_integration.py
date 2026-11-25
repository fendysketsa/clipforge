"""Art-direction hints stay in prompt text and never touch renderer evidence."""
import json

import api
import cron_long_strategy
import facebook_stories
import ryuundy_reference_catalog
import visual_style_hints


def test_editorial_brief_carries_a_compact_prompt_hint():
    brief = ryuundy_reference_catalog.editorial_brief('moral_animation_story')
    assert brief.startswith('Referensi pemilik channel')
    assert 'Art direction:' in brief
    assert '\n' not in brief
    assert len(brief) < 1600


def test_long_brief_adds_general_technique_without_short_fyp_language():
    brief = cron_long_strategy.LONG_EDITOR_BRIEF
    assert cron_long_strategy.VISUAL_DIRECTION_BRIEF in brief
    assert 'dua detik pertama' not in brief
    assert 'franchise' in brief and 'QC' in brief


def test_facebook_author_hint_is_prompt_only_and_bounded():
    plan = {'story': {'topic_text': 'memasak bersama anak'}}
    hint = facebook_stories._art_direction_hint(plan)
    assert hint.startswith('Art direction:')
    assert len(hint) <= visual_style_hints.TEXT_LIMIT + 2
    assert all(name not in hint.casefold() for name in ('ghibli', 'pixar', 'disney', 'klimt'))


def test_visual_style_endpoint_exposes_catalog_without_secrets():
    payload = api.runtime_visual_style()
    assert payload['renderer_neutral'] is True
    assert payload['rights_reference'] is False
    assert set(payload['profiles']) == set(visual_style_hints.PROFILES)
    assert 'DEEPSEEK_API_KEY' not in json.dumps(payload)
