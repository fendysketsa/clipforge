import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import api
import tiktok_uploader as uploader
import automatic_retry


@pytest.fixture
def failed_caption(monkeypatch, tmp_path):
    monkeypatch.setenv('TIKTOK_AUTOMATIC_RETRY_ENABLED','true')
    path = tmp_path / 'clip.mp4'
    path.write_bytes(b'exact rendered clip')
    stamp = (datetime.now(timezone.utc)-timedelta(minutes=20)).isoformat()
    clip = api.ClipFile(name='clip.mp4', url='/outputs/job/clip.mp4', size_bytes=19)
    job = api.ClipJob(id='job', status='completed', request=api.ClipJobRequest(),
        created_at=stamp, updated_at=stamp, clips=[clip])
    upload = api.TikTokUploadJob(id='upload', source_job_id=job.id, clip_url=clip.url,
        clip_name=clip.name, status='failed', created_at=stamp, updated_at=stamp,
        caption='Reviewed caption', target_handle='titikbalikislami',
        clip_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        logs=['POST_BASELINE_MATCHES:0', 'Video dipilih: clip.mp4'],
        error='Kolom caption TikTok tetap tidak dapat diklik setelah dialog ditutup; video belum diposting.')
    api.jobs[job.id] = job
    api.tiktok_uploads[upload.id] = upload
    monkeypatch.setattr(api, 'output_path_from_url', lambda url: path)
    monkeypatch.setattr(api, 'youtube_monetization_preflight_issue', lambda *args: None)
    monkeypatch.setattr(api, 'require_tiktok_ready', lambda: None)
    monkeypatch.setattr(api, 'upload_media_duration_issue', lambda _path: None)
    started = []
    monkeypatch.setattr(api, 'queue_tiktok_upload_jobs', lambda rows: started.extend(rows))
    return path, upload, started


def test_pre_post_caption_failure_retries_same_record_once(failed_caption):
    _, upload, started = failed_caption
    assert api.queue_tiktok_caption_recoveries_once() == 1
    assert len(started) == 1 and started[0].id == upload.id
    assert 'CAPTION_READY_RETRY_ONCE' in api.tiktok_uploads[upload.id].logs
    assert api.queue_tiktok_caption_recoveries_once() == 0
    api.tiktok_uploads[upload.id].status = 'failed'
    assert api.queue_tiktok_caption_recoveries_once() == 0


def test_cron_retry_filter_cannot_claim_an_unrelated_upload(failed_caption):
    _, upload, started = failed_caption
    assert api.queue_retryable_tiktok_uploads_once(source_job_ids=set()) == 0
    assert api.queue_retryable_tiktok_uploads_once(source_job_ids={'another-job'}) == 0
    assert not started
    assert api.queue_retryable_tiktok_uploads_once(source_job_ids={upload.source_job_id}) == 1
    assert [item.id for item in started] == [upload.id]


def test_retry_gets_new_tail_position_even_with_other_platform_and_file_queued(failed_caption):
    _,upload,started=failed_caption
    other=upload.model_copy(update={'id':'other','source_job_id':'other-job','clip_url':'/outputs/other.mp4',
        'clip_sha256':'different-file','status':'queued','created_at':api.now_iso()})
    api.tiktok_uploads[other.id]=other
    api.youtube_uploads['yt']=object()  # Its backlog must not starve TikTok retry intake.
    now=datetime.now(timezone.utc)
    assert api.queue_retryable_tiktok_uploads_once(now)==1
    live=api.tiktok_uploads[upload.id]
    assert live.id==upload.id and live.queued_at==now.isoformat() and live.auto_retry_count==1
    positions={row.id:row.queue_position for row in api.tiktok_uploads_with_queue_positions(list(api.tiktok_uploads.values()))}
    assert positions=={upload.id:2,'other':1}
    assert api.queue_retryable_tiktok_uploads_once(now)==0


@pytest.mark.parametrize('risk', ['post', 'accepted', 'changed', 'gate', 'hash', 'other_success', 'other_error'])
def test_unsafe_caption_recovery_never_retries(failed_caption, monkeypatch, risk):
    path, upload, started = failed_caption
    if risk == 'post': upload.logs.append('Tombol Post diklik setelah privasi public terverifikasi.')
    if risk == 'accepted': upload.logs.append('POST_API_ACCEPTED:api')
    if risk == 'changed': path.write_bytes(b'different clip')
    if risk == 'gate': monkeypatch.setattr(api, 'youtube_monetization_preflight_issue', lambda *a: 'hold')
    if risk == 'hash': upload.clip_sha256 = None
    if risk == 'other_success': api.tiktok_uploads['success'] = upload.model_copy(update={'id':'success', 'upload_confirmed':True})
    if risk == 'other_error': upload.error = 'Unknown remote state'
    assert api.queue_tiktok_caption_recoveries_once() == 0
    assert started == []


def test_background_editor_uses_verified_fill_when_click_is_unstable(monkeypatch):
    class Editor:
        value = 'filename-derived caption'
        def click(self, **kwargs): raise RuntimeError('waiting for element to be stable')
        def fill(self, value, **kwargs): self.value = value
        def input_value(self, **kwargs): return self.value
    editor = Editor()
    monkeypatch.setattr(uploader, 'dismiss_blocking_modal', lambda page: (True, ''))
    uploader.clear_caption_editor(object(), editor)
    assert editor.value == ''


@pytest.mark.parametrize('error,reason',[
    ('Kolom caption TikTok belum siap; video belum diposting.','caption_not_ready'),
    ('Kolom caption TikTok tidak ditemukan setelah video dipilih.','caption_editor_not_ready'),
    ('Caption TikTok tidak dapat menggantikan judul otomatis dari nama file; video tidak diposting.','caption_replacement_not_ready'),
    ('Transfer file CDP TikTok gagal sebelum posting; tidak ada posting yang dibuat.','file_transfer_before_post'),
    ('Tombol Post TikTok belum aktif setelah 600 detik; video tidak diterbitkan.','post_button_not_ready'),
    ('Input upload TikTok tidak ditemukan. Periksa sesi dan halaman TikTok Studio.','upload_form_not_ready'),
    ('Daftar posting TikTok belum siap diverifikasi; file belum dipilih dan belum diposting.','post_baseline_not_ready'),
    ('Draft TikTok belum dapat dibuang; file belum dipilih dan belum diposting.','draft_discard_not_ready'),
    ('Pilihan Only you/Hanya Anda tidak ditemukan; upload tidak diterbitkan.','privacy_control_not_ready'),
    ('Kontrol privasi TikTok belum siap. Video belum diposting.','privacy_control_not_ready'),
    ('Pilihan privasi TikTok belum terverifikasi pada kontrol. Video belum diposting.','privacy_control_not_ready'),
    ('BrowserType.connect_over_cdp: Timeout 15000ms exceeded.','browser_connection_before_post'),
    ('Status tidak diketahui setelah upload.',''),
    ('CAPTCHA required; kolom caption TikTok belum siap; video belum diposting.',''),
    ('Content safety screening refused input.',''),
    ('Copyright claim detected.',''),
    ('Sesi TikTok belum login.',''),
])
def test_only_explicit_pre_post_transient_failures_are_retryable(error,reason):
    assert automatic_retry.tiktok_retry_reason(error,['POST_BASELINE_MATCHES:0'])==reason


@pytest.mark.parametrize('log',['POST_SUBMIT_INTENT: click about to happen',
    'POST_API_ACCEPTED: accepted','POST_API_REJECTED: timeout','POST_ALREADY_PRESENT: caption',
    'Tombol Post diklik setelah privasi public terverifikasi.','VIDEO_URL:https://example.test/post'])
def test_any_submission_checkpoint_blocks_fresh_retry(log):
    error='Kolom caption TikTok belum siap; video belum diposting.'
    assert automatic_retry.tiktok_retry_reason(error,[log])==''


def test_three_durable_retries_use_backoff_same_record_and_original_settings(failed_caption):
    _,original,started=failed_caption
    failure=original.error
    clock=datetime.now(timezone.utc)
    for count in range(1,4):
        assert api.queue_retryable_tiktok_uploads_once(clock+timedelta(hours=1))==1
        row=api.tiktok_uploads[original.id]
        assert row.id==original.id and row.auto_retry_count==count
        assert (row.clip_sha256,row.caption,row.visibility,row.target_handle)==(
            original.clip_sha256,original.caption,original.visibility,original.target_handle)
        row.status='failed';row.error=failure
        api.schedule_tiktok_upload_retry(row.id)
        row=api.tiktok_uploads[row.id]
        if count<3:
            due=api.parsed_datetime(row.auto_retry_at)
            assert due is not None
            assert api.queue_retryable_tiktok_uploads_once(due-timedelta(seconds=1))==0
            clock=due
        else:
            assert row.auto_retry_at is None
    assert api.queue_retryable_tiktok_uploads_once(clock+timedelta(days=1))==0
    assert len(started)==3


def test_retry_delay_is_persisted_without_restarting_timer_each_scan(failed_caption):
    _,row,_=failed_caption
    clock=datetime.now(timezone.utc)
    row.updated_at=clock.isoformat()
    assert api.queue_retryable_tiktok_uploads_once(clock)==0
    first=api.tiktok_uploads[row.id].auto_retry_at
    assert api.queue_retryable_tiktok_uploads_once(clock+timedelta(seconds=20))==0
    assert api.tiktok_uploads[row.id].auto_retry_at==first
    assert api.queue_retryable_tiktok_uploads_once(clock+timedelta(seconds=61))==1


def test_submission_flags_survive_restart_and_log_compaction(failed_caption):
    _,row,started=failed_caption
    row.submission_started=True;row.logs=[];row.auto_retry_count=2
    restored=api.TikTokUploadJob.model_validate_json(row.model_dump_json())
    api.tiktok_uploads[row.id]=restored
    assert restored.submission_started and restored.auto_retry_count==2
    assert api.queue_retryable_tiktok_uploads_once()==0 and not started


def test_unknown_sibling_and_newer_attempt_are_not_duplicated(failed_caption):
    _,row,started=failed_caption
    sibling=row.model_copy(update={'id':'other','submission_accepted':True})
    api.tiktok_uploads[sibling.id]=sibling
    assert api.queue_retryable_tiktok_uploads_once()==0 and not started


def test_background_campaign_reuses_failed_record_without_resetting_budget(failed_caption):
    _,row,_=failed_caption
    row.auto_retry_count=3
    result=api.create_tiktok_upload_record(row.source_job_id,
        api.TikTokUploadRequest(clip_url=row.clip_url),allow_audited_automation=True)
    assert result.id==row.id and result.auto_retry_count==3


def test_retry_scheduler_can_be_disabled_without_new_submissions(failed_caption,monkeypatch):
    _,_,started=failed_caption
    monkeypatch.setenv('TIKTOK_AUTOMATIC_RETRY_ENABLED','false')
    assert api.queue_retryable_tiktok_uploads_once()==0 and not started


@pytest.mark.parametrize('confirmed',[False,True])
def test_worker_does_not_retransmit_after_post_intent_and_preserves_late_success(failed_caption,monkeypatch,confirmed):
    _,row,_=failed_caption
    row.status='queued';row.error=None
    logs=['POST_SUBMIT_INTENT: attempting Post']
    if confirmed:logs+=['UPLOAD_CONFIRMED:private','VIDEO_URL:https://www.tiktok.com/@titikbalikislami']
    logs+=['USER_ERROR:BrowserType.connect_over_cdp: Timeout 15000ms exceeded.']
    calls=[]
    class Process:
        stdout=logs
        def wait(self):return 1
    monkeypatch.setattr(api,'build_tiktok_upload_command',lambda *a,**k:['uploader','--cdp-url','http://localhost:9444'])
    monkeypatch.setattr(api.subprocess,'Popen',lambda *a,**k:calls.append(a) or Process())
    monkeypatch.setattr(api,'schedule_cross_platform_cleanup_after_tiktok',lambda *a:None)
    api.run_tiktok_upload(row.id)
    result=api.tiktok_uploads[row.id]
    assert len(calls)==1 and result.submission_started
    assert result.status==('completed' if confirmed else 'failed')
    assert result.auto_retry_at is None and result.upload_confirmed==confirmed


def test_retry_corrects_only_mismatched_religious_template_and_keeps_its_audit(failed_caption):
    _,row,_=failed_caption
    api.jobs[row.source_job_id].clips[0].title='Yuta dan Mio bermain Roblox'
    row.caption='Yuta dan Mio bermain Roblox. #KajianIslam #BelajarIslam'
    original=row.caption
    assert api.queue_retryable_tiktok_uploads_once()==1
    result=api.tiktok_uploads[row.id]
    assert result.auto_retry_original_caption==original
    assert '#GamingIndonesia' in result.caption and '#KajianIslam' not in result.caption
    assert result.visibility==row.visibility and result.clip_sha256==row.clip_sha256
