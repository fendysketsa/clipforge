import { Clock3, Film, ListChecks, RefreshCw, Scissors } from "lucide-react";
import Link from "next/link";

type TopbarProps = {
  isRefreshing?: boolean;
  onRefresh?: () => void;
  activePage?: "workspace" | "source-log";
};

export function Topbar({ isRefreshing = false, onRefresh, activePage = "workspace" }: TopbarProps) {
  return (
    <header className="topbar">
      <div className="topbar-brand">
        <span className="brandMark" aria-hidden="true">
          <Scissors size={20} />
        </span>
        <div className="brandCopy">
          <h1 className="logo-text" aria-label="Fendy Clipper">
            <span>Fendy</span>
            <span>Clipper</span>
          </h1>
          <p className="tagline">Tempel link. Pilih format. Siap review.</p>
        </div>
      </div>

      <nav className="topbarNav" aria-label="Navigasi halaman">
        <Link className={activePage === "workspace" ? "active" : ""} href="/#workspace">
          <Scissors size={15} />
          Buat klip
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
          Local workspace
        </span>
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
