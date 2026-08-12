import {
  BarChart3,
  CheckCircle2,
  ChevronDown,
  Clipboard,
  Clock3,
  Download,
  ExternalLink,
  Info,
  Lightbulb,
  LoaderCircle,
  RefreshCw,
  Settings2,
  Sparkles,
  Target,
  Trash2,
  UploadCloud,
  Video,
} from "lucide-react";
import { useEffect, useState } from "react";
import { getOutputUrl } from "../../lib/apiClient";
import { clipDisplayTitle, handleCopyTitle, handleDownload } from "../../lib/utils";
import type { ClipFile, YouTubeUploadJob } from "../../types/clip.type";
import { ThumbnailPrompt } from "./ThumbnailPrompt";

const COMPLETED_UPLOAD_STATUS_TTL_MS = 30_000;
const CLEANUP_SUCCESS_DISPLAY_MS = 6_000;
const CLEANUP_ITEMS = [
  { id: "thumbnail", label: "Thumbnail dan prompt thumbnail" },
  { id: "metadata", label: "Caption serta metadata JSON" },
  { id: "video", label: "Video utama MP4 hasil klip" },
  { id: "workspace", label: "File sementara dan folder kosong" },
  { id: "job_sync", label: "Card klip dan riwayat job disinkronkan" },
];

type ResultsSectionProps = {
  clips: ClipFile[];
  selectedClipUrls: string[];
  youtubeEnabled: boolean;
  youtubeStatusMessage: string;
  youtubeAutoUploadCount: number;
  youtubeUploads: YouTubeUploadJob[];
  isYouTubeLoginActive: boolean;
  onDeleteAllClips: () => void;
  onDeleteClip: (clip: ClipFile) => void;
  onDeleteSelectedClips: () => void;
  onCaptureYouTubeSession: () => void;
  onEnableNoCdpMode: () => void;
  onImportYouTubeCdpCookies: () => void;
  onSetupYouTubeOneTimeLogin: () => void;
  onStartYouTubeLogin: () => void;
  onUploadAllToYouTube: () => void;
  onUploadClipToYouTube: (clip: ClipFile) => void;
  onToggleAllClipSelection: () => void;
  onToggleClipSelection: (clipUrl: string) => void;
  onToggleClipCorrect: (clip: ClipFile, isCorrect: boolean) => void;
};

function friendlyYouTubeUploadError(message: string, usesChromeDebugging: boolean) {
  const clean = message.trim();
  const lowered = clean.toLowerCase();
  if (lowered.includes("connect_over_cdp") || lowered.includes("econnrefused")) {
    return "CDP belum aktif. Klik Login Sekali agar upload memakai Playwright storage-state tanpa CDP.";
  }
  if (lowered.includes("python youtube_uploader.py login")) {
    return "Session YouTube belum tersimpan. Klik Login Sekali, lalu Retry YouTube.";
  }
  if (
    usesChromeDebugging
    && (lowered.includes("sesi youtube belum login") || lowered.includes("youtube studio meminta login"))
  ) {
    return "Session YouTube belum valid. Klik Login Sekali agar Playwright menyimpan ulang storage-state.";
  }
  if (
    usesChromeDebugging
    && lowered.includes("playlist")
    && (lowered.includes("tidak ditemukan") || lowered.includes("not found"))
  ) {
    return "Studio belum siap membaca playlist. Klik Login Sekali untuk refresh session, lalu Retry YouTube.";
  }
  return clean;
}

function youtubeUploadErrorNeedsSessionRepair(message: string) {
  const lowered = message.toLowerCase();
  return [
    "cdp",
    "connect_over_cdp",
    "econnrefused",
    "login",
    "session",
    "sesi youtube",
    "remote debugging",
  ].some((marker) => lowered.includes(marker));
}

function fypScoreTone(score: number) {
  if (score >= 88) return "excellent";
  if (score >= 78) return "strong";
  if (score >= 65) return "promising";
  return "polish";
}

function completedUploadStatusIsVisible(upload: YouTubeUploadJob, now: number) {
  if (upload.status !== "completed") return true;
  if (!upload.video_url || upload.clip_delete_error) return true;
  if (upload.clip_delete_after && !upload.clip_deleted_at) return true;
  if (upload.clip_deleted_at) {
    const deletedAt = Date.parse(upload.clip_deleted_at);
    return Number.isNaN(deletedAt) || now - deletedAt < CLEANUP_SUCCESS_DISPLAY_MS;
  }
  const completedAt = Date.parse(upload.finished_at || upload.updated_at);
  return Number.isNaN(completedAt) || now - completedAt < COMPLETED_UPLOAD_STATUS_TTL_MS;
}

function uploadCleanupCountdown(upload: YouTubeUploadJob, now: number) {
  if (!upload.clip_delete_after || upload.clip_deleted_at) return null;
  if (typeof upload.clip_delete_remaining_seconds === "number") {
    return Math.max(0, Math.ceil(upload.clip_delete_remaining_seconds));
  }
  const deleteAt = Date.parse(upload.clip_delete_after);
  if (Number.isNaN(deleteAt)) return null;
  return Math.max(0, Math.ceil((deleteAt - now) / 1000));
}

function uploadCleanupProgress(upload: YouTubeUploadJob, now: number) {
  if (!upload.clip_delete_after) return 0;
  const deleteAt = Date.parse(upload.clip_delete_after);
  const startedAt = Date.parse(upload.finished_at || upload.updated_at);
  if (Number.isNaN(deleteAt) || Number.isNaN(startedAt) || deleteAt <= startedAt) return 0;
  const totalSeconds = (deleteAt - startedAt) / 1000;
  const elapsedSeconds = typeof upload.clip_delete_remaining_seconds === "number"
    ? totalSeconds - upload.clip_delete_remaining_seconds
    : (now - startedAt) / 1000;
  return Math.max(0, Math.min(12, (elapsedSeconds / totalSeconds) * 12));
}

export function ResultsSection({
  clips,
  selectedClipUrls,
  youtubeEnabled,
  youtubeStatusMessage,
  youtubeAutoUploadCount,
  youtubeUploads,
  isYouTubeLoginActive,
  onDeleteAllClips,
  onDeleteClip,
  onDeleteSelectedClips,
  onCaptureYouTubeSession,
  onEnableNoCdpMode,
  onImportYouTubeCdpCookies,
  onSetupYouTubeOneTimeLogin,
  onStartYouTubeLogin,
  onUploadAllToYouTube,
  onUploadClipToYouTube,
  onToggleAllClipSelection,
  onToggleClipSelection,
  onToggleClipCorrect,
}: ResultsSectionProps) {
  const [uploadStatusNow, setUploadStatusNow] = useState(() => Date.now());
  const selectedCount = selectedClipUrls.length;
  const allClipsSelected = clips.length > 0 && selectedCount === clips.length;
  const usesChromeDebugging = /remote debugging|cdp/i.test(youtubeStatusMessage);
  const openStudioWaitingLabel = usesChromeDebugging ? "Menyiapkan..." : "Menunggu login...";
  const hasCleanupCountdown = youtubeUploads.some(
    (upload) => Boolean(upload.clip_delete_after && !upload.clip_deleted_at),
  );

  useEffect(() => {
    if (!hasCleanupCountdown) return;
    setUploadStatusNow(Date.now());
    const interval = window.setInterval(() => setUploadStatusNow(Date.now()), 1000);
    return () => window.clearInterval(interval);
  }, [hasCleanupCountdown]);

  useEffect(() => {
    const now = Date.now();
    const nextExpiry = youtubeUploads.reduce<number | null>((nearest, upload) => {
      if (upload.status !== "completed") return nearest;
      const statusAt = Date.parse(upload.clip_deleted_at || upload.finished_at || upload.updated_at);
      if (Number.isNaN(statusAt)) return nearest;
      const expiresAt = statusAt + (
        upload.clip_deleted_at ? CLEANUP_SUCCESS_DISPLAY_MS : COMPLETED_UPLOAD_STATUS_TTL_MS
      );
      if (expiresAt <= now) return nearest;
      return nearest === null ? expiresAt : Math.min(nearest, expiresAt);
    }, null);

    if (nextExpiry === null) return;
    const timer = window.setTimeout(
      () => setUploadStatusNow(Date.now()),
      Math.max(0, nextExpiry - now + 50),
    );
    return () => window.clearTimeout(timer);
  }, [uploadStatusNow, youtubeUploads]);

  return (
    <section className="results" id="results">
      <div className="sectionHeader">
        <div className="sectionTitle">
          <span className="sectionEyebrow">Output</span>
          <h2>Klip Siap Digunakan</h2>
          <p>Review, unduh, atau kirim langsung ke YouTube.</p>
        </div>
        <div className="resultsActions">
          <span className="sectionBadge">{clips.length} klip siap</span>
          {clips.length > 0 ? (
            <>
              <label className="selectAllClips">
                <input checked={allClipsSelected} type="checkbox" onChange={onToggleAllClipSelection} />
                <span>Pilih semua</span>
              </label>
              {selectedCount > 0 ? (
                <button type="button" onClick={onDeleteSelectedClips} className="uiButton uiButton--danger">
                  <Trash2 size={16} />
                  <span>Hapus terpilih ({selectedCount})</span>
                </button>
              ) : null}
              <button
                type="button"
                onClick={onUploadAllToYouTube}
                className="uiButton uiButton--youtube"
                disabled={!youtubeEnabled}
                title={
                  youtubeEnabled
                    ? `Upload ${Math.min(youtubeAutoUploadCount, clips.length)} klip terbaik sebagai Private untuk pemeriksaan klaim`
                    : youtubeStatusMessage
                }
              >
                <UploadCloud size={16} />
                <span>Upload {Math.min(youtubeAutoUploadCount, clips.length)} terbaik</span>
              </button>
              <button type="button" onClick={onDeleteAllClips} className="uiButton uiButton--ghostDanger">
                <Trash2 size={16} />
                <span>Hapus semua</span>
              </button>
            </>
          ) : null}
        </div>
      </div>

      {clips.length > 0 && (usesChromeDebugging || !youtubeEnabled) ? (
        <details className="youtubeSetupPanel">
          <summary>
            <span className="youtubeSetupIcon">
              <Settings2 size={17} />
            </span>
            <span className="youtubeSetupCopy">
              <strong>Pengaturan koneksi YouTube</strong>
              <small>{youtubeStatusMessage}</small>
            </span>
            <ChevronDown className="detailsChevron" size={18} />
          </summary>
          <div className="youtubeSetupActions">
            <button
              type="button"
              onClick={onSetupYouTubeOneTimeLogin}
              className="uiButton uiButton--secondary"
              title="Ambil cookies/session sekali lalu upload berikutnya memakai storage-state"
            >
              <RefreshCw size={16} />
              <span>Login Sekali</span>
            </button>
            {usesChromeDebugging ? (
              <>
                <button
                  type="button"
                  onClick={onCaptureYouTubeSession}
                  className="uiButton uiButton--secondary"
                  disabled={isYouTubeLoginActive}
                >
                  <RefreshCw size={16} />
                  <span>CDP Opsional</span>
                </button>
                <button type="button" onClick={onEnableNoCdpMode} className="uiButton uiButton--secondary">
                  <Settings2 size={16} />
                  <span>Gunakan tanpa CDP</span>
                </button>
                <button
                  type="button"
                  onClick={onImportYouTubeCdpCookies}
                  className="uiButton uiButton--secondary"
                >
                  <Download size={16} />
                  <span>Ambil Cookies</span>
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  onClick={onStartYouTubeLogin}
                  className="uiButton uiButton--secondary"
                  disabled={isYouTubeLoginActive}
                >
                  <ExternalLink size={16} />
                  <span>Login YouTube</span>
                </button>
                <button
                  type="button"
                  onClick={onCaptureYouTubeSession}
                  className="uiButton uiButton--secondary"
                >
                  <RefreshCw size={16} />
                  <span>Sinkronkan Session</span>
                </button>
              </>
            )}
          </div>
        </details>
      ) : null}

      {clips.length ? (
        <div className="clipGrid">
          {clips.map((clip) => {
            const title = clipDisplayTitle(clip);
            const url = getOutputUrl(clip.url);
            const isSelected = selectedClipUrls.includes(clip.url);
            const latestUpload = youtubeUploads.find((upload) => upload.clip_url === clip.url);
            const isLongForm = clip.name.toLowerCase().startsWith("highlight_5menit_")
              || clip.name.toLowerCase().startsWith("resume_cerita_");
            const isUploadingToYouTube = latestUpload?.status === "queued" || latestUpload?.status === "running";
            const isAlreadyUploaded = latestUpload?.status === "completed" && Boolean(latestUpload.video_url);
            const hasRunningUpload = youtubeUploads.some((upload) => upload.status === "running");
            const queuePosition = latestUpload?.status === "queued"
              ? latestUpload.queue_position ?? null
              : null;
            const queueTotal = latestUpload?.status === "queued"
              ? latestUpload.queue_total ?? null
              : null;
            const processTurn = queuePosition === null
              ? null
              : queuePosition + (hasRunningUpload ? 1 : 0);
            const showLatestUploadStatus = Boolean(
              latestUpload && completedUploadStatusIsVisible(latestUpload, uploadStatusNow),
            );
            const cleanupCountdown = latestUpload
              ? uploadCleanupCountdown(latestUpload, uploadStatusNow)
              : null;
            const cleanupCountdownProgress = latestUpload
              ? uploadCleanupProgress(latestUpload, uploadStatusNow)
              : 0;
            const cleanupPending = cleanupCountdown !== null;
            const cleanupComplete = Boolean(latestUpload?.clip_deleted_at);
            const completedCleanupSteps = new Set(latestUpload?.clip_cleanup_completed_steps ?? []);
            const cleanupCurrentStep = latestUpload?.clip_cleanup_current_step ?? null;
            const cleanupStarted = Boolean(latestUpload?.clip_cleanup_started_at);
            const cleanupProgress = cleanupComplete
              ? 100
              : cleanupStarted
                ? Math.max(
                    12,
                    (completedCleanupSteps.size / CLEANUP_ITEMS.length) * 100,
                  )
                : cleanupCountdownProgress;
            const currentCleanupLabel = CLEANUP_ITEMS.find(
              (item) => item.id === cleanupCurrentStep,
            )?.label;
            const cleanupPanelVisible = cleanupPending || cleanupComplete;
            const cleanupTooltipId = latestUpload ? `cleanup-tooltip-${latestUpload.id}` : undefined;
            const rawUploadError = latestUpload?.error || latestUpload?.logs?.at(-1) || "";
            const uploadError = latestUpload?.status === "failed"
              ? friendlyYouTubeUploadError(rawUploadError, usesChromeDebugging)
              : "";
            const showSessionRecovery = youtubeUploadErrorNeedsSessionRepair(rawUploadError);
            const youtubeButtonTitle = youtubeEnabled
              ? isAlreadyUploaded
                ? `Sudah terupload ke YouTube${latestUpload.video_url ? `: ${latestUpload.video_url}` : ""}`
                : uploadError
                  ? `Upload ulang ke YouTube. Error terakhir: ${uploadError}`
                  : "Upload klip ini ke YouTube"
              : youtubeStatusMessage;

            return (
              <article
                className={`clipCard ${isLongForm ? "clipCardLongForm" : ""} ${clip.is_correct ? "clipCardCorrect" : ""} ${isSelected ? "selected" : ""}`}
                key={clip.url}
              >
                <div className="clipMedia">
                  <label className="clipSelect">
                    <input
                      aria-label={`Pilih ${title} untuk dihapus`}
                      checked={isSelected}
                      type="checkbox"
                      onChange={() => onToggleClipSelection(clip.url)}
                    />
                    <span>{isSelected ? "Dipilih" : "Pilih"}</span>
                  </label>
                  {clip.fyp_score !== null && clip.fyp_score !== undefined ? (
                    <span className={`clipScoreBadge fypScore-${fypScoreTone(clip.fyp_score)}`}>
                      <Sparkles size={14} />
                      {Math.round(clip.fyp_score)}
                    </span>
                  ) : null}
                  <video controls preload="metadata" src={url} />
                </div>
                <div className="clipInfo">
                  <div className="clipTitleBlock">
                    <span className="clipEyebrow">Klip siap posting</span>
                    <h3>{title}</h3>
                  </div>
                  <button
                    className="copyTitleButton"
                    type="button"
                    onClick={() => handleCopyTitle(title)}
                    title="Salin judul klip"
                  >
                    <Clipboard size={14} />
                    <span>Salin judul</span>
                  </button>
                </div>
                {clip.fyp_score !== null && clip.fyp_score !== undefined ? (
                  <>
                    <div className="clipMetrics">
                      <span className="clipMetric clipMetric--score">
                        <Sparkles size={13} />
                        FYP {Math.round(clip.fyp_score)}
                      </span>
                      {clip.key_point_score !== null && clip.key_point_score !== undefined ? (
                        <span className="clipMetric">Point {clip.key_point_score}</span>
                      ) : null}
                      {clip.loop_score !== null && clip.loop_score !== undefined ? (
                        <span className="clipMetric">Loop {clip.loop_score}</span>
                      ) : null}
                      {clip.output_resolution ? <span className="clipMetric">{clip.output_resolution}</span> : null}
                      {isLongForm && clip.thumbnail_url ? <span className="clipMetric">Thumbnail 16:9 siap</span> : null}
                    </div>
                    <details className="clipAnalysisDetails">
                      <summary>
                        <span className="detailsSummaryIcon">
                          <BarChart3 size={16} />
                        </span>
                        <span>
                          <strong>Analisis & perbaikan</strong>
                          <small>{clip.fyp_label || "Sudah dinilai"} · lihat detail kualitas klip</small>
                        </span>
                        <ChevronDown className="detailsChevron" size={18} />
                      </summary>
                      <div className="fypAnalysis">
                        {clip.hook ? (
                          <div className="analysisLine">
                            <Target size={15} />
                            <span><b>Hook:</b> {clip.hook}</span>
                          </div>
                        ) : null}
                        {clip.pov ? (
                          <div className="analysisLine">
                            <Video size={15} />
                            <span><b>POV:</b> {clip.pov}</span>
                          </div>
                        ) : null}
                        {clip.core_message ? (
                          <div className="analysisLine">
                            <Target size={15} />
                            <span><b>Intisari:</b> {clip.core_message}</span>
                          </div>
                        ) : null}
                        {clip.strengths?.length ? (
                          <div className="analysisBlock analysisStrength">
                            <b>Kekuatan</b>
                            <ul>{clip.strengths.slice(0, 3).map((item) => <li key={item}>{item}</li>)}</ul>
                          </div>
                        ) : null}
                        {clip.weaknesses?.length ? (
                          <div className="analysisBlock analysisWeakness">
                            <b>Temuan awal</b>
                            <ul>{clip.weaknesses.slice(0, 3).map((item) => <li key={item}>{item}</li>)}</ul>
                          </div>
                        ) : null}
                        {clip.applied_edits?.length ? (
                          <div className="analysisBlock analysisApplied">
                            <b><CheckCircle2 size={14} /> Perbaikan diterapkan</b>
                            <ul>{clip.applied_edits.map((item) => <li key={item}>{item}</li>)}</ul>
                          </div>
                        ) : null}
                        {clip.improvement_ideas?.length ? (
                          <div className="analysisBlock analysisIdea">
                            <div className="analysisIdeaHeader">
                              <b><Lightbulb size={14} /> Perlu tindakan manual</b>
                              <span>Belum otomatis</span>
                            </div>
                            <ol>{clip.improvement_ideas.slice(0, 3).map((item) => <li key={item}>{item}</li>)}</ol>
                          </div>
                        ) : null}
                      </div>
                    </details>
                  </>
                ) : null}
                <div className="clipCardFooter">
                  <label className="clipValidation">
                    <input
                      checked={clip.is_correct}
                      type="checkbox"
                      onChange={(event) => onToggleClipCorrect(clip, event.target.checked)}
                    />
                    <span>
                      <CheckCircle2 size={16} />
                      Hasil klip sudah benar
                    </span>
                  </label>
                  <div className="clipActions">
                    <a href={url} target="_blank" rel="noreferrer">
                      <ExternalLink size={16} />
                      <span>Buka klip</span>
                    </a>
                    <button type="button" className="clipDownloadButton" onClick={() => handleDownload(url, clip.name)}>
                      <Download size={16} />
                      <span>Unduh</span>
                    </button>
                    <button
                      type="button"
                      className="youtubeUploadButton"
                      onClick={() => onUploadClipToYouTube(clip)}
                      disabled={!youtubeEnabled || isUploadingToYouTube || isAlreadyUploaded}
                      title={youtubeButtonTitle}
                    >
                      <UploadCloud size={16} />
                      <span>
                        {isAlreadyUploaded
                          ? "Sudah YouTube"
                          : isUploadingToYouTube
                          ? "Mengupload..."
                          : latestUpload?.status === "failed"
                            ? "Ulangi YouTube"
                            : isLongForm
                              ? "Kirim + Thumbnail"
                              : "Kirim YouTube"}
                      </span>
                    </button>
                    <button className="clipDeleteButton" type="button" onClick={() => onDeleteClip(clip)}>
                      <Trash2 size={16} />
                      <span>Hapus</span>
                    </button>
                  </div>
                  {latestUpload && showLatestUploadStatus ? (
                    <div
                      aria-describedby={cleanupPanelVisible ? cleanupTooltipId : undefined}
                      aria-label={
                        cleanupComplete
                          ? "Upload YouTube selesai dan seluruh file lokal sudah terhapus."
                          : cleanupPending
                          ? `Upload YouTube selesai. File lokal akan dihapus otomatis dalam ${cleanupCountdown} detik.`
                          : undefined
                      }
                      className={`youtubeUploadStatus status-${latestUpload.status} ${cleanupPanelVisible ? "youtubeUploadStatus--cleanup isAutoOpen" : ""} ${cleanupComplete ? "isCleanupComplete" : ""}`}
                      tabIndex={cleanupPanelVisible ? 0 : undefined}
                    >
                      <UploadCloud size={14} />
                      <span className="youtubeUploadStatusText">
                        YouTube: {latestUpload.status}
                        {latestUpload.status === "completed" && latestUpload.visibility === "private"
                          ? " · tersimpan Private"
                          : null}
                        {isLongForm && latestUpload.thumbnail_url
                          ? latestUpload.thumbnail_attached
                            ? " · thumbnail terpasang"
                            : latestUpload.status === "running"
                              ? " · memasang thumbnail"
                              : " · thumbnail 16:9 siap"
                          : null}
                        {latestUpload.status === "queued" && queuePosition !== null
                          ? ` · antrean ${queuePosition} dari ${queueTotal ?? queuePosition}`
                          : null}
                        {latestUpload.status === "queued" && processTurn !== null
                          ? ` · giliran proses ke-${processTurn}`
                          : null}
                        {latestUpload.status === "completed"
                          ? latestUpload.clip_delete_error
                            ? cleanupCountdown && cleanupCountdown > 0
                              ? ` · retry hapus dalam ${cleanupCountdown} detik`
                              : " · mencoba ulang penghapusan file"
                            : cleanupPending
                              ? cleanupCountdown > 0
                                ? ` · cleanup bertahap selesai dalam ${cleanupCountdown} detik`
                                : " · sedang menghapus file..."
                              : cleanupComplete
                                ? " · semua file lokal terhapus"
                              : !latestUpload.video_url
                                ? " · file dipertahankan karena URL belum terverifikasi"
                                : null
                          : null}
                        {latestUpload.video_url ? (
                          <>
                            {" "}
                            · <a href={latestUpload.video_url} target="_blank" rel="noreferrer">buka</a>
                          </>
                        ) : null}
                      </span>
                      {latestUpload.status === "queued" && queuePosition !== null ? (
                        <span
                          className="queuePositionBadge"
                          title={`${queuePosition - 1} antrean menunggu di depan${hasRunningUpload ? ", 1 upload sedang diproses" : ""}`}
                        >
                          #{queuePosition}/{queueTotal ?? queuePosition}
                        </span>
                      ) : null}
                      {cleanupPanelVisible ? (
                        <>
                          <span className={`cleanupCountdownBadge ${cleanupCountdown === 0 ? "isDeleting" : ""} ${cleanupComplete ? "isComplete" : ""}`}>
                            {cleanupComplete ? (
                              <CheckCircle2 size={13} />
                            ) : cleanupCountdown === 0 ? (
                              <LoaderCircle className="spin" size={13} />
                            ) : (
                              <Clock3 size={13} />
                            )}
                            {cleanupComplete
                              ? "Terhapus"
                              : cleanupCountdown === 0
                                ? "Cleanup"
                                : `${cleanupCountdown}s`}
                          </span>
                          <Info className="cleanupInfoIcon" size={14} aria-hidden="true" />
                          <div
                            aria-live="polite"
                            className={`uploadCleanupTooltip ${cleanupComplete ? "isComplete" : ""}`}
                            id={cleanupTooltipId}
                            role="tooltip"
                          >
                            <div className="uploadCleanupTooltipHeader">
                              <span className="uploadCleanupTooltipIcon">
                                {cleanupComplete ? (
                                  <CheckCircle2 size={17} />
                                ) : cleanupCountdown === 0 ? (
                                  <LoaderCircle className="spin" size={17} />
                                ) : (
                                  <Trash2 size={17} />
                                )}
                              </span>
                              <span>
                                <strong>
                                  {cleanupComplete
                                    ? "Cleanup file lokal selesai"
                                    : currentCleanupLabel
                                      ? `Menghapus: ${currentCleanupLabel}`
                                    : cleanupCountdown === 0
                                    ? "Sedang membersihkan file lokal"
                                    : `Auto-cleanup bertahap · ${cleanupCountdown} detik`}
                                </strong>
                                <small>
                                  {cleanupComplete
                                    ? "Backend sudah mengonfirmasi seluruh file benar-benar terhapus."
                                    : "Upload dan URL YouTube sudah terverifikasi aman."}
                                </small>
                              </span>
                            </div>
                            <div className="uploadCleanupProgress" aria-hidden="true">
                              <span style={{ width: `${cleanupComplete ? 100 : cleanupProgress}%` }} />
                            </div>
                            <ul className="uploadCleanupSteps">
                              {CLEANUP_ITEMS.map((item) => {
                                const stepComplete = cleanupComplete || completedCleanupSteps.has(item.id);
                                const stepRunning = !stepComplete && cleanupCurrentStep === item.id;
                                const stepDetail = latestUpload.clip_cleanup_step_details?.[item.id];
                                return (
                                  <li
                                    className={stepComplete ? "isComplete" : stepRunning ? "isRunning" : "isWaiting"}
                                    key={item.id}
                                  >
                                    <span className="uploadCleanupStepIcon" aria-hidden="true">
                                      {stepComplete ? (
                                        <CheckCircle2 size={13} />
                                      ) : stepRunning ? (
                                        <LoaderCircle className="spin" size={12} />
                                      ) : (
                                        <Clock3 size={12} />
                                      )}
                                    </span>
                                    <span className="uploadCleanupStepCopy">
                                      <span>{item.label}</span>
                                      <small>
                                        {stepRunning
                                          ? "Sedang dieksekusi backend"
                                          : stepComplete && stepDetail?.duration_ms !== null
                                            && stepDetail?.duration_ms !== undefined
                                            ? `Selesai nyata · ${stepDetail.duration_ms} ms · ${stepDetail.removed_items} item`
                                            : stepComplete
                                              ? "Selesai dan terverifikasi backend"
                                              : "Menunggu giliran backend"}
                                      </small>
                                    </span>
                                  </li>
                                );
                              })}
                            </ul>
                            <p>
                              {cleanupComplete
                                ? "Semua checklist terkonfirmasi. Card akan ditutup otomatis."
                                : "Jika penghapusan gagal, backend akan retry otomatis tanpa menghapus video YouTube."}
                            </p>
                          </div>
                        </>
                      ) : null}
                    </div>
                  ) : null}
                  {latestUpload?.status === "failed" && uploadError ? (
                    <div className="youtubeUploadError" title={uploadError}>
                      <strong>Upload gagal</strong>
                      <span>{uploadError}</span>
                      {showSessionRecovery ? (
                        <>
                          <button type="button" onClick={onSetupYouTubeOneTimeLogin} disabled={isYouTubeLoginActive}>
                            <RefreshCw size={14} />
                            <span>{isYouTubeLoginActive ? openStudioWaitingLabel : "Login Sekali"}</span>
                          </button>
                          <button type="button" onClick={onCaptureYouTubeSession}>
                            <RefreshCw size={14} />
                            <span>{usesChromeDebugging ? "CDP Opsional" : "Sync Session Browser"}</span>
                          </button>
                          {usesChromeDebugging ? (
                            <>
                              <button type="button" onClick={onImportYouTubeCdpCookies}>
                                <Download size={14} />
                                <span>Ambil Cookies</span>
                              </button>
                              <button type="button" onClick={onEnableNoCdpMode}>
                                <Settings2 size={14} />
                                <span>Tanpa CDP</span>
                              </button>
                            </>
                          ) : null}
                        </>
                      ) : null}
                    </div>
                  ) : null}
                </div>
                <ThumbnailPrompt clip={clip} />
              </article>
            );
          })}
        </div>
      ) : (
        <div className="emptyState">
          <Video className="emptyStateIcon" size={32} />
          <p>Klip vertikal 9:16 yang selesai diproses akan muncul di sini.</p>
        </div>
      )}
    </section>
  );
}
