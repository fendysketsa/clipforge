import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Clipboard,
  Clock3,
  Download,
  ExternalLink,
  Image as ImageIcon,
  Info,
  LoaderCircle,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Sparkles,
  Target,
  Trash2,
  UploadCloud,
  Video,
} from "lucide-react";
import { useEffect, useState } from "react";
import { getOutputUrl, getLongProductionStatus } from "../../lib/apiClient";
import { longAutomationForClip, type LongProductionSnapshot } from "../../lib/longAutomation";
import { VIRAL_QUALITY_FLOOR } from "../../lib/constants";
import { clipDisplayTitle, handleCopyTitle, handleDownload } from "../../lib/utils";
import type { ClipFile, ClipJob, TikTokUploadJob, YouTubeUploadJob } from "../../types/clip.type";
import { uploadQueuePosition } from "../../lib/uploadQueue";
import { tiktokAutomaticRetryLabel, tiktokUploadForClip } from "../../lib/tiktokRetry";

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
  jobs: ClipJob[];
  selectedClipUrls: string[];
  youtubeEnabled: boolean;
  youtubeStatusMessage: string;
  youtubeAutoUploadCount: number;
  youtubeUploadAllAboveTarget: boolean;
  youtubeUploads: YouTubeUploadJob[];
  tiktokEnabled: boolean;
  tiktokStatusMessage: string;
  tiktokTargetHandle: string;
  tiktokAutoUploadCount: number;
  tiktokUploads: TikTokUploadJob[];
  isTikTokLoginActive: boolean;
  isYouTubeLoginActive: boolean;
  onDeleteAllClips: () => void;
  onDeleteClip: (clip: ClipFile) => void;
  onDeleteSelectedClips: () => void;
  onDeleteYouTubeUpload: (upload: YouTubeUploadJob) => Promise<void>;
  onCaptureYouTubeSession: () => void;
  onCheckTikTokSession: () => void;
  onEnableNoCdpMode: () => void;
  onImportYouTubeCdpCookies: () => void;
  onSetupYouTubeOneTimeLogin: () => void;
  onStartYouTubeLogin: () => void;
  onStartTikTokLogin: () => void;
  onUploadAllToYouTube: () => void;
  onUploadAllToTikTok: () => void;
  onUploadClipToYouTube: (clip: ClipFile) => void;
  onUploadClipToTikTok: (clip: ClipFile) => void;
  onToggleAllClipSelection: () => void;
  onToggleClipSelection: (clipUrl: string) => void;
  onToggleClipCorrect: (clip: ClipFile, isCorrect: boolean) => void;
};

function friendlyYouTubeUploadError(message: string, usesChromeDebugging: boolean) {
  const clean = message.trim();
  const lowered = clean.toLowerCase();
  if (lowered.includes("kebijakan nol-klaim") || lowered.includes("klaim content id")) {
    return "YouTube menemukan klaim Content ID. Klip dan catatan gagal dihapus otomatis; ClipForge langsung mencari sumber baru dan membuat antrean pengganti.";
  }
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

function friendlyTikTokUploadError(message: string, visibility?: "only_you" | "public") {
  const clean = message.trim();
  const lowered = clean.toLowerCase();
  if (lowered.includes("kontrol privasi tiktok") || lowered.includes("pilihan privasi tiktok")) {
    return `File sudah masuk ke form. Job meminta ${visibility === "public" ? "Everyone" : "Only you"}, tetapi pilihan itu belum terverifikasi. Post belum dikirim.`;
  }
  if (
    lowered.includes("transfer file cdp tiktok gagal sebelum posting")
    || (lowered.includes("set_input_files") && lowered.includes("tidak dapat menerima file video"))
  ) {
    return "Transfer video ke Chrome macet sebelum diposting. Klik Ulangi TikTok; uploader akan menyiapkan file yang lebih ringan dan beralih ke session tersimpan bila perlu.";
  }
  if (lowered.includes("tombol post tiktok belum siap")) {
    return "Pemrosesan video TikTok belum selesai. Klik Ulangi TikTok; uploader akan menunggu sampai tombol Post aktif.";
  }
  if (lowered.includes("connect_over_cdp") && lowered.includes("timeout")) {
    return "Koneksi ke Chrome TikTok macet. Coba ulang; uploader akan memakai session tersimpan sebagai cadangan.";
  }
  if (lowered.includes("connect_over_cdp") || lowered.includes("econnrefused")) {
    return "Chrome TikTok tidak dapat dihubungi. Klik Cek sesi TikTok, lalu coba ulang.";
  }
  return clean;
}

function isTikTokFileTransferError(message?: string | null) {
  const lowered = message?.toLowerCase() || "";
  return lowered.includes("transfer file cdp tiktok gagal sebelum posting")
    || (lowered.includes("set_input_files") && lowered.includes("tidak dapat menerima file video"));
}

function tiktokUploadErrorNeedsSessionRepair(message?: string | null) {
  const lowered = message?.toLowerCase() || "";
  return [
    "sesi tiktok belum login",
    "tiktok meminta login ulang",
    "session tiktok sudah habis",
    "sesi sudah habis",
    "akun browser aktif",
    "akun browser bukan pemilik",
    "connect_over_cdp",
    "econnrefused",
  ].some((marker) => lowered.includes(marker));
}

function displayTikTokSeriesLabel(label?: string | null, fallback?: string | null) {
  const clean = label?.trim() || "";
  if (clean === "Jawaban Ustadz 30 Detik") return fallback?.trim() || "Kajian Islam Ringkas";
  if (clean === "Kesalahan Ibadah Sehari-hari") return "Panduan Ibadah";
  if (clean === "Nasihat yang Sering Disalahpahami") return "Nasihat & Hikmah";
  return clean;
}

const QC_CHECK_LABELS: Record<string, string> = {
  verify_source_rights_and_permission_evidence: "Verifikasi hak sumber dan bukti izin",
  review_factual_and_religious_context: "Periksa fakta dan konteks keagamaan",
  watch_final_render_for_caption_crop_audio_and_timing: "Tonton render final: caption, crop, audio, dan timing",
  review_title_thumbnail_and_ad_suitability: "Periksa judul, thumbnail, dan kelayakan iklan",
  upload_private_then_complete_platform_checks: "Upload Private lalu selesaikan pemeriksaan platform",
};

function qcCheckLabel(value: string) {
  return QC_CHECK_LABELS[value] || value.replaceAll("_", " ");
}

function tiktokRunningStage(upload: TikTokUploadJob) {
  if (upload.status !== "running") return "";
  const recent = [...(upload.logs ?? [])].reverse();
  for (const line of recent) {
    if (/memeriksa daftar posts|post_submission_ack/i.test(line)) return "memverifikasi daftar Posts";
    if (/post_api_accepted|menerima proses posting/i.test(line)) return "TikTok menerima posting";
    if (/tombol post diklik|post_confirmation_dialog/i.test(line)) return "mengirim permintaan Post";
    if (/menunggu pemrosesan video|tombol post/i.test(line)) return "menunggu video siap diposting";
    if (/caption/i.test(line)) return "mengisi caption";
    if (/mengirim .* melalui transfer|video dipilih/i.test(line)) return "mentransfer video";
    if (/disiapkan menjadi/i.test(line)) return "menyiapkan file ringan";
    if (/target_account_confirmed|session_saved/i.test(line)) return "memeriksa akun TikTok";
  }
  return "menyiapkan TikTok Studio";
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
  if (score >= VIRAL_QUALITY_FLOOR) return "strong";
  return "polish";
}

function growthTargetReadiness(
  score: number,
  isLongForm: boolean,
  targetViews = 5000,
  targetSubscribers = 20,
  nextAction?: string | null,
  status?: string | null,
  manualPrivateReviewReady = false,
) {
  const target = `Target ${(targetViews / 1000).toLocaleString("id-ID", { maximumFractionDigits: 1 })}K / ${targetSubscribers} sub`;
  if (!manualPrivateReviewReady) {
    return {
      label: `${target} · upload ditahan`,
      tone: "hold",
      detail: nextAction || "Pengiriman menunggu hasil pemeriksaan klip.",
    };
  }
  if (status?.startsWith("revise")) {
    if (manualPrivateReviewReady) {
      return {
        label: `${target} · review manual`,
        tone: "test",
        detail: "Aman masuk review Private setelah checklist manusia; target growth belum lolos untuk auto-upload batch.",
      };
    }
    return {
      label: `${target} · poles dulu`,
      tone: "hold",
      detail: nextAction || "Quality gate cerita belum lolos; perbaiki output sebelum publikasi.",
    };
  }
  if (status === "test_hook_variant_first" && score >= VIRAL_QUALITY_FLOOR) {
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
  if (score >= VIRAL_QUALITY_FLOOR) {
    return {
      label: `${target} · layak uji`,
      tone: "strong",
      detail: nextAction || (isLongForm
        ? "Layak diuji sebagai long-form. Pantau impressions, CTR Beranda/Disarankan, retention 30 detik, average view duration, dan subscriber."
        : "Layak dipublikasikan sebagai eksperimen. Pantau engaged views, chose-to-view, retention, shares, dan subscriber; angka view tetap ditentukan respons penonton."),
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
  jobs,
  selectedClipUrls,
  youtubeEnabled,
  youtubeStatusMessage,
  youtubeAutoUploadCount,
  youtubeUploadAllAboveTarget,
  youtubeUploads,
  tiktokEnabled,
  tiktokStatusMessage,
  tiktokTargetHandle,
  tiktokAutoUploadCount,
  tiktokUploads,
  isTikTokLoginActive,
  isYouTubeLoginActive,
  onDeleteAllClips,
  onDeleteClip,
  onDeleteSelectedClips,
  onDeleteYouTubeUpload,
  onCaptureYouTubeSession,
  onCheckTikTokSession,
  onEnableNoCdpMode,
  onImportYouTubeCdpCookies,
  onSetupYouTubeOneTimeLogin,
  onStartYouTubeLogin,
  onStartTikTokLogin,
  onUploadAllToYouTube,
  onUploadAllToTikTok,
  onUploadClipToYouTube,
  onUploadClipToTikTok,
  onToggleAllClipSelection,
  onToggleClipSelection,
  onToggleClipCorrect,
}: ResultsSectionProps) {
  const [uploadStatusNow, setUploadStatusNow] = useState(() => Date.now());
  const [longProduction, setLongProduction] = useState<LongProductionSnapshot | null>(null);
  const hasLongOutput = clips.some(clip => /^(resume_cerita_|highlight_5menit_|long_animate_)/i.test(clip.name));
  const jakartaDay = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Jakarta", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
  const allClipsHeldByLongQc = clips.length > 0 && clips.every(clip => longAutomationForClip(clip.url, longProduction, jobs, jakartaDay)?.hold);
  useEffect(() => {
    if (!hasLongOutput) return;
    let disposed = false;
    const refresh = () => getLongProductionStatus()
      .then(value => { if (!disposed) setLongProduction(value); })
      .catch(() => undefined);
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, 10_000);
    return () => { disposed = true; window.clearInterval(timer); };
  }, [hasLongOutput]);
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
          <p>Review, unduh, atau kirim Private ke YouTube dan Only you ke TikTok.</p>
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
                disabled={!youtubeEnabled || allClipsHeldByLongQc}
                title={
                  youtubeEnabled
                    ? youtubeUploadAllAboveTarget
                      ? `Upload semua klip dengan skor FYP ≥80 sebagai Private dengan pemeriksaan nol-klaim`
                      : `Upload ${Math.min(youtubeAutoUploadCount, clips.length)} klip terbaik sebagai Private dengan pemeriksaan nol-klaim`
                    : youtubeStatusMessage
                }
              >
                <UploadCloud size={16} />
                <span>
                  {youtubeUploadAllAboveTarget
                    ? "Upload semua ≥80"
                    : `Upload ${Math.min(youtubeAutoUploadCount, clips.length)} terbaik`}
                </span>
              </button>
              <button
                type="button"
                onClick={tiktokEnabled ? onUploadAllToTikTok : onStartTikTokLogin}
                className="uiButton uiButton--tiktok"
                disabled={isTikTokLoginActive}
                aria-label={tiktokEnabled
                  ? `Upload ${Math.min(tiktokAutoUploadCount, clips.length)} clip terbaik ke @${tiktokTargetHandle} sebagai Only you`
                  : tiktokStatusMessage}
              >
                {tiktokEnabled ? <UploadCloud size={16} /> : <ExternalLink size={16} />}
                <span>
                  {tiktokEnabled
                    ? `TikTok ${Math.min(tiktokAutoUploadCount, clips.length)} terbaik`
                    : isTikTokLoginActive
                      ? "Menunggu login TikTok..."
                      : "Login TikTok"}
                </span>
              </button>
              <button type="button" onClick={onDeleteAllClips} className="uiButton uiButton--ghostDanger">
                <Trash2 size={16} />
                <span>Hapus semua</span>
              </button>
            </>
          ) : null}
        </div>
      </div>

      {clips.length ? (
        <div className="clipGrid">
          {clips.map((originalClip) => {
            const longAutomation = longAutomationForClip(originalClip.url, longProduction, jobs, jakartaDay);
            const clip = longAutomation?.hold ? { ...originalClip,
              youtube_upload_ready: false, youtube_upload_issue: longAutomation.reason,
              tiktok_upload_issue: longAutomation.reason, production_qc_brief: longAutomation.reason,
              automatic_repair_available: false,
            } : originalClip;
            const title = clipDisplayTitle(clip);
            const url = getOutputUrl(clip.url);
            const isSelected = selectedClipUrls.includes(clip.url);
            const latestUpload = youtubeUploads.find((upload) => upload.clip_url === clip.url);
            const tiktokState = tiktokUploadForClip(tiktokUploads, clip.url);
            const latestTikTokUpload = tiktokState.latest;
            const tiktokSeriesLabel = displayTikTokSeriesLabel(
              clip.tiktok_series_label,
              clip.growth_series,
            );
            const uploadTikTokSeriesLabel = displayTikTokSeriesLabel(
              latestTikTokUpload?.series_label,
              tiktokSeriesLabel,
            );
            const isLongForm = clip.name.toLowerCase().startsWith("highlight_5menit_")
              || clip.name.toLowerCase().startsWith("resume_cerita_")
              || clip.name.toLowerCase().startsWith("long_animate_");
            const outputDimensions = clip.output_resolution?.match(/^(\d+)x(\d+)$/i);
            const isPortraitOutput = Boolean(
              outputDimensions
              && Number(outputDimensions[2]) > Number(outputDimensions[1]),
            );
            const thumbnailVariants = (clip.thumbnail_variants?.length
              ? clip.thumbnail_variants
              : clip.thumbnail_url
                ? [clip.thumbnail_url]
                : []
            ).slice(0, 3);
            // Growth/FYP is an experiment-ranking signal, not a safety or
            // rights rule. The backend preflight owns upload eligibility and
            // may explicitly allow a reviewed quality-only fallback into the
            // Private-first workflow while keeping automatic batch upload
            // strict.
            const isUploadReady = !clip.context_recut_required
              && clip.youtube_upload_ready !== false;
            const growthReadiness = clip.fyp_score !== null && clip.fyp_score !== undefined
              ? growthTargetReadiness(
                  clip.fyp_score,
                  isLongForm,
                  clip.growth_target_views || (isLongForm ? 5000 : 20000),
                  clip.growth_target_subscribers || 20,
                  clip.growth_next_action,
                  clip.growth_status,
                  isUploadReady,
                )
              : null;
            const meetsFypTarget = isLongForm
              || typeof clip.fyp_score !== "number"
              || clip.fyp_score >= VIRAL_QUALITY_FLOOR;
            const automaticRepairDidNotPass = Boolean(clip.automatic_repair_available);
            const renderQcWarning = clip.render_qc_passed === false && clip.render_qc_blocking === false;
            const renderQcHold = clip.render_qc_blocking === true
              || (clip.render_qc_passed === false && !renderQcWarning);
            const automaticQcState = clip.context_recut_required
              || renderQcHold
              || clip.youtube_upload_ready === false
              ? "hold"
              : clip.render_qc_passed === true && clip.youtube_upload_ready === true
                ? "passed"
                : "pending";
            const automaticQcChecks = [
              {
                label: "Render visual",
                detail: renderQcWarning
                  ? "Catatan visual; tidak memblokir upload. Lihat peringatan QC."
                  : clip.render_qc_status === "review_required"
                  ? "Perlu pemeriksaan visual"
                  : clip.render_qc_status || "Belum ada hasil render QC",
                state: clip.render_qc_passed === true
                  ? "passed"
                  : renderQcHold
                    ? "failed"
                    : "pending",
              },
              {
                label: "Keutuhan konteks",
                detail: clip.context_recut_required
                  ? "Batas kalimat atau makna perlu dipotong ulang"
                  : clip.religious_context_safe === true
                    ? "Konteks sumber tetap utuh"
                    : clip.religious_context_safe === false
                      ? "Konteks sumber belum aman"
                      : "Menunggu data audit konteks",
                state: clip.context_recut_required || clip.religious_context_safe === false
                  ? "failed"
                  : clip.religious_context_safe === true
                    ? "passed"
                    : "pending",
              },
              {
                label: "Gate upload Private",
                detail: clip.youtube_upload_ready === true
                  ? "Lolos untuk tahap review Private"
                  : clip.youtube_upload_ready === false
                    ? clip.youtube_upload_issue || "Ditahan oleh quality gate"
                    : "Belum ada keputusan quality gate",
                state: clip.youtube_upload_ready === true
                  ? "passed"
                  : clip.youtube_upload_ready === false
                    ? "failed"
                    : "pending",
              },
            ] as const;
            const uploadReviewConfirmed = clip.is_correct;
            const isQueuedForYouTube = latestUpload?.status === "queued";
            const isRunningYouTubeUpload = latestUpload?.status === "running";
            const isUploadingToYouTube = isQueuedForYouTube || isRunningYouTubeUpload;
            const isAlreadyUploaded = latestUpload?.status === "completed" && Boolean(latestUpload.video_url);
            const youtubeClaimWasDetected = Boolean(
              latestUpload?.logs?.some((line) => line.startsWith("CLAIMED_UPLOAD_ABORTED:")),
            );
            const isUploadingToTikTok = latestTikTokUpload?.status === "queued" || latestTikTokUpload?.status === "running";
            const hasPendingTikTokPost = tiktokState.uncertain && !isUploadingToTikTok;
            const tiktokPrivacyPending = latestTikTokUpload?.status === "failed" && Boolean(latestTikTokUpload.error?.toLowerCase().includes("privasi tiktok"));
            const isAlreadyOnTikTok = latestTikTokUpload?.status === "completed" && latestTikTokUpload.upload_confirmed;
            const shouldRetryTikTokUpload = isTikTokFileTransferError(latestTikTokUpload?.error)
              || !tiktokUploadErrorNeedsSessionRepair(latestTikTokUpload?.error);
            const youtubeQueue = uploadQueuePosition(latestUpload, youtubeUploads);
            const tiktokQueue = uploadQueuePosition(latestTikTokUpload, tiktokUploads);
            const runningStage = latestUpload ? youtubeRunningStage(latestUpload) : "";
            const queuePosition = latestUpload?.status === "queued"
              ? youtubeQueue?.position ?? null
              : null;
            const queueTotal = latestUpload?.status === "queued"
              ? youtubeQueue?.total ?? null
              : null;
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
                  || "Upload ditahan: output belum lolos gate keamanan/editorial setelah perbaikan otomatis. Proses ulang sumber atau pilih klip lain."
                : !uploadReviewConfirmed
                  ? "Centang review hasil, fakta, dan hak penggunaan sebelum upload Private."
                : isAlreadyUploaded
                ? `Sudah terupload ke YouTube${latestUpload.video_url ? `: ${latestUpload.video_url}` : ""}`
                : youtubeClaimWasDetected
                  ? "Klip terkena klaim Content ID, sedang dihapus, dan sumber pengganti akan masuk antrean baru."
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
                className={`clipCard ${isLongForm ? "clipCardLongForm" : ""} ${isPortraitOutput ? "clipCardPortrait" : ""} ${clip.is_correct ? "clipCardCorrect" : ""} ${isSelected ? "selected" : ""}`}
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
                        : automaticRepairDidNotPass
                          ? "Ditahan setelah perbaikan otomatis"
                        : isUploadReady && !meetsFypTarget
                          ? "Siap review manual · skor di bawah target"
                        : isUploadReady
                          ? "Klip siap review Private"
                          : longAutomation?.providerDeclined
                            ? "Upload ditahan QC aplikasi"
                            : "Ditahan gate keamanan"}
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
                {longAutomation ? (
                  <div className="clipMetrics" role="status">
                    <span className={`clipMetric${longAutomation.hold ? " clipMetric--blocked" : ""}`}>{longAutomation.reason}</span>
                    {longAutomation.next ? <span className="clipMetric">{longAutomation.next}</span> : null}
                    {longAutomation.replacementVideoUrl ? (
                      <a className="clipMetric" href={longAutomation.replacementVideoUrl} target="_blank" rel="noreferrer">Buka video pengganti</a>
                    ) : null}
                  </div>
                ) : null}
                {growthReadiness || clip.context_recut_required || (isLongForm && clip.thumbnail_url) ? (
                  <div className="clipMetrics">
                    {growthReadiness ? (
                      <span
                        className={`clipMetric clipMetric--growth clipMetric--growth-${growthReadiness.tone}`}
                        title="Target eksperimen; hasil nyata dipantau setelah upload."
                      >
                        <Target size={13} />
                        {growthReadiness.label}
                      </span>
                    ) : null}
                    {clip.context_recut_required ? (
                      <span className="clipMetric clipMetric--blocked">Potong ulang wajib</span>
                    ) : null}
                    {isLongForm && clip.thumbnail_url ? (
                      <span className="clipMetric">Thumbnail siap</span>
                    ) : null}
                  </div>
                ) : null}
                {isLongForm && thumbnailVariants.length ? (
                  <details className="thumbnailVariantDesk">
                    <summary>
                      <span><ImageIcon size={14} /> Paket thumbnail</span>
                      <small>{thumbnailVariants.length} varian{thumbnailVariants.length === 3 ? " · siap A/B/C" : ""}</small>
                      <ChevronDown size={14} />
                    </summary>
                    <div className="thumbnailVariantGrid">
                      {thumbnailVariants.map((thumbnailUrl, index) => {
                        const resolvedThumbnailUrl = getOutputUrl(thumbnailUrl);
                        return (
                          <a href={resolvedThumbnailUrl} target="_blank" rel="noreferrer" key={thumbnailUrl}>
                            <span>Varian {String.fromCharCode(65 + index)}</span>
                            <img src={resolvedThumbnailUrl} alt={`Thumbnail ${String.fromCharCode(65 + index)} untuk ${title}`} />
                            <small><Download size={12} /> Buka resolusi penuh</small>
                          </a>
                        );
                      })}
                    </div>
                    <p>Upload varian A terlebih dahulu. Untuk long-form publik, uji hingga tiga varian lewat Test &amp; Compare YouTube dan pilih berdasarkan watch-time share.</p>
                  </details>
                ) : null}
                {clip.production_team_status ? (
                  <details className="productionTeamDesk">
                    <summary>
                      <span>
                        <Video size={14} />
                        Production Desk
                      </span>
                      <small className={`productionQcStatus productionQcStatus--${automaticQcState}`}>
                        {automaticQcState === "passed"
                          ? "QC otomatis lolos"
                          : automaticQcState === "hold"
                            ? "QC otomatis menahan"
                            : renderQcWarning && clip.youtube_upload_ready === true
                              ? "QC: catatan visual"
                            : "QC otomatis menunggu"}
                      </small>
                      <ChevronDown size={14} />
                    </summary>
                    <div className="productionTeamGrid">
                      <div>
                        <strong>Researcher</strong>
                        <span>{clip.production_research_brief || "Hook dan peak moment perlu diperiksa."}</span>
                      </div>
                      <div>
                        <strong>Editor</strong>
                        <span>{clip.production_editor_brief || "Treatment edit adaptif."}</span>
                      </div>
                      <div>
                        <strong>Distribution</strong>
                        <span>{clip.production_distribution_brief || "Paket metadata perlu dilengkapi."}</span>
                      </div>
                      <div>
                        <strong>Quality Control Otomatis</strong>
                        <span>{clip.production_qc_brief || "Hak, konteks, dan render perlu direview."}</span>
                      </div>
                    </div>
                    <section className={`automaticQcPanel automaticQcPanel--${automaticQcState}`}>
                      <div className="automaticQcHeader">
                        <span><ShieldCheck size={15} /> Skill QC Otomatis</span>
                        <strong>
                          {automaticQcState === "passed"
                            ? "Lulus"
                            : automaticQcState === "hold"
                              ? "Ditahan"
                              : renderQcWarning && clip.youtube_upload_ready === true
                                ? "Catatan visual"
                              : "Belum lengkap"}
                        </strong>
                      </div>
                      <p>Dijalankan otomatis setelah render dan sebelum klip boleh masuk antrean upload.</p>
                      <div className="automaticQcChecks">
                        {automaticQcChecks.map((check) => (
                          <div className={`automaticQcCheck automaticQcCheck--${check.state}`} key={check.label}>
                            {check.state === "passed" ? (
                              <CheckCircle2 size={14} />
                            ) : check.state === "failed" ? (
                              <AlertTriangle size={14} />
                            ) : (
                              <Clock3 size={14} />
                            )}
                            <span><strong>{check.label}</strong><small>{check.detail}</small></span>
                          </div>
                        ))}
                      </div>
                      {clip.render_qc_warnings?.length ? (
                        <div className="automaticQcWarnings">
                          <strong>Peringatan QC</strong>
                          <ul>
                            {clip.render_qc_warnings.map((warning) => <li key={warning}>{warning}</li>)}
                          </ul>
                        </div>
                      ) : null}
                      {clip.production_qc_checks?.length ? (
                        <div className="automaticQcHuman">
                          <strong>Verifikasi manusia sebelum publikasi</strong>
                          <ul>
                            {clip.production_qc_checks.map((check) => <li key={check}>{qcCheckLabel(check)}</li>)}
                          </ul>
                        </div>
                      ) : null}
                    </section>
                    <p>
                      QC otomatis boleh menahan klip, tetapi tidak menggantikan persetujuan manusia untuk izin sumber, fakta, hasil final, dan publikasi.
                    </p>
                  </details>
                ) : null}
                <div className="clipCardFooter">
                  {clip.context_recut_required || automaticRepairDidNotPass ? (
                    <div className="clipRepairNotice">
                      <Info size={16} />
                      <span>
                        {clip.context_recut_required
                          ? "Perbaikan otomatis sudah dijalankan, tetapi audit final masih menemukan batas kalimat atau makna yang belum utuh. Klip ini ditahan dari upload; proses ulang sumber atau pilih klip lain."
                          : clip.youtube_upload_issue
                            || "Perbaikan otomatis sudah dijalankan, tetapi audit transformasi editorial belum lolos. Klip ini tidak diteruskan ke upload."}
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
                    <button
                      type="button"
                      className="youtubeUploadButton"
                      onClick={() => onUploadClipToYouTube(clip)}
                      disabled={!youtubeEnabled || !isUploadReady || !uploadReviewConfirmed || isUploadingToYouTube || isAlreadyUploaded || youtubeClaimWasDetected}
                      title={youtubeButtonTitle}
                    >
                      <UploadCloud size={16} />
                      <span>
                        {!isUploadReady
                          ? longAutomation?.providerDeclined ? "Ditahan QC aplikasi" : "Quality gate · Ditahan"
                          : youtubeClaimWasDetected
                            ? "Menghapus · Klaim"
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
                    <button
                      type="button"
                      className={`tiktokUploadButton ${!tiktokEnabled ? "tiktokUploadButton--login" : ""}`}
                      onClick={() => tiktokEnabled ? onUploadClipToTikTok(clip) : onStartTikTokLogin()}
                      disabled={tiktokEnabled
                        ? !isUploadReady || !uploadReviewConfirmed || isUploadingToTikTok || isAlreadyOnTikTok || hasPendingTikTokPost
                        : isTikTokLoginActive}
                      aria-label={!tiktokEnabled
                        ? tiktokStatusMessage
                        : isAlreadyOnTikTok
                          ? `Sudah dikirim ke @${tiktokTargetHandle}.`
                        : !isUploadReady
                          ? clip.youtube_upload_issue || "Clip belum lolos gate keamanan/editorial."
                          : !uploadReviewConfirmed
                            ? "Centang review konteks, fakta, dan hak penggunaan."
                            : hasPendingTikTokPost
                                ? "Hasil Post sebelumnya perlu diperiksa sebelum pengiriman berikutnya."
                                : `Kirim ke @${tiktokTargetHandle} sebagai Only you.`}
                    >
                      {tiktokEnabled ? <UploadCloud size={16} /> : <ExternalLink size={16} />}
                      <span>{!tiktokEnabled
                        ? isTikTokLoginActive
                          ? "Menunggu login..."
                          : "Login TikTok"
                        : isAlreadyOnTikTok
                          ? "Sudah TikTok"
                        : !isUploadReady
                          ? "Quality gate · Ditahan"
                          : !uploadReviewConfirmed
                            ? "Review dulu"
                            : hasPendingTikTokPost
                                ? "Periksa status TikTok"
                              : latestTikTokUpload?.status === "queued"
                                ? "Antrean TikTok"
                                : latestTikTokUpload?.status === "running"
                                  ? "Upload TikTok..."
                                  : latestTikTokUpload?.status === "failed"
                                    ? "Ulangi TikTok"
                                    : "Kirim TikTok"}</span>
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
                      className={`youtubeUploadStatus status-${latestUpload.status} ${youtubeClaimWasDetected ? "youtubeUploadStatus--claim" : ""} ${cleanupPanelVisible ? "youtubeUploadStatus--cleanup isAutoOpen" : ""} ${cleanupComplete ? "isCleanupComplete" : ""}`}
                      tabIndex={cleanupPanelVisible ? 0 : undefined}
                    >
                      <UploadCloud size={14} />
                      <span className="youtubeUploadStatusText">
                        YouTube: {youtubeClaimWasDetected ? "menghapus · klaim Content ID" : latestUpload.status}
                        {!youtubeClaimWasDetected && runningStage ? ` · ${runningStage}` : null}
                        {latestUpload.status === "completed" && latestUpload.visibility === "private"
                          ? " · tersimpan Private"
                          : null}
                        {!youtubeClaimWasDetected && latestUpload.playlist
                          ? latestUpload.playlist_confirmed
                            ? ` · playlist ${latestUpload.playlist} terverifikasi`
                            : latestUpload.status === "running"
                              ? ` · mencari playlist ${latestUpload.playlist}`
                              : null
                          : null}
                        {!youtubeClaimWasDetected && latestUpload.thumbnail_url
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
                        {latestUpload.status === "queued" && youtubeQueue
                          ? ` · ${youtubeQueue.hint}`
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
                          title={youtubeQueue?.hint}
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
                    <div className={`youtubeUploadError ${youtubeClaimWasDetected ? "youtubeUploadError--claim" : ""}`} title={uploadError}>
                      <strong>{youtubeClaimWasDetected ? "Menghapus & mencari pengganti" : "Upload gagal"}</strong>
                      <span>{uploadError}</span>
                      {!youtubeClaimWasDetected ? (
                        <button type="button" onClick={() => void onDeleteYouTubeUpload(latestUpload)}>
                          <Trash2 size={14} />
                          <span>Hapus catatan gagal</span>
                        </button>
                      ) : null}
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
                  {latestTikTokUpload ? (
                    <div className={`youtubeUploadStatus tiktokUploadStatus status-${latestTikTokUpload.status}`}>
                      <UploadCloud size={14} />
                      <span className="youtubeUploadStatusText">
                        TikTok: {hasPendingTikTokPost ? "hasil Post belum pasti" : tiktokPrivacyPending ? "pengaturan privasi tertunda" : latestTikTokUpload.status}
                        {` · tujuan ${latestTikTokUpload.visibility === "public" ? "Everyone" : "Only you"}`}
                        {uploadTikTokSeriesLabel ? ` · ${uploadTikTokSeriesLabel}` : null}
                        {latestTikTokUpload.status === "running"
                          ? ` · ${tiktokRunningStage(latestTikTokUpload)}`
                          : null}
                        {latestTikTokUpload.status === "completed" && latestTikTokUpload.upload_confirmed
                          ? " · posting terverifikasi"
                          : null}
                        {latestTikTokUpload.status === "queued" && tiktokQueue?.position
                          ? ` · antrean ${tiktokQueue.position}/${tiktokQueue.total} · ${tiktokQueue.hint}`
                          : null}
                        {latestTikTokUpload.profile_url ? (
                          <> · <a href={latestTikTokUpload.profile_url} target="_blank" rel="noreferrer">profil</a></>
                        ) : null}
                      </span>
                    </div>
                  ) : null}
                  {latestTikTokUpload?.status === "failed" && latestTikTokUpload.error ? (
                    <div className="youtubeUploadError tiktokUploadError" title={latestTikTokUpload.error}>
                      <strong>{hasPendingTikTokPost ? "Hasil posting perlu diperiksa" : tiktokAutomaticRetryLabel(latestTikTokUpload) ? "TikTok dijadwalkan ulang otomatis" : tiktokPrivacyPending ? "Pengaturan privasi belum selesai" : "Upload TikTok gagal"}</strong>
                      <span>{hasPendingTikTokPost ? "Post pernah dicoba, tetapi hasil akhirnya belum terkonfirmasi. Periksa daftar posting sebelum mengirim video yang sama lagi." : tiktokAutomaticRetryLabel(latestTikTokUpload) || friendlyTikTokUploadError(latestTikTokUpload.error, latestTikTokUpload.visibility)}</span>
                      {hasPendingTikTokPost ? (
                        <a href="https://www.tiktok.com/tiktokstudio/content" target="_blank" rel="noreferrer">Buka daftar posting TikTok</a>
                      ) : tiktokAutomaticRetryLabel(latestTikTokUpload) ? (
                        <span>Backend akan memasukkan percobaan baru ke antrean. Anda tidak perlu menekan Ulangi.</span>
                      ) : <button
                        type="button"
                        onClick={shouldRetryTikTokUpload
                          ? () => onUploadClipToTikTok(clip)
                          : onCheckTikTokSession}
                        disabled={isTikTokLoginActive}
                      >
                        <RefreshCw size={14} />
                        <span>{isTikTokLoginActive
                          ? "Selesaikan login..."
                          : shouldRetryTikTokUpload
                            ? "Ulangi TikTok"
                            : "Cek sesi TikTok"}</span>
                      </button>}
                    </div>
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="emptyState">
          <Video className="emptyStateIcon" size={32} />
          <p>Hasil video yang selesai diproses akan muncul di sini.</p>
          <a className="uiButton" href="/#quick-start-title">Buat video pertama</a>
        </div>
      )}
    </section>
  );
}
