"use client";

import { useRef, useState } from "react";
import {
  AlertTriangle,
  BarChart3,
  Archive,
  ArrowRight,
  Check,
  CheckCircle2,
  ClipboardPaste,
  Clock3,
  Focus,
  Film,
  Link2,
  Loader2,
  Scissors,
  ShieldCheck,
  Sparkles,
  Subtitles,
  WandSparkles,
} from "lucide-react";
import { formatDuration } from "../../lib/utils";
import type { SourceProbe } from "../../lib/apiClient";
import type { ClipMode, SourceHistoryCheck } from "../../types/clip.type";

type QuickStartCardProps = {
  url: string;
  clipMode: ClipMode;
  videoDuration: number | null;
  sourceHistory: SourceHistoryCheck | null;
  sourceProbe: SourceProbe | null;
  isCheckingSourceHistory: boolean;
  allowReprocessSource: boolean;
  confirmSourceRights: boolean;
  isBusy: boolean;
  isSubmitting: boolean;
  error: string;
  onUrlChange: (value: string) => void;
  onClipModeChange: (value: ClipMode) => void;
  onAllowReprocessSourceChange: (value: boolean) => void;
  onConfirmSourceRightsChange: (value: boolean) => void;
  onStart: () => void;
};

const SHORT_STEPS = [
  { icon: Focus, label: "Framing otomatis", detail: "Wajah aman di 9:16" },
  { icon: Subtitles, label: "Caption dinamis", detail: "Nyaman dibaca di feed" },
  { icon: Sparkles, label: "Polish retention", detail: "Hook, ritme, dan payoff" },
];

const LONG_STEPS = [
  { icon: Sparkles, label: "Cold open", detail: "Momen terkuat masuk lebih awal" },
  { icon: Film, label: "Story chapters", detail: "Alur rapi, tanpa filler" },
  { icon: Focus, label: "YouTube packaging", detail: "Thumbnail dan judul selaras" },
];

const formatCompactNumber = (value?: number | null) => value === null || value === undefined
  ? "—"
  : new Intl.NumberFormat("id-ID", { notation: "compact", maximumFractionDigits: 1 }).format(value);

export function QuickStartCard({
  url,
  clipMode,
  videoDuration,
  sourceHistory,
  sourceProbe,
  isCheckingSourceHistory,
  allowReprocessSource,
  confirmSourceRights,
  isBusy,
  isSubmitting,
  error,
  onUrlChange,
  onClipModeChange,
  onAllowReprocessSourceChange,
  onConfirmSourceRightsChange,
  onStart,
}: QuickStartCardProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [pasteMessage, setPasteMessage] = useState("");
  const hasUrl = Boolean(url.trim());
  const invalidUrl = Boolean(hasUrl && sourceHistory && !sourceHistory.valid_youtube_url);
  const duplicateBlocked = Boolean(sourceHistory?.found && !allowReprocessSource);
  const sourceRightsBlocked = Boolean(sourceProbe?.source_rights_risk);
  const quickScore = sourceProbe?.momentum_score ?? null;
  const quickRecommendation = sourceProbe?.quick_check_recommendation ?? "unknown";
  const quickLabel = sourceProbe?.momentum_label || "Data publik belum cukup";
  const quickReason = sourceProbe?.quick_check_reason
    || (quickScore === null
      ? "Gunakan Scan Potensi Viral untuk menilai isi video."
      : `Momentum sumber ${Math.round(quickScore)}/100 hanya sinyal distribusi. Scan transkrip tetap menentukan nilai informasi, hook, konteks, dan payoff.`);
  const isWorking = isBusy || isSubmitting;
  const canStart = hasUrl
    && !invalidUrl
    && !isCheckingSourceHistory
    && !duplicateBlocked
    && !sourceRightsBlocked
    && confirmSourceRights
    && !isWorking;

  const pasteFromClipboard = async () => {
    try {
      const value = (await navigator.clipboard.readText()).trim();
      if (!value) {
        setPasteMessage("Clipboard kosong — tekan Ctrl+V di kolom link.");
        inputRef.current?.focus();
        return;
      }
      onUrlChange(value);
      setPasteMessage("Link berhasil ditempel.");
    } catch {
      setPasteMessage("Clipboard diblokir browser — tekan Ctrl+V.");
      inputRef.current?.focus();
    }
  };

  const sourceReady = Boolean(sourceProbe?.title || videoDuration);
  const isLong = clipMode === "highlight_5m";
  const polishSteps = isLong ? LONG_STEPS : SHORT_STEPS;

  return (
    <section className={`clipperHero${isLong ? " isLong" : ""}${isWorking ? " isWorking" : ""}`} aria-labelledby="quick-start-title">
      <div className="clipperHeroCopy">
        <span className="clipperKicker">{isLong ? <Film size={14} /> : <Scissors size={14} />} AI VIDEO CLIPPER</span>
        <h2 id="quick-start-title">
          Satu video masuk.<br />
          <em>{isLong ? "Cerita utuh siap ditonton." : "Short terbaik siap tayang."}</em>
        </h2>
        <p>
          {isLong
            ? "AI memilih chapter terbaik, menyusun alur, lalu menyiapkan video panjang yang rapi dan siap direview."
            : "AI menemukan momen terbaik lalu merapikan framing, caption, ritme, dan audio secara otomatis."}
        </p>

        <div className="clipperPromise">
          {polishSteps.map(({ icon: Icon, label, detail }) => (
            <span key={label}>
              <i><Icon size={16} /></i>
              <b>{label}<small>{detail}</small></b>
            </span>
          ))}
        </div>
      </div>

      <div className="sourceComposer">
        <div className="sourceComposerTop">
          <span><WandSparkles size={16} /> {isWorking ? "Sedang meracik video" : "Mulai dari link video"}</span>
          <b>{isLong ? "16:9 · 5–10 menit" : "9:16 · 25–45 dtk"}</b>
        </div>

        <div className="formatChoice" role="group" aria-label="Pilih jenis hasil video">
          <button className={!isLong ? "active" : ""} type="button" disabled={isWorking} onClick={() => onClipModeChange("short")}>
            <span><Scissors size={17} /></span>
            <b>Viral Short<small>Retention feed · 9:16</small></b>
            {!isLong ? <CheckCircle2 size={16} /> : null}
          </button>
          <button className={isLong ? "active" : ""} type="button" disabled={isWorking} onClick={() => onClipModeChange("highlight_5m")}>
            <span><Film size={17} /></span>
            <b>Long Highlight<small>Watch time · 16:9</small></b>
            {isLong ? <CheckCircle2 size={16} /> : null}
          </button>
        </div>

        <label className="sourceUrlField">
          <span>Link video sumber</span>
          <div className="sourceUrlInput">
            <Link2 size={20} />
            <input
              ref={inputRef}
              value={url}
              onChange={(event) => onUrlChange(event.target.value)}
              placeholder="Tempel link YouTube di sini…"
              inputMode="url"
              autoComplete="url"
            />
            <button type="button" onClick={() => { void pasteFromClipboard(); }}>
              <ClipboardPaste size={16} /><span>Tempel</span>
            </button>
          </div>
          <small className={pasteMessage.includes("berhasil") ? "isSuccess" : ""}>
            {isCheckingSourceHistory
              ? "Sedang memeriksa sumber…"
              : videoDuration
                ? `Terdeteksi · ${formatDuration(videoDuration)}`
                : pasteMessage || "YouTube watch, Shorts, Live, dan youtu.be"}
          </small>
        </label>

        {sourceReady && !sourceRightsBlocked ? (
          <div className="sourceDetected" role="status">
            <span className="sourceDetectedIcon"><Check size={18} /></span>
            <span>
              <small>Sumber siap dianalisis</small>
              <strong>{sourceProbe?.title || "Video terdeteksi"}</strong>
              {sourceProbe?.uploader ? <em>{sourceProbe.uploader}</em> : null}
            </span>
            {videoDuration ? <b><Clock3 size={13} /> {formatDuration(videoDuration)}</b> : null}
          </div>
        ) : null}

        {sourceProbe ? (
          <div className={`sourceQuickCheck is-${quickRecommendation}`} role="status">
            <div className="sourceQuickScore">
              <BarChart3 size={15} />
              <b>{sourceProbe.momentum_score === null ? "—" : Math.round(sourceProbe.momentum_score)}</b>
              <small>/100</small>
            </div>
            <div className="sourceQuickCopy">
              <span>QUICK CHECK OTOMATIS · SINYAL SUMBER</span>
              <strong>{quickLabel}</strong>
              <small>{quickReason}</small>
            </div>
            <div className="sourceQuickMetrics">
              <span><b>{formatCompactNumber(sourceProbe.view_count)}</b> views</span>
              <span><b>{formatCompactNumber(sourceProbe.views_per_day)}</b> /hari</span>
              <span><b>{sourceProbe.source_age_days ?? "—"}</b> hari</span>
              {quickRecommendation === "skip" ? (
                <button type="button" onClick={() => onUrlChange("")}>Lewati sumber</button>
              ) : null}
            </div>
          </div>
        ) : null}

        {sourceRightsBlocked ? (
          <div className="sourceNotice isDanger" role="alert">
            <AlertTriangle size={17} />
            <span>
              <strong>Sumber tidak aman untuk diproses ulang.</strong>
              <small>{sourceProbe?.source_rights_risk_reasons.slice(0, 2).join("; ")}. Gunakan rekaman sendiri atau materi berizin komersial.</small>
            </span>
          </div>
        ) : invalidUrl ? (
          <div className="sourceNotice isDanger" role="alert">
            <AlertTriangle size={17} /><span><strong>Link belum dikenali.</strong><small>Periksa alamat video lalu coba lagi.</small></span>
          </div>
        ) : sourceHistory?.found ? (
          <label className="sourceNotice isWarning">
            <AlertTriangle size={17} />
            <span>
              <strong>Sumber ini pernah diproses {sourceHistory.usage_count ? `${sourceHistory.usage_count}×` : "sebelumnya"}.</strong>
              <small>Aktifkan bila ingin membuat versi baru. <a href="/source-history"><Archive size={11} /> Buka Log Sumber</a></small>
            </span>
            <input
              type="checkbox"
              checked={allowReprocessSource}
              onChange={(event) => onAllowReprocessSourceChange(event.target.checked)}
            />
          </label>
        ) : sourceHistory?.valid_youtube_url ? (
          <div className="sourceNotice isSuccess" role="status">
            <CheckCircle2 size={17} /><span><strong>Link valid.</strong><small>Belum ada duplikat di riwayat.</small></span>
          </div>
        ) : null}

        <label className={`sourceRights${confirmSourceRights ? " checked" : ""}`}>
          <input
            type="checkbox"
            checked={confirmSourceRights}
            onChange={(event) => onConfirmSourceRightsChange(event.target.checked)}
          />
          <span><ShieldCheck size={16} /><b>Saya punya hak/izin untuk audio dan visual sumber ini.</b></span>
        </label>

        {error ? <div className="sourceError" role="alert">{error}</div> : null}

        <div className="sourceActionGrid isSingle">
          <button className="createShortButton" type="button" disabled={!canStart} onClick={onStart}>
            {isWorking ? <Loader2 className="spin" size={19} /> : <WandSparkles size={19} />}
            <span>
              {isWorking ? "Scan dan render sedang berjalan…" : isLong ? "Scan & Susun Long Highlight" : "Scan & Buat Short Terbaik"}
              <small>{isWorking ? "AI memilih kandidat lalu melanjutkan ke render" : isLong ? "Pilih chapter, susun alur, lalu render otomatis" : "Pilih momen terbaik, audit struktur dan konteks, lalu render"}</small>
            </span>
            {!isWorking ? <ArrowRight size={19} /> : null}
          </button>
        </div>

        {!confirmSourceRights && hasUrl ? <p className="sourceHint">Konfirmasi izin untuk menjalankan scan dan render dalam satu proses.</p> : null}
      </div>
    </section>
  );
}
