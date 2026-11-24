"""Moral/education story lane for school children and everyday family life."""
import pytest

import facebook_stories as stories


MORAL = [row for row in stories.DEFAULT_TOPICS if row['style'] == 'moral_anak']


def test_moral_style_is_a_registered_first_class_style():
    assert 'moral_anak' in stories.STYLES
    spec = stories.STYLES['moral_anak']
    assert spec['layout'] in {'compare', 'steps'}
    assert spec['label'] and spec['concept'] and len(spec['panels']) in (2, 3)
    assert '#CeritaMoral' in spec['hashtags'] and '#AnakSekolah' in spec['hashtags']


def test_moral_topics_cover_school_and_daily_life_without_new_permissions():
    assert len(MORAL) >= 10
    joined = ' '.join(row['text'] for row in MORAL)
    for word in ('sekolah', 'kantin', 'guru', 'teman', 'rumah', 'PR', 'maaf', 'terima kasih'):
        assert word in joined
    assert all(row['text'] == stories.normalize_topic(row['text']) for row in MORAL)
    assert all(stories.resolve_style(row['text'], row['style']) == 'moral_anak' for row in MORAL)


@pytest.mark.parametrize('topic', [row['text'] for row in MORAL])
def test_each_moral_topic_plans_and_verifies(topic):
    plan = stories.plan('moral-seed:' + topic[:12], 'reel', topic, style='moral_anak')
    assert plan['story']['style'] == 'moral_anak'
    assert plan['story']['topic_text'] == topic
    assert len(plan['stages']) == 4
    assert all(stage['text'] for stage in plan['stages'])
    assert 'Anak' in plan['caption'] or '#CeritaMoral' in plan['caption']
    stories.verify_plan(plan)
    authored = stories.author(plan)
    stories.verify_plan(authored)
    assert authored['script_sha256'] and authored['authoring'] == 'template_storyboard'
    assert authored['third_party_footage'] is False and authored['third_party_music'] is False


def test_moral_prompt_guides_a_child_safe_single_lesson(monkeypatch):
    prompts = []
    monkeypatch.setattr(stories, 'chat_completion', lambda *args, **kwargs: prompts.append(args) or '{}')
    monkeypatch.setattr(stories, 'extract_json', lambda _: {})
    plan = stories.plan('seed', 'reel', MORAL[0]['text'], style='moral_anak')
    authored = stories.author(plan, config=dict(base_url='http://local', model='test'))
    assert authored['authoring'] == 'template_storyboard'
    system = prompts[0][1][0]['content']
    assert 'anak sekolah' in system
    assert 'menakut-nakuti' in system and 'menghakimi' in system
    user = prompts[0][1][1]['content']
    assert 'Anak sekolah dan keluarga' in user
