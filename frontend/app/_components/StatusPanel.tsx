import {
  Check,
  ChevronDown,
  Circle,
  Clock3,
  FileText,
  Loader2,
  Scissors,
  Sparkles,
  Terminal,
  Video,
  XCircle,
} from "lucide-react";
import { statusIcon } from "../../lib/constants";
import { formatDuration, isActiveJob, jobElapsedSeconds } from "../../lib/utils";
import type { ClipJob } from "../../types/clip.type";

type StatusPanelProps = {
  job: ClipJob | null;
  latestLogs: string[];
  onCancelJob: () => void;
};

const STAGES = [
  { key: "source", label: "Sumber", icon: Video },
  { key: "transcript", label: "Transkrip", icon: FileText },
  { key: "selection", label: "Pilih hook", icon: Sparkles },
  { key: "render", label: "Render", icon: Scissors },
  { key: "finalize", label: "Selesai", icon: Check },
] as const;

const stageIndex = (job: ClipJob | null) => {
  if (!job) return -1;
  if (job.status === "completed") return STAGES.length;
  const normalized = (job.progress_stage || "").toLowerCase();
  const direct = STAGES.findIndex((stage) => normalized.includes(stage.key));
  if (direct >= 0) return direct;
  if (job.status === "queued") return -1;
  return Math.min(STAGES.length - 1, Math.floor((job.progress_percent ?? 0) / 20));
};

const statusLabel = (job: ClipJob | null) => {
  if (!job) return "Siap menerima sumber";
  const outputName = job.request.clip_mode === "highlight_5m" ? "Long Highlight" : "Short";
  if (job.status === "queued") return "Menunggu giliran";
  if (job.status === "running") return `Sedang membuat ${outputName}`;
  if (job.status === "completed") return `${outputName} selesai dibuat`;
  if (job.status === "cancelled") return "Proses dibatalkan";
  return "Proses perlu diperiksa";
};

const currentTaskLabel = (job: ClipJob | null) => {
  if (!job) return "SIAP";
  if (job.status === "queued") return "MENUNGGU GILIRAN";
  if (job.status === "running") return "SEDANG DIKERJAKAN";
  if (job.status === "completed") return "SELESAI";
  if (job.status === "cancelled") return "DIBATALKAN";
  return "PROSES GAGAL";
};

export function StatusPanel({ job, latestLogs, onCancelJob }: StatusPanelProps) {
  const StatusIcon = job ? statusIcon[job.status] : Circle;
  const currentStage = stageIndex(job);
  const progress = job?.status === "completed" ? 100 : Math.max(0, Math.min(100, Math.round(job?.progress_percent ?? 0)));
  const canCancel = isActiveJob(job);
  const elapsed = job ? jobElapsedSeconds(job) : 0;
  const isLong = job?.request.clip_mode === "highlight_5m";

  return (
    <section className={`panel clipStatus clipStatus--${job?.status ?? "idle"}`} aria-live="polite">
      <header className="clipStatusHeader">
        <span className="clipStatusIcon">
          <StatusIcon className={job?.status === "running" ? "spin" : ""} size={19} />
        </span>
        <span>
          <small>PROSES CLIPPER</small>
          <strong>{statusLabel(job)}</strong>
        </span>
        {job ? <b>{progress}%</b> : <b className="isReady">READY</b>}
      </header>

      {!job ? (
        <div className="clipStatusEmpty">
          <div className="emptyShortFrame"><Scissors size={24} /><i /></div>
          <div><strong>Belum ada proses aktif</strong><p>Tempel sumber di atas. Progres Short atau Long Highlight akan tampil ringkas di sini.</p></div>
        </div>
      ) : (
        <div className="clipStatusBody">
          <div className="clipProgressTrack" aria-label={`Progres ${progress}%`}>
            <span style={{ width: `${progress}%` }} />
          </div>

          <ol className="clipStageList">
            {STAGES.map(({ key, label, icon: Icon }, index) => {
              const complete = index < currentStage || job.status === "completed";
              const active = index === currentStage && canCancel;
              return (
                <li className={complete ? "isComplete" : active ? "isActive" : ""} key={key}>
                  <i>{complete ? <Check size={13} /> : active ? <Loader2 className="spin" size={13} /> : <Icon size={13} />}</i>
                  <span>{isLong && key === "selection" ? "Susun cerita" : label}</span>
                </li>
              );
            })}
          </ol>

          <div className="clipCurrentTask">
            <span><Sparkles size={15} /></span>
            <div>
              <small>{currentTaskLabel(job)}</small>
              <strong>{job.progress_detail || job.source_title || "Menyiapkan pipeline…"}</strong>
            </div>
            <time><Clock3 size={13} /> {formatDuration(elapsed)}</time>
          </div>

          {job.error ? <div className="clipStatusError"><XCircle size={15} /> {job.error}</div> : null}

          <div className="clipStatusActions">
            <details className="compactLogs">
              <summary><span><Terminal size={14} /> Detail proses</span><ChevronDown size={14} /></summary>
              <div>{latestLogs.length ? latestLogs.map((line, index) => <code key={`${line}-${index}`}>{line}</code>) : <code>Menunggu aktivitas…</code>}</div>
            </details>
            {canCancel ? <button type="button" onClick={onCancelJob}><XCircle size={15} /> Batalkan</button> : null}
          </div>
        </div>
      )}
    </section>
  );
}
