import json

import clipper
from llm import AIConfig, LLMUnavailableError
from clipper import (
    ClipCandidate,
    TranscriptSegment,
    ai_rescore_candidates,
    build_long_form_story_sequence,
    editorial_safety_profile,
    order_compilation_for_retention,
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
        key_point_score=score,
        boundary_quality="kalimat_tuntas",
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


def test_ai_brief_requires_distinct_angles_and_specific_titles():
    assert "every clip must answer a different viewer question" in clipper.AI_SYSTEM_PROMPT
    assert "concrete subject or object" in clipper.AI_SYSTEM_PROMPT
    assert "uppercase emphasis phrase" in clipper.AI_SYSTEM_PROMPT
    assert "constructive lesson" in clipper.AI_SYSTEM_PROMPT


def test_editorial_safety_rejects_mockery_and_keeps_constructive_victim_context():
    mockery = editorial_safety_profile(
        "Dia itu goblok dan pantas dipermalukan. Rasain, biar kapok."
    )
    constructive = editorial_safety_profile(
        "Saya dihina waktu itu. Pelajarannya, kita jangan menghakimi dan harus saling menghormati."
    )

    assert mockery["safe_for_selection"] is False
    assert mockery["direct_ridicule_or_insult"] is True
    assert mockery["celebrates_harm"] is True
    assert constructive["safe_for_selection"] is True
    assert constructive["constructive_takeaway"] is True


def test_short_selection_blocks_negative_story_without_constructive_takeaway():
    unsafe = make_candidate(
        0,
        0,
        95,
        "Saya dihina dan diejek di depan orang banyak. Cerita selesai begitu saja.",
    )
    safe = make_candidate(
        0,
        90,
        85,
        "Saya dihina, tetapi pelajarannya kita jangan menghakimi dan saling menghormati.",
    )

    assert select_candidates([unsafe, safe], 2) == [safe]


def test_compilation_selection_uses_the_same_editorial_safety_gate():
    unsafe = make_candidate(
        0,
        0,
        95,
        "Mereka bodoh dan pantas dipermalukan supaya kapok.",
    )
    safe = make_candidate(
        0,
        90,
        85,
        "Pelajarannya, kita sebaiknya saling menghormati dan tidak menghakimi.",
    )

    assert select_compilation_candidates([unsafe, safe], target_duration=120) == [safe]


def test_ai_rescore_pool_covers_timeline_and_sends_story_metrics(monkeypatch):
    candidates = [
        make_candidate(index, index * 60, 100 - index, f"Poin penting bagian {index}.")
        for index in range(50)
    ]
    captured_items = []

    def fake_chat_completion(config, messages):
        nonlocal captured_items
        captured_items = json.loads(messages[-1]["content"].split("Candidates:\n", 1)[1])
        return '{"clips": []}'

    monkeypatch.setattr(clipper, "chat_completion", fake_chat_completion)

    ai_rescore_candidates(
        candidates,
        AIConfig(enabled=True, base_url="http://localhost:20128/v1", model="local-model"),
        target_count=1,
    )

    assert len(captured_items) == 40
    assert max(item["start"] for item in captured_items) >= 2700
    assert all(
        {"hook", "key_point_score", "loop_score", "boundary_quality"} <= item.keys()
        for item in captured_items
    )


def test_short_selection_deduplicates_the_same_main_point():
    first = make_candidate(
        0,
        0,
        95,
        "Masalah terbesar ada pada keputusan pertama dan solusinya memeriksa risiko.",
    )
    duplicate = make_candidate(
        0,
        90,
        94,
        "Masalah terbesar ada pada keputusan pertama, solusinya adalah memeriksa risiko.",
    )
    different = make_candidate(
        0,
        180,
        90,
        "Ternyata angka pertumbuhan menunjukkan peluang pasar yang baru.",
    )

    selected = select_candidates([first, duplicate, different], 2)

    assert different in selected
    assert sum(item is first or item is duplicate for item in selected) == 1


def test_short_selection_returns_fewer_outputs_instead_of_repeating_one_point():
    first = make_candidate(
        0,
        0,
        95,
        "Kesalahan pertama membuat biaya membesar karena risiko tidak diperiksa sejak awal.",
    )
    repeated = make_candidate(
        0,
        90,
        94,
        "Biaya membesar akibat kesalahan pertama saat risiko tidak diperiksa sejak awal.",
    )

    selected = select_candidates([first, repeated], 2)

    assert selected == [first]


def test_short_selection_treats_fyp_score_as_ranking_not_safety_gate():
    weak_point = make_candidate(0, 0, 99, "Hook kuat tetapi isi utamanya belum cukup jelas.")
    weak_point.key_point_score = 54
    hanging = make_candidate(0, 90, 98, "Poin kuat tetapi kalimatnya masih menggantung.")
    hanging.boundary_quality = "menggantung"
    low_fyp = make_candidate(0, 150, 77, "Poin lengkap tetapi daya tariknya masih lemah.")
    ready = make_candidate(0, 240, 80, "Poin utama dan penutupnya sudah lengkap.")

    selected = select_candidates([weak_point, hanging, low_fyp, ready], 4)

    assert selected == [low_fyp, ready]


def test_short_selection_rejects_timing_audited_candidate_with_drop_off_risk():
    keyword_bait = make_candidate(
        0,
        0,
        96,
        "Ternyata rahasia penting ini punya jawaban yang mengejutkan.",
    )
    keyword_bait.retention_score = 57
    paced_story = make_candidate(
        0,
        90,
        82,
        "Masalah, bukti, dan jawabannya tersusun tanpa jeda panjang.",
    )
    paced_story.retention_score = 74

    selected = select_candidates([keyword_bait, paced_story], 2)

    assert selected == [paced_story]


def test_short_selection_can_include_low_score_when_structural_gates_pass():
    candidate = make_candidate(0, 0, 58, "Poin lengkap yang masih perlu auto-repair.")

    assert select_candidates([candidate], 1) == [candidate]
    assert select_candidates([candidate], 1, minimum_score=1) == [candidate]


def test_final_short_quality_gate_discards_result_below_fyp_80():
    below_target = make_candidate(0, 0, 77, "Poin lengkap tetapi belum cukup kuat.")
    ready = make_candidate(1, 90, 80, "Hook, isi, dan payoff sudah kuat.")

    assert select_candidates(
        [below_target, ready],
        2,
        minimum_score=clipper.SHORT_EXPORT_MIN_FYP_SCORE,
    ) == [ready]


def test_ai_rescore_accepts_common_alternate_candidate_key(monkeypatch):
    candidate = make_candidate(0, 0, 70, "Masalah dan jawabannya dijelaskan sampai tuntas.")
    config = AIConfig(
        enabled=True,
        base_url="http://127.0.0.1:11434/v1",
        model="llama-local",
    )
    monkeypatch.setattr(
        clipper,
        "chat_completion",
        lambda *args, **kwargs: '{"selected_clips":[{"id":0,"score":84,"title":"Jawaban yang Sering Terlewat"}]}',
    )

    rescored = ai_rescore_candidates([candidate], config, target_count=1)

    assert rescored[0].score > 70
    assert rescored[0].title == "Jawaban yang Sering Terlewat"


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


def test_compilation_selection_supports_ten_minute_story_resume():
    candidates = [
        make_candidate(0, start, 95 - (index % 8), f"Bab cerita {index}")
        for index, start in enumerate(range(0, 1200, 70))
    ]

    selected = select_compilation_candidates(candidates, target_duration=600)

    assert sum(item.duration for item in selected) == 600
    assert len(selected) == 10
    assert selected == sorted(selected, key=lambda item: item.start)


def test_compilation_selection_covers_late_story_payoff():
    candidates = [
        make_candidate(0, start, 99 - index, f"Perkembangan awal {index}")
        for index, start in enumerate(range(0, 700, 70))
    ]
    candidates.extend(
        [
            make_candidate(0, 1400, 74, "Konflik berkembang menuju jawaban."),
            make_candidate(0, 1960, 72, "Kesimpulan dan payoff utama cerita."),
        ]
    )

    selected = select_compilation_candidates(candidates, target_duration=600)

    assert any(item.start >= 1900 for item in selected)


def test_compilation_export_order_moves_strongest_segment_to_opening():
    candidates = [
        make_candidate(1, 0, 72, "Konteks awal"),
        make_candidate(2, 120, 96, "Jawaban yang paling kuat"),
        make_candidate(3, 240, 80, "Kesimpulan"),
    ]

    ordered = order_compilation_for_retention(candidates)

    assert ordered[0] is candidates[1]
    assert [item.start for item in ordered[1:]] == [0, 240]
    assert [item.start for item in candidates] == [0, 120, 240]


def test_long_story_director_uses_short_teaser_then_restores_chronology():
    candidates = [
        make_candidate(1, 0, 78, "Konteks awal masalah"),
        make_candidate(2, 120, 96, "Jawaban paling kuat"),
        make_candidate(3, 240, 84, "Penjelasan dan contoh"),
        make_candidate(4, 360, 88, "Kesimpulan dan payoff"),
    ]
    transcript = [
        TranscriptSegment(start=start, end=start + 5, text=f"Kalimat {start}.")
        for start in range(0, 420, 5)
    ]

    sequence, roles, plan = build_long_form_story_sequence(candidates, transcript)

    assert sequence[0].start == 120
    assert [item.index for item in candidates] == [1, 2, 3, 4]
    assert 10 <= sequence[0].duration <= 22
    assert [item.start for item in sequence[1:]] == sorted(item.start for item in sequence[1:])
    assert sum(item.duration for item in sequence) == sum(item.duration for item in candidates)
    assert sequence[2].start == sequence[0].end
    assert "Kalimat 120" in sequence[0].text
    assert "Kalimat 135" not in sequence[0].text
    assert "Kalimat 135" in sequence[2].text
    assert "Kalimat 120" not in sequence[2].text
    assert roles == [
        "cold_open",
        "context",
        "development",
        "evidence_and_answer",
        "payoff_conclusion",
    ]
    assert plan["quality_gate_passed"] is True
    assert plan["filler_padding_added"] is False
    assert plan["duplicated_teaser_content"] is False


def test_long_story_director_never_makes_an_arbitrary_partial_teaser():
    candidates = [
        make_candidate(1, 0, 82, "Konteks lengkap"),
        make_candidate(2, 120, 96, "Jawaban terkuat"),
        make_candidate(3, 240, 88, "Kesimpulan lengkap"),
    ]
    transcript = [
        TranscriptSegment(start=start, end=start + 5, text=f"fragmen {start}")
        for start in range(0, 300, 5)
    ]

    sequence, _roles, plan = build_long_form_story_sequence(candidates, transcript)

    assert sequence[0].start == 120
    assert sequence[0].duration == candidates[1].duration
    assert len(sequence) == len(candidates)
    assert plan["cold_open_boundary"] == "complete_selected_beat"
