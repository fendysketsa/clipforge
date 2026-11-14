"""Cron Long needs independent demand and a grounded, complete story arc."""
from copy import deepcopy

import pytest

import cron_long_strategy as strategy


@pytest.mark.parametrize("source", [
    {}, {"duration": 45, "views": 9_000_000}, {"duration": 1000, "views": 999},
    {"duration": float("nan"), "views": 1000}, {"duration": 1000, "views": True},
    {"duration": 1000, "views": "5000"}, {"duration": 1000, "views": 1000, "is_live": True},
])
def test_popularity_and_unknown_metadata_cannot_admit_a_short_or_unfinished_source(source):
    assert not strategy.source_profile(source)["eligible"]


def test_verified_long_demand_is_not_a_retention_prediction():
    profile = strategy.source_profile({"duration": 1200, "view_count": 5000})
    assert profile["eligible"]
    assert not profile["actual_retention_verified"]
    assert not profile["future_views_guaranteed"]


@pytest.fixture
def story():
    texts = ["Mengapa kucing ini selalu bersembunyi di dapur?",
             "Kami datang merawat kucing selama tujuh hari.",
             "Kami menemukan suara berasal dari pintu belakang.",
             "Setelah pintu diperbaiki kucing kembali makan dengan tenang."]
    material = [dict(part=i + 1, start=i * 60, end=(i + 1) * 60, text=text)
                for i, text in enumerate(texts)]
    review = dict(viewer_need="Memahami penyebab kucing tidak mau makan",
                  title_promise="Mencari penyebab kucing selalu bersembunyi di dapur",
                  reason="Pertanyaan dijawab melalui pemeriksaan dan tindakan tokoh",
                  checks={k: True for k in ("coherent_topic", "progression", "resolved_ending",
                      "adds_value_beyond_short", "no_filler", "promise_matches_content")},
                  beats=[dict(role=role, part=i + 1, quote=text,
                              why_continue="Tahap ini memberi informasi baru kepada penonton")
                         for i, (role, text) in enumerate(zip(
                             ("promise", "context", "development", "payoff"), texts))])
    return review, material


def test_complete_grounded_long_with_mostly_new_material_passes(story):
    review, material = story
    result = strategy.validate_review(review, material, [(0, 40), (10, 30)])
    assert result["passed"]
    assert result["new_material_fraction"] == pytest.approx(0.8333)


@pytest.mark.parametrize("change", ["invented_quote", "invented_part", "payoff_in_middle",
    "missing_context", "false_check", "unknown_check", "short_material", "mostly_short", "bad_json"])
def test_unknown_or_weak_story_cannot_render(story, change):
    review, material = deepcopy(story)
    anchors = []
    if change == "invented_quote": review["beats"][-1]["quote"] = "Kucing sebenarnya adalah alien dari planet Mars"
    if change == "invented_part": review["beats"][-1]["part"] = 99
    if change == "payoff_in_middle": review["beats"][-1]["part"] = 2
    if change == "missing_context": review["beats"].pop(1)
    if change == "false_check": review["checks"]["resolved_ending"] = False
    if change == "unknown_check": review["checks"]["progression"] = "true"
    if change == "short_material": material = material[:2]
    if change == "mostly_short": anchors = [(0, 200)]
    if change == "bad_json": review = [review]
    assert not strategy.validate_review(review, material, anchors)["passed"]


def test_long_direction_never_inherits_short_fyp_brief():
    import api
    request = api.AutoViralRequest(cron_theme_key="gaming_story")
    long = api.auto_viral_format_perspective(request, long_form=True)
    short = api.auto_viral_format_perspective(request, long_form=False)
    assert strategy.LONG_EDITOR_BRIEF in long
    assert "dua detik pertama" not in long
    assert "dua detik pertama" in short
    manual = api.AutoViralRequest(creator_perspective="Arahan saya sendiri")
    assert api.auto_viral_format_perspective(manual, long_form=True) == manual.creator_perspective


def test_long_gate_reaches_worker_only_for_long():
    import api
    request = api.ClipJobRequest(url="https://www.youtube.com/watch?v=abcdefghijk",
                                 clip_mode="highlight_5m", cron_long_strategy=True)
    assert "--cron-long-strategy" in api.build_clipper_command(request)
    request.clip_mode = "short"
    assert "--cron-long-strategy" not in api.build_clipper_command(request)


def test_long_ranking_uses_its_own_system_and_editorial_instructions(monkeypatch):
    import clipper
    from llm import AIConfig
    seen = []
    def completion(config, messages):
        seen.append(messages)
        return '{"clips":[]}'
    monkeypatch.setattr(clipper, 'chat_completion', completion)
    c = clipper.ClipCandidate(index=1, start=0, end=60, duration=60, score=85,
        title='Tujuan merawat kucing', reason='Cerita', text='Kami datang merawat kucing selama tujuh hari.')
    clipper.ai_rescore_candidates([c], AIConfig(True, 'http://local.test/v1', 'test'),
                                 compilation=True, long_strategy=True)
    assert strategy.LONG_EDITOR_BRIEF in seen[0][0]['content']
    assert '0–2 seconds' not in seen[0][0]['content']
    assert 'kontribusi bagian pada cerita Long' in seen[0][1]['content']


def test_long_json_repair_preserves_long_brief_and_chapter_budget(monkeypatch):
    import clipper
    from llm import AIConfig
    seen = []
    def completion(config, messages):
        seen.append(messages)
        return '{"clips":[' if len(seen) == 1 else '{"clips":[]}'
    monkeypatch.setattr(clipper, 'chat_completion', completion)
    c = clipper.ClipCandidate(index=1, start=0, end=60, duration=60, score=85,
        title='Merawat kucing', reason='Cerita', text='Kami merawat kucing selama tujuh hari.')
    clipper.ai_rescore_candidates([c], AIConfig(True, 'http://local.test/v1', 'test'),
                                 target_count=5, compilation=True, long_strategy=True)
    assert len(seen) == 2
    assert strategy.LONG_EDITOR_BRIEF in seen[1][0]['content']
    assert 'maksimal 5 clips' in seen[1][1]['content']


@pytest.mark.parametrize("provider", ["disabled", "unavailable", "malformed", "ungrounded"])
def test_missing_editorial_evidence_stops_before_media_render(tmp_path, monkeypatch, provider):
    import clipper
    from llm import AIConfig
    candidates = [clipper.ClipCandidate(index=i+1, start=i*60, end=(i+1)*60, duration=60,
                    score=85, title="Kucing dan pintu", reason="Cerita", text="Bahan sumber untuk cerita ini")
                  for i in range(4)]
    monkeypatch.setattr(clipper, "build_long_form_story_sequence", lambda *a: (candidates, [], {}))
    def forbidden(*a, **kw):
        pytest.fail("Media rendering must never start before a grounded editorial pass")
    monkeypatch.setattr(clipper, "export_clip", forbidden)
    def completion(*a, **kw):
        if provider == "unavailable": raise ConnectionError("test")
        return "not json" if provider == "malformed" else '{"checks":{}}'
    monkeypatch.setattr(clipper, "chat_completion", completion)
    with pytest.raises(RuntimeError, match="render ditahan"):
        clipper.export_compilation(tmp_path / "source.mp4", candidates, [], tmp_path / "clips",
            True, "blur", clipper.CaptionStyle(), AIConfig(enabled=provider != "disabled"),
            "top_right", [], "1080p", cron_long_strategy_required=True)
    assert (tmp_path / "cron_long_story_review.json").exists()
