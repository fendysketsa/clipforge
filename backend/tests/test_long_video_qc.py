"""A model response must never bypass evidence, rights, or duplicate-upload gates."""
import json
import io
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

import api
import long_video_qc as qc


@pytest.fixture(autouse=True)
def isolate_provider_credentials(monkeypatch, tmp_path):
    monkeypatch.setattr(qc, 'PROVIDER_CONFIG_PATH', tmp_path / 'provider.json')


def context():
    return dict(source_job_id="long", source_clip_url="/outputs/long/video.mp4",
        source_url="https://www.youtube.com/watch?v=abcdefghijk",
        rights_confirmed=True, rights_evidence="Written commercial permission for audio and video",
        rights_risks=[], claim_block=None, news_hot=False, repair_attempted=False,
        score_floor_met=True)


def model_result(action="PASS_UPLOAD"):
    return dict(decision=action, confidence=.95,
        hard_gates={k: True for k in qc.GATES}, ai_checks={k: True for k in qc.CHECKS},
        evidence=["At 0.5s the question is visible; 2.2s contains the complete answer."],
        repair_instructions=["Trim only the opening silence from output 0.0s to 0.2s."])


@pytest.fixture
def media(tmp_path):
    path = tmp_path / "video.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=640x360:r=12:d=3",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-c:v", "libx264", "-threads", "1",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)], check=True)
    path.with_suffix(".json").write_text(json.dumps({
        "source_provenance": {"url": context()["source_url"], "rights_verified": True},
        "editorial_safety": {"safe_for_selection": True},
        "parts": [{"start": 10, "end": 13, "text": "Pertanyaan. Jawaban lengkap."}],
    }))
    path.with_suffix(".srt").write_text("1\n00:00:00,100 --> 00:00:02,800\nPertanyaan. Jawaban lengkap.\n")
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-frames:v", "1", "-threads", "1",
        str(path.with_name("video_thumb.jpg"))], check=True)
    return path


def test_real_media_audit_uses_opening_ending_and_thumbnail(media):
    calls = []
    def reviewer(evidence, frames):
        calls.append((evidence, frames))
        assert all(f["data_url"].startswith("data:image/jpeg;base64,") for f in frames)
        assert evidence["audio_samples"] and all(s["data"] for s in evidence["audio_samples"])
        return model_result()
    result = qc.audit_long(media, context(), reviewer=reviewer)
    assert result["audit"]["decision"] == "PASS_UPLOAD"
    assert result["audit"]["upload_allowed"]
    assert .5 in result["frame_timestamps_seconds"]
    assert "thumbnail" in result["frame_timestamps_seconds"]
    assert calls[0][0]["audio_mean_db"] < 0


@pytest.mark.parametrize("failure", ["rights", "claim", "source", "context", "render", "hash"])
def test_hard_failure_never_calls_ai(media, failure):
    c = context()
    sidecar = json.loads(media.with_suffix(".json").read_text())
    if failure == "rights": c["rights_evidence"] = ""
    if failure == "claim": c["claim_block"] = "Content ID"
    if failure == "source": sidecar["source_provenance"]["url"] = "other"
    if failure == "context": c["news_hot"] = True
    if failure == "render": sidecar["render_quality_qc"] = {"blocking": True}
    if failure == "hash": sidecar["provenance"] = {"output_sha256": "wrong"}
    media.with_suffix(".json").write_text(json.dumps(sidecar))
    def forbidden(*args): pytest.fail("AI cannot override hard evidence")
    result = qc.audit_long(media, c, reviewer=forbidden)
    assert result["audit"]["decision"] == "DROP_SOURCE"
    assert not result["audit"]["upload_allowed"]
    assert media.is_file()  # reviewer returns a disposition; never deletes files


def test_documented_operator_permission_does_not_require_license_metadata(media):
    sidecar = json.loads(media.with_suffix('.json').read_text())
    sidecar['source_provenance'].update(rights_verified=False, rights_basis='unverified')
    media.with_suffix('.json').write_text(json.dumps(sidecar))
    result = qc.audit_long(media, context(), reviewer=lambda *args: model_result())
    assert result['audit']['decision'] == 'PASS_UPLOAD'
    assert not json.loads(media.with_suffix('.json').read_text())['source_provenance']['rights_verified']


def test_missing_transcript_is_drop(media):
    media.with_suffix(".srt").unlink()
    assert qc.audit_long(media, context())["audit"]["decision"] == "DROP_SOURCE"


def test_ai_outage_holds_without_guessing(media, monkeypatch):
    monkeypatch.delenv("CLIPFORGE_QC_AI_BASE_URL", raising=False)
    result = qc.audit_long(media, context())
    assert result["status"] == "waiting_for_ai_or_evidence"
    assert result["audit"] is None


def test_provider_safety_refusal_is_terminal_and_not_retried_as_outage(media):
    from urllib.error import HTTPError
    def refused(*args):
        raise HTTPError('https://test.invalid', 422, 'Rejected', {},
            io.BytesIO(b'{"error":"input rejected by content safety screening"}'))
    result = qc.audit_long(media, context(), reviewer=refused)
    assert result['status'] == 'reviewed'
    assert result['audit']['decision'] == 'DROP_SOURCE'
    assert result['audit']['upload_allowed'] is False


def test_provider_receives_images_and_audio_as_evidence(monkeypatch):
    monkeypatch.setenv('CLIPFORGE_QC_AI_BASE_URL', 'http://test.invalid/v1')
    monkeypatch.setenv('CLIPFORGE_QC_AI_MODEL', 'multimodal-test')
    qc.PROVIDER_CONFIG_PATH.write_text(json.dumps({'media_export_authorized': True}))
    def response(request, **kwargs):
        body = json.loads(request.data)
        content = body['messages'][0]['content']
        assert any(row['type'] == 'image_url' for row in content)
        assert any(row['type'] == 'input_audio' for row in content)
        assert 'AUDIO_BASE64' not in content[0]['text']
        return io.BytesIO(json.dumps({'choices': [{'message': {
            'content': json.dumps(model_result())}}]}).encode())
    monkeypatch.setattr(qc.urllib.request, 'urlopen', response)
    result = qc.vision_review({'audio_samples': [dict(start_seconds=0, duration_seconds=3,
        data='AUDIO_BASE64')], 'output_subtitles': 'Exact subtitle text'},
        [dict(timestamp_seconds=.5, data_url='data:image/jpeg;base64,IMAGE')])
    assert result['decision'] == 'PASS_UPLOAD'


def test_external_provider_requires_explicit_media_export_approval(monkeypatch):
    monkeypatch.setenv('CLIPFORGE_QC_AI_BASE_URL', 'https://test.invalid/v1')
    monkeypatch.setenv('CLIPFORGE_QC_AI_MODEL', 'multimodal-test')
    def forbidden(*args, **kwargs): pytest.fail('Unapproved media export')
    monkeypatch.setattr(qc.urllib.request, 'urlopen', forbidden)
    with pytest.raises(PermissionError):
        qc.vision_review({}, [])


def test_local_audio_review_compares_actual_recognition_with_timed_captions(monkeypatch):
    model = SimpleNamespace(transcribe=lambda *a, **k: (
        [SimpleNamespace(text='Pertanyaan. Jawaban lengkap.', avg_logprob=-.2)], None))
    monkeypatch.setattr(qc, 'local_audio_model', lambda: model)
    sample = dict(start_seconds=0, duration_seconds=3, data='d2F2')
    subtitles = '1\n00:00:00,100 --> 00:00:02,800\nPertanyaan. Jawaban lengkap.\n'
    assert qc.local_audio_evidence([sample], subtitles)[0]['caption_overlap_f1'] == 1
    model.transcribe = lambda *a, **k: ([SimpleNamespace(text='Different unrelated audio', avg_logprob=-.2)], None)
    with pytest.raises(ValueError):
        qc.local_audio_evidence([sample], subtitles)


@pytest.mark.parametrize("change", ["false_check", "string_bool", "missing_gate", "low_score", "low_confidence", "no_evidence"])
def test_contradictory_pass_is_rejected(change):
    raw, c = model_result(), context()
    if change == "false_check": raw["ai_checks"]["payoff"] = False
    if change == "string_bool": raw["ai_checks"]["caption"] = "true"
    if change == "missing_gate": del raw["hard_gates"]["meaning_preserved"]
    if change == "low_score": c["score_floor_met"] = False
    if change == "low_confidence": raw["confidence"] = .7
    if change == "no_evidence": raw["evidence"] = []
    with pytest.raises(ValueError):
        qc.validate_ai_result(raw, c, {k: True for k in qc.GATES}, [])


def test_failed_deterministic_gate_and_second_repair_cannot_pass():
    gates = {k: True for k in qc.GATES}
    gates["rights"] = False
    assert qc.validate_ai_result(model_result(), context(), gates, ["Rights failed"])["decision"] == "DROP_SOURCE"
    c = {**context(), "repair_attempted": True}
    assert qc.validate_ai_result(model_result("REPAIR_ONCE"), c,
        {k: True for k in qc.GATES}, [])["decision"] == "DROP_SOURCE"


def test_fingerprint_invalidates_on_subtitle_or_claim_change(media):
    original = qc.fingerprint(media, context())
    assert original != qc.fingerprint(media, {**context(), "claim_block": "claim"})
    media.with_suffix(".srt").write_text("Changed captions")
    assert original != qc.fingerprint(media, context())


@pytest.fixture
def worker(monkeypatch, tmp_path):
    c = context()
    path = tmp_path / "video.mp4"
    path.write_bytes(b"test artifact")
    job = api.ClipJob(id="long", status="completed", created_at=api.now_iso(), updated_at=api.now_iso(),
        request=api.ClipJobRequest(url=c["source_url"], clip_mode="highlight_5m", publication_review_required=True),
        clips=[api.ClipFile(name="video.mp4", url=c["source_clip_url"], size_bytes=13, fyp_score=95)])
    api.jobs[job.id] = job
    api.save_long_production_state(dict(enabled=True, daily_target=1, attempts=[],
        auto_qc_enabled=True, auto_qc_private_upload=True))
    monkeypatch.setattr(api, "output_path_from_url", lambda url: path)
    monkeypatch.setattr(api, "long_qc_context", lambda *args: c)
    audit = qc._decision(c, gates={k: True for k in qc.GATES}, action="PASS_UPLOAD",
        checks={k: True for k in qc.CHECKS}, evidence=["Test evidence"])
    monkeypatch.setattr(qc, "audit_long", lambda *args: dict(status="reviewed", audit=audit))
    monkeypatch.setattr(api, "youtube_monetization_preflight_issue", lambda *args: None)
    monkeypatch.setattr(api, "require_youtube_ready", lambda: None)
    monkeypatch.setattr(api, "long_qc_active", set())
    uploads = []
    def create(job_id, request):
        assert request.visibility == "private" and request.publish_at is None
        row = api.YouTubeUploadJob(id="upload", source_job_id=job_id, clip_url=request.clip_url,
            clip_name="video.mp4", status="queued", created_at=api.now_iso(), updated_at=api.now_iso(),
            visibility="private", title="Test")
        api.youtube_uploads[row.id] = row
        uploads.append(row)
        return row
    monkeypatch.setattr(api, "create_youtube_upload_record", create)
    monkeypatch.setattr(api, "queue_youtube_upload_jobs", lambda rows: None)
    return job, path, uploads, audit


def test_pass_queues_private_once_and_preserves_human_hold(worker):
    job, _, uploads, _ = worker
    api.run_long_qc(job.id, job.clips[0].url)
    api.run_long_qc(job.id, job.clips[0].url)
    assert len(uploads) == 1
    assert job.request.publication_review_required and not job.clips[0].is_correct


@pytest.mark.parametrize("reason", ["drop", "repair", "preflight", "disabled", "remote_unknown", "changed"])
def test_hold_never_uploads(worker, monkeypatch, reason):
    job, path, uploads, audit = worker
    if reason in {"drop", "repair"}:
        audit.update(decision="DROP_SOURCE" if reason == "drop" else "REPAIR_ONCE", upload_allowed=False)
    if reason == "preflight": monkeypatch.setattr(api, "youtube_monetization_preflight_issue", lambda *a: "Rights hold")
    if reason == "disabled":
        state = api.long_production_state(); state["auto_qc_private_upload"] = False; api.save_long_production_state(state)
    if reason == "remote_unknown": monkeypatch.setattr(api, "pending_completed_job_upload_urls", lambda *a, **k: [])
    if reason == "changed":
        def review(*a):
            path.write_bytes(b"changed during review")
            return dict(status="reviewed", audit=audit)
        monkeypatch.setattr(qc, "audit_long", review)
    api.run_long_qc(job.id, job.clips[0].url)
    assert uploads == []


def test_terminal_rejection_is_not_reaudited(worker, monkeypatch):
    job, _, _, audit = worker
    audit.update(decision="DROP_SOURCE", upload_allowed=False)
    api.run_long_qc(job.id, job.clips[0].url)
    assert api.queue_review_long_qc_once() == 0
    record = json.loads(api.long_qc_path(job.id, job.clips[0].url).read_text())
    assert record["audit"]["decision"] == "DROP_SOURCE"


def test_existing_remote_checkpoint_blocks_duplicate(worker):
    job, _, uploads, _ = worker
    api.youtube_uploads['old'] = api.YouTubeUploadJob(
        id='old', source_job_id=job.id, clip_url=job.clips[0].url,
        clip_name='video.mp4', status='failed', created_at=api.now_iso(), updated_at=api.now_iso(),
        title='Existing draft', visibility='private', video_url='https://www.youtube.com/watch?v=abcdefghijk',
        upload_confirmed=False, error='Remote state unknown after restart')
    api.run_long_qc(job.id, job.clips[0].url)
    assert uploads == []


def test_upload_record_is_durable_before_worker_starts(worker, monkeypatch):
    job, _, _, _ = worker
    def start(rows):
        saved = json.loads(api.YOUTUBE_UPLOADS_PATH.read_text())
        record = json.loads(api.long_qc_path(job.id, job.clips[0].url).read_text())
        assert saved[0]['id'] == record['upload_id'] == rows[0].id
    monkeypatch.setattr(api, 'queue_youtube_upload_jobs', start)
    api.run_long_qc(job.id, job.clips[0].url)
