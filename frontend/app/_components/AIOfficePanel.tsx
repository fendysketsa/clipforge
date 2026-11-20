"use client";

import { useEffect, useState } from "react";
import { Activity, CheckCircle2, CirclePause, Clock3, Loader2, RefreshCw, ShieldCheck, TriangleAlert } from "lucide-react";
import toast from "react-hot-toast";
import { getAIOffice, requestAIOfficeCheck } from "../../lib/apiClient";
import { officeStateLabel, officeStatus, officeTaskLabel, officeTime, type AIOfficeSnapshot } from "../../lib/aiOffice";
import { createPollingTask } from "../../lib/pollTask";

export function AIOfficePanel() {
  const [snapshot, setSnapshot] = useState<AIOfficeSnapshot | null>(null);
  const [refreshFailed, setRefreshFailed] = useState(false);
  const [requesting, setRequesting] = useState(false);
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const poll = createPollingTask(async current => {
      try {
        const result = await getAIOffice();
        if (current()) { setSnapshot(result); setRefreshFailed(false); setNow(Date.now()); }
      } catch {
        if (current()) { setRefreshFailed(true); setNow(Date.now()); }
      }
    }, () => !document.hidden);
    void poll.run();
    const timer = window.setInterval(poll.run, 20_000);
    document.addEventListener("visibilitychange", poll.run);
    return () => { poll.stop(); window.clearInterval(timer); document.removeEventListener("visibilitychange", poll.run); };
  }, []);
  const check = async () => {
    setRequesting(true);
    try {
      const result = await requestAIOfficeCheck();
      if (result.accepted) toast.success(result.message); else toast.error(result.message);
      setSnapshot(await getAIOffice()); setRefreshFailed(false); setNow(Date.now());
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Koordinator belum dapat menerima pemeriksaan.");
    } finally { setRequesting(false); }
  };
  const status = officeStatus(snapshot, now, refreshFailed);
  const StatusIcon = status.state === "working" ? Activity : status.state === "disabled" ? CirclePause
    : status.state === "degraded" ? TriangleAlert : status.state === "starting" ? Loader2 : ShieldCheck;
  const departments = new Map(snapshot?.departments.map(item => [item.id, item.name]) || []);
  const tasks = snapshot?.tasks.slice(-8).reverse() || [];
  return <section className={`aiOffice is-${status.state}`} aria-labelledby="ai-office-title">
    <header className="aiOfficeHeading">
      <div><span className="studioEyebrow">KOORDINATOR OPERASIONAL</span><h2 id="ai-office-title">Arahan & pekerjaan</h2><p>Koordinator membagi pekerjaan ke worker produksi, pemeriksaan, distribusi, dan cleanup.</p></div>
      <button className="uiButton" type="button" disabled={requesting || !snapshot?.enabled} onClick={() => { void check(); }}>
        {requesting ? <Loader2 size={15} className="spin" /> : <RefreshCw size={15} />} Periksa pekerjaan
      </button>
    </header>
    <div className="aiOfficeStatus" role="status">
      <StatusIcon size={20} className={status.state === "starting" ? "spin" : undefined} />
      <div><strong>{status.label}</strong><p>{status.detail}</p>
        {snapshot?.last_tick_at ? <small>Pemeriksaan terakhir {officeTime(snapshot.last_tick_at)}{snapshot.next_tick_at && snapshot.enabled && !status.stale ? ` · Berikutnya ${officeTime(snapshot.next_tick_at)}` : ""}</small> : null}
      </div>
    </div>
    {snapshot?.departments.length ? <div className="aiOfficeDepartments" aria-label="Pembagian pekerjaan">
      {snapshot.departments.map(department => <article key={department.id} className={`aiOfficeDepartment is-${department.state}`}>
        <div className="aiOfficeDepartmentTitle"><h3>{department.name}</h3><span>{status.stale ? "Status terakhir" : officeStateLabel[department.state]}</span></div>
        <p>{department.detail}</p><small>{department.role}{department.active_count > 0 ? ` · ${department.active_count} pekerjaan${status.stale ? " pada pembaruan terakhir" : " aktif"}` : ""}</small>
      </article>)}
    </div> : null}
    <details className="aiOfficeDecisions">
      <summary>Keputusan terakhir <span>{tasks.length ? `${tasks.length} aktivitas` : "Belum ada aktivitas"}</span></summary>
      {tasks.length ? <ol>{tasks.map(task => <li key={task.id} className={`is-${task.status}`}>
        <span className="aiOfficeTaskIcon">{task.status === "completed" ? <CheckCircle2 size={16} /> : task.status === "failed" ? <TriangleAlert size={16} /> : <Clock3 size={16} />}</span>
        <div><strong>{task.action}</strong><p>{task.summary}</p><small>{departments.get(task.department) || task.department} · {officeTaskLabel[task.status]} · {officeTime(task.finished_at || task.started_at)}{task.next_retry_at ? ` · Pemeriksaan berikutnya ${officeTime(task.next_retry_at)}` : ""}</small></div>
      </li>)}</ol> : <p className="aiOfficeNoDecisions">Belum ada penugasan tambahan. Worker mengikuti jadwal dan setelan yang berlaku.</p>}
    </details>
  </section>;
}
