export type OfficeState = "starting" | "working" | "waiting" | "disabled" | "degraded";

export type OfficeIncident = {
  id: string; department: string; title: string; reason: string; action: string;
  automatic: boolean; state: "waiting" | "needs_operator" | "resolved";
  severity: "critical" | "warning" | "info"; destination: "settings" | "history" | "facebook";
  job_id?: string | null; upload_id?: string | null;
  first_seen_at?: string | null; last_seen_at?: string | null; resolved_at?: string | null;
};

export type OfficeDirective = {
  id: string; key: string; department: string; title: string; reason: string;
  action: string; priority: "high" | "normal"; automatic: boolean;
  status: "active" | "blocked"; destination: string;
  evidence?: Record<string, number>; skills?: string[];
};

export type OfficeStrategy = {
  version: number; name: string; role: string; mission: string; audience: string;
  focus: string[]; priority_platforms: string[]; content_standard: string[]; model: string;
};

export type OfficeRepair = {
  id: string; incident_id?: string | null; incident_action?: string | null;
  department: string; action: string; status: "running" | "completed" | "deferred" | "failed";
  summary: string; started_at: string; finished_at: string | null;
};

export type OfficeDirector = {
  version?: number; name: string; role: string; model?: string; supervision?: string;
  strategy?: OfficeStrategy; directives?: OfficeDirective[];
  strategy_revision?: string; directives_at?: string | null;
  skills_version?: number; skills_applied?: number; skills_total?: number;
  learning?: { version: number; total: number; last_recorded_at: string | null;
    index_fresh: boolean; rules: string[] };
  repairs?: OfficeRepair[]; active_repair?: OfficeRepair | null;
  repair_count?: number; autonomous_repair?: boolean;
  active_jobs: number; active_uploads: number; open_incidents: number; needs_operator: number;
};

export const officeRepairAction: Record<string, string> = {
  verify_upload: "Mencocokkan bukti pengiriman",
  retry_tiktok: "Mengulang sebelum Post",
  recover_scheduled_uploads: "Menyambung antrean upload",
  recover_facebook: "Memulihkan Facebook",
  cleanup_history: "Mengarsipkan hasil gagal",
  use_supported_cron: "Memakai sumber cron yang didukung",
  worker_supervision: "Memulihkan worker",
};

export type AIOfficeSnapshot = {
  version: 1;
  activity?: { version: 1; available: boolean; observed_at: string; departments: OfficeDepartmentActivity[] };
  control_version?: number;
  incident_observation_available?: boolean;
  incidents?: OfficeIncident[];
  resolved_incidents?: OfficeIncident[];
  director?: OfficeDirector;
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

export function officeDirectives(snapshot: AIOfficeSnapshot | null, status?: OfficeDirective["status"]): OfficeDirective[] {
  const rows = snapshot?.director?.directives || [];
  return status ? rows.filter(row => row.status === status) : rows;
}

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

export type OfficeWorkState = "running" | "queued" | "blocked" | "idle" | "paused" | "unavailable";
export type OfficeWork = {
  id: string; state: "running" | "queued" | "blocked"; title: string; stage: string;
  kind: string; progress_percent: number | null; job_id: string | null; upload_id: string | null;
  platform: string | null; destination: "history" | "facebook";
};
export type OfficeDepartmentActivity = {
  id: string; available: boolean; state: OfficeWorkState; running_count: number;
  queued_count: number; blocked_count: number; total_count: number; detail: string; work: OfficeWork[];
};
export const officeWorkLabel: Record<OfficeWorkState, string> = {
  running: "Bekerja", queued: "Mengantre", blocked: "Tertahan", idle: "Siaga", paused: "Dijeda", unavailable: "Belum terbaca",
};

export function officeActivityStatus(snapshot: AIOfficeSnapshot | null, now: number, failed = false) {
  const activity = snapshot?.activity;
  const observed = Date.parse(activity?.observed_at || "");
  const fresh = !failed && activity?.version === 1 && activity.available && Number.isFinite(observed)
    && now - observed <= 30_000 && observed - now <= 5_000;
  return { fresh: Boolean(fresh), observedAt: activity?.observed_at || null };
}

export function officeAgentWork(snapshot: AIOfficeSnapshot | null, id: string, now: number, failed = false): OfficeDepartmentActivity {
  const row = snapshot?.activity?.departments.find(item => item.id === id);
  if (!officeActivityStatus(snapshot, now, failed).fresh || !row?.available) {
    return { id, available: false, state: "unavailable", running_count: 0, queued_count: 0, blocked_count: 0,
      total_count: 0, detail: snapshot?.activity?.version === 1 ? "Menunggu pembaruan aktivitas" : "Menunggu data antrean dari server", work: [] };
  }
  return row;
}

export function officeSpeech(snapshot: AIOfficeSnapshot, id: string, now: number, failed = false) {
  const row = officeAgentWork(snapshot, id, now, failed);
  const work = row.work[0];
  return { kind: "status", text: work ? `${work.stage}${work.progress_percent != null && work.state === "running" ? ` · ${Math.round(work.progress_percent)}%` : ""}: ${work.title}` : row.detail };
}
