"use client";

import { useRef, useState } from "react";
import {
  AlertTriangle,
  BarChart3,
  Archive,
  ArrowRight,
  BookOpen,
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
  storyText: string;
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
  onStoryTextChange: (value: string) => void;
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

const STORY_STEPS = [
  { icon: BookOpen, label: "Naskah otomatis", detail: "Pembuka sampai klimaks" },
  { icon: Film, label: "Scene sinematik", detail: "Tokoh, lokasi, dan gerak" },
  { icon: Sparkles, label: "Video lengkap", detail: "Dubbing, subtitle, dan musik" },
];

const HYPIT_COMMAND_PATTERN = /^\s*\/hypit(?:\s+|$)/i;
const HYPIT_QUICK_INTENT_PATTERN = /\b(?:ranking|rank|tier(?:\s+list)?|peringkat)\b/i;

const isHypitQuickPrompt = (value: string) => {
  if (!HYPIT_COMMAND_PATTERN.test(value)) return false;
  const body = value.replace(HYPIT_COMMAND_PATTERN, "").trim();
  return body.split(/\s+/).filter(Boolean).length <= 80 && HYPIT_QUICK_INTENT_PATTERN.test(body);
};

const formatCompactNumber = (value?: number | null) => value === null || value === undefined
  ? "—"
  : new Intl.NumberFormat("id-ID", { notation: "compact", maximumFractionDigits: 1 }).format(value);

export function QuickStartCard({
  url,
  storyText,
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
  onStoryTextChange,
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
  const isStory = clipMode === "long_animate";
  const isHypitPrompt = isStory && isHypitQuickPrompt(storyText);
  const hypitPromptWords = storyText
    .replace(/^\s*\/hypit\s*/i, "")
    .trim()
    .split(/\s+/)
    .filter(Boolean).length;
  const storyReady = hypitPromptWords >= 4;
  const canStart = isStory
    ? storyReady && confirmSourceRights && !isWorking
    : hasUrl
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
  const isLong = clipMode !== "short";
  const polishSteps = isStory ? STORY_STEPS : isLong ? LONG_STEPS : SHORT_STEPS;

  return (
    <section className={`clipperHero${isLong ? " isLong" : ""}${isWorking ? " isWorking" : ""}`} aria-labelledby="quick-start-title">
      <div className="clipperHeroCopy">
        <span className="clipperKicker">{isStory ? <BookOpen size={14} /> : isLong ? <Film size={14} /> : <Scissors size={14} />} AI PRODUCTION ENGINE</span>
        <h2 id="quick-start-title">
          {isStory ? "Satu ide cerita masuk." : "Satu video masuk."}<br />
          <em>{isStory ? "Video lengkap siap direview." : isLong ? "Cerita utuh siap ditonton." : "Short terbaik siap tayang."}</em>
        </h2>
        <p>
          {isStory
            ? "Tempel premis atau alur cerita. Hypit menyusun naskah semantik, Remotion merakit visual dan animasi, lalu ClipForge mengisi dubbing, subtitle, musik, dan QC otomatis."
            : isLong
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
          <span><WandSparkles size={16} /> {isWorking ? "Sedang meracik video" : isStory ? "Mulai dari jalan cerita" : "Mulai dari link video"}</span>
          <b>{isStory ? "9:16 · AI VIDEO" : isLong ? "16:9 · 5–10 menit" : "9:16 · 25–45 dtk"}</b>
        </div>

        <div className="formatChoice" role="group" aria-label="Pilih jenis hasil video">
          <button className={!isLong ? "active" : ""} type="button" disabled={isWorking} onClick={() => onClipModeChange("short")}>
            <span><Scissors size={17} /></span>
            <b>Viral Short<small>Retention feed · 9:16</small></b>
            {!isLong ? <CheckCircle2 size={16} /> : null}
          </button>
          <button className={clipMode === "highlight_5m" ? "active" : ""} type="button" disabled={isWorking} onClick={() => onClipModeChange("highlight_5m")}>
            <span><Film size={17} /></span>
            <b>Long Highlight<small>Watch time · 16:9</small></b>
            {clipMode === "highlight_5m" ? <CheckCircle2 size={16} /> : null}
          </button>
          <button className={isStory ? "active" : ""} type="button" disabled={isWorking} onClick={() => onClipModeChange("long_animate")}>
            <span><BookOpen size={17} /></span>
            <b>Generator Cerita<small>Premis → video jadi · 9:16</small></b>
            {isStory ? <CheckCircle2 size={16} /> : null}
          </button>
        </div>

        {isStory ? (
          <div className="storyStudioComposer">
            <header>
              <div className="storyStudioModeSwitch" aria-label="Mode pembuatan">
                <span className="active"><BookOpen size={14} /> 1. Prompt</span>
                <span className={storyReady ? "active" : ""}><Film size={14} /> 2. Video</span>
              </div>
              <small>{isHypitPrompt ? "HYPIT QUICK · CODE RENDERED" : "HYPIT TEXT-TO-VIDEO · REMOTION"}</small>
            </header>
            <label className="storyInputField">
              <span>Prompt video siap dirender</span>
              <textarea
                value={storyText}
                onChange={(event) => onStoryTextChange(event.target.value)}
                placeholder={'Contoh: Buatkan 10 detik video tentang seekor kucing yang berlari di kebun saat matahari terbit.'}
                rows={8}
                maxLength={30000}
              />
              <small>{storyText.trim().length.toLocaleString("id-ID")} / 30.000 karakter · minimum 4 kata · durasi dapat ditulis langsung di prompt</small>
            </label>
            <p className="sourceHint">Prompt langsung dikompilasi menjadi clip text-to-video Hypit. Remotion hanya merakit clip, caption stabil, audio, dan hasil akhir—tanpa tahap storyboard.</p>
            {!storyText.trim() ? (
              <div className="hypitPromptExamples" aria-label="Contoh prompt Hypit">
                <button type="button" onClick={() => onStoryTextChange("/hypit Make a ranking video that puts Hypit in S tier.")}>Ranking Hypit S tier</button>
                <button type="button" onClick={() => onStoryTextChange("/hypit Buat video ranking tentang patch kritis PHP yang menjadi isu hari ini.")}>Isu PHP hari ini</button>
              </div>
            ) : null}
            <footer>
              <div className="storyStudioTools">
                <span title="Prompt diikat ke satu aksi scene yang terukur"><Focus size={15} /> Prompt → scene</span>
                <span title="Hypit menghasilkan clip bergerak langsung"><WandSparkles size={15} /> Text-to-video</span>
                <span title="Remotion merakit clip tanpa caption berkedip"><Film size={15} /> Remotion stabil</span>
              </div>
              <div className="storyStudioDirector">
                <span><Sparkles size={14} /> Generate video</span>
                <button
                  aria-label="Generate video langsung dengan Hypit"
                  className="storyStudioSubmit"
                  disabled={!canStart}
                  type="button"
                  onClick={onStart}
                >
                  {isWorking ? <Loader2 className="spin" size={19} /> : <ArrowRight size={19} />}
                </button>
              </div>
            </footer>
          </div>
        ) : <label className="sourceUrlField">
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
        </label>}

        {!isStory && sourceReady && !sourceRightsBlocked ? (
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

        {!isStory && sourceProbe ? (
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

        {!isStory && sourceRightsBlocked ? (
          <div className="sourceNotice isDanger" role="alert">
            <AlertTriangle size={17} />
            <span>
              <strong>Sumber tidak aman untuk diproses ulang.</strong>
              <small>{sourceProbe?.source_rights_risk_reasons.slice(0, 2).join("; ")}. Gunakan rekaman sendiri atau materi berizin komersial.</small>
            </span>
          </div>
        ) : !isStory && invalidUrl ? (
          <div className="sourceNotice isDanger" role="alert">
            <AlertTriangle size={17} /><span><strong>Link belum dikenali.</strong><small>Periksa alamat video lalu coba lagi.</small></span>
          </div>
        ) : !isStory && sourceHistory?.found ? (
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
        ) : !isStory && sourceHistory?.valid_youtube_url ? (
          <div className="sourceNotice isSuccess" role="status">
            <CheckCircle2 size={17} /><span><strong>Link valid.</strong><small>Belum ada duplikat di riwayat.</small></span>
          </div>
        ) : null}

        {!isHypitPrompt ? <label className={`sourceRights${confirmSourceRights ? " checked" : ""}`}>
          <input
            type="checkbox"
            checked={confirmSourceRights}
            onChange={(event) => onConfirmSourceRightsChange(event.target.checked)}
          />
          <span><ShieldCheck size={16} /><b>{isStory ? "Saya punya hak atas cerita ini dan telah meninjau izin komersial provider AI." : "Saya punya hak/izin untuk audio dan visual sumber ini."}</b></span>
        </label> : (
          <div className="sourceNotice isSuccess" role="status">
            <CheckCircle2 size={17} /><span><strong>Render lokal siap.</strong><small>Visual dibuat dari kode; prompt ini tidak memakai footage, voice clone, atau ImageGen pihak ketiga.</small></span>
          </div>
        )}

        {error ? <div className="sourceError" role="alert">{error}</div> : null}

        {!isStory ? <div className="sourceActionGrid isSingle">
          <button className="createShortButton" type="button" disabled={!canStart} onClick={onStart}>
            {isWorking ? <Loader2 className="spin" size={19} /> : <WandSparkles size={19} />}
            <span>
              {isWorking ? "Produksi video sedang berjalan…" : isLong ? "Scan & Susun Long Highlight" : "Scan & Buat Short Terbaik"}
              <small>{isWorking ? "AI menyusun materi lalu melanjutkan ke render" : isLong ? "Pilih chapter, susun alur, lalu render otomatis" : "Pilih momen terbaik, audit struktur dan konteks, lalu render"}</small>
            </span>
            {!isWorking ? <ArrowRight size={19} /> : null}
          </button>
        </div> : null}

        {!isHypitPrompt && !confirmSourceRights && (isStory ? Boolean(storyText.trim()) : hasUrl) ? <p className="sourceHint">Storyboard boleh dibuat dulu. Konfirmasi hak dan izin diperlukan saat produksi video.</p> : null}
      </div>
    </section>
  );
}
