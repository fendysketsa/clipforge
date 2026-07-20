import { Link2, Loader2, Play, RefreshCw, Scissors, ShieldCheck, Sparkles, Type, Upload, UploadCloud } from "lucide-react";
import type { LocalLlmProvider } from "../../lib/apiClient";
import {
  CAPTION_FONT_SIZE_MAX,
  CAPTION_FONT_SIZE_MIN,
  CAPTION_FONTS,
  LOCAL_LLM_PRESETS,
  VIDEO_QUALITY_OPTIONS,
} from "../../lib/constants";
import type {
  CamCorner,
  CaptionFont,
  CaptionPosition,
  ClipMode,
  CropMode,
  SourceMode,
  VideoQuality,
} from "../../types/clip.type";
import { CaptionPreview } from "./CaptionPreview";

const CAM_CORNER_OPTIONS: { value: CamCorner; label: string }[] = [
  { value: "auto", label: "Auto" },
  { value: "tl", label: "Kiri Atas" },
  { value: "tr", label: "Kanan Atas" },
  { value: "bl", label: "Kiri Bawah" },
  { value: "br", label: "Kanan Bawah" },
];

type ControlPanelProps = {
  clipMode: ClipMode;
  onClipModeChange: (value: ClipMode) => void;
  cropMode: CropMode;
  error: string;
  isBusy: boolean;
  isSubmitting: boolean;
  isAutoViralRunning: boolean;
  sourceMode: SourceMode;
  uploadFileName: string;
  uploadPreviewUrl: string;
  isUploading: boolean;
  camCorner: CamCorner;
  onCamCornerChange: (value: CamCorner) => void;
  onSourceModeChange: (mode: SourceMode) => void;
  onUploadFileChange: (file: File | null) => void;
  maxDuration: number;
  minDuration: number;
  targetClips: number;
  maxClips: number | null;
  videoDuration: number | null;
  videoQuality: VideoQuality;
  onVideoQualityChange: (value: VideoQuality) => void;
  onTargetClipsChange: (value: number) => void;
  burnSubtitles: boolean;
  captionFontSize: number;
  captionPosition: CaptionPosition;
  captionColor: string;
  captionFont: CaptionFont;
  captionOutline: number;
  captionOutlineColor: string;
  onCaptionFontChange: (value: CaptionFont) => void;
  onCaptionOutlineChange: (value: number) => void;
  onCaptionOutlineColorChange: (value: string) => void;
  aiEnabled: boolean;
  aiBaseUrl: string;
  aiModel: string;
  aiApiKey: string;
  aiModels: string[];
  isLoadingModels: boolean;
  isDiscoveringLlms: boolean;
  localLlmProviders: LocalLlmProvider[];
  onLoadModels: () => void;
  onDiscoverLocalLlms: () => void;
  onSelectLocalProvider: (provider: LocalLlmProvider) => void;
  requiredHashtags: string;
  requireCreativeCommons: boolean;
  autoUploadYoutube: boolean;
  onRequiredHashtagsChange: (value: string) => void;
  onRequireCreativeCommonsChange: (value: boolean) => void;
  onAutoUploadYoutubeChange: (value: boolean) => void;
  onCropModeChange: (mode: CropMode) => void;
  onMaxDurationChange: (value: number) => void;
  onMinDurationChange: (value: number) => void;
  onBurnSubtitlesChange: (value: boolean) => void;
  onCaptionFontSizeChange: (value: number) => void;
  onCaptionPositionChange: (value: CaptionPosition) => void;
  onCaptionColorChange: (value: string) => void;
  onAiEnabledChange: (value: boolean) => void;
  onAiBaseUrlChange: (value: string) => void;
  onAiModelChange: (value: string) => void;
  onAiApiKeyChange: (value: string) => void;
  onStartAutoViral: () => void;
  onStartJob: () => void;
  onUrlChange: (value: string) => void;
  autoViralMessage: string;
  url: string;
};

export function ControlPanel({
  clipMode,
  onClipModeChange,
  cropMode,
  error,
  isBusy,
  isSubmitting,
  isAutoViralRunning,
  sourceMode,
  uploadFileName,
  uploadPreviewUrl,
  isUploading,
  camCorner,
  onCamCornerChange,
  onSourceModeChange,
  onUploadFileChange,
  maxDuration,
  minDuration,
  targetClips,
  maxClips,
  videoDuration,
  videoQuality,
  onVideoQualityChange,
  onTargetClipsChange,
  burnSubtitles,
  captionFontSize,
  captionPosition,
  captionColor,
  aiEnabled,
  aiBaseUrl,
  aiModel,
  aiApiKey,
  aiModels,
  isLoadingModels,
  isDiscoveringLlms,
  localLlmProviders,
  onLoadModels,
  onDiscoverLocalLlms,
  onSelectLocalProvider,
  requiredHashtags,
  requireCreativeCommons,
  autoUploadYoutube,
  onRequiredHashtagsChange,
  onRequireCreativeCommonsChange,
  onAutoUploadYoutubeChange,
  onCropModeChange,
  onMaxDurationChange,
  onMinDurationChange,
  onBurnSubtitlesChange,
  onCaptionFontSizeChange,
  onCaptionPositionChange,
  captionFont,
  captionOutline,
  captionOutlineColor,
  onCaptionFontChange,
  onCaptionOutlineChange,
  onCaptionOutlineColorChange,
  onCaptionColorChange,
  onAiEnabledChange,
  onAiBaseUrlChange,
  onAiModelChange,
  onAiApiKeyChange,
  onStartAutoViral,
  onStartJob,
  onUrlChange,
  autoViralMessage,
  url,
}: ControlPanelProps) {
  const hasSource = sourceMode === "url" ? Boolean(url.trim()) : Boolean(uploadFileName);
  const isStartDisabled = isSubmitting || isBusy || isUploading || !hasSource;
  const isProcessing = isSubmitting || isBusy;
  const localNoKeyBaseUrls = new Set<string>(
    LOCAL_LLM_PRESETS.filter((preset) => preset.label !== "Custom").map((preset) => preset.baseUrl),
  );
  const shouldShowApiKey = Boolean(aiApiKey.trim()) || !localNoKeyBaseUrls.has(aiBaseUrl);

  return (
    <section className="panel controlPanel">
      <div className="panelHeader">
        <Scissors size={20} />
        <h2>Potong Video</h2>
      </div>

      <div className="segmentedField">
        <span>Sumber Video</span>
        <div className="segmentedControl" role="group" aria-label="Sumber video">
          <button
            className={sourceMode === "url" ? "active" : ""}
            type="button"
            onClick={() => onSourceModeChange("url")}
          >
            <Link2 size={15} /> Link YouTube
          </button>
          <button
            className={sourceMode === "upload" ? "active" : ""}
            type="button"
            onClick={() => onSourceModeChange("upload")}
          >
            <Upload size={15} /> Upload Video
          </button>
        </div>
      </div>

      {sourceMode === "url" ? (
        <label className="field wide">
          <span>Link Video YouTube</span>
          <input
            value={url}
            onChange={(event) => onUrlChange(event.target.value)}
            placeholder="https://www.youtube.com/watch?v=..."
          />
          <p className="field-help">Pastikan video memiliki percakapan yang jelas untuk hasil transkripsi terbaik.</p>
        </label>
      ) : (
        <label className="field wide">
          <span>Upload File Video</span>
          <input
            type="file"
            accept="video/mp4,video/quicktime,video/x-matroska,video/webm,.mp4,.mov,.mkv,.webm,.m4v,.avi"
            onChange={(event) => onUploadFileChange(event.target.files?.[0] ?? null)}
          />
          <p className="field-help">
            {isUploading
              ? "Mengunggah video..."
              : uploadFileName
                ? `Siap: ${uploadFileName}`
                : "Format didukung: MP4, MOV, MKV, WEBM, M4V, AVI. Gunakan video milik sendiri atau yang sudah punya izin."}
          </p>
          {uploadPreviewUrl ? (
            <video className="uploadPreview" src={uploadPreviewUrl} controls preload="metadata" />
          ) : null}
        </label>
      )}

      {sourceMode === "url" ? (
        <div className="aiBlock">
          <label className="aiToggle">
            <span className="aiToggleLabel">
              <ShieldCheck size={16} />
              Wajib Creative Commons
            </span>
            <input
              type="checkbox"
              checked={requireCreativeCommons || sourceMode === "url"}
              disabled
              onChange={(event) => onRequireCreativeCommonsChange(event.target.checked)}
            />
          </label>
          <p className="field-help">Dikunci aktif: video non-CC akan dibatalkan sebelum download agar sumber lebih aman untuk dimodifikasi.</p>
        </div>
      ) : null}

      <div className="segmentedField">
        <span>Model Clip</span>
        <div className="segmentedControl" role="group" aria-label="Model clip">
          <button
            className={clipMode === "short" ? "active" : ""}
            type="button"
            onClick={() => onClipModeChange("short")}
          >
            Clip Pendek
          </button>
          <button
            className={clipMode === "highlight_5m" ? "active" : ""}
            type="button"
            onClick={() => onClipModeChange("highlight_5m")}
          >
            Highlight 5 Menit
          </button>
        </div>
        <p className="field-help">
          {clipMode === "highlight_5m"
            ? "Hanya kompilasi: AI memilih poin terpenting, menyusunnya kronologis, lalu menggabungkan menjadi satu video sekitar 5 menit."
            : "Hanya membuat clip vertikal maksimal 60 detik. Hook, animasi, sound effect, payoff, dan penutup loop diterapkan dalam satu render."}
        </p>
      </div>

      <div className="gridFields">
        <label className="field">
          <span>Durasi Minimum</span>
          <input
            min={5}
            max={clipMode === "short" ? 59 : 600}
            type="number"
            value={minDuration}
            onChange={(event) => onMinDurationChange(Number(event.target.value))}
          />
        </label>
        <label className="field">
          <span>Durasi Maksimum</span>
          <input
            min={10}
            max={clipMode === "short" ? 60 : 600}
            type="number"
            value={maxDuration}
            onChange={(event) => onMaxDurationChange(Number(event.target.value))}
          />
        </label>
      </div>

      {clipMode === "short" ? (
        <label className="field wide">
          <span>Target Jumlah Clip</span>
          <input
            min={0}
            max={maxClips ?? 50}
            type="number"
            value={targetClips || ""}
            placeholder="Auto (kosongkan = otomatis)"
            onChange={(event) => onTargetClipsChange(Math.max(0, Number(event.target.value)))}
          />
          <p className="field-help">
            {videoDuration
              ? `Durasi video ~${Math.round(videoDuration)}s. Maks ${maxClips} clip (durasi min × jumlah ≤ 80% video).`
              : "Kosongkan untuk otomatis. Akan disesuaikan dengan panjang video."}
            {maxClips !== null && targetClips > maxClips
              ? ` Target ${targetClips} melebihi batas, akan dipangkas ke ${maxClips}.`
              : ""}
          </p>
        </label>
      ) : (
        <div className="modeNotice">
          <strong>Target output: ±5:00 menit</strong>
          <span>
            {videoDuration && videoDuration < 300
              ? "Video sumber kurang dari 5 menit, sehingga hasil bisa lebih pendek."
              : "Bagian filler, intro panjang, dan pengulangan akan dilewati."}
          </span>
        </div>
      )}

      <div className="segmentedField">
        <span>Kualitas Output</span>
        <div className="segmentedControl" role="group" aria-label="Kualitas output video">
          {VIDEO_QUALITY_OPTIONS.map((option) => (
            <button
              key={option.value}
              className={videoQuality === option.value ? "active" : ""}
              type="button"
              onClick={() => onVideoQualityChange(option.value)}
              title={option.help}
            >
              {option.label}
            </button>
          ))}
        </div>
        <p className="field-help">
          {VIDEO_QUALITY_OPTIONS.find((option) => option.value === videoQuality)?.help}
        </p>
      </div>

      <div className="segmentedField">
        <span>Mode Crop</span>
        <div className="segmentedControl" role="group" aria-label="Mode crop video">
          <button
            className={cropMode === "center" ? "active" : ""}
            type="button"
            onClick={() => onCropModeChange("center")}
          >
            Center
          </button>
          <button
            className={cropMode === "person" ? "active" : ""}
            type="button"
            onClick={() => onCropModeChange("person")}
          >
            Follow Person
          </button>
          <button
            className={cropMode === "streamer" ? "active" : ""}
            type="button"
            onClick={() => onCropModeChange("streamer")}
          >
            Streamer
          </button>
        </div>
      </div>

      {cropMode === "streamer" ? (
        <div className="segmentedField">
          <span>Posisi Webcam di Sumber</span>
          <div className="segmentedControl segmentedControl--grid" role="group" aria-label="Posisi webcam">
            {CAM_CORNER_OPTIONS.map((option) => (
              <button
                key={option.value}
                className={camCorner === option.value ? "active" : ""}
                type="button"
                onClick={() => onCamCornerChange(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
          <p className="field-help">
            Webcam di-crop dari pojok ini lalu ditumpuk di atas gameplay (vertikal 9:16).
          </p>
        </div>
      ) : null}

      <div className="aiBlock">
        <label className="aiToggle">
          <span className="aiToggleLabel">
            <Type size={16} />
            Caption Otomatis
          </span>
          <input
            type="checkbox"
            checked={burnSubtitles}
            onChange={(event) => onBurnSubtitlesChange(event.target.checked)}
          />
        </label>
        <p className="field-help">
          Teks dibuat ringkas dan proporsional, dengan background gradient-blur aktif secara default.
        </p>

        {burnSubtitles ? (
          <div className="captionFields">
            <div className="captionControls">
              <div className="segmentedField">
                <span>
                  Ukuran Font: <strong>{captionFontSize}</strong>
                </span>
                <input
                  className="fontSlider"
                  type="range"
                  min={CAPTION_FONT_SIZE_MIN}
                  max={CAPTION_FONT_SIZE_MAX}
                  step={1}
                  value={captionFontSize}
                  onChange={(event) => onCaptionFontSizeChange(Number(event.target.value))}
                  aria-label="Ukuran font caption"
                />
                <div className="sliderTicks">
                  <span>Kecil</span>
                  <span>Sedang</span>
                  <span>Besar</span>
                </div>
              </div>

              <div className="segmentedField">
                <span>Posisi</span>
                <div className="segmentedControl" role="group" aria-label="Posisi caption">
                  <button
                    className={captionPosition === "upper" ? "active" : ""}
                    type="button"
                    onClick={() => onCaptionPositionChange("upper")}
                  >
                    Atas aman
                  </button>
                  <button
                    className={captionPosition === "center" ? "active" : ""}
                    type="button"
                    onClick={() => onCaptionPositionChange("center")}
                  >
                    Tengah
                  </button>
                  <button
                    className={captionPosition === "bottom" ? "active" : ""}
                    type="button"
                    onClick={() => onCaptionPositionChange("bottom")}
                  >
                    Bawah
                  </button>
                </div>
              </div>

              <label className="field">
                <span>Jenis Font</span>
                <select
                  className="fontSelect"
                  value={captionFont}
                  onChange={(event) => onCaptionFontChange(event.target.value as CaptionFont)}
                >
                  {CAPTION_FONTS.map((font) => (
                    <option key={font.value} value={font.value}>
                      {font.label}
                    </option>
                  ))}
                </select>
              </label>

              <div className="captionColorRow">
                <label className="field captionColorField">
                  <span>Warna Teks</span>
                  <input
                    type="color"
                    value={captionColor}
                    onChange={(event) => onCaptionColorChange(event.target.value.toUpperCase())}
                  />
                </label>
                <label className="field captionColorField">
                  <span>Warna Border</span>
                  <input
                    type="color"
                    value={captionOutlineColor}
                    onChange={(event) => onCaptionOutlineColorChange(event.target.value.toUpperCase())}
                  />
                </label>
              </div>

              <div className="segmentedField">
                <span>
                  Tebal Border: <strong>{captionOutline}</strong>
                </span>
                <input
                  className="fontSlider"
                  type="range"
                  min={0}
                  max={8}
                  step={0.5}
                  value={captionOutline}
                  onChange={(event) => onCaptionOutlineChange(Number(event.target.value))}
                  aria-label="Tebal border caption"
                />
                <div className="sliderTicks">
                  <span>Tanpa</span>
                  <span>Tebal</span>
                </div>
              </div>
            </div>

            <CaptionPreview
              fontSize={captionFontSize}
              position={captionPosition}
              color={captionColor}
              font={captionFont}
              outline={captionOutline}
              outlineColor={captionOutlineColor}
            />
          </div>
        ) : null}
      </div>

      <div className="aiBlock">
        <label className="aiToggle">
          <span className="aiToggleLabel">
            <Sparkles size={16} />
            AI Agent Pemilih Klip
          </span>
          <input
            type="checkbox"
            checked={aiEnabled}
            onChange={(event) => onAiEnabledChange(event.target.checked)}
          />
        </label>
        <p className="field-help">
          LLM menilai setiap kandidat dan memilih bagian paling kuat untuk dijadikan klip.
        </p>

        {aiEnabled ? (
          <div className="aiFields">
            <div className="llmPresetGrid" role="group" aria-label="Preset LLM lokal">
              {LOCAL_LLM_PRESETS.map((preset) => (
                <button
                  key={preset.baseUrl}
                  className={aiBaseUrl === preset.baseUrl ? "active" : ""}
                  type="button"
                  onClick={() => onAiBaseUrlChange(preset.baseUrl)}
                >
                  {preset.label}
                </button>
              ))}
            </div>
            <label className="field wide">
              <span>Endpoint (Base URL)</span>
              <input
                value={aiBaseUrl}
                onChange={(event) => onAiBaseUrlChange(event.target.value)}
                placeholder="http://localhost:20128/v1"
              />
              <p className="field-help">
                Jika aplikasi berjalan di Docker, endpoint localhost laptop otomatis diarahkan ke host.docker.internal.
              </p>
            </label>
            <button
              type="button"
              className="loadModelsButton discoverModelsButton"
              onClick={() => onDiscoverLocalLlms()}
              disabled={isDiscoveringLlms}
            >
              {isDiscoveringLlms ? <Loader2 className="spin" size={14} /> : <RefreshCw size={14} />}
              Cari LLM Lokal
            </button>
            {localLlmProviders.length > 0 ? (
              <div className="localProviderList">
                {localLlmProviders.map((provider) => (
                  <button
                    key={provider.base_url}
                    type="button"
                    onClick={() => onSelectLocalProvider(provider)}
                    className={aiBaseUrl === provider.base_url ? "active" : ""}
                  >
                    <strong>{provider.label}</strong>
                    <span>{provider.models.length} model</span>
                  </button>
                ))}
              </div>
            ) : null}
            {shouldShowApiKey ? (
              <label className="field wide">
                <span>API Key</span>
                <input
                  type="password"
                  value={aiApiKey}
                  onChange={(event) => onAiApiKeyChange(event.target.value)}
                  placeholder="sk-..."
                  autoComplete="off"
                />
              </label>
            ) : null}
            <label className="field wide">
              <span>Model</span>
              <div className="modelRow">
                {aiModels.length > 0 ? (
                  <select
                    className="fontSelect"
                    value={aiModel}
                    onChange={(event) => onAiModelChange(event.target.value)}
                  >
                    {!aiModels.includes(aiModel) ? <option value={aiModel}>{aiModel}</option> : null}
                    {aiModels.map((model) => (
                      <option key={model} value={model}>
                        {model}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    value={aiModel}
                    onChange={(event) => onAiModelChange(event.target.value)}
                    placeholder="Muat atau isi model Ollama"
                  />
                )}
                <button
                  type="button"
                  className="loadModelsButton"
                  onClick={onLoadModels}
                  disabled={isLoadingModels || !aiBaseUrl.trim()}
                >
                  {isLoadingModels ? <Loader2 className="spin" size={14} /> : <RefreshCw size={14} />}
                  {aiModels.length > 0 ? "Refresh" : "Muat Model"}
                </button>
              </div>
            </label>
            <label className="field wide">
              <span>Hashtag Wajib (opsional)</span>
              <input
                value={requiredHashtags}
                onChange={(event) => onRequiredHashtagsChange(event.target.value)}
                placeholder="fendyclipper, viral, fyp"
              />
              <p className="field-help">
                Hashtag ini selalu ditambahkan ke caption yang digenerate. Pisahkan dengan koma.
              </p>
            </label>
          </div>
        ) : null}
      </div>

      <div className="aiBlock">
        <label className="aiToggle">
          <span className="aiToggleLabel">
            <UploadCloud size={16} />
            Auto Upload YouTube
          </span>
          <input
            type="checkbox"
            checked={autoUploadYoutube}
            onChange={(event) => onAutoUploadYoutubeChange(event.target.checked)}
          />
        </label>
        <p className="field-help">
          Selesai clipping langsung antrekan 3 klip terbaik ke playlist Islam dengan judul, deskripsi singkat, dan hashtag otomatis.
        </p>
      </div>

      {error ? <p className="error">{error}</p> : null}

      <div className="aiBlock">
        <button className="ghostButton autoViralButton" type="button" disabled={isAutoViralRunning || isProcessing} onClick={onStartAutoViral}>
          {isAutoViralRunning ? <Loader2 className="spin" size={16} /> : <Sparkles size={16} />}
          {isAutoViralRunning ? "Auto Viral Berjalan..." : "Auto Viral CC"}
        </button>
        <p className="field-help">
          {autoViralMessage || "Cari luas 70+ tema Creative Commons—Islam, inspirasi, misteri, mitos/fakta, sejarah, dan horor relevan; prioritaskan 30 hari terbaru dan selalu lewati sumber lama."}
        </p>
      </div>

      <button className="primary" type="button" disabled={isStartDisabled} onClick={onStartJob}>
        {isProcessing ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
        {isProcessing ? "Sedang Memproses..." : "Mulai Potong Video"}
      </button>
    </section>
  );
}
