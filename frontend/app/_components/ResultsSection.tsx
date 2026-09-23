import {
  BarChart3,
  CheckCircle2,
  ChevronDown,
  Clipboard,
  Clock3,
  Download,
  ExternalLink,
  Info,
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
import { VIRAL_QUALITY_FLOOR } from "../../lib/constants";
import { clipDisplayTitle, handleCopyTitle, handleDownload } from "../../lib/utils";
import type { ClipFile, TikTokUploadJob, YouTubeUploadJob } from "../../types/clip.type";

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
  onCaptureYouTubeSession: () => void;
  onCheckTikTokSession: () => void;
  onEnableNoCdpMode: () => void;
  onImportYouTubeCdpCookies: () => void;
  onSetupYouTubeOneTimeLogin: () => void;
  onStartYouTubeLogin: () => void;
  onStartTikTokLogin: () => void;
  onRepairClip: (clip: ClipFile) => void;
  onRefreshYouTubePerformance: (upload: YouTubeUploadJob) => Promise<void>;
  onSaveYouTubeFeedMetrics: (
    upload: YouTubeUploadJob,
    metrics: { shown_in_feed?: number; stayed_to_watch_percentage?: number },
  ) => Promise<void>;
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

function friendlyTikTokUploadError(message: string) {
  const clean = message.trim();
  const lowered = clean.toLowerCase();
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
) {
  const target = `Target ${(targetViews / 1000).toLocaleString("id-ID", { maximumFractionDigits: 1 })}K / ${targetSubscribers} sub`;
  if (status?.startsWith("revise")) {
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
  selectedClipUrls,
  youtubeEnabled,
  youtubeStatusMessage,
  youtubeAutoUploadCount,
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
  onCaptureYouTubeSession,
  onCheckTikTokSession,
  onEnableNoCdpMode,
  onImportYouTubeCdpCookies,
  onSetupYouTubeOneTimeLogin,
  onStartYouTubeLogin,
  onStartTikTokLogin,
  onRepairClip,
  onRefreshYouTubePerformance,
  onSaveYouTubeFeedMetrics,
  onUploadAllToYouTube,
  onUploadAllToTikTok,
  onUploadClipToYouTube,
  onUploadClipToTikTok,
  onToggleAllClipSelection,
  onToggleClipSelection,
  onToggleClipCorrect,
}: ResultsSectionProps) {
  const [uploadStatusNow, setUploadStatusNow] = useState(() => Date.now());
  const [refreshingPerformanceId, setRefreshingPerformanceId] = useState<string | null>(null);
  const [savingFeedMetricsId, setSavingFeedMetricsId] = useState<string | null>(null);
  const [feedMetricDrafts, setFeedMetricDrafts] = useState<Record<string, {
    shownInFeed: string;
    stayedToWatch: string;
  }>>({});
  const selectedCount = selectedClipUrls.length;
  const allClipsSelected = clips.length > 0 && selectedCount === clips.length;
  const usesChromeDebugging = /remote debugging|cdp/i.test(youtubeStatusMessage);
  const openStudioWaitingLabel = usesChromeDebugging ? "Menyiapkan..." : "Menunggu login...";
  const hasCleanupCountdown = youtubeUploads.some(
    (upload) => Boolean(upload.clip_delete_after && !upload.clip_deleted_at),
  );
  const performanceUploads = youtubeUploads
    .filter((upload) => upload.status === "completed" && Boolean(upload.video_url))
    .slice(0, 8);

  const refreshPerformance = async (upload: YouTubeUploadJob) => {
    setRefreshingPerformanceId(upload.id);
    try {
      await onRefreshYouTubePerformance(upload);
    } finally {
      setRefreshingPerformanceId(null);
    }
  };

  const saveFeedMetrics = async (upload: YouTubeUploadJob) => {
    const latest = upload.performance_snapshots.at(-1);
    const draft = feedMetricDrafts[upload.id];
    const shownRaw = draft?.shownInFeed ?? latest?.shown_in_feed?.toString() ?? "";
    const stayedRaw = draft?.stayedToWatch ?? latest?.stayed_to_watch_percentage?.toString() ?? "";
    const shown = shownRaw.trim() === "" ? undefined : Math.max(0, Math.round(Number(shownRaw)));
    const stayed = stayedRaw.trim() === ""
      ? undefined
      : Math.max(0, Math.min(100, Number(stayedRaw)));
    if (
      (shown === undefined || !Number.isFinite(shown))
      && (stayed === undefined || !Number.isFinite(stayed))
    ) return;
    setSavingFeedMetricsId(upload.id);
    try {
      await onSaveYouTubeFeedMetrics(upload, {
        shown_in_feed: shown !== undefined && Number.isFinite(shown) ? shown : undefined,
        stayed_to_watch_percentage: stayed !== undefined && Number.isFinite(stayed) ? stayed : undefined,
      });
    } finally {
      setSavingFeedMetricsId(null);
    }
  };

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

      {clips.length > 0 ? (
        <details className="youtubeSetupPanel tiktokSetupPanel">
          <summary>
            <span className="youtubeSetupIcon"><Settings2 size={17} /></span>
            <span className="youtubeSetupCopy">
              <strong>TikTok @{tiktokTargetHandle} · Only you</strong>
              <small>{tiktokStatusMessage}</small>
            </span>
            <ChevronDown className="detailsChevron" size={18} />
          </summary>
          <div className="youtubeSetupActions">
            <button type="button" onClick={onStartTikTokLogin} className="uiButton uiButton--tiktok" disabled={isTikTokLoginActive}>
              <ExternalLink size={16} />
              <span>{isTikTokLoginActive ? "Menunggu login..." : "Login TikTok sekali"}</span>
            </button>
            <button
              type="button"
              onClick={onCheckTikTokSession}
              className="uiButton uiButton--tiktok"
              disabled={isTikTokLoginActive}
            >
              <RefreshCw size={16} />
              <span>{isTikTokLoginActive ? "Selesaikan login..." : "Cek sesi TikTok"}</span>
            </button>
            <a className="uiButton uiButton--secondary" href={`https://www.tiktok.com/@${tiktokTargetHandle}`} target="_blank" rel="noreferrer">
              <ExternalLink size={16} />
              <span>Buka profil</span>
            </a>
          </div>
        </details>
      ) : null}

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

      {performanceUploads.length > 0 ? (
        <details className="youtubePerformancePanel">
          <summary>
            <span className="youtubeSetupIcon"><BarChart3 size={17} /></span>
            <span className="youtubeSetupCopy">
              <strong>Loop belajar YouTube</strong>
              <small>Bandingkan view, retention, dan subscriber per seri—bukan tebakan skor FYP.</small>
            </span>
            <ChevronDown className="detailsChevron" size={18} />
          </summary>
          <div className="youtubePerformanceList">
            {performanceUploads.map((upload) => {
              const latest = upload.performance_snapshots.at(-1);
              const conversionViews = latest?.engaged_views ?? latest?.views ?? 0;
              const conversion = latest?.subscribers_gained !== null
                && latest?.subscribers_gained !== undefined
                && conversionViews > 0
                ? (latest.subscribers_gained * 1000) / conversionViews
                : null;
              const engagedRate = latest?.engaged_views !== null
                && latest?.engaged_views !== undefined
                && (latest?.views ?? 0) > 0
                ? (latest.engaged_views * 100) / latest.views
                : null;
              return (
                <article className="youtubePerformanceItem" key={upload.id}>
                  <div className="youtubePerformanceCopy">
                    <strong>{upload.title}</strong>
                    <small>
                      {upload.growth_series || "Seri belum ditentukan"} · target {upload.growth_target_views.toLocaleString("id-ID")} view / {upload.growth_target_subscribers} sub
                    </small>
                    {upload.performance_diagnosis?.[0] ? <p>{upload.performance_diagnosis[0]}</p> : null}
                  </div>
                  <div className="youtubePerformanceMetrics">
                    <span>View <b>{latest ? latest.views.toLocaleString("id-ID") : "—"}</b></span>
                    <span>Engaged <b>{latest?.engaged_views !== null && latest?.engaged_views !== undefined ? latest.engaged_views.toLocaleString("id-ID") : "—"}</b></span>
                    <span title="Engaged views dibagi public views; public views menghitung start/replay sejak 31 Maret 2025">Eng/View <b>{engagedRate !== null ? `${engagedRate.toFixed(1)}%` : "—"}</b></span>
                    <span>Feed <b>{latest?.shown_in_feed !== null && latest?.shown_in_feed !== undefined ? latest.shown_in_feed.toLocaleString("id-ID") : "—"}</b></span>
                    <span>Stayed <b>{latest?.stayed_to_watch_percentage !== null && latest?.stayed_to_watch_percentage !== undefined ? `${latest.stayed_to_watch_percentage.toFixed(1)}%` : "—"}</b></span>
                    <span>Retention <b>{latest?.average_view_percentage !== null && latest?.average_view_percentage !== undefined ? `${latest.average_view_percentage.toFixed(1)}%` : "—"}</b></span>
                    <span title={latest?.engaged_views !== null && latest?.engaged_views !== undefined ? "Subscriber per 1.000 engaged views" : "Subscriber per 1.000 public views"}>Sub/1K <b>{conversion !== null ? conversion.toFixed(2) : "—"}</b></span>
                  </div>
                  <div className="youtubeFeedMetricEditor">
                    <label>
                      <span>Shown in feed</span>
                      <input
                        min="0"
                        inputMode="numeric"
                        type="number"
                        placeholder="0"
                        value={feedMetricDrafts[upload.id]?.shownInFeed ?? latest?.shown_in_feed?.toString() ?? ""}
                        onChange={(event) => setFeedMetricDrafts((current) => ({
                          ...current,
                          [upload.id]: {
                            shownInFeed: event.target.value,
                            stayedToWatch: current[upload.id]?.stayedToWatch ?? latest?.stayed_to_watch_percentage?.toString() ?? "",
                          },
                        }))}
                      />
                    </label>
                    <label>
                      <span>Stayed to watch %</span>
                      <input
                        min="0"
                        max="100"
                        step="0.1"
                        inputMode="decimal"
                        type="number"
                        placeholder="0–100"
                        value={feedMetricDrafts[upload.id]?.stayedToWatch ?? latest?.stayed_to_watch_percentage?.toString() ?? ""}
                        onChange={(event) => setFeedMetricDrafts((current) => ({
                          ...current,
                          [upload.id]: {
                            shownInFeed: current[upload.id]?.shownInFeed ?? latest?.shown_in_feed?.toString() ?? "",
                            stayedToWatch: event.target.value,
                          },
                        }))}
                      />
                    </label>
                    <button
                      className="uiButton uiButton--secondary"
                      disabled={savingFeedMetricsId !== null}
                      onClick={() => { void saveFeedMetrics(upload); }}
                      type="button"
                    >
                      <span>{savingFeedMetricsId === upload.id ? "Menyimpan..." : "Simpan metrik Studio"}</span>
                    </button>
                  </div>
                  <div className="youtubePerformanceActions">
                    <button
                      className="uiButton uiButton--secondary"
                      disabled={refreshingPerformanceId !== null}
                      onClick={() => { void refreshPerformance(upload); }}
                      type="button"
                    >
                      <RefreshCw className={refreshingPerformanceId === upload.id ? "spin" : ""} size={15} />
                      <span>{refreshingPerformanceId === upload.id ? "Mengambil..." : "Perbarui"}</span>
                    </button>
                    <a href={upload.video_url || "#"} target="_blank" rel="noreferrer">
                      <ExternalLink size={15} />
                      <span>Studio/video</span>
                    </a>
                  </div>
                </article>
              );
            })}
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
            const latestTikTokUpload = tiktokUploads.find((upload) => upload.clip_url === clip.url);
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
              : isLongForm || (typeof clip.fyp_score === "number" && clip.fyp_score >= VIRAL_QUALITY_FLOOR);
            const meetsFypTarget = isLongForm
              || typeof clip.fyp_score !== "number"
              || clip.fyp_score >= VIRAL_QUALITY_FLOOR;
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
            const isUploadingToTikTok = latestTikTokUpload?.status === "queued" || latestTikTokUpload?.status === "running";
            const isAlreadyOnTikTok = latestTikTokUpload?.status === "completed" && latestTikTokUpload.upload_confirmed;
            const shouldRetryTikTokUpload = isTikTokFileTransferError(latestTikTokUpload?.error)
              || !tiktokUploadErrorNeedsSessionRepair(latestTikTokUpload?.error);
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
                  || "Upload ditahan: output belum lolos quality gate. Jalankan Perbaiki Otomatis."
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
                        disabled={isUploadingToYouTube || isUploadingToTikTok}
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
                    {!needsAutomaticRepair && !clip.context_recut_required ? (
                      <button
                        type="button"
                        className={`tiktokUploadButton ${!tiktokEnabled ? "tiktokUploadButton--login" : ""}`}
                        onClick={() => tiktokEnabled ? onUploadClipToTikTok(clip) : onStartTikTokLogin()}
                        disabled={tiktokEnabled
                          ? !isUploadReady || !uploadReviewConfirmed || isUploadingToTikTok || isAlreadyOnTikTok
                          : isTikTokLoginActive}
                        aria-label={!tiktokEnabled
                          ? tiktokStatusMessage
                          : !isUploadReady
                            ? clip.youtube_upload_issue || "Clip belum lolos quality gate."
                            : !uploadReviewConfirmed
                              ? "Centang review konteks, fakta, dan hak penggunaan."
                              : isAlreadyOnTikTok
                                ? `Sudah dikirim ke @${tiktokTargetHandle} sebagai Only you.`
                                : `Kirim ke @${tiktokTargetHandle} sebagai Only you.`}
                      >
                        {tiktokEnabled ? <UploadCloud size={16} /> : <ExternalLink size={16} />}
                        <span>{!tiktokEnabled
                          ? isTikTokLoginActive
                            ? "Menunggu login..."
                            : "Login TikTok"
                          : !isUploadReady
                            ? "Quality gate · Ditahan"
                            : !uploadReviewConfirmed
                              ? "Review dulu"
                              : isAlreadyOnTikTok
                                ? "Sudah TikTok"
                                : latestTikTokUpload?.status === "queued"
                                  ? "Antrean TikTok"
                                  : latestTikTokUpload?.status === "running"
                                    ? "Upload TikTok..."
                                    : latestTikTokUpload?.status === "failed"
                                      ? "Ulangi TikTok"
                                      : "Kirim TikTok"}</span>
                      </button>
                    ) : null}
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
                  {latestTikTokUpload ? (
                    <div className={`youtubeUploadStatus tiktokUploadStatus status-${latestTikTokUpload.status}`}>
                      <UploadCloud size={14} />
                      <span className="youtubeUploadStatusText">
                        TikTok: {latestTikTokUpload.status}
                        {uploadTikTokSeriesLabel ? ` · ${uploadTikTokSeriesLabel}` : null}
                        {latestTikTokUpload.status === "running"
                          ? ` · ${tiktokRunningStage(latestTikTokUpload)}`
                          : null}
                        {latestTikTokUpload.status === "completed" && latestTikTokUpload.upload_confirmed
                          ? " · tersimpan Only you"
                          : null}
                        {latestTikTokUpload.status === "queued" && latestTikTokUpload.queue_position
                          ? ` · antrean ${latestTikTokUpload.queue_position}/${latestTikTokUpload.queue_total ?? latestTikTokUpload.queue_position}`
                          : null}
                        {latestTikTokUpload.profile_url ? (
                          <> · <a href={latestTikTokUpload.profile_url} target="_blank" rel="noreferrer">profil</a></>
                        ) : null}
                      </span>
                    </div>
                  ) : null}
                  {latestTikTokUpload?.status === "failed" && latestTikTokUpload.error ? (
                    <div className="youtubeUploadError tiktokUploadError" title={latestTikTokUpload.error}>
                      <strong>Upload TikTok gagal</strong>
                      <span>{friendlyTikTokUploadError(latestTikTokUpload.error)}</span>
                      <button
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
                      </button>
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
          <p>Klip vertikal 9:16 yang selesai diproses akan muncul di sini.</p>
        </div>
      )}
    </section>
  );
}
