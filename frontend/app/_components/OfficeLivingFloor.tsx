"use client";
import { useEffect, useRef, useState } from "react";
import { MessageCircle, Minus, Plus, Radio, RotateCcw, Sun, Moon, Users } from "lucide-react";
import { officeActivityStatus, officeAgentWork, officeWorkLabel, officeSpeech, type AIOfficeSnapshot } from "../../lib/aiOffice";
import { OFFICE_PEOPLE, type OfficeActivity } from "../../lib/officeChoreography";
import type { createOfficeScene, OfficeProjection } from "../../lib/createOfficeScene";

const areaLabels = ["Ruang rapat", "Produksi & QC", "Distribusi & pemulihan", "Studio sosial & aset", "Lounge", "Coffee bar"];
const areaIds = ["meeting", "creative", "media", "assets", "lounge", "pantry"];
const activityLabel: Record<OfficeActivity, string> = { desk: "Di meja kerja", walk: "Berjalan", meeting: "Diskusi tim", coffee: "Di coffee bar", lounge: "Di lounge" };

export function Office3DFloor({ snapshot, now, refreshFailed, selected, onSelect, animate }: {
  snapshot: AIOfficeSnapshot; now: number; refreshFailed: boolean; selected: string; onSelect: (value: string) => void; animate: boolean;
}) {
  const host = useRef<HTMLDivElement>(null);
  const labels = useRef(new Map<string, HTMLButtonElement>()), areas = useRef(new Map<string, HTMLSpanElement>());
  const scene = useRef<ReturnType<typeof createOfficeScene> | null>(null);
  const elapsed = useRef(0), signature = useRef("");
  const [ready, setReady] = useState(false), [failed, setFailed] = useState(false), [inView, setInView] = useState(true);
  const [bubbles, setBubbles] = useState(true), [zoom, setZoom] = useState(1), [lighting, setLighting] = useState<"auto" | "day" | "night">("auto");
  const [activities, setActivities] = useState<Record<string, OfficeActivity>>({});
  const status = officeActivityStatus(snapshot, now, refreshFailed);
  const hour = new Date(now).getUTCHours();
  const night = lighting === "night" || lighting === "auto" && hour >= 12 && hour < 22;
  const states = Object.fromEntries(snapshot.departments.map(row => [row.id,officeAgentWork(snapshot,row.id,now,refreshFailed).state]));
  const latest = useRef({ selected, bubbles, states });
  latest.current = { selected, bubbles, states };
  useEffect(() => {
    if (!host.current) return;
    const element = host.current;
    let disposed = false;
    const project = (people: OfficeProjection[], rooms: OfficeProjection[]) => {
      const priority: Record<string,number> = { running:0,blocked:1,queued:2 };
      const candidates = people.filter(person => latest.current.states[person.id] in priority)
        .sort((a,b)=>priority[latest.current.states[a.id]]-priority[latest.current.states[b.id]]);
      const lead = candidates[0];
      const second = lead ? candidates.find(person => Math.hypot(person.x-lead.x,person.y-lead.y)>180) : undefined;
      for (const person of people) {
        const label = labels.current.get(person.id);
        if (!label) continue;
        label.style.left = `${person.x}px`; label.style.top = `${person.y}px`;
        const focus = latest.current.selected;
        const talking = latest.current.bubbles && (focus === person.id || focus === "all" && (person.id === lead?.id || person.id === second?.id));
        label.dataset.bubble = String(talking); label.style.zIndex = talking ? "6" : "3";
        const half = element.clientWidth < 640 ? 57.5 : 76.5;
        const shift = Math.max(half + 10 - person.x, Math.min(0, element.clientWidth - half - 10 - person.x));
        label.style.setProperty("--speech-shift", `${shift}px`);
        label.dataset.activity = person.activity;
      }
      for (const room of rooms) {
        const label = areas.current.get(room.id);
        if (label) { label.style.left = `${room.x}px`; label.style.top = `${room.y}px`; }
      }
      const next = people.map(person => person.activity).join("|");
      if (signature.current !== next) { signature.current = next; setActivities(Object.fromEntries(people.map(person => [person.id, person.activity]))); }
    };
    void import("../../lib/createOfficeScene").then(({ createOfficeScene }) => {
      if (disposed) return;
      scene.current = createOfficeScene(element, project); setReady(true);
    }).catch(() => { if (!disposed) { element.replaceChildren(); setFailed(true); } });
    const observer = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting), { rootMargin: "80px" });
    observer.observe(element);
    return () => { disposed = true; observer.disconnect(); scene.current?.dispose(); scene.current = null; };
  }, []);
  useEffect(() => {
    if (!ready || !scene.current) return;
    scene.current.zoom(zoom); scene.current.render(elapsed.current, night, latest.current.states);
    if (!animate || !inView) return;
    let frame = 0, previous = performance.now();
    const tick = (time: number) => {
      if (time - previous >= 32) {
        elapsed.current += Math.min((time - previous) / 1000, .1); previous = time;
        scene.current?.render(elapsed.current, night, latest.current.states);
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [ready, animate, inView, night, zoom]);
  useEffect(() => { scene.current?.render(elapsed.current, night, latest.current.states); }, [selected, bubbles, night, snapshot]);

  const chosen = OFFICE_PEOPLE.find(person => person.id === selected);
  const department = snapshot.departments.find(row => row.id === selected);
  const chosenWork = officeAgentWork(snapshot,selected,now,refreshFailed);
  return <div className={`officeDiorama${night ? " is-night" : ""}`}>
    <div className="officeDioramaBar"><div><span className="officeDioramaMark"><Users size={14} /></span><strong>RYUUNDY HQ <span>/ LANTAI 01</span></strong></div>
      <span className={`officeConnection${!status.fresh ? " is-stale" : ""}`}><i />{!status.fresh ? "Data terakhir" : "Antrean langsung"}</span></div>
    <div className="office3dFloor officeDioramaStage" data-ready={ready} data-animated={animate && inView} aria-label="AI Office 3D: ruangan kantor, karyawan berjalan, dan bubble percakapan">
      <div ref={host} className="officeCanvas" aria-hidden="true" />
      {!ready ? <div className="officeSceneLoading" role="status"><Users size={28} /><strong>{failed ? "Tampilan 3D tidak tersedia" : "Membuka pintu studio…"}</strong><span>{failed ? "Gunakan daftar tim di bawah untuk melihat aktivitas." : "Menyiapkan ruangan & tim Anda"}</span></div> : null}
      {ready ? <div className="officeSceneLabels" data-bubbles={bubbles}>{areaIds.map((id, index) => <span className={`officeAreaLabel is-${id}`} key={id} ref={element => { if (element) areas.current.set(id, element); else areas.current.delete(id); }}>{areaLabels[index]}</span>)}
        {OFFICE_PEOPLE.map(person => {
          const activity = activities[person.id] || "desk";
          const work = officeAgentWork(snapshot,person.id,now,refreshFailed);
          const speech = officeSpeech(snapshot, person.id, now, refreshFailed);
          return <button type="button" key={person.id} ref={element => { if (element) labels.current.set(person.id, element); else labels.current.delete(person.id); }}
            className={`officeWalker officePersonLabel${selected === person.id ? " is-selected" : ""}`} style={{ ["--person-color" as string]: person.color }}
            data-person={person.id} data-work-state={work.state} data-job-id={work.work[0]?.job_id || undefined} data-bubble="false" aria-pressed={selected === person.id}
            aria-label={`${person.name}, ${person.role}. ${activityLabel[activity]}. ${speech.text}`}
            onClick={() => onSelect(selected === person.id ? "all" : person.id)}>
            <span className="officeSpeech"><span><Radio size={10} />{officeWorkLabel[work.state]}</span><strong>{speech.text}</strong></span>
            <span className="officePersonName"><i />{person.name}<small>{person.role}</small></span>
          </button>;
        })}</div> : null}
      <div className="officeSceneTools" aria-label="Kontrol tampilan kantor"><button type="button" aria-label="Perkecil kantor" disabled={zoom <= .85} onClick={() => setZoom(value => Math.max(.85, value - .15))}><Minus size={15} /></button>
        <button type="button" aria-label="Atur ulang pembesaran" onClick={() => setZoom(1)}><RotateCcw size={13} /></button>
        <button type="button" aria-label="Perbesar kantor" disabled={zoom >= 1.3} onClick={() => setZoom(value => Math.min(1.3, value + .15))}><Plus size={15} /></button>
        <span /><button type="button" aria-pressed={bubbles} aria-label="Tampilkan bubble percakapan" onClick={() => setBubbles(value => !value)}><MessageCircle size={15} /></button>
        <button type="button" aria-label={lighting === "auto" ? "Pencahayaan otomatis, ubah ke siang" : lighting === "day" ? "Pencahayaan siang, ubah ke malam" : "Pencahayaan malam, ubah ke otomatis"} onClick={() => setLighting(value => value === "auto" ? "day" : value === "day" ? "night" : "auto")}>{night ? <Moon size={15} /> : <Sun size={15} />}</button></div>
    </div>
    <div className="officeDioramaFooter"><span><Radio size={13} />{status.fresh ? "Aktivitas mengikuti antrean sistem" : "Menunggu pembaruan aktivitas"}</span></div>
    {chosen && department ? <div className="officePersonDetail"><span style={{ background: chosen.color }}>{chosen.name.charAt(0)}</span><div><strong>{chosen.name} <small>{department.name}</small></strong><p>{chosenWork.work[0] ? `${chosenWork.work[0].stage} · ${chosenWork.work[0].title}` : chosenWork.detail}</p></div><span>{officeWorkLabel[chosenWork.state]}</span></div> : null}
  </div>;
}
