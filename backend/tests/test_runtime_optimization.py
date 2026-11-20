from datetime import datetime, timezone
import json

import pytest
import api
import dashboard_payload
import model_json


def upload(platform='youtube', **updates):
    fields=dict(id='row',source_job_id='job',clip_url='/outputs/job/clip.mp4',
        clip_name='clip.mp4',status='completed',created_at=api.now_iso(),updated_at=api.now_iso())
    if platform=='youtube':
        fields.update(title='Judul Indonesia — hikmah',video_url='https://www.youtube.com/watch?v=abcdefghijk',upload_confirmed=True)
        model=api.YouTubeUploadJob
    else:
        fields.update(caption='Nasihat Indonesia',target_handle='ryuundy',submission_started=True)
        model=api.TikTokUploadJob
    return model(**(fields|updates))


@pytest.mark.parametrize('platform',['youtube','tiktok'])
def test_dashboard_keeps_remote_identity_guards_and_full_store(platform,monkeypatch):
    markers=['Video dipilih: clip.mp4','Menyerahkan file ke YouTube Studio: clip.mp4',
        'REMOTE_UPLOAD_CHECKPOINT: abc','POST_SUBMIT_INTENT: possible',
        'POST_API_ACCEPTED: possible','CLAIMED_UPLOAD_ABORTED: hold',
        'THUMBNAIL_SKIPPED_DAILY_LIMIT: quota']
    snapshot_type=api.YouTubePerformanceSnapshot if platform=='youtube' else api.TikTokPerformanceSnapshot
    snapshot=snapshot_type(captured_at=api.now_iso(),source='manual',views=1200)
    row=upload(platform,logs=markers+[f'old log {i}' for i in range(160)],performance_snapshots=[snapshot])
    before=row.model_dump()
    monkeypatch.setattr(api,platform+'_uploads',{row.id:row})
    getter=getattr(api,'list_'+platform+'_uploads')
    compact=getter(dashboard=True)[0]
    full=getter()[0]
    assert all(marker in compact.logs for marker in markers)
    assert compact.logs[-8:]==row.logs[-8:] and len(compact.logs)==15
    assert full.logs==row.logs
    assert not compact.performance_snapshots and full.performance_snapshots==[snapshot]
    # Each independent GET supplies a fresh server clock for cleanup countdowns.
    omitted={'logs','performance_snapshots','backend_now'}
    assert {k:v for k,v in compact.model_dump().items() if k not in omitted}=={
        k:v for k,v in full.model_dump().items() if k not in omitted}
    assert getattr(api,platform+'_uploads')[row.id].model_dump()==before


@pytest.mark.parametrize('status',['queued','running'])
def test_active_upload_progress_logs_remain_complete(status):
    row=upload(status=status,logs=[str(i) for i in range(160)])
    assert dashboard_payload.compact_upload(row).logs==row.logs


@pytest.mark.parametrize('platform',['youtube','tiktok'])
def test_native_checkpoint_json_preserves_every_field_and_in_place_changes(platform):
    row=upload(platform,logs=['baris satu','kutipan " dan emoji 🎥'])
    expected=json.loads(json.dumps([row.model_dump()],ensure_ascii=False))
    assert json.loads(model_json.encode_records([row],type(row)))==expected
    row.logs.append('POST_SUBMIT_INTENT: persist immediately')
    row.status='failed'
    saved=json.loads(model_json.encode_records([row],type(row)))[0]
    assert saved['logs'][-1]==row.logs[-1] and saved['status']=='failed'


def test_native_job_checkpoint_omits_only_telemetry():
    job=api.ClipJob(id='job',status='running',created_at=api.now_iso(),updated_at=api.now_iso(),
        request=api.ClipJobRequest(source_file='owned.mp4',publication_review_required=True))
    expected=[job.model_dump(exclude={'telemetry'})]
    assert json.loads(model_json.encode_records([job],api.ClipJob,
        exclude={'__all__':{'telemetry'}}))==expected


def test_daily_plan_snapshot_omits_unused_heavy_fields_and_preserves_ownership(monkeypatch):
    monkeypatch.setenv('AUTO_VIRAL_DAILY_PLAN_ENABLED','true')
    run=api.AutoViralRun(id='campaign',trigger='schedule',status='completed',created_at=api.now_iso(),updated_at=api.now_iso(),
        request=api.AutoViralRequest(cron_daily_lane='private_short',cron_production_day='2026-11-20'),
        processed=[dict(job_id='child',repair_job_id='repair',long_job_id='long',status='completed',
            paired_short_snapshot={'created_at':api.now_iso(),'request':{'unused':'x'*100000}},source={'unused':'x'*100000})])
    monkeypatch.setattr(api,'auto_viral_runs',{run.id:run})
    captured={}
    original=api.daily_cron_plan.build_plan
    def build(**values):
        captured.update(values)
        return original(**values)
    monkeypatch.setattr(api.daily_cron_plan,'build_plan',build)
    api.daily_cron_plan_status(datetime(2026,11,20,tzinfo=timezone.utc))
    assert captured['runs'][0]['request']=={'cron_daily_lane':'private_short','cron_production_day':'2026-11-20'}
    item=captured['runs'][0]['processed'][0]
    assert item['repair_job_id']=='repair' and item['long_job_id']=='long'
    assert 'source' not in item and set(item['paired_short_snapshot'])=={'created_at'}


def test_runtime_optimization_capability_preserves_all_evidence():
    assert api.runtime_optimization()['full_upload_evidence_preserved'] is True
