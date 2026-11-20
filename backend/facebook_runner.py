"""One persisted Facebook production lane, owned by normal backend startup."""
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import shutil
import uuid

import facebook_activity as activity
import facebook_autopilot as policy
import facebook_originals as originals
import facebook_creative as creative
import facebook_browser as browser
import facebook_monetization as monetization


def now():return datetime.now(timezone.utc).isoformat()


def age(value):
    try:return (datetime.now(timezone.utc)-datetime.fromisoformat(value)).total_seconds()
    except (ValueError,TypeError):return float('inf')


class Runner:
    def __init__(self,api,store,session_check,enqueue,retry,check_monetization,reconcile=None,cleanup=None):
        self.api,self.store,self.session_check=api,store,session_check
        self.enqueue,self.retry,self.check_monetization=enqueue,retry,check_monetization
        self.reconcile=reconcile
        self.cleanup=cleanup
        self.stop=threading.Event();self.lock=threading.Lock();self.activity_lock=threading.Lock();self.thread=None
        self.start_lock=threading.Lock()

    def state(self):
        data=self.store()
        with data.lock:
            result=policy.snapshot(data.data.get('autopilot'),data.data.get('autopilot_runs',{}),
                list(data.data['uploads'].values()),data.data.get('activity'),monetization=data.data.get('monetization'))
            result.update(scheduler_running=bool(self.thread and self.thread.is_alive()),
                series_catalog=originals.series_catalogue(),
                heartbeat=data.data.get('autopilot_heartbeat'),message=data.data.get('autopilot_message'),
                activity_error=data.data.get('activity_error'))
            return result

    def update(self,key,**values):
        data=self.store()
        with data.lock:
            data.data['autopilot_runs'][key].update(**values,updated_at=now())
            data.data['autopilot_heartbeat']=now()
            data.save()

    def note(self,message):
        data=self.store()
        with data.lock:
            changed=data.data.get('autopilot_message')!=message
            data.data.update(autopilot_message=message,autopilot_heartbeat=now())
            if changed:data.save()

    def enabled(self):
        data=self.store()
        with data.lock:return policy.config(data.data.get('autopilot'))['enabled'] and not self.stop.is_set()

    def request_original(self,request_id,topic=None,series=None):
        """Reserve one new source; repeated HTTP requests keep the same identity."""
        key='requested:'+request_id
        data=self.store()
        if not self.lock.acquire(blocking=False):
            raise ValueError('Worker Facebook sedang bekerja; tunggu proses yang aktif.')
        try:
            with data.lock:
                rows=data.data.setdefault('autopilot_runs',{})
                if key in rows:return dict(rows[key])
                if not self.enabled():raise ValueError('Aktifkan otomasi Facebook terlebih dahulu.')
                if any(r.get('status') in policy.ACTIVE for r in rows.values()):
                    raise ValueError('Masih ada produksi atau unggahan yang harus diselesaikan.')
                with api_job_capacity(self.api) as available:
                    if not available:raise ValueError('Menunggu kapasitas produksi; maksimal dua proses bersamaan.')
                snapshot=data.data.get('monetization') or {}
                if any((snapshot.get(k) or {}).get('state')=='restricted' for k in ('program','policy')):
                    raise ValueError('Pembatasan Facebook masih aktif; publikasi ditahan.')
                if any(age(u.get('created_at'))<3*3600 for u in data.data['uploads'].values()):
                    raise ValueError('Jeda tiga jam antarunggahan Facebook belum selesai.')
                series=series or policy.config(data.data.get('autopilot'))['series']
                available=originals.topic_keys(series)
                if topic is not None and topic not in available:
                    raise ValueError('Topik animasi tidak tersedia.')
                seed=key
                if topic is None:
                    recent={r.get('topic') for r in sorted(rows.values(),key=lambda r:r.get('created_at',''))[-7:]}
                    topic=creative.choose_topic(seed,available,recent)
                plan=originals.plan(seed,'reel',topic=topic,series=series)
                current=policy.local_now();start,end=policy.week(current)
                row=dict(key=key,kind='reel',due_at=current.isoformat(),day=current.date().isoformat(),
                    week_start=start,week_end=end,due=True,content_seed=seed,title=plan['title'],topic=topic,series=series,
                    status='reserved',job_id=uuid.uuid4().hex,created_at=now(),updated_at=now(),
                    progress_percent=0,message='Reel animasi baru dicatat; menunggu worker Facebook.')
                rows[key]=row;data.save()
                return dict(row)
        finally:self.lock.release()

    def process_requested(self,key):
        # Both this action and the cron tick own the same lock. A request
        # that lost the race to cron must not start a second render or Post.
        with self.lock:
            data=self.store()
            with data.lock:row=dict(data.data.get('autopilot_runs',{}).get(key) or {})
            if row.get('status')=='reserved' and not row.get('attempts'):
                self.process(key)

    def consume_requested(self):
        """Normal startup consumes durable operator requests exactly once."""
        if not self.enabled():return
        folder=self.api.JOBS_PATH.parent/'facebook_requests'
        for path in sorted(folder.glob('*.json')):
            # Ignore unrelated files. The filename is the idempotency key,
            # never an arbitrary path to media or an upload destination.
            try:
                if len(path.stem)!=32 or uuid.UUID(path.stem).hex!=path.stem:continue
                request=json.loads(path.read_text())
                row=self.request_original(path.stem,request.get('topic'),request.get('series'))
            except ValueError as exc:
                self.note(str(exc));return
            # Reservation is already durable. If interrupted here, tick()
            # resumes the same row instead of creating another source/Post.
            path.unlink(missing_ok=True)
            self.process_requested(row['key'])
            return

    def refresh_activity(self):
        data=self.store()
        if not self.activity_lock.acquire(blocking=False):return
        try:
            with data.lock:
                profile=(data.data.get('session') or {}).get('verified_profile_id','')
                data.data['activity_attempt_at']=now();data.save()
            with self.api.social_upload_turn():result=activity.collect(profile)
            with data.lock:data.data.update(activity=result,activity_error=None);data.save()
            return result
        except Exception as exc:
            with data.lock:data.data['activity_error']=originals.qc.safe_error_detail(exc);data.save()
        finally:self.activity_lock.release()

    def synchronize(self):
        data=self.store()
        with data.lock:
            changed='autopilot_runs' not in data.data
            for key,row in data.data.setdefault('autopilot_runs',{}).items():
                upload=data.data['uploads'].get(row.get('upload_id'))
                if not upload:continue
                values=dict(status=upload['status'],message=upload.get('message'),
                    upload_confirmed=upload.get('upload_confirmed') is True,video_url=upload.get('video_url'))
                if values['upload_confirmed'] and row.get('upload_confirmed') is not True:
                    data.data['autopilot_monetization_attempt_at']=None
                    data.data['activity_attempt_at']=None
                if any(row.get(key)!=value for key,value in values.items()):row.update(values);changed=True
            if changed:data.save()

    def process(self,key):
        api=self.api;data=self.store()
        with data.lock:row=dict(data.data['autopilot_runs'][key])
        job_id=row['job_id'];folder=api.OUTPUTS_DIR/'facebook_autopilot'/job_id
        clip_url=f'/outputs/facebook_autopilot/{job_id}/facebook_original.mp4'
        media=folder/'facebook_original.mp4'
        self.update(key,attempts=row.get('attempts',0)+1)
        def progress(percent,stage,message):
            if job_id in api.cancelled_job_ids or not self.enabled():
                raise InterruptedError('Produksi Facebook dijeda atau dihentikan.')
            api.set_job(job_id,status='running',progress_percent=percent,progress_stage=stage,progress_detail=message)
            self.update(key,status='rendering',progress_percent=percent,message=message)
        try:
            with api.jobs_lock:
                job=api.jobs.get(job_id)
                if not job:
                    request=api.ClipJobRequest(target_platform='facebook',facebook_niche='digital_simple',
                        facebook_autopilot_key=key,facebook_source_rights='owned',
                        confirm_source_rights=True,source_rights_evidence=
                        'Naskah dan animasi demonstrasi diproduksi asli di ClipForge; narasi neural memakai layanan proyek, tanpa footage atau musik pihak lain.',
                        max_duration=55,auto_upload_youtube=False)
                    api.jobs[job_id]=api.ClipJob(id=job_id,status='queued',request=request,
                        created_at=row['created_at'],updated_at=now(),source_title=row['title'],source_uploader='Produksi asli RYUUNDY')
                    api.save_jobs_unlocked()
            valid_existing=False
            if media.is_file() and media.with_suffix('.json').is_file():
                try:
                    meta=json.loads(media.with_suffix('.json').read_text())
                    valid_existing=meta.get('media_sha256')==originals.qc.sha256(media)
                except (OSError,ValueError):pass
            if not valid_existing:
                source_plan=row.get('authored_plan')
                if not source_plan:
                    with data.lock:previous=[r['script_sha256'] for r in data.data['autopilot_runs'].values() if r.get('script_sha256')]
                    source_plan=originals.author(originals.plan(row['content_seed'],row['kind'],topic=row.get('topic'),series=row.get('series','digital')),previous)
                    self.update(key,authored_plan=source_plan,script_sha256=source_plan['script_sha256'],title=source_plan['title'])
                if row.get('repair_attempted'):source_plan.update(repair_attempted=True,caption_font_size=58)
                media=originals.render(source_plan,folder,progress)
            sidecar=json.loads(media.with_suffix('.json').read_text())
            if job_id in api.cancelled_job_ids:raise InterruptedError('Produksi Facebook dibatalkan.')
            clip=api.ClipFile(name=media.name,url=clip_url,size_bytes=media.stat().st_size,
                title=sidecar['title'],thumbnail_url=clip_url.removesuffix('.mp4')+'_thumb.jpg',
                social_caption=sidecar['facebook']['caption'],narrative_arc_complete=True,
                context_recut_required=False,religious_review_required=False,is_correct=False,
                output_resolution='1080x1920',render_qc_passed=True)
            api.set_job(job_id,status='completed',clips=[clip],finished_at=now(),progress_percent=100,
                progress_stage='complete',progress_detail='Reel asli selesai; menunggu QC independen.',error=None)
            self.update(key,status='qc',progress_percent=90,message='Memeriksa visual, suara, konteks dan caption.',last_qc_at=now(),rendered_at=now())
            if originals.automatic_pass(media,job_id,clip_url):
                record=json.loads(media.with_suffix('.auto-qc.json').read_text())
            else:
                record=originals.audit(media,job_id,clip_url,repair_attempted=row.get('repair_attempted') is True)
            decision=record.get('audit') or {}
            if decision.get('decision')=='REPAIR_ONCE' and not row.get('repair_attempted'):
                instructions=' '.join(decision.get('repair_instructions',[])).casefold()
                if ('caption' in instructions or 'subtitle' in instructions) and any(
                        word in instructions for word in ('larger','increase','too small','lebih besar','terlalu kecil')):
                    self.update(key,repair_attempted=True,repair_instructions=decision['repair_instructions'])
                    source_plan=json.loads((folder/'source-plan.json').read_text())
                    source_plan.update(repair_attempted=True,caption_font_size=58)
                    media=originals.render(source_plan,folder,progress)
                    clip=clip.model_copy(update={'size_bytes':media.stat().st_size})
                    api.set_job(job_id,status='completed',clips=[clip],progress_percent=100,finished_at=now())
                    record=originals.audit(media,job_id,clip_url,repair_attempted=True)
                else:
                    record['audit']=originals.qc._decision(dict(source_job_id=job_id,source_clip_url=clip_url),
                        gates=decision['hard_gates'],checks=decision['ai_checks'],evidence=decision['evidence']+
                        ['Requested repair is outside the bounded generated-caption repair; source dropped.'])
            media.with_suffix('.auto-qc.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
            audit=record.get('audit') or {}
            if audit.get('decision')!='PASS_UPLOAD' or not originals.automatic_pass(media,job_id,clip_url):
                dropped=audit.get('decision')=='DROP_SOURCE'
                self.update(key,status='dropped' if dropped else 'qc_wait',progress_percent=90,
                    message=record.get('message') or '; '.join(audit.get('evidence',[]))[-500:] or 'QC belum memberikan izin upload.',
                    qc_decision=audit.get('decision'),qc_evidence=audit.get('evidence',[]),
                    qc_provider_http_status=record.get('provider_http_status'),
                    qc_provider_error=record.get('provider_error'))
                if dropped:
                    api.set_job(job_id,status='failed',clips=[],error='QC menolak sumber; video ditarik dari hasil upload.')
                    if folder.resolve().is_relative_to((api.OUTPUTS_DIR/'facebook_autopilot').resolve()) and folder.name==job_id:
                        shutil.rmtree(folder)
                return
            self.update(key,status='ready',progress_percent=100,message='QC lulus; menyiapkan publikasi Facebook.')
            if not self.enabled() or job_id in api.cancelled_job_ids:return
            self.session_check()
            result=self.enqueue(job_id,clip_url,row['kind'])
            self.update(key,status=result['status'],upload_id=result['id'],message=result.get('message'))
        except InterruptedError as exc:
            api.set_job(job_id,status='cancelled',finished_at=now(),error=str(exc))
            self.update(key,status='cancelled',message=str(exc))
        except Exception as exc:
            message=originals.qc.safe_error_detail(exc)
            # Keep a successfully rendered file for a pre-submission retry.
            with api.jobs_lock:completed=bool(api.jobs.get(job_id) and api.jobs[job_id].status=='completed')
            if not completed:api.set_job(job_id,status='failed',finished_at=now(),error=message)
            self.update(key,status='dropped' if isinstance(exc,originals.SourceRejected) else 'failed',message=message)

    def tick(self):
        if not self.lock.acquire(blocking=False):return
        try:
            self.synchronize()
            if self.cleanup:self.cleanup()
            if not self.enabled():self.note('Otomasi Facebook dijeda.');return
            data=self.store()
            with data.lock:
                session=dict(data.data.get('session') or {})
                runs={key:dict(row) for key,row in data.data['autopilot_runs'].items()}
            # Retry only known pre-Post failures, never ambiguous submissions.
            for row in runs.values():
                if row.get('upload_id'):
                    with data.lock:upload=dict(data.data['uploads'].get(row['upload_id']) or {})
                    candidates=([upload['remote_story_url']] if upload.get('kind')=='story' and upload.get('remote_story_url')
                                else upload.get('candidate_video_urls',[]))
                    if (self.reconcile and upload.get('status')=='needs_review'
                            and (candidates or upload.get('existing_reel_urls') is not None)
                            and age(row.get('last_reconcile_at'))>=600):
                        self.update(row['key'],last_reconcile_at=now())
                        if upload.get('kind','reel')=='reel' and upload.get('existing_reel_urls') is not None:
                            try:
                                with self.api.social_upload_turn(),browser.connection() as context:
                                    recent=browser.recent_reel_urls(context,upload['profile_id'])
                                baseline=set(upload['existing_reel_urls'])
                                discovered=[url for url in recent if url not in baseline]
                                candidates=list(dict.fromkeys(discovered+list(candidates)))
                                data.update(upload['id'],candidate_video_urls=candidates[:12])
                            except Exception:pass
                        for url in candidates[:3]:
                            try:self.reconcile(upload['id'],url);break
                            except Exception:continue
                        return
                    if (upload.get('status')=='failed' and not upload.get('submission_started')
                            and not upload.get('video_url') and upload.get('attempts',1)<3
                            and age(upload.get('finished_at'))>=1800):
                        self.retry(row['upload_id']);return
                elif row.get('status') in {'reserved','rendering','qc','ready'} or (
                        row.get('status')=='qc_wait' and age(row.get('last_qc_at'))>=3600) or (
                        row.get('status')=='failed' and row.get('attempts',1)<3 and age(row.get('updated_at'))>=1800):
                    self.process(row['key']);return
            if age(session.get('checked_at'))>=600 or not session.get('account_verified'):
                # Failed identity checks back off instead of opening tabs every tick.
                if age(session.get('checked_at'))<300:
                    self.note(session.get('message','Periksa login Facebook.'));return
                session=self.session_check()
            if not session.get('account_verified'):
                self.note(session.get('message','Login Facebook diperlukan.'));return
            with data.lock:
                last_activity=data.data.get('activity_attempt_at')
                last_check=data.data.get('autopilot_monetization_attempt_at')
                bonus=policy.bonus_plan(data.data.get('monetization'),list(data.data['uploads'].values()))
            if age(last_activity)>=6*3600:
                with data.lock:data.data['activity_attempt_at']=now();data.save()
                try:self.refresh_activity()
                except Exception as exc:
                    with data.lock:data.data['activity_error']=originals.qc.safe_error_detail(exc);data.save()
            interval=1800 if bonus['state'] in {'produce_reels','await_facebook_confirmation'} else 6*3600
            if age(last_check)>=interval:
                with data.lock:data.data['autopilot_monetization_attempt_at']=now();data.save()
                self.check_monetization()
            with data.lock:
                snapshot=data.data.get('monetization') or {}
                if (snapshot.get('program') or {}).get('state')=='restricted' or (snapshot.get('policy') or {}).get('state')=='restricted':
                    self.note('Facebook menunjukkan pembatasan; publikasi otomatis ditahan.');return
                slot=policy.eligible(datetime.now(timezone.utc),data.data.get('autopilot'),runs,
                    list(data.data['uploads'].values()),monetization=snapshot)
            if not slot:
                self.note('Menunggu jadwal berikutnya atau hasil proses yang sedang berjalan.');return
            with api_job_capacity(self.api) as available:
                if not available:self.note('Menunggu kapasitas produksi; maksimal dua proses bersamaan.');return
                recent={r.get('topic') for r in sorted(runs.values(),key=lambda r:r.get('created_at',''))[-7:]}
                series=policy.config(data.data.get('autopilot'))['series']
                topic=creative.choose_topic(slot['content_seed'],originals.topic_keys(series),recent)
                content=originals.plan(slot['content_seed'],slot['kind'],topic=topic,series=series)
                with data.lock:
                    if slot['key'] in data.data['autopilot_runs']:return
                    row={**slot,'title':content['title'],'topic':content['topic'],'series':series,'status':'reserved','job_id':uuid.uuid4().hex,
                         'created_at':now(),'updated_at':now(),'progress_percent':0,'message':'Slot Facebook dicatat; menyiapkan demonstrasi asli.'}
                    data.data['autopilot_runs'][slot['key']]=row;data.save()
                self.process(slot['key'])
        finally:self.lock.release()

    def loop(self):
        while not self.stop.is_set():
            try:
                self.consume_requested()
                self.tick()
            except Exception as exc:self.note('Otomasi menunggu pemulihan: '+originals.qc.safe_error_detail(exc))
            self.stop.wait(30)

    def start(self):
        with self.start_lock:
            if self.thread and self.thread.is_alive():
                return False
            data=self.store()
            with data.lock:
                data.data.setdefault('autopilot',policy.config())
                data.data.setdefault('autopilot_runs',{})
                data.save()
            self.stop.clear();self.thread=threading.Thread(target=self.loop,daemon=True,name='facebook-autopilot');self.thread.start()
            return True


from contextlib import contextmanager

@contextmanager
def api_job_capacity(api):
    # Called before registering the new job, without holding this lock during IO.
    with api.jobs_lock:available=sum(job.status in {'queued','running'} for job in api.jobs.values())<2
    yield available
