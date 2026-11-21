# Kantor AI ClipForge

21 November 2026, Asia/Jakarta.

Kantor AI menambahkan koordinator operasional yang memantau worker produksi, QC/perbaikan, distribusi, pemulihan, cleanup, dan Facebook. Pemilihan sumber, render, audit AI, serta publikasi tetap dikerjakan oleh owner pipeline yang sudah ada. Koordinator memulihkan worker yang mati dan meminta pemeriksaan melalui owner tersebut; tidak membuat scheduler produksi kedua atau memberikan kelulusan QC sendiri.

## Perilaku operasional

- Satu thread koordinator memeriksa keadaan lokal setiap 30 detik. Worker yang masih hidup dibiarkan bekerja; worker yang mati dipulihkan sesuai setelan dan antreannya.
- Setelan cron yang tersimpan lebih diutamakan daripada default environment. Koordinator tidak mengaktifkan cron, publikasi, retry, atau Facebook yang dijeda operator. Antrean upload eksplisit yang sudah ada tetap boleh dilanjutkan walaupun penemuan sumber otomatis dijeda.
- Starter YouTube, TikTok, cron, generic upload sweeper, TikTok retry, dan Facebook memeriksa Thread yang sebenarnya di bawah lock. Subprocess upload yang masih hidup juga melindungi percobaan remote agar tidak ada transfer kedua.
- Arahan dicatat sebelum dispatch ke `backend/data/ai_office.json`, atomik dengan izin 0600. Jurnal menyimpan paling banyak 60 tugas. Kegagalan dispatch memakai backoff 60, 300, 900, dan 3600 detik yang bertahan setelah restart.
- Jurnal rusak tidak ditimpa dan tidak mengizinkan dispatch tanpa bukti. Kegagalan menulis hasil dipulihkan tanpa mengulangi callback yang sudah berhasil. Intent yang terputus setelah restart ditandai deferred sampai status worker diperiksa kembali.
- Satu kegagalan penugasan atau ketidaktersediaan status Facebook tidak menghentikan departemen lain. Error koordinator hanya mengekspos jenis exception; detail provider Facebook dibatasi dan dibersihkan dari data sensitif.
- Tombol pemeriksaan membangunkan owner yang diaktifkan, tanpa menghapus backoff verifikasi posting. Status tugas completed berarti arahan ke worker selesai; kelulusan video dan keberhasilan publikasi tetap memerlukan bukti masing-masing.
- GET `/api/ai-office` hanya membaca keadaan. POST `/api/ai-office/run` meminta koordinator melakukan pemeriksaan berikutnya. Snapshot tidak mengirim seluruh log upload, rencana naskah, atau kredensial.

## Antarmuka dan gerak proses

Navigasi `#automation` sekarang bernama **Kantor AI**. Panel koordinator ditambahkan secara lazy di atas panel cron dan antrean distribusi. Status departemen, pemeriksaan terakhir/berikutnya, dan keputusan terakhir berasal dari API. Status lama atau worker yang tidak tersedia ditandai secara eksplisit.

Alur bergerak menunjukkan produksi → QC → distribusi serta cabang pemulihan, cleanup, dan Facebook. Aktivitas visual mengikuti status dan jumlah pekerjaan nyata; tidak ada angka progres atau kegiatan agen yang dibuat-buat. Preview pengujian memakai fixture yang diberi label terpisah dari runtime production.

Gerak dapat dijeda dari tombol tampilan dan berhenti ketika data stale, koordinator tidak tersedia/dijeda, tab tersembunyi, atau perangkat meminta reduced-motion. Saat worker menunggu, grafik tidak mengarang proses aktif. Heartbeat koordinator menunjukkan pemantauan, sedangkan batang aktivitas menandai proses tanpa persentase palsu.

Implementasi memakai Python standard library dan komponen/CSS yang sudah tersedia. Tidak menambah paket, layanan LLM, browser, atau pipeline render untuk koordinator.

## Startup dan deployment

`AI_OFFICE_ENABLED=true` menjadi default Compose. Mengubahnya ke false hanya menjeda koordinator; worker tetap mengikuti setelan masing-masing. Source baru, readiness backend, serta marker frontend diperiksa melalui startup/build normal. Readiness mensyaratkan worker koordinator nyata, jurnal siap, heartbeat baru, dan capability yang sesuai ketika fitur diaktifkan; jeda QC departemen karena layanan pihak ketiga tidak disamakan dengan kegagalan koordinator.

Satu-satunya perintah deployment tetap:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

## Bukti dan status

Backend: **511 pengujian lulus** pada koordinator, lifecycle worker, deployment, cron recovery/health, YouTube, upload attention, rejected upload cleanup, terminal output cleanup, source download, dan Facebook. Seluruh source Python backend juga berhasil dikompilasi.

Frontend: lint/TypeScript dan **11 berkas pengujian Node lulus**. Build preview `UYU1dnuRYFvqoO_Zv7kzj` lulus pemeriksaan build, source prepare, dan HTTP health. Setelah marker animasi terakhir ditambahkan, subset backend koordinator/deployment diperiksa ulang: 48 pengujian lulus.

`browser-ui-review.json` merekam pengujian preview dengan fixture office dan request dashboard lain yang hanya baca: lebar 1440, 1280, 900, 390, dan 320, kedua tema, grid 3/2/1 kolom, tanpa overflow atau error JavaScript. Waktu animasi CSS terbukti bertambah untuk departemen fixture yang aktif; manual pause, reduced-motion, tab tersembunyi, stale, dan disabled berhenti sesuai kondisi. Screenshot `office-*.png` adalah preview fixture, bukan bukti aktivasi production. Rekaman video opsional tidak dibuat karena recorder Playwright di host tidak mempunyai binary ffmpeg-nya; pemeriksaan gerak langsung di browser tetap lulus. Server preview dihentikan setelah pemeriksaan.

## Pemeriksaan production terbaru

`runtime-before-deployment.json` adalah snapshot awal ketika endpoint office masih 404. Pemeriksaan lanjutan sesudah turn kembali berjalan menemukan **koordinator dasar sudah aktif**, worker hidup, jurnal siap, dan heartbeat baru. Bukti ada pada `runtime-final-check.json` dan `production-browser-review.json`.

Production menampilkan enam departemen, tetapi **peta proses animasi belum ada** (`animated_process_map=0`, `motion_toggle=0`). Build production `xzrIQVu6kg4Ej1bxxoZQZ` berbeda dari preview terbaru. `release-comparison.json` juga menunjukkan release backend dan Telegram yang tersimpan belum cocok dengan fingerprint source akhir. Karena itu source/perbaikan serta animasi terbaru masih memerlukan rebuild standar; refresh saja tidak mengaktifkannya.

Pemeriksaan akses sudo sebelumnya menghasilkan `sudo: a password is required`. Tidak ada render aktif yang dihentikan, hot patch, atau perubahan langsung pada antrean/pengaturan production untuk mengaktifkan fitur ini. Deployment baru harus tetap dibuktikan melalui release/readiness sesudah perintah standar berhasil.
