export type StudioView = "overview" | "create" | "results" | "history" | "automation" | "facebook" | "settings";

export function studioViewFromHash(hash: string): StudioView {
  const view = hash.replace(/^#/, "");
  if (!view || view === "overview") return "overview";
  return ["results", "history", "automation", "facebook", "settings"].includes(view)
    ? view as StudioView : "create";
}

export const STUDIO_VIEWS: Record<StudioView, { title: string; description: string }> = {
  overview: { title: "Semua produksi, satu tempat.", description: "Pantau pekerjaan, tinjau hasil, dan tentukan langkah berikutnya." },
  create: { title: "Wujudkan ide berikutnya.", description: "Pilih format, masukkan sumber, lalu siapkan video Anda." },
  results: { title: "Hasil video", description: "Tinjau hasil akhir, periksa kualitas, lalu unduh atau masukkan ke antrean." },
  history: { title: "Riwayat produksi", description: "Temukan kembali proses, hasil video, dan status distribusinya." },
  automation: { title: "Kantor AI", description: "Pantau arahan koordinator, pekerjaan tiap bagian, dan hasil distribusi video." },
  facebook: { title: "Facebook Reels", description: "Produksi pendek dengan pilihan momen, caption, dan pemeriksaan khusus Facebook." },
  settings: { title: "Koneksi platform", description: "Kelola akses YouTube, TikTok, dan Facebook untuk proses upload Anda." },
};
