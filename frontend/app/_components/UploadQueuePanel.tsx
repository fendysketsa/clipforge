"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowUpRight, CheckCircle2, ChevronLeft, ChevronRight, Clock3, Loader2, RefreshCw, Search, ShieldCheck, UploadCloud } from "lucide-react";
import type { TikTokUploadJob, YouTubeUploadJob } from "../../types/clip.type";
import { getUploadAttention, requestUploadAttentionCheck } from "../../lib/apiClient";
import { createPollingTask } from "../../lib/pollTask";
import toast from "react-hot-toast";
import type { UploadAttentionSnapshot } from "../../lib/studioQueue";
import { queueDate, studioQueueItems } from "../../lib/studioQueue";

type Filter = "active" | "attention" | "held" | "verified";

export function UploadQueuePanel({ youtube, tiktok }: { youtube: YouTubeUploadJob[]; tiktok: TikTokUploadJob[] }) {
  const [filter, setFilter] = useState<Filter>("active");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [attention, setAttention] = useState<UploadAttentionSnapshot | null>(null);
  const [attentionError, setAttentionError] = useState("");
  const [requesting, setRequesting] = useState(false);
  useEffect(() => {
    const poll = createPollingTask(async current => {
      try {
        const data = await getUploadAttention();
        if (current()) { setAttention(data); setAttentionError(data.error || ""); }
      } catch { if (current()) setAttentionError("Status otomatis belum tersedia. Data upload terakhir tetap ditampilkan."); }
    }, () => !document.hidden);
    void poll.run();
    const timer = window.setInterval(poll.run, 20_000);
    document.addEventListener("visibilitychange", poll.run);
    return () => { poll.stop(); window.clearInterval(timer); document.removeEventListener("visibilitychange", poll.run); };
  }, []);
  const requestCheck = async () => {
    setRequesting(true);
    try {
      const result = await requestUploadAttentionCheck();
      if (result.accepted) toast.success(result.message); else toast.error("Penanganan otomatis sedang dijeda di server.");
      setAttention(await getUploadAttention()); setAttentionError("");
    } catch (error) { toast.error(error instanceof Error ? error.message : "Pemeriksaan belum dapat dimulai."); }
    finally { setRequesting(false); }
  };
  const rows = useMemo(()=>studioQueueItems(youtube,tiktok,attention),[youtube,tiktok,attention]);
  const matches = (state:string, key:Filter) => key === "active" ? ["running","queued"].includes(state)
    : key === "attention" ? ["attention","failed"].includes(state) : key === "held" ? state === "held" : state === "verified";
  const filtered = rows.filter(row=>matches(row.state,filter) && `${row.title} ${row.platform}`.toLowerCase().includes(query.toLowerCase()));
  const pages = Math.max(1,Math.ceil(filtered.length/12));
  const currentPage = Math.min(page,pages-1);
  const visible = filtered.slice(currentPage*12,currentPage*12+12);
  return <section className="studioQueue" aria-labelledby="studio-queue-title">
    <div className="studioQueueHeader"><div><h2 id="studio-queue-title">Antrean distribusi</h2><p>Sistem menangani konfirmasi dan pemulihan upload YouTube serta TikTok.</p></div>
      <label className="studioSearch"><Search size={16} /><input aria-label="Cari antrean upload" placeholder="Cari judul atau platform…" value={query} onChange={e=>{setQuery(e.target.value);setPage(0);}} /></label>
    </div>
    <div className={`studioQueueAutomation${attention?.enabled && attention.worker_running ? " isRunning" : ""}`} role="status">
      <ShieldCheck size={18} /><div><strong>{attention?.enabled && attention.worker_running ? "Penanganan otomatis aktif" : attention ? "Penanganan otomatis sedang dijeda" : attentionError ? "Penanganan otomatis belum tersedia" : "Membaca status penanganan otomatis…"}</strong>
        <p>{attentionError || (attention?.rejected_upload_cleanup_version === 1
          ? "Video yang lolos dilanjutkan. Klip yang ditolak dibersihkan otomatis; status posting yang belum pasti dicocokkan."
          : "Posting yang sudah ada dicocokkan. Kegagalan aman dipulihkan; sumber yang belum memenuhi syarat ditahan.")}</p></div>
      <button className="uiButton" type="button" disabled={requesting || !attention?.enabled} onClick={() => { void requestCheck(); }}>
        {requesting ? <Loader2 className="spin" size={14} /> : <RefreshCw size={14} />} Periksa sekarang
      </button>
    </div>
    <div className="studioQueueFilters" role="group" aria-label="Filter antrean upload">
      {([{key:"active",label:"Aktif"},{key:"attention",label:"Ditangani otomatis"},{key:"held",label:"Ditahan"},{key:"verified",label:"Terverifikasi"}] as const).map(item=><button type="button" key={item.key} aria-pressed={filter===item.key}
        className={filter===item.key?"isActive":""} onClick={()=>{setFilter(item.key);setPage(0);}}>{item.label}<span>{rows.filter(row=>matches(row.state,item.key)).length}</span></button>)}
    </div>
    {visible.length ? <div className="studioQueueList">{visible.map(row=><article key={row.id} className={`studioQueueRow is-${row.state}${row.automatic && row.state !== "held" ? " isAutomatic" : ""}`}>
      <span className={`studioPlatformMark is${row.platform}`}>{row.platform === "YouTube" ? "Y" : "T"}</span>
      <div className="studioQueueCopy"><strong>{row.title}</strong><span>{row.platform} · {row.privacy} · {queueDate(row.updatedAt)}</span>{row.detail ? ["attention", "failed", "held"].includes(row.state) ? <p className="studioQueueRecoveryMessage">{row.detail}</p> : <details><summary>Lihat keterangan</summary><p>{row.detail}</p></details> : null}
        {row.nextCheckAt && row.automatic ? <small className="studioQueueNextCheck">Pemeriksaan berikutnya: {queueDate(new Date(row.nextCheckAt * 1000).toISOString())}</small> : null}</div>
      <span className="studioQueueState">{row.state === "verified" ? <CheckCircle2 size={14} /> : <Clock3 size={14} />}{row.label}</span>
      <a href={row.studioUrl} target="_blank" rel="noreferrer" aria-label={`Periksa ${row.title} di ${row.platform} Studio`} title="Periksa di Studio"><ArrowUpRight size={17} /></a>
    </article>)}</div> : <div className="studioQueueEmpty"><UploadCloud size={28} strokeWidth={1.4} /><strong>{query ? "Tidak ada hasil pencarian" : filter === "active" ? "Tidak ada upload yang mengantre" : "Belum ada data di kategori ini"}</strong><p>{query ? "Coba judul atau platform lain." : "Antrean baru akan muncul otomatis saat video siap didistribusikan."}</p></div>}
    {filtered.length>12 ? <footer className="studioPagination"><span>{currentPage*12+1}–{Math.min((currentPage+1)*12,filtered.length)} dari {filtered.length}</span><div><button type="button" aria-label="Halaman antrean sebelumnya" disabled={currentPage===0} onClick={()=>setPage(currentPage-1)}><ChevronLeft size={16} /></button><button type="button" aria-label="Halaman antrean berikutnya" disabled={currentPage===pages-1} onClick={()=>setPage(currentPage+1)}><ChevronRight size={16} /></button></div></footer> : null}
  </section>;
}
