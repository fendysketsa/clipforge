"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  Clock3,
  Download,
  ExternalLink,
  Loader2,
  Play,
  RefreshCw,
  Scissors,
  Settings2,
  XCircle,
  Activity,
  History,
  Video
} from "lucide-react";
import { createJob, exportJob, getJob, getJobs, getOutputUrl } from "../../lib/apiClient";
import type { ClipJob, JobStatus } from "../../types/clip.type";

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

function formatBytes(value: number) {
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function clipTitle(name: string) {
  return name.replace(/\.mp4$/i, "").replace(/^clip_\d+_/, "").replace(/-/g, " ");
}

function formatTime(seconds: number) {
  const whole = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(whole / 60);
  const rest = whole % 60;
  return `${minutes}:${rest.toString().padStart(2, "0")}`;
}

export const ClipperWorkspace = () => {
  const [url, setUrl] = useState("");
  const [top, setTop] = useState(5);
  const [minDuration, setMinDuration] = useState(35);
  const [maxDuration, setMaxDuration] = useState(180);
  const [analyzeSeconds, setAnalyzeSeconds] = useState("");
  const [force, setForce] = useState(false);
  const [reviewOnly, setReviewOnly] = useState(true);
  const [job, setJob] = useState<ClipJob | null>(null);
  const [jobs, setJobs] = useState<ClipJob[]>([]);
  const [selectedCandidates, setSelectedCandidates] = useState<number[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
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

  useEffect(() => {
    if (!job?.candidates.length || selectedCandidates.length) return;
    setSelectedCandidates(job.candidates.map((candidate) => candidate.index));
  }, [job?.id, job?.candidates.length, selectedCandidates.length]);

  async function handleStartJob() {
    setError("");
    if (!url.trim()) {
      setError("Link YouTube tidak boleh kosong.");
      return;
    }
    setIsSubmitting(true);

    try {
      const nextJob = await createJob({
        url,
        top,
        min_duration: minDuration,
        max_duration: maxDuration,
        model: "Systran/faster-whisper-base",
        language: "id",
        analyze_seconds: analyzeSeconds ? Number(analyzeSeconds) : null,
        burn_subtitles: true,
        force,
        review_only: reviewOnly,
      });
      setJob(nextJob);
      setSelectedCandidates([]);
      await loadJobs();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Gagal memulai proses.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleExportSelected() {
    if (!job || !selectedCandidates.length) return;
    setError("");
    setIsExporting(true);
    try {
      const nextJob = await exportJob(job.id, selectedCandidates);
      setJob(nextJob);
      await loadJobs();
    } catch (exportError) {
      setError(exportError instanceof Error ? exportError.message : "Gagal mengekspor klip yang dipilih.");
    } finally {
      setIsExporting(false);
    }
  }

  const StatusIcon = job ? statusIcon[job.status] : Activity;

  return (
    <main className="shell">
      <section className="topbar">
        <div className="topbar-brand">
          <h1 className="logo-text">yt-clip</h1>
          <p className="tagline">Turn long YouTube videos into ready-to-post clips.</p>
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
              <span>Jumlah Klip</span>
              <input min={1} max={12} type="number" value={top} onChange={(event) => setTop(Number(event.target.value))} />
            </label>
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
            <label className="field">
              <span>Mode Analisis (Detik)</span>
              <input
                min={10}
                max={7200}
                type="number"
                value={analyzeSeconds}
                onChange={(event) => setAnalyzeSeconds(event.target.value)}
                placeholder="Full video"
              />
            </label>
          </div>

          <div className="optionRow">
            <label className="check">
              <input type="checkbox" checked={force} onChange={(event) => setForce(event.target.checked)} />
              Buat ulang cache
            </label>
            <label className="check">
              <input type="checkbox" checked={reviewOnly} onChange={(event) => setReviewOnly(event.target.checked)} />
              Review sebelum export
            </label>
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
            <>
              <div className="jobMeta">
                <span>{job.request.top} klip target</span>
                <span>{job.request.min_duration}s - {job.request.max_duration}s</span>
                <span>{job.request.analyze_seconds ? `Test: ${job.request.analyze_seconds}s` : "Full video"}</span>
              </div>

              <div className="logBox">
                {latestLogs.length ? latestLogs.map((line, index) => <p key={`${line}-${index}`}>{line}</p>) : <p>Memulai proses pipeline...</p>}
              </div>

              {job.error ? <p className="error" style={{marginTop: "16px"}}>{job.error}</p> : null}
            </>
          ) : (
            <div className="emptyState">
              <Activity size={32} style={{ marginBottom: "12px", opacity: 0.5 }} />
              <p>Belum ada proses berjalan.</p>
              <p style={{ fontSize: "13px", marginTop: "4px" }}>Masukkan link YouTube, lalu klik <strong>Mulai Potong Video</strong> untuk memulai.</p>
            </div>
          )}
        </section>
      </section>

      {job?.candidates.length ? (
        <section className="review">
          <div className="sectionHeader">
            <h2>Review Kandidat Klip</h2>
            <span className="sectionBadge">{job.candidates.length} klip ditemukan</span>
          </div>
          <div className="candidateList">
            {job.candidates.map((candidate) => {
              const checked = selectedCandidates.includes(candidate.index);
              return (
                <article className="candidateCard" key={candidate.index} style={{ borderColor: checked ? "var(--primary)" : "" }}>
                  <label className="candidateCheck">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(event) => {
                        setSelectedCandidates((current) =>
                          event.target.checked
                            ? [...new Set([...current, candidate.index])].sort((a, b) => a - b)
                            : current.filter((index) => index !== candidate.index),
                        );
                      }}
                    />
                    Klip {candidate.index}
                  </label>
                  <div className="candidateMeta">
                    <span>{formatTime(candidate.start)} - {formatTime(candidate.end)}</span>
                    <span>{Math.round(candidate.duration)}s</span>
                    <span style={{ color: "var(--primary)" }}>Skor: {candidate.score}</span>
                  </div>
                  <h3>{candidate.title}</h3>
                  <p className="candidateReason">{candidate.reason}</p>
                  <p className="candidateText">{candidate.text}</p>
                </article>
              );
            })}
          </div>
          <button
            className="primary exportButton"
            type="button"
            disabled={isBusy || isExporting || !selectedCandidates.length}
            onClick={handleExportSelected}
          >
            {isExporting || isBusy ? <Loader2 className="spin" size={18} /> : <Scissors size={18} />}
            Export Klip Terpilih
          </button>
        </section>
      ) : null}

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
                  <span>{formatBytes(clip.size_bytes)}</span>
                </div>
                <div className="clipActions">
                  <a href={getOutputUrl(clip.url)} target="_blank" rel="noreferrer">
                    <ExternalLink size={16} />
                    Buka
                  </a>
                  <a href={getOutputUrl(clip.url)} download>
                    <Download size={16} />
                    Unduh
                  </a>
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
          <span className="sectionBadge">{jobs.length} total</span>
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
                  setSelectedCandidates([]);
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
