import { Clock3, Film, ListChecks, Loader2, Power, RefreshCw, Sparkles } from "lucide-react";
import Link from "next/link";
import type { AutoViralScheduleStatus } from "../../types/clip.type";

type TopbarProps = {
  isRefreshing?: boolean;
  onRefresh?: () => void;
  activePage?: "workspace" | "source-log";
  cronSchedule?: AutoViralScheduleStatus | null;
  isTogglingCron?: boolean;
  onToggleCron?: () => void;
};

export function Topbar({
  isRefreshing = false,
  onRefresh,
  activePage = "workspace",
  cronSchedule,
  isTogglingCron = false,
  onToggleCron,
}: TopbarProps) {
  return (
    <header className="topbar">
      <div className="topbar-brand">
        <span className="brandMark" aria-hidden="true">
          <Sparkles size={20} />
        </span>
        <div className="brandCopy">
          <h1 className="logo-text" aria-label="ClipForge Studio">
            <span>ClipForge</span>
            <span>Studio</span>
          </h1>
          <p className="tagline">Trend → original video → growth</p>
        </div>
      </div>

      <nav className="topbarNav" aria-label="Navigasi halaman">
        <Link className={activePage === "workspace" ? "active" : ""} href="/#quick-start-title">
          <Sparkles size={15} />
          Buat video
        </Link>
        <Link href="/#results">
          <Film size={15} />
          Hasil
        </Link>
        <Link href="/#history">
          <Clock3 size={15} />
          Riwayat
        </Link>
        <Link className={activePage === "source-log" ? "active" : ""} href="/source-history">
          <ListChecks size={15} />
          Log sumber
        </Link>
      </nav>

      <div className="topbarActions">
        <span className="systemBadge">
          <i aria-hidden="true" />
          Studio siap
        </span>
        {onToggleCron ? (
          <button
            className={`cronToggleButton ${cronSchedule?.enabled ? "isEnabled" : ""}`}
            type="button"
            onClick={onToggleCron}
            disabled={isTogglingCron || !cronSchedule}
            aria-pressed={Boolean(cronSchedule?.enabled)}
            title={cronSchedule?.message ?? "Membaca status cron"}
          >
            {isTogglingCron ? <Loader2 className="spin" size={15} /> : <Power size={15} />}
            <span>Cron {cronSchedule?.enabled ? "ON" : "OFF"}</span>
            <i aria-hidden="true" />
          </button>
        ) : null}
        {onRefresh ? (
          <button
            className="syncDataButton"
            type="button"
            onClick={onRefresh}
            disabled={isRefreshing}
            title="Sinkronkan ulang data terbaru dari backend. Ini bukan refresh browser."
          >
            <RefreshCw className={isRefreshing ? "spin" : ""} size={16} />
            <span>{isRefreshing ? "Sinkron..." : "Sinkronkan"}</span>
          </button>
        ) : null}
      </div>
    </header>
  );
}
