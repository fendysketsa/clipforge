"use client";
import { useEffect, useState } from "react";
import { Crown, Pause, Play } from "lucide-react";
import { officeMotion, officeStateLabel, officeStatus, type AIOfficeSnapshot } from "../../lib/aiOffice";

const team: Record<string, { role: string; color: string; initials: string }> = {
  production: { role: "Produser & peneliti", color: "#65aa96", initials: "PR" },
  quality: { role: "Editor & auditor", color: "#a495ce", initials: "QC" },
  distribution: { role: "Manajer distribusi", color: "#7dadd1", initials: "UP" },
  recovery: { role: "Teknisi pemulihan", color: "#d2a571", initials: "RE" },
  cleanup: { role: "Pengelola aset", color: "#9ebd79", initials: "AS" },
  facebook: { role: "Produser Facebook", color: "#828fd0", initials: "FB" },
};
function AgentDesk({ color, variant }: { color: string; variant: number }) {
  return <svg className="officeDeskDrawing" viewBox="0 0 160 115" aria-hidden="true">
    <ellipse cx="80" cy="105" rx="58" ry="7" fill="currentColor" opacity=".05" />
    <path d="M25 69h110v9H25zM32 78h5v23h-5zm91 0h5v23h-5z" fill="var(--office-desk)" />
    <rect x="54" y="28" width="61" height="38" rx="4" fill="var(--office-monitor)" />
    <rect x="58" y="32" width="53" height="29" rx="2" fill={color} opacity=".17" />
    <g className="officeMonitorLines" stroke={color} strokeWidth="2" strokeLinecap="round"><path d="M65 41h21m-21 6h34m-34 6h15" /><path className="officeCursor" d="M87 53h10" /></g>
    <path d="M80 66v4m-10 0h24" stroke="var(--office-monitor)" strokeWidth="4" />
    <rect x="34" y="60" width="10" height="10" rx="2" fill={color} /><path d="M44 62h3v5h-3" fill="none" stroke={color} strokeWidth="2" />
    <path d="M120 58l-3-10m3 10 7-12m-6 12 8-4" stroke={color} strokeWidth="3" strokeLinecap="round" /><path d="M115 57h13l-2 13h-9z" fill="var(--office-monitor)" />
    <rect x="55" y="81" width="48" height="22" rx="8" fill="var(--office-chair)" />
    <g className="officeAgentPerson"><path d="M62 78q18-19 36 0v17H62z" fill={color} /><path d="M66 76l-6-8m34 8 6-8" stroke={color} strokeWidth="8" strokeLinecap="round" />
      <circle cx="80" cy="68" r="12" fill="#dcae91" /><path d={variant % 2 ? "M68 68v-6q2-13 14-10 13 1 10 17l-5-9q-9 7-19 8" : "M67 68q-2-17 14-17 15 1 12 18l-5-8-16 2z"} fill="#35434a" />
      <path d="M72 96v9m16-9v9" stroke="var(--office-monitor)" strokeWidth="5" strokeLinecap="round" /></g>
  </svg>;
}
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
  const status = officeStatus(snapshot, now, refreshFailed);
  const motion = officeMotion(snapshot, now, refreshFailed, visible && !paused && !reduced);
  const active = new Set(motion.activeDepartments);
  return <section className="officeFloor" aria-labelledby="office-floor-title" data-motion={motion.canAnimate ? "live" : "paused"}>
    <header className="officeSectionHead"><div><span className="studioEyebrow">TIM OPERASIONAL</span><h3 id="office-floor-title">Di balik setiap video.</h3></div>
      <button type="button" className="officeQuietButton" aria-pressed={paused} disabled={reduced} title="Mengatur gerakan tampilan; pekerjaan server tetap berjalan."
        onClick={() => setPaused(value => !value)}>{paused || reduced ? <Play size={13} /> : <Pause size={13} />}{reduced ? "Gerak minimal" : paused ? "Aktifkan gerak" : "Jeda gerak"}</button></header>
    <div className="officeDirectorDesk"><span className="officeDirectorAvatar"><Crown size={23} /></span>
      <div><span>DIREKTUR STUDIO</span><strong>Prioritas jelas. Tim terarah.</strong><p>{status.stale ? "Menunggu pembaruan dari koordinator." : !snapshot.enabled ? "Koordinasi dijeda sesuai pengaturan." : "Memantau kendala, membagi arahan, memeriksa tindak lanjut."}</p></div><span className="officeDirectorSignal" aria-label={status.label} /></div>
    <div className="officeFloorRooms">{snapshot.departments.map((department, index) => {
      const member = team[department.id] || { role: department.role, color: "#65aa96", initials: "AI" };
      return <button type="button" className={`officeRoom${active.has(department.id) ? " is-working" : ""}${department.state === "degraded" ? " is-degraded" : ""}`}
        key={department.id} data-department={department.id} aria-pressed={selected === department.id} title={department.role + " " + department.detail} onClick={() => onSelect(selected === department.id ? "all" : department.id)}>
        <span className="officeRoomTop"><span>{member.initials}</span><span><i />{status.stale ? "Status terakhir" : officeStateLabel[department.state]}</span></span>
        <AgentDesk color={member.color} variant={index} /><strong>{department.name}</strong><span className="officeRoomRole">{member.role}</span>
        <span className="officeRoomWork">{status.stale ? "Menunggu pembaruan" : department.active_count > 0 ? `${department.active_count} pekerjaan aktif` : department.detail}</span>
      </button>;
    })}</div>
    <p className="officeFloorLegend"><i />{status.stale ? "Menampilkan pengamatan terakhir." : `${active.size} bagian sedang bekerja.`} Pilih meja untuk melihat kendalanya.</p>
  </section>;
}
