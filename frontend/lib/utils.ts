import toast from "react-hot-toast";
import type { ClipFile, ClipJob } from "../types/clip.type";

export function isActiveJob(job: ClipJob | null) {
  return job?.status === "queued" || job?.status === "running";
}

export function formatDuration(totalSeconds: number | null | undefined) {
  if (totalSeconds === null || totalSeconds === undefined || !Number.isFinite(totalSeconds)) {
    return "-";
  }

  const roundedSeconds = Math.max(0, Math.round(totalSeconds));
  const hours = Math.floor(roundedSeconds / 3600);
  const minutes = Math.floor((roundedSeconds % 3600) / 60);
  const seconds = roundedSeconds % 60;

  if (hours > 0) {
    return `${hours}j ${minutes}m ${seconds}d`;
  }

  if (minutes > 0) {
    return `${minutes}m ${seconds}d`;
  }

  return `${seconds}d`;
}

export function jobElapsedSeconds(job: ClipJob | null, now = Date.now()) {
  if (!job) return null;
  if (job.duration_seconds !== null && job.duration_seconds !== undefined) {
    return job.duration_seconds;
  }
  if (!isActiveJob(job) || !job.started_at) return null;

  const startedAt = new Date(job.started_at).getTime();
  if (!Number.isFinite(startedAt)) return null;
  return Math.max(0, (now - startedAt) / 1000);
}

export function clipTitle(name: string) {
  return name.replace(/\.mp4$/i, "").replace(/^clip_\d+_/, "").replace(/-/g, " ");
}

export function clipDisplayTitle(clip: ClipFile) {
  return clip.title?.trim() || clipTitle(clip.name);
}

async function downloadClip(url: string, filename: string) {
  const response = await fetch(url);
  if (!response.ok) throw new Error("Gagal mengunduh file");

  const blob = await response.blob();
  const blobUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = blobUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(blobUrl);
}

export async function handleDownload(url: string, filename: string) {
  toast
    .promise(downloadClip(url, filename), {
      loading: "Mengunduh klip...",
      success: "Klip berhasil diunduh!",
      error: "Gagal mengunduh klip",
    })
    .catch(() => {
      window.open(url, "_blank");
    });
}

export async function handleCopyTitle(title: string) {
  await navigator.clipboard.writeText(title);
  toast.success("Judul klip berhasil disalin");
}

export async function handleCopyText(text: string, message = "Berhasil disalin") {
  await navigator.clipboard.writeText(text);
  toast.success(message);
}
