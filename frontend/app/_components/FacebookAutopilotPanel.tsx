"use client";
import { useCallback, useEffect, useState } from 'react';
import { Check, CirclePause, Clock3, Loader2, PenLine, Play, Radio, Sparkles } from 'lucide-react';
import toast from 'react-hot-toast';
import { facebookRequest, type FacebookAutopilot } from '../../lib/facebook';

const labels: Record<string,string> = {
  reserved:'Menyiapkan ide',rendering:'Produksi',qc:'Pemeriksaan kualitas',qc_wait:'Menunggu bukti QC',
  ready:'Siap diterbitkan',queued:'Antrean upload',running:'Mengunggah',completed:'Terbit terkonfirmasi',
  needs_review:'Perlu pencocokan posting',failed:'Gagal sebelum publikasi',dropped:'Dilewati oleh QC',cancelled:'Dihentikan',
};
const date = (value?: string | null) => value ? new Date(value).toLocaleString('id-ID',{timeZone:'Asia/Jakarta',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})+' WIB' : 'Belum diperiksa';

export function FacebookAutopilotPanel() {
  const [data,setData]=useState<FacebookAutopilot|null>(null);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const [series,setSeries]=useState('');
  const [topic,setTopic]=useState('');
  const [customTopic,setCustomTopic]=useState('');
  const [storyStyle,setStoryStyle]=useState('');
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
      await facebookRequest('facebook/originals',{request_id:crypto.randomUUID().replaceAll('-',''),
        series:series||data?.config.series||'digital',topic:topic||null});
      toast.success('Reel animasi baru dimulai. QC tetap wajib sebelum tayang.');
      await load();
    } catch(reason){toast.error(reason instanceof Error?reason.message:'Produksi belum dimulai.');}
    finally{setBusy(false);}
  };
  const createFromTopic=async()=>{
    const text=customTopic.trim();
    if(text.length<4){toast.error('Tulis topik minimal empat karakter.');return;}
    setBusy(true);
    try {
      await facebookRequest('facebook/originals',{request_id:crypto.randomUUID().replaceAll('-',''),
        series:'topik',custom_topic:text,style:storyStyle||null});
      toast.success('Video topik baru dimulai. QC tetap wajib sebelum tayang.');
      setCustomTopic('');
      await load();
    } catch(reason){toast.error(reason instanceof Error?reason.message:'Produksi belum dimulai.');}
    finally{setBusy(false);}
  };
  const saveSeries=async()=>{
    if(!data)return;setBusy(true);
    try{
      setData(await facebookRequest<FacebookAutopilot>('facebook/autopilot',{
        enabled:data.config.enabled,series:series||data.config.series||'digital'}));
      toast.success('Tema untuk produksi terjadwal disimpan.');
    }catch(reason){toast.error(reason instanceof Error?reason.message:'Tema belum tersimpan.');}
    finally{setBusy(false);}
  };
  const selectedSeries=series||data?.config.series||'digital';
  const catalogue=data?.series_catalog||[];
  const selected=catalogue.find(item=>item.key===selectedSeries);
  const bank=data?.topic_bank||[];
  const storyStyles=data?.story_styles||[];
  const active=data?.active;
  const enabled=data?.config.enabled;
  const running=!!(enabled&&data?.scheduler_running);
  const warning=active&&['qc_wait','needs_review'].includes(active.status);
  const stages=['Ide asli','Render','QC','Antrean','Terbit'];
  const current=active ? ({reserved:0,rendering:1,qc:2,qc_wait:2,ready:3,queued:3,running:3,completed:4,needs_review:3}[active.status]??0) : -1;
  return <section className="fbAutopilot" aria-label="Kontrol produksi Facebook">
    <header className="fbAutoHeader"><div><span className="fbEyebrow"><Sparkles size={15}/> PRODUKSI OTOMATIS</span>
      <h2>Dari ide sampai tayang.</h2><p>Reel original dibuat, diperiksa, lalu diunggah sesuai jadwal.</p></div>
      <span className={`fbAutoLive ${running?'isRunning':''}`}><Radio size={13}/>{running?'Otomasi aktif':data&&!enabled?'Dijeda':'Belum aktif'}</span>
    </header>
    <div className="fbSeriesPicker">
      <div className="fbFormPair"><label>Tema animasi<select aria-label="Tema animasi" value={selectedSeries} disabled={busy||!catalogue.length} onChange={event=>{setSeries(event.target.value);setTopic('');}}>
        {catalogue.length?catalogue.map(item=><option key={item.key} value={item.key}>{item.label}</option>):<option value="digital">Memuat pilihan tema…</option>}</select></label>
        <label>Topik video<select aria-label="Topik video" value={topic} disabled={busy||!selected} onChange={event=>setTopic(event.target.value)}><option value="">Pilih otomatis</option>{selected?.topics.map(item=><option value={item.key} key={item.key}>{item.title}</option>)}</select></label></div>
      {selected?<p>{selected.description} <span>{selected.audience}.</span></p>:null}
      <button type="button" className="uiButton" disabled={busy||!data||!selected||selectedSeries===(data.config.series||'digital')} onClick={()=>void saveSeries()}>Gunakan tema untuk jadwal</button>
    </div>
    <div className="fbTopicComposer">
      <header><span className="fbTopicIcon"><PenLine size={16}/></span><div><strong>Topik bebas</strong><small>Ketik topik apa saja. Gaya cerita dipilih otomatis supaya hasil tidak monoton.</small></div></header>
      <textarea aria-label="Topik video bebas" value={customTopic} maxLength={140} rows={2}
        placeholder="Contoh: beda zaman cara guru menangani murid lupa PR"
        onChange={event=>setCustomTopic(event.target.value)}/>
      <div className="fbFormPair">
        <label>Gaya cerita<select aria-label="Gaya cerita" value={storyStyle} disabled={busy} onChange={event=>setStoryStyle(event.target.value)}>
          <option value="">Pilih otomatis</option>
          {storyStyles.map(item=><option key={item.key} value={item.key}>{item.label}</option>)}</select></label>
        <button type="button" className="uiButton uiButton--primary" disabled={!running||busy||!!active||customTopic.trim().length<4} onClick={()=>void createFromTopic()}>
          {busy?<Loader2 size={15} className="spin"/>:<PenLine size={15}/>} Buat video sekarang
        </button>
      </div>
      {bank.length?<div className="fbTopicChips" aria-label="Ide topik otomatis">
        {bank.slice(0,8).map(item=><button type="button" key={item.text} disabled={busy} onClick={()=>{setCustomTopic(item.text);setStoryStyle(item.style);}}>{item.text}</button>)}
      </div>:null}
    </div>
    <div className="fbAutoControls">
      <button type="button" className="uiButton uiButton--primary" disabled={!running||busy||!!active||!selected} onClick={()=>void createOriginal()}><Sparkles size={16}/> Buat Reel baru</button>
      <button type="button" className="uiButton" disabled={!data||busy} onClick={()=>void toggle()}>{busy?<Loader2 size={15} className="spin"/>:enabled?<CirclePause size={15}/>:<Play size={15}/>} {enabled?'Jeda otomasi':'Lanjutkan otomasi'}</button>
    </div>
    {error?<p role="alert" className="fbAutoNotice">{error} Progres terakhir tetap ditampilkan bila tersedia.</p>:null}
    <div className="fbAutoOverview">
      <div className={`fbAutoWork ${warning?'hasWarning':''}`}><div className="fbAutoSectionTitle"><h3>{active?'Sedang dikerjakan':'Jadwal berikutnya'}</h3><Clock3 size={15}/></div>
        <strong className="fbAutoWorkTitle">{active?.title||(data?.next_slot?`${data.next_slot.kind==='story'?'Cerita':'Reel'} · ${date(data.next_slot.due_at)}`:'Menunggu status worker')}</strong>
        <p>{active?.message||data?.message||'Status akan diperbarui otomatis.'}</p>
        {active?<><div className="fbAutoProgress" role="progressbar" aria-label="Progres produksi" aria-valuenow={active.progress_percent||0} aria-valuemin={0} aria-valuemax={100}><span style={{width:`${Math.max(0,Math.min(100,active.progress_percent||0))}%`}}/></div>
          <span className="fbAutoWorkStatus">{labels[active.status]||active.status} · {active.progress_percent||0}%</span></>:null}
        <ol className="fbAutoStages">{stages.map((label,index)=><li key={label} className={index===current?'isCurrent':index<current?'isDone':''}><span>{index<current?<Check size={11}/>:index+1}</span>{label}</li>)}</ol>
        <small>Terakhir dipantau: {date(data?.heartbeat)}</small>
      </div>
    </div>
    <footer className="fbAutoSchedule"><Clock3 size={15}/><span>{data ? `${data.config.weekly_posts} Reel · ${data.config.weekly_stories} Cerita per minggu` : 'Memuat jadwal…'}</span><span>{catalogue.find(item=>item.key===(data?.config.series||'digital'))?.label} · WIB</span></footer>
  </section>;
}
