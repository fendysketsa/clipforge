"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import {
  cancelJob,
  createJob,
  deleteAllJobClips,
  deleteFailedJobs,
  deleteJob,
  deleteJobClip,
  deleteJobs,
  discoverLocalLlms,
  fetchModels,
  getJob,
  getJobs,
  probeUrlDuration,
  updateJobClipStatus,
  uploadVideo,
  type LocalLlmProvider,
} from "../lib/apiClient";
import {
  DEFAULT_AI_BASE_URL,
  DEFAULT_AI_MODEL,
  DEFAULT_CAPTION_COLOR,
  DEFAULT_CAPTION_FONT,
  DEFAULT_CAPTION_FONT_SIZE,
  DEFAULT_CAPTION_OUTLINE,
  DEFAULT_CAPTION_OUTLINE_COLOR,
  DEFAULT_CAPTION_POSITION,
  DEFAULT_LANGUAGE,
  DEFAULT_MAX_DURATION,
  DEFAULT_MIN_DURATION,
  DEFAULT_MODEL,
  DEFAULT_VIDEO_QUALITY,
  JOB_POLL_INTERVAL_MS,
  MAX_REQUESTED_CLIPS,
  RECENT_LOG_LIMIT,
} from "../lib/constants";
import { isActiveJob } from "../lib/utils";
import type {
  CamCorner,
  CaptionFont,
  CaptionPosition,
  ClipFile,
  ClipJob,
  CropMode,
  SourceMode,
  VideoQuality,
} from "../types/clip.type";
import { ControlPanel } from "./_components/ControlPanel";
import { DeleteAllToast } from "./_components/DeleteAllToast";
import { HistorySection } from "./_components/HistorySection";
import { ResultsSection } from "./_components/ResultsSection";
import { StatusPanel } from "./_components/StatusPanel";
import { Topbar } from "./_components/Topbar";

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
  const [videoQuality, setVideoQuality] = useState<VideoQuality>(DEFAULT_VIDEO_QUALITY);
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
  const [aiEnabled, setAiEnabled] = useState(false);
  const [aiBaseUrl, setAiBaseUrl] = useState(DEFAULT_AI_BASE_URL);
  const [aiModel, setAiModel] = useState(DEFAULT_AI_MODEL);
  const [aiApiKey, setAiApiKey] = useState("");
  const [requiredHashtags, setRequiredHashtags] = useState("");
  const [aiModels, setAiModels] = useState<string[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [localLlmProviders, setLocalLlmProviders] = useState<LocalLlmProvider[]>([]);
  const [isDiscoveringLlms, setIsDiscoveringLlms] = useState(false);
  const [job, setJob] = useState<ClipJob | null>(null);
  const [jobs, setJobs] = useState<ClipJob[]>([]);
  const [selectedHistoryJobIds, setSelectedHistoryJobIds] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  const activeJobId = job?.id;
  const isBusy = isActiveJob(job);
  const latestLogs = useMemo(() => job?.logs.slice(-RECENT_LOG_LIMIT) ?? [], [job]);

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

  useEffect(() => {
    if (sourceMode !== "url") return;
    const trimmed = url.trim();
    if (!trimmed) {
      setVideoDuration(null);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      const duration = await probeUrlDuration(trimmed).catch(() => null);
      if (!cancelled) setVideoDuration(duration);
    }, 700);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [url, sourceMode]);

  const loadJobs = useCallback(async () => {
    setJobs(await getJobs());
  }, []);

  useEffect(() => {
    loadJobs().catch(() => undefined);
  }, [loadJobs]);

  useEffect(() => {
    setSelectedHistoryJobIds((current) =>
      current.filter((id) =>
        jobs.some((item) => item.id === id && (item.status === "failed" || item.status === "cancelled")),
      ),
    );
  }, [jobs]);

  useEffect(() => {
    if (!activeJobId) return;

    const interval = window.setInterval(async () => {
      const nextJob = await getJob(activeJobId);
      setJob(nextJob);

      if (nextJob.status === "completed" || nextJob.status === "failed" || nextJob.status === "cancelled") {
        loadJobs().catch(() => undefined);
      }
    }, JOB_POLL_INTERVAL_MS);

    return () => window.clearInterval(interval);
  }, [activeJobId, loadJobs]);

  useEffect(() => {
    if (!activeJobId || !isBusy) return;

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

  const handleDiscoverLocalLlms = useCallback(async () => {
    setIsDiscoveringLlms(true);
    try {
      const providers = await discoverLocalLlms();
      setLocalLlmProviders(providers);
      if (!providers.length) {
        toast.error("Belum menemukan LLM lokal. Pastikan Ollama/LM Studio/Jan sedang berjalan.");
        return;
      }

      const first = providers[0];
      setAiBaseUrl(first.base_url);
      setAiModels(first.models);
      if (first.models[0]) {
        setAiModel(first.models[0]);
      }
      toast.success(`${providers.length} provider LLM lokal ditemukan`);
    } catch (discoverError) {
      toast.error(discoverError instanceof Error ? discoverError.message : "Gagal mencari LLM lokal");
    } finally {
      setIsDiscoveringLlms(false);
    }
  }, []);

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
    setError("");

    if (sourceMode === "url" && !trimmedUrl) {
      setError("Link YouTube tidak boleh kosong.");
      return;
    }
    if (sourceMode === "upload" && !uploadToken) {
      setError("Unggah file video terlebih dahulu.");
      return;
    }

    setIsSubmitting(true);

    try {
      const nextJob = await toast.promise(
        createJob({
          url: sourceMode === "url" ? trimmedUrl : "",
          source_file: sourceMode === "upload" ? uploadToken : "",
          top: targetClips > 0 ? targetClips : undefined,
          min_duration: minDuration,
          max_duration: maxDuration,
          model: DEFAULT_MODEL,
          language: DEFAULT_LANGUAGE,
          video_quality: videoQuality,
          burn_subtitles: burnSubtitles,
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

      setJob(nextJob);
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
    burnSubtitles,
    camCorner,
    captionColor,
    captionFont,
    captionFontSize,
    captionOutline,
    captionOutlineColor,
    captionPosition,
    cropMode,
    loadJobs,
    maxDuration,
    minDuration,
    requiredHashtags,
    sourceMode,
    targetClips,
    uploadToken,
    url,
    videoQuality,
  ]);

  const handleDeleteAllConfirmed = useCallback(async () => {
    await toast.promise(deleteJobs(), {
      loading: "Menghapus riwayat...",
      success: "Seluruh riwayat berhasil dihapus!",
      error: "Gagal menghapus riwayat",
    });

    setJob(null);
    setSelectedHistoryJobIds([]);
    await loadJobs();
  }, [loadJobs]);

  const handleDeleteAll = useCallback(() => {
    toast((item) => <DeleteAllToast toastId={item.id} onConfirm={handleDeleteAllConfirmed} />, {
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
    setJob((current) => (current && ids.includes(current.id) ? null : current));
    await loadJobs();
  }, [loadJobs, selectedHistoryJobIds]);

  const handleDeleteSelected = useCallback(() => {
    if (!selectedHistoryJobIds.length) return;
    toast((item) => (
      <DeleteAllToast
        toastId={item.id}
        title={`Hapus ${selectedHistoryJobIds.length} riwayat terpilih?`}
        description="Riwayat failed/dibatalkan yang dicentang akan dihapus dari daftar."
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

  const handleDeleteClipConfirmed = useCallback(
    async (jobId: string, clip: ClipFile) => {
      const nextJob = await toast.promise(deleteJobClip(jobId, clip.url), {
        loading: "Menghapus file output...",
        success: "File output berhasil dihapus.",
        error: "Gagal menghapus file output",
      });

      setJob((current) => (current?.id === nextJob.id ? nextJob : current));
      await loadJobs();
    },
    [loadJobs],
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
      const nextJob = await toast.promise(deleteAllJobClips(jobId), {
        loading: "Menghapus semua klip sukses...",
        success: `${clipCount} klip sukses berhasil dihapus.`,
        error: "Gagal menghapus semua klip sukses",
      });

      setJob((current) => (current?.id === nextJob.id ? nextJob : current));
      await loadJobs();
    },
    [loadJobs],
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

  const handleCancelJob = useCallback(async () => {
    if (!activeJobId || !isBusy) return;
    await toast.promise(cancelJob(activeJobId), {
      loading: "Membatalkan proses...",
      success: "Proses dibatalkan dan output sementara dihapus.",
      error: "Gagal membatalkan proses",
    });
    const nextJob = await getJob(activeJobId).catch(() => null);
    if (nextJob) setJob(nextJob);
    await loadJobs();
  }, [activeJobId, isBusy, loadJobs]);

  return (
    <main className="shell">
      <Topbar onRefresh={loadJobs} />

      <section className="workspace">
        <ControlPanel
          cropMode={cropMode}
          error={error}
          isBusy={isBusy}
          isSubmitting={isSubmitting}
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
          targetClips={targetClips}
          maxClips={maxClips}
          videoDuration={videoDuration}
          videoQuality={videoQuality}
          onVideoQualityChange={setVideoQuality}
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
          onRequiredHashtagsChange={setRequiredHashtags}
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
          onStartJob={handleStartJob}
          onUrlChange={setUrl}
          url={url}
        />
        <StatusPanel job={job} latestLogs={latestLogs} onCancelJob={handleCancelJob} />
      </section>

      <ResultsSection
        clips={job?.clips ?? []}
        onDeleteAllClips={handleDeleteAllClips}
        onDeleteClip={handleDeleteClip}
        onToggleClipCorrect={handleToggleClipCorrect}
      />
      <HistorySection
        jobs={jobs}
        selectedJobIds={selectedHistoryJobIds}
        onDeleteAll={handleDeleteAll}
        onDeleteFailed={handleDeleteFailed}
        onDeleteSelected={handleDeleteSelected}
        onSelectJob={setJob}
        onToggleJobSelection={handleToggleHistoryJobSelection}
      />
    </main>
  );
}
