"use client";
import { useEffect, useState } from "react";
import { Activity, ArrowDownLeft, ArrowUpRight, CheckCheck, CirclePause, Clock3, Loader2, Radio, RefreshCw, ShieldCheck, TriangleAlert } from "lucide-react";
import toast from "react-hot-toast";
import { getAIOffice, requestAIOfficeCheck } from "../../lib/apiClient";
import { officeIncidents, officeStateLabel, officeStatus, officeTaskLabel, officeTime, type AIOfficeSnapshot } from "../../lib/aiOffice";
import { createPollingTask } from "../../lib/pollTask";
import { OfficeProcessMap } from "./OfficeProcessMap";
import { OfficeStudioFloor } from "./OfficeStudioFloor";

export function AIOfficePanel() {
  const [snapshot, setSnapshot] = useState<AIOfficeSnapshot | null>(null);
  const [refreshFailed, setRefreshFailed] = useState(false), [requesting, setRequesting] = useState(false);
  const [now, setNow] = useState(Date.now), [filter, setFilter] = useState("all"), [department, setDepartment] = useState("all");
  useEffect(() => {
    const poll = createPollingTask(async current => {
      try { const result = await getAIOffice(); if (current()) { setSnapshot(result); setRefreshFailed(false); setNow(Date.now()); } }
      catch { if (current()) { setRefreshFailed(true); setNow(Date.now()); } }
    }, () => !document.hidden);
    void poll.run();
    const timer = window.setInterval(poll.run, 15_000), clock = window.setInterval(() => setNow(Date.now()), 10_000);
    window.addEventListener("focus", poll.run); document.addEventListener("visibilitychange", poll.run);
    return () => { poll.stop(); window.clearInterval(timer); window.clearInterval(clock); window.removeEventListener("focus", poll.run); document.removeEventListener("visibilitychange", poll.run); };
  }, []);
  const check = async () => {
    if (requesting) return;
    setRequesting(true);
    try { const result = await requestAIOfficeCheck(); if (result.accepted) toast.success(result.message); else toast.error(result.message);
      setSnapshot(await getAIOffice()); setRefreshFailed(false); setNow(Date.now()); }
    catch (error) { toast.error(error instanceof Error ? error.message : "Koordinator belum dapat menerima pemeriksaan."); }
    finally { setRequesting(false); }
  };
  const status = officeStatus(snapshot, now, refreshFailed);
  const StatusIcon = status.state === "working" ? Radio : status.state === "disabled" ? CirclePause : status.state === "degraded" ? TriangleAlert : status.state === "starting" ? Loader2 : ShieldCheck;
  const departments = new Map(snapshot?.departments.map(item => [item.id, item.name]) || []);
  const tasks = snapshot?.tasks.slice(-8).reverse() || [], incidents = officeIncidents(snapshot, filter, department);
  const observed = snapshot?.control_version === 2 && snapshot.incident_observation_available, stats = snapshot?.director;
  const metrics = [
    { label: "Produksi aktif", value: observed ? stats?.active_jobs : undefined, icon: Activity, detail: "Video yang sedang diproses" },
    { label: "Distribusi aktif", value: observed ? stats?.active_uploads : undefined, icon: ArrowUpRight, detail: "Antrean & pengiriman platform" },
    { label: "Kendala terbuka", value: observed ? stats?.open_incidents : undefined, icon: TriangleAlert, detail: "Memiliki penanggung jawab" },
    { label: "Perlu keputusan Anda", value: observed ? stats?.needs_operator : undefined, icon: ArrowDownLeft, detail: "Akses, izin, atau persetujuan" },
  ];
  return <section className={`officeHQ is-${status.state}`} aria-labelledby="ai-office-title">
    <header className="officeHQHeading"><div><span className="studioEyebrow">RYUUNDY / STUDIO OPERATIONS</span>
      <h1 id="ai-office-title">Kantor AI<span>Studio dikelola. Kendala ditangani.</span></h1><p>Satu ruang untuk tim produksi, kualitas, distribusi, dan pemulihan studio Anda.</p></div>
      <button className="officeCommand" type="button" disabled={requesting || !snapshot?.enabled} onClick={() => { void check(); }}>{requesting ? <Loader2 size={16} className="spin" /> : <RefreshCw size={16} />}{requesting ? "Mengirim arahan…" : "Koordinasikan sekarang"}</button></header>
    <div className="officeHQStatus" role="status"><StatusIcon size={16} /><strong>{status.label}</strong><span>{snapshot?.last_tick_at ? `Diperiksa ${officeTime(snapshot.last_tick_at)}` : status.detail}</span>{status.stale ? <small>Data terakhir · menunggu pembaruan</small> : snapshot?.enabled ? <small>Pengawasan otomatis</small> : null}</div>
    <div className="officeMetrics">{metrics.map(metric => <article key={metric.label}><span><metric.icon size={15} />{metric.label}</span><strong>{metric.value ?? "—"}</strong><small>{status.stale ? "Pengamatan terakhir" : metric.detail}</small></article>)}</div>
    <div className="officeHQColumns"><div className="officeMainColumn">
      {snapshot?.departments.length ? <OfficeStudioFloor snapshot={snapshot} now={now} refreshFailed={refreshFailed} selected={department} onSelect={setDepartment} /> : <div className="officeFloor officeFloorLoading"><Loader2 size={22} className={!refreshFailed ? "spin" : ""} /><h3>{refreshFailed ? "Kantor belum dapat dihubungi" : "Menyiapkan ruang studio…"}</h3><p>{status.detail}</p></div>}
      <section className="officeIncidentBoard" aria-labelledby="office-incidents-title"><header className="officeSectionHead"><div><span className="studioEyebrow">MEJA PENANGANAN</span><h3 id="office-incidents-title">Setiap kendala punya pemilik.</h3></div><span className="officeTotal">{observed ? `${incidents.length} kendala` : "Belum terbaca"}</span></header>
        <div className="officeFilters" role="group" aria-label="Filter kendala studio">{[['all','Semua'],['automatic','Ditangani otomatis'],['operator','Perlu Anda']].map(([key,label]) => <button type="button" key={key} aria-pressed={filter === key} onClick={() => setFilter(key)}>{label}</button>)}{department !== "all" ? <button type="button" onClick={() => setDepartment("all")} className="officeClearFilter">{departments.get(department)} ×</button> : null}</div>
        {!observed ? <div className="officeEmpty"><Clock3 size={24} /><strong>Status kendala belum tersedia</strong><p>{snapshot?.control_version !== 2 ? "Pusat kendala memerlukan backend Kantor AI terbaru. Status tim yang tersedia tetap ditampilkan." : "Pengamatan kendala belum berhasil. Data kosong belum berarti semua pekerjaan sudah selesai."}</p></div>
          : !incidents.length ? <div className="officeEmpty"><CheckCheck size={26} /><strong>{department === "all" && filter === "all" ? "Tidak ada kendala terdeteksi" : "Tidak ada kendala pada pilihan ini"}</strong><p>{status.stale ? "Ini adalah hasil pengamatan terakhir; menunggu pembaruan server." : "Direktur terus memantau pekerjaan dan antrean studio."}</p></div>
          : <ol className="officeIncidentList">{incidents.map(incident => <li key={incident.id} className={`is-${incident.severity}`}><span className="officeIncidentMark"><TriangleAlert size={16} /></span><div><div className="officeIncidentMeta"><span>{departments.get(incident.department) || incident.department}</span><span>{incident.state === "needs_operator" ? "Perlu keputusan Anda" : incident.automatic && snapshot?.enabled && !status.stale ? "Koordinasi otomatis" : "Menunggu pemeriksaan"}</span></div><h4>{incident.title}</h4><p>{incident.reason}</p><a href={`/#${incident.destination}`}>{incident.destination === "settings" ? "Kelola koneksi" : "Lihat pekerjaan"}<ArrowUpRight size={12} /></a></div></li>)}</ol>}
      </section></div>
      <aside className="officeSideColumn"><section className="officeDirectorBrief"><span className="studioEyebrow">ARAHAN DIREKTUR</span><h3>Alur yang terus dijaga.</h3><ol>
        <li><span>01</span><div><strong>Temukan hambatan</strong><p>Baca kondisi produksi, hasil QC, dan bukti pengiriman.</p></div></li><li><span>02</span><div><strong>Pilih langkah pemulihan</strong><p>Ulangi gangguan sementara, gunakan cadangan yang tersedia, atau lewati sumber yang tidak layak.</p></div></li><li><span>03</span><div><strong>Pastikan hasilnya</strong><p>Kendala ditutup setelah tidak lagi ditemukan pada pemeriksaan.</p></div></li>
      </ol><p className="officeDirectorNote"><ShieldCheck size={15} />Keputusan dan jeda pemulihan tersimpan. QC serta konfirmasi platform tetap menentukan hasil.</p></section>
      <section className="officeJournal"><header className="officeSectionHead"><div><span className="studioEyebrow">BUKU KERJA</span><h3>Keputusan terbaru</h3></div><Clock3 size={16} /></header>
        {tasks.length ? <ol>{tasks.map(task => <li key={task.id} className={`is-${task.status}`}><i /><span>{officeTime(task.finished_at || task.started_at)}</span><strong>{task.action}</strong><p>{task.summary}</p><small>{departments.get(task.department) || task.department} · {officeTaskLabel[task.status]}</small>{task.next_retry_at ? <small>Berikutnya {officeTime(task.next_retry_at)}</small> : null}</li>)}</ol> : <div className="officeJournalEmpty"><p>Belum ada arahan tambahan.</p><small>Aktivitas akan dicatat saat koordinator menugaskan pekerjaan.</small></div>}</section>
      {(snapshot?.resolved_incidents?.length ?? 0) > 0 ? <details className="officeResolved"><summary><CheckCheck size={15} />Kendala yang telah ditutup <span>{snapshot!.resolved_incidents!.length}</span></summary><ul>{snapshot!.resolved_incidents!.slice().reverse().map(item => <li key={item.id}><strong>{item.title}</strong><small>Tidak ditemukan lagi · {officeTime(item.resolved_at || null)}</small></li>)}</ul></details> : null}
      </aside></div>
    {snapshot?.departments.length ? <details className="officeSystemDetails"><summary>Rincian alur & tanggung jawab bagian</summary><div className="officeRoleDetails">{snapshot.departments.map(item => <div key={item.id}><strong>{item.name} · {officeStateLabel[item.state]}</strong><p>{item.role}</p><small>{item.detail}</small></div>)}</div><OfficeProcessMap snapshot={snapshot} now={now} refreshFailed={refreshFailed} /></details> : null}
  </section>;
}
