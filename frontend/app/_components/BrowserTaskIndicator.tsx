"use client";

import { useEffect } from "react";
import type { ClipJob } from "../../types/clip.type";

/** Update only when the job changes; no animation timer or favicon churn. */
export function BrowserTaskIndicator({ job }: { job: ClipJob | null }) {
  const active = job?.status === "queued" || job?.status === "running";
  const percent = Math.max(0, Math.min(100, Math.round(job?.progress_percent ?? 0)));
  const title = active
    ? `[${percent}%] ${job?.status === "queued" ? "Menunggu giliran" : "Produksi berjalan"} · ClipForge Studio`
    : "ClipForge Studio";
  useEffect(() => {
    document.title = title;
    return () => { document.title = "ClipForge Studio"; };
  }, [title]);
  return null;
}
