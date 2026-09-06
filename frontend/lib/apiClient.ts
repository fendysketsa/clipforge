import type {
  AutoViralRequest,
  AutoViralRun,
  ViralContentSearchRequest,
  ViralContentSource,
  ClipJob,
  CreateClipJobInput,
  SourceHistoryCheck,
  SourceUsageLogResponse,
  TikTokConfig,
  TikTokSessionStatus,
  TikTokUploadJob,
  YouTubeConfig,
  YouTubeCdpRepairStatus,
  YouTubeCdpRefreshStatus,
  YouTubeLoginStatus,
  YouTubeUploadJob,
} from "../types/clip.type";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8010";
const CLIENT_API_BASE = API_BASE;

export type LocalLlmProvider = {
  label: string;
  base_url: string;
  models: string[];
};

export type ClipDeleteResult = {
  job: ClipJob | null;
  removed_job: boolean;
  removed_clips: number;
};

const responseErrorMessage = async (response: Response, fallback: string) => {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    if (typeof payload?.detail === "string" && payload.detail.trim()) {
      return payload.detail;
    }
  }

  const detail = await response.text().catch(() => "");
  return detail || fallback;
};

export const uploadVideo = async (file: File) => {
  const form = new FormData();
  form.append("file", file);
  // Upload straight to the backend; the Next.js proxy corrupts binary bodies.
  const response = await fetch(`${API_BASE}/api/uploads`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to upload video"));
  }
  return (await response.json()) as {
    source_file: string;
    original_name: string;
    duration: number | null;
  };
};

export const fetchModels = async (baseUrl: string, apiKey: string) => {
  const response = await fetch(`${API_BASE}/api/models`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ base_url: baseUrl, api_key: apiKey }),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to load models"));
  }
  const data = (await response.json()) as { models: string[] };
  return data.models;
};

export const discoverLocalLlms = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/local-llm/discover`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to discover local LLMs");
  }
  return (await response.json()) as LocalLlmProvider[];
};

export type SourceProbe = {
  duration: number | null;
  title: string | null;
  uploader: string | null;
  channel_id: string | null;
  license: string | null;
  source_rights_trusted: boolean;
  source_rights_risk: boolean;
  source_rights_risk_reasons: string[];
  source_rights_review_reasons: string[];
};

export const probeUrlSource = async (url: string) => {
  const response = await fetch(`${API_BASE}/api/probe?url=${encodeURIComponent(url)}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    return null;
  }
  return (await response.json()) as SourceProbe;
};

export const checkSourceHistory = async (url: string) => {
  const response = await fetch(
    `${CLIENT_API_BASE}/api/source-history?url=${encodeURIComponent(url)}`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Gagal memeriksa riwayat sumber"));
  }
  return (await response.json()) as SourceHistoryCheck;
};

export const getSourceUsageLog = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/source-usage-log`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Gagal memuat log penggunaan sumber"));
  }
  return (await response.json()) as SourceUsageLogResponse;
};

export const getJobs = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/jobs`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to load jobs");
  }
  return (await response.json()) as ClipJob[];
};

export const deleteJobs = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/jobs`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to delete jobs"));
  }
};

export const deleteFailedJobs = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/jobs/failed`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to delete failed jobs"));
  }
};

export const deleteJob = async (jobId: string) => {
  const response = await fetch(`${CLIENT_API_BASE}/api/jobs/${jobId}`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to delete job"));
  }
};

export const deleteJobClip = async (jobId: string, clipUrl: string) => {
  const response = await fetch(
    `${CLIENT_API_BASE}/api/jobs/${jobId}/clips?clip_url=${encodeURIComponent(clipUrl)}`,
    { method: "DELETE" },
  );
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to delete clip"));
  }
  return (await response.json()) as ClipDeleteResult;
};

export const deleteAllJobClips = async (jobId: string) => {
  const response = await fetch(`${CLIENT_API_BASE}/api/jobs/${jobId}/clips/all`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to delete clips"));
  }
  return (await response.json()) as ClipDeleteResult;
};

export const deleteSelectedJobClips = async (jobId: string, clipUrls: string[]) => {
  const response = await fetch(`${CLIENT_API_BASE}/api/jobs/${jobId}/clips/selected`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ urls: clipUrls }),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to delete selected clips"));
  }
  return (await response.json()) as ClipDeleteResult;
};

export const updateJobClipStatus = async (jobId: string, clipUrl: string, isCorrect: boolean) => {
  const response = await fetch(`${CLIENT_API_BASE}/api/jobs/${jobId}/clips`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: clipUrl, is_correct: isCorrect }),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to update clip"));
  }
  return (await response.json()) as ClipJob;
};

export const repairJobClip = async (jobId: string, clipUrl: string) => {
  const response = await fetch(`${CLIENT_API_BASE}/api/jobs/${jobId}/clips/repair`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: clipUrl }),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Gagal memulai perbaikan otomatis"));
  }
  return (await response.json()) as ClipJob;
};

export const cancelJob = async (jobId: string) => {
  const response = await fetch(`${CLIENT_API_BASE}/api/jobs/${jobId}/cancel`, {
    method: "POST",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to cancel job");
  }
};

export const getJob = async (jobId: string) => {
  const response = await fetch(`${CLIENT_API_BASE}/api/jobs/${jobId}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to load job");
  }
  return (await response.json()) as ClipJob;
};

export const getYouTubeConfig = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/youtube/config`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to load YouTube config"));
  }
  return (await response.json()) as YouTubeConfig;
};

export const getTikTokConfig = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/tiktok/config`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Gagal memuat konfigurasi TikTok"));
  }
  return (await response.json()) as TikTokConfig;
};

export const getTikTokUploads = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/tiktok/uploads`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Gagal memuat upload TikTok"));
  }
  return (await response.json()) as TikTokUploadJob[];
};

export const updateTikTokUploadPerformance = async (
  uploadId: string,
  metrics: {
    views: number;
    watched_full_percentage?: number | null;
    average_watch_time_seconds?: number | null;
    likes?: number | null;
    comments?: number | null;
    shares?: number | null;
    saves?: number | null;
    followers_gained?: number | null;
  },
) => {
  const response = await fetch(
    `${CLIENT_API_BASE}/api/tiktok/uploads/${encodeURIComponent(uploadId)}/performance`,
    {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(metrics),
    },
  );
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Gagal menyimpan metrik TikTok"));
  }
  return (await response.json()) as TikTokUploadJob;
};

export const checkTikTokSession = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/tiktok/session/check`, {
    method: "POST",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Gagal memeriksa session TikTok"));
  }
  return (await response.json()) as TikTokSessionStatus;
};

export const getTikTokLogin = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/tiktok/login`, { cache: "no-store" });
  if (!response.ok) throw new Error("Gagal membaca status login TikTok");
  return (await response.json()) as YouTubeLoginStatus;
};

export const startTikTokLogin = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/tiktok/login/start`, {
    method: "POST",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Gagal membuka login TikTok"));
  }
  return (await response.json()) as YouTubeLoginStatus;
};

export const enableYouTubeDirectProfileUpload = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/youtube/upload-mode/direct-profile`, {
    method: "POST",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to enable direct profile upload"));
  }
  return (await response.json()) as YouTubeConfig;
};

export const getYouTubeUploads = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/youtube/uploads`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to load YouTube uploads"));
  }
  return (await response.json()) as YouTubeUploadJob[];
};

export const refreshYouTubeUploadPerformance = async (uploadId: string) => {
  const response = await fetch(
    `${CLIENT_API_BASE}/api/youtube/uploads/${encodeURIComponent(uploadId)}/performance/refresh`,
    { method: "POST", cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Gagal memperbarui performa YouTube"));
  }
  return (await response.json()) as YouTubeUploadJob;
};

export const updateYouTubeUploadPerformance = async (
  uploadId: string,
  metrics: {
    views: number;
    engaged_views?: number | null;
    shown_in_feed?: number | null;
    stayed_to_watch_percentage?: number | null;
    average_view_duration?: number | null;
    average_view_percentage?: number | null;
    likes?: number | null;
    comments?: number | null;
    shares?: number | null;
    subscribers_gained?: number | null;
    subscribers_lost?: number | null;
  },
) => {
  const response = await fetch(
    `${CLIENT_API_BASE}/api/youtube/uploads/${encodeURIComponent(uploadId)}/performance`,
    {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(metrics),
    },
  );
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Gagal menyimpan metrik Studio"));
  }
  return (await response.json()) as YouTubeUploadJob;
};

export const getYouTubeLoginStatus = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/youtube/login`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to load YouTube login status"));
  }
  return (await response.json()) as YouTubeLoginStatus;
};

export const startYouTubeLogin = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/youtube/login/start`, {
    method: "POST",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to start YouTube login"));
  }
  return (await response.json()) as YouTubeLoginStatus;
};

export const captureYouTubeBrowserSession = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/youtube/session/capture`, {
    method: "POST",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to sync YouTube browser session"));
  }
  return (await response.json()) as YouTubeLoginStatus;
};

export const refreshYouTubeCdpChrome = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/youtube/cdp/refresh`, {
    method: "POST",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to refresh YouTube CDP Chrome"));
  }
  return (await response.json()) as YouTubeCdpRefreshStatus;
};

export const repairYouTubeCdpSession = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/youtube/cdp/repair`, {
    method: "POST",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to repair YouTube CDP session"));
  }
  return (await response.json()) as YouTubeCdpRepairStatus;
};

export const autoLoginYouTubeCdp = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/youtube/cdp/auto-login`, {
    method: "POST",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to auto-login YouTube CDP"));
  }
  return (await response.json()) as YouTubeCdpRepairStatus;
};

export const importYouTubeCdpCookies = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/youtube/cdp/import-cookies`, {
    method: "POST",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to import YouTube CDP cookies"));
  }
  return (await response.json()) as YouTubeCdpRepairStatus;
};

export const setupYouTubeOneTimeLogin = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/youtube/login/once`, {
    method: "POST",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to setup one-time YouTube login"));
  }
  return (await response.json()) as YouTubeCdpRepairStatus;
};

export const syncYouTubeCdpSession = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/youtube/cdp/sync`, {
    method: "POST",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to sync YouTube CDP session"));
  }
  return (await response.json()) as YouTubeCdpRepairStatus;
};

export const createYouTubeUpload = async (jobId: string, clipUrl: string) => {
  const response = await fetch(`${CLIENT_API_BASE}/api/jobs/${jobId}/youtube-uploads`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ clip_url: clipUrl }),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to queue YouTube upload"));
  }
  return (await response.json()) as YouTubeUploadJob;
};

export const createYouTubeUploadBatch = async (jobId: string, clipUrls: string[] = [], bestCount = 3) => {
  const response = await fetch(`${CLIENT_API_BASE}/api/jobs/${jobId}/youtube-uploads/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ clip_urls: clipUrls, best_count: bestCount }),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to queue YouTube uploads"));
  }
  return (await response.json()) as YouTubeUploadJob[];
};

export const createTikTokUpload = async (jobId: string, clipUrl: string) => {
  const response = await fetch(`${CLIENT_API_BASE}/api/jobs/${jobId}/tiktok-uploads`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ clip_url: clipUrl, visibility: "only_you" }),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Gagal memasukkan upload TikTok"));
  }
  return (await response.json()) as TikTokUploadJob;
};

export const createTikTokUploadBatch = async (jobId: string, clipUrls: string[] = [], bestCount = 2) => {
  const response = await fetch(`${CLIENT_API_BASE}/api/jobs/${jobId}/tiktok-uploads/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ clip_urls: clipUrls, best_count: bestCount, visibility: "only_you" }),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Gagal memasukkan batch TikTok"));
  }
  return (await response.json()) as TikTokUploadJob[];
};

export const startAutoViralCampaign = async (input: AutoViralRequest = {}) => {
  const response = await fetch(`${CLIENT_API_BASE}/api/automation/viral-cc`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to start auto viral campaign"));
  }
  return (await response.json()) as AutoViralRun;
};

export const searchViralContentSources = async (input: ViralContentSearchRequest) => {
  const response = await fetch(`${CLIENT_API_BASE}/api/automation/viral-cc/sources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to search viral content sources"));
  }
  return (await response.json()) as ViralContentSource[];
};

export const getAutoViralCampaign = async (runId: string) => {
  const response = await fetch(`${CLIENT_API_BASE}/api/automation/viral-cc/${runId}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to load auto viral campaign"));
  }
  return (await response.json()) as AutoViralRun;
};

export const createJob = async (input: CreateClipJobInput) => {
  const response = await fetch(`${CLIENT_API_BASE}/api/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to create job"));
  }

  return (await response.json()) as ClipJob;
};

export const getOutputUrl = (path: string) => `${API_BASE}${path}`;
