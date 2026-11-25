"use client";

import { useEffect, useRef, useState } from "react";
import { Activity, ArrowUpRight, ChevronRight, Clock3, Facebook, Film, FolderArchive, LayoutDashboard, Loader2, Menu, Plus, Power, RefreshCw, Scissors, Settings2, X } from "lucide-react";
import type { AutoViralScheduleStatus } from "../../types/clip.type";
import type { StudioView } from "../../lib/workspaceNavigation";
import { ThemeSwitch } from "./ThemeSwitch";

type TopbarProps = {
  isRefreshing?: boolean; onRefresh?: () => void;
  activePage?: "workspace" | "source-log"; activeView?: StudioView;
  cronSchedule?: AutoViralScheduleStatus | null;
  isTogglingCron?: boolean; onToggleCron?: () => void;
};

const navigation = [
  { key: "overview", href: "/#overview", label: "Ringkasan", icon: LayoutDashboard, group: "Workspace" },
  { key: "create", href: "/#quick-start-title", label: "Buat video", icon: Plus, group: "Workspace" },
  { key: "results", href: "/#results", label: "Hasil video", icon: Film, group: "Workspace" },
  { key: "history", href: "/#history", label: "Riwayat produksi", icon: Clock3, group: "Workspace" },
  { key: "automation", href: "/#automation", label: "Kantor AI", icon: Activity, group: "Kelola" },
  { key: "facebook", href: "/#facebook", label: "Facebook Studio", icon: Facebook, group: "Kelola" },
  { key: "source-log", href: "/source-history", label: "Arsip sumber", icon: FolderArchive, group: "Kelola" },
  { key: "settings", href: "/#settings", label: "Koneksi platform", icon: Settings2, group: "Kelola" },
];

export function Topbar({ isRefreshing = false, onRefresh, activePage = "workspace", activeView = "overview",
  cronSchedule, isTogglingCron = false, onToggleCron }: TopbarProps) {
  const selected = activePage === "source-log" ? "source-log" : activeView;
  const [menuOpen, setMenuOpen] = useState(false);
  const [now, setNow] = useState(Date.now);
  const menuButton = useRef<HTMLButtonElement>(null);
  const sidebar = useRef<HTMLElement>(null);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => window.clearInterval(timer);
  }, []);
  const clockText = new Intl.DateTimeFormat("id-ID", { timeZone: "Asia/Jakarta",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(new Date(now));
  useEffect(() => {
    if (!menuOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    sidebar.current?.querySelector<HTMLAnchorElement>('[aria-current="page"]')?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
      if (event.key !== "Tab") return;
      const controls = Array.from(sidebar.current?.querySelectorAll<HTMLElement>('a,button') ?? []);
      const first = controls[0], last = controls.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    const close = () => setMenuOpen(false);
    const resize = () => { if (window.innerWidth > 760) close(); };
    window.addEventListener("keydown", keydown);
    window.addEventListener("hashchange", close);
    window.addEventListener("resize", resize);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", keydown);
      window.removeEventListener("hashchange", close);
      window.removeEventListener("resize", resize);
      menuButton.current?.focus();
    };
  }, [menuOpen]);
  return <>
    <a className="studioSkipLink" href="#workspace-content" onClick={event => { event.preventDefault(); document.getElementById("workspace-content")?.focus(); }}>Lewati ke konten</a>
    <header className="studioTopbar">
      <button ref={menuButton} type="button" className="studioMenuButton" aria-label="Buka navigasi" aria-expanded={menuOpen} aria-controls="studio-navigation" onClick={() => setMenuOpen(true)}><Menu size={21} /></button>
      <a href="/#overview" className="studioBrand" aria-label="ClipForge Studio — ringkasan">
        <span className="studioBrandMark"><Scissors size={21} strokeWidth={2} /></span>
        <span>ClipForge<small>STUDIO</small></span>
      </a>
      <span className="studioTopbarContext">Workspace <ChevronRight size={13} /> <strong>{navigation.find(item => item.key === selected)?.label}</strong></span>
      <span className="studioTopbarClock" suppressHydrationWarning aria-label={`Waktu Jakarta ${clockText}`}><i />{clockText}<small>WIB</small></span>
      <div className="studioTopbarActions">
        {onToggleCron ? <button type="button" className={`studioCronToggle${cronSchedule?.enabled ? " isOn" : ""}`}
          onClick={onToggleCron} disabled={isTogglingCron || !cronSchedule}
          aria-pressed={Boolean(cronSchedule?.enabled)} title={cronSchedule?.message || "Membaca status cron"}>
          {isTogglingCron ? <Loader2 size={14} className="spin" /> : <Power size={14} />}
          <span>{!cronSchedule ? "Memuat cron" : `Cron ${cronSchedule.enabled ? "aktif" : "dijeda"}`}</span>
        </button> : null}
        {onRefresh ? <button className="studioSync" type="button" onClick={onRefresh} disabled={isRefreshing}
          aria-label="Sinkronkan data terbaru" title="Sinkronkan data terbaru">
          <RefreshCw size={16} className={isRefreshing ? "spin" : undefined} /><span>Sinkronkan</span>
        </button> : null}
        <ThemeSwitch />
      </div>
    </header>
    {menuOpen ? <button type="button" className="studioNavBackdrop" tabIndex={-1} aria-label="Tutup navigasi" onClick={() => setMenuOpen(false)} /> : null}
    <aside ref={sidebar} id="studio-navigation" className={`studioSidebar${menuOpen ? " isOpen" : ""}`} role={menuOpen ? "dialog" : undefined} aria-modal={menuOpen || undefined} aria-label="Menu studio">
      <div className="studioMobileNavHeading"><strong>Workspace Anda</strong><button type="button" aria-label="Tutup navigasi" onClick={() => setMenuOpen(false)}><X size={20} /></button></div>
      <nav aria-label="Navigasi studio">
        {["Workspace", "Kelola"].map(group => <div className="studioNavGroup" key={group}>
          <p className="studioNavCaption">{group}</p>
          {navigation.filter(item => item.group === group).map(({ key, href, label, icon: Icon }) => <a key={key} href={href}
            onClick={() => setMenuOpen(false)} className={selected === key ? "isActive" : ""} aria-current={selected === key ? "page" : undefined}>
            <Icon size={18} strokeWidth={1.8} /><span>{label}</span>{selected === key ? <ChevronRight size={14} /> : null}
          </a>)}
        </div>)}
      </nav>
      <div className="studioSidebarFooter">
        <span className="studioWorkspaceAvatar">CF</span><div><strong>ClipForge Studio</strong><span>Ruang kerja video Anda</span></div>
        <a href="https://studio.youtube.com" target="_blank" rel="noreferrer" aria-label="Buka YouTube Studio" title="YouTube Studio"><ArrowUpRight size={17} /></a>
      </div>
    </aside>
  </>;
}
