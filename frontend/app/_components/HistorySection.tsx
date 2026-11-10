"use client";

import { useEffect, useState, type CSSProperties } from "react";
import { ArrowUpRight, CalendarClock, CheckCheck, Clock3, Film, History, Link2, Music2, MonitorPlay, Smartphone, StopCircle, Trash2, Youtube } from "lucide-react";
import { API_BASE } from "../../lib/apiClient";
import { statusCopy, statusIcon } from "../../lib/constants";
import { formatDuration, jobElapsedSeconds } from "../../lib/utils";
import type { ClipJob, JobStatus, TikTokUploadJob, YouTubeUploadJob } from "../../types/clip.type";
import {articleText, articleFilmText, isArticlePresenterPrompt} from "../../lib/storyInput";
import { uploadQueuePosition } from "../../lib/uploadQueue";

function jobFormat(job: ClipJob) {
  if (job.request.clip_mode === "highlight_5m") {
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
    return { state: "queued", label: "Antrean otomatis", title: "Operator akan melanjutkan upload Private setelah antrean sebelumnya selesai." };
  }
  return null;
}

function uploadSummary<T extends PlatformUpload>(
  job: ClipJob,
  uploads: T[],
  isVerified: (upload: T) => boolean,
): PlatformUploadSummary {
  const relevant = uploads
    .filter((upload) => upload.source_job_id === job.id)
    .sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at));
  if (!relevant.length) {
    return { state: "idle", label: "Belum diunggah", title: "Belum ada proses upload untuk job ini." };
  }

  const latestByClip = new Map<string, T>();
  relevant.forEach((upload) => {
    if (!latestByClip.has(upload.clip_url)) latestByClip.set(upload.clip_url, upload);
  });
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
    return {
      state: "failed",
      label: verified ? `${verified}/${total} berhasil · ada gagal` : "Upload gagal",
      title: failed.error || "Upload terakhir gagal dan perlu dicoba ulang.",
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
  return { state: "idle", label: "Belum diunggah", title: "Belum ada upload yang terverifikasi." };
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
          <p>Progres produksi, hasil video, dan status upload dalam satu tempat.</p>
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

      <div className="jobList" data-layout="history-four-columns">
        {jobs.map((item) => {
          const Icon = statusIcon[item.status];
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
          const youtubeSummary = recordedYoutubeSummary && (recordedYoutubeSummary.state === "idle" || recordedYoutubeSummary.state === "failed")
            ? intakeSummary(item, intake) ?? recordedYoutubeSummary
            : recordedYoutubeSummary;
          const recordedTiktokSummary = item.status === "completed"
            ? uploadSummary(
                item,
                tiktokUploads,
                (upload) => upload.status === "completed" && upload.upload_confirmed && !upload.dry_run,
              )
            : null;

          const tiktokHold = item.clips.find((clip) => clip.tiktok_upload_issue)?.tiktok_upload_issue;
          const tiktokSummary: PlatformUploadSummary | null = recordedTiktokSummary?.state === "idle" && tiktokHold
            ? { state: "unverified", label: "Tertahan pemeriksaan", title: tiktokHold }
            : recordedTiktokSummary;

          const thumbnail = item.clips.find((clip) => clip.thumbnail_url)?.thumbnail_url;
          const score = Math.max(0, ...item.clips.map((clip) => clip.fyp_score ?? 0));

          return (
            <article
              className={`jobRow jobRow--${item.status} ${isSelected ? "selected" : ""}`}
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
              <button className="jobRowMain" type="button" onClick={() => onSelectJob(item)} aria-label={`Buka ${sourceLabel(item)}`}>
                <div className={`jobCardPreview${thumbnail ? " hasThumbnail" : ""}`}>
                  {thumbnail ? <img src={`${API_BASE}${thumbnail}`} alt="" loading="lazy" onError={(event) => { event.currentTarget.style.display = "none"; }} /> : null}
                  <div className="jobCardPreviewFallback"><FormatIcon size={32} strokeWidth={1.3} /><span>{format.title}</span></div>
                  <span className={`jobFormatBadge jobFormatBadge--${format.kind}`}><FormatIcon size={13} />{format.label} · {format.aspect}</span>
                  <span className="jobPreviewOpen"><ArrowUpRight size={18} /></span>
                </div>
                <div className="jobCardBody">
                <div className="jobRowTop">
                  <span className={`jobRow-status status-${item.status}`}>
                    <span className="jobRow-statusIcon">
                      <Icon className={item.status === "running" ? "spin" : ""} size={15} />
                    </span>
                    <span className="jobRow-statusLabel">{statusCopy[item.status]}</span>
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
                    {item.error ? <p className="jobCardError" title={item.error}>{item.error}</p> : null}
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
                          {recordedTiktokSummary?.state === "idle" && tiktokHold ? <em className="jobPlatformHold">{tiktokHold}</em> : null}
                        </span>
                      </span>
                    </div>
                  ) : null}
                </div>
                <span className="jobOpenHint"><span>{isProcessing ? "Lihat progres" : "Buka hasil video"}</span><ArrowUpRight size={16} /></span>
                </div>
              </button>
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
      {!jobs.length ? (
        <div className="emptyState historyEmptyState">
          <History className="emptyStateIcon" size={30} />
          <p>Belum ada riwayat proses.</p>
          <p className="emptyStateHint">Job yang Anda jalankan akan tersimpan dan tampil di bagian ini.</p>
        </div>
      ) : null}
    </section>
  );
}
