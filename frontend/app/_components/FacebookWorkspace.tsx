"use client";
import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { CheckCircle2, Clapperboard, Copy, Download, Facebook, Loader2, RefreshCw, ShieldCheck, Upload } from 'lucide-react';
import toast from 'react-hot-toast';
import { cancelJob, updateJobClipStatus, uploadVideo } from '../../lib/apiClient';
import { facebookRequest, mediaUrl, type FacebookConfig, type FacebookProduction, type FacebookQC, type FacebookSession, type FacebookUpload } from '../../lib/facebook';
import { FacebookConnection } from './FacebookConnection';

const statusLabel: Record<string,string> = {queued:'Menunggu', running:'Diproses', completed:'Selesai', failed:'Gagal', cancelled:'Dibatalkan', needs_review:'Periksa hasil posting'};

export function FacebookWorkspace() {
  const [config, setConfig] = useState<FacebookConfig | null>(null);
  const [productions, setProductions] = useState<FacebookProduction[]>([]);
  const [uploads, setUploads] = useState<FacebookUpload[]>([]);
  const [session, setSession] = useState<FacebookSession>({});
  const [error, setError] = useState('');
  const [niche, setNiche] = useState('tech_daily');
  const [sourceMode, setSourceMode] = useState('file');
  const [url, setUrl] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [rights, setRights] = useState('owned');
  const [evidence, setEvidence] = useState('');
  const [perspective, setPerspective] = useState('');
  const [reprocess, setReprocess] = useState(false);
  const [max, setMax] = useState(38);
  const [count, setCount] = useState(1);
  const [busy, setBusy] = useState('');
  const [audits, setAudits] = useState<Record<string,FacebookQC>>({});
  const [remoteUrls, setRemoteUrls] = useState<Record<string,string>>({});
  const refresh = useCallback(async () => {
    try {
      const [settings, jobs, posts] = await Promise.all([
        facebookRequest<FacebookConfig>('facebook/config'),
        facebookRequest<FacebookProduction[]>('facebook/jobs'),
        facebookRequest<FacebookUpload[]>('facebook/uploads'),
      ]);
      setConfig(settings); setSession(settings.session); setProductions(jobs); setUploads(posts); setError('');
    } catch (reason) {setError(reason instanceof Error ? reason.message : 'Status Facebook belum tersedia.');}
  }, []);
  useEffect(() => {void refresh(); const timer = setInterval(() => {void refresh();}, 10_000); return () => clearInterval(timer);}, [refresh]);
  const sessionChanged = useCallback((value: FacebookSession) => setSession(value), []);
  const perform = async (key: string, action: () => Promise<unknown>) => {
    setBusy(key);
    try {await action(); await refresh();}
    catch (reason) {toast.error(reason instanceof Error ? reason.message : 'Tindakan belum berhasil.');}
    finally {setBusy('');}
  };
  const create = (event: FormEvent) => {
    event.preventDefault();
    if (sourceMode === 'file' && !file) {toast.error('Pilih video terlebih dahulu.'); return;}
    void perform('create', async () => {
      const uploaded = sourceMode === 'file' && file ? await uploadVideo(file) : null;
      await facebookRequest('facebook/jobs', {url: sourceMode === 'url' ? url : '', source_file: uploaded?.source_file || '',
        niche, max_duration:max, top:count, rights, rights_evidence:evidence, creator_perspective:perspective,
        allow_reprocess_source:reprocess});
      toast.success('Produksi Facebook masuk antrean.');
    });
  };
  const selected = config?.niches.find(item => item.key === niche);
  return <div className="fbWorkspace">
    <div className="fbIntro"><div><span className="fbEyebrow"><Facebook size={16}/> FACEBOOK REELS</span>
      <h2>Satu tips. Langsung berguna.</h2><p>Target 30 detik · maksimal 55 detik · portrait 1080×1920</p></div>
      <div className="fbRecipe"><strong>Hook → langkah → hasil</strong><span>Subtitle frasa stabil · watermark RYUUNDY</span></div></div>
    <FacebookConnection onChange={sessionChanged}/>
    {error ? <p role="alert" className="fbError">{error}</p> : null}
    <div className="fbColumns">
      <form className="fbComposer" onSubmit={create}>
        <header><Clapperboard size={19}/><h2>Produksi khusus Facebook</h2></header>
        <label>Niche<select value={niche} onChange={event => setNiche(event.target.value)}>
          {(config?.niches || [{key:'tech_daily', label:'Tips teknologi & trik HP sehari-hari'}]).map(item => <option key={item.key} value={item.key}>{item.label}</option>)}</select></label>
        <p className="fbHint">{selected?.brief || 'Pilih satu masalah sehari-hari dengan langkah dan hasil yang jelas di video.'}</p>
        <label>Video yang akan dipotong<select value={sourceMode} onChange={event => setSourceMode(event.target.value)}><option value="file">Video dari perangkat</option><option value="url">URL YouTube milik sendiri / berizin</option></select></label>
        {sourceMode === 'file' ? <label className="fbFile"><Upload size={18}/><span>{file?.name || 'Pilih video panjang'}</span><input type="file" accept="video/*" onChange={event => setFile(event.target.files?.[0] || null)}/></label> :
          <label>URL video<input type="url" required value={url} onChange={event => setUrl(event.target.value)} placeholder="https://www.youtube.com/watch?v=…"/></label>}
        <div className="fbFormPair"><label>Batas durasi<select value={max} onChange={event => setMax(Number(event.target.value))}><option value={38}>Sekitar 30 detik (maks. 38)</option><option value={45}>Maksimal 45 detik</option><option value={55}>Maksimal 55 detik</option></select></label>
          <label>Jumlah clip<select value={count} onChange={event => setCount(Number(event.target.value))}>{[1,2,3].map(value => <option key={value} value={value}>{value} clip terbaik</option>)}</select></label></div>
        <label>Hak video dan audio<select value={rights} onChange={event => setRights(event.target.value)}><option value="owned">Rekaman milik sendiri</option><option value="permission_no_credit">Izin penggunaan tanpa atribusi publik</option></select></label>
        <label>Bukti hak penggunaan<textarea required minLength={20} value={evidence} onChange={event => setEvidence(event.target.value)} placeholder="Jelaskan kepemilikan rekaman dan audio, atau referensi izin pemilik (minimal 6 kata)." rows={3}/></label>
        <label>Sudut pandang editor <span className="fbOptional">opsional</span><textarea value={perspective} onChange={event => setPerspective(event.target.value)} rows={2} placeholder="Contoh: prioritaskan cara merapikan foto dan hasilnya."/></label>
        {sourceMode === 'url' ? <label className="fbCheck"><input type="checkbox" checked={reprocess} onChange={event => setReprocess(event.target.checked)}/> Saya mengizinkan proses ulang jika video sudah pernah dipakai.</label> : null}
        <p className="fbHint">Caption publik tanpa sumber. Materi yang mewajibkan kredit perlu izin terpisah. Data asal tetap tersimpan untuk pemeriksaan.</p>
        <button className="uiButton uiButton--primary fbSubmit" disabled={!!busy || !config} type="submit">{busy === 'create' ? <Loader2 size={17} className="spin"/> : <Clapperboard size={17}/>} {busy === 'create' ? 'Menyiapkan produksi…' : 'Buat clip Facebook'}</button>
      </form>
      <section className="fbResults" aria-label="Hasil khusus Facebook">
        <header className="fbResultsHeading"><div><h2>Proses & hasil Facebook</h2><p>{productions.length} produksi · {uploads.filter(item => item.upload_confirmed).length} Reel terkonfirmasi</p></div><button className="uiButton" onClick={() => void refresh()} type="button" aria-label="Perbarui hasil Facebook"><RefreshCw size={15}/></button></header>
        {!productions.length ? <div className="fbEmpty"><Facebook size={32}/><h3>Ruang untuk Reel pertama.</h3><p>Pilih video, lalu biarkan editor mencari satu tips dengan pembukaan, langkah, dan hasil yang utuh.</p><span>01 Pilih momen · 02 Clip & QC · 03 Preview · 04 Upload</span></div> : null}
        {productions.map(({job,results}) => <article className="fbProduction" key={job.id}>
          <header><div><span className={`fbState is-${job.status}`}>{statusLabel[job.status]}</span><h3>{job.source_title || `Produksi Facebook · ${job.id.slice(0,8)}`}</h3></div><small>{new Date(job.created_at).toLocaleDateString('id-ID', {timeZone:'Asia/Jakarta'})}</small></header>
          {['queued','running'].includes(job.status) ? <div className="fbProgress" aria-live="polite"><progress value={job.progress_percent || 0} max={100}/><span>{job.progress_detail || 'Menunggu worker…'}</span><button type="button" disabled={!!busy} onClick={() => void perform(job.id, () => cancelJob(job.id))}>Batalkan produksi</button></div> : null}
          {job.error ? <p className="fbError">{job.error}</p> : null}
          {job.clips.map(clip => {
            const key = `${job.id}:${clip.url}`;
            const caption = results.find(result => result.clip_url === clip.url)?.caption || '';
            const post = uploads.find(item => item.job_id === job.id && item.clip_url === clip.url);
            const audit = audits[key];
            return <div className="fbResult" key={clip.url}>
              <video controls playsInline preload="metadata" poster={clip.thumbnail_url ? mediaUrl(clip.thumbnail_url) : undefined} src={mediaUrl(clip.url)} aria-label={`Preview ${clip.title || clip.name}`}/>
              <div className="fbResultDetail"><h4>{clip.title || clip.name}</h4><span className="fbEyebrow">CAPTION FACEBOOK</span><p className="fbCaption">{caption || 'Caption belum tersedia.'}</p>
                <div className="fbActions"><button className="uiButton" disabled={!caption} type="button" onClick={() => void perform(`copy:${key}`, () => navigator.clipboard.writeText(caption).then(() => toast.success('Caption disalin.')))}><Copy size={14}/> Salin caption</button><a className="uiButton" href={mediaUrl(clip.url)} download><Download size={14}/> Unduh video</a></div>
                <label className="fbCheck"><input type="checkbox" checked={clip.is_correct} disabled={!!busy || !!post} onChange={event => {const checked = event.target.checked; setAudits(previous => {const next = {...previous}; delete next[key]; return next;}); void perform(`review:${key}`, () => updateJobClipStatus(job.id,clip.url,checked));}}/> Saya sudah menonton; konteks, subtitle, dan hasil sudah benar.</label>
                <div className="fbActions"><button className="uiButton" type="button" disabled={!!busy} onClick={() => void perform(`qc:${key}`, async () => {const value = await facebookRequest<FacebookQC>('facebook/qc',{job_id:job.id,clip_url:clip.url}); setAudits(previous => ({...previous,[key]:value}));})}><ShieldCheck size={15}/> Periksa QC</button>
                  <button className="uiButton uiButton--primary" type="button" disabled={!!busy || !!post || audit?.decision !== 'PASS_UPLOAD' || !session.account_verified || !!error} onClick={() => void perform(`post:${key}`, () => facebookRequest('facebook/uploads',{job_id:job.id,clip_url:clip.url}))}><Facebook size={15}/> Upload Reel publik</button></div>
                {audit ? <div className="fbAudit" role="status">{audit.decision === 'PASS_UPLOAD' ? <p><CheckCircle2 size={14}/> QC lulus; siap masuk antrean.</p> : <><strong>Ditahan untuk diperiksa</strong><ul>{audit.issues.map(issue => <li key={issue}>{issue}</li>)}</ul></>}</div> : <p className="fbHint">Tonton preview dan periksa QC sebelum upload.</p>}
                {post ? <div className="fbPost" role="status"><strong>{post.upload_confirmed ? 'Reel terkonfirmasi' : statusLabel[post.status]}</strong><p>{post.message}</p>{post.video_url && post.upload_confirmed ? <a href={post.video_url} target="_blank" rel="noreferrer">Lihat Reel ↗</a> : null}
                  {post.status === 'needs_review' ? <div className="fbReconcile"><label>Permalink Reel yang sudah diposting<input type="url" value={remoteUrls[post.id] || ''} placeholder="https://www.facebook.com/reel/…/" onChange={event => setRemoteUrls(previous => ({...previous,[post.id]:event.target.value}))}/></label><button type="button" className="uiButton" disabled={!!busy || !remoteUrls[post.id]} onClick={() => void perform(`verify:${post.id}`, () => facebookRequest(`facebook/uploads/${post.id}/verify-remote`, {video_url:remoteUrls[post.id]}))}>Cocokkan hasil remote</button></div> : null}</div> : null}
              </div></div>;
          })}
        </article>)}
      </section>
    </div>
  </div>;
}
