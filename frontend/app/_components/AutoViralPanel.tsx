import { CheckCircle2, Clock3, ExternalLink, Loader2, Radar, Search, ShieldCheck } from "lucide-react";
import type {
  AutoViralRun,
  AutoViralScheduleStatus,
  IslamicContentNiche,
  ViralContentSource,
  ViralSearchFilters,
} from "../../types/clip.type";

type Props = {
  niche: IslamicContentNiche;
  filters: ViralSearchFilters;
  sources: ViralContentSource[];
  selectedUrls: string[];
  message: string;
  run: AutoViralRun | null;
  schedule: AutoViralScheduleStatus | null;
  isSearching: boolean;
  isRunning: boolean;
  onNicheChange: (value: IslamicContentNiche) => void;
  onFiltersChange: (value: ViralSearchFilters) => void;
  onSearch: () => void;
  onToggleSource: (url: string) => void;
  onStart: () => void;
};

const NICHES: { value: IslamicContentNiche; label: string }[] = [
  { value: "islamic_current_viral", label: "Isu Muslim terkini" },
  { value: "islamic_practical_life", label: "Masalah hidup praktis" },
  { value: "islamic_mental_health", label: "Mental health Islami" },
  { value: "halal_wealth", label: "Rezeki & bisnis halal" },
  { value: "fiqih_harian", label: "Fiqih harian" },
  { value: "islamic_history", label: "Sejarah Islam" },
  { value: "auto", label: "Campuran otomatis" },
];

const formatNumber = (value: number) => new Intl.NumberFormat("id-ID", { notation: "compact" }).format(value);
const formatDate = (value?: string | null) => value
  ? new Intl.DateTimeFormat("id-ID", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Jakarta" }).format(new Date(value))
  : "-";

export function AutoViralPanel({
  niche,
  filters,
  sources,
  selectedUrls,
  message,
  run,
  schedule,
  isSearching,
  isRunning,
  onNicheChange,
  onFiltersChange,
  onSearch,
  onToggleSource,
  onStart,
}: Props) {
  const completed = run?.processed.filter((item) => item.status === "completed").length ?? 0;
  const progress = Math.max(0, Math.min(100, run?.progress_percent ?? 0));

  return (
    <section className="panel autoViralPanel">
      <div className="panelHeader">
        <div className="panelHeaderTitle">
          <span className="panelHeaderIcon"><Radar size={18} /></span>
          <div className="panelTitleCopy">
            <span className="panelEyebrow">YouTube trend intelligence</span>
            <h2>Radar Viral Otomatis</h2>
          </div>
        </div>
        <span className={`autoScheduleBadge ${schedule?.enabled ? "enabled" : ""}`}>
          <Clock3 size={12} />
          {schedule?.enabled ? `Tiap ${schedule.interval_hours} jam` : "Cron nonaktif"}
        </span>
      </div>

      <div className="autoScheduleSummary">
        <span>{schedule?.message ?? "Membaca konfigurasi scheduler..."}</span>
        <small>
          Berikutnya: {formatDate(schedule?.next_run_at)} · Terakhir: {formatDate(schedule?.last_started_at)}
        </small>
      </div>

      <div className="viralSearchFilterPanel">
        <label className="viralFilterItem">
          <span>Tema</span>
          <select value={niche} onChange={(event) => onNicheChange(event.target.value as IslamicContentNiche)}>
            {NICHES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
        <label className="viralFilterItem">
          <span>Periode upload</span>
          <select value={filters.upload_date_filter} onChange={(event) => onFiltersChange({ ...filters, upload_date_filter: event.target.value as ViralSearchFilters["upload_date_filter"] })}>
            <option value="today">Hari ini</option>
            <option value="this_week">7 hari</option>
            <option value="this_month">30 hari</option>
            <option value="this_year">Tahun ini</option>
          </select>
        </label>
        <label className="viralFilterItem">
          <span>Durasi sumber</span>
          <select value={filters.duration_filter} onChange={(event) => onFiltersChange({ ...filters, duration_filter: event.target.value as ViralSearchFilters["duration_filter"] })}>
            <option value="any">Semua durasi</option>
            <option value="under_3">Di bawah 3 menit</option>
            <option value="between_3_20">3–20 menit</option>
            <option value="over_20">Di atas 20 menit</option>
          </select>
        </label>
        <label className="viralFilterItem">
          <span>Urutan</span>
          <select value={filters.sort_order} onChange={(event) => onFiltersChange({ ...filters, sort_order: event.target.value as ViralSearchFilters["sort_order"] })}>
            <option value="popularity">Momentum & views</option>
            <option value="relevance">Relevansi</option>
            <option value="newest">Paling baru</option>
          </select>
        </label>
        <div className="viralFilterItem viralFilterLocked">
          <span>Kualitas & lisensi</span>
          <strong><ShieldCheck size={14} /> HD + Creative Commons</strong>
          <small>Tetap melewati guard hak audio/visual.</small>
        </div>
      </div>

      <button className="uiButton uiButton--secondary autoViralButton" type="button" disabled={isSearching || isRunning} onClick={onSearch}>
        {isSearching ? <Loader2 className="spin" size={16} /> : <Search size={16} />}
        {isSearching ? "Membaca chart & statistik..." : "Cari Kandidat dari Tren YouTube"}
      </button>

      {message ? <p className="viralFilterPolicy">{message}</p> : null}

      {sources.length ? (
        <div className="autoContentResults">
          {sources.map((source) => {
            const selected = selectedUrls.includes(source.url);
            return (
              <article className={`autoContentCard ${selected ? "selected" : ""}`} key={source.url}>
                <label className="autoContentSelect">
                  <input type="checkbox" checked={selected} onChange={() => onToggleSource(source.url)} />
                  <span className="autoContentRank">#{source.rank}</span>
                  <span className="autoContentTitle">{source.title}</span>
                </label>
                <div className="autoContentMeta">
                  <span>{formatNumber(source.views)} views</span>
                  <span>{formatNumber(source.views_per_day)}/hari</span>
                  <span>Skor {Math.round(source.score)}</span>
                  <span>Trend +{source.trend_signal_score ?? 0}</span>
                  <span>{source.search_provider === "youtube_data_api" ? "YouTube API" : "Fallback"}</span>
                </div>
                <div className="autoContentReason">
                  <span>{source.ranking_reason}</span>
                  <a href={source.url} target="_blank" rel="noreferrer" aria-label="Buka sumber"><ExternalLink size={14} /></a>
                </div>
              </article>
            );
          })}
          <button className="uiButton primary autoQueueButton" type="button" disabled={!selectedUrls.length || isRunning} onClick={onStart}>
            <CheckCircle2 size={17} /> Olah {selectedUrls.length} sumber terpilih
          </button>
        </div>
      ) : null}

      {run ? (
        <div className="autoRunMonitor">
          <div className="autoRunHeading">
            <div>
              <strong>{run.trigger === "schedule" ? "Run cron" : "Run manual"} · {run.status}</strong>
              <span>{run.progress_stage.replaceAll("_", " ")} · {completed}/{run.progress_total || run.request.video_count} sumber selesai</span>
            </div>
            <b>{progress}%</b>
          </div>
          <div className="autoViralProgress" aria-label={`Progress automation ${progress}%`}><span style={{ width: `${progress}%` }} /></div>
          <p>{run.message}</p>
          <div className="autoRunLogs">
            {run.logs.slice(-8).map((line, index) => <code key={`${line}-${index}`}>{line}</code>)}
          </div>
        </div>
      ) : null}
    </section>
  );
}
