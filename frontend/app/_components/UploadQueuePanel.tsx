"use client";

import { useMemo, useState } from "react";
import { ArrowUpRight, CheckCircle2, ChevronLeft, ChevronRight, Clock3, Search, UploadCloud } from "lucide-react";
import type { TikTokUploadJob, YouTubeUploadJob } from "../../types/clip.type";
import { queueDate, studioQueueItems } from "../../lib/studioQueue";

type Filter = "active" | "attention" | "verified";

export function UploadQueuePanel({ youtube, tiktok }: { youtube: YouTubeUploadJob[]; tiktok: TikTokUploadJob[] }) {
  const [filter, setFilter] = useState<Filter>("active");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const rows = useMemo(()=>studioQueueItems(youtube,tiktok),[youtube,tiktok]);
  const matches = (state:string, key:Filter) => key === "active" ? ["running","queued"].includes(state)
    : key === "attention" ? ["attention","failed"].includes(state) : state === "verified";
  const filtered = rows.filter(row=>matches(row.state,filter) && `${row.title} ${row.platform}`.toLowerCase().includes(query.toLowerCase()));
  const pages = Math.max(1,Math.ceil(filtered.length/12));
  const currentPage = Math.min(page,pages-1);
  const visible = filtered.slice(currentPage*12,currentPage*12+12);
  return <section className="studioQueue" aria-labelledby="studio-queue-title">
    <div className="studioQueueHeader"><div><h2 id="studio-queue-title">Antrean distribusi</h2><p>Status nyata upload YouTube dan TikTok.</p></div>
      <label className="studioSearch"><Search size={16} /><input aria-label="Cari antrean upload" placeholder="Cari judul atau platform…" value={query} onChange={e=>{setQuery(e.target.value);setPage(0);}} /></label>
    </div>
    <div className="studioQueueFilters" role="group" aria-label="Filter antrean upload">
      {([{key:"active",label:"Aktif"},{key:"attention",label:"Perlu perhatian"},{key:"verified",label:"Terverifikasi"}] as const).map(item=><button type="button" key={item.key} aria-pressed={filter===item.key}
        className={filter===item.key?"isActive":""} onClick={()=>{setFilter(item.key);setPage(0);}}>{item.label}<span>{rows.filter(row=>matches(row.state,item.key)).length}</span></button>)}
    </div>
    {visible.length ? <div className="studioQueueList">{visible.map(row=><article key={row.id} className={`studioQueueRow is-${row.state}`}>
      <span className={`studioPlatformMark is${row.platform}`}>{row.platform === "YouTube" ? "Y" : "T"}</span>
      <div className="studioQueueCopy"><strong>{row.title}</strong><span>{row.platform} · {row.privacy} · {queueDate(row.updatedAt)}</span>{row.detail ? <details><summary>Lihat keterangan</summary><p>{row.detail}</p></details> : null}</div>
      <span className="studioQueueState">{row.state === "verified" ? <CheckCircle2 size={14} /> : <Clock3 size={14} />}{row.label}</span>
      <a href={row.studioUrl} target="_blank" rel="noreferrer" aria-label={`Periksa ${row.title} di ${row.platform} Studio`} title="Periksa di Studio"><ArrowUpRight size={17} /></a>
    </article>)}</div> : <div className="studioQueueEmpty"><UploadCloud size={28} strokeWidth={1.4} /><strong>{query ? "Tidak ada hasil pencarian" : filter === "active" ? "Tidak ada upload yang mengantre" : "Belum ada data di kategori ini"}</strong><p>{query ? "Coba judul atau platform lain." : "Antrean baru akan muncul otomatis saat video siap didistribusikan."}</p></div>}
    {filtered.length>12 ? <footer className="studioPagination"><span>{currentPage*12+1}–{Math.min((currentPage+1)*12,filtered.length)} dari {filtered.length}</span><div><button type="button" aria-label="Halaman antrean sebelumnya" disabled={currentPage===0} onClick={()=>setPage(currentPage-1)}><ChevronLeft size={16} /></button><button type="button" aria-label="Halaman antrean berikutnya" disabled={currentPage===pages-1} onClick={()=>setPage(currentPage+1)}><ChevronRight size={16} /></button></div></footer> : null}
  </section>;
}
