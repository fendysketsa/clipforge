import { CheckCircle2, Clipboard, Download, ExternalLink, Trash2, Video } from "lucide-react";
import { getOutputUrl } from "../../lib/apiClient";
import { clipTitle, handleCopyTitle, handleDownload } from "../../lib/utils";
import type { ClipFile } from "../../types/clip.type";
import { ThumbnailPrompt } from "./ThumbnailPrompt";

type ResultsSectionProps = {
  clips: ClipFile[];
  onDeleteAllClips: () => void;
  onDeleteClip: (clip: ClipFile) => void;
  onToggleClipCorrect: (clip: ClipFile, isCorrect: boolean) => void;
};

export function ResultsSection({
  clips,
  onDeleteAllClips,
  onDeleteClip,
  onToggleClipCorrect,
}: ResultsSectionProps) {
  return (
    <section className="results">
      <div className="sectionHeader">
        <h2>Klip Siap Digunakan</h2>
        <div className="resultsActions">
          <span className="sectionBadge">{clips.length} klip siap</span>
          {clips.length > 0 ? (
            <button type="button" onClick={onDeleteAllClips} className="ghostButton dangerTextButton">
              <Trash2 size={15} />
              Hapus semua klip
            </button>
          ) : null}
        </div>
      </div>

      {clips.length ? (
        <div className="clipGrid">
          {clips.map((clip) => {
            const title = clipTitle(clip.name);
            const url = getOutputUrl(clip.url);

            return (
              <article className={`clipCard ${clip.is_correct ? "clipCardCorrect" : ""}`} key={clip.url}>
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
                  <button className="clipDeleteButton" type="button" onClick={() => onDeleteClip(clip)}>
                    <Trash2 size={16} />
                    Hapus
                  </button>
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
