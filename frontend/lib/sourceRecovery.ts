import type { ClipJob } from "../types/clip.type";

function sourceId(value: string) {
  try {
    const url = new URL(value);
    if (!["https:", "http:"].includes(url.protocol)) return "";
    const host = url.hostname.toLowerCase();
    const id = host === "youtu.be" ? url.pathname.slice(1) :
      ["youtube.com", "www.youtube.com", "m.youtube.com"].includes(host)
        ? url.searchParams.get("v") || url.pathname.match(/^\/(?:shorts|live|embed)\/([\w-]{11})\/?$/)?.[1] : "";
    return /^[\w-]{11}$/.test(id || "") ? id! : "";
  } catch { return ""; }
}

export function sourceRecoveryForJob(job: ClipJob, jobs: ClipJob[]): ClipJob | null {
  if (job.status !== "failed" || job.clips.length || job.candidates.length || job.request.review_only
      || job.request.publication_review_required) return null;
  const transportFailure = (job.download_diagnostics?.transport_failure && !job.download_diagnostics.recovered && /unduh|download|metadata/i.test(job.error || "")) ||
    /^(?:Koneksi server ke YouTube gagal saat|Koneksi jalur unduh YouTube terputus saat)/.test(job.error || "");
  if (!transportFailure) return null;
  const source = sourceId(job.source_url || job.request.url);
  const failedAt = Date.parse(job.finished_at || job.updated_at);
  if (!source || !Number.isFinite(failedAt)) return null;
  return jobs.filter(other => other.id !== job.id && Date.parse(other.created_at) >= failedAt
    && sourceId(other.source_url || other.request.url) === source
    && other.request.clip_mode === job.request.clip_mode
    && (other.request.target_platform || "standard") === (job.request.target_platform || "standard")
    && !other.request.review_only && !other.request.publication_review_required
    && (["queued", "running"].includes(other.status) || (other.status === "completed" && other.clips.length > 0)))
    .sort((a,b) => Date.parse(b.created_at) - Date.parse(a.created_at))[0] || null;
}
