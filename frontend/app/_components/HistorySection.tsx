import { Trash2 } from "lucide-react";
import { statusCopy, statusIcon } from "../../lib/constants";
import type { ClipJob } from "../../types/clip.type";

type HistorySectionProps = {
  jobs: ClipJob[];
  selectedJobIds: string[];
  onDeleteAll: () => void;
  onDeleteFailed: () => void;
  onDeleteSelected: () => void;
  onSelectJob: (job: ClipJob) => void;
  onToggleJobSelection: (jobId: string) => void;
};

export function HistorySection({
  jobs,
  selectedJobIds,
  onDeleteAll,
  onDeleteFailed,
  onDeleteSelected,
  onSelectJob,
  onToggleJobSelection,
}: HistorySectionProps) {
  const failedJobs = jobs.filter((item) => item.status === "failed" || item.status === "cancelled");
  const selectedCount = selectedJobIds.length;

  return (
    <section className="history">
      <div className="sectionHeader">
        <h2>Riwayat Proses</h2>
        <div className="historyActions">
          <span className="sectionBadge">{jobs.length} total</span>
          {failedJobs.length > 0 ? (
            <button type="button" onClick={onDeleteFailed} className="ghostButton dangerTextButton">
              <Trash2 size={15} />
              Hapus gagal
            </button>
          ) : null}
          {selectedCount > 0 ? (
            <button type="button" onClick={onDeleteSelected} className="dangerButton historyDeleteSelected">
              <Trash2 size={15} />
              Hapus terpilih ({selectedCount})
            </button>
          ) : null}
          {jobs.length > 0 ? (
            <button
              type="button"
              onClick={onDeleteAll}
              className="iconButton dangerIconButton"
              title="Hapus Semua Riwayat"
            >
              <Trash2 size={16} />
            </button>
          ) : null}
        </div>
      </div>

      <div className="jobList">
        {jobs.map((item) => {
          const Icon = statusIcon[item.status];
          const count = item.clips.length ? `${item.clips.length} klip` : `${item.candidates.length} kandidat`;
          const canSelectForDelete = item.status === "failed" || item.status === "cancelled";
          const isSelected = selectedJobIds.includes(item.id);

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
                <div className={`jobRow-status status-${item.status}`}>
                  <Icon className={item.status === "running" ? "spin" : ""} size={18} />
                </div>
                <span>{statusCopy[item.status]}</span>
                <strong>{count}</strong>
              </button>
            </div>
          );
        })}
      </div>
    </section>
  );
}
