"use client";

import { useEffect, useState } from "react";
import { Activity, AlertCircle, ChevronDown, Clock3, Loader2, Power } from "lucide-react";
import type { AutoViralScheduleStatus } from "../../types/clip.type";
import { cronActivityView, cronDate, cronLongActivity } from "../../lib/cronActivity";

type Props = {
  schedule: AutoViralScheduleStatus | null;
  receivedAt: number | null;
  refreshFailed: boolean;
};

export function CronActivity({ schedule, receivedAt, refreshFailed }: Props) {
  const [now, setNow] = useState(0);
  useEffect(() => {
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 5_000);
    return () => window.clearInterval(timer);
  }, []);
  const view = cronActivityView(schedule, receivedAt, now, refreshFailed);
  const health = schedule?.scheduler_health;
  const capacity = schedule?.capacity;
  const queue = schedule?.upload_queue;
  const plan = schedule?.daily_plan;
  const Icon = view.issue || view.tone === "warning" ? AlertCircle
    : view.busy ? Loader2 : view.state === "disabled" ? Power : Clock3;
  return (
    <section className={`cronActivity cronActivity--${view.tone}`} aria-label="Aktivitas cron">
      <div className="cronActivityMain">
        <span className="cronActivityIcon" aria-hidden="true"><Icon size={20} className={view.busy && !view.issue ? "spin" : undefined} /></span>
        <div className="cronActivityCopy">
          <div className="cronActivityHeading">
            <span>AKTIVITAS CRON</span>
            <strong role="status">{view.label}</strong>
            {view.percent !== null && view.busy ? <b>{view.percent}%</b> : null}
          </div>
          <p>{view.detail}</p>
          {schedule?.activity?.source_title ? <p className="cronActivitySource">{schedule.activity.source_title}</p> : null}
          {view.percent !== null && view.busy ? (
            <progress className="cronActivityProgress" value={view.percent} max={100} aria-label="Progres proses saat ini" />
          ) : null}
          {view.issue ? <p className="cronActivityWarning" role="status">{view.issue}</p> : null}
          <p className="cronActivityChecked">Pemeriksaan terakhir: {cronDate(health?.last_checked_at)} · pembaruan otomatis 15 detik</p>
          {schedule?.short_schedule_daily_limit ? <p className="cronActivityChecked">Publikasi Short: maksimal <strong>{schedule.short_schedule_daily_limit} klip berbeda per tanggal WIB</strong>. Sisa produksi mendapat tanggal berikutnya; Long dihitung terpisah.</p> : null}
          {plan?.enabled ? (
            <div className="cronDailyPlan" aria-label="Target produksi cron harian">
              <div className="cronDailyPlanHeading"><strong>Target {plan.day} WIB · {plan.total_target} video</strong><span>{plan.total_uploaded} terunggah terverifikasi</span></div>
              <div className="cronDailyLanes">
                {(["scheduled_short", "private_short", "long"] as const).map(key => {
                  const lane = plan.lanes[key];
                  return <div className="cronDailyLane" key={key}>
                    <div><strong>{lane.label}</strong><b>{lane.uploaded}/{lane.target}</b></div>
                    <progress value={lane.uploaded} max={Math.max(1, lane.target)} aria-label={`${lane.label} terunggah terverifikasi`} />
                    <span>{lane.active} diproses · {lane.ready} render siap/QC · {lane.held} perlu verifikasi</span>
                    <small>{lane.remaining} slot produksi tersisa{key === "long" && plan.long_production_enabled === false ? " · produksi Long dinonaktifkan" : ""}</small>
                    {key === "long" ? <small>{cronLongActivity(health?.long_production_status, plan.long_production_enabled)}{plan.long_rejected_today ? ` ${plan.long_rejected_today} hasil ditolak QC; tidak dihitung berhasil.` : ""}</small> : null}
                  </div>;
                })}
              </div>
              <p>Semua jalur otomatis lewat cron. Hasil yang menunggu QC/review dicadangkan; hasil gagal atau ditolak tidak dianggap berhasil.</p>
            </div>
          ) : null}
          {schedule && !schedule.enabled && view.busy ? <p>Peluncuran cron baru nonaktif; pekerjaan ini tetap diselesaikan.</p> : null}
          <details className="cronActivityDetails">
            <summary>Detail pemeriksaan <ChevronDown size={13} aria-hidden="true" /></summary>
            <div>
              <p>Pemeriksaan selesai: {cronDate(health?.last_checked_at)}</p>
              {schedule?.activity?.updated_at ? <p>Perubahan aktivitas: {cronDate(schedule.activity.updated_at)}</p> : null}
              {schedule?.last_run_status ? <p>Siklus terakhir ({({ completed: "selesai", failed: "gagal", cancelled: "dibatalkan", running: "berjalan", queued: "mengantre" } as Record<string, string>)[schedule.last_run_status] ?? schedule.last_run_status}): {schedule.last_run_message || "Belum ada ringkasan"} · {cronDate(schedule.last_finished_at || schedule.last_started_at)}</p> : <p>Belum ada siklus cron tercatat.</p>}
              <p>Data diterima: {receivedAt ? cronDate(new Date(receivedAt).toISOString()) : "Belum tersedia"} · diperbarui otomatis setiap 15 detik.</p>
            </div>
          </details>
        </div>
      </div>
      <div className="cronActivityMeta">
        <div><span>{view.nextLabel}</span><strong>{cronDate(schedule?.next_run_at)}</strong></div>
        {capacity?.enabled ? <div><span>{capacity.daily_mode ? "Antrean tersimpan lintas tanggal" : "Kapasitas YouTube"}</span><strong>{capacity.daily_mode ? `Jadwal ${capacity.scheduled_count} · cadangan lama Private ${capacity.private_count}` : `Jadwal ${capacity.scheduled_count}/${capacity.scheduled_limit} · Private ${capacity.private_count}/${capacity.private_limit}`}</strong>{capacity.daily_mode ? <span>Antrean ini terpisah dari target produksi hari ini.</span> : null}</div> : null}
        {queue ? <div><span><Activity size={12} aria-hidden="true" /> Antrean upload studio</span><strong>YouTube {queue.youtube.running} berjalan, {queue.youtube.queued} menunggu <i>·</i> TikTok {queue.tiktok.running} berjalan, {queue.tiktok.queued} menunggu</strong></div> : null}
      </div>
    </section>
  );
}
