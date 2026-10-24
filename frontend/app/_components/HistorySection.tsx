"use client";

import { useEffect, useState } from "react";
import { CalendarClock, Clock3, ExternalLink, Film, History, Link2, Music2, MonitorPlay, Smartphone, StopCircle, Trash2, Youtube } from "lucide-react";
import { statusCopy, statusIcon } from "../../lib/constants";
import { formatDuration, jobElapsedSeconds } from "../../lib/utils";
import type { ClipJob, JobStatus, TikTokUploadJob, YouTubeUploadJob } from "../../types/clip.type";

function jobFormat(job: ClipJob) {
  if (job.request.clip_mode === "highlight_5m") {
    return { aspect: "16:9", kind: "long", label: "LONG", title: "Long Highlight" } as const;
  }
  if (job.request.clip_mode === "long_animate") {
    return { aspect: "9:16", kind: "story", label: "LONG CERITA", title: "Generator Cerita" } as const;
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
};

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
    return {
      state: "running",
      label: verified ? `Mengunggah · ${verified}/${total} terverifikasi` : "Sedang mengunggah",
      title: "Upload sedang berlangsung dan belum seluruhnya terverifikasi.",
    };
  }
  if (statuses.has("queued")) {
    return {
      state: "queued",
      label: verified ? `Antrean · ${verified}/${total} terverifikasi` : "Menunggu antrean",
      title: "Upload sudah masuk antrean backend.",
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
  onDeleteSelected,
  onSelectJob,
  onStopJob,
  onToggleJobSelection,
}: HistorySectionProps) {
  const hasActiveJobs = jobs.some((item) => item.status === "queued" || item.status === "running");
  const [now, setNow] = useState(() => Date.now());
  const failedJobs = jobs.filter((item) => item.status === "failed" || item.status === "cancelled");
  const processJobs = jobs.filter(
    (item) => item.status === "queued" || item.status === "running" || item.status === "failed" || item.status === "cancelled",
  );
  const selectedCount = selectedJobIds.length;
  const formatDate = (value: string) =>
    new Intl.DateTimeFormat("id-ID", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));

  const sourceLabel = (job: ClipJob) => {
    if (job.source_title?.trim()) return job.source_title.trim();
    if (job.request.clip_mode === "long_animate" && job.request.script_text.trim()) {
      return job.request.script_text.trim().replace(/\s+/g, " ").slice(0, 72);
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

  return (
    <section className="history" id="history">
      <div className="sectionHeader">
        <div className="sectionTitle">
          <span className="sectionEyebrow">Workspace</span>
          <h2>Riwayat Proses</h2>
          <p>Lihat kembali proses dan buka hasil klip sebelumnya.</p>
        </div>
        <div className="historyActions">
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
              className="uiButton uiButton--danger"
              title="Hapus catatan job queued, running, failed, dan cancelled"
            >
              <Trash2 size={16} />
              <span>Hapus job proses ({processJobs.length})</span>
            </button>
          ) : null}
        </div>
      </div>

      <div className="jobList">
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
          const youtubeSummary = item.status === "completed"
            ? uploadSummary(
                item,
                youtubeUploads,
                (upload) => upload.status === "completed"
                  && upload.upload_confirmed === true
                  && !upload.dry_run
                  && Boolean(upload.video_url),
              )
            : null;
          const tiktokSummary = item.status === "completed"
            ? uploadSummary(
                item,
                tiktokUploads,
                (upload) => upload.status === "completed" && upload.upload_confirmed && !upload.dry_run,
              )
            : null;

          return (
            <div className={`jobRow ${isSelected ? "selected" : ""}`} key={item.id}>
              {canSelectForDelete ? (
                <input
                  aria-label={`Pilih riwayat ${statusCopy[item.status]} untuk dihapus`}
                  checked={isSelected}
                  className="jobSelect"
                  type="checkbox"
                  onChange={() => onToggleJobSelection(item.id)}
                />
              ) : null}
              <button className="jobRowMain" type="button" onClick={() => onSelectJob(item)}>
                <div className="jobRowTop">
                  <span className={`jobRow-status status-${item.status}`}>
                    <Icon className={item.status === "running" ? "spin" : ""} size={16} />
                    {statusCopy[item.status]}
                    {isProcessing ? <span className="jobRow-statusPercent">{progressPercent}%</span> : null}
                  </span>
                  <div className="jobRowTopMeta">
                    <span
                      className={`jobFormatBadge jobFormatBadge--${format.kind}`}
                      title={`${format.title}, rasio ${format.aspect}`}
                    >
                      <FormatIcon size={14} />
                      {format.label} · {format.aspect}
                    </span>
                    <strong>
                      <Film size={14} />
                      {count}
                    </strong>
                  </div>
                </div>
                <h3>{sourceLabel(item)}</h3>
                {youtubeSummary && tiktokSummary ? (
                  <div className="jobPlatformStatuses" aria-label="Status upload YouTube dan TikTok">
                    <span
                      className={`jobPlatformStatus state-${youtubeSummary.state}`}
                      title={youtubeSummary.title}
                    >
                      <Youtube size={15} />
                      <span><small>YouTube</small><strong>{youtubeSummary.label}</strong></span>
                    </span>
                    <span
                      className={`jobPlatformStatus state-${tiktokSummary.state}`}
                      title={tiktokSummary.title}
                    >
                      <Music2 size={15} />
                      <span><small>TikTok</small><strong>{tiktokSummary.label}</strong></span>
                    </span>
                  </div>
                ) : null}
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
                <div className="jobSourceLine">
                  <Link2 size={14} />
                  <span>{url || "Upload lokal"}</span>
                </div>
                <div className="jobDetailGrid">
                  <span>
                    <CalendarClock size={13} />
                    {formatDate(item.created_at)}
                  </span>
                  {item.source_uploader ? <span>{item.source_uploader}</span> : null}
                  {elapsedSeconds !== null ? (
                    <span>
                      <Clock3 size={13} />
                      {formatDuration(elapsedSeconds)}
                    </span>
                  ) : null}
                  <span>{item.request.crop_mode}</span>
                  <span>{item.request.video_quality}</span>
                  <span>Auto FYP adaptif</span>
                  {item.request.ai_enabled ? <span>AI: {item.request.ai_model || "local"}</span> : <span>AI off</span>}
                </div>
                {url ? (
                  <span className="jobOpenHint">
                    <ExternalLink size={13} />
                    Klik kartu untuk membuka hasil klip
                  </span>
                ) : null}
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
            </div>
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
