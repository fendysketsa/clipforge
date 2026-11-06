# Penolakan seleksi dan pengulangan sumber cron, 6 November 2026

Reference learning sebelumnya sudah diaktifkan pada 11:27 WIB menurut
`ryuundy-reference-learning-activation.json`. Keempat hash source cocok ketika
diperiksa sebelum perbaikan insiden ini. Pemeriksaan Docker langsung tetap
memerlukan sudo. Fitur freeze/cutout/stop-motion masih berupa treatment.

Screenshot memperlihatkan dua job berbeda. Sumber Minecraft `9FOhn2EOVsE`
gagal pada seleksi setelah 58 segmen ditranskripsikan. Model tidak mengembalikan
ranking klip yang dapat digunakan; heuristik, repair, dan perluasan sampai 105
detik juga tidak menghasilkan kandidat yang lolos. Workspace gagal telah
dihapus, sehingga penyebab detail skor setiap kandidat tidak dapat direplay
dari transkrip lama. Tidak ada dasar untuk memaksa klip tersebut lolos.

Masalah tambahan yang terkonfirmasi: sumber yang sama muncul dalam enam
percobaan campaign. Cooldown scheduler hanya membaca penggunaan sumber yang
berhasil dirender, dan secara sengaja melewati job failed/cancelled. Akibatnya
penolakan seleksi terminal tidak masuk daftar pengecualian putaran berikutnya.

Perbaikan source:

- Sumber cron dengan pesan penolakan seleksi yang spesifik, status job failed,
  dan nol klip mendapat cooldown default 24 jam (batas konfigurasi 1–168 jam).
- Checkpoint campaign menjadi bukti tahan cleanup; job gagal yang dihapus dari
  Riwayat tidak membuat sumber segera terpilih lagi.
- Timestamp penolakan dicatat tersendiri untuk kejadian baru. Checkpoint lama
  memakai timestamp parent yang tersedia.
- Network/model/render/upload error, cancellation, hasil review, dan hasil
  dengan klip tidak diklasifikasikan sebagai penolakan seleksi tersebut.
- Tidak menandai sumber gagal sebagai sukses, tidak membuat larangan permanen,
  dan tidak melonggarkan syarat kualitas atau alur manual.

Validasi: 150 tes seleksi/context/deployment/cooldown dan 41 tes API terkait
lulus (191 total). Setelah penambahan syarat ownership cron pada pencatatan
timestamp, 21 tes cooldown diulang dan tetap lulus. Replay offline atas 100
campaign tersimpan, dengan job cards dianggap sudah dibersihkan, memastikan
sumber bermasalah dikecualikan dari cron dan tetap tidak masuk riwayat sukses.
Replay tidak menulis state produksi.

Sumber Roblox pengganti `d_QKCUP345Y` tetap berjalan. Pada pemeriksaan pukul
12:02 WIB, proses sudah melewati verifikasi download dan mencapai transkripsi
57% di CUDA (progress keseluruhan 37%). Tidak ada restart, stop, delete, atau
re-upload yang dilakukan pada insiden ini.

Status patch cooldown: **aktif di runtime**, terkonfirmasi 6 November 2026
pukul 14:56 WIB setelah pengguna menjalankan script aktivasi. Hash API terbaru
dan empat modul terkait cocok dengan source yang diuji. API sehat dan cron
kembali enabled/scheduler_running. Laporan aktivasi 11:27 WIB merupakan versi
lama; bukti terkini berada di `ryuundy-motion-completion-20261106.json`.

Bukti: `selection-rejection-incident-20261106.json` dan
`selection-rejection-replay-20261106.json`.
