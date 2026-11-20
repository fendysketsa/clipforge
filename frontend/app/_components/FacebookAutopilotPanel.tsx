"use client";
import { useCallback, useEffect, useState } from 'react';
import { ArrowUpRight, Check, CirclePause, Clock3, Loader2, Play, Radio, RefreshCw, Sparkles } from 'lucide-react';
import toast from 'react-hot-toast';
import { facebookRequest, type FacebookAutopilot } from '../../lib/facebook';

const labels: Record<string,string> = {
  reserved:'Menyiapkan ide',rendering:'Produksi',qc:'Pemeriksaan kualitas',qc_wait:'Menunggu bukti QC',
  ready:'Siap diterbitkan',queued:'Antrean upload',running:'Mengunggah',completed:'Terbit terkonfirmasi',
  needs_review:'Perlu pencocokan posting',failed:'Gagal sebelum publikasi',dropped:'Dilewati oleh QC',cancelled:'Dihentikan',
};
const date = (value?: string | null) => value ? new Date(value).toLocaleString('id-ID',{timeZone:'Asia/Jakarta',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})+' WIB' : 'Belum diperiksa';

function Ring({value,target,label,color}:{value:number;target:number;label:string;color:string}) {
  const complete=value>=target;
  return <div className="fbAutoMetric">
    <div className="fbAutoRing" style={{'--ring-color':color,'--ring-fill':`${Math.min(100,value/Math.max(1,target)*100)}%`} as React.CSSProperties}>
      <div><strong>{value}<span>/{target}</span></strong>{complete ? <Check size={14} aria-label="Sasaran tercapai"/> : null}</div>
    </div><strong>{label}</strong><span>Terbit terkonfirmasi</span>
  </div>;
}

export function FacebookAutopilotPanel() {
  const [data,setData]=useState<FacebookAutopilot|null>(null);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const load=useCallback(async()=>{
    try {setData(await facebookRequest<FacebookAutopilot>('facebook/autopilot'));setError('');}
    catch(reason){setError(reason instanceof Error?reason.message:'Progres otomatis belum tersedia.');}
  },[]);
  useEffect(()=>{void load();const timer=setInterval(()=>void load(),10_000);return()=>clearInterval(timer);},[load]);
  const toggle=async()=>{
    if(!data)return;setBusy(true);
    try {setData(await facebookRequest<FacebookAutopilot>('facebook/autopilot',{enabled:!data.config.enabled}));}
    catch(reason){toast.error(reason instanceof Error?reason.message:'Pengaturan belum tersimpan.');}
    finally{setBusy(false);}
  };
  const createOriginal=async()=>{
    setBusy(true);
    try {
      await facebookRequest('facebook/originals',{request_id:crypto.randomUUID().replaceAll('-','')});
      toast.success('Reel animasi baru dimulai. QC tetap wajib sebelum tayang.');
      await load();
    } catch(reason){toast.error(reason instanceof Error?reason.message:'Produksi belum dimulai.');}
    finally{setBusy(false);}
  };
  const active=data?.active;
  const enabled=data?.config.enabled;
  const running=!!(enabled&&data?.scheduler_running);
  const warning=active&&['qc_wait','needs_review'].includes(active.status);
  const stages=['Ide asli','Render','QC','Antrean','Terbit'];
  const current=active ? ({reserved:0,rendering:1,qc:2,qc_wait:2,ready:3,queued:3,running:3,completed:4,needs_review:3}[active.status]??0) : -1;
  const activity=data?.activity;
  const bonus=data?.bonus_priority;
  return <section className="fbAutopilot" aria-label="Progres otomatis Facebook Pro">
    <header className="fbAutoHeader"><div><span className="fbEyebrow"><Sparkles size={15}/> KHUSUS FB PRO</span>
      <h2>Anda pantau. Produksi berjalan.</h2><p>Tips digital keluarga · animasi objek 2D · narasi dan SFX</p></div>
      <div className="fbAutoControls"><span className={`fbAutoLive ${running?'isRunning':''}`}><Radio size={13}/>{running?'Otomasi aktif':data&&!enabled?'Dijeda':'Belum aktif'}</span>
        <button type="button" className="uiButton" disabled={!running||busy||!!active} onClick={()=>void createOriginal()}><Sparkles size={15}/> Buat Reel animasi</button>
        <button type="button" className="uiButton" disabled={!data||busy} onClick={()=>void toggle()}>{busy?<Loader2 size={15} className="spin"/>:enabled?<CirclePause size={15}/>:<Play size={15}/>} {enabled?'Jeda':'Lanjutkan'}</button></div>
    </header>
    {error?<p role="alert" className="fbAutoNotice">{error} Progres terakhir tetap ditampilkan bila tersedia.</p>:null}
    {bonus?.amount_usd!=null?<div className="fbAutoBonus"><div><span className="fbEyebrow">TARGET PERTAMA</span>
      <h3>{bonus.awarded?'Bonus terkonfirmasi':bonus.priority?`Kejar bonus US$${bonus.amount_usd}`:bonus.state==='await_facebook_confirmation'?'Menunggu konfirmasi bonus':'Periksa kembali status bonus'}</h3>
      <p>{bonus.priority?'Reel didahulukan dari cerita sampai jumlah publikasi awal cukup.':bonus.state==='await_facebook_confirmation'?'Jumlah publikasi lokal cukup; menunggu pengakuan dan tayangan yang memenuhi syarat di Facebook.':'Status bonus mengikuti bukti terakhir dari akun Facebook.'}</p></div>
      <div><strong>{bonus.facebook_completed_reels??'—'} / {bonus.required_reels??'—'}</strong><span>Reel diakui Facebook</span>
        <small>{bonus.locally_confirmed_reels} Reel dengan durasi terverifikasi</small></div>
      <p className="fbAutoBonusTerms">Minimal {bonus.minimum_duration_seconds??'—'} detik per Reel · {bonus.minimum_qualified_views??'—'} tayangan memenuhi syarat pada {bonus.minimum_reels_with_qualified_views??'—'} Reel. {bonus.period_label||''}<br/>{bonus.note}</p>
    </div>:null}
    <div className="fbAutoOverview">
      <div className="fbAutoPlan"><div className="fbAutoSectionTitle"><h3>Rencana produksi mingguan</h3><span>Senin–Minggu · WIB</span></div>
        {data?<div className="fbAutoMetrics"><Ring value={data.confirmed_posts} target={data.config.weekly_posts} label="Reel / postingan" color="#66baff"/>
          <Ring value={data.confirmed_stories} target={data.config.weekly_stories} label="Cerita" color="#f5b46e"/>
          <div className="fbAutoMetric fbAutoProduced"><strong>{data.produced}</strong><strong>Video diproduksi</strong><span>Belum tentu diterbitkan</span></div></div>:<p className="fbAutoHint">Memuat rencana dan hasil terkonfirmasi…</p>}
        <p className="fbAutoHint">Hitungan hasil ClipForge terpisah dari tugas dan bonus Facebook. Jeda minimal 3 jam; slot terlewat tidak ditumpuk sekaligus.</p>
      </div>
      <div className={`fbAutoWork ${warning?'hasWarning':''}`}><div className="fbAutoSectionTitle"><h3>{active?'Sedang dikerjakan':'Jadwal berikutnya'}</h3><Clock3 size={15}/></div>
        <strong className="fbAutoWorkTitle">{active?.title||(data?.next_slot?`${data.next_slot.kind==='story'?'Cerita':'Reel'} · ${date(data.next_slot.due_at)}`:'Menunggu status worker')}</strong>
        <p>{active?.message||data?.message||'Status akan diperbarui otomatis.'}</p>
        {active?<><div className="fbAutoProgress" role="progressbar" aria-label="Progres produksi" aria-valuenow={active.progress_percent||0} aria-valuemin={0} aria-valuemax={100}><span style={{width:`${Math.max(0,Math.min(100,active.progress_percent||0))}%`}}/></div>
          <span className="fbAutoWorkStatus">{labels[active.status]||active.status} · {active.progress_percent||0}%</span></>:null}
        <ol className="fbAutoStages">{stages.map((label,index)=><li key={label} className={index===current?'isCurrent':index<current?'isDone':''}><span>{index<current?<Check size={11}/>:index+1}</span>{label}</li>)}</ol>
        <small>Terakhir dipantau: {date(data?.heartbeat)}</small>
      </div>
    </div>
    <div className="fbAutoTasks"><div className="fbAutoSectionTitle"><div><h3>Tugas dari Facebook</h3><p>{activity?.period_label||'Menunggu pembacaan aktivitas akun'}</p></div>
      <button type="button" className="uiButton" disabled={busy||!data} onClick={()=>{
        setBusy(true);void facebookRequest('facebook/activity/check',{}).then(()=>toast.success('Pemeriksaan tugas dimulai.')).catch(reason=>toast.error(String(reason))).finally(()=>setBusy(false));
      }}><RefreshCw size={14}/> Periksa</button></div>
      {activity?.tasks.length?<div className="fbAutoTaskGrid">{activity.tasks.map(task=><div key={task.key}><div><span>{task.label}</span><strong>{task.completed}<small>/{task.target}</small></strong></div><progress value={Math.min(task.completed,task.target)} max={task.target}/></div>)}</div>:<p className="fbAutoHint">Angka tugas ditampilkan setelah Facebook memberikan data yang dapat dibaca.</p>}
      {activity?<p className="fbAutoHint">Dibaca {date(activity.checked_at)}. {activity.note}</p>:null}
      {data?.activity_error?<p className="fbAutoNotice">Pembaruan aktivitas tertunda. Bukti terakhir tetap disimpan.</p>:null}
    </div>
    {data?.runs.length?<div className="fbAutoRecent"><h3>Aktivitas produksi FB Pro</h3>{data.runs.slice(0,4).map(run=><div className="fbAutoRecentRow" key={run.key}><span>{run.kind==='story'?'CERITA':'REEL'}</span><div><strong>{run.title}</strong><small>{labels[run.status]||run.status} · {date(run.created_at)}</small></div>{run.video_url?<a href={run.video_url} target="_blank" rel="noopener noreferrer" aria-label={`Lihat ${run.title} di Facebook`}><ArrowUpRight size={17}/></a>:null}</div>)}</div>:null}
  </section>;
}
