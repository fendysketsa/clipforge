from api import (
    ClipCandidate,
    ClipFile,
    ClipJob,
    ClipJobRequest,
    best_youtube_clip_urls,
)


def make_clip(index: int) -> ClipFile:
    return ClipFile(
        name=f"clip_{index:02d}.mp4",
        url=f"/outputs/demo/clips/clip_{index:02d}.mp4",
        size_bytes=1,
    )


def make_candidate(index: int, score: int) -> ClipCandidate:
    return ClipCandidate(
        index=index,
        start=0,
        end=10,
        duration=10,
        score=score,
        title=f"Clip {index}",
        reason="test",
        text="test",
    )


def test_best_youtube_clip_urls_uses_candidate_scores():
    job = ClipJob(
        id="job-1",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/demo"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[make_clip(1), make_clip(2), make_clip(3), make_clip(4)],
        candidates=[
            make_candidate(1, 70),
            make_candidate(2, 98),
            make_candidate(3, 85),
            make_candidate(4, 92),
        ],
    )

    assert best_youtube_clip_urls(job, 3) == [
        "/outputs/demo/clips/clip_02.mp4",
        "/outputs/demo/clips/clip_04.mp4",
        "/outputs/demo/clips/clip_03.mp4",
    ]


def test_best_youtube_clip_urls_falls_back_to_clip_order_without_scores():
    job = ClipJob(
        id="job-1",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/demo"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[make_clip(1), make_clip(2), make_clip(3), make_clip(4)],
    )

    assert best_youtube_clip_urls(job, 3) == [
        "/outputs/demo/clips/clip_01.mp4",
        "/outputs/demo/clips/clip_02.mp4",
        "/outputs/demo/clips/clip_03.mp4",
    ]
