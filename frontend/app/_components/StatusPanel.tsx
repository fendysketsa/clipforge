import { useEffect, useState } from "react";
import { Activity, Clock3, XCircle } from "lucide-react";
import { statusIcon } from "../../lib/constants";
import { formatDuration, isActiveJob, jobElapsedSeconds } from "../../lib/utils";
import type { ClipJob } from "../../types/clip.type";

type StatusPanelProps = {
  job: ClipJob | null;
  latestLogs: string[];
  onCancelJob: () => void;
};

export function StatusPanel({ job, latestLogs, onCancelJob }: StatusPanelProps) {
  const [now, setNow] = useState(() => Date.now());
  const StatusIcon = job ? statusIcon[job.status] : Activity;
  const canCancel = isActiveJob(job);
  const elapsedSeconds = jobElapsedSeconds(job, now);

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
              {job.request.clip_mode === "highlight_5m"
                ? "Hanya highlight ±5 menit"
                : `${job.request.top ?? "Auto"} clip pendek maks. 60 detik`}
            </span>
            <span>
              {job.request.min_duration}s - {job.request.max_duration}s
            </span>
            <span>{job.request.enhanced_edit ? "Edit adaptif sinematik aktif" : "Edit standar"}</span>
            <span>{job.request.remove_running_text ? "Running text bawah dipotong" : "Footer sumber dipertahankan"}</span>
            <span>{job.request.analyze_seconds ? `Analisis: ${job.request.analyze_seconds}s` : "Full video"}</span>
            <span>{job.request.crop_mode === "person" ? "Follow person" : "Center crop"}</span>
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
