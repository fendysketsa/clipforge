import { ChevronDown, Clipboard, Download, ImageIcon, MessageSquareText } from "lucide-react";
import { getOutputUrl } from "../../lib/apiClient";
import { handleCopyText, handleDownload } from "../../lib/utils";
import type { ClipFile } from "../../types/clip.type";

type ThumbnailPromptProps = {
  clip: ClipFile;
};

export function ThumbnailPrompt({ clip }: ThumbnailPromptProps) {
  if (!clip.thumbnail_url && !clip.thumbnail_prompt && !clip.social_caption) {
    return null;
  }

  const thumbUrl = clip.thumbnail_url ? getOutputUrl(clip.thumbnail_url) : null;
  const thumbName = clip.name.replace(/\.mp4$/i, "_thumb.jpg");
  const prompt = clip.thumbnail_prompt?.trim() ?? "";
  const caption = clip.social_caption?.trim() ?? "";

  return (
    <details className="thumbBlock">
      <summary>
        <span className="detailsSummaryIcon">
          <ImageIcon size={16} />
        </span>
        <span className="thumbSummaryCopy">
          <strong>Materi posting</strong>
          <small>
            {[thumbUrl ? "thumbnail" : "", prompt ? "prompt" : "", caption ? "caption" : ""]
              .filter(Boolean)
              .join(" · ")}
          </small>
        </span>
        <ChevronDown className="detailsChevron" size={18} />
      </summary>

      <div className="thumbContent">
        {thumbUrl ? (
          <div className="thumbPreview">
            <div className="thumbBlockHeader">
              <ImageIcon size={14} />
              <span>Thumbnail</span>
            </div>
            <img src={thumbUrl} alt="Screenshot momen terbaik untuk thumbnail" />
            <button type="button" onClick={() => handleDownload(thumbUrl, thumbName)}>
              <Download size={15} />
              <span>Unduh thumbnail</span>
            </button>
          </div>
        ) : null}

        {prompt ? (
          <div className="thumbPromptBox">
            <div className="thumbBlockHeader">
              <Clipboard size={14} />
              <span>Prompt thumbnail</span>
            </div>
            <pre>{prompt}</pre>
            <button type="button" onClick={() => handleCopyText(prompt, "Prompt thumbnail disalin")}>
              <Clipboard size={15} />
              <span>Salin prompt</span>
            </button>
          </div>
        ) : null}

        {caption ? (
          <div className="thumbPromptBox">
            <div className="thumbBlockHeader">
              <MessageSquareText size={14} />
              <span>Caption posting</span>
            </div>
            <pre>{caption}</pre>
            <button type="button" onClick={() => handleCopyText(caption, "Caption post disalin")}>
              <Clipboard size={15} />
              <span>Salin caption</span>
            </button>
          </div>
        ) : null}
      </div>
    </details>
  );
}
