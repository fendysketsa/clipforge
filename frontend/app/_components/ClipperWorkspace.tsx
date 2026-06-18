"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  Clipboard,
  Clock3,
  Download,
  ExternalLink,
  Loader2,
  Play,
  RefreshCw,
  Scissors,
  XCircle,
  Activity,
  Video,
  Trash2,
} from "lucide-react";
import toast from "react-hot-toast";
import { createJob, getJob, getJobs, getOutputUrl, deleteJobs } from "../../lib/apiClient";
import type { ClipJob, CropMode, JobStatus } from "../../types/clip.type";

const statusCopy: Record<JobStatus, string> = {
  queued: "Queued",
  running: "Processing",
  completed: "Completed",
  failed: "Failed",
};

const statusIcon = {
  queued: Clock3,
  running: Loader2,
  completed: CheckCircle2,
  failed: XCircle,
};

function clipTitle(name: string) {
  return name.replace(/\.mp4$/i, "").replace(/^clip_\d+_/, "").replace(/-/g, " ");
}

async function handleDownload(url: string, filename: string) {
  const downloadPromise = async () => {
    const response = await fetch(url);
    if (!response.ok) throw new Error("Gagal mengunduh file");
    const blob = await response.blob();
    const blobUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = blobUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(blobUrl);
  };

  toast.promise(downloadPromise(), {
    loading: 'Mengunduh klip...',
    success: 'Klip berhasil diunduh!',
    error: 'Gagal mengunduh klip',
  }).catch(() => {
    window.open(url, "_blank");
  });
}

async function handleCopyTitle(title: string) {
  await navigator.clipboard.writeText(title);
  toast.success("Judul klip berhasil disalin");
}

export const ClipperWorkspace = () => {
  const [url, setUrl] = useState("");
  const [minDuration, setMinDuration] = useState(35);
  const [maxDuration, setMaxDuration] = useState(180);
  const [cropMode, setCropMode] = useState<CropMode>("person");
  const [job, setJob] = useState<ClipJob | null>(null);
  const [jobs, setJobs] = useState<ClipJob[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  const activeJobId = job?.id;
  const isBusy = job?.status === "queued" || job?.status === "running";

  async function loadJobs() {
    setJobs(await getJobs());
  }

  useEffect(() => {
    loadJobs().catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!activeJobId) return;

    const interval = window.setInterval(async () => {
      const nextJob = await getJob(activeJobId);
      setJob(nextJob);
      if (nextJob.status === "completed" || nextJob.status === "failed") {
        loadJobs().catch(() => undefined);
      }
    }, 2200);

    return () => window.clearInterval(interval);
  }, [activeJobId]);

  const latestLogs = useMemo(() => job?.logs.slice(-10) ?? [], [job]);

  async function handleStartJob() {
    setError("");
    if (!url.trim()) {
      setError("Link YouTube tidak boleh kosong.");
      return;
    }
    setIsSubmitting(true);

    try {
      const jobPromise = createJob({
        url,
        min_duration: minDuration,
        max_duration: maxDuration,
        model: "Systran/faster-whisper-small",
        language: "id",
        burn_subtitles: true,
        crop_mode: cropMode,
      });

      const nextJob = await toast.promise(jobPromise, {
        loading: 'Mempersiapkan proses pemotongan...',
        success: 'Proses pemotongan berhasil dimulai!',
        error: 'Gagal memulai proses pemotongan',
      });

      setJob(nextJob);
      await loadJobs();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Gagal memulai proses.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleDeleteAll() {
    toast((t) => (
      <div className="confirmToast">
        <div className="confirmToast-copy">
          <strong>Hapus seluruh riwayat dan output?</strong>
          <p>
          Semua job dan file video di folder outputs akan dihapus.
          </p>
        </div>
        <div className="confirmToast-actions">
          <button className="ghostButton" type="button" onClick={() => toast.dismiss(t.id)}>
            Batal
          </button>
          <button
            className="dangerButton"
            type="button"
            onClick={async () => {
              toast.dismiss(t.id);
              try {
                const deletePromise = deleteJobs();
                await toast.promise(deletePromise, {
                  loading: 'Menghapus riwayat...',
                  success: 'Seluruh riwayat berhasil dihapus!',
                  error: 'Gagal menghapus riwayat',
                });
                setJob(null);
                await loadJobs();
              } catch (err) {
                // error handled by toast
              }
            }}
          >
            Hapus Semua
          </button>
        </div>
      </div>
    ), { duration: Infinity });
  }

  const StatusIcon = job ? statusIcon[job.status] : Activity;

  return (
    <main className="shell">
      <section className="topbar">
        <div className="topbar-brand">
          <img className="brandMark" src="/logo.svg" alt="" aria-hidden="true" />
          <div className="brandCopy">
            <h1 className="logo-text">ClipForge</h1>
            <p className="tagline">Turn long videos into ready-to-post clips.</p>
          </div>
        </div>
        <button className="iconButton" type="button" onClick={() => loadJobs()} title="Refresh data">
          <RefreshCw size={18} />
        </button>
      </section>

      <section className="workspace">
        <section className="panel controlPanel">
          <div className="panelHeader">
            <Scissors size={20} />
            <h2>Potong Video YouTube</h2>
          </div>

          <label className="field wide">
            <span>Link Video YouTube</span>
            <input
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://www.youtube.com/watch?v=..."
              required
            />
            <p className="field-help">Pastikan video memiliki percakapan yang jelas untuk hasil transkripsi terbaik.</p>
          </label>

          <div className="gridFields">
            <label className="field">
              <span>Durasi Minimum</span>
              <input
                min={5}
                max={600}
                type="number"
                value={minDuration}
                onChange={(event) => setMinDuration(Number(event.target.value))}
              />
            </label>
            <label className="field">
              <span>Durasi Maksimum</span>
              <input
                min={10}
                max={600}
                type="number"
                value={maxDuration}
                onChange={(event) => setMaxDuration(Number(event.target.value))}
              />
            </label>
          </div>

          <div className="segmentedField">
            <span>Mode Crop</span>
            <div className="segmentedControl" role="group" aria-label="Mode crop video">
              <button
                className={cropMode === "center" ? "active" : ""}
                type="button"
                onClick={() => setCropMode("center")}
              >
                Center
              </button>
              <button
                className={cropMode === "person" ? "active" : ""}
                type="button"
                onClick={() => setCropMode("person")}
              >
                Follow Person
              </button>
            </div>
          </div>

          {error ? <p className="error">{error}</p> : null}

          <button className="primary" type="button" disabled={isSubmitting || isBusy || !url.trim()} onClick={handleStartJob}>
            {isSubmitting || isBusy ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
            {isSubmitting || isBusy ? "Sedang Memproses..." : "Mulai Potong Video"}
          </button>
        </section>

        <section className="panel statusPanel">
          <div className="panelHeader">
            <StatusIcon className={job?.status === "running" ? "spin" : ""} size={20} />
            <h2>Aktivitas</h2>
          </div>

          {job ? (
            <div className="activityContent">
              <div className="jobMeta">
                <span>{job.request.top ?? "Auto"} klip target</span>
                <span>{job.request.min_duration}s - {job.request.max_duration}s</span>
                <span>{job.request.analyze_seconds ? `Test: ${job.request.analyze_seconds}s` : "Full video"}</span>
                <span>{job.request.crop_mode === "person" ? "Follow person" : "Center crop"}</span>
              </div>

              <div className="logBox">
                {latestLogs.length ? latestLogs.map((line, index) => <p key={`${line}-${index}`}>{line}</p>) : <p>Memulai proses pipeline...</p>}
              </div>

              {job.error ? <p className="error" style={{marginTop: "16px"}}>{job.error}</p> : null}
            </div>
          ) : (
            <div className="emptyState activityEmptyState">
              <Activity size={32} style={{ marginBottom: "12px", opacity: 0.5 }} />
              <p>Belum ada proses berjalan.</p>
              <p style={{ fontSize: "13px", marginTop: "4px" }}>Masukkan link YouTube, lalu klik <strong>Mulai Potong Video</strong> untuk memulai.</p>
            </div>
          )}
        </section>
      </section>

      <section className="results">
        <div className="sectionHeader">
          <h2>Klip Siap Digunakan</h2>
          <span className="sectionBadge">{job?.clips.length ?? 0} klip siap</span>
        </div>

        {job?.clips.length ? (
          <div className="clipGrid">
            {job.clips.map((clip) => (
              <article className="clipCard" key={clip.url}>
                <video controls preload="metadata" src={getOutputUrl(clip.url)} />
                <div className="clipInfo">
                  <h3>{clipTitle(clip.name)}</h3>
                  <button
                    className="copyTitleButton"
                    type="button"
                    onClick={() => handleCopyTitle(clipTitle(clip.name))}
                    title="Salin judul klip"
                  >
                    <Clipboard size={14} />
                    Copy
                  </button>
                </div>
                <div className="clipActions">
                  <a href={getOutputUrl(clip.url)} target="_blank" rel="noreferrer">
                    <ExternalLink size={16} />
                    Buka
                  </a>
                  <button type="button" onClick={() => handleDownload(getOutputUrl(clip.url), clip.name)}>
                    <Download size={16} />
                    Unduh
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="emptyState">
            <Video size={32} style={{ marginBottom: "12px", opacity: 0.5 }} />
            <p>Klip vertikal 9:16 yang selesai diproses akan muncul di sini.</p>
          </div>
        )}
      </section>

      <section className="history">
        <div className="sectionHeader">
          <h2>Riwayat Proses</h2>
          <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
            <span className="sectionBadge">{jobs.length} total</span>
            {jobs.length > 0 && (
              <button
                type="button"
                onClick={handleDeleteAll}
                className="iconButton"
                title="Hapus Semua Riwayat"
                style={{ width: "32px", height: "32px", color: "var(--danger)" }}
              >
                <Trash2 size={16} />
              </button>
            )}
          </div>
        </div>
        <div className="jobList">
          {jobs.map((item) => {
            const Icon = statusIcon[item.status];
            return (
              <button
                className="jobRow"
                type="button"
                key={item.id}
                onClick={() => {
                  setJob(item);
                }}
              >
                <div className={`jobRow-status status-${item.status}`}>
                  <Icon className={item.status === "running" ? "spin" : ""} size={18} />
                </div>
                <span>{statusCopy[item.status]}</span>
                <strong>{item.clips.length ? `${item.clips.length} klip` : `${item.candidates.length} kandidat`}</strong>
              </button>
            );
          })}
        </div>
      </section>
    </main>
  );
};
