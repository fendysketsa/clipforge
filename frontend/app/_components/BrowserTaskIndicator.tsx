"use client";

import { useEffect, useMemo, useRef } from "react";
import type { AutoViralRun, ClipJob } from "../../types/clip.type";

type BrowserTaskIndicatorProps = {
  job: ClipJob | null;
  autoViralRun: AutoViralRun | null;
  isSearchingSources: boolean;
};

const DEFAULT_TITLE = "Fendy Clipper";
const DEFAULT_ICON = "/favicon.svg";
const FRAME_DURATION_MS = 240;
const BACKGROUND_UPDATE_MS = 1_000;

const stageLabels: Record<string, string> = {
  queued: "Menunggu antrean",
  preflight: "Memeriksa sumber",
  trend_discovery: "Membaca tren YouTube",
  fallback_discovery: "Memperluas pencarian",
  source: "Menyiapkan sumber",
  transcript: "Membuat transkrip",
  selection: "Memilih hook",
  render: "Merender klip",
  finalize: "Finalisasi hasil",
  youtube_upload: "Upload YouTube",
  complete: "Selesai",
};

const readableStage = (value?: string | null) => {
  const normalized = (value || "queued").trim().toLowerCase();
  const withoutClipPrefix = normalized.startsWith("clip_")
    ? normalized.slice("clip_".length)
    : normalized;
  return stageLabels[normalized]
    || stageLabels[withoutClipPrefix]
    || withoutClipPrefix.replaceAll("_", " ");
};

const spinnerIcon = (angle: number) => {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
      <rect x="5" y="5" width="54" height="54" rx="14" fill="#03130E"/>
      <circle cx="32" cy="32" r="19" fill="none" stroke="#123A32" stroke-width="7"/>
      <path d="M32 13a19 19 0 0 1 18.2 13.6" fill="none" stroke="#5EEAD4" stroke-width="7" stroke-linecap="round" transform="rotate(${angle} 32 32)"/>
      <circle cx="32" cy="32" r="5" fill="#34D399"/>
    </svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
};

const spinnerFrames = Array.from({ length: 12 }, (_, frame) => spinnerIcon(frame * 30));

export function BrowserTaskIndicator({
  job,
  autoViralRun,
  isSearchingSources,
}: BrowserTaskIndicatorProps) {
  const activity = useMemo(() => {
    const autoViralActive = autoViralRun?.status === "queued" || autoViralRun?.status === "running";
    if (autoViralActive && autoViralRun) {
      return {
        active: true,
        percent: Math.max(0, Math.min(100, Math.round(autoViralRun.progress_percent || 0))),
        stage: readableStage(autoViralRun.progress_stage),
        detail: autoViralRun.message || "Menjalankan kampanye Auto Viral",
      };
    }

    const jobActive = job?.status === "queued" || job?.status === "running";
    if (jobActive && job) {
      return {
        active: true,
        percent: Math.max(0, Math.min(100, Math.round(job.progress_percent || 0))),
        stage: readableStage(job.progress_stage),
        detail: job.progress_detail || job.source_title || `Task ${job.id.slice(0, 8)}`,
      };
    }

    if (isSearchingSources) {
      return {
        active: true,
        percent: 0,
        stage: "Mencari sumber",
        detail: "Membaca tren dan kandidat Creative Commons",
      };
    }

    return { active: false, percent: 0, stage: "", detail: "" };
  }, [
    autoViralRun?.id,
    autoViralRun?.message,
    autoViralRun?.progress_percent,
    autoViralRun?.progress_stage,
    autoViralRun?.status,
    isSearchingSources,
    job?.id,
    job?.progress_detail,
    job?.progress_percent,
    job?.progress_stage,
    job?.source_title,
    job?.status,
  ]);

  const activityRef = useRef(activity);
  const updateIndicatorRef = useRef<(() => void) | null>(null);
  activityRef.current = activity;

  useEffect(() => {
    let icon = document.querySelector<HTMLLinkElement>('link[rel~="icon"]');
    if (!icon) {
      icon = document.createElement("link");
      icon.rel = "icon";
      document.head.appendChild(icon);
    }

    if (!activity.active) {
      document.title = DEFAULT_TITLE;
      icon.href = DEFAULT_ICON;
      return;
    }

    const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const startedAt = Date.now();
    let interval: number | undefined;

    const update = () => {
      const current = activityRef.current;
      if (!current.active) return;

      const reducedMotion = motionPreference.matches;
      const elapsedFrames = reducedMotion
        ? 0
        : Math.floor((Date.now() - startedAt) / FRAME_DURATION_MS);
      const normalizedDetail = current.detail.replace(/\s+/g, " ").trim().slice(0, 100);
      const ticker = `${current.stage}${normalizedDetail ? ` • ${normalizedDetail}` : ""} • Fendy Clipper • `;
      const offset = ticker.length ? elapsedFrames % ticker.length : 0;
      const movingText = reducedMotion
        ? ticker
        : `${ticker.slice(offset)}${ticker.slice(0, offset)}`;
      document.title = `[${current.percent}%] ${movingText}`;
      icon.href = spinnerFrames[elapsedFrames % spinnerFrames.length];
    };

    const schedule = () => {
      if (interval !== undefined) window.clearInterval(interval);
      update();
      interval = motionPreference.matches
        ? undefined
        : window.setInterval(
          update,
          document.hidden ? BACKGROUND_UPDATE_MS : FRAME_DURATION_MS,
        );
    };

    updateIndicatorRef.current = update;
    schedule();
    document.addEventListener("visibilitychange", schedule);
    window.addEventListener("pageshow", schedule);
    motionPreference.addEventListener("change", schedule);

    return () => {
      if (interval !== undefined) window.clearInterval(interval);
      document.removeEventListener("visibilitychange", schedule);
      window.removeEventListener("pageshow", schedule);
      motionPreference.removeEventListener("change", schedule);
      updateIndicatorRef.current = null;
      document.title = DEFAULT_TITLE;
      icon.href = DEFAULT_ICON;
    };
  }, [activity.active]);

  useEffect(() => {
    updateIndicatorRef.current?.();
  }, [activity.detail, activity.percent, activity.stage]);

  return null;
}
