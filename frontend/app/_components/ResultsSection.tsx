import {
  CheckCircle2,
  Clipboard,
  Download,
  ExternalLink,
  Lightbulb,
  RefreshCw,
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
    <section className="results">
      <div className="sectionHeader">
        <h2>Klip Siap Digunakan</h2>
        <div className="resultsActions">
          <span className="sectionBadge">{clips.length} klip siap</span>
          {clips.length > 0 ? (
            <>
              <label className="selectAllClips">
                <input checked={allClipsSelected} type="checkbox" onChange={onToggleAllClipSelection} />
                Pilih semua
              </label>
              {selectedCount > 0 ? (
                <button type="button" onClick={onDeleteSelectedClips} className="dangerButton historyDeleteSelected">
                  <Trash2 size={15} />
                  Hapus terpilih ({selectedCount})
                </button>
              ) : null}
              <button
                type="button"
                onClick={onUploadAllToYouTube}
                className="ghostButton youtubeButton"
                disabled={!youtubeEnabled}
                title={
                  youtubeEnabled
                    ? `Auto upload ${Math.min(youtubeAutoUploadCount, clips.length)} klip terbaik ke YouTube`
                    : youtubeStatusMessage
                }
              >
                <UploadCloud size={15} />
                Upload {Math.min(youtubeAutoUploadCount, clips.length)} terbaik
              </button>
              {usesChromeDebugging ? (
                <>
                  <button
                    type="button"
                    onClick={onSetupYouTubeOneTimeLogin}
                    className="ghostButton youtubeButton"
                    title="Ambil cookies/session sekali lalu upload berikutnya memakai storage-state tanpa CDP"
                  >
                    <RefreshCw size={15} />
                    Login Sekali
                  </button>
                  <button
                    type="button"
                    onClick={onCaptureYouTubeSession}
                    className="ghostButton youtubeButton"
                    disabled={isYouTubeLoginActive}
                    title="Cadangan: start CDP, hydrate login, dan validasi akun/channel target"
                  >
                    <RefreshCw size={15} />
                    CDP Opsional
                  </button>
                  <button
                    type="button"
                    onClick={onEnableNoCdpMode}
                    className="ghostButton youtubeButton"
                    title="Matikan CDP dan upload memakai Playwright/profile backend langsung"
                  >
                    <RefreshCw size={15} />
                    Tanpa CDP
                  </button>
                  <button
                    type="button"
                    onClick={onImportYouTubeCdpCookies}
                    className="ghostButton youtubeButton"
                    title="Ambil cookies langsung dari Chrome CDP yang sudah login dan simpan ke storage-state"
                  >
                    <RefreshCw size={15} />
                    Ambil Cookies
                  </button>
                </>
              ) : !youtubeEnabled ? (
                <>
                  <button
                    type="button"
                    onClick={onSetupYouTubeOneTimeLogin}
                    className="ghostButton youtubeButton"
                    title="Ambil cookies/session sekali dari Chrome/profile yang sudah login"
                  >
                    <RefreshCw size={15} />
                    Login Sekali
                  </button>
                  <button
                    type="button"
                    onClick={onStartYouTubeLogin}
                    className="ghostButton youtubeButton"
                    disabled={isYouTubeLoginActive}
                    title={youtubeStatusMessage}
                  >
                    <ExternalLink size={15} />
                    Login YouTube
                  </button>
                  <button
                    type="button"
                    onClick={onCaptureYouTubeSession}
                    className="ghostButton youtubeButton"
                    title="Simpan session browser ke Playwright storage-state"
                  >
                    <RefreshCw size={15} />
                    Sync Session
                  </button>
                </>
              ) : null}
              <button type="button" onClick={onDeleteAllClips} className="ghostButton dangerTextButton">
                <Trash2 size={15} />
                Hapus semua klip
              </button>
            </>
          ) : null}
        </div>
      </div>

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
                <label className="clipSelect">
                  <input
                    aria-label={`Pilih ${title} untuk dihapus`}
                    checked={isSelected}
                    type="checkbox"
                    onChange={() => onToggleClipSelection(clip.url)}
                  />
                </label>
                <video controls preload="metadata" src={url} />
                <div className="clipInfo">
                  <h3>{title}</h3>
                  <button
                    className="copyTitleButton"
                    type="button"
                    onClick={() => handleCopyTitle(title)}
                    title="Salin judul klip"
                  >
                    <Clipboard size={14} />
                    Copy
                  </button>
                </div>
                {clip.fyp_score !== null && clip.fyp_score !== undefined ? (
                  <div className="fypAnalysis">
                    <div className="fypScoreRow">
                      <span className={`fypScore fypScore-${fypScoreTone(clip.fyp_score)}`}>
                        <Sparkles size={15} />
                        FYP {Math.round(clip.fyp_score)}/100
                      </span>
                      <strong>{clip.fyp_label || "Sudah dinilai"}</strong>
                      {clip.output_resolution ? (
                        <span className="resolutionBadge">{clip.output_resolution} HD</span>
                      ) : null}
                    </div>
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
                        <b>Yang masih kurang</b>
                        <ul>{clip.weaknesses.slice(0, 3).map((item) => <li key={item}>{item}</li>)}</ul>
                      </div>
                    ) : null}
                    {clip.applied_edits?.length ? (
                      <div className="analysisBlock analysisApplied">
                        <b><CheckCircle2 size={14} /> Diterapkan Codex</b>
                        <ul>{clip.applied_edits.slice(0, 4).map((item) => <li key={item}>{item}</li>)}</ul>
                      </div>
                    ) : null}
                    {clip.improvement_ideas?.length ? (
                      <div className="analysisBlock analysisIdea">
                        <div className="analysisIdeaHeader">
                          <b><Lightbulb size={14} /> Ide Codex</b>
                          <span>Prioritas edit</span>
                        </div>
                        <ol>{clip.improvement_ideas.slice(0, 3).map((item) => <li key={item}>{item}</li>)}</ol>
                      </div>
                    ) : null}
                  </div>
                ) : null}
                <label className="clipValidation">
                  <input
                    checked={clip.is_correct}
                    type="checkbox"
                    onChange={(event) => onToggleClipCorrect(clip, event.target.checked)}
                  />
                  <span>
                    <CheckCircle2 size={16} />
                    Terclip benar
                  </span>
                </label>
                <div className="clipActions">
                  <a href={url} target="_blank" rel="noreferrer">
                    <ExternalLink size={16} />
                    Buka
                  </a>
                  <button type="button" onClick={() => handleDownload(url, clip.name)}>
                    <Download size={16} />
                    Unduh
                  </button>
                  <button
                    type="button"
                    className="youtubeUploadButton"
                    onClick={() => onUploadClipToYouTube(clip)}
                    disabled={!youtubeEnabled || isUploadingToYouTube}
                    title={youtubeButtonTitle}
                  >
                    <UploadCloud size={16} />
                    {isUploadingToYouTube ? "Uploading" : latestUpload?.status === "failed" ? "Retry YouTube" : "YouTube"}
                  </button>
                  <button className="clipDeleteButton" type="button" onClick={() => onDeleteClip(clip)}>
                    <Trash2 size={16} />
                    Hapus
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
                      {isYouTubeLoginActive ? openStudioWaitingLabel : "Login Sekali"}
                    </button>
                    <button type="button" onClick={onCaptureYouTubeSession}>
                      {usesChromeDebugging ? "CDP Opsional" : "Sync Session Browser"}
                    </button>
                    {usesChromeDebugging ? (
                      <>
                        <button type="button" onClick={onImportYouTubeCdpCookies}>
                          Ambil Cookies
                        </button>
                        <button type="button" onClick={onEnableNoCdpMode}>
                          Tanpa CDP
                        </button>
                      </>
                    ) : null}
                  </div>
                ) : null}
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
