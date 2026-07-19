export type JobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";
export type YouTubeVisibility = "private" | "unlisted" | "public";
export type CropMode = "center" | "person" | "streamer";
export type VideoQuality = "standard" | "high" | "max";
export type ClipMode = "short" | "highlight_5m";
export type CamCorner = "auto" | "br" | "bl" | "tr" | "tl";
export type CaptionPosition = "upper" | "center" | "bottom";
export type CaptionFont =
  | "DejaVu Sans"
  | "DejaVu Serif"
  | "Liberation Sans"
  | "Liberation Serif"
  | "Noto Sans";
export type SourceMode = "url" | "upload";

export type ClipFile = {
  name: string;
  url: string;
  size_bytes: number;
  title?: string | null;
  thumbnail_url?: string | null;
  thumbnail_prompt?: string | null;
  social_caption?: string | null;
  fyp_score?: number | null;
  fyp_label?: string | null;
  fyp_reason?: string | null;
  hook?: string | null;
  pov?: string | null;
  strengths?: string[];
  weaknesses?: string[];
  improvement_ideas?: string[];
  applied_edits?: string[];
  output_resolution?: string | null;
  is_correct: boolean;
};

export type ClipCandidate = {
  index: number;
  start: number;
  end: number;
  duration: number;
  score: number;
  title: string;
  reason: string;
  text: string;
  hook?: string;
  pov?: string;
  fyp_label?: string;
  strengths?: string[];
  weaknesses?: string[];
  improvement_ideas?: string[];
  applied_edits?: string[];
};

export type ClipJob = {
  id: string;
  status: JobStatus;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  duration_seconds?: number | null;
  source_title?: string | null;
  source_url?: string | null;
  source_uploader?: string | null;
  logs: string[];
  clips: ClipFile[];
  candidates: ClipCandidate[];
  error: string | null;
  request: {
    url: string;
    source_file: string;
    top: number | null;
    min_duration: number;
    max_duration: number;
    clip_mode: ClipMode;
    compilation_target_seconds: number;
    model: string;
    language: string;
    analyze_seconds: number | null;
    video_quality: VideoQuality;
    burn_subtitles: boolean;
    enhanced_edit: boolean;
    remove_running_text: boolean;
    crop_mode: CropMode;
    cam_corner: CamCorner;
    caption_font_size: number;
    caption_position: CaptionPosition;
    caption_color: string;
    caption_font: CaptionFont;
    caption_outline: number;
    caption_outline_color: string;
    require_creative_commons: boolean;
    auto_upload_youtube: boolean;
    ai_enabled: boolean;
    ai_base_url: string;
    ai_model: string;
  };
};

export type CreateClipJobInput = {
  url?: string;
  source_file?: string;
  top?: number;
  min_duration: number;
  max_duration: number;
  clip_mode?: ClipMode;
  compilation_target_seconds?: number;
  model: string;
  language: string;
  analyze_seconds?: number | null;
  video_quality?: VideoQuality;
  burn_subtitles: boolean;
  enhanced_edit?: boolean;
  remove_running_text?: boolean;
  crop_mode: CropMode;
  cam_corner?: CamCorner;
  caption_font_size?: number;
  caption_position?: CaptionPosition;
  caption_color?: string;
  caption_font?: CaptionFont;
  caption_outline?: number;
  caption_outline_color?: string;
  required_hashtags?: string[];
  require_creative_commons?: boolean;
  auto_upload_youtube?: boolean;
  ai_enabled?: boolean;
  ai_base_url?: string;
  ai_model?: string;
  ai_api_key?: string;
};

export type YouTubeConfig = {
  enabled: boolean;
  playwright_installed: boolean;
  auth_state_exists: boolean;
  auth_state_path: string;
  auth_status_message?: string | null;
  upload_uses_cdp?: boolean;
  direct_profile_upload?: boolean;
  chromium_profile_ready?: boolean;
  chromium_profile_path?: string;
  default_visibility: YouTubeVisibility;
  default_made_for_kids: boolean;
  default_tags: string[];
  default_playlist: string;
  target_channel: string;
  target_email: string;
  auto_upload_count: number;
  active_upload_id?: string | null;
};

export type YouTubeUploadJob = {
  id: string;
  source_job_id: string;
  clip_url: string;
  clip_name: string;
  status: JobStatus;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  duration_seconds?: number | null;
  title: string;
  description: string;
  thumbnail_url?: string | null;
  visibility: YouTubeVisibility;
  made_for_kids: boolean;
  tags: string[];
  playlist: string;
  target_channel: string;
  dry_run: boolean;
  video_url?: string | null;
  logs: string[];
  error?: string | null;
};

export type YouTubeLoginStatus = {
  active: boolean;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  logs: string[];
};

export type YouTubeCdpRefreshStatus = {
  started: boolean;
  cdp_ready: boolean;
  started_at: string;
  command: string[];
  log_path: string;
  message: string;
  logs: string[];
};

export type YouTubeCdpRepairStatus = {
  ok: boolean;
  cdp_ready: boolean;
  session_ready: boolean;
  hydrated: boolean;
  profile_sync_requested?: boolean;
  source_profile_ready?: boolean;
  source_profile_path?: string;
  cookies_imported?: boolean;
  cookie_count?: number;
  youtube_cookie_count?: number;
  storage_state_path?: string;
  login_required?: boolean;
  started_at: string;
  message: string;
  refresh?: YouTubeCdpRefreshStatus | null;
  error?: string | null;
  logs: string[];
};

export type AutoViralRequest = {
  video_count?: number;
  clips_per_video?: number;
  search_limit_per_query?: number;
  min_source_duration?: number;
  max_source_duration?: number;
  min_views?: number;
  max_age_days?: number;
  top?: number | null;
  min_duration?: number;
  max_duration?: number;
  video_quality?: VideoQuality;
  crop_mode?: CropMode;
  burn_subtitles?: boolean;
  ai_enabled?: boolean;
  ai_base_url?: string;
  ai_model?: string;
  ai_api_key?: string;
};

export type AutoViralRun = {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  created_at: string;
  updated_at: string;
  finished_at?: string | null;
  request: AutoViralRequest;
  message: string;
  selected_sources: Record<string, unknown>[];
  processed: Record<string, unknown>[];
  errors: string[];
  logs: string[];
};
