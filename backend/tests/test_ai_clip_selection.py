import json

import clipper
from llm import AIConfig, LLMUnavailableError
from clipper import (
    ClipCandidate,
    ai_rescore_candidates,
    select_candidates,
    select_compilation_candidates,
    select_output_candidates,
)


def make_candidate(index: int, start: float, score: int, text: str) -> ClipCandidate:
    return ClipCandidate(
        index=index,
        start=start,
        end=start + 60,
        duration=60,
        score=score,
        title=f"Candidate {index}",
        reason="heuristic",
        text=text,
    )


def test_ai_ranked_candidate_beats_higher_heuristic_score(monkeypatch):
    generic = make_candidate(0, 0, 95, "Pembukaan biasa dan konteks umum.")
    fyp_point = make_candidate(
        0,
        90,
        62,
        "Ternyata cara ini salah. Masalahnya bukan di tools, tapi di keputusan pertama.",
    )

    def fake_chat_completion(config, messages):
        return json.dumps(
            {
                "clips": [
                    {
                        "id": 1,
                        "score": 92,
                        "title": "Kesalahan Pertama",
                        "reason": "Ada tension dan payoff yang jelas.",
                        "pov": "Penonton merasa sedang diingatkan sebelum rugi.",
                    }
                ]
            }
        )

    monkeypatch.setattr(clipper, "chat_completion", fake_chat_completion)

    rescored = ai_rescore_candidates(
        [generic, fyp_point],
        AIConfig(enabled=True, base_url="http://localhost:20128/v1", model="local-model"),
        target_count=1,
    )
    selected = select_candidates(rescored, 1)

    assert selected[0].title == "Kesalahan Pertama"
    assert selected[0].score == 84
    assert selected[0].fyp_label == "Kuat"
    assert selected[0].pov == "Penonton merasa sedang diingatkan sebelum rugi."
    assert selected[0].reason.startswith("AI FYP:")
    assert generic.score < selected[0].score


def test_ai_rescore_keeps_heuristics_when_endpoint_is_missing():
    candidate = make_candidate(0, 0, 77, "Intinya ini contoh kandidat.")

    rescored = ai_rescore_candidates(
        [candidate],
        AIConfig(enabled=True, base_url="", model=""),
        target_count=1,
    )

    assert rescored == [candidate]
    assert candidate.score == 77


def test_ai_rescore_disables_offline_provider_for_rest_of_job(monkeypatch, capsys):
    candidate = make_candidate(0, 0, 77, "Intinya ini contoh kandidat.")
    config = AIConfig(
        enabled=True,
        base_url="http://127.0.0.1:11434/v1",
        model="missing-model",
    )
    monkeypatch.setattr(clipper, "_AI_UNAVAILABLE_NOTICE_PRINTED", False)
    monkeypatch.setattr(
        clipper,
        "chat_completion",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            LLMUnavailableError("offline")
        ),
    )

    rescored = ai_rescore_candidates([candidate], config, target_count=1)

    assert rescored == [candidate]
    assert config.enabled is False
    output = capsys.readouterr().out
    assert "fallback lokal" in output
    assert "AI agent failed" not in output


def test_compilation_selection_reaches_five_minutes_without_overlap():
    candidates = [
        make_candidate(0, start, 95 - index, f"Poin penting {index}")
        for index, start in enumerate((0, 70, 140, 210, 280, 350))
    ]

    selected = select_compilation_candidates(candidates, target_duration=300)

    assert sum(item.duration for item in selected) == 300
    assert len(selected) == 5
    assert selected == sorted(selected, key=lambda item: item.start)
    assert all(
        left.end <= right.start
        for left, right in zip(selected, selected[1:])
    )


def test_short_mode_does_not_build_a_compilation_selection():
    candidates = [
        make_candidate(0, start, 95 - index, f"Poin penting {index}")
        for index, start in enumerate((0, 70, 140, 210, 280, 350))
    ]

    shorts, compilation = select_output_candidates(
        candidates,
        clip_mode="short",
        short_limit=3,
        compilation_target=300,
    )

    assert len(shorts) == 3
    assert compilation == []


def test_highlight_mode_builds_only_the_compilation_selection():
    candidates = [
        make_candidate(0, start, 95 - index, f"Poin penting {index}")
        for index, start in enumerate((0, 70, 140, 210, 280, 350))
    ]

    selected, compilation = select_output_candidates(
        candidates,
        clip_mode="highlight_5m",
        short_limit=3,
        compilation_target=300,
    )

    assert selected is compilation
    assert sum(item.duration for item in compilation) == 300
