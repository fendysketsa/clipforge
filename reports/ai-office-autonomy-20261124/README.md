# Pemulihan otomatis Kantor AI — 24 November 2026

Implementasi sumber selesai. Aktivasi produksi belum berhasil: perintah deployment standar berhenti karena sudo meminta password. Backend produksi masih sehat dan belum melaporkan `autonomous_recovery_version: 1`.

## Keputusan otomatis

- QC Facebook mencoba model utama lalu maksimal satu model cadangan yang sudah dikonfigurasi di proyek, pada endpoint dan aturan ekspor yang sama. Perpindahan hanya untuk HTTP 429/502/503/504; penolakan keamanan 422 dan masalah otorisasi tidak berpindah model. Bukti PASS tetap terikat pada file, sumber, model, dan gerbang QC sebenarnya.
- Jadwal pemulihan QC tersimpan sebelum permintaan provider. Jeda bertingkat 5 menit, 15 menit, 1 jam, lalu 6 jam; `Retry-After` provider dihormati hingga 24 jam. Restart dan tombol koordinasi tidak menghapus jeda.
- Pemeriksaan dialog Story memakai nama dialog yang tepat dan menutupnya melalui Tutup. Pemeriksaan langsung pada akun tersimpan menghasilkan `public_verified: true` dan nol dialog tersisa, tanpa mengganti pilihan atau menekan Bagikan.
- Pemulihan memeriksa semua upload Facebook, termasuk upload tanpa run autopilot. Gangguan jaringan sebelum Post mengikuti batas tiga percobaan; kegagalan dispatch memiliki cooldown tersimpan. Posting tidak pasti dicocokkan melalui identitas remote, bukan dikirim ulang.
- Tiga Story dari 15–17 November terbukti `submission_started: false` dan sudah lebih dari 24 jam. Setelah aktivasi, kebijakan akan menandainya dilewati tanpa publikasi, menyimpan file, identitas, pesan kegagalan, dan jumlah percobaan. UI membedakan dilewati dari upload berhasil. Keputusan terhadap data nyata dicatat dalam `live-diagnosis.json`; belum dieksekusi di produksi.
- Hasil yang menunggu QC menahan produksi tambahan pada formatnya, sementara format Facebook lain yang memenuhi syarat dapat berjalan. Story baru memerlukan pemeriksaan audiens yang berhasil; hasil probe dibatasi jeda dan diikat ke akun.
- Eksperimen cerita tanpa bukti izin provider dilewati otomatis agar pemilihan sumber cron biasa tetap berjalan. Tidak ada bukti izin atau QC yang dibuat-buat. Kuota dan pengaturan operator tetap dipertahankan.

## Validasi

- 285 pengujian backend lulus: pemulihan Facebook, autopilot, workspace, edukasi, Kantor AI, deployment, cerita cron, upload attention, dan backlog.
- 13 berkas pengujian Node frontend lulus; build mencakup pemeriksaan TypeScript.
- Build frontend dan pemeriksaan manifest build/startup lulus. Ini merupakan bukti build lokal, bukan aktivasi layanan produksi.
- Regresi mencakup larangan replay Post, bukti pra-pengiriman yang eksplisit, batas retry, restart ketika QC sedang berjalan, fingerprint QC model cadangan, perubahan file, isolasi akun probe, dan pengaturan jeda.
- Pengujian API memakai fixture/mocks. Eksekusi perlu izin socket lokal karena TestClient tertahan dalam sandbox; regresi lengkap berhasil setelah izin tersebut diberikan.
- Tidak ada publikasi baru yang dilakukan selama diagnosis. Tidak ada sesi, pengaturan privasi, publication hold, atau identitas remote yang dihapus.

## Deployment

Perintah yang sudah dicoba:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

Hasil: `sudo: a password is required`. Tidak ada jalur aktivasi alternatif yang digunakan. Readiness normal sekarang mensyaratkan kemampuan pemulihan baru dan source verification tetap mencakup modul Python yang ditambahkan. Bukti status produksi terakhir ada dalam `runtime-check.json`.
