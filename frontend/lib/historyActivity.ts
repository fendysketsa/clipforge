import type { ClipJob, TikTokUploadJob, YouTubeUploadJob } from "../types/clip.type";

/** Rendering and delivery have separate lifecycles; keep both discoverable. */
export function historyUploadActivity(uploads: (YouTubeUploadJob | TikTokUploadJob)[]) {
  const active = uploads.filter(upload => !upload.dry_run && !upload.attention_archived_at
    && (upload.status === "queued" || upload.status === "running"));
  return {
    jobIds: new Set(active.map(upload => upload.source_job_id)),
    runningJobIds: new Set(active.filter(upload => upload.status === "running").map(upload => upload.source_job_id)),
    count: active.length,
  };
}

export function historyJobIsActive(job: ClipJob, uploadingJobIds: Set<string>) {
  return job.status === "queued" || job.status === "running" || uploadingJobIds.has(job.id);
}

export function intakeIsFresh(checkedEpoch?: number, now = Date.now()) {
  if (!Number.isFinite(checkedEpoch)) return false;
  const age = now / 1000 - (checkedEpoch as number);
  return age >= -30 && age <= 90;
}
