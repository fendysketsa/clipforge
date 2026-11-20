# Perbaikan fallback kompilasi Long — 15 November 2026

Tiga percobaan cron Long hari ini gagal sebelum render karena audit alur cerita
tidak menemukan bukti ending/alur yang cukup. Workspace percobaan tersebut sudah
dibersihkan oleh mekanisme lama; tidak ada hasil Roblox baru yang diklaim selesai.
Snapshot pemeriksaan awal tersimpan di `live-long-production.json`.

## Perilaku baru

- Audit cerita tetap berjalan. Jika bukti cerita gagal, job yang sama mencoba
  kompilasi dari kandidat sumber asli, berurutan, tanpa teaser duplikat.
- Kompilasi minimal tiga momen dan 180 detik, maksimal 600 detik. Potongan harus
  berbasis transkrip, tidak tumpang tindih, tidak identik, mempertahankan anchor
  Short dan sedikitnya 60% bahan di luar anchor tersebut.
- Judul, label riwayat dan progres menyebut kompilasi. Audit cerita yang gagal
  tetap tersimpan sebagai gagal; audit kompilasi memiliki bukti terpisah yang
  terikat pada timestamp dan teks potongan sebenarnya.
- QC Long independen memeriksa format kompilasi, audio, subtitle, bingkai,
  integritas media, konteks dan hak sumber sebelum mengizinkan upload. Klaim
  cerita utuh tidak dipaksakan. Penolakan konten oleh provider tetap ditahan.
- Tidak mengubah target cron, pengaturan operator, hold politik, atau identitas
  upload. Readiness normal Docker mensyaratkan capability fallback versi 1.

## Bukti verifikasi

- `tests.xml`: **379 lulus** untuk fallback, cron Long, QC, produksi Long,
  deployment, operator QC dan caption.
- Typecheck dan production build frontend berhasil pada sesi pengerjaan ini.
- `render-verification.json`: pipeline export sebenarnya menghasilkan video
  fixture **240.021333 detik, 1920×1080**, empat momen kronologis. Hash sumber
  tetap sama dan decode seluruh audio/video lulus. Frame diperiksa pada
  `compiled-frame.png`; video ada di `rendered/`.
- Fixture memakai gambar dan nada sintetis. Bukti ini membuktikan jalur render,
  bukan mutu cerita Roblox, sinkronisasi dialog manusia atau kelayakan publikasi.
  QC publikasi independen tidak diberikan kepada fixture.
- `verify_render.py` menyimpan reproduksi fixture; tidak mendaftarkan job atau
  mengunggah video ke platform mana pun.

## Aktivasi belum berhasil

Perintah standar sudah dicoba:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

Sudo menolak karena membutuhkan password dan terminal interaktif. Runtime masih
belum mengiklankan capability kompilasi. `deployment-verification.json` mencatat
hasilnya. Ada satu job aktif saat pemeriksaan terakhir; percobaan sudo gagal
sebelum mengubah layanan. Belum ada rerender sumber Long gagal dengan worker baru.
