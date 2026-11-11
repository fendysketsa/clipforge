import type { TikTokUploadJob } from "../types/clip.type";

export function tiktokUploadForClip(uploads: TikTokUploadJob[], clipUrl: string) {
  const rows = uploads.filter((row) => row.clip_url === clipUrl && !row.dry_run)
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
  const newest = rows[0];
  if (!newest) return { latest: undefined, uncertain: false };
  const account = newest.target_handle.toLowerCase().replace(/^@/, "");
  const related = rows.filter((row) => row.target_handle.toLowerCase().replace(/^@/, "") === account);
  const confirmed = related.find((row) => row.status === "completed" && row.upload_confirmed && row.profile_url
    && (row.id === newest.id || Boolean(newest.clip_sha256 && row.clip_sha256 === newest.clip_sha256)));
  const uncertain = !confirmed && related.some((row) => !row.upload_confirmed && (
    row.submission_started || row.submission_accepted || row.profile_url
    || row.logs.some((line) => line.startsWith("POST_SUBMIT_INTENT:") || line.startsWith("POST_API_ACCEPTED:"))
  ));
  return { latest: confirmed ?? newest, uncertain };
}

export function tiktokAutomaticRetryLabel(upload?: TikTokUploadJob): string | null {
  if (!upload || upload.status !== "failed" || !upload.auto_retry_at
    || upload.submission_started || upload.submission_accepted
    || upload.upload_confirmed || upload.profile_url
    || (upload.auto_retry_count ?? 0) >= 3) return null;
  const date = new Date(upload.auto_retry_at);
  if (!Number.isFinite(date.getTime())) return null;
  const time = date.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Jakarta" });
  return `Ulang otomatis ${time} WIB · percobaan ${(upload.auto_retry_count ?? 0) + 1}/3`;
}
