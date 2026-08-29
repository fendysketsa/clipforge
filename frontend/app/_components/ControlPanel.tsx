import { AlertTriangle, CheckCircle2, ChevronDown, ExternalLink, History, Link2, ListPlus, Loader2, Play, RefreshCw, Scissors, Search, ShieldCheck, Sparkles, Type, Upload, UploadCloud } from "lucide-react";
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
  BackgroundMode,
  CaptionFont,
  CaptionPosition,
  ClipMode,
  CropMode,
  IslamicContentNiche,
  SourceMode,
  SourceHistoryCheck,
  VideoQuality,
  ViralContentSource,
  ViralSearchFilters,
  VisualMode,
} from "../../types/clip.type";
import { CaptionPreview } from "./CaptionPreview";

const CAM_CORNER_OPTIONS: { value: CamCorner; label: string }[] = [
  { value: "auto", label: "Auto" },
  { value: "tl", label: "Kiri Atas" },
  { value: "tr", label: "Kanan Atas" },
  { value: "bl", label: "Kiri Bawah" },
  { value: "br", label: "Kanan Bawah" },
];

const ISLAMIC_NICHE_OPTIONS: { value: IslamicContentNiche; label: string; description: string }[] = [
  {
    value: "islamic_practical_life",
    label: "Islam Praktis Sehari-hari",
    description: "Orang tua, keluarga, sedekah, rezeki, ibadah, emosi, dan masalah hidup dengan jawaban yang konkret.",
  },
  {
    value: "auto",
    label: "Auto Niche Terbaik",
    description: "Membandingkan momentum, kecocokan tema, kebaruan, dan Bahasa Indonesia di semua niche lalu memilih yang terkuat.",
  },
  {
    value: "islamic_current_viral",
    label: "Isu Muslim & Kajian Viral Terkini",
    description: "Topik Muslim Indonesia yang ramai hari ini, minggu ini, dan paling baru.",
  },
  {
    value: "islamic_mental_health",
    label: "Kesehatan Mental & Ketenangan Jiwa",
    description: "Overthinking, ketenangan hati, tawakal, emosi, dan psikologi Islam.",
  },
  {
    value: "halal_wealth",
    label: "Rezeki Halal, Karier & Keuangan",
    description: "Rezeki halal, riba, investasi syariah, bisnis, dan etika kerja.",
  },
  {
    value: "fiqih_harian",
    label: "Fikih Harian & Perbaikan Salat",
    description: "Kesalahan salat, wudu, doa, dan pembelajaran ibadah praktis.",
  },
  {
    value: "islamic_history",
    label: "Sejarah Islam & Kisah Penuh Hikmah",
    description: "Kisah Nabi, Sahabat, peradaban, ilmuwan, dan hikmah sejarah.",
  },
];

function compactMetric(value: number) {
  return new Intl.NumberFormat("id-ID", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function shortDuration(value?: number | null) {
  if (!value) return "-";
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60);
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function freshnessLabel(ageDays?: number | null) {
  if (ageDays === null || ageDays === undefined) return "Tanggal belum tersedia";
  if (ageDays <= 0) return "Hari ini";
  if (ageDays === 1) return "Kemarin";
  if (ageDays <= 7) return `${ageDays} hari lalu`;
  if (ageDays <= 30) return `${Math.ceil(ageDays / 7)} minggu lalu`;
  return `${Math.ceil(ageDays / 30)} bulan lalu`;
}

type ControlPanelProps = {
  clipMode: ClipMode;
  onClipModeChange: (value: ClipMode) => void;
  cropMode: CropMode;
  error: string;
  isBusy: boolean;
  isSubmitting: boolean;
  isAutoViralRunning: boolean;
  isSearchingAutoContent: boolean;
  autoContentNiche: IslamicContentNiche;
  autoContentSources: ViralContentSource[];
  viralSearchFilters: ViralSearchFilters;
  selectedAutoContentUrls: string[];
  sourceMode: SourceMode;
  scriptText: string;
  onScriptTextChange: (value: string) => void;
  confirmLongAnimateRights: boolean;
  onConfirmLongAnimateRightsChange: (value: boolean) => void;
  uploadFileName: string;
  uploadPreviewUrl: string;
  isUploading: boolean;
  camCorner: CamCorner;
  onCamCornerChange: (value: CamCorner) => void;
  onSourceModeChange: (mode: SourceMode) => void;
  onUploadFileChange: (file: File | null) => void;
  maxDuration: number;
  minDuration: number;
  compilationTargetSeconds: number;
  onCompilationTargetSecondsChange: (value: number) => void;
  targetClips: number;
  maxClips: number | null;
  videoDuration: number | null;
  videoQuality: VideoQuality;
  visualMode: VisualMode;
  backgroundMode: BackgroundMode;
  onVideoQualityChange: (value: VideoQuality) => void;
  onVisualModeChange: (value: VisualMode) => void;
  onBackgroundModeChange: (value: BackgroundMode) => void;
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
  confirmSourceRights: boolean;
  autoUploadYoutube: boolean;
  onRequiredHashtagsChange: (value: string) => void;
  onRequireCreativeCommonsChange: (value: boolean) => void;
  onConfirmSourceRightsChange: (value: boolean) => void;
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
  onSearchAutoContent: () => void;
  onViralSearchFiltersChange: (value: ViralSearchFilters) => void;
  onAutoContentNicheChange: (value: IslamicContentNiche) => void;
  onToggleAutoContentSource: (sourceUrl: string) => void;
  onStartJob: () => void;
  onUrlChange: (value: string) => void;
  sourceHistory: SourceHistoryCheck | null;
  isCheckingSourceHistory: boolean;
  allowReprocessSource: boolean;
  onAllowReprocessSourceChange: (value: boolean) => void;
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
  isSearchingAutoContent,
  autoContentNiche,
  autoContentSources,
  viralSearchFilters,
  selectedAutoContentUrls,
  sourceMode,
  scriptText,
  onScriptTextChange,
  confirmLongAnimateRights,
  onConfirmLongAnimateRightsChange,
  uploadFileName,
  uploadPreviewUrl,
  isUploading,
  camCorner,
  onCamCornerChange,
  onSourceModeChange,
  onUploadFileChange,
  maxDuration,
  minDuration,
  compilationTargetSeconds,
  onCompilationTargetSecondsChange,
  targetClips,
  maxClips,
  videoDuration,
  videoQuality,
  backgroundMode,
  onVideoQualityChange,
  onVisualModeChange,
  onBackgroundModeChange,
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
  confirmSourceRights,
  autoUploadYoutube,
  onRequiredHashtagsChange,
  onRequireCreativeCommonsChange,
  onConfirmSourceRightsChange,
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
  onSearchAutoContent,
  onViralSearchFiltersChange,
  onAutoContentNicheChange,
  onToggleAutoContentSource,
  onStartJob,
  onUrlChange,
  sourceHistory,
  isCheckingSourceHistory,
  allowReprocessSource,
  onAllowReprocessSourceChange,
  autoViralMessage,
  url,
}: ControlPanelProps) {
  const isLongAnimate = clipMode === "long_animate";
  const hasSource = isLongAnimate
    ? scriptText.trim().length >= 120 && scriptText.trim().split(/\s+/).length >= 30
    : sourceMode === "url"
      ? Boolean(url.trim())
      : Boolean(uploadFileName);
  const duplicateApprovalRequired = !isLongAnimate && sourceMode === "url" && Boolean(sourceHistory?.found) && !allowReprocessSource;
  const sourceCheckPending = !isLongAnimate && sourceMode === "url" && Boolean(url.trim()) && isCheckingSourceHistory;
  const invalidCheckedSource = !isLongAnimate && sourceMode === "url"
    && Boolean(url.trim())
    && Boolean(sourceHistory)
    && !sourceHistory?.valid_youtube_url;
  const isStartDisabled = isSubmitting
    || isBusy
    || isUploading
    || !hasSource
    || sourceCheckPending
    || invalidCheckedSource
    || duplicateApprovalRequired
    || (!isLongAnimate && sourceMode === "url" && !confirmSourceRights)
    || (isLongAnimate && !confirmLongAnimateRights);
  const isProcessing = isSubmitting || isBusy;
  const localNoKeyBaseUrls = new Set<string>(
    LOCAL_LLM_PRESETS.filter((preset) => preset.label !== "Custom").map((preset) => preset.baseUrl),
  );
  const shouldShowApiKey = Boolean(aiApiKey.trim()) || !localNoKeyBaseUrls.has(aiBaseUrl);

  return (
    <section className="panel controlPanel">
      <div className="panelHeader">
        <span className="panelHeaderIcon">
          <Scissors size={18} />
        </span>
        <div className="panelTitleCopy">
          <span className="panelEyebrow">{isLongAnimate ? "Scene Cinema" : "Clip builder"}</span>
          <h2>{isLongAnimate ? "Buat Long Animate" : "Buat Klip Baru"}</h2>
        </div>
      </div>

      <div className="controlSection">
        <div className="controlSectionHeading">
          <span>01</span>
          <div>
            <h3>{isLongAnimate ? "Tulis naskah video" : "Pilih sumber video"}</h3>
            <p>{isLongAnimate ? "Naskah menjadi storyboard, visual, animasi, narasi, dan video utuh." : "Tempel link YouTube atau upload file dari perangkat."}</p>
          </div>
        </div>

        {!isLongAnimate ? <div className="segmentedField">
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
        </div> : null}

        {isLongAnimate ? (
          <>
            <label className="field wide longAnimateScriptField">
              <span>Naskah Long Animate · {scriptText.trim().split(/\s+/).filter(Boolean).length} kata</span>
              <textarea
                value={scriptText}
                onChange={(event) => onScriptTextChange(event.target.value.slice(0, 30000))}
                placeholder={'JUDUL: ...\nKARAKTER KONSISTEN: ...\nGAYA VISUAL: ...\n\n### ADEGAN 1 — ...\nVISUAL: Satu momen yang terlihat kamera.\nNARASI: Kalimat yang benar-benar dibacakan.\nTEKS LAYAR: Opsional, maksimal 6 kata.'}
                rows={12}
              />
              <p className="field-help">
                Minimal 120 karakter dan 30 kata. Hanya isi NARASI yang dijadikan suara dan subtitle; VISUAL tidak dibacakan.
              </p>
            </label>
            <details className="compactDisclosure longAnimateScriptGuide">
              <summary>
                <span>
                  <strong>Format naskah agar hasil paling bersih</strong>
                  <small>Pisahkan arahan gambar, voice-over, dan teks layar. Tidak perlu menulis resolusi, subtitle, transisi, atau negative prompt berulang kali.</small>
                </span>
                <ChevronDown size={17} />
              </summary>
              <div className="compactDisclosureBody">
                <p>
                  Buat minimal tiga blok ADEGAN. VISUAL berisi satu momen yang bisa dibekukan menjadi satu frame—subjeknya bebas mengikuti cerita: manusia, hewan, robot, benda, kendaraan, alam, atau dunia fantasi. Detail yang tidak diminta tidak akan ditambahkan. NARASI boleh <code>-</code> bila adegan sengaja hening.
                </p>
                <pre>{`JUDUL: Misi di Europa
KARAKTER KONSISTEN: Robot penjelajah jingga dengan satu antena biru.
GAYA VISUAL: Animasi 3D clay stop-motion, tekstur tanah liat, cahaya biru dingin.

### ADEGAN 1 — Pendaratan
VISUAL: Robot jingga turun dari wahana di permukaan es Europa yang retak.
NARASI: Robot penjelajah tiba untuk mencari tanda samudra bawah tanah.
TEKS LAYAR: Misi Dimulai

### ADEGAN 2 — Pemindaian
VISUAL: Robot menempelkan pemindai biru pada retakan es bercahaya.
NARASI: Sensor menangkap getaran air jauh di bawah lapisan es.
TEKS LAYAR: Sinyal Air

### ADEGAN 3 — Mengirim Data
VISUAL: Antena robot menyala saat sinyal biru melesat menuju wahana di orbit.
NARASI: Temuan dikirim sebelum badai partikel mencapai lokasi.
TEKS LAYAR: Data Terkirim`}</pre>
              </div>
            </details>
            <label className="sourceHistoryApproval longAnimateRights">
              <input
                type="checkbox"
                checked={confirmLongAnimateRights}
                onChange={(event) => onConfirmLongAnimateRightsChange(event.target.checked)}
              />
              <span>
                Saya memiliki hak atas naskah ini dan memastikan provider gambar/suara yang dikonfigurasi mengizinkan penggunaan komersial di YouTube.
              </span>
            </label>
            <div className="modeNotice">
              <strong>AI disclosure otomatis · upload awal Private</strong>
              <span>Scene mengikuti gaya visual dan isi tiap adegan; suara sintetis serta musik prosedural ditandai untuk disclosure. Figur publik, logo, karakter berhak cipta, dan klaim baru dilarang oleh prompt produksi.</span>
            </div>
          </>
        ) : sourceMode === "url" ? (
          <>
            <label className="field wide">
              <span>Link Video YouTube</span>
              <input
                value={url}
                onChange={(event) => onUrlChange(event.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
              />
              <p className="field-help">Pastikan video memiliki percakapan yang jelas untuk hasil transkripsi terbaik.</p>
            </label>
            {url.trim() && isCheckingSourceHistory ? (
              <div className="sourceHistoryNotice isChecking" role="status">
                <Loader2 className="spin" size={18} />
                <div>
                  <strong>Memeriksa jejak sumber…</strong>
                  <span>Mencocokkan ID video dengan seluruh job dan arsip Fendy Clipper.</span>
                </div>
              </div>
            ) : sourceHistory?.valid_youtube_url && sourceHistory.found ? (
              <div className="sourceHistoryNotice isDuplicate" role="alert">
                <AlertTriangle size={20} />
                <div className="sourceHistoryCopy">
                  <strong>Video ini sudah pernah masuk Fendy Clipper</strong>
                  <span>
                    Sistem menemukan jejak pemrosesan sebelumnya. Periksa formatnya agar tidak membuat hasil ganda tanpa sengaja.
                  </span>
                  <div className="sourceHistoryBadges">
                    {sourceHistory.has_short_clips || sourceHistory.attempted_modes.includes("short") ? (
                      <span>Clip pendek</span>
                    ) : null}
                    {sourceHistory.has_highlight_5m || sourceHistory.attempted_modes.includes("highlight_5m") ? (
                      <span>Long Story 5–10 menit</span>
                    ) : null}
                    {sourceHistory.archived && !sourceHistory.attempted_modes.length ? <span>Arsip lama</span> : null}
                  </div>
                  {sourceHistory.matches[0] ? (
                    <small>
                      <History size={13} />
                      Terakhir: {sourceHistory.matches[0].source_title || `Job ${sourceHistory.matches[0].job_id.slice(0, 8)}`}
                      {` · ${sourceHistory.matches[0].status}`}
                      {` · ${new Date(sourceHistory.matches[0].created_at).toLocaleDateString("id-ID")}`}
                    </small>
                  ) : null}
                  <label className="sourceHistoryApproval">
                    <input
                      type="checkbox"
                      checked={allowReprocessSource}
                      onChange={(event) => onAllowReprocessSourceChange(event.target.checked)}
                    />
                    <span>Saya sudah memeriksa riwayat dan memang ingin memproses ulang sumber ini.</span>
                  </label>
                </div>
              </div>
            ) : sourceHistory?.valid_youtube_url ? (
              <div className="sourceHistoryNotice isClear" role="status">
                <CheckCircle2 size={18} />
                <div>
                  <strong>Belum pernah diproses</strong>
                  <span>ID video tidak ditemukan pada riwayat dan arsip Fendy Clipper.</span>
                </div>
              </div>
            ) : url.trim() && sourceHistory ? (
              <div className="sourceHistoryNotice isInvalid" role="alert">
                <AlertTriangle size={18} />
                <div>
                  <strong>Link YouTube belum dikenali</strong>
                  <span>Gunakan link watch, youtu.be, Shorts, Live, atau Embed yang memuat ID video.</span>
                </div>
              </div>
            ) : null}
          </>
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

        {!isLongAnimate && sourceMode === "url" ? (
          <div className="aiBlock compactBlock">
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
            <p className="field-help">Dikunci aktif: video non-CC akan dibatalkan sebelum download. CC hanya metadata lisensi, bukan jaminan uploader memegang hak rekaman.</p>
            <label className="sourceHistoryApproval">
              <input
                type="checkbox"
                checked={confirmSourceRights}
                onChange={(event) => onConfirmSourceRightsChange(event.target.checked)}
              />
              <span>
                Saya memiliki rekaman ini atau izin komersial yang dapat dibuktikan untuk memakai ulang seluruh audio dan visualnya. Saya paham atribusi, crop, subtitle, dan durasi pendek tidak otomatis mencegah Content ID.
              </span>
            </label>
          </div>
        ) : null}
      </div>

      <div className="controlSection">
        <div className="controlSectionHeading">
          <span>02</span>
          <div>
            <h3>Atur format output</h3>
            <p>Tentukan panjang, kualitas, dan fokus visual klip.</p>
          </div>
        </div>

        <div className="segmentedField">
        <span>Model Clip</span>
        <div className="segmentedControl segmentedControl--three" role="group" aria-label="Model produksi">
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
            Long Story 5–10 Menit
          </button>
          <button
            className={clipMode === "long_animate" ? "active" : ""}
            type="button"
            onClick={() => onClipModeChange("long_animate")}
          >
            Long Animate
          </button>
        </div>
        <p className="field-help">
          {clipMode === "long_animate"
            ? "Scene Cinema mengubah naskah menjadi storyboard, art bible, visual per scene, gerak kamera, voice-over, subtitle, musik, thumbnail, dan satu video 16:9 utuh."
            : clipMode === "highlight_5m"
            ? "Codex Long Story Director membuat teaser singkat tanpa duplikasi, lalu merangkai konteks, perkembangan, penjelasan, dan kesimpulan secara kronologis dalam 16:9—tanpa filler. Deskripsi menambahkan ajakan Viralkan yang wajar untuk 7 hari pertama; kelayakan tetap ditentukan YouTube."
            : "Clip vertikal adaptif 25–180 detik: Codex memilih durasi terpendek yang cukup untuk hook, konteks, perkembangan, dan payoff—bukan memanjangkan isi dengan filler. Frame cover, caption safe-area, CTA Subscribe kontekstual, dan loop alami tetap aktif."}
        </p>
      </div>

      {clipMode !== "long_animate" ? <div className="gridFields">
        <label className="field">
          <span>{clipMode === "short" ? "Durasi Minimum" : "Durasi Minimum per Bagian"}</span>
          <input
            min={5}
            max={clipMode === "short" ? 179 : 600}
            type="number"
            value={minDuration}
            onChange={(event) => onMinDurationChange(Number(event.target.value))}
          />
        </label>
        <label className="field">
          <span>{clipMode === "short" ? "Durasi Maksimum" : "Durasi Maksimum per Bagian"}</span>
          <input
            min={10}
            max={clipMode === "short" ? 180 : 600}
            type="number"
            value={maxDuration}
            onChange={(event) => onMaxDurationChange(Number(event.target.value))}
          />
        </label>
      </div> : null}

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
      ) : clipMode === "highlight_5m" ? (
        <>
          <label className="field wide">
            <span>Target Durasi Long Story · {Math.round(compilationTargetSeconds / 60)} menit</span>
            <input
              min={300}
              max={600}
              step={60}
              type="range"
              value={compilationTargetSeconds}
              onChange={(event) => onCompilationTargetSecondsChange(Number(event.target.value))}
            />
            <p className="field-help">Pilih 5–10 menit. Cerita boleh lebih pendek bila materi inti tidak cukup; durasi tidak akan dipenuhi dengan filler demi mengejar angka.</p>
          </label>
          <div className="modeNotice">
            <strong>Landscape otomatis · 16:9 · target ±{Math.round(compilationTargetSeconds / 60)}:00</strong>
            <span>
              {videoDuration && videoDuration < compilationTargetSeconds
                ? "Video sumber lebih pendek dari target, sehingga hasil mengikuti materi yang tersedia."
                : "POV, konflik, konteks, dan payoff dirangkai kronologis; intro panjang, filler, dan pengulangan dilewati."}
            </span>
          </div>
        </>
      ) : (
        <div className="modeNotice longAnimateEstimate">
          <strong>
            Target tepat 20 detik · 16:9 Full HD
          </strong>
          <span>TTS diukur lebih dulu, lalu 3–7 scene dapat dipecah menjadi beberapa shot. Narasi yang terlalu panjang akan dipercepat agar timeline tetap tepat 20 detik.</span>
        </div>
      )}

      <details className="compactDisclosure formatDisclosure">
        <summary>
          <span>
            <strong>Visual & framing</strong>
            <small>{VIDEO_QUALITY_OPTIONS.find((option) => option.value === videoQuality)?.label} · Auto FYP · {backgroundMode === "keep" ? "Background asli" : backgroundMode === "mosque" ? "Masjid" : "Auto bersih"}</small>
          </span>
          <ChevronDown size={17} />
        </summary>
        <div className="compactDisclosureBody">
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
        <span>Gaya Visual</span>
        <div className="segmentedControl" role="group" aria-label="Gaya visual video otomatis">
          <button
            className="active"
            type="button"
            onClick={() => onVisualModeChange("auto_fyp")}
          >
            Auto FYP Viral
          </button>
        </div>
        <p className="field-help">
          Satu mode untuk clip pendek dan panjang: framing sinematik menjadi dasar, lalu depth 3D, nuansa arsip TV, reframe, atau split speaker dipilih selektif dari isi video. Variasi tetap konsisten dengan cerita agar tidak tampak seperti template massal.
        </p>
      </div>

      <div className="segmentedField">
        <span>Background Video</span>
        <div className="segmentedControl" role="group" aria-label="Pembersihan background video">
          <button
            className={backgroundMode === "auto_clean" ? "active" : ""}
            type="button"
            onClick={() => onBackgroundModeChange("auto_clean")}
          >
            Auto Bersih
          </button>
          <button
            className={backgroundMode === "mosque" ? "active" : ""}
            type="button"
            onClick={() => onBackgroundModeChange("mosque")}
          >
            Masjid Megah
          </button>
          <button
            className={backgroundMode === "keep" ? "active" : ""}
            type="button"
            onClick={() => onBackgroundModeChange("keep")}
          >
            Pertahankan
          </button>
        </div>
        <p className="field-help">
          {backgroundMode === "auto_clean"
            ? "Backdrop penuh tulisan dibersihkan otomatis. Mode Clean Detail tidak menambahkan panel bawah atau gradasi di atas pembicara."
            : backgroundMode === "mosque"
              ? "Selalu mencoba virtual background masjid; pembicara, meja, dan mikrofon tetap dipertahankan."
              : "Tidak mengubah background asli selain crop dan frame visual."}
        </p>
      </div>

      {clipMode === "short" ? (
        <>
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
        </>
      ) : (
        <div className="modeNotice">
          <strong>Komposisi pembicara otomatis</strong>
          <span>Frame tetap 16:9; sistem mencari dua wajah dan memusatkan panel kiri–kanan tanpa crop manual.</span>
        </div>
      )}
        </div>
      </details>
      </div>

      <details className="controlSection controlDisclosure">
        <summary className="controlDisclosureSummary">
          <div className="controlSectionHeading">
            <span>03</span>
            <div>
              <h3>Poles secara otomatis</h3>
              <p>Caption, AI agent, hashtag, dan upload YouTube.</p>
            </div>
          </div>
          <div className="controlDisclosureMeta">
            <span>{burnSubtitles ? "Caption aktif" : "Caption nonaktif"}</span>
            <span>{aiEnabled ? "AI aktif" : "AI nonaktif"}</span>
            <ChevronDown size={17} />
          </div>
        </summary>

        <div className="controlDisclosureBody">

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
          Teks dibuat ringkas dengan outline/shadow di safe-zone, tanpa gradient atau blur di atas wajah.
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
              clipMode={clipMode}
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
                placeholder="viralindonesia, trendingindonesia, kontenpilihan"
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
          {clipMode === "highlight_5m" || clipMode === "long_animate"
            ? "Selesai render, video landscape dan thumbnail otomatis diupload sebagai Private. Untuk Long Animate, disclosure AI ikut diaktifkan; publikasikan hanya setelah hak, Checks, judul, thumbnail, dan isi scene direview."
            : "Selesai clipping langsung antrekan 3 klip terbaik sebagai Private. Kebijakan nol-klaim aktif: Content ID apa pun membatalkan aksi Simpan/Publikasikan, termasuk klaim yang saat ini disebut tidak berdampak."}
        </p>
        </div>
        </div>
      </details>

      <div className="controlActions">
        {error ? <p className="error">{error}</p> : null}

        <details className="viralDiscoveryDisclosure">
          <summary>
            <span className="viralDiscoveryIcon"><Search size={17} /></span>
            <span>
              <strong>Belum punya sumber?</strong>
              <small>Cari 3 referensi CC berisiko lebih rendah</small>
            </span>
            <span className="autoContentBadge">AUTO NICHE</span>
            <ChevronDown size={17} />
          </summary>
          <div className="aiBlock viralBlock">
          <div className="autoContentHeading">
            <span className="aiToggleLabel"><Sparkles size={16} /> Pencarian Otomatis Konten Islami</span>
            <span className="autoContentBadge">3 TERATAS</span>
          </div>

          <label className="field autoNicheField">
            <span>Tema konten pilihan</span>
            <select
              value={autoContentNiche}
              disabled={isSearchingAutoContent || isAutoViralRunning}
              onChange={(event) => onAutoContentNicheChange(event.target.value as IslamicContentNiche)}
            >
              {ISLAMIC_NICHE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
            <small>{ISLAMIC_NICHE_OPTIONS.find((option) => option.value === autoContentNiche)?.description}</small>
          </label>

          <div className="viralSearchFilterPanel">
            <div className="viralFilterItem viralFilterLocked">
              <span>Jenis</span>
              <strong><ShieldCheck size={13} /> Video</strong>
            </div>
            <label className="viralFilterItem">
              <span>Durasi</span>
              <select
                value={viralSearchFilters.duration_filter}
                disabled={isSearchingAutoContent || isAutoViralRunning}
                onChange={(event) => onViralSearchFiltersChange({
                  ...viralSearchFilters,
                  duration_filter: event.target.value as ViralSearchFilters["duration_filter"],
                })}
              >
                <option value="any">Semua durasi</option>
                <option value="under_3">Kurang dari 3 menit</option>
                <option value="between_3_20">3–20 menit</option>
                <option value="over_20">Lebih dari 20 menit</option>
              </select>
            </label>
            <label className="viralFilterItem">
              <span>Tanggal unggah</span>
              <select
                value={viralSearchFilters.upload_date_filter}
                disabled={isSearchingAutoContent || isAutoViralRunning}
                onChange={(event) => onViralSearchFiltersChange({
                  ...viralSearchFilters,
                  upload_date_filter: event.target.value as ViralSearchFilters["upload_date_filter"],
                })}
              >
                <option value="today">Hari ini</option>
                <option value="this_week">Minggu ini</option>
                <option value="this_month">Bulan ini</option>
                <option value="this_year">Tahun ini</option>
              </select>
            </label>
            <label className="viralFilterItem">
              <span>Kualitas</span>
              <select
                value={viralSearchFilters.definition_filter}
                disabled={isSearchingAutoContent || isAutoViralRunning}
                onChange={(event) => onViralSearchFiltersChange({
                  ...viralSearchFilters,
                  definition_filter: event.target.value as ViralSearchFilters["definition_filter"],
                })}
              >
                <option value="hd">HD saja</option>
                <option value="any">Semua kualitas</option>
              </select>
            </label>
            <div className="viralFilterItem viralFilterLocked viralFilterLicense">
              <span>Lisensi</span>
              <strong><ShieldCheck size={13} /> Metadata CC</strong>
              <small>Bukan bukti kepemilikan hak</small>
            </div>
            <label className="viralFilterItem">
              <span>Prioritaskan</span>
              <select
                value={viralSearchFilters.sort_order}
                disabled={isSearchingAutoContent || isAutoViralRunning}
                onChange={(event) => onViralSearchFiltersChange({
                  ...viralSearchFilters,
                  sort_order: event.target.value as ViralSearchFilters["sort_order"],
                })}
              >
                <option value="popularity">Popularitas</option>
                <option value="relevance">Relevansi</option>
                <option value="newest">Paling baru</option>
              </select>
            </label>
          </div>
          <div className="viralFilterPolicy">
            <ShieldCheck size={14} />
            <span>Metadata Creative Commons dan Bahasa Indonesia wajib. Sinyal akun fan/reupload, TV, film, musik, broadcaster, dan risiko Content ID tetap ditampilkan sebagai peringatan; gate ketat baru membatalkan sumber saat clipping dimulai.</span>
          </div>

          <button
            className="ghostButton autoViralButton"
            type="button"
            disabled={isSearchingAutoContent || isAutoViralRunning || isProcessing}
            onClick={onSearchAutoContent}
          >
            {isSearchingAutoContent ? <Loader2 className="spin" size={16} /> : <Search size={16} />}
            {isSearchingAutoContent ? "Mengambil dari Google YouTube API..." : "Cari 3 Konten Viral Terbaru"}
          </button>

          {autoContentSources.length ? (
            <div className="autoContentResults">
              {autoContentSources.map((source) => {
                const selected = selectedAutoContentUrls.includes(source.url);
                return (
                  <article className={`autoContentCard${selected ? " selected" : ""}`} key={source.url}>
                    <label className="autoContentSelect">
                      <input
                        type="checkbox"
                        checked={selected}
                        disabled={isAutoViralRunning}
                        onChange={() => onToggleAutoContentSource(source.url)}
                      />
                      <span className="autoContentRank">#{source.rank}</span>
                      <span className="autoContentTitle">{source.title}</span>
                    </label>
                    <div className="autoContentMeta">
                      <span>{compactMetric(source.views)} tayangan</span>
                      <span>{compactMetric(source.views_per_day)} tayangan/hari</span>
                      <span>{freshnessLabel(source.age_days)}</span>
                      <span>{shortDuration(source.duration)}</span>
                      {source.definition === "hd" || (source.height ?? 0) >= 720 ? <span>HD</span> : null}
                      {source.search_provider === "youtube_data_api" ? <span>Google API</span> : null}
                      {source.search_provider === "yt_dlp_fallback" ? <span>Fallback CC</span> : null}
                      {source.filter_match === "adaptive" ? <span>Filter diperluas</span> : null}
                      <span>kecocokan {Math.round(source.niche_score)}/100</span>
                    </div>
                    {source.relaxed_filters?.length ? (
                      <div className="autoFilterRelaxation">
                        <span>Penyesuaian: {source.relaxed_filters.join(" • ")}</span>
                      </div>
                    ) : null}
                    {source.content_id_risk === "high" ? (
                      <div className="autoRightsWarning" role="alert">
                        <ShieldCheck size={13} />
                        <span>
                          Risiko Content ID tinggi: {source.content_id_risk_reasons?.join(" • ") || "perlu review hak manual"}. Sumber akan dihentikan sebelum download saat proses clipping.
                        </span>
                      </div>
                    ) : null}
                    <div className="autoContentReason">
                      <ShieldCheck size={13} />
                      <span>{source.ranking_reason}</span>
                      <a href={source.url} target="_blank" rel="noreferrer" aria-label="Buka sumber YouTube">
                        <ExternalLink size={14} />
                      </a>
                    </div>
                  </article>
                );
              })}
            </div>
          ) : null}

          {autoContentSources.length ? (
            <button
              className="primary autoQueueButton"
              type="button"
              disabled={isAutoViralRunning || isProcessing || selectedAutoContentUrls.length === 0}
              onClick={onStartAutoViral}
            >
              {isAutoViralRunning ? <Loader2 className="spin" size={16} /> : <ListPlus size={16} />}
              {isAutoViralRunning
                ? "Antrean clipping berjalan..."
                : `Masukkan ${selectedAutoContentUrls.length} Pilihan ke Antrean`}
            </button>
          ) : null}

          <p className="field-help">
            {autoViralMessage || "Google YouTube API mencari metadata CC secara luas. Peringatan risiko tidak menyembunyikan hasil; clipping dan upload tetap terkunci ketika hak audio/visual atau pemeriksaan Content ID tidak aman."}
          </p>
          </div>
        </details>

        <button className="primary" type="button" disabled={isStartDisabled} onClick={onStartJob}>
          {isProcessing ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
          {isProcessing
            ? "Sedang Memproses..."
            : sourceHistory?.found
              ? allowReprocessSource
                ? "Proses Ulang Sumber"
                : "Konfirmasi Sebelum Proses Ulang"
              : "Mulai Potong Video"}
        </button>
        {!hasSource ? <p className="startHint">Tambahkan sumber video untuk mulai memproses.</p> : null}
      </div>
    </section>
  );
}
