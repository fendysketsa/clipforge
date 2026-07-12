import { RefreshCw } from "lucide-react";

type TopbarProps = {
  isRefreshing?: boolean;
  onRefresh: () => void;
};

export function Topbar({ isRefreshing = false, onRefresh }: TopbarProps) {
  return (
    <section className="topbar">
      <div className="topbar-brand">
        <div className="brandCopy">
          <h1 className="logo-text" aria-label="Fendy Clipper">
            <span>FENDY</span>
            <span>CLIPPER</span>
          </h1>
          <p className="tagline">Turn long videos into ready-to-post clips.</p>
        </div>
      </div>
      <button
        className="syncDataButton"
        type="button"
        onClick={onRefresh}
        disabled={isRefreshing}
        title="Sinkronkan ulang status job, riwayat proses, dan daftar klip dari backend. Ini bukan refresh browser."
      >
        <RefreshCw className={isRefreshing ? "spin" : ""} size={16} />
        <span>{isRefreshing ? "Menyinkronkan..." : "Sinkronkan Data"}</span>
      </button>
    </section>
  );
}
