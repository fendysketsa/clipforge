import tempfile
from pathlib import Path

from api import ClipCandidate, ClipFile, ClipJob, ClipJobRequest, cleanup_clip_files, cleanup_job_files
from clipper import cleanup_intermediate, friendly_youtube_error, prepare_uploaded_source


def test_cleanup_removes_source_and_audio_keeps_clips():
    work = Path(tempfile.mkdtemp())
    (work / "source.mp4").write_bytes(b"x" * 100)
    (work / "audio_1800s.wav").write_bytes(b"y" * 100)
    (work / "transcript.json").write_text("[]")
    (work / "clips").mkdir()
    (work / "clips" / "clip_01.mp4").write_bytes(b"z" * 10)

    cleanup_intermediate(work, work / "source.mp4")

    names = {p.name for p in work.iterdir()}
    assert "source.mp4" not in names
    assert "audio_1800s.wav" not in names
    assert "transcript.json" in names
    assert "clips" in names
    assert (work / "clips" / "clip_01.mp4").exists()


def test_prepare_uploaded_source_does_not_copy():
    upload = Path(tempfile.mkdtemp()) / "video.mp4"
    upload.write_bytes(b"u" * 100)
    work = Path(tempfile.mkdtemp())

    returned, meta = prepare_uploaded_source(upload, work)

    # The upload is read in place, not duplicated into the work dir.
    assert returned == upload
    assert list(work.iterdir()) == []
    assert meta["ext"] == "mp4"


def test_cleanup_does_not_delete_external_upload():
    upload = Path(tempfile.mkdtemp()) / "video.mp4"
    upload.write_bytes(b"u" * 100)
    work = Path(tempfile.mkdtemp())

    # An uploaded source lives outside the work dir and must survive cleanup.
    cleanup_intermediate(work, upload)

    assert upload.exists()


def test_friendly_youtube_error_explains_network_failure():
    message = friendly_youtube_error(RuntimeError("[Errno 101] Network is unreachable"), "membaca metadata")

    assert "Upload Video" in message
    assert "membaca metadata" in message


def test_cleanup_clip_files_removes_output_artifacts(monkeypatch):
    import api

    outputs = Path(tempfile.mkdtemp())
    clip_dir = outputs / "work" / "clips"
    clip_dir.mkdir(parents=True)
    clip_path = clip_dir / "clip_01.mp4"
    thumb_path = clip_dir / "clip_01_thumb.jpg"
    prompt_path = clip_dir / "clip_01_thumb.txt"
    caption_path = clip_dir / "clip_01_caption.txt"
    for path in (clip_path, thumb_path, prompt_path, caption_path):
        path.write_bytes(b"x")

    monkeypatch.setattr(api, "OUTPUTS_DIR", outputs)

    clip = ClipFile(
        name="clip_01.mp4",
        url="/outputs/work/clips/clip_01.mp4",
        size_bytes=1,
        thumbnail_url="/outputs/work/clips/clip_01_thumb.jpg",
    )

    assert cleanup_clip_files(clip) == 6
    assert not clip_path.exists()
    assert not thumb_path.exists()
    assert not prompt_path.exists()
    assert not caption_path.exists()
    assert not clip_dir.exists()


def test_clip_sidecar_title_reads_full_title(monkeypatch):
    import api

    outputs = Path(tempfile.mkdtemp())
    clip_dir = outputs / "work" / "clips"
    clip_dir.mkdir(parents=True)
    clip_path = clip_dir / "clip_01_saya-tidak-condong-tidak-setuju-kepada-buy.mp4"
    clip_path.write_bytes(b"x")
    clip_path.with_suffix(".json").write_text(
        '{"title": "Saya Tidak Condong, Tidak Setuju Kepada Buyut Saya"}',
        encoding="utf-8",
    )

    monkeypatch.setattr(api, "OUTPUTS_DIR", outputs)

    clip = ClipFile(
        name=clip_path.name,
        url="/outputs/work/clips/clip_01_saya-tidak-condong-tidak-setuju-kepada-buy.mp4",
        size_bytes=1,
    )

    assert api.clip_sidecar_title(clip) == "Saya Tidak Condong, Tidak Setuju Kepada Buyut Saya"


def test_enrich_clip_title_from_candidate_index_when_sidecar_missing(monkeypatch):
    import api

    outputs = Path(tempfile.mkdtemp())
    clip_dir = outputs / "work" / "clips"
    clip_dir.mkdir(parents=True)
    clip_path = clip_dir / "clip_09_saya-tidak-condong-tidak-setuju-kepada-buy.mp4"
    clip_path.write_bytes(b"x")

    monkeypatch.setattr(api, "OUTPUTS_DIR", outputs)

    clips = [
        ClipFile(
            name=clip_path.name,
            url="/outputs/work/clips/clip_09_saya-tidak-condong-tidak-setuju-kepada-buy.mp4",
            size_bytes=1,
        )
    ]
    candidates = [
        ClipCandidate(
            index=9,
            start=0,
            end=10,
            duration=10,
            score=90,
            title="Saya Tidak Condong Tidak Setuju Kepada Buya Arrazi",
            reason="test",
            text="test",
        )
    ]

    enriched = api.enrich_clips_with_candidate_titles(clips, candidates)

    assert enriched[0].title == "Saya Tidak Condong Tidak Setuju Kepada Buya Arrazi"


def test_cleanup_job_files_removes_related_output_folder(monkeypatch):
    import api

    outputs = Path(tempfile.mkdtemp())
    clip_dir = outputs / "video-title" / "clips"
    clip_dir.mkdir(parents=True)
    (outputs / "video-title" / "metadata.json").write_text("{}")
    (outputs / "video-title" / "candidates.json").write_text("[]")
    clip_path = clip_dir / "clip_01.mp4"
    clip_path.write_bytes(b"x")

    monkeypatch.setattr(api, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(api, "jobs", {})

    job = ClipJob(
        id="job-1",
        status="completed",
        request=ClipJobRequest(url="https://youtu.be/x"),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        clips=[
            ClipFile(
                name="clip_01.mp4",
                url="/outputs/video-title/clips/clip_01.mp4",
                size_bytes=1,
            )
        ],
    )

    cleanup_job_files(job)

    assert not (outputs / "video-title").exists()
