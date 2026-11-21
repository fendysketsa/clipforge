"use client";

import { useEffect, useState, type CSSProperties } from "react";
import { ArrowUpRight, CalendarClock, CheckCheck, ChevronLeft, ChevronRight, Clock3, Film, History, Link2, Music2, MonitorPlay, Search, Smartphone, StopCircle, Trash2, Youtube } from "lucide-react";
import { sourceRecoveryForJob } from "../../lib/sourceRecovery";
import { API_BASE } from "../../lib/apiClient";
import { statusCopy, statusIcon } from "../../lib/constants";
import { formatDuration, jobElapsedSeconds } from "../../lib/utils";
import type { ClipJob, JobStatus, TikTokUploadJob, YouTubeUploadJob } from "../../types/clip.type";
import {articleText, articleFilmText, isArticlePresenterPrompt} from "../../lib/storyInput";
import { uploadQueuePosition } from "../../lib/uploadQueue";
import { tiktokAutomaticRetryLabel, tiktokUploadForClip } from "../../lib/tiktokRetry";
import { automaticHandlingView, automaticUploadSummary } from "../../lib/automaticHandling";
import { queueDate } from "../../lib/studioQueue";

function jobFormat(job: ClipJob) {
  if (job.request.clip_mode === "highlight_5m") {
    if (job.clips.some(clip => clip.long_format === "compilation")) {
      return { aspect: "16:9", kind: "long", label: "KOMPILASI", title: "Kompilasi Momen" } as const;
    }
    return { aspect: "16:9", kind: "long", label: "LONG", title: "Long Highlight" } as const;
  }
  if (job.request.clip_mode === "long_animate") {
    if (isArticlePresenterPrompt(job.request.script_text || "")) {
      return { aspect: "9:16", kind: "story", label: "PRESENTASI", title: "Presenter Animasi" } as const;
    }
    return { aspect: job.request.story_aspect_ratio || "9:16", kind: "story", label: "LONG CERITA", title: "Generator Cerita" } as const;
  }
  return { aspect: "9:16", kind: "short", label: "SHORT", title: "Viral Short" } as const;
}

type HistorySectionProps = {
  jobs: ClipJob[];
  youtubeUploads: YouTubeUploadJob[];
  tiktokUploads: TikTokUploadJob[];
  selectedJobIds: string[];
  onDeleteAll: () => void;
  onDeleteFailed: () => void;
  onDeleteJob: (jobId: string) => void;
  onDeleteSelected: () => void;
  onSelectJob: (job: ClipJob) => void;
  onStopJob: (jobId: string) => void;
  onToggleJobSelection: (jobId: string) => void;
};

type PlatformUpload = YouTubeUploadJob | TikTokUploadJob;
type PlatformUploadState = JobStatus | "idle" | "partial" | "verified" | "unverified";

type PlatformUploadSummary = {
  state: PlatformUploadState;
  label: string;
  title: string;
  queueHint?: string;
};

type AutomaticIntake = {
  enabled?: boolean;
  checked_epoch?: number;
  clips?: { source_job_id: string; clip_url: string; status?: string }[];
};

function intakeSummary(job: ClipJob, intake: AutomaticIntake | null): PlatformUploadSummary | null {
  if (!intake?.enabled) return null;
  const rows = intake.clips?.filter((row) => row.source_job_id === job.id) ?? [];
  if (!rows.length) return null;
  if (rows.some((row) => row.status === "waiting_for_long_qc")) {
    return { state: "unverified", label: "Menunggu QC Long", title: "Video menunggu audit kualitas sebelum upload otomatis." };
  }
  if (rows.some((row) => row.status === "preflight_hold")) {
    return { state: "unverified", label: "Tertahan pemeriksaan", title: "Upload otomatis menunggu pemeriksaan file atau metadata backend." };
  }
  if (rows.some((row) => row.status === "needs_remote_verification")) {
    return { state: "unverified", label: "Menunggu verifikasi", title: "Sistem memeriksa hasil request sebelumnya agar video tidak terupload dua kali." };
  }
  if (rows.some((row) => row.status === "submitting")) {
    return { state: "queued", label: "Menyiapkan upload", title: "Metadata dan antrean sedang disiapkan otomatis oleh server." };
  }
  if (rows.some((row) => !row.status || row.status === "pending")) {
    return { state: "queued", label: "Antrean otomatis", title: "Server melanjutkan upload Private setelah antrean sebelumnya selesai." };
  }
  return null;
}

function uploadSummary<T extends PlatformUpload>(
  job: ClipJob,
  uploads: T[],
  isVerified: (upload: T) => boolean,
  tiktok = false,
): PlatformUploadSummary {
  const relevant = uploads
    .filter((upload) => upload.source_job_id === job.id && !upload.attention_archived_at)
    .sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at));
  if (!relevant.length) {
    return { state: "idle", label: job.request.review_only ? "Mode review" : "Menunggu penanganan otomatis",
      title: job.request.review_only ? "Mode review tidak masuk upload otomatis."
        : "Belum ada catatan upload; sistem memeriksa kelayakan sebelum menyiapkan pengiriman." };
  }

  const latestByClip = new Map<string, T>();
  relevant.forEach((upload) => {
    if (!latestByClip.has(upload.clip_url)) latestByClip.set(upload.clip_url, upload);
  });
  if (tiktok) {
    for (const clipUrl of latestByClip.keys()) {
      const state = tiktokUploadForClip(relevant as TikTokUploadJob[], clipUrl);
      if (state.uncertain) return {
        state: "unverified", label: "Menunggu verifikasi Post",
        title: "Sistem mencocokkan percobaan yang sudah mencapai Post sebelum pengiriman berikutnya agar tidak dobel.",
      };
      if (state.latest) latestByClip.set(clipUrl, state.latest as T);
    }
  }
  const latest = [...latestByClip.values()];
  const expectedClipUrls = new Set([
    ...job.clips.map((clip) => clip.url),
    ...latest.map((upload) => upload.clip_url),
  ]);
  const total = Math.max(1, expectedClipUrls.size);
  const verified = latest.filter(isVerified).length;
  const statuses = new Set(latest.map((upload) => upload.status));
  const failed = latest.find((upload) => upload.status === "failed");

  if (statuses.has("running")) {
    const queue = uploadQueuePosition(latest.find((upload) => upload.status === "running"), uploads);
    return {
      state: "running",
      label: queue?.position ? `Mengunggah · ${queue.position}/${queue.total}`
        : verified ? `Mengunggah · ${verified}/${total} terverifikasi` : "Sedang mengunggah",
      title: "Upload sedang berlangsung dan belum seluruhnya terverifikasi.",
      queueHint: queue?.hint,
    };
  }
  if (statuses.has("queued")) {
    const next = latest.filter((upload) => upload.status === "queued")
      .sort((left, right) => (left.queue_position ?? Infinity) - (right.queue_position ?? Infinity))[0];
    const queue = uploadQueuePosition(next, uploads);
    return {
      state: "queued",
      label: queue?.position ? `Antrean ${queue.position}/${queue.total}`
        : verified ? `Antrean · ${verified}/${total} terverifikasi` : "Menunggu antrean",
      title: queue ? `Urutan proses platform ini, termasuk upload aktif. ${queue.hint}.` : "Upload sudah masuk antrean backend.",
      queueHint: queue?.hint,
    };
  }
  if (failed) {
    const retry = "auto_retry_at" in failed ? tiktokAutomaticRetryLabel(failed as TikTokUploadJob) : null;
    if (retry) return { state: "queued", label: "Ulang otomatis", title: retry, queueHint: retry };
    return {
      state: "failed",
      label: verified ? `${verified}/${total} terverifikasi · pemulihan` : "Menunggu pemulihan",
      title: failed.error || "Percobaan terakhir gagal; penanganan berikutnya mengikuti pemeriksaan otomatis backend.",
    };
  }
  if (verified >= total) {
    return {
      state: "verified",
      label: total > 1 ? `Terverifikasi ${verified}/${total}` : "Terupload & terverifikasi",
      title: "Backend telah mengonfirmasi upload nyata ke platform.",
    };
  }
  if (verified > 0) {
    return {
      state: "partial",
      label: `${verified}/${total} terverifikasi`,
      title: "Sebagian klip sudah terverifikasi di platform; sisanya belum.",
    };
  }
  if (statuses.has("completed")) {
    return {
      state: "unverified",
      label: "Selesai, belum terverifikasi",
      title: "Catatan proses selesai, tetapi backend belum memiliki bukti upload nyata yang lengkap.",
    };
  }
  if (statuses.has("cancelled")) {
    return { state: "cancelled", label: "Upload dibatalkan", title: "Proses upload dibatalkan." };
  }
  return { state: "idle", label: "Menunggu penanganan otomatis", title: "Belum ada upload terverifikasi; sistem memeriksa langkah berikutnya." };
}

export function HistorySection({
  jobs,
  youtubeUploads,
  tiktokUploads,
  selectedJobIds,
  onDeleteAll,
  onDeleteFailed,
  onDeleteJob,
  onDeleteSelected,
  onSelectJob,
  onStopJob,
  onToggleJobSelection,
}: HistorySectionProps) {
  const hasActiveJobs = jobs.some((item) => item.status === "queued" || item.status === "running");
  const [intake, setIntake] = useState<AutomaticIntake | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [page, setPage] = useState(0);
  const failedJobs = jobs.filter((item) => item.status === "failed" || item.status === "cancelled");
  const processJobs = jobs.filter(
    (item) => item.status === "queued" || item.status === "running" || item.status === "failed" || item.status === "cancelled",
  );
  const selectedCount = selectedJobIds.length;
  const formatDate = (value: string) =>
    new Intl.DateTimeFormat("id-ID", {
      timeZone: "Asia/Jakarta",
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));

  const sourceLabel = (job: ClipJob) => {
    if (job.source_title?.trim()) return job.source_title.trim();
    if (job.request.clip_mode === "long_animate" && job.request.script_text.trim()) {
      return articleFilmText(articleText(job.request.script_text)).replace(/\s+/g, " ").slice(0, 72);
    }
    if (job.request.source_file) return job.request.source_file.split("/").pop() || "Upload video";
    if (!job.request.url) return "Video tanpa judul";
    try {
      const url = new URL(job.request.url);
      return `${url.hostname.replace(/^www\./, "")}${url.pathname}`;
    } catch {
      return job.request.url;
    }
  };

  const sourceUrl = (job: ClipJob) => job.source_url || job.request.url;
  const filteredJobs = jobs.filter(item => {
    const match = filter === "all" || (filter === "active" ? ["running", "queued"].includes(item.status)
      : filter === "failed" ? ["failed", "cancelled"].includes(item.status) : item.status === filter);
    return match && `${sourceLabel(item)} ${item.source_uploader || ""}`.toLowerCase().includes(query.toLowerCase());
  });
  const pages = Math.max(1, Math.ceil(filteredJobs.length / 12));
  const currentPage = Math.min(page, pages - 1);
  const visibleJobs = filteredJobs.slice(currentPage * 12, currentPage * 12 + 12);

  useEffect(() => {
    if (!hasActiveJobs) return;
    setNow(Date.now());
    const interval = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(interval);
  }, [hasActiveJobs]);

  useEffect(() => {
    let cancelled = false;
    let inFlight = false;
    const refresh = async () => {
      if (document.hidden || inFlight) return;
      inFlight = true;
      try {
        const response = await fetch(`${API_BASE}/outputs/_automation/upload-status.json`, { cache: "no-store", signal: AbortSignal.timeout(8000) });
        if (response.ok) {
          const snapshot = await response.json() as AutomaticIntake;
          if (!cancelled) setIntake(snapshot);
        }
      } catch { /* Uploads continue independently of this optional status feed. */ }
      finally { inFlight = false; }
    };
    void refresh();
    const timer = window.setInterval(refresh, 15000);
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, []);

  return (
    <section className="history" id="history">
      <div className="sectionHeader">
        <div className="sectionTitle">
          <span className="sectionEyebrow">Workspace</span>
          <h2>Riwayat Proses</h2>
          <p>Produksi, pemulihan, dan cleanup rutin dilanjutkan otomatis; hasil dan buktinya dapat dilihat di sini.</p>
        </div>
        <div className="historyActions">
          <span className="historyLiveCount"><span />{jobs.filter((item) => item.status === "running" || item.status === "queued").length} diproses</span>
          <span className="historyReadyCount"><CheckCheck size={15} />{jobs.filter((item) => item.status === "completed").length} selesai</span>
          <span className="sectionBadge">{jobs.length} total</span>
          {failedJobs.length > 0 ? (
            <button type="button" onClick={onDeleteFailed} className="uiButton uiButton--ghostDanger">
              <Trash2 size={16} />
              <span>Hapus gagal</span>
            </button>
          ) : null}
          {selectedCount > 0 ? (
            <button type="button" onClick={onDeleteSelected} className="uiButton uiButton--danger">
              <Trash2 size={16} />
              <span>Hapus terpilih ({selectedCount})</span>
            </button>
          ) : null}
          {processJobs.length > 0 ? (
            <button
              type="button"
              onClick={onDeleteAll}
              className="uiButton uiButton--ghostDanger"
              title="Hapus catatan job queued, running, failed, dan cancelled"
            >
              <Trash2 size={16} />
              <span>Hapus job proses ({processJobs.length})</span>
            </button>
          ) : null}
        </div>
      </div>

      <div className="studioHistoryToolbar">
        <div className="studioQueueFilters" role="group" aria-label="Filter riwayat produksi">
          {[{key:"all",label:"Semua"},{key:"active",label:"Diproses"},{key:"completed",label:"Selesai"},{key:"failed",label:"Gagal / dibatalkan"}].map(item => <button type="button" key={item.key} aria-pressed={filter === item.key} className={filter === item.key ? "isActive" : ""} onClick={() => {setFilter(item.key);setPage(0);}}>{item.label}</button>)}
        </div>
        <label className="studioSearch"><Search size={16} /><input aria-label="Cari riwayat produksi" placeholder="Cari judul atau sumber…" value={query} onChange={event => {setQuery(event.target.value);setPage(0);}} /></label>
      </div>
      <div className="jobList" data-layout="history-four-columns">
        {visibleJobs.map((item) => {
          const recovery = sourceRecoveryForJob(item, jobs);
          const handling = automaticHandlingView(item.automatic_handling);
          const handlingStatus = handling?.urgent ? "failed" : handling
            ? handling.state === "archived" ? "cancelled" : "queued" : item.status;
          const shownStatus = recovery?.status || (item.status === "running" || item.status === "queued" ? item.status : handlingStatus);
          const Icon = statusIcon[shownStatus];
          const count = item.clips.length ? `${item.clips.length} klip` : `${item.candidates.length} kandidat`;
          const canSelectForDelete = item.status !== "queued" && item.status !== "running";
          const canStop = item.status === "queued" || item.status === "running";
          const isSelected = selectedJobIds.includes(item.id);
          const url = sourceUrl(item);
          const elapsedSeconds = jobElapsedSeconds(item, now);
          const format = jobFormat(item);
          const FormatIcon = format.kind === "short" ? Smartphone : MonitorPlay;
          const isProcessing = item.status === "queued" || item.status === "running";
          const progressPercent = Math.max(0, Math.min(100, Math.round(item.progress_percent ?? 0)));
          const progressDetail =
            item.progress_detail?.trim() ||
            (item.status === "queued" ? "Menunggu slot worker" : "Memproses video");
          const recordedYoutubeSummary = item.status === "completed"
            ? uploadSummary(
                item,
                youtubeUploads,
                (upload) => upload.status === "completed"
                  && upload.upload_confirmed === true
                  && !upload.dry_run
                  && Boolean(upload.video_url),
              )
            : null;
          const intakeYoutubeSummary = recordedYoutubeSummary && (recordedYoutubeSummary.state === "idle" || recordedYoutubeSummary.state === "failed")
            ? intakeSummary(item, intake) ?? recordedYoutubeSummary
            : recordedYoutubeSummary;
          const youtubeSummary: PlatformUploadSummary | null = intakeYoutubeSummary
            ? automaticUploadSummary(item.automatic_handling, intakeYoutubeSummary.state) ?? intakeYoutubeSummary : null;
          const recordedTiktokSummary = item.status === "completed"
            ? uploadSummary(
                item,
                tiktokUploads,
                (upload) => upload.status === "completed" && upload.upload_confirmed && !upload.dry_run && Boolean(upload.profile_url),
                true,
              )
            : null;

          const tiktokHold = item.clips.find((clip) => clip.tiktok_upload_issue)?.tiktok_upload_issue;
          const holdTiktokSummary: PlatformUploadSummary | null = recordedTiktokSummary?.state === "idle" && tiktokHold
            ? { state: "unverified", label: "Tertahan pemeriksaan", title: tiktokHold }
            : recordedTiktokSummary;
          const automaticTiktokSummary = holdTiktokSummary
            ? automaticUploadSummary(item.automatic_handling, holdTiktokSummary.state) : null;
          const tiktokSummary: PlatformUploadSummary | null = automaticTiktokSummary
            ? { ...automaticTiktokSummary, title: tiktokHold ? `${automaticTiktokSummary.title} Batas pemeriksaan: ${tiktokHold}` : automaticTiktokSummary.title }
            : holdTiktokSummary;

          const thumbnail = item.clips.find((clip) => clip.thumbnail_url)?.thumbnail_url;
          const score = Math.max(0, ...item.clips.map((clip) => clip.fyp_score ?? 0));

          return (
            <article
              className={`jobRow jobRow--${shownStatus}${recovery ? " hasSourceRecovery" : ""} ${isSelected ? "selected" : ""}`}
              key={item.id}
              style={{ "--job-progress": `${item.status === "completed" ? 100 : progressPercent}%` } as CSSProperties}
            >
              {canSelectForDelete ? (
                <input
                  aria-label={`Pilih riwayat ${statusCopy[item.status]} untuk dihapus`}
                  checked={isSelected}
                  className="jobSelect"
                  type="checkbox"
                  onChange={() => onToggleJobSelection(item.id)}
                />
              ) : null}
              <button className="jobRowMain" type="button" onClick={() => onSelectJob(recovery || item)} aria-label={`Buka ${recovery ? "pemulihan " : ""}${sourceLabel(item)}`}>
                <div className={`jobCardPreview${thumbnail ? " hasThumbnail" : ""}`}>
                  {thumbnail ? <img src={`${API_BASE}${thumbnail}`} alt="" loading="lazy" onError={(event) => { event.currentTarget.style.display = "none"; }} /> : null}
                  <div className="jobCardPreviewFallback"><FormatIcon size={32} strokeWidth={1.3} /><span>{format.title}</span></div>
                  <span className={`jobFormatBadge jobFormatBadge--${format.kind}`}><FormatIcon size={13} />{format.label} · {format.aspect}</span>
                  <span className="jobPreviewOpen"><ArrowUpRight size={18} /></span>
                </div>
                <div className="jobCardBody">
                <div className="jobRowTop">
                  <span className={`jobRow-status status-${shownStatus}`}>
                    <span className="jobRow-statusIcon">
                      <Icon className={shownStatus === "running" ? "spin" : ""} size={15} />
                    </span>
                    <span className="jobRow-statusLabel">{recovery ? recovery.status === "completed" ? "Sumber pulih" : "Sedang dipulihkan" : handling?.label || statusCopy[item.status]}</span>
                    {isProcessing ? <span className="jobRow-statusPercent">{progressPercent}%</span> : null}
                  </span>
                  <span className="jobClipCount"><Film size={13} />{count}</span>
                </div>
                <h3 title={sourceLabel(item)}>{sourceLabel(item)}</h3>
                <div className={`jobRowContent${youtubeSummary && tiktokSummary ? " hasPlatforms" : ""}`}>
                  <div className="jobRowCore">
                    {isProcessing ? (
                      <div className="jobProgress" title={progressDetail}>
                        <div className="jobProgressMeta">
                          <span>{progressDetail}</span>
                          <b>{progressPercent}% selesai</b>
                        </div>
                        <div
                          aria-label={`Progres proses ${progressPercent}%`}
                          aria-valuemax={100}
                          aria-valuemin={0}
                          aria-valuenow={progressPercent}
                          className="jobProgressTrack"
                          role="progressbar"
                        >
                          <span className="jobProgressFill" style={{ width: `${progressPercent}%` }} />
                        </div>
                    </div>
                    ) : null}
                    {recovery ? <div className="jobSourceRecovery"><strong>{recovery.status === "completed" ? "Percobaan berikutnya sudah menghasilkan video." : "Sumber yang sama sedang diproses kembali."}</strong>
                      <p>{recovery.status === "completed" ? "Buka hasil untuk meninjau kualitas dan status upload." : recovery.progress_detail || "Sistem melanjutkan pemulihan; Anda tidak perlu membuat job baru."}</p>
                      <small>{recovery.status === "completed" ? `${recovery.clips.length} hasil tersedia` : `${Math.round(recovery.progress_percent || 0)}% · ${statusCopy[recovery.status]}`}</small>
                    </div> : handling ? <div className="jobSourceRecovery jobAutomaticHandling">
                      <strong>{handling.label}</strong><p>{handling.detail}</p>
                      {handling.nextCheckAt ? <small>Pemeriksaan berikutnya: {queueDate(handling.nextCheckAt)}</small> : null}
                    </div> : item.error ? <p className="jobCardError" title={item.error}>{item.error}</p> : null}
                    {item.director_recovery?.summary ? (
                      <div className="jobDirectorRecovery">
                        <strong>{item.director_recovery.outcome === "source_replaced" ? "Sumber pengganti diproses" : "Rencana sutradara"}</strong>
                        <span>{item.director_recovery.summary}</span>
                        {item.director_recovery.next_source_title ? <small>{item.director_recovery.next_source_title}</small> : null}
                      </div>
                    ) : null}
                    <div className="jobSourceLine" title={url || "Upload lokal"}>
                      <Link2 size={14} />
                      <span>{item.source_uploader || url || "Upload lokal"}</span>
                    </div>
                    <div className="jobDetailGrid">
                      <span>
                        <CalendarClock size={13} />
                        <small>Dibuat</small>
                        <b>{formatDate(item.created_at)}</b>
                      </span>
                      {elapsedSeconds !== null ? (
                        <span>
                          <Clock3 size={13} />
                          <small>Durasi proses</small>
                          <b>{formatDuration(elapsedSeconds)}</b>
                        </span>
                      ) : null}
                      <span>
                        <small>Preset</small>
                        <b>{item.request.crop_mode} · {item.request.video_quality}</b>
                      </span>
                      <span title={item.request.ai_enabled ? item.request.ai_model || "AI lokal" : "AI nonaktif"}>
                        <small>{score ? "Skor FYP" : "Pipeline"}</small>
                        <b>{score ? `${score}/100` : item.request.ai_enabled ? "Auto FYP · AI" : "Auto FYP"}</b>
                      </span>
                    </div>
                  </div>
                  {youtubeSummary && tiktokSummary ? (
                    <div className="jobPlatformStatuses" aria-label="Status upload YouTube dan TikTok">
                      <span
                        className={`jobPlatformStatus state-${youtubeSummary.state}`}
                        title={youtubeSummary.title}
                      >
                        <Youtube size={15} />
                        <span>
                          <small>YouTube</small><strong>{youtubeSummary.label}</strong>
                          {youtubeSummary.queueHint ? <em className="jobPlatformQueue">{youtubeSummary.queueHint}</em> : null}
                        </span>
                      </span>
                      <span
                        className={`jobPlatformStatus state-${tiktokSummary.state}`}
                        title={tiktokSummary.title}
                      >
                        <Music2 size={15} />
                        <span>
                          <small>TikTok</small><strong>{tiktokSummary.label}</strong>
                          {tiktokSummary.queueHint ? <em className="jobPlatformQueue">{tiktokSummary.queueHint}</em> : null}
                          {!handling && recordedTiktokSummary?.state === "idle" && tiktokHold ? <em className="jobPlatformHold">{tiktokHold}</em> : null}
                        </span>
                      </span>
                    </div>
                  ) : null}
                </div>
                <span className="jobOpenHint"><span>{recovery ? "Lihat pemulihan sumber" : isProcessing ? "Lihat progres" : handling ? "Lihat catatan penanganan" : item.status === "failed" ? "Lihat detail kegagalan" : "Buka hasil video"}</span><ArrowUpRight size={16} /></span>
                </div>
              </button>
              {(recovery || handling) && item.error ? <details className="jobPreviousFailure"><summary>Rincian percobaan sebelumnya</summary><p>{item.error}</p></details> : null}
              {handling && tiktokHold ? <details className="jobPreviousFailure"><summary>Dasar pemeriksaan publikasi</summary><p>{tiktokHold}</p></details> : null}
              {canStop ? (
                <button
                  className="uiButton uiButton--ghostDanger stopJobRowButton"
                  type="button"
                  onClick={() => onStopJob(item.id)}
                  title="Stop proses running/queued"
                >
                  <StopCircle size={15} />
                  <span>Stop</span>
                </button>
              ) : null}
              {canSelectForDelete ? (
                <button
                  aria-label={`Hapus riwayat ${statusCopy[item.status]}`}
                  className="uiButton uiButton--ghostDanger deleteJobRowButton"
                  type="button"
                  onClick={() => onDeleteJob(item.id)}
                  title="Hapus kartu dari riwayat"
                >
                  <Trash2 size={15} />
                  <span className="jobDeleteLabel">Hapus</span>
                </button>
              ) : null}
            </article>
          );
        })}
      </div>
      {!filteredJobs.length ? (
        <div className="emptyState historyEmptyState">
          <History className="emptyStateIcon" size={30} />
          <p>{jobs.length ? "Tidak ada riwayat yang cocok." : "Belum ada riwayat proses."}</p>
          <p className="emptyStateHint">{jobs.length ? "Ubah pencarian atau pilih filter lain." : "Video yang Anda buat akan tersimpan dan tampil di sini."}</p>
        </div>
      ) : null}
      {filteredJobs.length > 12 ? <footer className="studioPagination"><span>{currentPage * 12 + 1}–{Math.min((currentPage + 1) * 12, filteredJobs.length)} dari {filteredJobs.length} proses</span><div><button type="button" aria-label="Halaman riwayat sebelumnya" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}><ChevronLeft size={16} /></button><button type="button" aria-label="Halaman riwayat berikutnya" disabled={currentPage === pages - 1} onClick={() => setPage(currentPage + 1)}><ChevronRight size={16} /></button></div></footer> : null}
    </section>
  );
}
