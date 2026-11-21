import type { TikTokUploadJob, YouTubeUploadJob } from "../types/clip.type";

export type UploadAttentionSnapshot = {
  version: number; enabled: boolean; worker_running: boolean; error?: string;
  rejected_upload_cleanup_version?: number;
  items: { id: string; state: "held" | "checking" | "waiting"; reason: string;
    action: string; attempts: number; checked_at?: number | null; next_check_at?: number | null; urgent?: boolean }[];
};

export type StudioQueueItem = {
  id: string; platform: "YouTube" | "TikTok"; title: string; updatedAt: string;
  state: "running" | "queued" | "verified" | "attention" | "failed" | "held";
  label: string; privacy: string; detail: string; studioUrl: string;
  automatic?: boolean; nextCheckAt?: number | null; checkedAt?: number | null;
  urgent?: boolean;
};

export function studioQueueItems(youtube: YouTubeUploadJob[], tiktok: TikTokUploadJob[], attention?: UploadAttentionSnapshot | null): StudioQueueItem[] {
  const items: StudioQueueItem[] = [];
  const seen = new Set<string>();
  for (const row of [...youtube].sort((a,b) => Date.parse(b.updated_at)-Date.parse(a.updated_at))) {
    const transferred = row.file_selection_started || row.logs?.some(line => line.startsWith("Video dipilih:") || line.startsWith("Menyerahkan file ke YouTube Studio:") || line.startsWith("REMOTE_UPLOAD_CHECKPOINT"));
    if (row.attention_archived_at || row.dry_run || (row.status === "cancelled" && !row.video_url && !transferred)) continue;
    const videoId = row.video_url?.match(/[?&]v=([A-Za-z0-9_-]{11})(?:&|$)/)?.[1];
    const identity = videoId || row.id;
    if (seen.has(identity)) continue;
    seen.add(identity);
    const verified = row.status === "completed" && row.upload_confirmed && Boolean(videoId);
    const state = row.status === "running" || row.status === "queued" ? row.status
      : verified ? "verified" : row.video_url || transferred ? "attention" : "failed";
    items.push({id:`youtube-${row.id}`,platform:"YouTube",title:row.title || row.clip_name,updatedAt:row.updated_at,state,
      label:state === "verified" ? "Upload terverifikasi" : state === "attention" ? "Perlu verifikasi" : state === "failed" ? "Perlu ditangani" : state === "running" ? "Sedang diproses" : "Menunggu giliran",
      privacy:row.publish_at && Date.parse(row.publish_at) > Date.now() ? "Terjadwal" : row.visibility === "private" ? "Private" : row.visibility === "unlisted" ? "Tidak publik" : row.visibility === "public" ? "Publik" : "Privasi belum tersedia",
      detail:state === "attention" ? "Status video yang sudah ada dicocokkan sebelum pengiriman berikutnya." : row.error || (row.publish_at ? `Jadwal ${queueDate(row.publish_at)}` : ""),
      studioUrl:videoId ? `https://studio.youtube.com/video/${videoId}/edit` : "https://studio.youtube.com"});
  }
  for (const row of tiktok) {
    if (row.attention_archived_at || row.dry_run) continue;
    const exactPost = /^https:\/\/www\.tiktok\.com\/@[\w.]+\/video\/\d{10,25}(?:[?#].*)?$/.test(row.profile_url || "");
    const postIdentity = exactPost ? row.profile_url!.split(/[?#]/)[0] : `tiktok-${row.id}`;
    if (seen.has(postIdentity)) continue;
    seen.add(postIdentity);
    const verified = row.status === "completed" && row.upload_confirmed && exactPost;
    const uncertain = row.submission_started || row.submission_accepted || row.profile_url
      || row.logs?.some(line => line.startsWith("POST_SUBMIT_INTENT:") || line.startsWith("POST_API_ACCEPTED:"));
    if (row.status === "cancelled" && !uncertain) continue;
    const state = row.status === "running" || row.status === "queued" ? row.status
      : verified ? "verified" : uncertain ? "attention" : "failed";
    items.push({id:`tiktok-${row.id}`,platform:"TikTok",title:row.caption || row.clip_name,updatedAt:row.updated_at,state,
      label:state === "verified" ? "Upload terverifikasi" : state === "attention" ? "Perlu verifikasi" : state === "failed" ? "Perlu ditangani" : state === "running" ? "Sedang diproses" : "Menunggu giliran",
      privacy:row.visibility === "only_you" ? "Only you" : "Publik",
      detail:state === "attention" ? "Post pernah dikirim; sistem mencocokkan bukti agar video tidak terkirim dua kali." : row.error || "",
      studioUrl:"https://www.tiktok.com/tiktokstudio/content"});
  }
  const handling = new Map(attention?.items.map(item => [item.id, item]) ?? []);
  return items.map(row => {
    const item = handling.get(row.id);
    if (!item || ["verified", "queued", "running"].includes(row.state)) return row;
    const automatic = Boolean(attention?.enabled && attention?.worker_running);
    const urgent = item.urgent === true;
    return { ...row, state: urgent || item.state === "held" ? "held" as const : row.state,
      automatic: automatic && !urgent, urgent,
      label: urgent ? "Perlu tindakan Anda" : item.state === "held" ? "Menunggu bukti"
        : !attention?.enabled ? "Otomatis dijeda" : !attention.worker_running ? "Menunggu worker"
        : item.state === "checking" ? "Sedang diperiksa"
        : item.action.startsWith("archive") ? "Menyiapkan arsip otomatis" : "Terjadwal otomatis",
      detail: item.reason, nextCheckAt: item.next_check_at, checkedAt: item.checked_at };
  }).sort((a,b)=>Date.parse(b.updatedAt)-Date.parse(a.updatedAt));
}

export function queueDate(value: string) {
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat("id-ID", {
    day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit",timeZone:"Asia/Jakarta",
  }).format(date) + " WIB" : "Waktu belum tersedia";
}
