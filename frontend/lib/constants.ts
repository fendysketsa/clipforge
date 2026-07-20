import { CheckCircle2, Clock3, Loader2, XCircle, type LucideIcon } from "lucide-react";
import type { ClipMode, JobStatus, VideoQuality } from "../types/clip.type";

export const DEFAULT_MIN_DURATION = 15;
export const DEFAULT_MAX_DURATION = 60;
export const DEFAULT_MODEL = "Systran/faster-whisper-small";
export const DEFAULT_LANGUAGE = "id";
export const DEFAULT_VIDEO_QUALITY: VideoQuality = "high";
export const DEFAULT_CLIP_MODE: ClipMode = "short";
export const COMPILATION_TARGET_SECONDS = 300;
export const DEFAULT_AI_ENABLED = true;
export const DEFAULT_AI_BASE_URL = "http://localhost:11434/v1";
export const DEFAULT_AI_MODEL = "";
export const DEFAULT_CAPTION_FONT_SIZE = 10;
export const DEFAULT_CAPTION_POSITION = "upper";
export const DEFAULT_CAPTION_COLOR = "#FFFFFF";
export const CAPTION_FONT_SIZE_MIN = 8;
export const CAPTION_FONT_SIZE_MAX = 36;
export const DEFAULT_CAPTION_FONT = "DejaVu Sans";
export const DEFAULT_CAPTION_OUTLINE = 1.5;
export const DEFAULT_CAPTION_OUTLINE_COLOR = "#000000";
// Maps backend font family -> a CSS stack for the live preview.
export const CAPTION_FONTS = [
  { value: "DejaVu Sans", label: "DejaVu Sans", css: '"DejaVu Sans", system-ui, sans-serif' },
  { value: "DejaVu Serif", label: "DejaVu Serif", css: '"DejaVu Serif", Georgia, serif' },
  { value: "Liberation Sans", label: "Liberation Sans", css: '"Liberation Sans", Arial, sans-serif' },
  { value: "Liberation Serif", label: "Liberation Serif", css: '"Liberation Serif", "Times New Roman", serif' },
  { value: "Noto Sans", label: "Noto Sans", css: '"Noto Sans", system-ui, sans-serif' },
] as const;
export const JOB_POLL_INTERVAL_MS = 2200;
export const RECENT_LOG_LIMIT = 10;
export const MAX_REQUESTED_CLIPS = 12;
export const VIDEO_QUALITY_OPTIONS: { value: VideoQuality; label: string; help: string }[] = [
  { value: "standard", label: "Standar", help: "Lebih cepat, ukuran file lebih kecil." },
  { value: "high", label: "Jernih", help: "Detail lebih tajam untuk Reels/Shorts." },
  { value: "max", label: "Maksimal", help: "Paling jernih, proses dan file lebih besar." },
];
export const LOCAL_LLM_PRESETS = [
  { label: "Ollama", baseUrl: "http://localhost:11434/v1" },
  { label: "LM Studio", baseUrl: "http://localhost:1234/v1" },
  { label: "Jan", baseUrl: "http://localhost:1337/v1" },
  { label: "LocalAI", baseUrl: "http://localhost:8080/v1" },
  { label: "Custom", baseUrl: "http://localhost:20128/v1" },
] as const;

export const statusCopy: Record<JobStatus, string> = {
  queued: "Queued",
  running: "Processing",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Dibatalkan",
};

export const statusIcon: Record<JobStatus, LucideIcon> = {
  queued: Clock3,
  running: Loader2,
  completed: CheckCircle2,
  failed: XCircle,
  cancelled: XCircle,
};
