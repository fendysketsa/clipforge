"use client";

import { useRef, useState } from "react";
import {
  Archive,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ClipboardPaste,
  Clock3,
  Film,
  Link2,
  Loader2,
  Scissors,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import { formatDuration } from "../../lib/utils";
import type { ClipMode, SourceHistoryCheck } from "../../types/clip.type";

type QuickStartCardProps = {
  url: string;
  clipMode: ClipMode;
  videoDuration: number | null;
  sourceHistory: SourceHistoryCheck | null;
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

export function QuickStartCard({
  url,
  clipMode,
  videoDuration,
  sourceHistory,
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
  const isWorking = isBusy || isSubmitting;
  const canStart = hasUrl
    && !invalidUrl
    && !isCheckingSourceHistory
    && !duplicateBlocked
    && confirmSourceRights
    && !isWorking;

  const pasteFromClipboard = async () => {
    try {
      const value = (await navigator.clipboard.readText()).trim();
      if (!value) {
        setPasteMessage("Clipboard kosong. Tekan Ctrl+V di kolom link.");
        inputRef.current?.focus();
        return;
      }
      onUrlChange(value);
      setPasteMessage("Link berhasil ditempel.");
    } catch {
      setPasteMessage("Browser memblokir clipboard. Tekan Ctrl+V di kolom link.");
      inputRef.current?.focus();
    }
  };

  const modeLabel = clipMode === "highlight_5m" ? "Long Story" : "Clip Pendek";

  return (
    <section className="quickStart" aria-labelledby="quick-start-title">
      <div className="quickStartIntro">
        <span className="quickStartEyebrow"><Scissors size={14} /> Quick Start</span>
        <h2 id="quick-start-title">Satu link. Dua format. Siap review.</h2>
        <p>
          Pilih format, tempel link YouTube, lalu klik proses. Pengaturan aman sudah disiapkan.
        </p>
        <div className="quickStartFacts" aria-label="Ringkasan kemampuan">
          <span><ShieldCheck size={14} /> Lisensi & audit aktif</span>
          <span><Clock3 size={14} /> Hingga 3 proses paralel</span>
          <span><Film size={14} /> Output selalu direview dulu</span>
        </div>
      </div>

      <div className="quickStartComposer">
        <div className="quickModeGrid" role="group" aria-label="Pilih format video">
          <button
            className={clipMode === "short" ? "active" : ""}
            type="button"
            onClick={() => onClipModeChange("short")}
          >
            <span className="quickModeIcon"><Scissors size={19} /></span>
            <span>
              <strong>Clip Pendek</strong>
              <small>9:16 · 25–180 detik · beberapa momen terbaik</small>
            </span>
            {clipMode === "short" ? <CheckCircle2 size={18} /> : null}
          </button>
          <button
            className={clipMode === "highlight_5m" ? "active" : ""}
            type="button"
            onClick={() => onClipModeChange("highlight_5m")}
          >
            <span className="quickModeIcon"><Film size={19} /></span>
            <span>
              <strong>Long Story</strong>
              <small>16:9 · 5–10 menit · alur kronologis tanpa filler</small>
            </span>
            {clipMode === "highlight_5m" ? <CheckCircle2 size={18} /> : null}
          </button>
        </div>

        <label className="quickLinkField">
          <span>Link video YouTube</span>
          <div className="quickLinkInput">
            <Link2 size={19} />
            <input
              ref={inputRef}
              value={url}
              onChange={(event) => onUrlChange(event.target.value)}
              placeholder="Tempel https://youtube.com/watch?v=..."
              inputMode="url"
              autoComplete="url"
            />
            <button type="button" onClick={() => { void pasteFromClipboard(); }}>
              <ClipboardPaste size={16} /> Tempel
            </button>
          </div>
          <small className={pasteMessage.includes("berhasil") ? "isSuccess" : ""}>
            {isCheckingSourceHistory
              ? "Memeriksa link, durasi, dan riwayat sumber…"
              : videoDuration
                ? `Video terdeteksi · durasi ${formatDuration(videoDuration)}`
                : pasteMessage || "Mendukung link watch, youtu.be, Shorts, Live, dan Embed."}
          </small>
        </label>

        {invalidUrl ? (
          <div className="quickNotice isDanger" role="alert">
            <AlertTriangle size={17} />
            <span>Link belum dikenali sebagai video YouTube. Periksa lalu tempel ulang.</span>
          </div>
        ) : sourceHistory?.found ? (
          <label className="quickNotice isWarning">
            <AlertTriangle size={17} />
            <span className="quickNoticeCopy">
              <strong>Sumber ini pernah diproses {sourceHistory.usage_count ? `${sourceHistory.usage_count} kali` : "sebelumnya"}.</strong>
              <small>
                {sourceHistory.last_processed_at
                  ? `Terakhir ${new Intl.DateTimeFormat("id-ID", { dateStyle: "medium", timeZone: "Asia/Jakarta" }).format(new Date(sourceHistory.last_processed_at))}. `
                  : ""}
                Centang bila memang ingin membuat versi baru.
              </small>
              <a href="/source-history"><Archive size={12} /> Buka arsip sumber</a>
            </span>
            <input
              type="checkbox"
              checked={allowReprocessSource}
              onChange={(event) => onAllowReprocessSourceChange(event.target.checked)}
            />
          </label>
        ) : sourceHistory?.valid_youtube_url ? (
          <div className="quickNotice isSuccess" role="status">
            <CheckCircle2 size={17} />
            <span>Link valid dan belum ditemukan dalam riwayat proses.</span>
          </div>
        ) : null}

        <label className="quickRightsCheck">
          <input
            type="checkbox"
            checked={confirmSourceRights}
            onChange={(event) => onConfirmSourceRightsChange(event.target.checked)}
          />
          <span>
            Saya memiliki rekaman ini atau izin komersial yang dapat dibuktikan untuk seluruh audio dan visual.
          </span>
        </label>

        {error ? <div className="quickError" role="alert">{error}</div> : null}

        <div className="quickStartActions">
          <a href="#workspace"><SlidersHorizontal size={15} /> Poles hasil</a>
          <button className="quickStartButton" type="button" disabled={!canStart} onClick={onStart}>
            {isWorking ? <Loader2 className="spin" size={18} /> : <ArrowRight size={18} />}
            {isWorking ? "Sedang menyiapkan…" : `Proses ${modeLabel}`}
          </button>
        </div>
        {!confirmSourceRights && hasUrl ? (
          <p className="quickStartHint">Centang konfirmasi izin sumber untuk mengaktifkan tombol proses.</p>
        ) : null}
      </div>
    </section>
  );
}
