import type { ClipJob } from "../types/clip.type";

export type LongProductionSnapshot = {
  enabled?: boolean;
  daily_target?: number;
  daily_attempt_limit?: number;
  auto_qc_private_upload?: boolean;
  attempts?: { day: string; job_id?: string; status?: string; qc_decision?: string;
    confirmed_upload_id?: string; confirmed_video_url?: string }[];
  qc_reviews?: {
    source_job_id?: string;
    source_clip_url?: string;
    status?: string;
    upload_hold?: string;
    youtube_worker_error?: string;
    audit?: { decision?: string; upload_allowed?: boolean; evidence?: string[] } | null;
  }[];
};

export function longAutomationForClip(url: string, snapshot: LongProductionSnapshot | null, jobs: ClipJob[], day: string) {
  const job = jobs.find(row => row.request.clip_mode === "highlight_5m"
    && row.request.publication_review_required && row.clips?.some(clip => clip.url === url));
  const review = snapshot?.qc_reviews?.find(row => row.source_clip_url === url)
    ?? (job ? { source_job_id: job.id } : null);
  if (!review) return null;
  const audit = review.audit;
  const decision = audit?.decision;
  const providerDeclined = decision === "DROP_SOURCE" && audit?.evidence?.some(line =>
    line.toLowerCase().includes("provider explicitly declined") && line.toLowerCase().includes("content safety screening"));
  const passed = review.status === "reviewed" && decision === "PASS_UPLOAD" && audit?.upload_allowed === true && !review.upload_hold;
  const reason = review.upload_hold ? `Upload Long ditahan: ${review.upload_hold}` : passed ? "QC Long lolos."
    : providerDeclined ? "QC aplikasi menahan pengiriman: pemeriksa AI menolak menilai sumber ini."
      : decision === "DROP_SOURCE" ? "Sumber Long ini dilewati QC (DROP_SOURCE)."
      : decision === "REPAIR_ONCE" ? "Long menunggu satu perbaikan sesuai audit QC."
        : "Long sedang menunggu hasil QC otomatis.";
  const attemptIds = new Set(snapshot?.attempts?.map(row => row.job_id));
  const replacement = jobs.find(job => job.id !== review.source_job_id && attemptIds.has(job.id)
    && job.request.clip_mode === "highlight_5m" && ["queued", "running"].includes(job.status));
  const latestAttempt = snapshot?.attempts?.filter(row => row.day === day && row.job_id !== review.source_job_id).at(-1);
  const completedReplacement = latestAttempt && jobs.find(row => row.id === latestAttempt.job_id && row.status === "completed");
  const replacementReview = completedReplacement && snapshot?.qc_reviews?.find(row => row.source_job_id === completedReplacement.id);
  const confirmedReplacementUrl = latestAttempt?.status === "completed" && latestAttempt.confirmed_upload_id
    && /^https:\/\/www\.youtube\.com\/watch\?v=[A-Za-z0-9_-]{11}$/.test(latestAttempt.confirmed_video_url ?? "")
    ? latestAttempt.confirmed_video_url : undefined;
  let next = "";
  if (replacement) {
    const percent = Math.round(replacement.progress_percent ?? 0);
    next = `Cron memproses Long berikutnya: ${percent}% · ${replacement.progress_detail || replacement.source_title || replacement.status}`;
  } else if (confirmedReplacementUrl) {
    next = "Long pengganti sudah terunggah ke YouTube.";
  } else if (!snapshot?.enabled) {
    next = "Produksi Long otomatis sedang nonaktif.";
  } else if (completedReplacement && replacementReview?.status !== "reviewed") {
    next = "Long berikutnya selesai dirender; menunggu hasil QC otomatis.";
  } else if (completedReplacement && replacementReview?.audit?.decision === "PASS_UPLOAD"
    && replacementReview.audit.upload_allowed === true && snapshot.auto_qc_private_upload) {
    next = replacementReview.upload_hold
      ? `Upload Long berikutnya ditahan: ${replacementReview.upload_hold}`
      : "Long berikutnya lolos QC; worker melanjutkan antrean YouTube Private otomatis.";
  } else if (passed && snapshot.auto_qc_private_upload) {
    next = review.youtube_worker_error
      ? "Antrean YouTube menunggu pemulihan worker otomatis."
      : "Worker cron melanjutkan antrean YouTube Private otomatis.";
  } else if (decision === "DROP_SOURCE") {
    const attemptsToday = snapshot.attempts?.filter(row => row.day === day).length ?? 0;
    next = attemptsToday >= (snapshot.daily_attempt_limit ?? (snapshot.daily_target ?? 1) + 2)
      ? "Batas percobaan Long hari ini tercapai; sumber baru mengikuti jadwal berikutnya."
      : "Cron mencari Long pengganti dari sumber lain.";
  }
  return { hold: !passed, reason, next, decision, replacementId: replacement?.id,
    replacementVideoUrl: confirmedReplacementUrl, providerDeclined };
}
