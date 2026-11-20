import io
import json
from pathlib import Path

import pytest
import api
import clipper
import source_download as source

URL='https://www.youtube.com/watch?v=abcdefghijk'


@pytest.mark.parametrize('error,category',[
 ('Temporary failure in name resolution','dns'),('connection timed out','connect_timeout'),
 ('The read operation timed out','read_timeout'),('Connection reset by peer','connection_reset'),
 ('[Errno 101] Network is unreachable','network_unreachable'),('HTTP Error 503','server_error'),
 ('HTTP Error 429','rate_limited'),('HTTP Error 403 Forbidden','forbidden'),
 ('Sign in: operation timed out','authentication'),('Requested format is not available','format_unavailable'),
 ('private video connection timed out','source_unavailable')])
def test_transport_is_distinct_from_format_auth_and_source_policy(error,category):
 assert source.category(error)==category


def test_diagnostics_remove_credentials_headers_and_signed_urls():
 text=source.redact('failed https://user:pass@cdn.test/videoplayback?sig=secret&token=hidden Cookie: SID=credential')
 assert 'cdn.test/videoplayback' in text
 for secret in ['user:pass','sig=','secret','hidden','credential']:
  assert secret not in text


def test_network_retries_resume_same_partial_and_keep_recovery_evidence(monkeypatch,tmp_path):
 options=[];sleeps=[]
 class Download:
  def __init__(self,opts):self.opts=opts
  def __enter__(self):return self
  def __exit__(self,*_):return False
  def extract_info(self,url,download):
   options.append(self.opts)
   if len(options)==1:raise RuntimeError('Connection reset by peer')
   return {'id':'abcdefghijk'}
 monkeypatch.setattr(clipper,'YoutubeDL',Download)
 monkeypatch.setattr(clipper.time,'sleep',sleeps.append)
 result=clipper.extract_source_with_recovery(URL,{'outtmpl':'source.mp4','continuedl':True},download=True,
  diagnostic_dir=tmp_path,stage='video',strategy='default')
 assert result['id']=='abcdefghijk' and sleeps==[2]
 assert options[0]['outtmpl']==options[1]['outtmpl'] and all(o['continuedl'] for o in options)
 events=json.loads((tmp_path/'source_download_diagnostics.json').read_text())['events']
 assert events[0]['category']=='connection_reset' and events[-1]['recovered']


def test_all_compatibility_routes_share_one_transport_retry_budget(monkeypatch,tmp_path):
 calls=[];sleeps=[]
 class Download:
  def __init__(self,opts):calls.append(opts)
  def __enter__(self):return self
  def __exit__(self,*_):return False
  def extract_info(self,*args,**kwargs):raise RuntimeError('Temporary failure in name resolution')
 monkeypatch.setattr(clipper,'YoutubeDL',Download)
 monkeypatch.setattr(clipper.time,'sleep',sleeps.append)
 monkeypatch.setattr(clipper,'select_usable_source_media',lambda _:None)
 monkeypatch.setattr(clipper,'ffmpeg_path',lambda:'ffmpeg')
 with pytest.raises(clipper.UserFacingError,match='Pemulihan otomatis'):
  clipper.download_video(URL,tmp_path)
 assert len(calls)==7 and sleeps==[2,5]
 assert len({o['outtmpl'] for o in calls})==5


@pytest.mark.parametrize('error',['HTTP Error 403: Forbidden','Sign in to confirm you are not a bot','private video','HTTP Error 429'])
def test_recovery_does_not_retry_auth_denial_rights_or_rate_limit(monkeypatch,tmp_path,error):
 class Download:
  def __init__(self,opts):pass
  def __enter__(self):return self
  def __exit__(self,*_):return False
  def extract_info(self,*args,**kwargs):raise RuntimeError(error)
 monkeypatch.setattr(clipper,'YoutubeDL',Download)
 monkeypatch.setattr(clipper.time,'sleep',lambda *_:pytest.fail('No retry for this rejection'))
 with pytest.raises(RuntimeError,match=error):
  clipper.extract_source_with_recovery(URL,{},download=True,diagnostic_dir=tmp_path,stage='video',strategy='default')


def test_authenticated_retry_uses_fresh_cookie_stream_without_logging_values(monkeypatch,tmp_path):
 calls=[]
 class Download:
  def __init__(self,opts):self.cookies=opts['cookiefile'];calls.append(self.cookies)
  def __enter__(self):return self
  def __exit__(self,*_):self.cookies.close();return False
  def extract_info(self,*args,**kwargs):
   assert self.cookies.read()=='private-cookie-contents'
   if len(calls)==1:raise RuntimeError('Connection refused')
   return {'id':'abcdefghijk'}
 monkeypatch.setattr(clipper,'YoutubeDL',Download);monkeypatch.setattr(clipper.time,'sleep',lambda *_:None)
 clipper.extract_source_with_recovery(URL,{'cookiefile':io.StringIO('private-cookie-contents')},download=True,
  diagnostic_dir=tmp_path,stage='video',strategy='default')
 assert calls[0] is not calls[1]
 assert 'private-cookie-contents' not in (tmp_path/'source_download_diagnostics.json').read_text()


@pytest.fixture
def jobs(monkeypatch,tmp_path):
 monkeypatch.setattr(api,'jobs',{})
 monkeypatch.setattr(api,'job_processes',{})
 monkeypatch.setattr(api,'youtube_uploads',{})
 monkeypatch.setattr(api,'tiktok_uploads',{})
 monkeypatch.setattr(api,'auto_viral_runs',{})
 monkeypatch.setattr(api,'OUTPUTS_DIR',tmp_path/'outputs')
 monkeypatch.setattr(api,'SOURCE_USAGE_HISTORY_PATH',tmp_path/'data/history.json')
 monkeypatch.setattr(api,'save_jobs_unlocked',lambda:None)
 monkeypatch.setattr(api,'save_auto_viral_runs_unlocked',lambda:None)
 old=api.ClipJob(id='old',status='failed',created_at='2026-11-20T01:00:00Z',updated_at='2026-11-20T01:01:00Z',
  request=api.ClipJobRequest(url=URL),error='Koneksi server ke YouTube gagal saat mengunduh video.')
 new=api.ClipJob(id='new',status='completed',created_at='2026-11-20T02:00:00Z',updated_at='2026-11-20T02:03:00Z',
  request=api.ClipJobRequest(url=URL),clips=[api.ClipFile(name='clip.mp4',url='/outputs/new/clip.mp4',size_bytes=1)])
 api.jobs.update(old=old,new=new)
 return old,new,tmp_path


def test_evidence_survives_workspace_cleanup_and_requires_matching_source(jobs):
 old,new,root=jobs
 work=api.OUTPUTS_DIR/old.id/'source';work.mkdir(parents=True)
 source.record(work,URL,stage='video',strategy='default',attempt=1,error=RuntimeError('connection timed out'))
 api.preserve_source_download_evidence(old.id,api.OUTPUTS_DIR/old.id)
 assert api.jobs[old.id].download_diagnostics['evidence_retained']
 path=api.SOURCE_USAGE_HISTORY_PATH.parent/'source_download_diagnostics/old.json'
 assert path.exists()
 api.cleanup_failed_job_artifacts(api.OUTPUTS_DIR/old.id)
 assert path.exists() and not work.exists()
 assert json.loads(path.read_text())['source_id']=='abcdefghijk'


def test_successful_later_source_archives_empty_network_failure_and_preserves_proof(jobs):
 old,new,root=jobs
 assert api.cleanup_recovered_source_jobs_once()==1
 assert set(api.jobs)=={'new'}
 evidence=json.loads((root/'data/source_download_recoveries/old.json').read_text())
 assert evidence['original_job_id']=='old' and evidence['recovered_by_job_id']=='new'


@pytest.mark.parametrize('guard',['active','no_results','different_source','different_format','review','workspace','process','upload','qc_error'])
def test_cleanup_never_removes_unresolved_active_review_or_remote_work(jobs,guard):
 old,new,root=jobs
 if guard=='active':new.status='running'
 elif guard=='no_results':new.clips=[]
 elif guard=='different_source':new.request.url='https://youtu.be/lmnopqrstuv'
 elif guard=='different_format':new.request.clip_mode='highlight_5m'
 elif guard=='review':old.request.publication_review_required=True
 elif guard=='workspace':(api.OUTPUTS_DIR/old.id).mkdir(parents=True)
 elif guard=='process':api.job_processes[old.id]=object()
 elif guard=='upload':
  api.youtube_uploads['one']=api.YouTubeUploadJob(id='one',source_job_id=old.id,clip_url='/outputs/x.mp4',clip_name='x.mp4',
   status='failed',created_at=old.created_at,updated_at=old.updated_at,title='Original')
 elif guard=='qc_error':
  old.error='QC menolak sumber';old.download_diagnostics={'transport_failure':True,'recovered':True}
 assert api.cleanup_recovered_source_jobs_once()==0 and old.id in api.jobs


def test_success_cleanup_preserves_small_redacted_diagnostics(tmp_path):
 source.record(tmp_path,URL,stage='video',strategy='default',attempt=1,error=RuntimeError('Connection reset by peer'))
 media=tmp_path/'source.mp4';media.write_bytes(b'media')
 clipper.cleanup_intermediate(tmp_path,media)
 assert not media.exists() and (tmp_path/'source_download_diagnostics.json').exists()


def test_mismatched_source_cannot_supply_diagnostics_for_another_job(jobs):
 old,new,root=jobs;work=api.OUTPUTS_DIR/old.id;work.mkdir(parents=True)
 source.record(work,'https://youtu.be/lmnopqrstuv',stage='video',strategy='default',attempt=1,error=RuntimeError('timed out'))
 api.preserve_source_download_evidence(old.id,work)
 assert api.jobs[old.id].download_diagnostics is None


def test_active_child_and_checkpoint_consumer_protect_old_failure(jobs):
 old,new,root=jobs
 api.jobs['child']=new.model_copy(update={'id':'child','status':'running','repair_source_job_id':old.id})
 assert api.cleanup_recovered_source_jobs_once()==0
 api.jobs.pop('child')
 run=api.AutoViralRun(id='run',status='running',trigger='schedule',created_at=old.created_at,updated_at=old.updated_at,
  request=api.AutoViralRequest(),processed=[dict(job_id=old.id,status='running',job_status='failed')])
 api.auto_viral_runs['run']=run
 assert api.cleanup_recovered_source_jobs_once()==0


def test_terminal_campaign_reconciles_stale_queued_child_before_archiving(jobs):
 old,new,root=jobs
 run=api.AutoViralRun(id='run',status='failed',trigger='schedule',created_at=old.created_at,updated_at=old.updated_at,
  request=api.AutoViralRequest(),processed=[dict(job_id=old.id,status='running',job_status='queued',youtube_upload_ids=['keep-this'])])
 api.auto_viral_runs['run']=run
 assert api.cleanup_recovered_source_jobs_once()==1
 repaired=api.auto_viral_runs['run'];item=repaired.processed[0]
 assert item['status']==item['job_status']=='failed' and item['clip_count']==0
 assert item['youtube_upload_ids']==['keep-this']
 assert item['source_download_original_state']=={'status':'running','job_status':'queued'}
 assert repaired.updated_at==run.updated_at and repaired.status=='failed'


def test_checkpoint_write_failure_retains_source_card_and_original_state(jobs,monkeypatch):
 old,new,root=jobs
 run=api.AutoViralRun(id='run',status='failed',trigger='schedule',created_at=old.created_at,updated_at=old.updated_at,
  request=api.AutoViralRequest(),processed=[dict(job_id=old.id,status='running',job_status='queued')])
 api.auto_viral_runs['run']=run
 def unavailable():raise OSError('disk unavailable')
 monkeypatch.setattr(api,'save_auto_viral_runs_unlocked',unavailable)
 assert api.cleanup_recovered_source_jobs_once()==0
 assert old.id in api.jobs and api.auto_viral_runs['run'].processed[0]['job_status']=='queued'


def test_quiet_downloader_logger_retains_underlying_error_without_leaking_tokens(monkeypatch,tmp_path,capsys):
 class Download:
  def __init__(self,opts):self.logger=opts['logger']
  def __enter__(self):return self
  def __exit__(self,*_):return False
  def extract_info(self,*args,**kwargs):
   self.logger.error('Low-level CDN error https://user:secret@cdn.test/videoplayback?token=private-signature')
   raise RuntimeError('ffmpeg exited with code 1')
 monkeypatch.setattr(clipper,'YoutubeDL',Download)
 with pytest.raises(RuntimeError):
  clipper.extract_source_with_recovery(URL,{},download=True,diagnostic_dir=tmp_path,stage='video',strategy='default')
 diagnostic=(tmp_path/'source_download_diagnostics.json').read_text()
 assert 'Low-level CDN error' in diagnostic
 assert 'secret' not in diagnostic and 'private-signature' not in diagnostic
 assert 'Low-level CDN error' not in capsys.readouterr().out


def test_archived_recovery_can_reconcile_terminal_checkpoint_after_card_is_gone(jobs):
 old,new,root=jobs
 assert api.cleanup_recovered_source_jobs_once()==1
 run=api.AutoViralRun(id='run',status='failed',trigger='schedule',created_at=old.created_at,updated_at=old.updated_at,
  request=api.AutoViralRequest(),processed=[dict(job_id=old.id,status='running',job_status='queued')])
 api.auto_viral_runs['run']=run
 assert api.reconcile_terminal_source_download_checkpoints_once()==1
 assert api.auto_viral_runs['run'].processed[0]['job_status']=='failed'
 assert api.archived_source_download_failure('../old') is None


def test_card_write_failure_restores_job_and_private_state(jobs, monkeypatch):
 old,new,root=jobs
 monkeypatch.setattr(api,'job_secrets',{'old':{'cookie':'preserved'}})
 def unavailable():raise OSError('disk unavailable')
 monkeypatch.setattr(api,'save_jobs_unlocked',unavailable)
 assert api.cleanup_recovered_source_jobs_once()==0
 assert api.jobs['old'] is old and api.job_secrets['old']=={'cookie':'preserved'}
 assert (root/'data/source_download_recoveries/old.json').exists()


def test_diagnostic_write_failure_does_not_replace_original_transport_error(monkeypatch,tmp_path):
 class Download:
  def __init__(self,opts):pass
  def __enter__(self):return self
  def __exit__(self,*_):return False
  def extract_info(self,*args,**kwargs):raise RuntimeError('Connection reset by peer')
 def unavailable(*args,**kwargs):raise OSError('disk unavailable')
 monkeypatch.setattr(clipper,'YoutubeDL',Download)
 monkeypatch.setattr(source,'record',unavailable)
 monkeypatch.setattr(clipper.time,'sleep',lambda *_:None)
 with pytest.raises(RuntimeError,match='Connection reset by peer'):
  clipper.extract_source_with_recovery(URL,{},download=True,diagnostic_dir=tmp_path,stage='video',strategy='default')
