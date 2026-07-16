import type {
  AutoViralRequest,
  AutoViralRun,
  ClipJob,
  CreateClipJobInput,
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

export const probeUrlDuration = async (url: string) => {
  const response = await fetch(`${API_BASE}/api/probe?url=${encodeURIComponent(url)}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    return null;
  }
  const data = (await response.json()) as { duration: number | null };
  return data.duration;
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

export const getYouTubeUploads = async () => {
  const response = await fetch(`${CLIENT_API_BASE}/api/youtube/uploads`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Failed to load YouTube uploads"));
  }
  return (await response.json()) as YouTubeUploadJob[];
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
