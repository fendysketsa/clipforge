"use client";

import {
  CalendarClock,
  CheckCircle2,
  ChevronDown,
  Clock3,
  ExternalLink,
  FileVideo2,
  Film,
  ListChecks,
  Loader2,
  Search,
  Sparkles,
  Youtube,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { getSourceUsageLog } from "../../lib/apiClient";
import type { ClipMode, SourceUsageLogEntry, SourceUsageLogResponse } from "../../types/clip.type";
import { SiteFooter } from "../_components/SiteFooter";
import { Topbar } from "../_components/Topbar";

type ModeFilter = "all" | ClipMode;

const formatDateTime = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("id-ID", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Jakarta",
  }).format(date);
};

const formatDuration = (seconds?: number | null) => {
  if (seconds === null || seconds === undefined) return "—";
  const rounded = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(rounded / 60);
  const remainder = rounded % 60;
  return minutes ? `${minutes}m ${remainder}s` : `${remainder}s`;
};

const sourceVideoId = (url: string) => {
  try {
    return new URL(url).searchParams.get("v") || "—";
  } catch {
    return "—";
  }
};

export default function SourceHistoryPage() {
  const [data, setData] = useState<SourceUsageLogResponse>({ items: [], total: 0, unique_sources: 0 });
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<ModeFilter>("all");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  const loadLog = useCallback(async (notify = false) => {
    setIsLoading(true);
    setError("");
    try {
      const next = await getSourceUsageLog();
      setData(next);
      if (notify) toast.success("Log sumber berhasil disinkronkan");
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : "Gagal memuat log sumber";
      setError(message);
      if (notify) toast.error(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadLog().catch(() => undefined);
  }, [loadLog]);

  const counts = useMemo(() => ({
    short: data.items.filter((item) => item.clip_mode === "short").length,
    highlight: data.items.filter((item) => item.clip_mode === "highlight_5m").length,
  }), [data.items]);

  const filteredItems = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("id-ID");
    return data.items.filter((item) => {
      if (mode !== "all" && item.clip_mode !== mode) return false;
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
  }, [data.items, mode, query]);

  return (
    <main className="shell sourceLogPage">
      <Topbar
        activePage="source-log"
        isRefreshing={isLoading}
        onRefresh={() => loadLog(true)}
      />

      <section className="sourceLogHero">
        <div>
          <span className="sourceLogEyebrow"><ListChecks size={15} /> Audit log sumber</span>
          <h2>Riwayat Link YouTube Berhasil Diproses</h2>
          <p>
            Log ini hanya dibuat setelah proses clipper selesai sukses. Job gagal atau dibatalkan tidak dimasukkan.
          </p>
        </div>
        <div className="sourceLogIntegrity">
          <CheckCircle2 size={20} />
          <span><strong>Success-only log</strong>Persisten meski card hasil sudah dibersihkan</span>
        </div>
      </section>

      <section className="sourceLogStats" aria-label="Ringkasan log sumber">
        <article>
          <span><CalendarClock size={18} /> Total proses sukses</span>
          <strong>{data.total}</strong>
        </article>
        <article>
          <span><Youtube size={18} /> Sumber unik</span>
          <strong>{data.unique_sources}</strong>
        </article>
        <article>
          <span><Sparkles size={18} /> Clip pendek</span>
          <strong>{counts.short}</strong>
        </article>
        <article>
          <span><Film size={18} /> Highlight / Resume</span>
          <strong>{counts.highlight}</strong>
        </article>
      </section>

      <section className="sourceLogPanel">
        <div className="sourceLogToolbar">
          <label className="sourceLogSearch">
            <Search size={16} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Cari judul, channel, ID video, job, atau file output…"
            />
          </label>
          <div className="sourceLogFilters" role="group" aria-label="Filter format hasil">
            <button className={mode === "all" ? "active" : ""} type="button" onClick={() => setMode("all")}>
              Semua <span>{data.total}</span>
            </button>
            <button className={mode === "short" ? "active" : ""} type="button" onClick={() => setMode("short")}>
              Clip pendek <span>{counts.short}</span>
            </button>
            <button className={mode === "highlight_5m" ? "active" : ""} type="button" onClick={() => setMode("highlight_5m")}>
              Highlight <span>{counts.highlight}</span>
            </button>
          </div>
        </div>

        {error ? <div className="sourceLogError">{error}</div> : null}
        {isLoading && !data.items.length ? (
          <div className="sourceLogEmpty"><Loader2 className="spin" size={28} /><strong>Memuat audit log…</strong></div>
        ) : filteredItems.length ? (
          <div className="sourceLogList">
            {filteredItems.map((item) => <SourceLogCard item={item} key={`${item.job_id}-${item.clip_mode}`} />)}
          </div>
        ) : (
          <div className="sourceLogEmpty">
            <FileVideo2 size={30} />
            <strong>{data.items.length ? "Tidak ada log yang cocok" : "Belum ada proses sukses tercatat"}</strong>
            <span>{data.items.length ? "Ubah kata pencarian atau filter format." : "Log pertama muncul otomatis setelah clipper berhasil."}</span>
          </div>
        )}
      </section>

      <SiteFooter />
    </main>
  );
}

function SourceLogCard({ item }: { item: SourceUsageLogEntry }) {
  const isHighlight = item.clip_mode === "highlight_5m";
  return (
    <article className="sourceLogCard">
      <div className={`sourceLogModeIcon ${isHighlight ? "isHighlight" : "isShort"}`}>
        {isHighlight ? <Film size={20} /> : <Sparkles size={20} />}
      </div>
      <div className="sourceLogCardMain">
        <div className="sourceLogCardHeader">
          <div>
            <span className="sourceLogDate"><Clock3 size={13} /> {formatDateTime(item.processed_at)} WIB</span>
            <h3>{item.source_title || `Video YouTube ${sourceVideoId(item.source_url)}`}</h3>
            <p>{item.source_uploader || "Channel tidak tercatat"}</p>
          </div>
          <span className={`sourceLogModeBadge ${isHighlight ? "isHighlight" : "isShort"}`}>
            {isHighlight ? "Highlight / Resume 5–10 menit" : "Clip pendek"}
          </span>
        </div>

        <div className="sourceLogMeta">
          <span><b>{item.clip_count}</b> output</span>
          <span>Proses <b>{formatDuration(item.processing_duration_seconds)}</b></span>
          {item.compilation_target_seconds ? <span>Target <b>{Math.round(item.compilation_target_seconds / 60)} menit</b></span> : null}
          <span>Auto-upload <b>{item.auto_upload_youtube ? "Aktif" : "Tidak"}</b></span>
          <span>Job <b>{item.job_id.slice(0, 10)}</b></span>
        </div>

        <div className="sourceLogActions">
          <a href={item.source_url} target="_blank" rel="noreferrer">
            <Youtube size={15} /> Buka sumber <ExternalLink size={12} />
          </a>
          <code>{sourceVideoId(item.source_url)}</code>
        </div>

        {item.output_names.length ? (
          <details className="sourceLogOutputs">
            <summary><FileVideo2 size={14} /> Lihat {item.output_names.length} file hasil <ChevronDown size={15} /></summary>
            <ul>{item.output_names.map((name) => <li key={name}>{name}</li>)}</ul>
          </details>
        ) : null}
      </div>
    </article>
  );
}
