"""A model response must never bypass evidence, rights, or duplicate-upload gates."""
import json
import io
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

import api
import long_video_qc as qc

ORIGINAL_YOUTUBE_PREFLIGHT = api.youtube_monetization_preflight_issue


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


def test_cron_long_cannot_reuse_media_without_its_story_evidence(media):
    c = {**context(), "cron_long_strategy_required": True}
    def forbidden(*args): pytest.fail("A media review cannot replace missing Long story evidence")
    result = qc.audit_long(media, c, reviewer=forbidden)
    assert result["audit"]["decision"] == "DROP_SOURCE"
    assert not result["audit"]["upload_allowed"]


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


@pytest.mark.parametrize('status', [422, 503])
def test_provider_diagnostics_preserve_request_id_without_credentials(media, monkeypatch, status):
    from urllib.error import HTTPError
    monkeypatch.setenv('CLIPFORGE_QC_AI_API_KEY', 'test-api-key')
    def failed(*args):
        message = 'input rejected by content safety screening' if status == 422 else 'temporarily unavailable'
        raise HTTPError('https://test.invalid', status, 'Provider error',
            {'x-request-id': 'req-support-123'},
            io.BytesIO(json.dumps({'error': message, 'key': 'test-api-key', 'authorization': 'Bearer another-token'}).encode()))
    result = qc.audit_long(media, context(), reviewer=failed)
    assert result['provider_request_id'] == 'req-support-123'
    assert result['provider_http_status'] == status and result['stage'] == 'vision_review'
    assert 'test-api-key' not in result['provider_error'] and 'another-token' not in result['provider_error']
    if status == 422:
        assert qc.terminal_provider_rejection(result)
        assert not result['audit']['upload_allowed'] and 'retry_after_seconds' not in result
    else:
        assert result['audit'] is None and result['status'] == 'waiting_for_ai_or_evidence'


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


def test_audio_caption_mismatch_is_a_source_failure_not_an_outage_retry(media, monkeypatch):
    monkeypatch.setattr(qc, 'provider_config', lambda: {'audio_review_mode': 'local_whisper'})
    def mismatch(*args):
        raise qc.AudioCaptionMismatch('Rendered audio does not sufficiently match timed captions at output 0.000-3.000s')
    monkeypatch.setattr(qc, 'local_audio_evidence', mismatch)
    result = qc.audit_long(media, context(), reviewer=lambda *args: pytest.fail('Mismatched audio reached AI'))
    assert result['status'] == 'reviewed' and result['stage'] == 'local_audio'
    assert result['audit']['decision'] == 'DROP_SOURCE'
    assert result['audit']['upload_allowed'] is False
    assert '0.000-3.000s' in result['audit']['evidence'][0]
    assert 'retry_after_seconds' not in result
    assert media.is_file()


def test_failed_ai_contract_reports_stage_and_redacts_credentials(media, monkeypatch):
    monkeypatch.setattr(qc, 'provider_config', lambda: {'audio_review_mode': 'remote', 'api_key': 'test-secret-token'})
    def invalid(*args):
        raise ValueError('Invalid boolean test-secret-token Bearer another-secret https://user:password@example.test/v1')
    monkeypatch.setattr(qc, 'validate_ai_result', invalid)
    result = qc.audit_long(media, context(), reviewer=lambda *args: model_result())
    assert result['status'] == 'waiting_for_ai_or_evidence'
    assert result['audit'] is None and result['stage'] == 'ai_validation'
    assert result['reason'] == 'ValueError'
    assert 'Invalid boolean' in result['reason_detail']
    assert all(secret not in result['reason_detail'] for secret in ('test-secret-token', 'another-secret', 'user:password'))


def test_unavailable_local_recognizer_keeps_hold_instead_of_rejecting_source(media, monkeypatch):
    monkeypatch.setattr(qc, 'provider_config', lambda: {'audio_review_mode': 'local_whisper'})
    def unavailable(*args):
        raise ValueError('Cached local Whisper model unavailable')
    monkeypatch.setattr(qc, 'local_audio_evidence', unavailable)
    result = qc.audit_long(media, context())
    assert result['status'] == 'waiting_for_ai_or_evidence' and result['audit'] is None
    assert result['stage'] == 'local_audio'
    assert result['reason_detail'] == 'Cached local Whisper model unavailable'


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


@pytest.fixture
def tiktok_long(worker, monkeypatch):
    job, media, youtube, audit = worker
    state = api.long_production_state()
    state['auto_qc_tiktok_upload'] = True
    api.save_long_production_state(state)
    monkeypatch.setattr(api, 'require_tiktok_ready', lambda: None)
    monkeypatch.setattr(api, 'tiktok_login_is_active', lambda: False)
    created = []
    def create(job_id, request, *, allow_audited_automation=False):
        assert request.visibility == 'only_you' and allow_audited_automation
        row = api.TikTokUploadJob(id='tiktok-long', source_job_id=job_id,
            clip_url=request.clip_url, clip_name='video.mp4', status='queued',
            created_at=api.now_iso(), updated_at=api.now_iso(), caption='Test', visibility='only_you', target_handle='test')
        created.append(row)
        return row
    def start(rows):
        record = json.loads(api.long_qc_path(job.id, job.clips[0].url).read_text())
        assert rows[0].id in api.tiktok_uploads
        assert record['tiktok_upload_id'] == rows[0].id
        saved = json.loads(api.TIKTOK_UPLOADS_PATH.read_text())
        assert any(row['id'] == rows[0].id for row in saved)
    monkeypatch.setattr(api, 'create_tiktok_upload_record', create)
    monkeypatch.setattr(api, 'queue_tiktok_upload_jobs', start)
    return job, media, youtube, created, audit


def confirmed_youtube_for(job):
    return api.YouTubeUploadJob(id='already-youtube', source_job_id=job.id,
        clip_url=job.clips[0].url, clip_name='video.mp4', status='completed',
        created_at=api.now_iso(), updated_at=api.now_iso(), title='Existing',
        upload_confirmed=True, video_url='https://www.youtube.com/watch?v=abcdefghijk')


def test_youtube_success_does_not_starve_tiktok_long_and_restart_cannot_duplicate(tiktok_long):
    job, _, youtube, tiktok, _ = tiktok_long
    existing = confirmed_youtube_for(job)
    api.youtube_uploads[existing.id] = existing
    api.run_long_qc(job.id, job.clips[0].url)
    api.run_long_qc(job.id, job.clips[0].url)
    assert not youtube and len(tiktok) == 1
    assert api.youtube_uploads[existing.id].upload_confirmed
    assert job.request.publication_review_required and not job.clips[0].is_correct


def test_youtube_outage_does_not_block_tiktok_long(tiktok_long, monkeypatch):
    job, _, _, tiktok, _ = tiktok_long
    def unavailable():
        raise RuntimeError('YouTube temporarily unavailable')
    monkeypatch.setattr(api, 'require_youtube_ready', unavailable)
    api.run_long_qc(job.id, job.clips[0].url)
    assert len(tiktok) == 1
    record = json.loads(api.long_qc_path(job.id, job.clips[0].url).read_text())
    assert record['youtube_worker_error'] == 'RuntimeError'
    assert record['tiktok_upload_visibility'] == 'only_you'


@pytest.mark.parametrize('hold', ['drop', 'repair', 'preflight', 'disabled', 'login', 'unknown_submission'])
def test_tiktok_long_holds_do_not_submit(tiktok_long, monkeypatch, hold):
    job, _, _, tiktok, audit = tiktok_long
    if hold in {'drop', 'repair'}:
        audit.update(decision='DROP_SOURCE' if hold == 'drop' else 'REPAIR_ONCE', upload_allowed=False)
    if hold == 'preflight':
        monkeypatch.setattr(api, 'youtube_monetization_preflight_issue', lambda *a: 'Rights hold')
    if hold == 'disabled':
        state = api.long_production_state(); state['auto_qc_tiktok_upload'] = False
        api.save_long_production_state(state)
    if hold == 'login': monkeypatch.setattr(api, 'tiktok_login_is_active', lambda: True)
    if hold == 'unknown_submission':
        old = api.TikTokUploadJob(id='uncertain', source_job_id=job.id,
            clip_url=job.clips[0].url, clip_name='video.mp4', status='failed',
            created_at=api.now_iso(), updated_at=api.now_iso(), caption='Test', submission_started=True, target_handle='test')
        api.tiktok_uploads[old.id] = old
    api.run_long_qc(job.id, job.clips[0].url)
    assert not tiktok


def test_queue_does_not_skip_passed_long_with_youtube_pointer_but_no_tiktok(tiktok_long, monkeypatch):
    job, media, _, _, audit = tiktok_long
    existing = confirmed_youtube_for(job)
    api.youtube_uploads[existing.id] = existing
    api.save_long_qc(api.long_qc_path(job.id, job.clips[0].url), dict(status='reviewed',
        audit=audit, fingerprint=qc.fingerprint(media, api.long_qc_context(job, job.clips[0])),
        upload_id=existing.id))
    started = []
    monkeypatch.setattr(api.threading, 'Thread', lambda **kwargs: SimpleNamespace(start=lambda: started.append(kwargs)))
    assert api.queue_review_long_qc_once() == 1
    assert started[0]['args'] == (job.id, job.clips[0].url)


def test_provider_refusal_is_not_resubmitted_after_fingerprint_change(tiktok_long, monkeypatch):
    job, _, youtube, tiktok, audit = tiktok_long
    audit.update(decision='DROP_SOURCE', upload_allowed=False,
        hard_gates={**audit['hard_gates'], 'context_safe':False},
        evidence=['AI provider explicitly declined this source during content safety screening.'])
    api.save_long_qc(api.long_qc_path(job.id, job.clips[0].url), dict(status='reviewed',
        audit=audit, fingerprint='old-before-provider-or-metadata-change'))
    monkeypatch.setattr(qc, 'audit_long', lambda *a: pytest.fail('A terminal source was sent to the provider again'))
    assert api.queue_review_long_qc_once() == 0
    api.run_long_qc(job.id, job.clips[0].url)
    assert not youtube and not tiktok
    assert 'ditolak pemeriksaan konten' in api.long_tiktok_review_hold(job, job.clips[0])


def test_long_hold_display_explains_caption_failure(tiktok_long):
    job, _, _, _, audit = tiktok_long
    audit.update(decision='DROP_SOURCE', upload_allowed=False,
        evidence=['Invalid or overlapping output caption timing'])
    api.save_long_qc(api.long_qc_path(job.id, job.clips[0].url), dict(status='reviewed', audit=audit))
    assert 'subtitle' in api.long_tiktok_review_hold(job, job.clips[0])


def test_terminal_long_qc_blocks_youtube_even_when_manual_review_is_checked(tiktok_long, monkeypatch):
    job, _, _, _, audit = tiktok_long
    clip = job.clips[0]
    clip.is_correct = True
    audit.update(decision='DROP_SOURCE', upload_allowed=False,
        hard_gates={**audit['hard_gates'], 'context_safe': False},
        evidence=['AI provider explicitly declined this source during content safety screening.'])
    api.save_long_qc(api.long_qc_path(job.id, clip.url), dict(status='reviewed', audit=audit))
    assert 'DROP_SOURCE' in ORIGINAL_YOUTUBE_PREFLIGHT(job, clip)
    assert api.long_upload_review_hold(job, clip) == api.long_tiktok_review_hold(job, clip)


def test_display_exposes_long_qc_hold_instead_of_false_youtube_ready(tiktok_long, monkeypatch):
    job, _, _, _, audit = tiktok_long
    audit.update(decision='DROP_SOURCE', upload_allowed=False,
        hard_gates={**audit['hard_gates'], 'context_safe': False},
        evidence=['AI provider explicitly declined this source during content safety screening.'])
    api.save_long_qc(api.long_qc_path(job.id, job.clips[0].url), dict(status='reviewed', audit=audit))
    for name in ['enrich_job_source_metadata', 'enrich_job_codex_feedback',
                 'enrich_job_clip_titles', 'enrich_job_director_recovery', 'attach_job_telemetry']:
        monkeypatch.setattr(api, name, lambda item: item)
    display = api.enrich_job_for_display(job).clips[0]
    assert display.youtube_upload_ready is False
    assert 'DROP_SOURCE' in display.youtube_upload_issue
    assert display.tiktok_upload_issue == display.youtube_upload_issue
    assert display.production_qc_brief == display.youtube_upload_issue
    assert display.automatic_repair_available is False


def test_changed_media_during_platform_setup_cannot_enter_tiktok(tiktok_long, monkeypatch):
    job, media, _, tiktok, _ = tiktok_long
    monkeypatch.setattr(api, 'require_tiktok_ready', lambda: media.write_bytes(b'changed after review'))
    api.run_long_qc(job.id, job.clips[0].url)
    assert not tiktok
    record = json.loads(api.long_qc_path(job.id, job.clips[0].url).read_text())
    assert record['status'] == 'evidence_changed' and record['audit'] is None


def test_cached_rejection_releases_daily_success_count_without_reaudit(tiktok_long, monkeypatch):
    job, media, _, _, audit = tiktok_long
    state = api.long_production_state()
    state['attempts'] = [dict(job_id=job.id, status='completed')]
    api.save_long_production_state(state)
    audit.update(decision='DROP_SOURCE', upload_allowed=False)
    api.save_long_qc(api.long_qc_path(job.id, job.clips[0].url), dict(status='reviewed', audit=audit,
        fingerprint=qc.fingerprint(media, api.long_qc_context(job, job.clips[0]))))
    monkeypatch.setattr(qc, 'audit_long', lambda *a: pytest.fail('Unchanged rejected Long was reaudited'))
    assert api.queue_review_long_qc_once() == 0
    assert api.long_production_state()['attempts'][0]['qc_decision'] == 'DROP_SOURCE'
