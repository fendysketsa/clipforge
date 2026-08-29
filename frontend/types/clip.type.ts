export type JobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";
export type YouTubeVisibility = "private" | "unlisted" | "public";
export type CropMode = "center" | "person" | "streamer";
export type VideoQuality = "standard" | "high" | "max";
export type ClipMode = "short" | "highlight_5m" | "long_animate";
export type VisualMode = "auto_fyp" | "cinematic" | "speaker_split" | "animated_3d" | "retro_tv";
export type BackgroundMode = "auto_clean" | "keep" | "mosque";
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
  core_message?: string | null;
  strengths?: string[];
  weaknesses?: string[];
  improvement_ideas?: string[];
  applied_edits?: string[];
  key_point_score?: number | null;
  loop_score?: number | null;
  retention_score?: number | null;
  boundary_quality?: string | null;
  output_resolution?: string | null;
  auditor_name?: string | null;
  audit_id?: string | null;
  growth_series?: string | null;
  growth_target_views?: number | null;
  growth_target_subscribers?: number | null;
  subscriber_intent_score?: number | null;
  growth_status?: string | null;
  growth_quality_gate_passed?: boolean | null;
  growth_next_action?: string | null;
  growth_checkpoints?: number[];
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
  key_point_score?: number;
  loop_score?: number;
  retention_score?: number;
  boundary_quality?: string;
};

export type ClipJob = {
  id: string;
  status: JobStatus;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  duration_seconds?: number | null;
  progress_percent?: number;
  progress_stage?: string | null;
  progress_detail?: string | null;
  progress_step?: number;
  progress_total_steps?: number;
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
    script_text: string;
    top: number | null;
    min_duration: number;
    max_duration: number;
    clip_mode: ClipMode;
    compilation_target_seconds: number;
    model: string;
    language: string;
    analyze_seconds: number | null;
    video_quality: VideoQuality;
    visual_mode: VisualMode;
    background_mode: BackgroundMode;
    burn_subtitles: boolean;
    enhanced_edit: boolean;
    remove_running_text: boolean;
    auto_blur_watermarks: boolean;
    crop_mode: CropMode;
    cam_corner: CamCorner;
    caption_font_size: number;
    caption_position: CaptionPosition;
    caption_color: string;
    caption_font: CaptionFont;
    caption_outline: number;
    caption_outline_color: string;
    require_creative_commons: boolean;
    confirm_source_rights: boolean;
    confirm_long_animate_rights: boolean;
    auto_upload_youtube: boolean;
    allow_reprocess_source?: boolean;
    ai_enabled: boolean;
    ai_base_url: string;
    ai_model: string;
  };
};

export type CreateClipJobInput = {
  url?: string;
  source_file?: string;
  script_text?: string;
  top?: number;
  min_duration: number;
  max_duration: number;
  clip_mode?: ClipMode;
  compilation_target_seconds?: number;
  model: string;
  language: string;
  analyze_seconds?: number | null;
  video_quality?: VideoQuality;
  visual_mode?: VisualMode;
  background_mode?: BackgroundMode;
  burn_subtitles: boolean;
  enhanced_edit?: boolean;
  remove_running_text?: boolean;
  auto_blur_watermarks?: boolean;
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
  confirm_source_rights?: boolean;
  confirm_long_animate_rights?: boolean;
  auto_upload_youtube?: boolean;
  allow_reprocess_source?: boolean;
  ai_enabled?: boolean;
  ai_base_url?: string;
  ai_model?: string;
  ai_api_key?: string;
};

export type SourceHistoryJob = {
  job_id: string;
  status: JobStatus;
  created_at: string;
  source_title?: string | null;
  clip_mode: ClipMode;
  clip_count: number;
};

export type SourceHistoryCheck = {
  input_url: string;
  normalized_url?: string | null;
  valid_youtube_url: boolean;
  found: boolean;
  archived: boolean;
  has_short_clips: boolean;
  has_highlight_5m: boolean;
  attempted_modes: ClipMode[];
  matches: SourceHistoryJob[];
};

export type SourceUsageLogEntry = {
  job_id: string;
  source_url: string;
  source_title?: string | null;
  source_uploader?: string | null;
  clip_mode: ClipMode;
  processed_at: string;
  clip_count: number;
  output_names: string[];
  processing_duration_seconds?: number | null;
  compilation_target_seconds?: number | null;
  auto_upload_youtube: boolean;
};

export type SourceUsageLogResponse = {
  items: SourceUsageLogEntry[];
  total: number;
  unique_sources: number;
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
  public_daily_limit: number;
  public_min_gap_hours: number;
  public_cadence_message: string;
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
  thumbnail_attached?: boolean;
  altered_content?: boolean;
  visibility: YouTubeVisibility;
  made_for_kids: boolean;
  tags: string[];
  playlist: string;
  playlist_confirmed?: boolean;
  target_channel: string;
  dry_run: boolean;
  video_url?: string | null;
  clip_sha256?: string | null;
  queue_position?: number | null;
  queue_total?: number | null;
  clip_delete_after?: string | null;
  clip_deleted_at?: string | null;
  clip_delete_error?: string | null;
  clip_cleanup_started_at?: string | null;
  clip_cleanup_current_step?: string | null;
  clip_cleanup_completed_steps?: string[];
  clip_cleanup_step_details?: Record<string, {
    started_at: string;
    completed_at?: string | null;
    duration_ms?: number | null;
    removed_items: number;
  }>;
  growth_series?: string;
  growth_target_views: number;
  growth_target_subscribers: number;
  performance_status: "not_measured" | "learning" | "views_target_met" | "target_met";
  performance_diagnosis: string[];
  performance_snapshots: Array<{
    captured_at: string;
    source: "youtube_analytics" | "youtube_public" | "manual";
    views: number;
    engaged_views?: number | null;
    average_view_duration?: number | null;
    average_view_percentage?: number | null;
    likes?: number | null;
    comments?: number | null;
    shares?: number | null;
    subscribers_gained?: number | null;
    subscribers_lost?: number | null;
  }>;
  backend_now?: string | null;
  clip_delete_remaining_seconds?: number | null;
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

export type IslamicContentNiche =
  | "auto"
  | "islamic_practical_life"
  | "islamic_current_viral"
  | "islamic_mental_health"
  | "halal_wealth"
  | "fiqih_harian"
  | "islamic_history";

export type ViralContentSource = {
  rank: number;
  url: string;
  title: string;
  uploader: string;
  duration?: number | null;
  definition?: string;
  height?: number | null;
  views: number;
  views_per_day: number;
  engagement_rate: number;
  age_days?: number | null;
  likes?: number | null;
  license?: string | null;
  rights_verified: boolean;
  license_metadata_verified?: boolean;
  content_id_risk?: "review" | "high";
  content_id_risk_reasons?: string[];
  score: number;
  viral_score: number;
  niche: IslamicContentNiche;
  niche_label: string;
  niche_score: number;
  language_score: number;
  search_provider?: "youtube_data_api" | "yt_dlp_fallback";
  search_elapsed_ms?: number;
  filter_match?: "exact" | "adaptive";
  relaxed_filters?: string[];
  ranking_reason: string;
};

export type ViralSearchFilters = {
  duration_filter: "any" | "under_3" | "between_3_20" | "over_20";
  upload_date_filter: "today" | "this_week" | "this_month" | "this_year";
  definition_filter: "any" | "hd";
  sort_order: "popularity" | "relevance" | "newest";
};

export type ViralContentSearchRequest = ViralSearchFilters & {
  niche: IslamicContentNiche;
  video_count?: number;
  max_age_days?: number;
  min_views?: number;
  exclude_urls?: string[];
};

export type AutoViralRequest = {
  niche?: IslamicContentNiche;
  video_count?: number;
  clips_per_video?: number;
  search_limit_per_query?: number;
  min_source_duration?: number;
  max_source_duration?: number;
  min_views?: number;
  max_age_days?: number;
  duration_filter?: ViralSearchFilters["duration_filter"];
  upload_date_filter?: ViralSearchFilters["upload_date_filter"];
  definition_filter?: ViralSearchFilters["definition_filter"];
  sort_order?: ViralSearchFilters["sort_order"];
  top?: number | null;
  min_duration?: number;
  max_duration?: number;
  video_quality?: VideoQuality;
  visual_mode?: VisualMode;
  background_mode?: BackgroundMode;
  crop_mode?: CropMode;
  burn_subtitles?: boolean;
  ai_enabled?: boolean;
  ai_base_url?: string;
  ai_model?: string;
  ai_api_key?: string;
  source_urls?: string[];
  auto_upload_youtube?: boolean;
};

export type AutoViralRun = {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  created_at: string;
  updated_at: string;
  finished_at?: string | null;
  request: AutoViralRequest;
  message: string;
  selected_sources: ViralContentSource[];
  processed: Record<string, unknown>[];
  errors: string[];
  logs: string[];
};
