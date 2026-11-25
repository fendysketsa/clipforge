"use client";
import { useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowUp, Crosshair, MessageCircle, Minus, Plus, Radio, RotateCcw, RotateCw, Sun, Moon, Users } from "lucide-react";
import { officeActivityStatus, officeAgentWork, officeRepairAction, officeWorkLabel, officeSpeech, type AIOfficeSnapshot } from "../../lib/aiOffice";
import { OFFICE_PEOPLE, type OfficeActivity, type OfficeWorkCue } from "../../lib/officeChoreography";
import type { createOfficeScene, OfficeProjection } from "../../lib/createOfficeScene";

const areaLabels = ["Ruang rapat", "Produksi & QC", "Distribusi & pemulihan", "Studio sosial & aset", "Lounge", "Coffee bar"];
const areaIds = ["meeting", "creative", "media", "assets", "lounge", "pantry"];
const repairSeat: Record<string, number> = { production: 0, quality: 1, distribution: 2, recovery: 3, cleanup: 4, facebook: 5 };
const activityLabel: Record<OfficeActivity, string> = { desk: "Di meja kerja", walk: "Berjalan", greet: "Salaman saat papasan", patrol: "Keliling mengecek tim", meeting: "Diskusi tim", briefing: "Menerima arahan pimpinan", observing: "Memantau tim", notice: "Mengecek papan tugas", chat: "Berbincang dengan tim", coffee: "Di coffee bar", lounge: "Di lounge", reading: "Membaca", sofa: "Beristirahat sebentar", cards: "Menyusun ide", copy: "Menyiapkan bahan", write: "Menyiapkan langkah", call: "Menghubungi tim", snack: "Ngopi sebentar" };

export function Office3DFloor({ snapshot, now, refreshFailed, selected, onSelect, animate }: {
  snapshot: AIOfficeSnapshot; now: number; refreshFailed: boolean; selected: string; onSelect: (value: string) => void; animate: boolean;
}) {
  const host = useRef<HTMLDivElement>(null);
  const labels = useRef(new Map<string, HTMLButtonElement>()), areas = useRef(new Map<string, HTMLSpanElement>());
  const scene = useRef<ReturnType<typeof createOfficeScene> | null>(null);
  const elapsed = useRef(0), signature = useRef("");
  const [ready, setReady] = useState(false), [failed, setFailed] = useState(false), [inView, setInView] = useState(true);
  const saved = () => { try { return JSON.parse(localStorage.getItem('office3d-view') || '{}') as Record<string, unknown>; } catch { return {}; } };
  const initial = saved();
  const [bubbles, setBubbles] = useState(initial.bubbles !== false), [zoom, setZoom] = useState(typeof initial.zoom === 'number' ? initial.zoom : 1),
    [lighting, setLighting] = useState<"auto" | "day" | "night">(initial.lighting === 'day' || initial.lighting === 'night' ? initial.lighting : 'auto'),
    [follow, setFollow] = useState(initial.follow === true);
  useEffect(() => { try { localStorage.setItem('office3d-view', JSON.stringify({ bubbles, zoom, lighting, follow })); } catch { /* storage unavailable */ } }, [bubbles, zoom, lighting, follow]);
  const [activities, setActivities] = useState<Record<string, OfficeActivity>>({});
  const [chats, setChats] = useState<Record<string, string>>({});
  const status = officeActivityStatus(snapshot, now, refreshFailed);
  const hour = new Date(now).getUTCHours();
  const night = lighting === "night" || lighting === "auto" && hour >= 12 && hour < 22;
  const workRows = OFFICE_PEOPLE.map(person => officeAgentWork(snapshot, person.id, now, refreshFailed));
  const states = Object.fromEntries(workRows.map(row => [row.id, row.state]));
  const workCues: Record<string, OfficeWorkCue> = Object.fromEntries(workRows.map(row => [row.id, {
    state: row.state, stage: row.work[0]?.stage || "", title: row.work[0]?.title || "" }]));
  const activeRepair = snapshot.director?.active_repair || null;
  const leadIncident = (snapshot.incidents || []).find(row => row.state !== "needs_operator" && row.automatic) || null;
  const attentionSeat = repairSeat[activeRepair?.department || leadIncident?.department || ""] ?? null;
  const repairBrief = activeRepair ? activeRepair.summary
    : leadIncident ? `Kendala: ${leadIncident.title} · ${officeRepairAction[leadIncident.action] || "memeriksa"}` : "";
  const latest = useRef({ selected, bubbles, states, repairing: Boolean(repairBrief) });
  latest.current = { selected, bubbles, states, repairing: Boolean(repairBrief) };
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
        const talking = latest.current.bubbles && (Boolean(person.chatWith)
          || (person.id === "director" && latest.current.repairing)
          || focus === person.id || focus === "all" && (person.id === lead?.id || person.id === second?.id));
        label.dataset.bubble = String(talking);
        label.style.zIndex = focus === person.id ? "9" : talking ? "6" : "3";
        const half = element.clientWidth < 640 ? 57.5 : 76.5;
        const shift = Math.max(half + 10 - person.x, Math.min(0, element.clientWidth - half - 10 - person.x));
        label.style.setProperty("--speech-shift", `${shift}px`);
        label.dataset.activity = person.activity;
      }
      for (const room of rooms) {
        const label = areas.current.get(room.id);
        if (label) { label.style.left = `${room.x}px`; label.style.top = `${room.y}px`; }
      }
      const next = people.map(person => `${person.activity}:${person.chatWith || ""}`).join("|");
      if (signature.current !== next) {
        signature.current = next;
        setActivities(Object.fromEntries(people.map(person => [person.id, person.activity])));
        setChats(Object.fromEntries(people.map(person => [person.id, person.chatWith || ""])));
      }
    };
    void import("../../lib/createOfficeScene").then(({ createOfficeScene }) => {
      if (disposed) return;
      scene.current = createOfficeScene(element, project, value => setZoom(value)); setReady(true);
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
        scene.current?.render(elapsed.current, night, latest.current.states, workCues);
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [ready, animate, inView, night, zoom]);
  useEffect(() => { scene.current?.render(elapsed.current, night, latest.current.states, workCues); }, [selected, bubbles, night, snapshot]);
  useEffect(() => { if (follow && selected !== 'all') scene.current?.focusOn(selected); }, [follow, selected]);
  useEffect(() => { scene.current?.setAttention(attentionSeat); }, [ready, attentionSeat]);

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
          const chatWith = chats[person.id];
          const chatName = OFFICE_PEOPLE.find(row => row.id === chatWith)?.name || chatWith;
          // The answer is always the colleague's real queue status; no made-up work.
          const repairing = person.id === "director" && Boolean(repairBrief);
          const bubble = repairing ? repairBrief
            : chatWith
              ? person.id === "director" ? `Cek progres ${chatName}: apa yang sedang dikerjakan?` : `Menjawab pimpinan: ${speech.text}`
              : speech.text;
          return <button type="button" key={person.id} ref={element => { if (element) labels.current.set(person.id, element); else labels.current.delete(person.id); }}
            className={`officeWalker officePersonLabel${selected === person.id ? " is-selected" : ""}`} style={{ ["--person-color" as string]: person.color }}
            data-person={person.id} data-work-state={work.state} data-job-id={work.work[0]?.job_id || undefined} data-bubble="false" data-chat={chatWith || undefined} aria-pressed={selected === person.id}
            aria-label={`${person.name}, ${person.role}. ${activityLabel[activity]}. ${bubble}`}
            onClick={() => onSelect(selected === person.id ? "all" : person.id)}>
            <span className="officeSpeech"><span>{chatWith || repairing ? <MessageCircle size={10} /> : <Radio size={10} />}{repairing ? "Perbaikan" : chatWith ? "Obrolan" : officeWorkLabel[work.state]}</span><strong>{bubble}</strong></span>
            <span className="officePersonName"><i />{person.name}<small>{person.role}</small></span>
          </button>;
        })}</div> : null}
      <div className="officeSceneTools" aria-label="Kontrol tampilan kantor"><button type="button" aria-label="Putar sudut pandang ke kiri" onClick={() => scene.current?.rotate(-Math.PI / 8)}><RotateCcw size={14} /></button>
        <button type="button" aria-label="Putar sudut pandang ke kanan" onClick={() => scene.current?.rotate(Math.PI / 8)}><RotateCw size={14} /></button>
        <button type="button" aria-label="Kembalikan sudut pandang dan pembesaran" onClick={() => { scene.current?.resetView(); setZoom(1); }}><RotateCcw size={13} /></button>
        <span />
        <button type="button" aria-label="Lihat dari atas" onClick={() => scene.current?.tilt(.18)}><ArrowUp size={14} /></button>
        <button type="button" aria-label="Lihat dari samping" onClick={() => scene.current?.tilt(-.18)}><ArrowDown size={14} /></button>
        <span />
        <button type="button" aria-label="Perkecil kantor" disabled={zoom <= .6} onClick={() => setZoom(value => Math.max(.6, value - .2))}><Minus size={15} /></button>
        <button type="button" aria-label="Perbesar kantor" disabled={zoom >= 2.6} onClick={() => setZoom(value => Math.min(2.6, value + .2))}><Plus size={15} /></button>
        <span /><button type="button" aria-pressed={follow} aria-label="Ikuti agen yang dipilih" onClick={() => setFollow(value => !value)}><Crosshair size={15} /></button>
        <button type="button" aria-pressed={bubbles} aria-label="Tampilkan bubble percakapan" onClick={() => setBubbles(value => !value)}><MessageCircle size={15} /></button>
        <button type="button" aria-label={lighting === "auto" ? "Pencahayaan otomatis, ubah ke siang" : lighting === "day" ? "Pencahayaan siang, ubah ke malam" : "Pencahayaan malam, ubah ke otomatis"} onClick={() => setLighting(value => value === "auto" ? "day" : value === "day" ? "night" : "auto")}>{night ? <Moon size={15} /> : <Sun size={15} />}</button></div>
    </div>
    <div className="officeDioramaFooter"><span><Radio size={13} />{status.fresh ? "Aktivitas mengikuti antrean sistem" : "Menunggu pembaruan aktivitas"}</span></div>
    {chosen && department ? <div className="officePersonDetail"><span style={{ background: chosen.color }}>{chosen.name.charAt(0)}</span><div><strong>{chosen.name} <small>{department.name}</small></strong><p>{chosenWork.work[0] ? `${chosenWork.work[0].stage} · ${chosenWork.work[0].title}` : chosenWork.detail}</p></div><span>{officeWorkLabel[chosenWork.state]}</span></div> : null}
  </div>;
}
