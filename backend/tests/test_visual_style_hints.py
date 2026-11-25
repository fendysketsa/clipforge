"""Prompt-only art direction: no renderer, rights or QC claims."""
import pytest

import visual_style_hints as styles


def test_catalog_is_bounded_and_prompt_only():
    result = styles.catalog()
    assert result['version'] == styles.VERSION
    assert result['scope'] == 'prompt_hint_only'
    assert result['renderer_neutral'] is True and result['rights_reference'] is False
    assert 8 <= len(result['profiles']) <= 12
    assert set(result['profiles']) == set(styles.PROFILES)
    for row in result['profiles'].values():
        assert 2 <= len(row['palette']) <= styles.PALETTE_LIMIT
        assert row['prompt'] and row['motion_hint'] and row['label']


def test_style_choice_is_deterministic_and_preference_is_checked():
    first = styles.style_for('podcast deny sumargo')
    assert first == styles.style_for('podcast deny sumargo')
    assert first in styles.PROFILES
    assert styles.style_for('podcast deny sumargo', 'paper_cutout') == 'paper_cutout'
    with pytest.raises(ValueError):
        styles.style_for('x', 'unknown_style')


def test_hint_is_short_and_never_claims_rights_or_publication():
    hint = styles.prompt_hint('Cerita moral anak sekolah')
    assert hint['style'] in styles.PROFILES
    assert len(hint['text']) <= styles.TEXT_LIMIT + 1
    assert 'Art direction:' in hint['text']
    assert hint['palette'] == styles.PROFILES[hint['style']]['palette']
    lowered = hint['text'].casefold()
    for forbidden in ('ghibli', 'pixar', 'disney', 'rick', 'morty', 'klimt', 'warhol',
                      'hak cipta', 'qc lulus', 'terupload', 'published', 'approved'):
        assert forbidden not in lowered


def test_enrich_prompt_keeps_the_original_instruction():
    base = 'Satu pesan moral, tokoh orisinal, bahasa ramah anak.'
    result = styles.enrich_prompt(base, 'memasak bersama', preferred='soft_flat', max_length=120)
    assert result['prompt'].startswith(base)
    assert result['prompt'].endswith(result['text'])
    assert len(result['text']) <= 121
    with pytest.raises(ValueError):
        styles.enrich_prompt('', 'x')


@pytest.mark.parametrize('change', [
    {'label': ''}, {'prompt': 12}, {'motion_hint': ''},
    {'palette': ['#fff']}, {'palette': ['red', '#123456']}, {'palette': ['#123456'] * 7},
])
def test_invalid_profile_is_rejected(change):
    row = dict(label='Contoh', prompt='Bentuk geometris sederhana dan warna primer.',
               motion_hint='Satu gerakan per beat.', palette=['#112233', '#445566'])
    row.update(change)
    with pytest.raises(ValueError):
        styles.validate_profile(row)
