"use client";

import { Activity, ArrowRight, BookOpen, CheckCircle2, Clapperboard, Clock3, Film, Layers3, Play, Scissors, UploadCloud } from "lucide-react";
import { useMemo } from "react";
import type { AutoViralScheduleStatus, ClipJob, TikTokUploadJob, YouTubeUploadJob } from "../../types/clip.type";
import { studioQueueItems, queueDate } from "../../lib/studioQueue";
const statusLabel = { queued: "Mengantre", running: "Diproses", completed: "Selesai", failed: "Perlu perhatian", cancelled: "Dibatalkan" };

const formats = [
  { icon: Scissors, title: "Short", description: "Momen terbaik dalam format vertikal.", meta: "9:16 · Video pendek", mode: "short" },
  { icon: Film, title: "Long Highlight", description: "Rangkai bagian penting jadi cerita utuh.", meta: "16:9 · Video panjang", mode: "highlight_5m" },
  { icon: BookOpen, title: "Generator Video", description: "Ubah artikel atau ide menjadi animasi.", meta: "Artikel · Cerita · Naskah", mode: "long_animate" },
] as const;

type Props = {
  jobs: ClipJob[]; youtube: YouTubeUploadJob[]; tiktok: TikTokUploadJob[];
  schedule: AutoViralScheduleStatus | null; ready: boolean; error: string;
  dataReady: { jobs: boolean; youtube: boolean; tiktok: boolean };
  onSelectJob: (job: ClipJob) => void; onCreate: (mode: "short" | "highlight_5m" | "long_animate") => void;
};

export function StudioOverview({ jobs, youtube, tiktok, schedule, ready, dataReady, error, onSelectJob, onCreate }: Props) {
  const summary = useMemo(() => {
    const queue = studioQueueItems(youtube, tiktok);
    return {
      active: jobs.filter(item => ["queued", "running"].includes(item.status)).length,
      clips: jobs.reduce((sum, item) => sum + item.clips.length, 0),
      pending: queue.filter(item => ["queued", "running"].includes(item.state)).length,
      attention: queue.filter(item => ["attention", "failed"].includes(item.state)).length,
      recent: [...jobs].sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at)).slice(0, 5),
    };
  }, [jobs, youtube, tiktok]);
  const metrics = [
    { icon: Activity, label: "Produksi aktif", value: dataReady.jobs ? summary.active : "—", detail: "Sedang dikerjakan & mengantre", href: "/#history", tone: "info" },
    { icon: Film, label: "Hasil tersedia", value: dataReady.jobs ? summary.clips : "—", detail: "Video tersimpan untuk ditinjau", href: "/#results", tone: "success" },
    { icon: UploadCloud, label: "Antrean upload", value: dataReady.youtube && dataReady.tiktok ? summary.pending : "—", detail: "Distribusi YouTube & TikTok", href: "/#automation", tone: "primary" },
    { icon: Clapperboard, label: "Upload cron hari ini", value: schedule?.daily_plan?.total_uploaded ?? "—", detail: `Target ${schedule?.daily_plan?.total_target ?? 23} video · WIB`, href: "/#automation", tone: "warning" },
  ];
  return <div className="studioOverview" aria-busy={!ready}>
    {error ? <div className="studioDataNotice" role="status">{error} Data terakhir tetap ditampilkan. Gunakan Sinkronkan untuk mencoba lagi.</div> : null}
    <section className="overviewMetrics" aria-label="Ringkasan operasional">
      {metrics.map(({ icon: Icon, ...metric }) => <a href={metric.href} className={`overviewMetric tone-${metric.tone}`} key={metric.label}>
        <div><span>{metric.label}</span><Icon size={18} /></div>
        <strong>{ready ? metric.value : "—"}</strong>
        <p>{metric.detail}<ArrowRight size={14} /></p>
      </a>)}
    </section>
    <section className="overviewLaunch" aria-labelledby="overview-launch-title">
      <div className="overviewLaunchHeader"><div><span className="studioEyebrow">DARI IDE KE VIDEO</span><h2 id="overview-launch-title">Apa yang ingin Anda buat?</h2></div><span className="overviewStepHint">Pilih format untuk memulai <ArrowRight size={15} /></span></div>
      <div className="overviewFormats">{formats.map(({ icon: Icon, ...format }, index) => <button type="button" key={format.mode} onClick={() => onCreate(format.mode)}>
        <span className={`overviewFormatIcon format-${index}`}><Icon size={24} strokeWidth={1.6} /></span>
        <span className="overviewFormatCopy"><strong>{format.title}</strong><span>{format.description}</span><small>{format.meta}</small></span>
        <ArrowRight size={18} className="overviewFormatArrow" />
      </button>)}</div>
    </section>
    <div className="overviewColumns">
      <section className="overviewRecent" aria-labelledby="overview-recent-title">
        <header><div><span className="studioEyebrow">AKTIVITAS</span><h2 id="overview-recent-title">Produksi terbaru</h2></div><a href="/#history">Lihat semua <ArrowRight size={15} /></a></header>
        {summary.recent.length ? <div>{summary.recent.map(item => <button type="button" className="overviewRecentRow" key={item.id} onClick={() => onSelectJob(item)}>
          <span className={`overviewRecentIcon is-${item.status}`}>{item.status === "completed" ? <CheckCircle2 size={19} /> : item.status === "running" ? <Activity size={19} /> : <Clock3 size={19} />}</span>
          <span className="overviewRecentCopy"><strong>{item.source_title || (item.request.clip_mode === "long_animate" ? "Video dari artikel / cerita" : "Produksi video")}</strong><small>{queueDate(item.updated_at)} · {item.clips.length} hasil</small></span>
          <span className={`overviewRecentState is-${item.status}`}>{statusLabel[item.status]}{item.status === "running" ? ` · ${Math.round(item.progress_percent ?? 0)}%` : ""}</span><ArrowRight size={16} />
        </button>)}</div> : <div className="overviewEmpty"><Layers3 size={29} /><strong>{!ready ? "Membaca aktivitas studio…" : !dataReady.jobs ? "Aktivitas belum tersedia" : "Produksi pertama dimulai dari sini"}</strong><p>{ready && !dataReady.jobs ? "Coba sinkronkan kembali untuk membaca status produksi." : "Pilih salah satu format di atas untuk menyiapkan video."}</p></div>}
      </section>
      <aside className="overviewGuide">
        <div className="overviewGuideTop"><span className="studioEyebrow">ALUR KERJA</span><Play size={17} /></div>
        <h2>Lebih teratur,<br /> dari awal sampai tayang.</h2>
        <ol><li><span>01</span><div><strong>Siapkan sumber</strong><p>Pilih video, artikel, atau cerita.</p></div></li><li><span>02</span><div><strong>Tinjau hasil</strong><p>Periksa video dan status kualitasnya.</p></div></li><li><span>03</span><div><strong>Kelola distribusi</strong><p>Pantau upload dan konfirmasi platform.</p></div></li></ol>
        <a href={summary.attention ? "/#automation" : "/#settings"}>{summary.attention ? `${summary.attention} upload ditangani sistem` : "Kelola koneksi platform"}<ArrowRight size={16} /></a>
      </aside>
    </div>
  </div>;
}
