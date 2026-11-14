export type StudioView = "create" | "results" | "history" | "automation" | "settings";

export function studioViewFromHash(hash: string): StudioView {
  const view = hash.replace(/^#/, "");
  return ["results", "history", "automation", "settings"].includes(view)
    ? view as StudioView : "create";
}

export const STUDIO_VIEWS: Record<StudioView, { title: string; description: string }> = {
  create: { title: "Ruang untuk ide berikutnya.", description: "Mulai dari video, artikel, atau cerita. Siapkan hasil yang layak ditonton." },
  results: { title: "Hasil video", description: "Tinjau hasil akhir, periksa kualitas, lalu unduh atau masukkan ke antrean." },
  history: { title: "Riwayat produksi", description: "Temukan kembali proses, hasil video, dan status distribusinya." },
  automation: { title: "Otomasi & antrean", description: "Lihat apa yang sedang dikerjakan, target harian, dan pekerjaan yang membutuhkan perhatian." },
  settings: { title: "Koneksi platform", description: "Kelola akses YouTube dan TikTok untuk proses upload Anda." },
};
