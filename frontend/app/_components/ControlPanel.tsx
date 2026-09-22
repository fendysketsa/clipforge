import {
  Bot,
  BookOpen,
  Captions,
  Check,
  ChevronDown,
  Clock3,
  Focus,
  Film,
  Gauge,
  Scissors,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Image as ImageIcon,
  UploadCloud,
  WandSparkles,
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

const CAPTION_POSITIONS: { value: CaptionPosition; label: string }[] = [
  { value: "upper", label: "Atas" },
  { value: "center", label: "Tengah" },
  { value: "bottom", label: "Bawah" },
];

function ToggleCard({ checked, description, disabled, icon, label, onChange }: {
  checked: boolean;
  description: string;
  disabled: boolean;
  icon: ReactNode;
  label: string;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className={`shortToggle${checked ? " active" : ""}`}>
      <span className="shortToggleIcon">{icon}</span>
      <span><strong>{label}</strong><small>{description}</small></span>
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} />
      <i aria-hidden="true" />
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
  const disabled = isBusy || isSubmitting;
  const isLong = clipMode === "highlight_5m";
  const targetMinutes = Math.round(compilationTargetSeconds / 60);
  const selectedQuality = VIDEO_QUALITY_OPTIONS.find((option) => option.value === videoQuality);
  const preset = cropMode === "streamer"
    ? "split"
    : captionPosition === "center" && captionFontSize >= 11
      ? "punchy"
      : "clean";

  const applyPreset = (next: "clean" | "punchy" | "split") => {
    onAiEnabledChange(true);
    onBurnSubtitlesChange(true);
    if (next === "clean") {
      onCropModeChange("person");
      onCaptionPositionChange("bottom");
      onCaptionFontSizeChange(8);
      onVideoQualityChange("standard");
    } else if (next === "punchy") {
      onCropModeChange("person");
      onCaptionPositionChange("center");
      onCaptionFontSizeChange(12);
      onVideoQualityChange("high");
    } else {
      onCropModeChange("streamer");
      onCaptionPositionChange("bottom");
      onCaptionFontSizeChange(9);
      onVideoQualityChange("high");
    }
  };

  return (
    <details className="panel shortPolish" id="production-settings">
      <summary className="shortPolishSummary">
        <span className="shortPolishIcon"><WandSparkles size={19} /></span>
        <span>
          <small>{isLong ? "POLISH LONG VIDEO" : "POLISH SHORT"}</small>
          <strong>{isLong ? "Struktur & watch time" : "Gaya edit"}</strong>
          <em>{isLong ? "Susun cerita, chapter, dan packaging YouTube." : "Default sudah siap. Buka kalau ingin mengubah karakter hasil."}</em>
        </span>
        <span className="shortPolishSnapshot">
          <b>{isLong ? `Story Arc · ${targetMinutes} menit` : preset === "clean" ? "Clean Focus" : preset === "punchy" ? "Punchy" : "Split Screen"}</b>
          <small>{isLong ? "16:9 · chapter lengkap" : `${minDuration}–${maxDuration} dtk`} · {selectedQuality?.label}</small>
        </span>
        <ChevronDown size={18} />
      </summary>

      <div className="shortPolishBody">
        <div className="autoPolishBanner">
          <span><Sparkles size={18} /></span>
          <div>
            <strong>{isLong ? "Long-form Director aktif" : "Auto Polish aktif"}</strong>
            <small>{isLong ? "Cold open, story arc, chapter cards, cinematic grading, thumbnail, dan audit watch-time diterapkan otomatis." : "Hook-first cut, smart zoom, beat edit, audio leveling, dan audit retention diterapkan otomatis."}</small>
          </div>
          <b><Check size={14} /> ON</b>
        </div>

        {isLong ? (
          <>
            <section className="polishSection">
              <header><span>01</span><div><strong>Mesin retention long-form</strong><small>Setiap bagian punya fungsi dalam perjalanan penonton.</small></div></header>
              <div className="longFeatureGrid">
                <span><Sparkles size={17} /><b>Cold open<small>Segmen terkuat membuka video</small></b></span>
                <span><BookOpen size={17} /><b>Chapter story<small>Konteks → tensi → payoff</small></b></span>
                <span><ImageIcon size={17} /><b>CTR package<small>Thumbnail dan judul satu janji</small></b></span>
              </div>
            </section>

            <section className="polishSection">
              <header><span>02</span><div><strong>Target panjang cerita</strong><small>Lebih panjang hanya jika materi memang cukup kuat.</small></div></header>
              <div className="longDurationGrid" role="group" aria-label="Pilih panjang Long Highlight">
                {[300, 480, 600].map((seconds) => (
                  <button className={compilationTargetSeconds === seconds ? "active" : ""} type="button" key={seconds} disabled={disabled} onClick={() => onCompilationTargetSecondsChange(seconds)}>
                    <Film size={16} /><span><strong>{seconds / 60} menit</strong><small>{seconds === 300 ? "Padat" : seconds === 480 ? "Seimbang" : "Mendalam"}</small></span>
                    {compilationTargetSeconds === seconds ? <Check size={15} /> : null}
                  </button>
                ))}
              </div>
              {videoDuration ? <p className="targetSourceNote"><Clock3 size={13} /> Sumber {Math.round(videoDuration / 60)} menit · AI hanya mengambil chapter yang lolos quality gate</p> : null}
            </section>
          </>
        ) : (
          <>
            <section className="polishSection">
              <header><span>01</span><div><strong>Pilih rasa edit</strong><small>Satu klik mengatur framing, caption, dan kualitas.</small></div></header>
              <div className="editPresetGrid">
                <button className={preset === "clean" ? "active" : ""} type="button" disabled={disabled} onClick={() => applyPreset("clean")}>
                  <Focus size={18} /><span><strong>Clean Focus</strong><small>Natural, fokus wajah</small></span>{preset === "clean" ? <Check size={16} /> : null}
                </button>
                <button className={preset === "punchy" ? "active" : ""} type="button" disabled={disabled} onClick={() => applyPreset("punchy")}>
                  <Sparkles size={18} /><span><strong>Punchy</strong><small>Caption besar, ritme cepat</small></span>{preset === "punchy" ? <Check size={16} /> : null}
                </button>
                <button className={preset === "split" ? "active" : ""} type="button" disabled={disabled} onClick={() => applyPreset("split")}>
                  <Scissors size={18} /><span><strong>Split Screen</strong><small>Pembicara + layar</small></span>{preset === "split" ? <Check size={16} /> : null}
                </button>
              </div>
            </section>

            <section className="polishSection">
              <header><span>02</span><div><strong>Target output</strong><small>Biarkan jumlah 0 agar AI menentukan otomatis.</small></div></header>
              <div className="shortTargetGrid">
                <label><span>Durasi minimum</span><div><input type="number" min={5} max={179} value={minDuration} disabled={disabled} onChange={(event) => onMinDurationChange(Number(event.target.value))} /><small>detik</small></div></label>
                <label><span>Durasi maksimum</span><div><input type="number" min={10} max={180} value={maxDuration} disabled={disabled} onChange={(event) => onMaxDurationChange(Number(event.target.value))} /><small>detik</small></div></label>
                <label><span>Jumlah Short</span><div><input type="number" min={0} max={maxClips ?? 12} value={targetClips} disabled={disabled} onChange={(event) => onTargetClipsChange(Number(event.target.value))} /><small>{targetClips === 0 ? "auto" : `maks. ${maxClips ?? 12}`}</small></div></label>
              </div>
              {videoDuration ? <p className="targetSourceNote"><Clock3 size={13} /> Sumber {Math.round(videoDuration / 60)} menit · batas jumlah disesuaikan otomatis</p> : null}
            </section>
          </>
        )}

        <details className="polishAdvanced">
          <summary><span><SlidersHorizontal size={16} /> Detail lanjutan</span><small>Subtitle, kualitas, dan upload</small><ChevronDown size={16} /></summary>
          <div className="polishAdvancedBody">
            <div className="shortToggleGrid">
              <ToggleCard checked={burnSubtitles} disabled={disabled} icon={<Captions size={17} />} label="Subtitle" description="Burn-in ke video" onChange={onBurnSubtitlesChange} />
              <ToggleCard checked={aiEnabled} disabled={disabled} icon={<Bot size={17} />} label="Seleksi AI" description={isLong ? "Chapter & alur" : "Hook & konteks"} onChange={onAiEnabledChange} />
              <ToggleCard checked={autoUploadYoutube} disabled={disabled} icon={<UploadCloud size={17} />} label="Antrean YouTube" description="Tetap melalui review" onChange={onAutoUploadYoutubeChange} />
            </div>

            <div className="advancedFields">
              <label><span><Gauge size={14} /> Kualitas</span><select value={videoQuality} disabled={disabled} onChange={(event) => onVideoQualityChange(event.target.value as VideoQuality)}>{VIDEO_QUALITY_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label} — {option.help}</option>)}</select></label>
              <label><span>Font caption</span><select value={captionFont} disabled={disabled} onChange={(event) => onCaptionFontChange(event.target.value as CaptionFont)}>{CAPTION_FONTS.map((font) => <option key={font.value} value={font.value}>{font.label}</option>)}</select></label>
              <label><span>Posisi caption</span><select value={captionPosition} disabled={disabled} onChange={(event) => onCaptionPositionChange(event.target.value as CaptionPosition)}>{CAPTION_POSITIONS.map((position) => <option key={position.value} value={position.value}>{position.label}</option>)}</select></label>
              <label><span>Ukuran caption</span><input type="number" min={CAPTION_FONT_SIZE_MIN} max={CAPTION_FONT_SIZE_MAX} value={captionFontSize} disabled={disabled} onChange={(event) => onCaptionFontSizeChange(Number(event.target.value))} /></label>
              <label className="colorInput"><span>Warna teks</span><input type="color" value={captionColor} disabled={disabled} onChange={(event) => onCaptionColorChange(event.target.value)} /></label>
              <label><span>Outline</span><input type="number" min={0} max={4} step={0.5} value={captionOutline} disabled={disabled} onChange={(event) => onCaptionOutlineChange(Number(event.target.value))} /></label>
              <label className="colorInput"><span>Warna outline</span><input type="color" value={captionOutlineColor} disabled={disabled} onChange={(event) => onCaptionOutlineColorChange(event.target.value)} /></label>
            </div>
          </div>
        </details>

        <footer className="shortPolishFooter"><ShieldCheck size={15} /><span>{isLong ? "Long Highlight menyertakan thumbnail 16:9 dan tetap masuk review sebelum publikasi." : "Hasil selalu masuk tahap review sebelum publikasi."}</span></footer>
      </div>
    </details>
  );
}
