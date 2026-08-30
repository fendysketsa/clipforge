import { useEffect, useState } from "react";
import { Activity, Clock3, Sparkles, XCircle } from "lucide-react";
import { statusIcon } from "../../lib/constants";
import { formatDuration, isActiveJob, jobElapsedSeconds } from "../../lib/utils";
import type { ClipJob } from "../../types/clip.type";

type StatusPanelProps = {
  job: ClipJob | null;
  latestLogs: string[];
  onCancelJob: () => void;
  onSwitchToOriginalRebuild: () => void;
};

export function StatusPanel({ job, latestLogs, onCancelJob, onSwitchToOriginalRebuild }: StatusPanelProps) {
  const [now, setNow] = useState(() => Date.now());
  const StatusIcon = job ? statusIcon[job.status] : Activity;
  const canCancel = isActiveJob(job);
  const elapsedSeconds = jobElapsedSeconds(job, now);
  const canSwitchToOriginalRebuild = Boolean(
    job?.status === "failed"
    && job.request.clip_mode !== "original_rebuild"
    && /content id|broadcaster|original rebuild/i.test(`${job.error || ""} ${job.logs.join(" ")}`),
  );

  useEffect(() => {
    if (!canCancel) return;

    setNow(Date.now());
    const interval = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(interval);
  }, [canCancel, job?.id]);

  return (
    <section className="panel statusPanel">
      <div className="panelHeader">
        <div className="panelHeaderTitle">
          <span className="panelHeaderIcon">
            <StatusIcon className={job?.status === "running" ? "spin" : ""} size={18} />
          </span>
          <div className="panelTitleCopy">
            <span className="panelEyebrow">Monitor proses</span>
            <h2>Aktivitas</h2>
          </div>
        </div>
        {canCancel ? (
          <button className="uiButton uiButton--ghostDanger cancelJobButton" type="button" onClick={onCancelJob}>
            <XCircle size={16} />
            <span>Batalkan</span>
          </button>
        ) : null}
      </div>

      {job ? (
        <div className="activityContent">
          <div className={`statusProgress statusProgress--${job.status}`} aria-label={`Status job: ${job.status}`}>
            <span />
          </div>
          <div className="jobMeta">
            <span>
              {job.request.clip_mode === "long_animate"
                ? "Long Animate · storyboard ke video 16:9 · target stabilitas 5K"
                : job.request.clip_mode === "original_rebuild"
                ? "Original Rebuild · transkrip riset ke media baru 16:9 · review fakta wajib"
                : job.request.clip_mode === "highlight_5m"
                ? `Long Story landscape ±${Math.round(job.request.compilation_target_seconds / 60)} menit · target stabilitas 5K`
                : `${job.request.top ?? "Auto"} clip pendek adaptif 25–180 detik · target eksperimen 20K`}
            </span>
            <span>
              {job.request.clip_mode === "original_rebuild"
                ? "Audio & piksel sumber tidak masuk output"
                : job.request.clip_mode === "long_animate"
                  ? "Timeline mengikuti target Scene Cinema"
                  : `${job.request.min_duration}s - ${job.request.max_duration}s`}
            </span>
            <span>{job.request.enhanced_edit ? "Edit adaptif sinematik aktif" : "Edit standar"}</span>
            <span>Auto FYP Viral adaptif</span>
            <span>
              {job.request.clip_mode === "long_animate" || job.request.clip_mode === "original_rebuild"
                ? "Visual generatif per scene"
                : job.request.background_mode === "keep"
                ? "Background asli"
                : job.request.background_mode === "mosque"
                  ? "Virtual background masjid"
                  : "Auto clean + jamaah adaptif"}
            </span>
            <span>{job.request.clip_mode === "original_rebuild" ? "Rewrite anti-verbatim aktif" : job.request.clip_mode === "long_animate" ? "Naskah menjadi arah visual baru" : job.request.remove_running_text ? "Pembersihan footer aktif" : "Frame sumber dipertahankan jernih"}</span>
            <span>{job.request.clip_mode === "original_rebuild" ? "Suara sumber tidak dikloning" : job.request.clip_mode === "long_animate" ? "Voice-over generatif per scene" : job.request.auto_blur_watermarks ? "Blur watermark otomatis aktif" : "Blur watermark nonaktif"}</span>
            {job.request.clip_mode === "original_rebuild" ? <span>Perspektif kreator: {job.request.creator_perspective.trim().split(/\s+/).filter(Boolean).length} kata</span> : null}
            {job.request.clip_mode === "long_animate" || job.request.clip_mode === "original_rebuild" ? <span>Referensi lisensi tercatat; review dokumen + variasi channel wajib</span> : null}
            <span>{job.request.clip_mode === "long_animate" ? "Tanpa analisis footage sumber" : job.request.analyze_seconds ? `Analisis: ${job.request.analyze_seconds}s` : "Full video"}</span>
            <span>
              {job.request.clip_mode === "long_animate" || job.request.clip_mode === "original_rebuild"
                ? "Canvas: 16:9 Scene Cinema"
                : <>Job crop: {job.request.crop_mode === "person"
                ? "Follow person"
                : job.request.crop_mode === "streamer"
                  ? "Streamer"
                  : "Center"}</>}
            </span>
            <span>
              <Clock3 size={13} />
              Durasi: {formatDuration(elapsedSeconds)}
            </span>
          </div>

          <div className="logBox">
            {latestLogs.length ? (
              latestLogs.map((line, index) => <p key={`${line}-${index}`}>{line}</p>)
            ) : (
              <p>Memulai proses pipeline...</p>
            )}
          </div>

          {job.error ? <p className="error errorWithSpacing">{job.error}</p> : null}
          {canSwitchToOriginalRebuild ? (
            <button className="uiButton" type="button" onClick={onSwitchToOriginalRebuild}>
              <Sparkles size={16} />
              Gunakan topiknya lewat Original Rebuild
            </button>
          ) : null}
        </div>
      ) : (
        <div className="emptyState activityEmptyState">
          <Activity className="emptyStateIcon" size={32} />
          <p>Belum ada proses berjalan.</p>
          <p className="emptyStateHint">
            Masukkan link YouTube, lalu klik <strong>Mulai Potong Video</strong> untuk memulai.
          </p>
        </div>
      )}
    </section>
  );
}
