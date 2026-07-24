import { Clock3, Film, RefreshCw, Scissors } from "lucide-react";

type TopbarProps = {
  isRefreshing?: boolean;
  onRefresh: () => void;
};

export function Topbar({ isRefreshing = false, onRefresh }: TopbarProps) {
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
          <p className="tagline">Video panjang, jadi konten singkat.</p>
        </div>
      </div>

      <nav className="topbarNav" aria-label="Navigasi halaman">
        <a href="#workspace">
          <Scissors size={15} />
          Buat klip
        </a>
        <a href="#results">
          <Film size={15} />
          Hasil
        </a>
        <a href="#history">
          <Clock3 size={15} />
          Riwayat
        </a>
      </nav>

      <div className="topbarActions">
        <span className="systemBadge">
          <i aria-hidden="true" />
          Local workspace
        </span>
        <button
          className="syncDataButton"
          type="button"
          onClick={onRefresh}
          disabled={isRefreshing}
          title="Sinkronkan ulang status job, riwayat proses, dan daftar klip dari backend. Ini bukan refresh browser."
        >
          <RefreshCw className={isRefreshing ? "spin" : ""} size={16} />
          <span>{isRefreshing ? "Sinkron..." : "Sinkronkan"}</span>
        </button>
      </div>
    </header>
  );
}
