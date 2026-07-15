import { CheckCircle2, Clipboard, Download, ExternalLink, RefreshCw, Trash2, UploadCloud, Video } from "lucide-react";
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
    return "Chrome remote debugging belum aktif di port 9222. Jalankan ./scripts/recreate-compose-up.sh dan biarkan Chrome Studio tetap terbuka.";
  }
  if (lowered.includes("python youtube_uploader.py login")) {
    return "Card ini masih membawa error lama dari storage-state. Upload sekarang memakai Chrome remote debugging; jalankan ./scripts/recreate-compose-up.sh, pastikan Chrome Studio login, lalu klik Retry YouTube.";
  }
  if (
    usesChromeDebugging
    && (lowered.includes("sesi youtube belum login") || lowered.includes("youtube studio meminta login"))
  ) {
    return "Chrome CDP belum login ke akun target. Login harus di window Chrome yang dibuka command terminal, bukan tab dashboard. Klik Salin Command Login.";
  }
  return clean;
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
  const openStudioLabel = usesChromeDebugging ? "Salin Command Login" : "Buka Login YouTube";
  const openStudioWaitingLabel = usesChromeDebugging ? "Menyalin command..." : "Menunggu login...";

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
              {!youtubeEnabled ? (
                <>
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
                    title={usesChromeDebugging ? "Buka dan cek Chrome Studio remote debugging" : "Simpan session dari Chrome remote debugging ke Playwright storage state"}
                  >
                    <RefreshCw size={15} />
                    {usesChromeDebugging ? "Salin Cek Chrome" : "Sync Session"}
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
                    <button type="button" onClick={onStartYouTubeLogin} disabled={isYouTubeLoginActive}>
                      {isYouTubeLoginActive ? openStudioWaitingLabel : openStudioLabel}
                    </button>
                    <button type="button" onClick={onCaptureYouTubeSession}>
                      {usesChromeDebugging ? "Salin Cek Chrome" : "Sync Session Browser"}
                    </button>
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
