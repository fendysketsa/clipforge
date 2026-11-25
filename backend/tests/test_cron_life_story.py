from datetime import datetime
import hashlib
import json
from types import SimpleNamespace as NS
from zoneinfo import ZoneInfo

import pytest

import api
import cron_life_story as story

def plan(used=0):
    return dict(enabled=True, day=story.today(), lanes={'scheduled_short': dict(used=used, remaining=17-used)})


def draft():
    # Distinct concrete scenes; production directions never enter TTS.
    texts = [
        'Di meja makan yang hampir kosong, Damar membuka pesan penolakan kerjanya. Ia menatap satu piring nasi, lalu menyimpan telepon agar dapat mendengar pertanyaan istrinya dengan tenang.',
        'Sudah tiga hari Damar hanya mengirim lamaran yang sama. Pagi ini persediaan beras menipis, sementara istrinya juga menunggu pembayaran jahitan yang belum selesai dikerjakan pelanggan.',
        'Damar memilih mendatangi bengkel tetangga dan menanyakan pekerjaan harian. Ia membawa contoh catatan persediaan yang pernah dibuatnya, sambil menjelaskan kapan ia bisa mulai membantu di sana.',
        'Pemilik bengkel meminta bantuan merapikan suku cadang selama setengah hari. Damar mencatat jumlah barang, memisahkan kotak yang rusak, dan bertanya lagi ketika instruksinya belum jelas.',
        'Sore itu Damar menerima pembayaran sesuai kesepakatan kerja tadi pagi. Ia membeli beras secukupnya, menyisihkan ongkos melamar kerja, lalu menulis pengeluaran bersama istrinya di buku kecil.',
        'Pekerjaan tetap memang belum didapatkan Damar. Namun kebutuhan makan hari ini terbantu, dan besok ia memiliki langkah yang lebih jelas daripada hanya menunggu kabar dari layar telepon.',
    ]
    return dict(title='Satu Pekerjaan Kecil Saat Lamaran Belum Terjawab',
        character_bible='Damar adalah pria Indonesia dewasa berusia tiga puluh tahun berambut pendek memakai kemeja biru polos dan celana cokelat',
        scenes=[dict(role=role, narration=text, visual=f'Damar melakukan aksi adegan {i} dengan ekspresi berbeda di lingkungan rumah dan bengkel sederhana yang jelas terlihat')
                for i, (role, text) in enumerate(zip(story.ROLES, texts))])


def test_daily_reservations_survive_restart_and_do_not_reset_failed_attempts(tmp_path):
    path=tmp_path/'state.json'
    first=story.reserve(path,'one','2026-11-24',2)
    assert story.reserve(path,'one','2026-11-24',2)==first
    story.update(path,'one',status='render_failed')
    second=story.reserve(path,'two','2026-11-24',2)
    assert first['topic']!=second['topic']
    with pytest.raises(ValueError,match='Jatah'):
        story.reserve(path,'three','2026-11-24',2)
    assert len(story.read(path)['episodes'])==2


def test_corrupt_ledger_never_becomes_an_empty_duplicate_ledger(tmp_path):
    path=tmp_path/'state.json';path.write_text('[]')
    with pytest.raises(ValueError):story.reserve(path,'run','2026-11-24',2)
    assert path.read_text()=='[]'


def test_experiment_uses_existing_short_quota_and_spaces_second_attempt():
    state={'episodes':{}}
    assert story.due(state,plan(),2)
    state['episodes']['one']={'day':story.today(),'status':'failed'}
    assert not story.due(state,plan(),2)
    assert story.due(state,plan(6),2)
    assert not story.due(state,plan(17),2)
    assert not story.due(state,plan(6),1)


def test_script_is_parseable_and_duplicate_narration_is_rejected():
    from long_animate import _scene_sections
    payload=draft();title,script=story.validate(payload,[])
    sections=_scene_sections(script)
    assert len(sections)==6 and sections[0]['narration']==payload['scenes'][0]['narration']
    assert title==payload['title'] and 'Arahan sutradara:' not in sections[0]['narration']
    with pytest.raises(ValueError,match='mirip'):
        story.validate(payload,[' '.join(s['narration'] for s in payload['scenes'])])


@pytest.mark.parametrize('risk',['missing_payoff','role','repeat','claim','direction_in_voice'])
def test_script_validation_does_not_silently_fill_missing_or_unsafe_evidence(risk):
    payload=draft()
    if risk=='missing_payoff':payload['scenes'].pop()
    elif risk=='role':payload['scenes'][0]['role']='payoff'
    elif risk=='repeat':payload['scenes'][1]['narration']=payload['scenes'][0]['narration']
    elif risk=='claim':payload['scenes'][1]['narration']+=' Semua orang dijamin sukses.'
    else:payload['scenes'][0]['narration']+='\nVisual: ubah gambar'
    with pytest.raises(ValueError):story.validate(payload,[])


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv('AUTO_VIRAL_DAILY_PLAN_ENABLED','true')
    monkeypatch.setenv('AUTO_VIRAL_CRON_LIFE_STORY_ENABLED','true')
    monkeypatch.setenv('AUTO_VIRAL_CRON_LIFE_STORY_PROVIDER_RIGHTS_EVIDENCE','Operator license document for configured image voice providers')
    monkeypatch.setattr(api,'daily_cron_plan_status',lambda:plan())


def test_cron_selection_and_missing_provider_evidence_are_explicit(configured,monkeypatch):
    request=api.scheduled_cron_life_story_request()
    assert request.cron_original_story and request.cron_daily_lane=='scheduled_short'
    assert not request.create_paired_long_video and request.video_count==1
    monkeypatch.delenv('AUTO_VIRAL_CRON_LIFE_STORY_PROVIDER_RIGHTS_EVIDENCE')
    assert api.scheduled_cron_life_story_request() is None
    status=api.get_cron_life_stories()
    assert status['state']=='waiting_for_provider_rights' and not status['provider_rights_ready']


def test_worker_flags_and_short_format_do_not_leak_into_manual_jobs(monkeypatch):
    monkeypatch.setenv('CLIPFORGE_CRON_LIFE_STORY','true')
    manual=api.ClipJobRequest(clip_mode='long_animate')
    automated=manual.model_copy(update={'scheduled_original_story':True})
    assert 'CLIPFORGE_CRON_LIFE_STORY' not in api.clipper_worker_environment(manual)
    assert api.clipper_worker_environment(automated)['CLIPFORGE_CRON_LIFE_STORY']=='true'
    clip=api.ClipFile(name='clip_01_cron_life_story.mp4',url='/outputs/story/clip.mp4',size_bytes=1)
    job=api.ClipJob(id='story',status='completed',created_at=api.now_iso(),updated_at=api.now_iso(),request=manual)
    assert api.is_compilation_clip(job,clip)
    job.request=automated
    assert not api.is_compilation_clip(job,clip)


def valid_sidecar():
    return dict(cron_life_story={'version':1,'series':story.SERIES}, aspect_ratio='9:16',duration=100,
        final_qc={'passed':True},narration_quality={'passed':True},cold_open_contract={'quality_gate_passed':True},
        dynamic_captions={'presentation':'stable_phrase_no_active_word_flicker'},asset_license_ledger={'complete':True})


@pytest.mark.parametrize('risk',['duration','landscape','qc','voice','caption','rights','missing'])
def test_upload_preflight_fails_closed(risk):
    data=valid_sidecar()
    assert story.preflight(data) is None
    if risk=='duration':data['duration']='unknown'
    elif risk=='landscape':data['aspect_ratio']='16:9'
    elif risk=='qc':data['final_qc']['passed']=False
    elif risk=='voice':data['narration_quality']['passed']=False
    elif risk=='caption':data['dynamic_captions']['presentation']='word_flash'
    elif risk=='rights':data['asset_license_ledger']['complete']=False
    else:data.pop('cron_life_story')
    assert story.preflight(data)


def test_completed_episode_checkpoints_same_child_then_uses_existing_uploader(configured,monkeypatch):
    request=api.scheduled_cron_life_story_request()
    run=api.AutoViralRun(id='episode',trigger='schedule',status='running',created_at=api.now_iso(),updated_at=api.now_iso(),request=request)
    api.auto_viral_runs[run.id]=run
    monkeypatch.setattr(api,'chat_completion',lambda *args,**kw:json.dumps(draft()))
    calls=[]
    def render(job_id,*args):
        assert api.auto_viral_runs[run.id].processed[0]['job_id']==job_id
        api.jobs[job_id]=api.jobs[job_id].model_copy(update={'status':'completed','clips':[
            api.ClipFile(name='clip_01_cron_life_story.mp4',url='/outputs/story/clip.mp4',size_bytes=1)]})
    monkeypatch.setattr(api,'run_clip_job_with_campaign_progress',render)
    def upload(run_id,req,items):
        calls.append(items[0]['job_id']);return items
    monkeypatch.setattr(api,'upload_auto_viral_processed_jobs',upload)
    request=request.model_copy(update={'auto_upload_youtube':True})
    story.run(api,run.id,request)
    child=api.auto_viral_runs[run.id].processed[0]['job_id']
    assert calls==[child] and api.auto_viral_runs[run.id].status=='completed'
    assert api.jobs[child].request.cron_daily_lane=='scheduled_short'
    assert not api.jobs[child].request.auto_upload_youtube
    with pytest.raises(ValueError,match='checkpoint'):
        story.run(api,run.id,request)
    assert len(api.jobs)==1 and calls==[child]


def test_manual_campaign_cannot_enter_original_story_worker(configured):
    request=api.scheduled_cron_life_story_request()
    api.auto_viral_runs['manual']=api.AutoViralRun(id='manual',trigger='manual',status='running',
        created_at=api.now_iso(),updated_at=api.now_iso(),request=request)
    with pytest.raises(ValueError,match='khusus cron'):story.run(api,'manual',request)


def test_public_job_endpoint_strips_cron_story_marker(monkeypatch):
    captured=[]
    def capture(request):
        captured.append(request)
        raise RuntimeError('sanitized')
    monkeypatch.setattr(api,'ensure_source_rights_attestation',capture)
    with pytest.raises(RuntimeError,match='sanitized'):
        api.create_job(api.ClipJobRequest(scheduled_original_story=True))
    assert captured[0].scheduled_original_story is False


def test_manual_automation_cannot_request_original_cron_story(configured,monkeypatch):
    class Thread:
        def __init__(self,**kwargs):pass
        def start(self):pass
    monkeypatch.setattr(api.threading,'Thread',Thread)
    monkeypatch.setattr(api,'auto_viral_active_run_id',None)
    run=api.create_and_start_auto_viral_campaign(api.scheduled_cron_life_story_request())
    assert run.trigger=='manual' and run.request.cron_original_story is False


@pytest.mark.parametrize('risk',['manual','landscape','short','missing_scenes','missing_camera'])
def test_illustrated_camera_recipe_is_exclusive_to_complete_cron_shorts(risk):
    args=dict(enabled=True,aspect='9:16',duration=100,
              scenes=[NS(narration=str(i)) for i in range(6)],camera_shots=6)
    assert story.illustrated_recipe_allowed(**args)
    if risk=='manual':args['enabled']=False
    if risk=='landscape':args['aspect']='16:9'
    if risk=='short':args['duration']=5
    if risk=='missing_scenes':args['scenes']=args['scenes'][:5]
    if risk=='missing_camera':args['camera_shots']=0
    assert not story.illustrated_recipe_allowed(**args)


def test_render_identity_and_thumbnail_stay_in_short_product(tmp_path):
    source=tmp_path/'long_animate_story.mp4';source.write_bytes(b'encoded video identity')
    source.with_name(source.stem+'_thumb.jpg').write_bytes(b'poster')
    data={}
    output=story.mark_render(source,data,'script','Judul cerita')
    assert output.name=='clip_01_cron_life_story.mp4' and output.read_bytes()==b'encoded video identity'
    assert output.with_name(output.stem+'_thumb.jpg').read_bytes()==b'poster'
    assert data['cron_life_story']['subject_motion_claimed'] is False
    assert not api.youtube_upload_is_long_form(NS(cron_daily_lane='scheduled_short',clip_name=output.name))
    with pytest.raises(ValueError):
        source.write_bytes(b'another render');story.mark_render(source,{},'script','title')


def test_original_cron_story_consumes_one_scheduled_short_and_no_long_slot():
    from daily_cron_plan import build_plan
    now=datetime.now(ZoneInfo('Asia/Jakarta'))
    job=dict(id='original',status='running',created_at=now.isoformat(),clips=[],request=dict(
        clip_mode='long_animate',scheduled_original_story=True,cron_daily_lane='scheduled_short',
        cron_production_day=story.today(now),top=1))
    result=build_plan(now=now,targets={'scheduled_short':24,'private_short':4,'long':2},
        jobs=[job],runs=[],uploads=[],attempts=[])
    assert result['lanes']['scheduled_short']['used']==1
    assert result['lanes']['long']['used']==result['lanes']['private_short']['used']==0
    assert result['total_target']==30


def test_render_provenance_must_match_the_owning_episode_script():
    data=valid_sidecar()
    data['cron_life_story']['script_sha256']=hashlib.sha256(b'episode one').hexdigest()
    assert story.preflight(data,'episode one') is None
    assert story.preflight(data,'another episode')


@pytest.mark.parametrize('key',['cron_life_story','final_qc','narration_quality','cold_open_contract',
    'dynamic_captions','asset_license_ledger'])
def test_malformed_sidecar_proof_is_a_hold_not_an_api_crash(key):
    data=valid_sidecar();data[key]=['untrusted']
    assert story.preflight(data)


def test_fiction_disclosure_is_bounded_idempotent_and_cron_only():
    text=story.disclose('Narasi ringkas. '*500,2200)
    assert len(text)<=2200 and 'Cerita ilustrasi fiksi RYUUNDY' in text
    assert story.disclose(text,2200)==text
    job=api.ClipJob(id='story',status='completed',created_at=api.now_iso(),updated_at=api.now_iso(),
        request=api.ClipJobRequest(scheduled_original_story=True))
    assert 'bantuan AI' in api.append_scheduled_source_credit('Caption',job,max_length=2200)
    job.request.scheduled_original_story=False
    assert api.append_scheduled_source_credit('Caption',job,max_length=2200)=='Caption'


def test_channel_recovery_policy_keeps_its_existing_short_duration_limits(configured,monkeypatch):
    monkeypatch.setattr(api,'youtube_channel_recovery_mode',lambda:True)
    assert api.scheduled_cron_life_story_request() is None
