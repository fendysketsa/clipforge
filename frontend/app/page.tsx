"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import toast from "react-hot-toast";
import {
  autoLoginYouTubeCdp,
  cancelJob,
  captureYouTubeBrowserSession,
  checkSourceHistory,
  createJob,
  createYouTubeUpload,
  createYouTubeUploadBatch,
  deleteAllJobClips,
  deleteFailedJobs,
  deleteJob,
  deleteJobClip,
  deleteSelectedJobClips,
  deleteJobs,
  discoverLocalLlms,
  enableYouTubeDirectProfileUpload,
  fetchModels,
  getAutoViralCampaign,
  getJob,
  getJobs,
  getYouTubeConfig,
  getYouTubeUploads,
  importYouTubeCdpCookies,
  probeUrlDuration,
  setupYouTubeOneTimeLogin,
  searchViralContentSources,
  startYouTubeLogin,
  startAutoViralCampaign,
  updateJobClipStatus,
  uploadVideo,
  type ClipDeleteResult,
  type LocalLlmProvider,
} from "../lib/apiClient";
import {
  DEFAULT_AI_BASE_URL,
  DEFAULT_AI_ENABLED,
  DEFAULT_AI_MODEL,
  DEFAULT_CAPTION_COLOR,
  DEFAULT_CAPTION_FONT,
  DEFAULT_CAPTION_FONT_SIZE,
  DEFAULT_CAPTION_OUTLINE,
  DEFAULT_CAPTION_OUTLINE_COLOR,
  DEFAULT_CAPTION_POSITION,
  DEFAULT_CLIP_MODE,
  DEFAULT_LANGUAGE,
  DEFAULT_MAX_DURATION,
  DEFAULT_MIN_DURATION,
  DEFAULT_MODEL,
  DEFAULT_VIDEO_QUALITY,
  COMPILATION_MAX_SECONDS,
  COMPILATION_MIN_SECONDS,
  COMPILATION_TARGET_SECONDS,
  JOB_POLL_INTERVAL_MS,
  MAX_REQUESTED_CLIPS,
  RECENT_LOG_LIMIT,
} from "../lib/constants";
import { isActiveJob } from "../lib/utils";
import type {
  AutoViralRun,
  BackgroundMode,
  CamCorner,
  CaptionFont,
  CaptionPosition,
  ClipMode,
  ClipFile,
  ClipJob,
  CropMode,
  IslamicContentNiche,
  SourceMode,
  SourceHistoryCheck,
  ViralContentSource,
  VideoQuality,
  VisualMode,
  YouTubeConfig,
  YouTubeUploadJob,
} from "../types/clip.type";
import { ControlPanel } from "./_components/ControlPanel";
import { DeleteAllToast } from "./_components/DeleteAllToast";
import { HistorySection } from "./_components/HistorySection";
import { ResultsSection } from "./_components/ResultsSection";
import { StatusPanel } from "./_components/StatusPanel";
import { SiteFooter } from "./_components/SiteFooter";
import { Topbar } from "./_components/Topbar";
import { WorkflowBar } from "./_components/WorkflowBar";

const isProcessJob = (item: ClipJob | null) =>
  item?.status === "queued" || item?.status === "running" || item?.status === "failed" || item?.status === "cancelled";
const CLEANUP_SUCCESS_DISPLAY_MS = 6_000;
const CLEANUP_PROGRESS_POLL_MS = 250;

export default function HomePage() {
  const [url, setUrl] = useState("");
  const [sourceMode, setSourceMode] = useState<SourceMode>("url");
  const [uploadToken, setUploadToken] = useState("");
  const [uploadFileName, setUploadFileName] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [minDuration, setMinDuration] = useState(DEFAULT_MIN_DURATION);
  const [maxDuration, setMaxDuration] = useState(DEFAULT_MAX_DURATION);
  const [targetClips, setTargetClips] = useState(0);
  const [videoDuration, setVideoDuration] = useState<number | null>(null);
  const [sourceHistory, setSourceHistory] = useState<SourceHistoryCheck | null>(null);
  const [isCheckingSourceHistory, setIsCheckingSourceHistory] = useState(false);
  const [allowReprocessSource, setAllowReprocessSource] = useState(false);
  const [videoQuality, setVideoQuality] = useState<VideoQuality>(DEFAULT_VIDEO_QUALITY);
  const [visualMode, setVisualMode] = useState<VisualMode>("auto_fyp");
  const [backgroundMode, setBackgroundMode] = useState<BackgroundMode>("keep");
  const [clipMode, setClipMode] = useState<ClipMode>(DEFAULT_CLIP_MODE);
  const [compilationTargetSeconds, setCompilationTargetSeconds] = useState(COMPILATION_TARGET_SECONDS);
  const [uploadPreviewUrl, setUploadPreviewUrl] = useState("");
  const [cropMode, setCropMode] = useState<CropMode>("person");
  const [camCorner, setCamCorner] = useState<CamCorner>("auto");
  const [burnSubtitles, setBurnSubtitles] = useState(true);
  const [captionFontSize, setCaptionFontSize] = useState(DEFAULT_CAPTION_FONT_SIZE);
  const [captionPosition, setCaptionPosition] = useState<CaptionPosition>(DEFAULT_CAPTION_POSITION);
  const [captionColor, setCaptionColor] = useState(DEFAULT_CAPTION_COLOR);
  const [captionFont, setCaptionFont] = useState<CaptionFont>(DEFAULT_CAPTION_FONT);
  const [captionOutline, setCaptionOutline] = useState(DEFAULT_CAPTION_OUTLINE);
  const [captionOutlineColor, setCaptionOutlineColor] = useState(DEFAULT_CAPTION_OUTLINE_COLOR);
  const [aiEnabled, setAiEnabled] = useState(DEFAULT_AI_ENABLED);
  const [aiBaseUrl, setAiBaseUrl] = useState(DEFAULT_AI_BASE_URL);
  const [aiModel, setAiModel] = useState(DEFAULT_AI_MODEL);
  const [aiApiKey, setAiApiKey] = useState("");
  const [requiredHashtags, setRequiredHashtags] = useState("");
  const [requireCreativeCommons, setRequireCreativeCommons] = useState(true);
  const [autoUploadYoutube, setAutoUploadYoutube] = useState(false);
  const [aiModels, setAiModels] = useState<string[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [localLlmProviders, setLocalLlmProviders] = useState<LocalLlmProvider[]>([]);
  const [isDiscoveringLlms, setIsDiscoveringLlms] = useState(false);
  const [hasAutoDiscoveredLlms, setHasAutoDiscoveredLlms] = useState(false);
  const [activeJob, setActiveJob] = useState<ClipJob | null>(null);
  const [job, setJob] = useState<ClipJob | null>(null);
  const [jobs, setJobs] = useState<ClipJob[]>([]);
  const [youtubeConfig, setYoutubeConfig] = useState<YouTubeConfig | null>(null);
  const [youtubeUploads, setYoutubeUploads] = useState<YouTubeUploadJob[]>([]);
  const [autoViralRun, setAutoViralRun] = useState<AutoViralRun | null>(null);
  const [autoContentNiche, setAutoContentNiche] = useState<IslamicContentNiche>("islamic_mental_health");
  const [autoContentSources, setAutoContentSources] = useState<ViralContentSource[]>([]);
  const [selectedAutoContentUrls, setSelectedAutoContentUrls] = useState<string[]>([]);
  const [isSearchingAutoContent, setIsSearchingAutoContent] = useState(false);
  const [isYouTubeLoginActive, setIsYouTubeLoginActive] = useState(false);
  const [selectedHistoryJobIds, setSelectedHistoryJobIds] = useState<string[]>([]);
  const [selectedClipUrls, setSelectedClipUrls] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRefreshingData, setIsRefreshingData] = useState(false);
  const [error, setError] = useState("");
  const browserStartedJobId = useRef<string | null>(null);
  const notifiedAutoViralRunId = useRef<string | null>(null);
  const cleanupConfirmationTimer = useRef<number | null>(null);

  const activeJobId = activeJob?.id;
  const isBusy = isActiveJob(activeJob);
  const activityJob = isBusy ? activeJob : job;
  const isAutoViralRunning = autoViralRun?.status === "queued" || autoViralRun?.status === "running";
  const latestLogs = useMemo(() => activityJob?.logs.slice(-RECENT_LOG_LIMIT) ?? [], [activityJob]);
  const hasActiveYouTubeUpload = youtubeUploads.some(
    (upload) =>
      upload.status === "queued"
      || upload.status === "running"
      || Boolean(upload.clip_delete_after && !upload.clip_deleted_at),
  );
  const hasPendingYouTubeCleanup = youtubeUploads.some(
    (upload) => Boolean(upload.clip_delete_after && !upload.clip_deleted_at),
  );

  // min_duration * target_clips must fit within 80% of the video length.
  const maxClips = useMemo(() => {
    if (!videoDuration || minDuration <= 0) return MAX_REQUESTED_CLIPS;
    return Math.min(MAX_REQUESTED_CLIPS, Math.max(1, Math.floor((videoDuration * 0.8) / minDuration)));
  }, [videoDuration, minDuration]);

  useEffect(() => {
    if (targetClips > maxClips) {
      setTargetClips(maxClips);
    }
  }, [maxClips, targetClips]);

  const handleClipModeChange = useCallback((value: ClipMode) => {
    setClipMode(value);
    setTargetClips(0);
    setVisualMode("auto_fyp");
    setBackgroundMode("keep");
    setCaptionFontSize(8);
    setCaptionOutline(0.5);
    if (value === "highlight_5m") {
      setMinDuration(30);
      setMaxDuration(90);
      setCompilationTargetSeconds(COMPILATION_TARGET_SECONDS);
      setVisualMode("cinematic");
      setBackgroundMode("keep");
    } else {
      setMinDuration(DEFAULT_MIN_DURATION);
      setMaxDuration(DEFAULT_MAX_DURATION);
    }
  }, []);

  useEffect(() => {
    if (sourceMode !== "url") {
      setSourceHistory(null);
      setIsCheckingSourceHistory(false);
      setAllowReprocessSource(false);
      return;
    }
    const trimmed = url.trim();
    if (!trimmed) {
      setVideoDuration(null);
      setSourceHistory(null);
      setIsCheckingSourceHistory(false);
      setAllowReprocessSource(false);
      return;
    }
    let cancelled = false;
    setIsCheckingSourceHistory(true);
    const timer = window.setTimeout(() => {
      checkSourceHistory(trimmed)
        .then((history) => {
          if (!cancelled) setSourceHistory(history);
        })
        .catch(() => {
          if (!cancelled) setSourceHistory(null);
        })
        .finally(() => {
          if (!cancelled) setIsCheckingSourceHistory(false);
        });
      probeUrlDuration(trimmed).then((duration) => {
        if (!cancelled) setVideoDuration(duration);
      }).catch(() => {
        if (!cancelled) setVideoDuration(null);
      });
    }, 700);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [url, sourceMode]);

  const loadJobs = useCallback(async () => {
    const nextJobs = await getJobs();
    setJobs(nextJobs);
    return nextJobs;
  }, []);

  const loadYouTubeUploads = useCallback(async () => {
    const [config, uploads] = await Promise.all([getYouTubeConfig(), getYouTubeUploads()]);
    setYoutubeConfig(config);
    setYoutubeUploads(uploads);
    return uploads;
  }, []);

  const handleSyncData = useCallback(async () => {
    if (isRefreshingData) return;
    setIsRefreshingData(true);
    try {
      await Promise.all([loadJobs(), loadYouTubeUploads()]);
      if (activeJobId) {
        const nextJob = await getJob(activeJobId).catch(() => null);
        if (nextJob) {
          setActiveJob(nextJob);
          setJob((current) => (current?.id === nextJob.id || current === null ? nextJob : current));
        }
      }
      toast.success("Data job, riwayat, dan klip sudah disinkronkan");
    } catch (syncError) {
      toast.error(syncError instanceof Error ? syncError.message : "Gagal sinkronisasi data");
    } finally {
      setIsRefreshingData(false);
    }
  }, [activeJobId, isRefreshingData, loadJobs, loadYouTubeUploads]);

  useEffect(() => {
    loadJobs().catch(() => undefined);
    loadYouTubeUploads().catch(() => undefined);
  }, [loadJobs, loadYouTubeUploads]);

  useEffect(() => {
    if (!hasPendingYouTubeCleanup) return;
    let cancelled = false;
    const refreshCleanupProgress = async () => {
      const uploads = await getYouTubeUploads().catch(() => null);
      if (!cancelled && uploads) {
        setYoutubeUploads(uploads);
      }
    };
    refreshCleanupProgress();
    const interval = window.setInterval(refreshCleanupProgress, CLEANUP_PROGRESS_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [hasPendingYouTubeCleanup]);

  useEffect(() => {
    if (!hasActiveYouTubeUpload) return;
    const interval = window.setInterval(async () => {
      const result = await Promise.all([loadYouTubeUploads(), loadJobs()]).catch(() => null);
      if (!result) return;
      const [nextUploads, nextJobs] = result;
      const selectedJobId = job?.id;
      if (!selectedJobId) return;
      const nextJob = nextJobs.find((item) => item.id === selectedJobId) ?? null;
      const now = Date.now();
      const recentCleanup = nextUploads
        .filter((upload) => upload.source_job_id === selectedJobId && upload.clip_deleted_at)
        .map((upload) => ({
          upload,
          deletedAt: Date.parse(upload.clip_deleted_at || ""),
        }))
        .filter(({ deletedAt }) => !Number.isNaN(deletedAt) && now - deletedAt < CLEANUP_SUCCESS_DISPLAY_MS)
        .sort((left, right) => right.deletedAt - left.deletedAt)[0];
      const removedClipIsAwaitingConfirmation = Boolean(
        recentCleanup
        && job.clips.some((clip) => clip.url === recentCleanup.upload.clip_url)
        && !nextJob?.clips.some((clip) => clip.url === recentCleanup.upload.clip_url),
      );

      if (removedClipIsAwaitingConfirmation && recentCleanup) {
        if (cleanupConfirmationTimer.current !== null) {
          window.clearTimeout(cleanupConfirmationTimer.current);
        }
        cleanupConfirmationTimer.current = window.setTimeout(async () => {
          const refreshedJobs = await loadJobs().catch(() => null);
          if (!refreshedJobs) return;
          setJob((current) => (
            current?.id === selectedJobId
              ? refreshedJobs.find((item) => item.id === selectedJobId) ?? null
              : current
          ));
          cleanupConfirmationTimer.current = null;
        }, Math.max(250, recentCleanup.deletedAt + CLEANUP_SUCCESS_DISPLAY_MS - now));
        return;
      }
      setJob((current) => (current?.id === selectedJobId ? nextJob : current));
    }, JOB_POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [hasActiveYouTubeUpload, job?.id, loadJobs, loadYouTubeUploads]);

  useEffect(() => () => {
    if (cleanupConfirmationTimer.current !== null) {
      window.clearTimeout(cleanupConfirmationTimer.current);
    }
  }, []);

  useEffect(() => {
    if (!autoViralRun || (autoViralRun.status !== "queued" && autoViralRun.status !== "running")) return;
    const interval = window.setInterval(async () => {
      const nextRun = await getAutoViralCampaign(autoViralRun.id).catch(() => null);
      if (!nextRun) return;
      setAutoViralRun(nextRun);
      if ((nextRun.status === "completed" || nextRun.status === "failed") && notifiedAutoViralRunId.current !== nextRun.id) {
        notifiedAutoViralRunId.current = nextRun.id;
        if (nextRun.status === "completed") {
          toast.success(
            nextRun.request.auto_upload_youtube === false
              ? "Clipping kandidat niche selesai dan siap direview."
              : "Auto Viral CC selesai. Alert Telegram sudah dikirim bila token tersedia.",
          );
        } else {
          toast.error(nextRun.message || "Auto Viral CC gagal", { duration: 9000 });
        }
        loadJobs().then((nextJobs) => {
          const latestJobId = [...nextRun.processed]
            .reverse()
            .map((item) => typeof item.job_id === "string" ? item.job_id : "")
            .find(Boolean);
          const latestAutoJob = latestJobId
            ? nextJobs.find((item) => item.id === latestJobId)
            : undefined;
          if (latestAutoJob) {
            setActiveJob(latestAutoJob);
            setJob(latestAutoJob);
          }
        }).catch(() => undefined);
        loadYouTubeUploads().catch(() => undefined);
      }
    }, JOB_POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [autoViralRun, loadJobs, loadYouTubeUploads]);

  useEffect(() => {
    if (isActiveJob(activeJob)) return;

    const runningJob = jobs.find(isActiveJob);
    if (runningJob) {
      setActiveJob(runningJob);
    }
  }, [activeJob, jobs]);

  useEffect(() => {
    setSelectedHistoryJobIds((current) =>
      current.filter((id) =>
        jobs.some((item) => item.id === id && item.status !== "queued" && item.status !== "running"),
      ),
    );
  }, [jobs]);

  useEffect(() => {
    setSelectedClipUrls((current) => current.filter((url) => job?.clips.some((clip) => clip.url === url)));
  }, [job]);

  useEffect(() => {
    if (!activeJobId || !isBusy) return;

    const interval = window.setInterval(async () => {
      const nextJob = await getJob(activeJobId);
      setActiveJob(nextJob);

      if (nextJob.status === "completed" || nextJob.status === "failed" || nextJob.status === "cancelled") {
        if (browserStartedJobId.current === nextJob.id) {
          browserStartedJobId.current = null;
        }
        setJob((current) => (current?.id === nextJob.id || current === null ? nextJob : current));
        loadJobs().catch(() => undefined);
      }
    }, JOB_POLL_INTERVAL_MS);

    return () => window.clearInterval(interval);
  }, [activeJobId, isBusy, loadJobs]);

  useEffect(() => {
    if (!activeJobId || !isBusy || browserStartedJobId.current !== activeJobId) return;

    const message = "Proses clip masih berjalan. Jika halaman ditutup atau direload, proses akan dibatalkan dan output sementara akan dihapus.";
    const warnBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = message;
      return message;
    };
    const cancelOnLeave = () => {
      const endpoint = `/api/jobs/${activeJobId}/cancel`;
      if (navigator.sendBeacon) {
        navigator.sendBeacon(endpoint, new Blob([], { type: "text/plain" }));
        return;
      }
      fetch(endpoint, { method: "POST", keepalive: true }).catch(() => undefined);
    };

    window.addEventListener("beforeunload", warnBeforeUnload);
    window.addEventListener("pagehide", cancelOnLeave);
    return () => {
      window.removeEventListener("beforeunload", warnBeforeUnload);
      window.removeEventListener("pagehide", cancelOnLeave);
    };
  }, [activeJobId, isBusy]);

  const handleLoadModels = useCallback(async () => {
    const base = aiBaseUrl.trim();
    if (!base) return;
    setIsLoadingModels(true);
    try {
      const models = await fetchModels(base, aiApiKey.trim());
      setAiModels(models);
      if (models.length) {
        toast.success(`${models.length} model dimuat`);
      } else {
        toast.error("Tidak ada model ditemukan");
      }
    } catch (modelsError) {
      toast.error(modelsError instanceof Error ? modelsError.message : "Gagal memuat model");
    } finally {
      setIsLoadingModels(false);
    }
  }, [aiBaseUrl, aiApiKey]);

  const handleDiscoverLocalLlms = useCallback(async (silent = false) => {
    setIsDiscoveringLlms(true);
    try {
      const providers = await discoverLocalLlms();
      setLocalLlmProviders(providers);
      if (!providers.length) {
        if (!silent) {
          toast.error("Belum menemukan LLM lokal. Pastikan Ollama/LM Studio/Jan sedang berjalan.");
        }
        return;
      }

      const first = providers[0];
      setAiBaseUrl(first.base_url);
      setAiModels(first.models);
      if (first.models[0]) {
        setAiModel(first.models[0]);
      }
      if (!silent) {
        toast.success(`${providers.length} provider LLM lokal ditemukan`);
      }
    } catch (discoverError) {
      if (!silent) {
        toast.error(discoverError instanceof Error ? discoverError.message : "Gagal mencari LLM lokal");
      }
    } finally {
      setIsDiscoveringLlms(false);
    }
  }, []);

  useEffect(() => {
    if (!aiEnabled || hasAutoDiscoveredLlms || localLlmProviders.length || isDiscoveringLlms) return;
    setHasAutoDiscoveredLlms(true);
    handleDiscoverLocalLlms(true).catch(() => undefined);
  }, [
    aiEnabled,
    handleDiscoverLocalLlms,
    hasAutoDiscoveredLlms,
    isDiscoveringLlms,
    localLlmProviders.length,
  ]);

  const handleAiEnabledChange = useCallback(
    (value: boolean) => {
      setAiEnabled(value);
      if (value && !localLlmProviders.length && !isDiscoveringLlms) {
        handleDiscoverLocalLlms().catch(() => undefined);
      }
    },
    [handleDiscoverLocalLlms, isDiscoveringLlms, localLlmProviders.length],
  );

  const handleSelectLocalProvider = useCallback((provider: LocalLlmProvider) => {
    setAiBaseUrl(provider.base_url);
    setAiApiKey("");
    setAiModels(provider.models);
    if (provider.models[0]) {
      setAiModel(provider.models[0]);
    }
  }, []);

  const handleAiBaseUrlChange = useCallback((value: string) => {
    setAiBaseUrl((current) => {
      if (current !== value) {
        setAiModels([]);
      }
      return value;
    });
    if (/localhost:(11434|1234|1337|8080)|127\.0\.0\.1:(11434|1234|1337|8080)/.test(value)) {
      setAiApiKey("");
    }
  }, []);

  const handleSourceModeChange = useCallback((mode: SourceMode) => {
    setSourceMode(mode);
    setError("");
  }, []);

  const handleTargetClipsChange = useCallback(
    (value: number) => {
      setTargetClips(Math.max(0, Math.min(MAX_REQUESTED_CLIPS, maxClips, value)));
    },
    [maxClips],
  );

  const handleUploadFileChange = useCallback(async (file: File | null) => {
    setError("");
    setUploadPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return file ? URL.createObjectURL(file) : "";
    });
    if (!file) {
      setUploadToken("");
      setUploadFileName("");
      setVideoDuration(null);
      return;
    }

    setIsUploading(true);
    try {
      const result = await toast.promise(uploadVideo(file), {
        loading: "Mengunggah video...",
        success: "Video berhasil diunggah!",
        error: "Gagal mengunggah video",
      });
      setUploadToken(result.source_file);
      setUploadFileName(result.original_name);
      setVideoDuration(result.duration);
    } catch (uploadError) {
      setUploadToken("");
      setVideoDuration(null);
      setUploadFileName("");
      setError(uploadError instanceof Error ? uploadError.message : "Gagal mengunggah video.");
    } finally {
      setIsUploading(false);
    }
  }, []);

  const handleStartJob = useCallback(async () => {
    const trimmedUrl = url.trim();
    const effectiveMaxDuration = clipMode === "short" ? Math.min(60, maxDuration) : maxDuration;
    setError("");

    if (isActiveJob(activeJob)) {
      setError("Proses clipping masih berjalan. Tunggu selesai atau batalkan sebelum memulai proses baru.");
      return;
    }
    if (sourceMode === "url" && !trimmedUrl) {
      setError("Link YouTube tidak boleh kosong.");
      return;
    }
    if (sourceMode === "upload" && !uploadToken) {
      setError("Unggah file video terlebih dahulu.");
      return;
    }
    if (effectiveMaxDuration <= minDuration) {
      setError(
        clipMode === "short"
          ? "Durasi minimum clip pendek harus di bawah 60 detik."
          : "Durasi maksimum harus lebih besar dari durasi minimum.",
      );
      return;
    }

    setIsSubmitting(true);

    try {
      const nextJob = await toast.promise(
        createJob({
          url: sourceMode === "url" ? trimmedUrl : "",
          source_file: sourceMode === "upload" ? uploadToken : "",
          top: clipMode === "short" && targetClips > 0 ? targetClips : undefined,
          min_duration: minDuration,
          max_duration: effectiveMaxDuration,
          clip_mode: clipMode,
          compilation_target_seconds: Math.max(
            COMPILATION_MIN_SECONDS,
            Math.min(COMPILATION_MAX_SECONDS, compilationTargetSeconds),
          ),
          model: DEFAULT_MODEL,
          language: DEFAULT_LANGUAGE,
          video_quality: videoQuality,
          visual_mode: visualMode,
          background_mode: backgroundMode,
          burn_subtitles: burnSubtitles,
          remove_running_text: false,
          auto_blur_watermarks: true,
          crop_mode: cropMode,
          cam_corner: camCorner,
          caption_font_size: captionFontSize,
          caption_position: captionPosition,
          caption_color: captionColor,
          caption_font: captionFont,
          caption_outline: captionOutline,
          caption_outline_color: captionOutlineColor,
          required_hashtags: requiredHashtags
            .split(",")
            .map((tag) => tag.trim())
            .filter(Boolean),
          require_creative_commons: requireCreativeCommons,
          auto_upload_youtube: autoUploadYoutube,
          allow_reprocess_source: sourceMode === "url" && allowReprocessSource,
          ai_enabled: aiEnabled,
          ai_base_url: aiBaseUrl.trim(),
          ai_model: aiModel.trim(),
          ai_api_key: aiApiKey.trim(),
        }),
        {
          loading: "Mempersiapkan proses pemotongan...",
          success: "Proses pemotongan berhasil dimulai!",
          error: "Gagal memulai proses pemotongan",
        },
      );

      setActiveJob(nextJob);
      setJob(nextJob);
      browserStartedJobId.current = nextJob.id;
      await loadJobs();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Gagal memulai proses.");
    } finally {
      setIsSubmitting(false);
    }
  }, [
    aiApiKey,
    aiBaseUrl,
    aiEnabled,
    aiModel,
    activeJob,
    allowReprocessSource,
    autoUploadYoutube,
    burnSubtitles,
    backgroundMode,
    camCorner,
    captionColor,
    captionFont,
    captionFontSize,
    captionOutline,
    captionOutlineColor,
    captionPosition,
    clipMode,
    compilationTargetSeconds,
    cropMode,
    loadJobs,
    maxDuration,
    minDuration,
    requireCreativeCommons,
    requiredHashtags,
    sourceMode,
    targetClips,
    uploadToken,
    url,
    videoQuality,
    visualMode,
  ]);

  const handleDeleteAllConfirmed = useCallback(async () => {
    await toast.promise(deleteJobs(), {
      loading: "Membatalkan job aktif dan menghapus catatan proses...",
      success: "Catatan job proses berhasil dihapus. Clips tetap aman.",
      error: "Gagal menghapus job proses",
    });

    setActiveJob(null);
    setJob((current) => (isProcessJob(current) ? null : current));
    browserStartedJobId.current = null;
    setSelectedHistoryJobIds([]);
    await loadJobs();
  }, [loadJobs]);

  const handleDeleteAll = useCallback(() => {
    toast((item) => (
      <DeleteAllToast
        toastId={item.id}
        title="Hapus job proses?"
        description="Catatan job queued, running, failed, dan cancelled akan dihapus. Job completed, clips, dan file hasil video tidak akan dihapus."
        confirmLabel="Hapus Job Proses"
        onConfirm={handleDeleteAllConfirmed}
      />
    ), {
      duration: Infinity,
    });
  }, [handleDeleteAllConfirmed]);

  const handleToggleHistoryJobSelection = useCallback((jobId: string) => {
    setSelectedHistoryJobIds((current) =>
      current.includes(jobId) ? current.filter((id) => id !== jobId) : [...current, jobId],
    );
  }, []);

  const handleDeleteSelectedConfirmed = useCallback(async () => {
    const ids = selectedHistoryJobIds;
    if (!ids.length) return;

    await toast.promise(Promise.all(ids.map((id) => deleteJob(id))), {
      loading: "Menghapus riwayat terpilih...",
      success: `${ids.length} riwayat berhasil dihapus.`,
      error: "Gagal menghapus riwayat terpilih",
    });

    setSelectedHistoryJobIds([]);
    setActiveJob((current) => (current && ids.includes(current.id) ? null : current));
    setJob((current) => (current && ids.includes(current.id) ? null : current));
    await loadJobs();
  }, [loadJobs, selectedHistoryJobIds]);

  const handleDeleteSelected = useCallback(() => {
    if (!selectedHistoryJobIds.length) return;
    toast((item) => (
      <DeleteAllToast
        toastId={item.id}
        title={`Hapus ${selectedHistoryJobIds.length} riwayat terpilih?`}
        description="Riwayat yang dicentang akan dihapus dari daftar beserta file output yang terkait."
        confirmLabel="Hapus Terpilih"
        onConfirm={handleDeleteSelectedConfirmed}
      />
    ), { duration: Infinity });
  }, [handleDeleteSelectedConfirmed, selectedHistoryJobIds.length]);

  const handleDeleteFailedConfirmed = useCallback(async () => {
    await toast.promise(deleteFailedJobs(), {
      loading: "Membersihkan riwayat gagal...",
      success: "Riwayat gagal berhasil dibersihkan.",
      error: "Gagal membersihkan riwayat gagal",
    });

    setSelectedHistoryJobIds([]);
    setActiveJob((current) =>
      current && (current.status === "failed" || current.status === "cancelled") ? null : current,
    );
    setJob((current) =>
      current && (current.status === "failed" || current.status === "cancelled") ? null : current,
    );
    await loadJobs();
  }, [loadJobs]);

  const handleDeleteFailed = useCallback(() => {
    toast((item) => (
      <DeleteAllToast
        toastId={item.id}
        title="Hapus semua riwayat gagal?"
        description="Semua proses failed dan dibatalkan akan dihapus supaya riwayat tetap bersih."
        confirmLabel="Hapus Gagal"
        onConfirm={handleDeleteFailedConfirmed}
      />
    ), { duration: Infinity });
  }, [handleDeleteFailedConfirmed]);

  const applyClipDeleteResult = useCallback(
    async (jobId: string, result: ClipDeleteResult) => {
      setActiveJob((current) => (current?.id === jobId ? result.job : current));
      setJob((current) => (current?.id === jobId ? result.job : current));
      setSelectedClipUrls((current) =>
        result.job ? current.filter((url) => result.job?.clips.some((clip) => clip.url === url)) : [],
      );
      await loadJobs();
    },
    [loadJobs],
  );

  const handleDeleteClipConfirmed = useCallback(
    async (jobId: string, clip: ClipFile) => {
      const result = await toast.promise(deleteJobClip(jobId, clip.url), {
        loading: "Menghapus file output...",
        success: "File output berhasil dihapus.",
        error: "Gagal menghapus file output",
      });

      await applyClipDeleteResult(jobId, result);
    },
    [applyClipDeleteResult],
  );

  const handleDeleteClip = useCallback(
    (clip: ClipFile) => {
      if (!job) return;
      const jobId = job.id;
      toast((item) => (
        <DeleteAllToast
          toastId={item.id}
          title={`Hapus ${clip.name}?`}
          description="File clip dan file pendukungnya di folder outputs akan dihapus."
          confirmLabel="Hapus File"
          onConfirm={() => handleDeleteClipConfirmed(jobId, clip)}
        />
      ), { duration: Infinity });
    },
    [handleDeleteClipConfirmed, job],
  );

  const handleDeleteAllClipsConfirmed = useCallback(
    async (jobId: string, clipCount: number) => {
      const result = await toast.promise(deleteAllJobClips(jobId), {
        loading: "Menghapus semua klip sukses...",
        success: `${clipCount} klip sukses dan riwayatnya berhasil dihapus.`,
        error: "Gagal menghapus semua klip sukses",
      });

      await applyClipDeleteResult(jobId, result);
    },
    [applyClipDeleteResult],
  );

  const handleDeleteAllClips = useCallback(() => {
    if (!job || !job.clips.length) return;

    const jobId = job.id;
    const clipCount = job.clips.length;
    toast((item) => (
      <DeleteAllToast
        toastId={item.id}
        title={`Hapus ${clipCount} klip sukses?`}
        description="Semua file clip di hasil job ini beserta thumbnail, prompt, dan caption pendukungnya akan dihapus dari outputs."
        confirmLabel="Hapus Semua Klip"
        onConfirm={() => handleDeleteAllClipsConfirmed(jobId, clipCount)}
      />
    ), { duration: Infinity });
  }, [handleDeleteAllClipsConfirmed, job]);

  const handleToggleClipSelection = useCallback((clipUrl: string) => {
    setSelectedClipUrls((current) =>
      current.includes(clipUrl) ? current.filter((url) => url !== clipUrl) : [...current, clipUrl],
    );
  }, []);

  const handleToggleAllClipSelection = useCallback(() => {
    setSelectedClipUrls((current) => {
      const clipUrls = job?.clips.map((clip) => clip.url) ?? [];
      if (clipUrls.length > 0 && current.length === clipUrls.length) {
        return [];
      }
      return clipUrls;
    });
  }, [job]);

  const handleDeleteSelectedClipsConfirmed = useCallback(
    async (jobId: string, clipUrls: string[]) => {
      const result = await toast.promise(deleteSelectedJobClips(jobId, clipUrls), {
        loading: "Menghapus klip terpilih...",
        success: `${clipUrls.length} klip terpilih berhasil dihapus.`,
        error: "Gagal menghapus klip terpilih",
      });

      await applyClipDeleteResult(jobId, result);
    },
    [applyClipDeleteResult],
  );

  const handleDeleteSelectedClips = useCallback(() => {
    if (!job || !selectedClipUrls.length) return;

    const jobId = job.id;
    const clipUrls = selectedClipUrls;
    toast((item) => (
      <DeleteAllToast
        toastId={item.id}
        title={`Hapus ${clipUrls.length} klip terpilih?`}
        description="Klip yang dicentang beserta file thumbnail, prompt, dan caption pendukungnya akan dihapus dari outputs. Jika semua klip job ini habis, riwayatnya ikut dihapus."
        confirmLabel="Hapus Terpilih"
        onConfirm={() => handleDeleteSelectedClipsConfirmed(jobId, clipUrls)}
      />
    ), { duration: Infinity });
  }, [handleDeleteSelectedClipsConfirmed, job, selectedClipUrls]);

  const handleToggleClipCorrect = useCallback(
    async (clip: ClipFile, isCorrect: boolean) => {
      if (!job) return;

      const previousJob = job;
      setJob((current) => {
        if (!current) return current;
        return {
          ...current,
          clips: current.clips.map((item) =>
            item.url === clip.url ? { ...item, is_correct: isCorrect } : item,
          ),
        };
      });

      try {
        const nextJob = await updateJobClipStatus(job.id, clip.url, isCorrect);
        setJob((current) => (current?.id === nextJob.id ? nextJob : current));
        await loadJobs();
      } catch (updateError) {
        setJob(previousJob);
        toast.error(updateError instanceof Error ? updateError.message : "Gagal menyimpan status clip");
      }
    },
    [job, loadJobs],
  );

  const requireValidYouTubeSession = useCallback(<T extends { ok: boolean; error?: string | null; message?: string | null }>(result: T) => {
    if (!result.ok) {
      throw new Error(result.error || result.message || "Session YouTube belum valid");
    }
    return result;
  }, []);

  const usesChromeDebugging = useCallback(
    () => Boolean(youtubeConfig?.upload_uses_cdp ?? /remote debugging|cdp/i.test(youtubeConfig?.auth_status_message ?? "")),
    [youtubeConfig?.auth_status_message, youtubeConfig?.upload_uses_cdp],
  );

  const handleUploadClipToYouTube = useCallback(
    async (clip: ClipFile) => {
      if (!job) return;
      const includesAutomaticThumbnail = clip.name.toLowerCase().startsWith("highlight_5menit_")
        || clip.name.toLowerCase().startsWith("resume_cerita_");
      try {
        const upload = await toast.promise(createYouTubeUpload(job.id, clip.url), {
          loading: includesAutomaticThumbnail
            ? "Memvalidasi video landscape dan thumbnail 16:9..."
            : "Memasukkan upload YouTube ke antrean...",
          success: (upload) =>
            upload.status === "completed" && upload.video_url
              ? "Klip ini sudah terupload. Upload duplikat dilewati."
              : includesAutomaticThumbnail
                ? "Video dan thumbnail otomatis masuk antrean YouTube."
                : "Upload masuk antrean. Session akan disinkronkan otomatis bila diperlukan.",
          error: (error) => error instanceof Error ? error.message : "Gagal membuat upload YouTube",
        });
        setYoutubeUploads((current) => [upload, ...current.filter((item) => item.id !== upload.id)]);
        loadYouTubeUploads().catch(() => undefined);
      } catch {
        // toast.promise already displayed the actionable status.
      }
    },
    [job, loadYouTubeUploads],
  );

  const handleUploadAllToYouTube = useCallback(async () => {
    if (!job || !job.clips.length) return;
    const bestCount = youtubeConfig?.auto_upload_count ?? 3;
    try {
      const uploads = await toast.promise(createYouTubeUploadBatch(job.id, [], bestCount), {
        loading: `Memasukkan ${Math.min(bestCount, job.clips.length)} klip terbaik ke antrean YouTube...`,
        success: (uploads) => {
          const activeCount = uploads.filter(
            (upload) => upload.status === "queued" || upload.status === "running",
          ).length;
          const skippedCount = uploads.filter(
            (upload) => upload.status === "completed" && Boolean(upload.video_url),
          ).length;
          if (!activeCount) {
            return `${skippedCount || uploads.length} klip sudah terupload; semua duplikat dilewati.`;
          }
          return `${activeCount} klip diproses/masuk antrean${skippedCount ? `, ${skippedCount} duplikat dilewati` : ""}.`;
        },
        error: (error) => error instanceof Error ? error.message : "Gagal membuat batch upload YouTube",
      });
      setYoutubeUploads((current) => {
        const nextIds = new Set(uploads.map((upload) => upload.id));
        return [...uploads, ...current.filter((item) => !nextIds.has(item.id))];
      });
      loadYouTubeUploads().catch(() => undefined);
    } catch {
      // toast.promise already displayed the actionable status.
    }
  }, [job, loadYouTubeUploads, youtubeConfig?.auto_upload_count]);

  const handleStartYouTubeLogin = useCallback(async () => {
    if (usesChromeDebugging()) {
      try {
        await toast.promise(setupYouTubeOneTimeLogin().then(requireValidYouTubeSession), {
          loading: "Menyiapkan login sekali...",
          success: "Login sekali aktif. Upload berikutnya memakai Playwright storage-state.",
          error: (error) => error instanceof Error ? error.message : "Gagal menyiapkan login sekali",
        });
        loadYouTubeUploads().catch(() => undefined);
      } catch {
        // toast.promise already displayed the backend error.
      }
      return;
    }
    try {
      await toast.promise(startYouTubeLogin(), {
        loading: "Membuka login YouTube Playwright...",
        success: "Proses login Playwright dimulai. Setelah Studio tampil, session akan disimpan otomatis.",
        error: (error) => error instanceof Error ? error.message : "Gagal membuka login Playwright",
      });
      setIsYouTubeLoginActive(true);
      window.setTimeout(() => {
        setIsYouTubeLoginActive(false);
        loadYouTubeUploads().catch(() => undefined);
      }, 12000);
    } catch {
      // toast.promise already displayed the backend error.
    }
  }, [loadYouTubeUploads, requireValidYouTubeSession, usesChromeDebugging]);

  const handleCaptureYouTubeSession = useCallback(async () => {
    if (usesChromeDebugging()) {
      try {
        await toast.promise(autoLoginYouTubeCdp().then(requireValidYouTubeSession), {
          loading: "Auto-login Chrome CDP...",
          success: "Chrome CDP login otomatis dan akun target valid. Aman untuk Retry YouTube.",
          error: (error) => error instanceof Error ? error.message : "CDP belum siap",
        });
      } catch {
        // toast.promise already displayed the backend error.
      }
      loadYouTubeUploads().catch(() => undefined);
      return;
    }
    try {
      await toast.promise(captureYouTubeBrowserSession(), {
        loading: "Menyinkronkan session dari browser...",
        success: "Session YouTube tersimpan. Klik Retry YouTube.",
        error: "Gagal sync session browser",
      });
      loadYouTubeUploads().catch(() => undefined);
    } catch (captureError) {
      toast.error(captureError instanceof Error ? captureError.message : "Gagal sync session browser", {
        duration: 9000,
      });
    }
  }, [loadYouTubeUploads, requireValidYouTubeSession, usesChromeDebugging]);

  const handleImportYouTubeCdpCookies = useCallback(async () => {
    try {
      await toast.promise(importYouTubeCdpCookies().then(requireValidYouTubeSession), {
        loading: "Mengambil cookies dari Chrome CDP...",
        success: (result) =>
          `Cookies Chrome tersimpan (${result.youtube_cookie_count ?? 0} cookies YouTube/Google).`,
        error: (error) => error instanceof Error ? error.message : "Gagal mengambil cookies Chrome CDP",
      });
      loadYouTubeUploads().catch(() => undefined);
    } catch {
      // toast.promise already displayed the backend error.
    }
  }, [loadYouTubeUploads, requireValidYouTubeSession]);

  const handleSetupYouTubeOneTimeLogin = useCallback(async () => {
    try {
      const result = await toast.promise(setupYouTubeOneTimeLogin(), {
        loading: "Menyiapkan login sekali...",
        success: (result) =>
          result.login_required
            ? result.message
            : `Login sekali aktif (${result.youtube_cookie_count ?? 0} cookies YouTube/Google). Upload berikutnya otomatis.`,
        error: (error) => error instanceof Error ? error.message : "Gagal menyiapkan login sekali",
      });
      if (!result.login_required) requireValidYouTubeSession(result);
      setIsYouTubeLoginActive(Boolean(result.login_required));
      loadYouTubeUploads().catch(() => undefined);
    } catch {
      // toast.promise already displayed the backend error.
    }
  }, [loadYouTubeUploads, requireValidYouTubeSession]);

  const handleEnableNoCdpMode = useCallback(async () => {
    try {
      const config = await toast.promise(enableYouTubeDirectProfileUpload(), {
        loading: "Mengaktifkan mode tanpa CDP...",
        success: (config) =>
          config.enabled
            ? "Mode tanpa CDP aktif. Upload akan memakai browser/profile backend."
            : "Mode tanpa CDP aktif, tapi profile belum terdeteksi.",
        error: (error) => error instanceof Error ? error.message : "Gagal mengaktifkan mode tanpa CDP",
      });
      setYoutubeConfig(config);
      loadYouTubeUploads().catch(() => undefined);
    } catch {
      // toast.promise already displayed the backend error.
    }
  }, [loadYouTubeUploads]);

  const handleCancelJob = useCallback(async (jobId = activeJobId ?? "") => {
    if (!jobId) return;
    const targetJob = jobs.find((item) => item.id === jobId);
    if (targetJob && !isActiveJob(targetJob)) return;

    await toast.promise(cancelJob(jobId), {
      loading: "Membatalkan proses...",
      success: "Proses distop. Clip yang sudah selesai tetap aman.",
      error: "Gagal membatalkan proses",
    });
    const nextJob = await getJob(jobId).catch(() => null);
    if (nextJob) {
      setActiveJob(nextJob);
      setJob((current) => (current?.id === nextJob.id || current === null ? nextJob : current));
    }
    if (activeJobId === jobId) {
      browserStartedJobId.current = null;
    }
    await loadJobs();
  }, [activeJobId, jobs, loadJobs]);

  const handleSearchAutoContent = useCallback(async () => {
    if (isSearchingAutoContent || isAutoViralRunning) return;
    setIsSearchingAutoContent(true);
    try {
      const sources = await toast.promise(
        searchViralContentSources({
          niche: autoContentNiche,
          video_count: 3,
          max_age_days: 30,
          min_views: 1000,
        }),
        {
          loading: "Mencari dan meranking kandidat niche...",
          success: (items) => `Top ${items.length} kandidat niche siap dipilih.`,
          error: (searchError) => searchError instanceof Error ? searchError.message : "Pencarian gagal",
        },
      );
      setAutoContentSources(sources);
      setSelectedAutoContentUrls(sources.map((source) => source.url));
    } catch {
      // toast.promise already presents the backend search error.
    } finally {
      setIsSearchingAutoContent(false);
    }
  }, [autoContentNiche, isAutoViralRunning, isSearchingAutoContent]);

  const handleToggleAutoContentSource = useCallback((sourceUrl: string) => {
    setSelectedAutoContentUrls((current) => (
      current.includes(sourceUrl)
        ? current.filter((item) => item !== sourceUrl)
        : [...current, sourceUrl]
    ));
  }, []);

  const handleStartAutoViral = useCallback(async () => {
    if (isAutoViralRunning || !selectedAutoContentUrls.length) return;

    try {
      const selectedSources = autoContentSources.filter((source) => selectedAutoContentUrls.includes(source.url));
      const selectedMaxAge = Math.max(30, ...selectedSources.map((source) => source.age_days ?? 0));
      const run = await toast.promise(
        startAutoViralCampaign({
          niche: autoContentNiche,
          source_urls: selectedAutoContentUrls,
          video_count: selectedAutoContentUrls.length,
          auto_upload_youtube: false,
          clips_per_video: 3,
          max_age_days: Math.min(365, selectedMaxAge),
          top: targetClips || null,
          min_duration: minDuration,
          max_duration: Math.min(60, maxDuration),
          video_quality: videoQuality,
          visual_mode: visualMode,
          background_mode: backgroundMode,
          crop_mode: cropMode,
          burn_subtitles: burnSubtitles,
          ai_enabled: aiEnabled,
          ai_base_url: aiBaseUrl,
          ai_model: aiModel,
          ai_api_key: aiApiKey,
        }),
        {
          loading: "Memasukkan pilihan ke antrean clipping...",
          success: `${selectedAutoContentUrls.length} sumber masuk antrean clipping.`,
          error: "Gagal memasukkan sumber ke antrean clipping",
        },
      );
      notifiedAutoViralRunId.current = null;
      setAutoViralRun(run);
    } catch (autoError) {
      toast.error(autoError instanceof Error ? autoError.message : "Gagal memulai antrean clipping", { duration: 9000 });
    }
  }, [
    aiApiKey,
    aiBaseUrl,
    aiEnabled,
    aiModel,
    autoContentNiche,
    autoContentSources,
    backgroundMode,
    burnSubtitles,
    cropMode,
    isAutoViralRunning,
    maxDuration,
    minDuration,
    selectedAutoContentUrls,
    targetClips,
    videoQuality,
    visualMode,
  ]);

  return (
    <main className="shell">
      <Topbar isRefreshing={isRefreshingData} onRefresh={handleSyncData} />

      <WorkflowBar
        hasSource={sourceMode === "url" ? Boolean(url.trim()) : Boolean(uploadFileName)}
        isProcessing={isBusy || isSubmitting}
        hasResults={Boolean(job?.clips.length)}
      />

      <section className="workspace" id="workspace">
        <ControlPanel
          clipMode={clipMode}
          onClipModeChange={handleClipModeChange}
          cropMode={cropMode}
          error={error}
          isBusy={isBusy}
          isSubmitting={isSubmitting}
          isAutoViralRunning={isAutoViralRunning}
          isSearchingAutoContent={isSearchingAutoContent}
          autoContentNiche={autoContentNiche}
          autoContentSources={autoContentSources}
          selectedAutoContentUrls={selectedAutoContentUrls}
          sourceMode={sourceMode}
          uploadFileName={uploadFileName}
          uploadPreviewUrl={uploadPreviewUrl}
          isUploading={isUploading}
          camCorner={camCorner}
          onCamCornerChange={setCamCorner}
          onSourceModeChange={handleSourceModeChange}
          onUploadFileChange={handleUploadFileChange}
          maxDuration={maxDuration}
          minDuration={minDuration}
          compilationTargetSeconds={compilationTargetSeconds}
          onCompilationTargetSecondsChange={setCompilationTargetSeconds}
          targetClips={targetClips}
          maxClips={maxClips}
          videoDuration={videoDuration}
          videoQuality={videoQuality}
          visualMode={visualMode}
          backgroundMode={backgroundMode}
          onVideoQualityChange={setVideoQuality}
          onVisualModeChange={setVisualMode}
          onBackgroundModeChange={setBackgroundMode}
          onTargetClipsChange={handleTargetClipsChange}
          burnSubtitles={burnSubtitles}
          captionFontSize={captionFontSize}
          captionPosition={captionPosition}
          captionColor={captionColor}
          captionFont={captionFont}
          captionOutline={captionOutline}
          captionOutlineColor={captionOutlineColor}
          onCaptionFontChange={setCaptionFont}
          onCaptionOutlineChange={setCaptionOutline}
          onCaptionOutlineColorChange={setCaptionOutlineColor}
          aiEnabled={aiEnabled}
          aiBaseUrl={aiBaseUrl}
          aiModel={aiModel}
          aiApiKey={aiApiKey}
          aiModels={aiModels}
          isLoadingModels={isLoadingModels}
          isDiscoveringLlms={isDiscoveringLlms}
          localLlmProviders={localLlmProviders}
          onLoadModels={handleLoadModels}
          onDiscoverLocalLlms={handleDiscoverLocalLlms}
          onSelectLocalProvider={handleSelectLocalProvider}
          requiredHashtags={requiredHashtags}
          requireCreativeCommons={requireCreativeCommons}
          autoUploadYoutube={autoUploadYoutube}
          onRequiredHashtagsChange={setRequiredHashtags}
          onRequireCreativeCommonsChange={setRequireCreativeCommons}
          onAutoUploadYoutubeChange={setAutoUploadYoutube}
          onCropModeChange={setCropMode}
          onMaxDurationChange={setMaxDuration}
          onMinDurationChange={setMinDuration}
          onBurnSubtitlesChange={setBurnSubtitles}
          onCaptionFontSizeChange={setCaptionFontSize}
          onCaptionPositionChange={setCaptionPosition}
          onCaptionColorChange={setCaptionColor}
          onAiEnabledChange={handleAiEnabledChange}
          onAiBaseUrlChange={handleAiBaseUrlChange}
          onAiModelChange={setAiModel}
          onAiApiKeyChange={setAiApiKey}
          onStartAutoViral={handleStartAutoViral}
          onSearchAutoContent={handleSearchAutoContent}
          onAutoContentNicheChange={(value) => {
            setAutoContentNiche(value);
            setAutoContentSources([]);
            setSelectedAutoContentUrls([]);
          }}
          onToggleAutoContentSource={handleToggleAutoContentSource}
          onStartJob={handleStartJob}
          onUrlChange={(value) => {
            setUrl(value);
            setSourceHistory(null);
            setIsCheckingSourceHistory(Boolean(value.trim()));
            setAllowReprocessSource(false);
          }}
          sourceHistory={sourceHistory}
          isCheckingSourceHistory={isCheckingSourceHistory}
          allowReprocessSource={allowReprocessSource}
          onAllowReprocessSourceChange={setAllowReprocessSource}
          autoViralMessage={autoViralRun?.message ?? ""}
          url={url}
        />
        <StatusPanel job={activityJob} latestLogs={latestLogs} onCancelJob={handleCancelJob} />
      </section>

      <ResultsSection
        clips={job?.clips ?? []}
        selectedClipUrls={selectedClipUrls}
        youtubeEnabled={Boolean(youtubeConfig?.enabled)}
        youtubeStatusMessage={youtubeConfig?.auth_status_message ?? "Login YouTube Playwright belum siap"}
        youtubeAutoUploadCount={youtubeConfig?.auto_upload_count ?? 3}
        youtubeUploads={youtubeUploads}
        isYouTubeLoginActive={isYouTubeLoginActive}
        onDeleteAllClips={handleDeleteAllClips}
        onDeleteClip={handleDeleteClip}
        onDeleteSelectedClips={handleDeleteSelectedClips}
        onCaptureYouTubeSession={handleCaptureYouTubeSession}
        onEnableNoCdpMode={handleEnableNoCdpMode}
        onImportYouTubeCdpCookies={handleImportYouTubeCdpCookies}
        onSetupYouTubeOneTimeLogin={handleSetupYouTubeOneTimeLogin}
        onStartYouTubeLogin={handleStartYouTubeLogin}
        onUploadAllToYouTube={handleUploadAllToYouTube}
        onUploadClipToYouTube={handleUploadClipToYouTube}
        onToggleAllClipSelection={handleToggleAllClipSelection}
        onToggleClipSelection={handleToggleClipSelection}
        onToggleClipCorrect={handleToggleClipCorrect}
      />
      <HistorySection
        jobs={jobs}
        selectedJobIds={selectedHistoryJobIds}
        onDeleteAll={handleDeleteAll}
        onDeleteFailed={handleDeleteFailed}
        onDeleteSelected={handleDeleteSelected}
        onSelectJob={setJob}
        onStopJob={handleCancelJob}
        onToggleJobSelection={handleToggleHistoryJobSelection}
      />
      <SiteFooter />
    </main>
  );
}
