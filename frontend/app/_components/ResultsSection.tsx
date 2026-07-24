import {
  BarChart3,
  CheckCircle2,
  ChevronDown,
  Clipboard,
  Download,
  ExternalLink,
  Lightbulb,
  RefreshCw,
  Settings2,
  Sparkles,
  Target,
  Trash2,
  UploadCloud,
  Video,
} from "lucide-react";
import { getOutputUrl } from "../../lib/apiClient";
import { clipDisplayTitle, handleCopyTitle, handleDownload } from "../../lib/utils";
import type { ClipFile, YouTubeUploadJob } from "../../types/clip.type";
import { ThumbnailPrompt } from "./ThumbnailPrompt";

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

function fypScoreTone(score: number) {
  if (score >= 88) return "excellent";
  if (score >= 78) return "strong";
  if (score >= 65) return "promising";
  return "polish";
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
  const selectedCount = selectedClipUrls.length;
  const allClipsSelected = clips.length > 0 && selectedCount === clips.length;
  const usesChromeDebugging = /remote debugging|cdp/i.test(youtubeStatusMessage);
  const openStudioWaitingLabel = usesChromeDebugging ? "Menyiapkan..." : "Menunggu login...";

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
            const isUploadingToYouTube = latestUpload?.status === "queued" || latestUpload?.status === "running";
            const rawUploadError = latestUpload?.error || latestUpload?.logs?.at(-1) || "";
            const uploadError = friendlyYouTubeUploadError(rawUploadError, usesChromeDebugging);
            const youtubeButtonTitle = youtubeEnabled
              ? uploadError
                ? `Upload ulang ke YouTube. Error terakhir: ${uploadError}`
                : "Upload klip ini ke YouTube"
              : youtubeStatusMessage;

            return (
              <article
                className={`clipCard ${clip.is_correct ? "clipCardCorrect" : ""} ${isSelected ? "selected" : ""}`}
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
                      disabled={!youtubeEnabled || isUploadingToYouTube}
                      title={youtubeButtonTitle}
                    >
                      <UploadCloud size={16} />
                      <span>
                        {isUploadingToYouTube
                          ? "Mengupload..."
                          : latestUpload?.status === "failed"
                            ? "Ulangi YouTube"
                            : "Kirim YouTube"}
                      </span>
                    </button>
                    <button className="clipDeleteButton" type="button" onClick={() => onDeleteClip(clip)}>
                      <Trash2 size={16} />
                      <span>Hapus</span>
                    </button>
                  </div>
                  {latestUpload ? (
                    <div className={`youtubeUploadStatus status-${latestUpload.status}`}>
                      <UploadCloud size={14} />
                      <span>
                        YouTube: {latestUpload.status}
                        {latestUpload.video_url ? (
                          <>
                            {" "}
                            · <a href={latestUpload.video_url} target="_blank" rel="noreferrer">buka</a>
                          </>
                        ) : null}
                      </span>
                    </div>
                  ) : null}
                  {latestUpload?.status === "failed" && uploadError ? (
                    <div className="youtubeUploadError" title={uploadError}>
                      <strong>Upload gagal</strong>
                      <span>{uploadError}</span>
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
