"use client";
import { useEffect, useState } from "react";
import { Pause, Play } from "lucide-react";
import { officeActivityStatus, officeAgentWork, officeWorkLabel, type AIOfficeSnapshot } from "../../lib/aiOffice";
import { Office3DFloor } from "./OfficeLivingFloor";

export function OfficeStudioFloor({ snapshot, now, refreshFailed, selected, onSelect }: {
  snapshot: AIOfficeSnapshot; now: number; refreshFailed: boolean; selected: string; onSelect: (value: string) => void;
}) {
  const [paused, setPaused] = useState(false), [visible, setVisible] = useState(true), [reduced, setReduced] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => { setVisible(!document.hidden); setReduced(media.matches); };
    update(); document.addEventListener("visibilitychange", update); media.addEventListener("change", update);
    return () => { document.removeEventListener("visibilitychange", update); media.removeEventListener("change", update); };
  }, []);
  const animate = officeActivityStatus(snapshot,now,refreshFailed).fresh && visible && !paused && !reduced;
  return <section className="officeFloor" aria-label="Kantor AI 3D" data-motion={animate ? "live" : "paused"}>
    <header className="officeSectionHead"><h3>Aktivitas studio</h3><button type="button" className="officeQuietButton" aria-pressed={paused} disabled={reduced} title="Jeda tampilan; pekerjaan server tetap berjalan." onClick={() => setPaused(value => !value)}>{paused || reduced ? <Play size={13} /> : <Pause size={13} />}{reduced ? "Gerak minimal" : paused ? "Aktifkan gerak" : "Jeda gerak"}</button></header>
    <Office3DFloor snapshot={snapshot} now={now} refreshFailed={refreshFailed} selected={selected} onSelect={onSelect} animate={animate} />
    <div className="officeFloorRooms" role="group" aria-label="Pilih bagian">{snapshot.departments.map(department => {
      const row=officeAgentWork(snapshot,department.id,now,refreshFailed);
      return <button type="button" className={`officeRoom is-${row.state}`} key={department.id} data-department={department.id} aria-pressed={selected===department.id} onClick={()=>onSelect(selected===department.id ? "all":department.id)}><strong>{department.name}</strong><span>{officeWorkLabel[row.state]}{row.running_count ? ` · ${row.running_count}` : row.queued_count ? ` · ${row.queued_count}` : ""}</span></button>;
    })}</div>
  </section>;
}
