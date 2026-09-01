import {
  Bot,
  Captions,
  ChevronDown,
  Film,
  Gauge,
  Scissors,
  ShieldCheck,
  SlidersHorizontal,
  UploadCloud,
} from "lucide-react";
import type { ReactNode } from "react";
import {
  CAPTION_FONT_SIZE_MAX,
  CAPTION_FONT_SIZE_MIN,
  CAPTION_FONTS,
  VIDEO_QUALITY_OPTIONS,
} from "../../lib/constants";
import type {
  CaptionFont,
  CaptionPosition,
  ClipMode,
  CropMode,
  VideoQuality,
} from "../../types/clip.type";

type ControlPanelProps = {
  clipMode: ClipMode;
  cropMode: CropMode;
  isBusy: boolean;
  isSubmitting: boolean;
  maxDuration: number;
  minDuration: number;
  compilationTargetSeconds: number;
  targetClips: number;
  maxClips: number | null;
  videoDuration: number | null;
  videoQuality: VideoQuality;
  burnSubtitles: boolean;
  captionFontSize: number;
  captionPosition: CaptionPosition;
  captionColor: string;
  captionFont: CaptionFont;
  captionOutline: number;
  captionOutlineColor: string;
  aiEnabled: boolean;
  autoUploadYoutube: boolean;
  onCompilationTargetSecondsChange: (value: number) => void;
  onTargetClipsChange: (value: number) => void;
  onVideoQualityChange: (value: VideoQuality) => void;
  onCropModeChange: (value: CropMode) => void;
  onMaxDurationChange: (value: number) => void;
  onMinDurationChange: (value: number) => void;
  onBurnSubtitlesChange: (value: boolean) => void;
  onCaptionFontSizeChange: (value: number) => void;
  onCaptionPositionChange: (value: CaptionPosition) => void;
  onCaptionColorChange: (value: string) => void;
  onCaptionFontChange: (value: CaptionFont) => void;
  onCaptionOutlineChange: (value: number) => void;
  onCaptionOutlineColorChange: (value: string) => void;
  onAiEnabledChange: (value: boolean) => void;
  onAutoUploadYoutubeChange: (value: boolean) => void;
};

const CROP_OPTIONS: { value: CropMode; label: string; help: string }[] = [
  { value: "person", label: "Ikuti Wajah", help: "Fokus pembicara" },
  { value: "center", label: "Tengah", help: "Crop stabil" },
  { value: "streamer", label: "Split", help: "Pembicara + layar" },
];

const CAPTION_POSITIONS: { value: CaptionPosition; label: string }[] = [
  { value: "upper", label: "Atas" },
  { value: "center", label: "Tengah" },
  { value: "bottom", label: "Bawah" },
];

function ToggleCard({
  checked,
  description,
  disabled,
  icon,
  label,
  onChange,
}: {
  checked: boolean;
  description: string;
  disabled: boolean;
  icon: ReactNode;
  label: string;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className={`productionToggle${checked ? " active" : ""}`}>
      <span className="productionToggleIcon">{icon}</span>
      <span className="productionToggleCopy">
        <strong>{label}</strong>
        <small>{description}</small>
      </span>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className="productionSwitch" aria-hidden="true" />
    </label>
  );
}

export function ControlPanel({
  clipMode,
  cropMode,
  isBusy,
  isSubmitting,
  maxDuration,
  minDuration,
  compilationTargetSeconds,
  targetClips,
  maxClips,
  videoDuration,
  videoQuality,
  burnSubtitles,
  captionFontSize,
  captionPosition,
  captionColor,
  captionFont,
  captionOutline,
  captionOutlineColor,
  aiEnabled,
  autoUploadYoutube,
  onCompilationTargetSecondsChange,
  onTargetClipsChange,
  onVideoQualityChange,
  onCropModeChange,
  onMaxDurationChange,
  onMinDurationChange,
  onBurnSubtitlesChange,
  onCaptionFontSizeChange,
  onCaptionPositionChange,
  onCaptionColorChange,
  onCaptionFontChange,
  onCaptionOutlineChange,
  onCaptionOutlineColorChange,
  onAiEnabledChange,
  onAutoUploadYoutubeChange,
}: ControlPanelProps) {
  const controlsDisabled = isBusy || isSubmitting;
  const isLongStory = clipMode === "highlight_5m";
  const selectedQuality = VIDEO_QUALITY_OPTIONS.find((option) => option.value === videoQuality);
  const targetMinutes = Math.round(compilationTargetSeconds / 60);

  return (
    <section className="panel controlPanel productionSettings" aria-labelledby="production-settings-title">
      <header className="productionHeader">
        <span className="productionHeaderIcon"><SlidersHorizontal size={19} /></span>
        <div>
          <span className="panelEyebrow">Pengaturan opsional</span>
          <h2 id="production-settings-title">Poles Hasil</h2>
          <p>Default sudah siap. Ubah hanya bila hasil membutuhkan karakter berbeda.</p>
        </div>
        <span className="activeFormatBadge">
          {isLongStory ? <Film size={15} /> : <Scissors size={15} />}
          {isLongStory ? "Long Story · 16:9" : "Clip Pendek · 9:16"}
        </span>
      </header>

      <div className="productionSummary" aria-label="Ringkasan pengaturan aktif">
        <span><Gauge size={14} /> {selectedQuality?.label ?? "Standar"}</span>
        <span>
          {isLongStory
            ? `${targetMinutes} menit target cerita`
            : `${minDuration}–${maxDuration} detik per clip`}
        </span>
        <span>{burnSubtitles ? "Subtitle aktif" : "Tanpa subtitle"}</span>
      </div>

      <div className="productionGroup">
        <div className="productionGroupHeading">
          <div>
            <span>01</span>
            <h3>Kualitas & durasi</h3>
          </div>
          <p>{selectedQuality?.help}</p>
        </div>

        <div className="qualityCards" role="group" aria-label="Kualitas video">
          {VIDEO_QUALITY_OPTIONS.map((option) => (
            <button
              key={option.value}
              className={videoQuality === option.value ? "active" : ""}
              type="button"
              disabled={controlsDisabled}
              onClick={() => onVideoQualityChange(option.value)}
            >
              <strong>{option.label}</strong>
              <small>{option.value === "standard" ? "Cepat" : option.value === "high" ? "Seimbang" : "Detail"}</small>
            </button>
          ))}
        </div>

        {isLongStory ? (
          <label className="productionRange">
            <span>
              <strong>Target cerita</strong>
              <b>{targetMinutes} menit</b>
            </span>
            <input
              type="range"
              min={300}
              max={600}
              step={60}
              value={compilationTargetSeconds}
              disabled={controlsDisabled}
              onChange={(event) => onCompilationTargetSecondsChange(Number(event.target.value))}
            />
            <small>5 menit <i /> 10 menit</small>
          </label>
        ) : (
          <div className="durationGrid">
            <label>
              <span>Minimum</span>
              <div><input type="number" min={5} max={179} value={minDuration} disabled={controlsDisabled} onChange={(event) => onMinDurationChange(Number(event.target.value))} /><small>detik</small></div>
            </label>
            <label>
              <span>Maksimum</span>
              <div><input type="number" min={10} max={180} value={maxDuration} disabled={controlsDisabled} onChange={(event) => onMaxDurationChange(Number(event.target.value))} /><small>detik</small></div>
            </label>
            <label>
              <span>Jumlah clip</span>
              <div><input type="number" min={0} max={maxClips ?? 50} value={targetClips} disabled={controlsDisabled} onChange={(event) => onTargetClipsChange(Number(event.target.value))} /><small>{targetClips === 0 ? "auto" : `maks. ${maxClips ?? 50}`}</small></div>
            </label>
          </div>
        )}
      </div>

      {!isLongStory ? (
        <div className="productionGroup">
          <div className="productionGroupHeading">
            <div><span>02</span><h3>Framing vertikal</h3></div>
            <p>AI menjaga subjek tetap berada di area aman 9:16.</p>
          </div>
          <div className="cropCards" role="group" aria-label="Mode framing">
            {CROP_OPTIONS.map((option) => (
              <button
                key={option.value}
                className={cropMode === option.value ? "active" : ""}
                type="button"
                disabled={controlsDisabled}
                onClick={() => onCropModeChange(option.value)}
              >
                <strong>{option.label}</strong>
                <small>{option.help}</small>
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="longStoryNote">
          <Film size={18} />
          <div><strong>Komposisi sinematik otomatis</strong><span>Long Story mempertahankan rasio 16:9 dan alur kronologis tanpa filler.</span></div>
        </div>
      )}

      <div className="productionToggleGrid">
        <ToggleCard
          checked={burnSubtitles}
          disabled={controlsDisabled}
          icon={<Captions size={18} />}
          label="Subtitle"
          description="Caption otomatis siap review"
          onChange={onBurnSubtitlesChange}
        />
        <ToggleCard
          checked={aiEnabled}
          disabled={controlsDisabled}
          icon={<Bot size={18} />}
          label="Seleksi AI"
          description="Pilih momen dan susun konteks"
          onChange={onAiEnabledChange}
        />
        <ToggleCard
          checked={autoUploadYoutube}
          disabled={controlsDisabled}
          icon={<UploadCloud size={18} />}
          label="Siapkan YouTube"
          description="Masuk antrean upload setelah review"
          onChange={onAutoUploadYoutubeChange}
        />
      </div>

      {burnSubtitles ? (
        <details className="captionDisclosure">
          <summary><span><Captions size={16} /> Gaya subtitle</span><ChevronDown size={16} /></summary>
          <div className="captionCompactGrid">
            <label>
              <span>Font</span>
              <select value={captionFont} disabled={controlsDisabled} onChange={(event) => onCaptionFontChange(event.target.value as CaptionFont)}>
                {CAPTION_FONTS.map((font) => <option key={font.value} value={font.value}>{font.label}</option>)}
              </select>
            </label>
            <label>
              <span>Posisi</span>
              <select value={captionPosition} disabled={controlsDisabled} onChange={(event) => onCaptionPositionChange(event.target.value as CaptionPosition)}>
                {CAPTION_POSITIONS.map((position) => <option key={position.value} value={position.value}>{position.label}</option>)}
              </select>
            </label>
            <label>
              <span>Ukuran</span>
              <input type="number" min={CAPTION_FONT_SIZE_MIN} max={CAPTION_FONT_SIZE_MAX} value={captionFontSize} disabled={controlsDisabled} onChange={(event) => onCaptionFontSizeChange(Number(event.target.value))} />
            </label>
            <label className="colorField">
              <span>Warna teks</span>
              <input type="color" value={captionColor} disabled={controlsDisabled} onChange={(event) => onCaptionColorChange(event.target.value)} />
            </label>
            <label>
              <span>Outline</span>
              <input type="number" min={0} max={4} step={0.5} value={captionOutline} disabled={controlsDisabled} onChange={(event) => onCaptionOutlineChange(Number(event.target.value))} />
            </label>
            <label className="colorField">
              <span>Warna outline</span>
              <input type="color" value={captionOutlineColor} disabled={controlsDisabled} onChange={(event) => onCaptionOutlineColorChange(event.target.value)} />
            </label>
          </div>
        </details>
      ) : null}

      <footer className="productionFooter">
        <ShieldCheck size={16} />
        <span>
          {videoDuration
            ? "Pengaturan tersimpan untuk sumber yang sudah terdeteksi."
            : "Tempel link dan mulai proses dari Quick Start di atas."}
        </span>
        <a href="#quick-start-title">Kembali ke Quick Start</a>
      </footer>
    </section>
  );
}
