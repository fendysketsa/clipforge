"use client";

import {
  Archive,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Copy,
  ExternalLink,
  FileVideo2,
  Film,
  Folder,
  FolderOpen,
  HardDrive,
  Layers3,
  ListFilter,
  Loader2,
  Search,
  Sparkles,
  Youtube,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { getSourceUsageLog } from "../../lib/apiClient";
import type { SourceUsageFolder, SourceUsageLogEntry, SourceUsageLogResponse } from "../../types/clip.type";
import { Topbar } from "../_components/Topbar";

type ModeFilter = "all" | "short" | "highlight_5m";

const MONTH_FORMATTER = new Intl.DateTimeFormat("id-ID", { month: "long" });

const monthName = (month: number) => MONTH_FORMATTER.format(new Date(Date.UTC(2024, month - 1, 1)));

const archiveParts = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return { year: 0, month: 0, key: "unknown" };
  const parts = new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    timeZone: "Asia/Jakarta",
  }).formatToParts(date);
  const year = Number(parts.find((part) => part.type === "year")?.value || 0);
  const month = Number(parts.find((part) => part.type === "month")?.value || 0);
  return { year, month, key: `${year}-${String(month).padStart(2, "0")}` };
};

const formatDateTime = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("id-ID", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Jakarta",
  }).format(date);
};

const formatDuration = (seconds?: number | null) => {
  if (seconds === null || seconds === undefined) return "—";
  const rounded = Math.max(0, Math.round(seconds));
  const hours = Math.floor(rounded / 3600);
  const minutes = Math.floor((rounded % 3600) / 60);
  const remainder = rounded % 60;
  if (hours) return `${hours}j ${minutes}m`;
  return minutes ? `${minutes}m ${remainder}d` : `${remainder}d`;
};

const sourceVideoId = (url: string) => {
  try {
    const parsed = new URL(url);
    if (parsed.hostname.includes("youtu.be")) return parsed.pathname.split("/").filter(Boolean)[0] || "—";
    return parsed.searchParams.get("v")
      || parsed.pathname.match(/\/(?:shorts|live|embed)\/([^/?#]+)/)?.[1]
      || "—";
  } catch {
    return "—";
  }
};

const copyText = async (value: string, label: string) => {
  try {
    await navigator.clipboard.writeText(value);
    toast.success(`${label} disalin`);
  } catch {
    toast.error(`Gagal menyalin ${label.toLowerCase()}`);
  }
};

export default function SourceHistoryPage() {
  const [data, setData] = useState<SourceUsageLogResponse>({ items: [], folders: [], total: 0, unique_sources: 0 });
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<ModeFilter>("all");
  const [archiveFilter, setArchiveFilter] = useState("all");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  const loadLog = useCallback(async (notify = false) => {
    setIsLoading(true);
    setError("");
    try {
      const next = await getSourceUsageLog();
      setData({ ...next, folders: next.folders ?? [] });
      if (notify) toast.success("Arsip sumber berhasil disinkronkan");
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : "Gagal memuat arsip sumber";
      setError(message);
      if (notify) toast.error(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadLog().catch(() => undefined);
  }, [loadLog]);

  const activeItems = useMemo(
    () => data.items.filter((item) => item.clip_mode === "short" || item.clip_mode === "highlight_5m"),
    [data.items],
  );

  const counts = useMemo(() => ({
    short: activeItems.filter((item) => item.clip_mode === "short").length,
    long: activeItems.filter((item) => item.clip_mode === "highlight_5m").length,
    outputs: activeItems.reduce((total, item) => total + item.clip_count, 0),
  }), [activeItems]);

  const folders = useMemo<SourceUsageFolder[]>(() => {
    if (data.folders.length) return data.folders;
    const grouped = new Map<string, SourceUsageLogEntry[]>();
    activeItems.forEach((item) => {
      const key = archiveParts(item.processed_at).key;
      grouped.set(key, [...(grouped.get(key) ?? []), item]);
    });
    return [...grouped.entries()].map(([key, items]) => {
      const { year, month } = archiveParts(items[0]?.processed_at || "");
      return {
        key,
        year,
        month,
        total: items.length,
        unique_sources: new Set(items.map((item) => item.source_url)).size,
        short_count: items.filter((item) => item.clip_mode === "short").length,
        long_count: items.filter((item) => item.clip_mode === "highlight_5m").length,
      };
    }).sort((a, b) => b.key.localeCompare(a.key));
  }, [activeItems, data.folders]);

  const folderYears = useMemo(() => {
    const grouped = new Map<number, SourceUsageFolder[]>();
    folders.forEach((folder) => grouped.set(folder.year, [...(grouped.get(folder.year) ?? []), folder]));
    return [...grouped.entries()].sort(([a], [b]) => b - a);
  }, [folders]);

  const filteredItems = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("id-ID");
    return activeItems.filter((item) => {
      const partition = archiveParts(item.processed_at);
      if (mode !== "all" && item.clip_mode !== mode) return false;
      if (archiveFilter !== "all") {
        const matchesArchive = archiveFilter.includes("-")
          ? partition.key === archiveFilter
          : partition.year === Number(archiveFilter);
        if (!matchesArchive) return false;
      }
      if (!needle) return true;
      return [
        item.source_title,
        item.source_uploader,
        item.source_url,
        item.job_id,
        sourceVideoId(item.source_url),
        ...item.output_names,
      ].some((value) => String(value || "").toLocaleLowerCase("id-ID").includes(needle));
    });
  }, [activeItems, archiveFilter, mode, query]);

  const groupedResults = useMemo(() => {
    const years = new Map<number, Map<number, SourceUsageLogEntry[]>>();
    filteredItems.forEach((item) => {
      const { year, month } = archiveParts(item.processed_at);
      const months = years.get(year) ?? new Map<number, SourceUsageLogEntry[]>();
      months.set(month, [...(months.get(month) ?? []), item]);
      years.set(year, months);
    });
    return [...years.entries()]
      .sort(([a], [b]) => b - a)
      .map(([year, months]) => ({
        year,
        months: [...months.entries()].sort(([a], [b]) => b - a),
      }));
  }, [filteredItems]);

  const currentFolderLabel = archiveFilter === "all"
    ? "Semua arsip"
    : archiveFilter.includes("-")
      ? `${monthName(Number(archiveFilter.split("-")[1]))} ${archiveFilter.split("-")[0]}`
      : `Tahun ${archiveFilter}`;

  return (
    <main className="shell sourceLogPage sourceArchivePage">
      <Topbar activePage="source-log" isRefreshing={isLoading} onRefresh={() => loadLog(true)} />

      <section className="sourceArchiveHero">
        <div className="sourceArchiveHeroCopy">
          <span className="sourceLogEyebrow"><Archive size={15} /> Arsip sumber</span>
          <h2>Jejak sumber, tersusun rapi.</h2>
          <p>Setiap proses sukses otomatis masuk folder tahun dan bulan. Temukan sumber lama tanpa menyisir seluruh riwayat.</p>
        </div>
        <div className="archivePathPreview" aria-label="Lokasi folder penyimpanan">
          <HardDrive size={18} />
          <span><small>Struktur penyimpanan</small><code>source_usage / tahun / bulan</code></span>
          <CheckCircle2 size={17} />
        </div>
      </section>

      <section className="sourceArchiveStats" aria-label="Ringkasan arsip sumber">
        <article><span><Layers3 size={17} /> Proses sukses</span><strong>{activeItems.length}</strong><small>Short + Long Story</small></article>
        <article><span><Youtube size={17} /> Sumber unik</span><strong>{data.unique_sources}</strong><small>Deteksi duplikat aktif</small></article>
        <article><span><FileVideo2 size={17} /> File dihasilkan</span><strong>{counts.outputs}</strong><small>Siap ditinjau</small></article>
        <article><span><CalendarDays size={17} /> Folder bulan</span><strong>{folders.length}</strong><small>{folderYears.length} tahun arsip</small></article>
      </section>

      <section className="sourceArchiveShell">
        <aside className="archiveSidebar" aria-label="Folder arsip">
          <div className="archiveSidebarTitle"><FolderOpen size={17} /><span><strong>Folder sumber</strong><small>{folders.length} periode</small></span></div>
          <button className={archiveFilter === "all" ? "active" : ""} type="button" onClick={() => setArchiveFilter("all")}>
            <Archive size={15} /><span>Semua arsip</span><b>{activeItems.length}</b>
          </button>
          <div className="archiveTree">
            {folderYears.map(([year, months]) => (
              <div className="archiveYearNode" key={year}>
                <button className={archiveFilter === String(year) ? "active" : ""} type="button" onClick={() => setArchiveFilter(String(year))}>
                  <Folder size={15} /><span>{year}</span><b>{months.reduce((sum, folder) => sum + folder.total, 0)}</b>
                </button>
                <div>
                  {months.map((folder) => (
                    <button className={archiveFilter === folder.key ? "active" : ""} key={folder.key} type="button" onClick={() => setArchiveFilter(folder.key)}>
                      <span>{monthName(folder.month)}</span><b>{folder.total}</b>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </aside>

        <div className="archiveContent">
          <div className="sourceArchiveToolbar">
            <div className="archiveCurrentFolder"><FolderOpen size={18} /><span><small>Lokasi aktif</small><strong>{currentFolderLabel}</strong></span></div>
            <label className="sourceLogSearch">
              <Search size={16} />
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cari judul, channel, ID video, job, atau output…" />
              {query ? <button type="button" onClick={() => setQuery("")}>Hapus</button> : null}
            </label>
            <div className="sourceLogFilters" role="group" aria-label="Filter format hasil">
              <button className={mode === "all" ? "active" : ""} type="button" onClick={() => setMode("all")}><ListFilter size={13} /> Semua</button>
              <button className={mode === "short" ? "active" : ""} type="button" onClick={() => setMode("short")}><Sparkles size={13} /> Short <span>{counts.short}</span></button>
              <button className={mode === "highlight_5m" ? "active" : ""} type="button" onClick={() => setMode("highlight_5m")}><Film size={13} /> Long <span>{counts.long}</span></button>
            </div>
          </div>

          {error ? <div className="sourceLogError">{error}</div> : null}
          {isLoading && !activeItems.length ? (
            <div className="sourceLogEmpty"><Loader2 className="spin" size={28} /><strong>Membuka arsip sumber…</strong></div>
          ) : groupedResults.length ? (
            <div className="archiveResults">
              {groupedResults.map(({ year, months }) => (
                <section className="archiveYearGroup" key={year}>
                  <header><FolderOpen size={18} /><h3>{year}</h3><span>{months.reduce((sum, [, items]) => sum + items.length, 0)} proses</span></header>
                  {months.map(([month, items]) => (
                    <section className="archiveMonthGroup" key={`${year}-${month}`}>
                      <div className="archiveMonthHeader">
                        <span className="archiveFolderTab"><Folder size={16} /></span>
                        <div><h4>{monthName(month)}</h4><span>{items.length} proses · {new Set(items.map((item) => item.source_url)).size} sumber unik</span></div>
                        <code>{year}/{String(month).padStart(2, "0")}</code>
                      </div>
                      <div className="sourceArchiveList">
                        {items.map((item) => <SourceLogCard item={item} key={`${item.job_id}-${item.clip_mode}`} />)}
                      </div>
                    </section>
                  ))}
                </section>
              ))}
            </div>
          ) : (
            <div className="sourceLogEmpty">
              <FolderOpen size={30} />
              <strong>{activeItems.length ? "Folder ini tidak memiliki hasil yang cocok" : "Arsip masih kosong"}</strong>
              <span>{activeItems.length ? "Ubah folder, pencarian, atau filter format." : "Folder pertama dibuat otomatis setelah proses berhasil."}</span>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

function SourceLogCard({ item }: { item: SourceUsageLogEntry }) {
  const isLong = item.clip_mode === "highlight_5m";
  const videoId = sourceVideoId(item.source_url);
  return (
    <article className="sourceArchiveCard">
      <span className={`archiveModeMark ${isLong ? "isLong" : "isShort"}`}>{isLong ? <Film size={17} /> : <Sparkles size={17} />}</span>
      <div className="sourceArchiveCardBody">
        <div className="sourceArchiveCardTitle">
          <div>
            <span className="sourceLogDate"><Clock3 size={12} /> {formatDateTime(item.processed_at)} WIB</span>
            <h3>{item.source_title || `Video YouTube ${videoId}`}</h3>
            <p>{item.source_uploader || "Channel tidak tercatat"}</p>
          </div>
          <span className={`sourceLogModeBadge ${isLong ? "isHighlight" : "isShort"}`}>{isLong ? "Long Story" : "Clip Pendek"}</span>
        </div>
        <div className="sourceArchiveCardMeta">
          <span><b>{item.clip_count}</b> output</span>
          <span>Proses <b>{formatDuration(item.processing_duration_seconds)}</b></span>
          {item.compilation_target_seconds ? <span>Target <b>{Math.round(item.compilation_target_seconds / 60)} menit</b></span> : null}
          <span>Upload <b>{item.auto_upload_youtube ? "Aktif" : "Manual"}</b></span>
        </div>
        <div className="sourceArchiveCardActions">
          <a href={item.source_url} target="_blank" rel="noreferrer"><Youtube size={14} /> Buka sumber <ExternalLink size={11} /></a>
          <button type="button" onClick={() => { void copyText(videoId, "ID video"); }}><Copy size={12} /> {videoId}</button>
          <button type="button" onClick={() => { void copyText(item.job_id, "ID job"); }}><Copy size={12} /> Job {item.job_id.slice(0, 8)}</button>
        </div>
        {item.output_names.length ? (
          <details className="sourceLogOutputs">
            <summary><FileVideo2 size={14} /> {item.output_names.length} file hasil <ChevronDown size={15} /></summary>
            <ul>{item.output_names.map((name) => <li key={name}>{name}</li>)}</ul>
          </details>
        ) : null}
      </div>
    </article>
  );
}
