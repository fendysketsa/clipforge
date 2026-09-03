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
const RELIGIOUS_REVIEW_LABELS: Record<string, string> = {
  compare_clip_with_source_context: "Bandingkan clip dengan konteks sumber",
  verify_quran_or_hadith_reference_and_wording: "Periksa rujukan dan redaksi ayat/hadis",
  verify_ruling_scope_conditions_and_exceptions: "Periksa batas, syarat, dan pengecualian hukum",
  confirm_clip_does_not_reverse_the_speaker_meaning: "Pastikan potongan tidak membalik maksud pembicara",
  confirm_audio_visual_and_music_rights: "Pastikan hak audio, visual, dan musik",
  review_private_upload_in_youtube_checks: "Periksa hasil Private melalui YouTube Checks",
};

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
  onRepairClip: (clip: ClipFile) => void;
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

function youtubeRunningStage(upload: YouTubeUploadJob) {
  if (upload.status !== "running") return "";
  const recent = [...(upload.logs ?? [])].reverse();
  for (const line of recent) {
    if (/modal upload sudah tertutup|menunggu konfirmasi final transfer/i.test(line)) {
      return "verifikasi hasil upload";
    }
    if (/masuk ke tab visibilitas|mengatur visibilitas|step 4 visibilitas/i.test(line)) return "finalisasi Private";
    if (/copyright sudah aman|checks masih berjalan|menunggu youtube studio checks/i.test(line)) {
      return "pemeriksaan copyright/komunitas";
    }
    if (/playlist/i.test(line)) return "verifikasi playlist";
    if (/thumbnail/i.test(line)) return "verifikasi thumbnail";
    if (/subtitle|elemen video/i.test(line)) return "subtitle & elemen video";
    if (/file.*dipilih|mengunggah|upload.*dimulai/i.test(line)) return "transfer video";
  }
  return "menyiapkan YouTube Studio";
}

function fypScoreTone(score: number) {
  if (score >= 88) return "excellent";
  if (score >= 80) return "strong";
  if (score >= 65) return "promising";
  return "polish";
}

function growthTargetReadiness(
  score: number,
  isLongForm: boolean,
  targetViews = 5000,
  targetSubscribers = 20,
  nextAction?: string | null,
  status?: string | null,
) {
  const target = `Target ${(targetViews / 1000).toLocaleString("id-ID", { maximumFractionDigits: 1 })}K / ${targetSubscribers} sub`;
  if (status?.startsWith("revise")) {
    return {
      label: `${target} · poles dulu`,
      tone: "hold",
      detail: nextAction || "Quality gate cerita belum lolos; perbaiki output sebelum publikasi.",
    };
  }
  if (status === "test_hook_variant_first") {
    return {
      label: isLongForm ? `${target} · A/B packaging` : `${target} · uji hook`,
      tone: "test",
      detail: nextAction || "Ubah satu variabel, lalu bandingkan dengan upload seformat dan seseri.",
    };
  }
  if (score >= 88) {
    return {
      label: `${target} · siap uji`,
      tone: "excellent",
      detail: nextAction || (isLongForm
        ? "Hook, alur, dan packaging sudah kuat; publikasikan Private dulu lalu cek thumbnail, judul, dan retention 30 detik."
        : "Hook dan payoff sudah kuat; publikasikan Private dulu, buka Edit thumbnail di aplikasi YouTube dan geser ke frame cover awal sekitar 0,78 detik—jangan mengandalkan pilihan otomatis tengah—lalu ukur engaged views, chose-to-view, dan subscriber yang dihasilkan."),
    };
  }
  if (score >= 80) {
    return {
      label: `${target} · layak uji`,
      tone: "strong",
      detail: nextAction || (isLongForm
        ? "Layak diuji sebagai long-form. Pantau impressions, CTR Beranda/Disarankan, retention 30 detik, average view duration, dan subscriber."
        : "Layak dipublikasikan sebagai eksperimen. Pantau engaged views, chose-to-view, retention, shares, dan subscriber; angka view tetap ditentukan respons penonton."),
    };
  }
  if (score >= 65) {
    return {
      label: isLongForm ? `${target} · A/B packaging` : `${target} · uji hook`,
      tone: "test",
      detail: nextAction || (isLongForm
        ? "Uji judul/thumbnail lewat fitur A/B YouTube setelah video siap; perbaiki juga temuan di bawah."
        : "Coba satu varian hook secara berurutan—fitur A/B native YouTube tidak tersedia untuk Shorts—lalu bandingkan respons penonton."),
    };
  }
  return {
    label: `${target} · poles dulu`,
    tone: "hold",
    detail: nextAction || "Belum disarankan untuk mengejar distribusi. Pilih kandidat lain atau perkuat hook, tempo, dan payoff.",
  };
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
  onRepairClip,
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
                    ? `Upload ${Math.min(youtubeAutoUploadCount, clips.length)} klip terbaik sebagai Private dengan pemeriksaan nol-klaim`
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
              || clip.name.toLowerCase().startsWith("resume_cerita_")
              || clip.name.toLowerCase().startsWith("long_animate_");
            const growthReadiness = clip.fyp_score !== null && clip.fyp_score !== undefined
              ? growthTargetReadiness(
                  clip.fyp_score,
                  isLongForm,
                  clip.growth_target_views || (isLongForm ? 5000 : 20000),
                  clip.growth_target_subscribers || 20,
                  clip.growth_next_action,
                  clip.growth_status,
                )
              : null;
            const passesGrowthGate = typeof clip.growth_quality_gate_passed === "boolean"
              ? clip.growth_quality_gate_passed
              : isLongForm || (typeof clip.fyp_score === "number" && clip.fyp_score >= 80);
            const meetsFypTarget = isLongForm
              || typeof clip.fyp_score !== "number"
              || clip.fyp_score >= 80;
            const isUploadReady = passesGrowthGate
              && meetsFypTarget
              && !clip.context_recut_required
              && clip.youtube_upload_ready !== false;
            const needsAutomaticRepair = Boolean(clip.automatic_repair_available);
            const uploadReviewConfirmed = clip.is_correct;
            const isQueuedForYouTube = latestUpload?.status === "queued";
            const isRunningYouTubeUpload = latestUpload?.status === "running";
            const isUploadingToYouTube = isQueuedForYouTube || isRunningYouTubeUpload;
            const isAlreadyUploaded = latestUpload?.status === "completed" && Boolean(latestUpload.video_url);
            const hasRunningUpload = youtubeUploads.some((upload) => upload.status === "running");
            const runningStage = latestUpload ? youtubeRunningStage(latestUpload) : "";
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
            const thumbnailWasSkipped = Boolean(
              latestUpload?.logs?.some((line) => line.startsWith("THUMBNAIL_SKIPPED")),
            );
            const thumbnailDailyLimitWasReached = Boolean(
              latestUpload?.logs?.some((line) => line.startsWith("THUMBNAIL_SKIPPED_DAILY_LIMIT:")),
            );
            const uploadError = latestUpload?.status === "failed"
              ? friendlyYouTubeUploadError(rawUploadError, usesChromeDebugging)
              : "";
            const showSessionRecovery = youtubeUploadErrorNeedsSessionRepair(rawUploadError);
            const youtubeButtonTitle = youtubeEnabled
              ? !isUploadReady
                ? clip.youtube_upload_issue
                  || "Upload ditahan: output belum lolos quality gate formatnya. Buka Analisis & perbaikan, lalu render ulang."
                : !uploadReviewConfirmed
                  ? "Centang review hasil, fakta, dan hak penggunaan sebelum upload Private."
                : isAlreadyUploaded
                ? `Sudah terupload ke YouTube${latestUpload.video_url ? `: ${latestUpload.video_url}` : ""}`
                : isQueuedForYouTube
                  ? "Klip sedang menunggu giliran upload YouTube."
                  : isRunningYouTubeUpload
                    ? "Upload sedang diproses dan diverifikasi oleh YouTube Studio."
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
                    <span className="clipEyebrow">
                      {clip.context_recut_required
                        ? "Perlu perbaikan batas konteks"
                        : needsAutomaticRepair
                          ? "Perlu perbaikan editorial"
                        : isUploadReady
                          ? "Klip siap review Private"
                          : "Ditahan quality gate"}
                    </span>
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
                      {growthReadiness ? (
                        <span
                          className={`clipMetric clipMetric--growth clipMetric--growth-${growthReadiness.tone}`}
                          title="Indikator kesiapan eksperimen, bukan jaminan jumlah view."
                        >
                          <Target size={13} />
                          {growthReadiness.label}
                        </span>
                      ) : null}
                      {clip.key_point_score !== null && clip.key_point_score !== undefined ? (
                        <span className="clipMetric">Point {clip.key_point_score}</span>
                      ) : null}
                      {clip.loop_score !== null && clip.loop_score !== undefined ? (
                        <span className="clipMetric">Loop {clip.loop_score}</span>
                      ) : null}
                      {clip.retention_score !== null && clip.retention_score !== undefined ? (
                        <span
                          className="clipMetric"
                          title="Skor kesiapan editorial 30 detik pertama, bukan prediksi retention penonton."
                        >
                          Retention-ready {clip.retention_score}
                        </span>
                      ) : null}
                      {clip.narrative_arc_score !== null && clip.narrative_arc_score !== undefined ? (
                        <span
                          className="clipMetric"
                          title="Audit urutan hook, konteks, konflik, jawaban, dan ending kuat."
                        >
                          Narasi {clip.narrative_arc_score}{clip.narrative_arc_complete ? " ✓" : ""}
                        </span>
                      ) : null}
                      {clip.context_recut_required ? (
                        <span
                          className="clipMetric clipMetric--blocked"
                          title="Audit final menemukan ucapan atau makna yang masih menggantung."
                        >
                          Potong ulang wajib
                        </span>
                      ) : clip.religious_context_safe === true ? (
                        <span
                          className="clipMetric"
                          title="Batas otomatis memastikan kalimat kajian tidak dimulai atau diakhiri menggantung; verifikasi sumber tetap diperlukan."
                        >
                          Konteks kajian aman
                        </span>
                      ) : null}
                      {clip.output_resolution ? <span className="clipMetric">{clip.output_resolution}</span> : null}
                      {clip.auditor_name && clip.audit_id ? (
                        <span className="clipMetric" title={`Audit editorial otomatis ${clip.audit_id}`}>
                          FENDY AUDIT
                        </span>
                      ) : null}
                      {clip.growth_series ? <span className="clipMetric">Seri: {clip.growth_series}</span> : null}
                      {clip.subscriber_intent_score !== null
                        && clip.subscriber_intent_score !== undefined ? (
                        <span className="clipMetric">Potensi sub {clip.subscriber_intent_score}</span>
                      ) : null}
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
                        {growthReadiness ? (
                          <div className={`viewTargetReadiness viewTargetReadiness--${growthReadiness.tone}`}>
                            <Target size={15} />
                            <span><b>{growthReadiness.label}.</b> {growthReadiness.detail} Ini indikator kesiapan, bukan jaminan view.</span>
                          </div>
                        ) : null}
                        {clip.religious_review_required ? (
                          <div className="analysisBlock analysisIdea">
                            <div className="analysisIdeaHeader">
                              <b><Info size={14} /> Review konteks kajian wajib</b>
                              <span>
                                Risiko {clip.religious_review_risk || "medium"} · {clip.religious_claim_count || 0} klaim
                              </span>
                            </div>
                            {clip.source_context_before ? (
                              <p><b>Sebelum clip:</b> {clip.source_context_before}</p>
                            ) : null}
                            {clip.source_context_after ? (
                              <p><b>Sesudah clip:</b> {clip.source_context_after}</p>
                            ) : null}
                            <ol>
                              {(clip.religious_review_checks || []).map((item) => (
                                <li key={item}>{RELIGIOUS_REVIEW_LABELS[item] || item.replaceAll("_", " ")}</li>
                              ))}
                            </ol>
                          </div>
                        ) : null}
                        {clip.growth_checkpoints?.length ? (
                          <div className="analysisLine">
                            <BarChart3 size={15} />
                            <span><b>Checkpoint review:</b> {clip.growth_checkpoints.map((item) => item.toLocaleString("id-ID")).join(" → ")} views</span>
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
                  {clip.context_recut_required || needsAutomaticRepair ? (
                    <div className="clipRepairNotice">
                      <Info size={16} />
                      <span>
                        {clip.context_recut_required
                          ? "Audit final menemukan batas kalimat atau makna kajian belum utuh. Buat versi aman sebelum review dan upload."
                          : clip.youtube_upload_issue
                            || "Audit transformasi editorial belum lolos. Render ulang klip ini sebelum upload."}
                      </span>
                    </div>
                  ) : null}
                  <label className="clipValidation">
                    <input
                      checked={clip.context_recut_required ? false : clip.is_correct}
                      type="checkbox"
                      disabled={clip.context_recut_required}
                      onChange={(event) => onToggleClipCorrect(clip, event.target.checked)}
                    />
                    <span>
                      <CheckCircle2 size={16} />
                      {clip.religious_review_required
                        ? "Konteks, rujukan agama, fakta, dan hak penggunaan sudah saya review"
                        : "Hasil, fakta, dan hak penggunaan sudah saya review"}
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
                    {needsAutomaticRepair || clip.context_recut_required ? (
                      <button
                        type="button"
                        className="clipRepairButton"
                        onClick={() => onRepairClip(clip)}
                        disabled={isUploadingToYouTube}
                        title="Render ulang hanya MP4 klip ini dengan perbaikan editorial otomatis"
                      >
                        <Sparkles size={16} />
                        <span>Perbaiki Otomatis</span>
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="youtubeUploadButton"
                        onClick={() => onUploadClipToYouTube(clip)}
                        disabled={!youtubeEnabled || !isUploadReady || !uploadReviewConfirmed || isUploadingToYouTube || isAlreadyUploaded}
                        title={youtubeButtonTitle}
                      >
                        <UploadCloud size={16} />
                        <span>
                          {!isUploadReady
                            ? "Quality gate · Ditahan"
                            : isAlreadyUploaded
                              ? "Sudah YouTube"
                              : isQueuedForYouTube
                                ? "Menunggu antrean"
                                : isRunningYouTubeUpload
                                  ? "Mengupload..."
                                  : latestUpload?.status === "failed"
                                    ? "Ulangi YouTube"
                                    : isLongForm
                                      ? "Kirim + Thumbnail"
                                      : "Kirim YouTube"}
                        </span>
                      </button>
                    )}
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
                        {runningStage ? ` · ${runningStage}` : null}
                        {latestUpload.status === "completed" && latestUpload.visibility === "private"
                          ? " · tersimpan Private"
                          : null}
                        {latestUpload.playlist
                          ? latestUpload.playlist_confirmed
                            ? ` · playlist ${latestUpload.playlist} terverifikasi`
                            : latestUpload.status === "running"
                              ? ` · mencari playlist ${latestUpload.playlist}`
                              : null
                          : null}
                        {latestUpload.thumbnail_url
                          ? latestUpload.thumbnail_attached
                            ? " · thumbnail terpasang"
                            : latestUpload.status === "running"
                              ? isLongForm
                                ? " · memasang thumbnail"
                                : " · mencoba thumbnail Shorts"
                              : thumbnailWasSkipped
                                ? thumbnailDailyLimitWasReached
                                  ? " · thumbnail otomatis YouTube (kuota kustom harian tercapai)"
                                  : " · thumbnail dilewati oleh Studio"
                                : isLongForm
                                  ? " · thumbnail 16:9 siap"
                                  : null
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
