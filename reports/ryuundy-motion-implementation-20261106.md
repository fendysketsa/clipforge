# RYUUNDY motion inserts dan penyelesaian cooldown seleksi

Status: source, tes, demo, dan aktivasi produksi versi ini selesai.
Aktivasi terkonfirmasi pada 6 November 2026 pukul 14:56 WIB: kelima hash
runtime cocok dengan source tervalidasi, API sehat, serta cron enabled dan
scheduler_running kembali true. Bukti: `ryuundy-motion-completion-20261106.json`.
Laporan aktivasi 11:27 WIB adalah versi lama dan kini telah digantikan oleh
laporan aktivasi terbaru yang mencakup cooldown serta renderer motion.

Pada pemeriksaan setelah aktivasi, tidak ada job atau campaign aktif. Scheduler
menunggu kapasitas jadwal/Private dan menetapkan pemeriksaan berikutnya pada
16:01 WIB. Implementasi berlaku untuk render baru; hasil lama tidak diubah.
Demo dan smoke render yang dijelaskan di bawah tetap merupakan bukti lokal
dengan source sintetis, bukan klaim bahwa render terjadwal baru sudah selesai.

## Perilaku yang tersedia

`backend/ryuundy_motion.py` menambahkan tiga keluarga visual ke alur
`clipper.export_clip` untuk Short Auto FYP:

- `freeze_inset`: satu frame sumber ditahan sebagai panel analisis terpisah,
  dengan cuplikan ucapan yang cocok dengan transkrip pada timestamp tersebut.
- `cutout_stop_motion`: crop persegi panjang area sumber yang sudah direview
  diangkat dan diperbesar bertahap dari posisi aslinya. Crop detail didecode
  langsung dari sumber beresolusi asli. Ini bukan segmentasi rambut/tubuh.
- `step_diagram`: satu objek kertas bergerak dan kalimat panjang berubah menjadi
  dua baris. Hanya tersedia ketika sumber memang menjelaskan pemisahan baris
  subtitle/caption; tidak dipaksakan untuk topik lain.

Objek memiliki 12 pose per detik, dengan output 30fps. Sutradara memilih paling
banyak satu insert otomatis dari perubahan/hasil yang benar-benar diucapkan
atau pola manfaat praktis yang lengkap. Plain footage tanpa pemicu tidak
mendapat efek berdasarkan timer acak.

Video sumber tetap berjalan. Insert tidak menambah, menghilangkan, atau
mengulang waktu sumber; audio serta caption tetap mengikuti timeline yang
sama. Caption dirender sesudah insert. Normalisasi/mixing dan fitur outro
yang memang sudah ada dalam pipeline tidak diubah oleh modul ini.

Untuk landscape di dalam portrait, panel diperkecil agar menempati ruang di
atas sumber. Jika ruang aman tidak cukup, insert dilewati. Bukti/sumber,
layout multi-panel, kartu sosial, avatar reaction, konteks sensitif, dan
dialogue-first tertentu mendapat prioritas sehingga visual tidak ditumpuk.
Insert berakhir sebelum akhir sumber, sehingga tidak menimpa outro yang
mungkin sudah dikonfigurasi.

Asset prosedural dirender lokal melalui FFmpeg/librsvg; tidak ada panggilan
generasi gambar/video berbayar. Asset video insert berada dalam subfolder
`.ryuundy-motion`, di luar indeks publik `clips/*.mp4`, dan disimpan bersama
job untuk inspeksi. Asset tersebut tidak boleh menjadi kandidat upload.
Kegagalan persiapan opsional dicatat di sidecar dan rendering utama berlanjut.

## Bukti hasil

- `ryuundy-motion-demo-20261106.mp4`: studi visual asli 18 detik, 1080x1920,
  30fps, tanpa narasi. Memperlihatkan tiga teknik di atas. Scene dan contoh
  teks dibuat khusus untuk studi ini, tanpa footage kreator lain.
- Tiga frame detail dan grid temporal dipakai untuk memeriksa penempatan,
  keterbacaan, perubahan objek, dan kembali ke sumber. Demo tidak menguji
  performa wajah manusia atau narasi; klaim review dibatasi pada studi visual.
- Regresi video membandingkan seluruh 300 frame pada area sumber yang tidak
  tertutup insert. Pixel checksum tetap identik dan hash audio sama. EOF movie
  insert teruji finite tanpa output-duration fence pada regresi tersebut.
- Render smoke melalui fungsi `clipper.export_clip` memakai source sintetis
  30 detik; sidecar menunjukkan motion enabled/rendered, output 1080x1920,
  dan durasi 30 detik. QC exposure meminta review pada source test-pattern;
  smoke ini memverifikasi integrasi renderer, bukan persetujuan upload konten.
- 436 tes terkait lulus: 395 seleksi/cooldown/motion/caption/deployment/News dan
  41 API discovery/cron. Setelah penyesuaian penyimpanan asset dan kualitas
  crop, 71 tes motion/deployment diulang. Hasil tersimpan dalam laporan JSON.

Demo dapat direproduksi:

```bash
python scripts/render-ryuundy-motion-demo.py
```

## Permintaan crop yang sudah direview

File opsional `motion.json` berada di folder job yang merupakan parent folder
`clips/`. `clip_start` dan `quote` harus cocok dengan klip serta transkripnya.
Koordinat region adalah x, y, lebar, tinggi relatif terhadap sumber asli.

```json
{
  "clips": [
    {
      "clip_start": 120.0,
      "kind": "cutout_stop_motion",
      "quote": "Kutipan persis minimal empat kata dari transkrip klip ini.",
      "review_status": "source_checked",
      "reviewed_by": "editor yang memeriksa frame",
      "region": [0.2, 0.15, 0.3, 0.4]
    }
  ]
}
```

Manifest yang tidak sah tidak memberi izin kepada model untuk mengarang ROI.
Region yang belum direview tidak dipakai untuk crop detail. Tidak ada klaim
bahwa anotasi koordinat membuktikan kebenaran pernyataan pembicara.

## Aktivasi dan verifikasi

```bash
sudo bash /www/wwwroot/clipper/clipforge/scripts/activate-ryuundy-reference-learning.sh
```

Script membangun backend, memeriksa hash kelima modul serta decoder SVG dalam
image, mem-pause peluncuran cron baru, menunggu pekerjaan aktif selesai,
memeriksa proses media, men-stage dan compile modul, memeriksa idle sekali lagi,
lalu me-restart backend yang sama. Decoder runtime ikut diperiksa sebelum
penggantian modul; kontrol cron semula dipulihkan jika tahap menunggu gagal.
Frontend tidak berubah.

Kelima modul: `api`, `youtube_remote_status`, `ryuundy_reference_learning`,
`clipper`, dan `ryuundy_motion`. Laporan aktivasi baru harus memuat hash versi
ini di `ryuundy-reference-learning-activation.json`. `--skip-build` hanya dapat
dipakai setelah image baru yang cocok selesai dibangun. Tidak ada job aktif
yang dibatalkan dan tidak ada upload yang diulang untuk aktivasi ini.

Pemeriksaan setelah script aktivasi selesai:

```bash
python scripts/verify-ryuundy-deployment.py
```

Verifier mencocokkan source dengan manifest validasi tes, kelima hash dari
laporan aktivasi, dan API health/scheduler live. Laporan lama atau modul motion
yang belum tercantum menghasilkan exit nonzero dan `activation_not_confirmed`.
Hasil ditulis ke `ryuundy-motion-completion-20261106.json`; bukti source/tes
berada di `ryuundy-motion-validation-20261106.json`.
