import type { AutomaticHandling } from "../types/clip.type";

/** Backend evidence owns urgency; a failed attempt alone is not a manual task. */
export function automaticHandlingView(handling?: AutomaticHandling | null) {
  if (!handling) return null;
  const urgent = handling.urgent === true;
  const labels = {
    processing: "Sedang ditangani otomatis",
    waiting: "Menunggu pemeriksaan",
    blocked: "Produksi gagal · tanpa hasil",
    archiving: "Dibersihkan otomatis",
    archived: "Diarsipkan otomatis",
    urgent: "Menunggu sistem",
  };
  return {
    state: handling.state,
    label: urgent ? "Perlu tindakan Anda" : labels[handling.state],
    detail: handling.reason,
    action: handling.action,
    urgent,
    nextCheckAt: handling.action === "retain" ? null : handling.next_check_at,
  };
}

/** Never replace real upload progress/confirmation with a planned disposition. */
export function automaticUploadSummary(handling: AutomaticHandling | null | undefined, recordedState: string) {
  const view = automaticHandlingView(handling);
  if (!view || ["running", "queued", "verified", "partial"].includes(recordedState)) return null;
  return {
    state: view.state === "archived" ? "cancelled" as const : "unverified" as const,
    label: view.label,
    title: view.detail,
  };
}
