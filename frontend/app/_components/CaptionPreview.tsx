import { CAPTION_FONTS } from "../../lib/constants";
import type { CaptionFont, CaptionPosition } from "../../types/clip.type";

type CaptionPreviewProps = {
  fontSize: number;
  position: CaptionPosition;
  color: string;
  font: CaptionFont;
  outline: number;
  outlineColor: string;
};

const PREVIEW_HEIGHT = 320;
// Maps the backend ASS font size to a close CSS preview size.
const FONT_CALIBRATION = 0.96;
const SAMPLE_TEXT = "Contoh caption rapi di layar";

function outlineShadow(width: number, color: string): string {
  if (width <= 0) return "none";
  // Preview canvas is ~1/6 of the real frame, scale the border to match.
  const w = Math.max(0.5, (width * PREVIEW_HEIGHT) / 1920 * 6);
  const offsets: string[] = [];
  for (let x = -w; x <= w; x += w) {
    for (let y = -w; y <= w; y += w) {
      if (x === 0 && y === 0) continue;
      offsets.push(`${x}px ${y}px 0 ${color}`);
    }
  }
  return offsets.join(", ");
}

export function CaptionPreview({
  fontSize,
  position,
  color,
  font,
  outline,
  outlineColor,
}: CaptionPreviewProps) {
  const scaledFont = fontSize * FONT_CALIBRATION;
  const fontCss = CAPTION_FONTS.find((item) => item.value === font)?.css ?? "sans-serif";

  return (
    <div className="captionPreview">
      <span className="captionPreviewLabel">Preview</span>
      <div
        className="captionPreviewStage"
        style={{ height: PREVIEW_HEIGHT, aspectRatio: "9 / 16" }}
      >
        <div
          className={`captionPreviewText captionPreviewText--${position}`}
          style={{
            fontSize: `${scaledFont}px`,
            color,
            fontFamily: fontCss,
            textShadow: outlineShadow(outline, outlineColor),
          }}
        >
          {SAMPLE_TEXT}
        </div>
      </div>
    </div>
  );
}
