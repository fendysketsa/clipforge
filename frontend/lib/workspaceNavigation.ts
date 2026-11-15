export type StudioView = "create" | "results" | "history" | "automation" | "facebook" | "settings";

export function studioViewFromHash(hash: string): StudioView {
  const view = hash.replace(/^#/, "");
  return ["results", "history", "automation", "facebook", "settings"].includes(view)
    ? view as StudioView : "create";
}

export const STUDIO_VIEWS: Record<StudioView, { title: string; description: string }> = {
  create: { title: "Ruang untuk ide berikutnya.", description: "Mulai dari video, artikel, atau cerita. Siapkan hasil yang layak ditonton." },
  results: { title: "Hasil video", description: "Tinjau hasil akhir, periksa kualitas, lalu unduh atau masukkan ke antrean." },
  history: { title: "Riwayat produksi", description: "Temukan kembali proses, hasil video, dan status distribusinya." },
  automation: { title: "Otomasi & antrean", description: "Lihat apa yang sedang dikerjakan, target harian, dan pekerjaan yang membutuhkan perhatian." },
  facebook: { title: "Facebook Reels", description: "Produksi pendek dengan pilihan momen, caption, dan pemeriksaan khusus Facebook." },
  settings: { title: "Koneksi platform", description: "Kelola akses YouTube, TikTok, dan Facebook untuk proses upload Anda." },
};
