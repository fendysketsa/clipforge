"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { Crown, Loader2, Hand, TriangleAlert, Moon, CheckCheck, Radio } from "lucide-react";
import type { AIOfficeSnapshot } from "../../lib/aiOffice";

type Room = { id: string; name: string; initials: string; color: string; x: number; y: number };
const ROOMS: Room[] = [
  { id: "production", name: "Produksi", initials: "PR", color: "#65aa96", x: 15, y: 32 },
  { id: "quality", name: "QC", initials: "QC", color: "#a495ce", x: 50, y: 32 },
  { id: "distribution", name: "Distribusi", initials: "UP", color: "#7dadd1", x: 85, y: 32 },
  { id: "recovery", name: "Pemulihan", initials: "RE", color: "#d2a571", x: 15, y: 79 },
  { id: "cleanup", name: "Kebersihan", initials: "AS", color: "#9ebd79", x: 50, y: 79 },
  { id: "facebook", name: "Facebook", initials: "FB", color: "#828fd0", x: 85, y: 79 },
];
const HUB = { x: 50, y: 55 };

function statusOf(snapshot: AIOfficeSnapshot, id: string) {
  const row = snapshot.departments.find(item => item.id === id);
  if (!row) return { state: "waiting", active: 0 };
  return { state: row.state, active: row.active_count };
}

function AgentSprite({ room, state, moving, index }: { room: Room; state: string; moving: boolean; index: number }) {
  const Icon = state === "degraded" ? TriangleAlert : state === "needs_operator" ? Hand
    : state === "working" ? Loader2 : state === "disabled" ? Moon : CheckCheck;
  return <div className={`officeWalker is-${state}${moving ? " is-moving" : ""}`} style={{ ["--walk-color" as string]: room.color }}>
    <span className="officeWalkerBadge"><Icon size={13} className={state === "working" ? "spin" : undefined} /></span>
    <svg viewBox="0 0 48 66" aria-hidden="true" className="officeWalkerBody">
      <ellipse cx="24" cy="62" rx="14" ry="3.5" className="officeWalkerShadow" />
      <g className="officeWalkerLegs"><path d="M18 46v13m12-13v13" stroke="currentColor" strokeWidth="5" strokeLinecap="round" /></g>
      <path d="M13 28q11-8 22 0l3 19H10z" fill="currentColor" />
      <g className="officeWalkerArms"><path d="M14 31 7 42m27-11 7 11" stroke="currentColor" strokeWidth="5" strokeLinecap="round" /></g>
      <circle cx="24" cy="20" r="10" fill="#e8b999" />
      <path d={index % 2 ? "M14 20q-1-13 11-12 11 1 9 14l-4-9q-8 6-16 7" : "M14 21q-2-14 11-13 12 1 9 14l-4-8-14 2z"} fill="#35434a" />
      <circle cx="20" cy="20" r="1.4" fill="#35434a" /><circle cx="28" cy="20" r="1.4" fill="#35434a" />
    </svg>
    <span className="officeWalkerTag">{room.initials}</span>
  </div>;
}

export function Office3DFloor({ snapshot, now, refreshFailed, selected, onSelect }: {
  snapshot: AIOfficeSnapshot; now: number; refreshFailed: boolean; selected: string; onSelect: (value: string) => void;
}) {
  const [moving, setMoving] = useState(false);
  const previous = useRef("");
  const hour = useMemo(() => new Date(now).getUTCHours(), [now]);
  const night = hour >= 12 && hour < 22; // 19:00–05:00 WIB
  const stale = refreshFailed || (Number.isFinite(Date.parse(snapshot.last_tick_at || "")) && now - Date.parse(snapshot.last_tick_at || "") > 120_000);

  const positions = useMemo(() => ROOMS.map(room => {
    const info = statusOf(snapshot, room.id);
    const needsOperator = (snapshot.incidents || []).some(row => row.department === room.id && row.state === "needs_operator");
    if (stale) return { room, x: HUB.x, y: HUB.y, state: "waiting", active: 0 };
    if (needsOperator) return { room, x: HUB.x + (room.x - HUB.x) * .35, y: HUB.y, state: "needs_operator", active: info.active };
    if (info.state === "degraded") return { room, x: 15, y: 76, state: "degraded", active: info.active };
    if (info.state === "disabled") return { room, x: 50, y: 92, state: "disabled", active: 0 };
    if (info.state === "working" || info.active > 0) return { room, x: room.x, y: room.y + 4, state: "working", active: info.active };
    return { room, x: room.x + (HUB.x - room.x) * .18, y: room.y - 4, state: "waiting", active: 0 };
  }), [snapshot, stale]);

  const signature = positions.map(row => `${row.state}:${Math.round(row.x)}:${Math.round(row.y)}`).join("|");
  useEffect(() => {
    if (previous.current && previous.current !== signature) {
      setMoving(true);
      const timer = window.setTimeout(() => setMoving(false), 1150);
      previous.current = signature;
      return () => window.clearTimeout(timer);
    }
    previous.current = signature;
  }, [signature]);

  const flow = positions.some(row => row.state === "working");
  return <div className={`office3dFloor${night ? " is-night" : ""}${flow ? " is-flowing" : ""}`} aria-label="AI Office 3D: lantai kantor AI yang bergerak mengikuti status worker">
    <div className="office3dSky" aria-hidden="true"><i /><i /><i /></div>
    <div className="office3dGrid" aria-hidden="true" />
    <div className="officeConveyor" aria-hidden="true"><span /><span /><span /><span /></div>
    <div className="officeDirectorPod"><span><Crown size={17} /></span><strong>Pimpinan Digital</strong><small>{snapshot.director?.strategy?.name || "Direktur Studio"}</small></div>
    {ROOMS.map((room, index) => {
      const info = statusOf(snapshot, room.id);
      return <button type="button" key={room.id} className={`officeZone${selected === room.id ? " is-selected" : ""}${info.state === "degraded" ? " is-alert" : ""}`}
        style={{ left: `${room.x}%`, top: `${room.y}%`, ["--room-color" as string]: room.color }}
        onClick={() => onSelect(selected === room.id ? "all" : room.id)} aria-label={`${room.name}: ${info.state}`}>
        <span className="officeZoneFloor" /><span className="officeZoneDesk"><i /><i /></span>
        <span className="officeZoneName">{room.name}</span>
        <span className="officeZoneCount">{info.active > 0 ? info.active : ""}</span>
      </button>;
    })}
    {positions.map((row, index) => <div key={row.room.id} className="officeWalkerSlot"
      style={{ left: `${row.x}%`, top: `${row.y}%` }}>
      <AgentSprite room={row.room} state={row.state} moving={moving} index={index} />
    </div>)}
    <div className="office3dLegend"><Radio size={12} /> AI Office 3D · {stale ? "Menampilkan pengamatan terakhir" : `${positions.filter(row => row.state === "working").length} agen bekerja`} · klik ruangan untuk menyaring kendala</div>
  </div>;
}
