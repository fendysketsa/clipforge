"use client";
import { useEffect, useState } from "react";
import { ArrowUpRight, CheckCheck, Clock3, Loader2, Radio, RefreshCw, RotateCcw, Trash2, TriangleAlert } from "lucide-react";
import toast from "react-hot-toast";
import { deleteAIOfficeReview, getAIOffice, requestAIOfficeCheck, retryAIOfficeReview } from "../../lib/apiClient";
import { officeActivityStatus, officeAgentWork, officeIncidents, officeTime, officeWorkLabel, type AIOfficeSnapshot } from "../../lib/aiOffice";
import { createPollingTask } from "../../lib/pollTask";
import { OfficeLiveDesk } from "./OfficeLiveDesk";
import { OfficeStudioFloor } from "./OfficeStudioFloor";

export function AIOfficePanel() {
  const [snapshot, setSnapshot] = useState<AIOfficeSnapshot | null>(null);
  const [refreshFailed, setRefreshFailed] = useState(false), [requesting, setRequesting] = useState(false);
  const [reviewBusy, setReviewBusy] = useState("");
  const [now, setNow] = useState(Date.now), [department, setDepartment] = useState("all");
  useEffect(() => {
    const poll = createPollingTask(async current => {
      try { const result = await getAIOffice(); if (current()) { setSnapshot(result); setRefreshFailed(false); setNow(Date.now()); } }
      catch { if (current()) { setRefreshFailed(true); setNow(Date.now()); } }
    }, () => !document.hidden);
    void poll.run();
    const timer = window.setInterval(poll.run, 5_000), clock = window.setInterval(() => setNow(Date.now()), 1_000);
    window.addEventListener("focus", poll.run); document.addEventListener("visibilitychange", poll.run);
    return () => { poll.stop(); window.clearInterval(timer); window.clearInterval(clock); window.removeEventListener("focus", poll.run); document.removeEventListener("visibilitychange", poll.run); };
  }, []);
  const check = async () => {
    if (requesting) return;
    setRequesting(true);
    try {
      const result = await requestAIOfficeCheck();
      if (result.accepted) toast.success(result.message); else toast.error(result.message);
      setSnapshot(await getAIOffice()); setRefreshFailed(false); setNow(Date.now());
    } catch (error) { toast.error(error instanceof Error ? error.message : "Pemeriksaan belum dapat dijalankan."); }
    finally { setRequesting(false); }
  };
  const actOnReview = async (jobId: string, action: "retry" | "delete") => {
    if (reviewBusy) return;
    setReviewBusy(jobId + action);
    try {
      const result = action === "retry" ? await retryAIOfficeReview(jobId) : await deleteAIOfficeReview(jobId);
      toast.success(action === "retry" && "message" in result ? String(result.message) : "Pekerjaan dihapus dari antrean.");
      setSnapshot(await getAIOffice()); setNow(Date.now());
    } catch (error) { toast.error(error instanceof Error ? error.message : "Aksi review belum berhasil."); }
    finally { setReviewBusy(""); }
  };
  const status = officeActivityStatus(snapshot, now, refreshFailed);
  const departments = snapshot?.departments || [];
  const activity = departments.map(row => officeAgentWork(snapshot,row.id,now,refreshFailed));
  const names = new Map(departments.map(row => [row.id,row.name]));
  const totals = activity.reduce((sum,row) => ({ running:sum.running+row.running_count,queued:sum.queued+row.queued_count }),{running:0,queued:0});
  const work = activity.filter(row => department === "all" || row.id === department)
    .flatMap(row => row.work.map(item => ({...item,department:row.id})))
    .sort((a,b) => ({running:0,queued:1,blocked:2}[a.state]-{running:0,queued:1,blocked:2}[b.state]));
  const incidents = officeIncidents(snapshot,"all",department);
  const observed = snapshot?.control_version === 2 && snapshot.incident_observation_available;
  return <section className="officeHQ" aria-labelledby="ai-office-title">
    <header className="officeHQHeading"><div><span className="studioEyebrow">RYUUNDY / OPERATIONS</span><h1 id="ai-office-title">Kantor AI</h1></div>
      <button className="officeCommand" type="button" disabled={requesting || !snapshot?.enabled} onClick={() => void check()}>{requesting ? <Loader2 size={15} className="spin" /> : <RefreshCw size={15} />}{requesting ? "Memeriksa…" : "Periksa sistem"}</button></header>
    <div className={`officeHQStatus${!status.fresh ? " is-stale" : ""}`} role="status">{status.fresh ? <Radio size={14} /> : <Clock3 size={14} />}<strong>{status.fresh ? `${totals.running} bekerja · ${totals.queued} mengantre` : snapshot?.activity ? "Menunggu pembaruan aktivitas" : "Membaca antrean sistem…"}</strong><span>{status.observedAt ? `Diperbarui ${officeTime(status.observedAt)}` : ""}</span></div>
    {snapshot?.departments.length ? <><OfficeLiveDesk snapshot={snapshot} now={now} refreshFailed={refreshFailed} selected={department} onSelect={setDepartment} /><OfficeStudioFloor snapshot={snapshot} now={now} refreshFailed={refreshFailed} selected={department} onSelect={setDepartment} /></> : <div className="officeFloor officeFloorLoading"><Loader2 size={22} /><h3>{refreshFailed ? "Kantor belum dapat dihubungi" : "Menyiapkan kantor…"}</h3></div>}
    <nav className="officeWorkTools" aria-label="Alat kerja studio"><a href="/#quick-start-title">Buat video <ArrowUpRight size={13} /></a><a href="/#results">Hasil video <ArrowUpRight size={13} /></a><a href="/#history">Riwayat produksi <ArrowUpRight size={13} /></a><a href="/#facebook">Facebook Studio <ArrowUpRight size={13} /></a><a href="/#settings">Koneksi platform <ArrowUpRight size={13} /></a></nav>
    <section className="officeWorkBoard" aria-labelledby="office-work-title"><header className="officeSectionHead"><h3 id="office-work-title">Antrean & pekerjaan{department !== "all" ? ` · ${names.get(department) || department}` : ""}</h3>{department !== "all" ? <button className="officeQuietButton" type="button" onClick={() => setDepartment("all")}>Semua bagian</button> : <span className="officeTotal">{status.fresh ? `${work.length} terlihat` : "Data belum mutakhir"}</span>}</header>
      {!status.fresh ? <p className="officeWorkEmpty">Status pekerjaan menunggu data antrean terbaru dari server.</p> : !work.length ? <p className="officeWorkEmpty"><CheckCheck size={16} />Tidak ada pekerjaan aktif pada pilihan ini.</p> : <ol className="officeWorkList">{work.slice(0,12).map(item => <li className={`is-${item.state}`} key={`${item.department}:${item.id}`} data-work-id={item.id} data-stage={item.stage_key || undefined}>
        <span className="officeWorkState">{item.state === "running" ? <Radio size={13} /> : item.state === "queued" ? <Clock3 size={13} /> : <TriangleAlert size={13} />}{officeWorkLabel[item.state]}</span>
        <div><a href={`/#${item.destination}`}>{item.title}<ArrowUpRight size={12} /></a><p>{names.get(item.department)}{item.platform ? ` · ${item.platform}` : ""} · {item.stage}</p>{item.job_id ? <small>Job {item.job_id.slice(0,8)}</small> : null}{item.state === "running" && item.progress_percent != null ? <span className="officeWorkMeter"><i style={{ width: `${Math.round(item.progress_percent)}%` }} /></span> : null}</div>
        <span className="officeWorkProgress">{item.state === "running" && item.progress_percent != null ? `${Math.round(item.progress_percent)}%` : "—"}</span>
      </li>)}</ol>}
      {work.length > 12 ? <a className="officeWorkMore" href="/#history">Lihat pekerjaan lainnya <ArrowUpRight size={13} /></a> : null}
    </section>
    {incidents.length || !observed && snapshot ? <details className="officeIncidentBoard"><summary><TriangleAlert size={14} />{observed ? `${incidents.length} kendala${incidents.some(row=>row.state==="needs_operator") ? " · perlu diperiksa" : ""}${snapshot?.director?.active_repair ? " · pimpinan memperbaiki" : ""}` : "Status kendala belum tersedia"}</summary><ol className="officeIncidentList">{incidents.map(item => <li key={item.id}><div><div className="officeIncidentMeta">{names.get(item.department)} · {item.state === "needs_operator" ? "Perlu keputusan Anda" : "Menunggu pemulihan"}</div><h4>{item.title}</h4><p>{item.reason}</p><a href={`/#${item.destination}`}>{item.destination === "settings" ? "Kelola koneksi" : "Lihat pekerjaan"}<ArrowUpRight size={12} /></a>{item.job_id && ["review_quality", "defer_manual_review"].includes(item.action) ? <span className="officeReviewActions"><button type="button" disabled={Boolean(reviewBusy)} onClick={() => void actOnReview(item.job_id!, "retry")}><RotateCcw size={12} />Ulangi beda pendekatan</button><button type="button" disabled={Boolean(reviewBusy)} onClick={() => void actOnReview(item.job_id!, "delete")}><Trash2 size={12} />Hapus dari antrean</button></span> : null}</div></li>)}</ol></details> : null}
  </section>;
}
