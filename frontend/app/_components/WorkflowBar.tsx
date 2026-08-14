"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AudioLines,
  Check,
  CircleDot,
  Clock3,
  FileCheck2,
  Film,
  Loader2,
  Link2,
  SearchCheck,
} from "lucide-react";
import { formatDuration, jobElapsedSeconds } from "../../lib/utils";
import type { ClipJob, ClipMode } from "../../types/clip.type";

type WorkflowBarProps = {
  hasSource: boolean;
  isProcessing: boolean;
  hasResults: boolean;
  job: ClipJob | null;
  clipMode: ClipMode;
  sourceValue: string;
};

const stageRanges = [
  { key: "source", label: "Sumber", shortHint: "Ambil video", longHint: "Ambil video", animateHint: "Baca naskah", start: 0, end: 18, icon: Film },
  { key: "transcript", label: "Transkrip", shortHint: "Audio & ucapan", longHint: "Audio & alur", animateHint: "Petakan beat", start: 18, end: 45, icon: AudioLines },
  { key: "selection", label: "Seleksi", shortHint: "Pilih hook", longHint: "Susun cerita", animateHint: "Storyboard", start: 45, end: 67, icon: SearchCheck },
  { key: "render", label: "Render", shortHint: "Klip per klip", longHint: "Long Story 16:9", animateHint: "Scene Cinema", start: 67, end: 94, icon: Loader2 },
  { key: "finalize", label: "Finalisasi", shortHint: "Audit & simpan", longHint: "Audit & thumbnail", animateHint: "AI disclosure", start: 94, end: 100, icon: FileCheck2 },
] as const;

const fallbackProgressFromLogs = (job: ClipJob | null) => {
  if (!job) return 0;
  if (job.status === "completed") return 100;
  const text = job.logs.join(" ").toLocaleLowerCase();
  if (/done\. exported|selesai dan terverifikasi/.test(text)) return 100;
  if (/exporting vertical|exporting 16:9|merender|rendering/.test(text)) return 70;
  if (/enhanced motion|structural edits|codex structural/.test(text)) return 63;
  if (/ai agent selected|scoring candidate|review candidates/.test(text)) return 50;
  if (/transcribed/.test(text)) return 44;
  if (/loading model|transcrib/.test(text)) return 28;
  if (/extracting audio/.test(text)) return 20;
  if (/fetching video|using uploaded video/.test(text)) return 8;
  return job.status === "running" ? 2 : 0;
};

const stageDescriptions: Record<string, { doing: string; output: string }> = {
  source: {
    doing: "Mengambil metadata, memvalidasi sumber, dan menyiapkan file video kerja.",
    output: "File sumber siap untuk ekstraksi audio.",
  },
  transcript: {
    doing: "Mengekstrak audio, mengenali ucapan, bahasa, dan timestamp setiap kalimat.",
    output: "Transkrip bertimestamp untuk membaca alur cerita.",
  },
  selection: {
    doing: "Menilai hook, pesan utama, kelengkapan konteks, payoff, dan ending kandidat.",
    output: "Kandidat terbaik yang aman diteruskan ke render.",
  },
  render: {
    doing: "Menerapkan crop, caption, visual adaptif, audio, watermark, dan encoding final.",
    output: "Video MP4 siap melalui pemeriksaan akhir.",
  },
  finalize: {
    doing: "Menyimpan metadata, thumbnail, caption sosial, audit hak, dan kesiapan monetisasi.",
    output: "Paket hasil lengkap siap direview atau diposting.",
  },
};

const animateStageDescriptions: Record<string, { doing: string; output: string }> = {
  source: {
    doing: "Membaca naskah dan memvalidasi hak serta kelengkapan input.",
    output: "Naskah siap diarahkan menjadi cerita visual.",
  },
  transcript: {
    doing: "Memetakan narasi, hook, konflik, konteks, jawaban, dan payoff.",
    output: "Beat cerita siap masuk ke storyboard.",
  },
  selection: {
    doing: "Menyusun storyboard, art bible, prompt visual, palet, dan motion tiap scene.",
    output: "Scene berbeda tetapi tetap berada dalam satu dunia visual.",
  },
  render: {
    doing: "Membuat gambar, voice-over, gerak kamera, subtitle, dan musik setiap scene.",
    output: "Seluruh scene siap digabungkan menjadi video 16:9.",
  },
  finalize: {
    doing: "Membuat thumbnail, chapter, metadata, disclosure AI, dan audit hak.",
    output: "Long Animate siap direview sebagai upload Private.",
  },
};

export function WorkflowBar({
  hasSource,
  isProcessing,
  hasResults,
  job,
  clipMode,
  sourceValue,
}: WorkflowBarProps) {
  const [now, setNow] = useState(() => Date.now());
  const mode = job?.request.clip_mode ?? clipMode;
  const isLongAnimate = mode === "long_animate";
  const isLongForm = mode === "highlight_5m" || isLongAnimate;
  const isStopped = job?.status === "failed" || job?.status === "cancelled";
  const isComplete = !isProcessing && (job ? job.status === "completed" : hasResults);
  const backendProgress = job?.progress_percent;
  const progress = Math.max(
    0,
    Math.min(
      100,
      isComplete
        ? 100
        : typeof backendProgress === "number" && backendProgress > 0
          ? backendProgress
          : isProcessing
            ? Math.max(job ? fallbackProgressFromLogs(job) : 0, 1)
            : 0,
    ),
  );
  const remaining = Math.max(0, 100 - progress);
  const elapsedSeconds = jobElapsedSeconds(job, now);
  const activeStageIndex = progress >= 100
    ? stageRanges.length - 1
    : Math.max(0, stageRanges.findIndex((stage) => progress < stage.end));
  const activeStage = stageRanges[activeStageIndex];
  const stageDescription = (isLongAnimate ? animateStageDescriptions : stageDescriptions)[activeStage.key];
  const nextStage = stageRanges[activeStageIndex + 1];
  const source = job?.request.url || job?.source_url || job?.request.source_file || sourceValue;
  const localSourceName = source && !source.startsWith("http")
    ? source.split(/[\\/]/).filter(Boolean).at(-1) || source
    : "";
  const sourceLabel = job?.source_title || (isLongAnimate
    ? "Naskah orisinal pengguna"
    : localSourceName
      ? `Upload lokal · ${localSourceName}`
      : source || "Belum ada sumber");
  const stageProgress = progress >= 100
    ? 100
    : Math.max(0, Math.min(99, Math.round(((progress - activeStage.start) / (activeStage.end - activeStage.start)) * 100)));

  const detail = useMemo(() => {
    if (isComplete) return isLongForm ? "Video panjang siap direview, diposting, atau diunduh." : "Semua klip pendek siap direview, diposting, atau diunduh.";
    if (isStopped) return job?.error || "Proses berhenti sebelum seluruh tahap selesai.";
    if (job?.progress_detail) return job.progress_detail;
    if (isProcessing) return isLongAnimate
      ? "Menjalankan Scene Cinema: storyboard, gambar, animasi, suara, subtitle, dan audit AI."
      : isLongForm
        ? "Menjalankan Long Story Director: teaser, alur, render, dan quality gate 1K."
        : "Menjalankan pipeline klip pendek satu per satu.";
    if (hasSource) return "Sumber siap. Atur gaya lalu mulai proses.";
    return "Masukkan link atau upload video untuk memulai.";
  }, [hasSource, isComplete, isLongAnimate, isLongForm, isProcessing, isStopped, job?.error, job?.progress_detail]);

  useEffect(() => {
    if (!isProcessing) return;
    setNow(Date.now());
    const interval = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(interval);
  }, [isProcessing, job?.id]);

  return (
    <section className={`workflowBar ${isProcessing ? "workflowBar--running" : ""} ${isStopped ? "workflowBar--stopped" : ""}`} aria-label="Progres pembuatan video">
      <div className="workflowSummary">
        <div className="workflowSummaryTopline">
          <span className="workflowEyebrow">Proses {isLongForm ? "video panjang" : "klip pendek"}</span>
          <span className={`workflowLiveBadge ${isProcessing ? "is-live" : ""}`}>
            <CircleDot size={10} />
            {isComplete ? "Selesai" : isStopped ? "Terhenti" : isProcessing ? "Berjalan" : hasSource ? "Siap" : "Menunggu"}
          </span>
        </div>
        <strong className="workflowCurrentTask">
          {isComplete ? "Hasil siap" : isStopped ? "Proses terhenti" : isProcessing ? activeStage.label : "Alur produksi"}
        </strong>
        <p>{detail}</p>
        <div className="workflowSource" title={source || sourceLabel}>
          <Link2 size={13} />
          <span>
            <small>Sumber aktif{job ? ` · Task ${job.id.slice(0, 8)}` : ""}</small>
            {source?.startsWith("http") ? (
              <a href={source} target="_blank" rel="noreferrer">{job?.source_title || source}</a>
            ) : (
              <strong>{sourceLabel}</strong>
            )}
          </span>
        </div>
        <div className="workflowRuntime">
          <Clock3 size={14} />
          <span>Waktu berjalan</span>
          <strong>{formatDuration(elapsedSeconds ?? 0)}</strong>
        </div>
        {isProcessing && job ? (
          <p className="workflowPersistenceNote">
            Task ini terkunci ke tab sekarang. Refresh akan menyambung kembali; tab baru dapat menjalankan link baru.
          </p>
        ) : null}
      </div>

      <div className="workflowProgressPanel">
        <div className="workflowProgressStats">
          <span><i className="done" /> Dikerjakan <strong>{Math.round(progress)}%</strong></span>
          <span><i /> Belum dikerjakan <strong>{Math.round(remaining)}%</strong></span>
        </div>
        <div
          className="workflowMeter"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(progress)}
          aria-label={`Progres ${Math.round(progress)} persen`}
        >
          <span style={{ width: `${progress}%` }} />
        </div>

        <ol className="workflowSteps">
          {stageRanges.map((stage, index) => {
            const complete = progress >= stage.end;
            const current = !isComplete && index === activeStageIndex && (isProcessing || isStopped);
            const pending = !complete && !current;
            const Icon = complete ? Check : stage.icon;

            return (
              <li
                className={`${complete ? "complete" : ""} ${current ? "current" : ""} ${pending ? "pending" : ""}`}
                key={stage.key}
                aria-current={current ? "step" : undefined}
              >
                <span className="workflowDot">
                  <Icon className={current && stage.key === "render" && isProcessing ? "spin" : ""} size={15} />
                </span>
                <span className="workflowStepCopy">
                  <strong>{stage.label}</strong>
                  <small>
                    {complete
                      ? "100% selesai"
                      : current
                        ? `${stageProgress}% tahap ini`
                        : isLongAnimate ? stage.animateHint : isLongForm ? stage.longHint : stage.shortHint}
                  </small>
                </span>
              </li>
            );
          })}
        </ol>
        <div className="workflowTaskDetails">
          <span>
            <small>Tahap aktif</small>
            <strong>{isComplete ? "5/5 · Selesai" : `${activeStageIndex + 1}/5 · ${job?.progress_stage === "queued" ? "Antrean worker" : activeStage.label}`}</strong>
          </span>
          <span>
            <small>Sedang dilakukan</small>
            <strong>{isComplete ? "Seluruh pipeline telah selesai." : job?.progress_detail || stageDescription.doing}</strong>
          </span>
          <span>
            <small>Hasil tahap / berikutnya</small>
            <strong>{isComplete ? stageDescription.output : `${stageDescription.output}${nextStage ? ` Berikutnya: ${nextStage.label}.` : ""}`}</strong>
          </span>
        </div>
      </div>
    </section>
  );
}
