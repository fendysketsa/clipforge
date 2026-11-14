"use client";

import { Activity, ArrowUpRight, Clock3, Film, FolderArchive, Loader2, Plus, Power, RefreshCw, Settings2, Sparkles } from "lucide-react";
import type { AutoViralScheduleStatus } from "../../types/clip.type";
import type { StudioView } from "../../lib/workspaceNavigation";

type TopbarProps = {
  isRefreshing?: boolean; onRefresh?: () => void;
  activePage?: "workspace" | "source-log"; activeView?: StudioView;
  cronSchedule?: AutoViralScheduleStatus | null;
  isTogglingCron?: boolean; onToggleCron?: () => void;
};

const navigation = [
  { key: "create", href: "/#quick-start-title", label: "Buat video", icon: Plus },
  { key: "results", href: "/#results", label: "Hasil video", icon: Film },
  { key: "history", href: "/#history", label: "Riwayat", icon: Clock3 },
  { key: "automation", href: "/#automation", label: "Otomasi", icon: Activity },
  { key: "settings", href: "/#settings", label: "Koneksi", icon: Settings2 },
  { key: "source-log", href: "/source-history", label: "Arsip sumber", icon: FolderArchive },
];

export function Topbar({ isRefreshing = false, onRefresh, activePage = "workspace", activeView = "create",
  cronSchedule, isTogglingCron = false, onToggleCron }: TopbarProps) {
  const selected = activePage === "source-log" ? "source-log" : activeView;
  return <>
    <header className="studioTopbar">
      <a href="/#quick-start-title" className="studioBrand" aria-label="ClipForge Studio — buat video">
        <span className="studioBrandMark"><Sparkles size={21} strokeWidth={1.7} /></span>
        <span>ClipForge<small>STUDIO</small></span>
      </a>
      <span className="studioTopbarContext">Ruang produksi <span>/</span> {navigation.find(item => item.key === selected)?.label}</span>
      <div className="studioTopbarActions">
        {onToggleCron ? <button type="button" className={`studioCronToggle${cronSchedule?.enabled ? " isOn" : ""}`}
          onClick={onToggleCron} disabled={isTogglingCron || !cronSchedule}
          aria-pressed={Boolean(cronSchedule?.enabled)} title={cronSchedule?.message || "Membaca status cron"}>
          {isTogglingCron ? <Loader2 size={14} className="spin" /> : <Power size={14} />}
          <span>{!cronSchedule ? "Memuat cron" : `Cron ${cronSchedule.enabled ? "aktif" : "nonaktif"}`}</span>
        </button> : null}
        {onRefresh ? <button className="studioSync" type="button" onClick={onRefresh} disabled={isRefreshing}
          aria-label="Sinkronkan data terbaru" title="Sinkronkan data terbaru">
          <RefreshCw size={16} className={isRefreshing ? "spin" : undefined} /><span>Sinkronkan</span>
        </button> : null}
      </div>
    </header>
    <aside className="studioSidebar">
      <p className="studioNavCaption">WORKSPACE</p>
      <nav aria-label="Navigasi studio">
        {navigation.map(({ key, href, label, icon: Icon }) => <a key={key} href={href}
          className={selected === key ? "isActive" : ""} aria-current={selected === key ? "page" : undefined}>
          <Icon size={18} strokeWidth={1.7} /><span>{label}</span>{selected === key ? <i /> : null}
        </a>)}
      </nav>
      <div className="studioSidebarFooter">
        <span className="studioWorkspaceAvatar">CF</span><div><strong>Workspace lokal</strong><span>Video & otomasi</span></div>
        <a href="https://studio.youtube.com" target="_blank" rel="noreferrer" aria-label="Buka YouTube Studio" title="YouTube Studio"><ArrowUpRight size={16} /></a>
      </div>
    </aside>
  </>;
}
