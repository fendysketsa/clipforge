import json

import pytest

import article_presenter as presenter
from hypit_quick import _dialogue_cues, _quick_manifest, _quick_reveal_times, build_hypit_quick_plan, is_hypit_quick_prompt, quick_preview_payload
from llm import AIConfig

ARTICLE = (
    "Daun memiliki pori-pori kecil bernama stomata. Stomata membantu pertukaran gas pada tumbuhan. "
    "Saat fotosintesis daun menyerap karbon dioksida dan menghasilkan oksigen. "
    "Respirasi tumbuhan berlangsung pada siang dan malam hari."
)


def test_article_route_needs_only_article_and_builds_complete_presentation(tmp_path):
    prompt = '/hypit presenter\n' + ARTICLE
    assert is_hypit_quick_prompt(prompt)
    plan = build_hypit_quick_plan(prompt)
    assert plan.presentation_mode
    assert plan.source_article == ARTICLE
    assert 3 <= len(plan.beats) <= 12
    assert 0 < plan.duration <= 300
    assert all(beat.source_quote in ARTICLE for beat in plan.beats)
    assert all(len(beat.presentation_scene['objects']) >= 2 for beat in plan.beats)
    assert all(cue.speaker == 'HOST' for cue in _dialogue_cues(plan, _quick_reveal_times(plan)))
    manifest = _quick_manifest(plan, tmp_path, tmp_path / 'script.svml', [], _quick_reveal_times(plan))
    assert manifest['composition']['presentationMode']
    assert manifest['composition']['midCta']['enabled'] is False
    assert manifest['composition']['beats'][0]['presentationScene']['relations']
    assert quick_preview_payload(prompt)['expansion']['format'] == 'article_presenter_v1'


def test_article_preflight_does_not_spend_llm_request(monkeypatch):
    monkeypatch.setattr(presenter, 'chat_completion', lambda *_args, **_kwargs: pytest.fail('preflight must not call LLM'))
    preview = quick_preview_payload('/hypit presenter\n' + ARTICLE)
    assert preview['image_provider']['ready']


def test_model_object_graph_and_safe_custom_artwork_reach_renderer(monkeypatch, tmp_path):
    svg = '<svg viewBox="0 0 160 160"><path d="M20 20 L140 20 L80 140 Z" fill="#55CCAA"/></svg>'
    article = 'Robot memiliki sensor untuk mendeteksi benda. Sensor mengirimkan data kepada robot. Robot menggunakan data untuk mengatur gerakan.'
    sentences = article.split('. ')[:3]
    payload = {'title': 'Cara Robot Bekerja', 'hook': sentences[0], 'payoff': sentences[2], 'beats': [
        {'title': 'Robot dan sensor', 'narration': sentence, 'source_quote': sentence,
         'scene': {'layout': 'cause_effect', 'objects': [
             {'id': 'robot', 'kind': 'gear', 'label': 'Robot', 'action': 'rotate'},
             {'id': 'detail', 'kind': 'custom', 'label': 'Sensor', 'svg': svg},
         ], 'relations': [{'from': 'robot', 'to': 'detail', 'label': 'memiliki', 'kind': 'flow'}], 'focus': 'detail'}}
        for sentence in sentences
    ]}
    monkeypatch.setattr(presenter, 'chat_completion', lambda *_args, **_kwargs: json.dumps(payload))
    config = AIConfig(enabled=True, base_url='http://model.test/v1', model='model')
    plan = build_hypit_quick_plan('/hypit presenter\n' + article, config)
    assert plan.planning_mode == 'ai_grounded'
    scene = plan.beats[0].presentation_scene
    assert scene['focus'] == 'detail'
    assert scene['objects'][1]['svg'].startswith('<svg')
    assert scene['relations'][0]['from'] == 'robot'
    manifest = _quick_manifest(plan, tmp_path, tmp_path / 'script.svml', [], _quick_reveal_times(plan))
    assert manifest['composition']['beats'][0]['presentationScene']['objects'][1]['svg'] == scene['objects'][1]['svg']


@pytest.mark.parametrize('svg', [
    '<svg><script>alert(1)</script></svg>',
    '<svg><image href="https://example.com/image.png"/></svg>',
    '<svg onload="alert(1)"><path d="M0 0"/></svg>',
    '<svg><foreignObject/></svg>',
    '<!DOCTYPE svg [<!ENTITY x "unsafe">]><svg/>',
    '<svg><text>Fakta palsu</text></svg>',
    '<svg><path fill="url(https://example.com)"/></svg>',
])
def test_model_svg_cannot_execute_or_fetch_or_embed_claims(svg):
    assert presenter.sanitize_object_svg(svg) == ''


def test_broken_graph_is_repaired_without_dangling_relations():
    scene = presenter.validate_presenter_scene({
        'objects': [{'id': 'a', 'kind': 'leaf', 'action': []}, {'id': 'b', 'kind': 'gas'}],
        'layout': [], 'focus': [],
        'relations': [{'from': 'missing', 'to': 'b'}, {'from': [], 'to': 'a'}],
    }, visual='plant_life', sentence=ARTICLE, source=ARTICLE)
    ids = {obj['id'] for obj in scene['objects']}
    assert scene['relations']
    assert all(edge['from'] in ids and edge['to'] in ids for edge in scene['relations'])


def test_model_failure_falls_back_without_losing_article_conclusion(monkeypatch):
    def fail(*_args, **_kwargs):
        raise ConnectionError('offline')
    monkeypatch.setattr(presenter, 'chat_completion', fail)
    article = ' '.join(f'Bagian {i} menjelaskan proses secara lengkap.' for i in range(12))
    payload = presenter.plan_article_presentation(article, AIConfig(enabled=True, base_url='http://model.test', model='model'))
    assert payload['_planning_mode'] == 'local_fallback'
    assert '11' in payload['beats'][-1]['source_quote']
    assert all(beat['source_quote'] in article for beat in payload['beats'])


def test_small_model_partial_outline_still_directs_each_complete_sentence(monkeypatch):
    calls = []
    def completion(_config, messages, **_kwargs):
        calls.append(messages[-1]['content'])
        if messages[-1]['content'].startswith('ARTIKEL:'):
            return json.dumps({'beats': [{'narration': 'partial'}]})
        return json.dumps({'scene': {
            'layout': 'process', 'objects': [
                {'id': 'leaf', 'kind': 'leaf', 'label': 'Daun'},
                {'id': 'gas', 'kind': 'gas', 'label': 'Gas'},
            ], 'relations': [{'from': 'gas', 'to': 'leaf', 'kind': 'exchange'}], 'focus': 'leaf',
        }})
    monkeypatch.setattr(presenter, 'chat_completion', completion)
    wrapped = 'Tumbuhan dan Daun\n' + ARTICLE.replace(' dan ', '\ndan ')
    payload = presenter.plan_article_presentation(wrapped, AIConfig(enabled=True, base_url='http://model.test', model='small'))
    assert payload['_planning_mode'] == 'ai_visual_director'
    assert len(calls) == 1 + len(payload['beats'])
    assert any(beat['presentation_scene']['authorship'] in {'model_scene', 'model_directed'} for beat in payload['beats'])
    assert all(beat['presentation_scene']['relations'] for beat in payload['beats'])
    assert not any(beat['narration'].startswith('dan ') for beat in payload['beats'])


def test_presenter_repairs_reversed_oxygen_flow_and_wrong_plant_symbol():
    scene = presenter.validate_presenter_scene({
        'objects': [{'id': 'plant', 'kind': 'person', 'label': 'Tumbuhan'}, {'id': 'oxygen', 'kind': 'gas', 'label': 'Oksigen'}],
        'relations': [{'from': 'plant', 'to': 'oxygen', 'label': 'Menghasilkan oksigen'}],
    }, visual='plant_respiration', sentence='Tumbuhan membutuhkan oksigen untuk menghasilkan energi.', source=ARTICLE)
    nodes = {node['id']: node for node in scene['objects']}
    assert any(node['kind'] == 'tree' for node in scene['objects'])
    first = scene['relations'][0]
    assert nodes[first['from']]['label'] == 'Oksigen'
    assert nodes[first['to']]['label'] == 'Tumbuhan'
    assert first['label'] == 'digunakan'
    assert not any('Menghasilkan oksigen' in edge['label'] for edge in scene['relations'])


def test_presenter_api_preview_accepts_article_and_passes_selected_model(monkeypatch):
    import api
    captured = []
    original = api.quick_preview_payload
    def preview(prompt, config=None):
        captured.append(config)
        return original(prompt)
    monkeypatch.setattr(api, 'quick_preview_payload', preview)
    result = api.create_storyboard_preview(api.StoryboardPreviewRequest(
        story_text='/hypit presenter\n' + ARTICLE,
        ai_enabled=True, ai_base_url='http://model.test/v1', ai_model='my-model',
    ))
    assert result.image_provider.ready
    assert captured[0].model == 'my-model'


def test_short_article_produces_actionable_validation():
    with pytest.raises(ValueError, match='dua belas'):
        build_hypit_quick_plan('/hypit presenter\nDaun dan tumbuhan')
