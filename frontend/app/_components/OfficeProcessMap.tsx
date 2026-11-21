"use client";

import { useEffect, useState } from "react";
import { Archive, ArrowDown, ChevronRight, Cpu, Facebook, Film, Pause, Play, ScanLine, UploadCloud, Wrench } from "lucide-react";
import { officeMotion, officeStateLabel, officeStatus, type AIOfficeSnapshot } from "../../lib/aiOffice";

const mainStages = [
  { id: "production", label: "Produksi", icon: Film },
  { id: "quality", label: "QC & perbaikan", icon: ScanLine },
  { id: "distribution", label: "Distribusi", icon: UploadCloud },
];
const supportStages = [
  { id: "recovery", label: "Pemulihan", icon: Wrench },
  { id: "cleanup", label: "Kebersihan", icon: Archive },
  { id: "facebook", label: "Facebook Studio", icon: Facebook },
];

export function OfficeProcessMap({ snapshot, now, refreshFailed }: {
  snapshot: AIOfficeSnapshot; now: number; refreshFailed: boolean;
}) {
  const [visible, setVisible] = useState(true);
  const [paused, setPaused] = useState(false);
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const visibility = () => setVisible(!document.hidden);
    const preference = () => setReduced(media.matches);
    visibility(); preference();
    document.addEventListener("visibilitychange", visibility);
    media.addEventListener("change", preference);
    return () => { document.removeEventListener("visibilitychange", visibility); media.removeEventListener("change", preference); };
  }, []);
  const status = officeStatus(snapshot, now, refreshFailed);
  const motion = officeMotion(snapshot, now, refreshFailed, visible && !paused && !reduced);
  const departments = new Map(snapshot.departments.map(department => [department.id, department]));
  const active = new Set(motion.activeDepartments);
  const supervisor = status.stale ? "Menunggu pembaruan" : !snapshot.enabled ? "Koordinator dijeda"
    : status.state === "degraded" ? "Memerlukan pemulihan" : status.state === "starting" ? "Menyiapkan pemeriksaan" : "Memantau & mengarahkan";
  const node = (stage: typeof mainStages[number], support = false) => {
    const department = departments.get(stage.id);
    const Icon = stage.icon;
    const working = active.has(stage.id);
    const moving = working && motion.canAnimate;
    return <article key={stage.id} data-department={stage.id}
      className={`aiOfficeStation${support ? " is-support" : ""}${working ? " is-working" : ""}${moving ? " is-moving" : ""}${department?.state === "degraded" ? " is-degraded" : ""}`}>
      <span className="aiOfficeStationIcon" aria-hidden="true"><Icon size={support ? 17 : 21} /><i /></span>
      <div><strong>{department?.name || stage.label}</strong><span>{!department ? "Status belum tersedia" : status.stale ? "Status terakhir"
        : department.active_count > 0 ? `${department.active_count} pekerjaan aktif` : officeStateLabel[department.state]}</span></div>
      {!support ? <div className="aiOfficeProcessTrack" aria-hidden="true"><i /></div> : <span className="aiOfficeBranchSignal" aria-hidden="true"><i /><i /><i /></span>}
    </article>;
  };
  const branches = supportStages.filter(stage => departments.has(stage.id));
  return <div className={`aiOfficeProcessMap${status.stale ? " is-stale" : ""}`} data-motion={motion.canAnimate ? "live" : "paused"} aria-label="Peta proses Kantor AI">
    <div className="aiOfficeMapHeading"><div><span className="studioEyebrow">ALUR KERJA LANGSUNG</span><p>Gerak mengikuti bagian yang sedang bekerja.</p></div>
      <button type="button" className="aiOfficeMotionToggle" disabled={reduced} aria-pressed={paused}
        title={reduced ? "Gerak minimal mengikuti preferensi perangkat." : "Hanya mengatur animasi tampilan; pekerjaan server tetap berjalan."}
        onClick={() => setPaused(value => !value)}>{paused || reduced ? <Play size={12} /> : <Pause size={12} />}{reduced ? "Gerak minimal" : paused ? "Aktifkan animasi" : "Jeda animasi"}</button>
    </div>
    <div className={`aiOfficeSupervisor${motion.monitoring ? " is-monitoring" : ""}`}>
      <span className="aiOfficeSupervisorCore" aria-hidden="true"><i /><Cpu size={25} /><b /><b /><b /></span>
      <div><strong>Koordinator</strong><span>{supervisor}</span></div>
      <ArrowDown className="aiOfficeSupervisorArrow" size={16} aria-hidden="true" />
    </div>
    <div className="aiOfficePipeline">
      {mainStages.flatMap((stage, index) => index === 0 ? [node(stage)] : [
        <span key={`link-${stage.id}`} className={`aiOfficeFlowLink${motion.canAnimate && active.has(mainStages[index - 1].id) && active.has(stage.id) ? " is-flowing" : ""}`} aria-hidden="true"><i /><ChevronRight size={15} /></span>, node(stage),
      ])}
    </div>
    {branches.length ? <div className="aiOfficeBranches" aria-label="Bagian pendukung">{branches.map(stage => node(stage, true))}</div> : null}
    <p className="aiOfficeMapLegend"><span />Indikator proses menunjukkan aktivitas, bukan persentase penyelesaian.</p>
  </div>;
}
