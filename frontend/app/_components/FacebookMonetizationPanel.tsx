"use client";

import { useCallback, useEffect, useState } from 'react';
import { ArrowUpRight, BadgeCheck, ChevronDown, CircleDollarSign, Copy, ExternalLink, Loader2, RefreshCw, Target } from 'lucide-react';
import toast from 'react-hot-toast';
import { facebookRequest, type FacebookBrief, type FacebookMonetization } from '../../lib/facebook';

const dollars = (amount: number | null | undefined) => amount == null ? 'Belum diketahui' :
  new Intl.NumberFormat('id-ID', {style:'currency', currency:'USD', minimumFractionDigits:2}).format(amount);
const number = (value: number | null | undefined) => value == null ? '—' : value.toLocaleString('id-ID');
const PLATFORM_URL = 'https://www.facebook.com/professional_dashboard/monetization/';

export function FacebookMonetizationPanel({onUseBrief}: {onUseBrief: (brief: FacebookBrief) => void}) {
  const [snapshot, setSnapshot] = useState<FacebookMonetization | null>(null);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const load = useCallback(async () => {
    try {setSnapshot(await facebookRequest<FacebookMonetization>('facebook/monetization')); setError('');}
    catch (reason) {setError(reason instanceof Error ? reason.message : 'Status monetisasi belum tersedia.');}
  }, []);
  useEffect(() => {void load();}, [load]);
  useEffect(() => {
    if (snapshot?.check_state !== 'running') return;
    const timer = setInterval(() => {void load();}, 5000);
    return () => clearInterval(timer);
  }, [snapshot?.check_state, load]);
  const check = async () => {
    setSubmitting(true);
    try {setSnapshot(await facebookRequest<FacebookMonetization>('facebook/monetization/check', {})); setError('');}
    catch (reason) {setError(reason instanceof Error ? reason.message : 'Pemeriksaan belum berhasil.');}
    finally {setSubmitting(false);}
  };
  const active = snapshot?.program.state === 'active';
  const busy = submitting || snapshot?.check_state === 'running';
  const stale = Boolean(snapshot?.checked_at && Date.now() - Date.parse(snapshot.checked_at) > 24 * 60 * 60 * 1000);
  const bonus = snapshot?.bonus;
  const copyBrief = async (brief: FacebookBrief) => {
    try {await navigator.clipboard.writeText(brief.caption); toast.success('Draft caption disalin. Cocokkan dengan rekaman sebelum dipakai.');}
    catch {toast.error('Caption belum dapat disalin.');}
  };
  return <section className="fbMonetization" aria-labelledby="fb-monetization-title">
    <header className="fbMoneyHeader"><div><span className="fbEyebrow"><CircleDollarSign size={16}/> MONETISASI FACEBOOK</span>
      <h2 id="fb-monetization-title">{active ? 'Akses aktif. Bangun tayangan yang memenuhi syarat.' : snapshot?.program.state === 'restricted' ? 'Pembatasan monetisasi perlu diperiksa.' : 'Periksa peluang monetisasi akun Anda.'}</h2>
      <p>{active ? 'Status program sudah terbuka. Pendapatan tetap bergantung pada kelayakan konten dan hasil tontonan.' : 'Keadaan akun, bonus, kelayakan konten dan pembayaran diperiksa secara terpisah.'}</p></div>
      <div className="fbMoneyActions"><button type="button" className="uiButton uiButton--primary" disabled={busy} onClick={() => void check()}>{busy ? <Loader2 size={15} className="spin"/> : <RefreshCw size={15}/>} {busy ? 'Memeriksa akun…' : 'Analisis akun sekarang'}</button><a className="uiButton" href={snapshot?.links.overview || PLATFORM_URL} target="_blank" rel="noreferrer">Dasbor Facebook <ArrowUpRight size={14}/></a></div>
    </header>
    <div className={`fbMoneyEvidence ${active ? 'isActive' : ''}`} role="status">{active ? <BadgeCheck size={15}/> : <CircleDollarSign size={15}/>}
      <span>{active ? 'Program monetisasi aktif' : 'Akses monetisasi belum terkonfirmasi'}{snapshot?.policy.state === 'clear' ? ' · Tidak ada batasan pada pemeriksaan' : snapshot?.policy.state === 'restricted' ? ' · Pembatasan terdeteksi' : ''}</span>
      <small>{snapshot?.checked_at ? `${stale ? 'Bukti lama · ' : ''}${new Date(snapshot.checked_at).toLocaleString('id-ID', {timeZone:'Asia/Jakarta'})} WIB` : 'Belum ada pemeriksaan akun'}</small>
    </div>
    {error || snapshot?.last_error ? <p role="alert" className="fbError">{error || snapshot?.last_error}</p> : null}
    {stale ? <p className="fbMoneyNotice">Status dan sisa waktu bonus mungkin berubah. Jalankan analisis ulang sebelum mengambil keputusan.</p> : null}
    <div className="fbMoneyMetrics">
      <div><span>Estimasi {snapshot?.earnings.period || 'pendapatan'}</span><strong>{dollars(snapshot?.earnings.estimated_usd)}</strong><small>Angka tercatat, belum tentu siap dicairkan</small></div>
      <div><span>Tayangan memenuhi syarat</span><strong>{number(snapshot?.earnings.qualified_views)}</strong><small>Ukuran yang relevan untuk penghasilan</small></div>
      <div><span>{bonus ? `Bonus ${dollars(bonus.amount_usd)}` : 'Bonus akun'}</span><strong>{bonus ? `${number(bonus.completed_reels)} / ${number(bonus.required_reels)} Reel` : 'Belum terbaca'}</strong><small>{bonus?.period_label || 'Periode mengikuti dasbor Facebook'}</small></div>
      <div><span>Kesiapan pencairan</span><strong className="fbMoneyTextValue">{snapshot?.payout.state === 'ready' ? 'Siap menurut Facebook' : snapshot?.payout.state === 'action_required' ? 'Perlu tindakan' : 'Belum terverifikasi'}</strong><small>Rekening, identitas dan pajak bila diminta</small></div>
    </div>
    {snapshot ? <>
      <div className="fbMoneyDiagnosis">
        <div><span className="fbEyebrow"><Target size={14}/> FOKUS PERBAIKAN</span><h3>{snapshot.earnings.qualified_views === 0 ? 'Mulai dari tontonan yang bertahan.' : 'Pertahankan yang menghasilkan tontonan.'}</h3>
          {snapshot.earnings.non_qualified_reasons.length ? <ul className="fbReasonList">{snapshot.earnings.non_qualified_reasons.map(reason => <li key={reason.label}><strong>{reason.percent}%</strong><span>{reason.label}</span></li>)}</ul> : <p>Alasan tayangan tidak memenuhi syarat belum terbaca. Buka tingkat pendapatan Facebook untuk memeriksanya.</p>}
          <p>{snapshot.insights.views != null ? `${number(snapshot.insights.views)} tayangan total · ${number(snapshot.insights.three_second_views)} tayangan 3 detik (${snapshot.insights.period || 'periode insight'}). ` : ''}Tayangan total dan tayangan yang memenuhi syarat adalah ukuran berbeda.</p>
          <a href={snapshot.links.rate} target="_blank" rel="noreferrer">Lihat alasan & tingkat pendapatan <ArrowUpRight size={13}/></a>
        </div>
        <aside><h3>{bonus ? 'Selesaikan bonus yang tersedia' : 'Periksa bonus yang tersedia'}</h3>
          {bonus ? <><progress value={bonus.completed_reels || 0} max={bonus.required_reels || 1} aria-label="Progres Reel memenuhi syarat menurut Facebook"/>
            <p>Buat {number(bonus.required_reels)} Reel, masing-masing minimal {number(bonus.minimum_duration_seconds)} detik. Capai {number(bonus.minimum_qualified_views)} tayangan yang memenuhi syarat pada setidaknya {number(bonus.minimum_reels_with_qualified_views)} Reel.</p>
            {bonus.days_remaining_at_check != null ? <small>{bonus.days_remaining_at_check} hari tersisa saat pemeriksaan. Periksa kembali batas waktu di Facebook.</small> : null}
            <p className="fbHint">Progres berasal dari Facebook. Jumlah upload ClipForge tidak menggantikan syarat bonus, dan bonus belum berarti uang sudah cair.</p></> : <p>Syarat dan progres bonus belum diketahui. Ketiadaan data bukan tanda akun ditolak.</p>}
        </aside>
      </div>
      <div className="fbMoneyNext"><header><h3>Langkah yang dikerjakan lebih dahulu</h3><p>Prioritas berdasarkan pemeriksaan akun; jadwal ini tidak memublikasikan video otomatis.</p></header>
        <ol>{snapshot.actions.map(action => <li key={action.key}><span>{action.priority}</span><div><h4>{action.title}</h4><p>{action.detail}</p></div><a href={action.href} target="_blank" rel="noreferrer" aria-label={`Buka Facebook: ${action.title}`}><ExternalLink size={16}/></a></li>)}</ol>
      </div>
      <details className="fbMoneyOriginality"><summary>Apakah hasil clipper bisa menghasilkan uang? <ChevronDown size={15}/></summary>
        <p>Jalur otomatis memproduksi naskah dan demonstrasi digital sendiri, dengan label simulasi dan pemeriksaan hasil. Rekaman Anda dapat ditambahkan sebagai bahan lain. Potongan video pihak lain yang hanya diberi watermark, subtitle, crop, atau perubahan kecepatan belum menunjukkan nilai tambah yang cukup untuk monetisasi Facebook.</p>
        <p>Izin hak cipta dan orisinalitas monetisasi adalah pemeriksaan berbeda. Status QC lulus atau upload selesai tidak sama dengan persetujuan monetisasi Facebook. Caption publik tetap tanpa sumber; bukti hak penggunaan tetap disimpan secara internal.</p>
        <p>{snapshot.payout.message}</p>
      </details>
      <details className="fbMoneyBriefs"><summary><span>Ide rekaman tambahan, bila ingin <small>Opsional · target 30 detik · maksimum 55 · belum berupa video</small></span><ChevronDown size={16}/></summary>
        <div>{snapshot.production_briefs.map((brief,index) => <article key={brief.key}><span className="fbEyebrow">REEL {index+1} · REKAMAN ASLI DIPERLUKAN</span><h4>{brief.title}</h4><blockquote>{brief.hook}</blockquote><p>{brief.recording}</p><p className="fbHint">{brief.sequence.join(' → ')}</p><p className="fbHint">{brief.proof}</p><div className="fbActions"><button className="uiButton" type="button" onClick={() => onUseBrief(brief)}>Gunakan arahan ini</button><button className="uiButton" type="button" onClick={() => void copyBrief(brief)}><Copy size={14}/> Salin draft caption</button></div></article>)}</div>
      </details>
      <p className="fbMoneyFooter">{snapshot.limits}</p>
    </> : <div className="fbMoneyEmpty"><p>Analisis akan membaca status monetisasi, bonus, tingkat pendapatan dan kesiapan pembayaran dari akun target. Data rekening dan pajak tidak disimpan di ClipForge.</p></div>}
  </section>;
}
