import type { AutoViralScheduleStatus } from "../types/clip.type";

export function cronActivityView(
  schedule: AutoViralScheduleStatus | null, receivedAt: number | null,
  now: number, refreshFailed: boolean,
) {
  const stale = receivedAt !== null && now - receivedAt > 45_000;
  const tick = Date.parse(schedule?.scheduler_health?.last_tick_at ?? "");
  const heartbeatLate = Boolean(schedule?.enabled && schedule.scheduler_running
    && Number.isFinite(tick) && now - tick > 120_000);
  const issue = refreshFailed || stale
    ? "Status belum berhasil diperbarui. Menampilkan data terakhir."
    : heartbeatLate ? "Pemeriksaan cron belum memberi kabar baru lebih dari 2 menit." : null;
  const activity = schedule?.activity;
  const state = activity?.state ?? (!schedule ? "loading"
    : !schedule.enabled ? "disabled"
      : !schedule.scheduler_running ? "worker_unavailable" : "scheduled");
  const busy = ["running", "uploading", "checking"].includes(state);
  return {
    state, busy, issue,
    tone: issue || ["worker_unavailable", "retry_wait", "rights_hold", "browser_wait"].includes(state)
      ? "warning" : busy ? "active" : state === "disabled" ? "muted" : "waiting",
    label: activity?.label ?? (!schedule ? "Membaca status cron…"
      : !schedule.enabled ? "Cron nonaktif"
        : !schedule.scheduler_running ? "Worker cron belum berjalan" : "Menunggu jadwal"),
    detail: activity?.detail || schedule?.message || "Menghubungkan ke scheduler untuk membaca aktivitas terbaru.",
    percent: activity?.progress_percent == null ? null
      : Math.max(0, Math.min(100, activity.progress_percent)),
    nextLabel: schedule?.activity?.state === "capacity_wait" ? "Cek kapasitas berikutnya" : "Jadwal berikutnya",
  };
}

export function cronDate(value?: string | null) {
  if (!value || !Number.isFinite(Date.parse(value))) return "Belum tersedia";
  return new Intl.DateTimeFormat("id-ID", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit",
    timeZone: "Asia/Jakarta",
  }).format(new Date(value)) + " WIB";
}

export function cronLongActivity(status?: string, enabled?: boolean) {
  if (enabled === false) return "Produksi Long dinonaktifkan.";
  const labels: Record<string, string> = {
    disabled: "Produksi Long dinonaktifkan.", queued: "Long masuk antrean render.",
    waiting_for_render: "Menunggu giliran render.", waiting_for_campaign: "Menunggu proses Short selesai.",
    reserved: "Reservasi Long masih menunggu pemeriksaan.", waiting_for_qc: "Menunggu hasil QC Long.",
    daily_target_reached: "Slot produksi Long hari ini terisi.",
    daily_attempt_limit: "Batas percobaan Long hari ini tercapai.",
    source_rejected: "Sumber Long ditolak; sumber lain diperiksa pada giliran berikutnya.",
    waiting_for_eligible_short: "Menunggu sumber Long yang memenuhi syarat.",
  };
  return labels[status ?? ""] ?? "Menunggu pemeriksaan jalur Long.";
}
