export type OfficeState = "starting" | "working" | "waiting" | "disabled" | "degraded";

export type OfficeIncident = {
  id: string; department: string; title: string; reason: string; action: string;
  automatic: boolean; state: "waiting" | "needs_operator" | "resolved";
  severity: "critical" | "warning" | "info"; destination: "settings" | "history" | "facebook";
  job_id?: string | null; upload_id?: string | null;
  first_seen_at?: string | null; last_seen_at?: string | null; resolved_at?: string | null;
};

export type AIOfficeSnapshot = {
  version: 1;
  control_version?: number;
  incident_observation_available?: boolean;
  incidents?: OfficeIncident[];
  resolved_incidents?: OfficeIncident[];
  director?: { name: string; role: string; active_jobs: number; active_uploads: number;
    open_incidents: number; needs_operator: number };
  enabled: boolean;
  worker_running: boolean;
  state: OfficeState;
  label: string;
  detail: string;
  last_tick_at: string | null;
  next_tick_at: string | null;
  departments: {
    id: string; name: string; role: string; state: Exclude<OfficeState, "starting">;
    detail: string; active_count: number;
  }[];
  tasks: {
    id: string; department: string; action: string;
    status: "running" | "completed" | "deferred" | "failed";
    started_at: string; finished_at: string | null; summary: string; next_retry_at: string | null;
  }[];
};

export function officeStatus(snapshot: AIOfficeSnapshot | null, now: number, refreshFailed = false) {
  if (!snapshot) return { state: "starting", label: refreshFailed ? "Koordinator belum tersedia" : "Membaca status koordinator…",
    detail: refreshFailed ? "Status Kantor AI belum dapat dibaca. Aktivitas produksi tetap dapat dilihat di bawah." : "Mengambil status dan keputusan terakhir dari server.", stale: false };
  if (!snapshot.enabled) return { state: "disabled", label: snapshot.label || "Koordinator dijeda", detail: snapshot.detail, stale: false };
  const checkedAt = Date.parse(snapshot.last_tick_at || "");
  const stale = refreshFailed || (!Number.isFinite(checkedAt) ? snapshot.state !== "starting" : now - checkedAt > 120_000 || checkedAt - now > 30_000);
  if (!snapshot.worker_running || stale) return { state: "degraded", label: "Status koordinator perlu diperiksa",
    detail: !snapshot.worker_running ? "Worker koordinator belum berjalan. Status produksi terakhir tetap ditampilkan."
      : "Pembaruan koordinator belum diterima. Aktivitas terakhir ditampilkan sambil menunggu pemeriksaan berikutnya.", stale: true };
  return { state: snapshot.state, label: snapshot.label, detail: snapshot.detail, stale: false };
}

/** Motion follows observed work; pausing the view never pauses server workers. */
export function officeMotion(snapshot: AIOfficeSnapshot | null, now: number, refreshFailed = false, visible = true) {
  const status = officeStatus(snapshot, now, refreshFailed);
  const current = Boolean(snapshot?.enabled && snapshot.worker_running && !status.stale
    && status.state !== "starting" && status.state !== "disabled");
  return {
    canAnimate: current && visible,
    monitoring: current && visible && ["working", "waiting"].includes(status.state),
    activeDepartments: current ? snapshot!.departments.filter(department => department.state === "working"
      && Number.isFinite(department.active_count) && department.active_count > 0).map(department => department.id) : [],
  };
}

export const officeStateLabel: Record<OfficeState, string> = {
  starting: "Menyiapkan", working: "Bekerja", waiting: "Menunggu giliran", disabled: "Dijeda", degraded: "Perlu pemulihan",
};

export const officeTaskLabel = {
  running: "Dikerjakan", completed: "Arahan diterima", deferred: "Menunggu giliran", failed: "Belum selesai",
} as const;

export function officeIncidents(snapshot: AIOfficeSnapshot | null, filter = "all", department = "all") {
  return (snapshot?.incidents ?? []).filter(row => row.state !== "resolved"
    && (department === "all" || row.department === department)
    && (filter === "all" || (filter === "operator" ? row.state === "needs_operator" : row.automatic)));
}

export function officeTime(value: string | null) {
  if (!value) return "Belum tersedia";
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat("id-ID", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Jakarta",
  }).format(date) + " WIB" : "Belum tersedia";
}
