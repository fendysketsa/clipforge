"use client";
import { Activity, AlertTriangle, Radio } from "lucide-react";
import { officeActivityStatus, officeAgentWork, officeRepairAction, officeTaskLabel, officeTime, officeWorkLabel, type AIOfficeSnapshot } from "../../lib/aiOffice";

/** A live, data-only snapshot of each department's current worker task. */
export function OfficeLiveDesk({ snapshot, now, refreshFailed, selected, onSelect }: {
  snapshot: AIOfficeSnapshot; now: number; refreshFailed: boolean; selected: string; onSelect: (value: string) => void;
}) {
  const status = officeActivityStatus(snapshot, now, refreshFailed);
  const repair = snapshot.director?.active_repair;
  const blocker = (snapshot.incidents || []).find(row => row.state !== "needs_operator" && row.automatic);
  const focus = repair
    ? `${repair.department}: ${repair.summary}`
    : blocker ? `${blocker.department}: ${officeRepairAction[blocker.action] || blocker.title}` : "";
  return <section className="officeLiveDesk" aria-labelledby="office-live-title">
    <header className="officeLiveHead">
      <div className="officeLiveTitle"><Activity size={14} /><h3 id="office-live-title">Papan kerja langsung</h3></div>
      <span className="officeLiveClock">{status.fresh ? `Diperbarui ${officeTime(status.observedAt)}` : "Menunggu data worker"}</span>
    </header>
    <div className="officeLiveGrid">
      {snapshot.departments.map(department => {
        const work = officeAgentWork(snapshot, department.id, now, refreshFailed);
        const primary = work.work[0];
        const progress = primary?.state === "running" && primary.progress_percent != null
          ? Math.max(0, Math.min(100, Math.round(primary.progress_percent))) : null;
        return <button type="button" key={department.id}
          className={`officeLiveCard is-${work.state}${selected === department.id ? " is-selected" : ""}`}
          data-department={department.id} data-stage={primary?.stage_key || undefined}
          aria-pressed={selected === department.id}
          onClick={() => onSelect(selected === department.id ? "all" : department.id)}>
          <span className="officeLiveCardTop"><strong>{department.name}</strong><i>{officeWorkLabel[work.state]}</i></span>
          <span className="officeLiveStage">{primary?.stage || work.detail}</span>
          <span className="officeLiveWork">{primary?.title || "Tidak ada pekerjaan aktif"}</span>
          <span className="officeLiveMeter" data-kind={progress != null ? "running" : work.state}><i style={progress != null ? { width: `${progress}%` } : undefined} /></span>
          <span className="officeLiveMeta">
            <em>{work.running_count} jalan</em><em>{work.queued_count} antre</em><em>{work.blocked_count} tertahan</em>
            {progress != null ? <b>{progress}%</b> : null}
          </span>
        </button>;
      })}
    </div>
    {focus ? <p className="officeLiveFocus"><Radio size={13} /><span>Pimpinan menangani <strong>{focus}</strong></span></p>
      : status.fresh ? <p className="officeLiveFocus is-clear"><AlertTriangle size={13} /><span>Tidak ada kendala yang perlu perbaikan otomatis.</span></p> : null}
    {snapshot.tasks.length ? <ul className="officeLiveFeed" aria-label="Arahan terakhir pimpinan">{snapshot.tasks.slice(-3).reverse().map(task =>
      <li key={task.id} data-status={task.status}><i /><span>{task.action}</span><em>{officeTaskLabel[task.status]}</em></li>)}</ul> : null}
  </section>;
}
