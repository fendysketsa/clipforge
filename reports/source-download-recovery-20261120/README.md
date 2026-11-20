# Pemulihan unduhan sumber dan riwayat produksi

Pemeriksaan 20 November 2026, Asia/Jakarta.

## Hasil operasional yang sudah diverifikasi

- Kegagalan lama `0e00b171d00d499e956d1c439c382203` berasal dari sumber YouTube `akd6qhczJz8`. Kartu ini tidak memiliki klip, kandidat, workspace, atau catatan upload.
- Percobaan berikutnya, `2c3f719e76b34944baa586fbc58bc3eb`, berhasil menyelesaikan satu klip dari sumber yang sama. Proses ini sudah berjalan saat investigasi; tidak dibuat ulang oleh pemeriksaan ini.
- Catatan upload YouTube `3a4f9778e4df4dcfb1a8996a0970a44e` berstatus completed dan upload_confirmed, dengan URL https://www.youtube.com/watch?v=tv9D7PIotOk.
- Catatan upload TikTok `70110ec016f94ff2a11c7cbaecccf1e2` berstatus completed dan upload_confirmed, dengan URL https://www.tiktok.com/@titikbalikislami/video/7710290579321605377.
- Identitas kedua upload diperiksa lagi setelah pembersihan dan tetap sama. Pemeriksaan ini tidak mengirim upload baru atau mengubah visibilitas platform.
- Bukti pemulihan disimpan secara atomik di `backend/data/source_download_recoveries/0e00b171d00d499e956d1c439c382203.json`, izin 0600. Setelah pengaman diperiksa ulang, kartu gagal kosong dihapus melalui API. GET kartu lama menghasilkan 404; respons DELETE menyatakan satu job dan nol output dihapus.
- Hasil pengganti memiliki peringatan exposure QC: render_qc_passed=false, render_qc_blocking=false, youtube_upload_ready=true. Keberhasilan upload bukan pernyataan bahwa seluruh QC lulus. Pengaman dan keputusan QC tidak diubah dalam perbaikan ini.

Bukti terpilih ada pada `live-recovery.json`.

## Akar masalah dan batas bukti

Pesan lama menyatakan koneksi server ke YouTube gagal. Exception jaringan asli tidak lagi tersedia: logger yt-dlp membuang warning/error, exception diganti pesan umum, lalu workspace dibersihkan. Karena itu, kegagalan DNS, CDN, timeout, atau socket tertentu pada percobaan lama tidak dapat dipastikan. Sumber identik berhasil diunduh pada percobaan selanjutnya; bukti tidak mendukung kesimpulan bahwa server kehilangan internet secara permanen.

Selain itu, campaign `1e2cff8aa33e45939620c410f8a580bf` sudah failed, sementara item anak masih berstatus running/queued. Checkpoint ini perlu diselaraskan agar tidak menggambarkan pekerjaan terminal sebagai aktif.

## Perbaikan source

- Retry transport memakai jeda 2 dan 5 detik pada strategi dan file parsial yang sama. Anggaran dua retry tambahan dibagi oleh seluruh jalur kompatibilitas dalam satu fase; lima strategi video tetap tersedia. Kegagalan terus-menerus dibatasi tujuh percobaan video, bukan pengulangan tak terbatas per strategi.
- Error format, autentikasi, hak/sumber ditolak, dan rate limit dibedakan dari gangguan transport. Perbaikan tidak menambah retry transport untuk penolakan tersebut. Cookie dalam memori dibuat ulang untuk setiap percobaan agar tidak memakai stream tertutup.
- Logger menyimpan pesan asli dan rantai penyebab secara terbatas setelah kredensial, header, serta query URL bertanda tangan dibersihkan. Bukti kecil dipertahankan ketika media sementara dihapus dan diarsipkan sebelum workspace gagal dibersihkan. Kegagalan menulis diagnostik tidak mengganti exception transport asli.
- UI menghubungkan kartu gagal dengan percobaan berikutnya hanya bila identitas sumber, format, platform, urutan waktu, hasil, dan pengaman review cocok. Detail kegagalan sebelumnya tetap dapat dibaca; kartu membuka proses pemulihan yang benar.
- Checkpoint campaign failed/cancelled diselaraskan dengan kegagalan anak yang terbukti. Status keseluruhan, waktu cooldown, bidang lain, dan identitas upload dipertahankan. Hook akhir campaign, startup, serta maintenance menjalankan rekonsiliasi.
- Pembersihan otomatis hanya mengarsipkan kegagalan download kosong setelah sumber pengganti yang cocok selesai. Pekerjaan aktif, review/hold, workspace, relasi recovery aktif, catatan upload, dan consumer checkpoint dilindungi. Kegagalan menyimpan checkpoint atau daftar job mempertahankan kartu dan state sebelumnya.
- Receipt pemulihan yang tervalidasi juga dapat menyelaraskan checkpoint terminal setelah kartu lama sudah dibersihkan. Receipt kasus ini sudah disiapkan; penyelarasan checkpoint di runtime menunggu deployment normal.
- Tidak ada dependency runtime baru. Readiness normal memeriksa capability `/api/runtime/source-download`; Docker tetap menyalin dan memverifikasi seluruh source Python melalui manifest yang sudah ada.

## Verifikasi

- Backend: 185 pengujian lulus pada source download, cleanup, rejected source cleanup, automatic output cleanup, cron autonomous recovery, Compose deployment, dan upload attention.
- Formatter pesan error: 10 pengujian lulus pada subset `test_api_budget.py`.
- Frontend: TypeScript/lint dan 10 berkas pengujian Node lulus.
- Production build preview: `xIui4FowlokeasxXOXGLq`; pemeriksaan build, persiapan, dan HTTP health lulus.
- Browser preview: lebar 1440, 1280, 390, dan 320, tema terang/gelap; tidak ada overflow horizontal atau error JavaScript. Kartu pemulihan, detail percobaan lama, dan navigasi diperiksa. Preview menggunakan snapshot job awal dengan API GET yang dicerminkan; bukan bukti deployment production. Screenshot dan `browser-review.json` disimpan di folder ini. Server preview dihentikan setelah pemeriksaan.
- Python compilation dan `git diff --check` lulus.

## Status aktivasi

API health production OK. Pemeriksaan terakhir menemukan worker upload attention versi 1 sudah aktif dan scheduler berjalan. Perbaikan unduhan dalam laporan ini belum aktif: `/api/runtime/source-download` masih 404 dan release runtime berbeda dari fingerprint source akhir. Rincian ada di `runtime-verification.json`.

Produksi berikutnya dibiarkan berjalan sampai selesai. Setelah itu, deployment standar dicoba:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

Perintah berhenti sebelum Docker dijalankan karena sudo memerlukan terminal/kata sandi (`sudo: a password is required`). Tidak ada hot patch atau perintah aktivasi pengganti. Perbaikan source, backend checkpoint reconciliation, dan UI pemulihan belum boleh dinyatakan aktif sampai perintah standar berhasil dan readiness runtime diverifikasi.
