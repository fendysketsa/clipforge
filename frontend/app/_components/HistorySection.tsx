import { CalendarClock, Clock3, ExternalLink, Film, History, Link2, StopCircle, Trash2 } from "lucide-react";
import { statusCopy, statusIcon } from "../../lib/constants";
import { formatDuration, jobElapsedSeconds } from "../../lib/utils";
import type { ClipJob } from "../../types/clip.type";

type HistorySectionProps = {
  jobs: ClipJob[];
  selectedJobIds: string[];
  onDeleteAll: () => void;
  onDeleteFailed: () => void;
  onDeleteSelected: () => void;
  onSelectJob: (job: ClipJob) => void;
  onStopJob: (jobId: string) => void;
  onToggleJobSelection: (jobId: string) => void;
};

export function HistorySection({
  jobs,
  selectedJobIds,
  onDeleteAll,
  onDeleteFailed,
  onDeleteSelected,
  onSelectJob,
  onStopJob,
  onToggleJobSelection,
}: HistorySectionProps) {
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
          const elapsedSeconds = jobElapsedSeconds(item);

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
                  </span>
                  <strong>
                    <Film size={14} />
                    {count}
                  </strong>
                </div>
                <h3>{sourceLabel(item)}</h3>
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
