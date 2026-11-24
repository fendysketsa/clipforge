# Long video: janji pembuka yang lebih ketat + retensi terukur — 24 November 2026

## Masalah yang ditemukan

Pipeline Long sudah lengkap (source demand → teaser 10–22 dtk → kronologi sumber → QC → Private upload),
tetapi dua hal masih lemah:

1. Aturan "janji di 30 detik pertama" dan "tiap tahap memberi informasi baru" hanya ada di prompt/
   dokumentasi. `validate_review()` memeriksa urutan peran dan kutipan, tetapi tidak memeriksa
   **kapan** janji itu muncul atau apakah alasan lanjut (`why_continue`) hanya mengulang ringkasan.
2. Sistem membaca aggregate `averageViewDuration` / `averageViewPercentage` dari YouTube Analytics,
   tetapi **tidak pernah** mengambil laporan `audienceRetention`. Jadi "retensi 30 detik" selama ini
   adalah heuristik editor, bukan data penonton yang sebenarnya.

Kondisi produksi saat audit: lane Long aktif 1 job, target 2/hari, 1 ditolak, 0 ter-upload hari ini.

## Yang diubah

### 1. Bukti hook Long yang dapat diverifikasi (`backend/cron_long_strategy.py`)

- `STORY_REVIEW_VERSION = 2`, `PROMISE_OPENING_SECONDS = 30.0`.
- `LONG_EDITOR_BRIEF` dan `review_prompt()` sekarang secara eksplisit meminta janji muncul di
  30 detik pertama, belum menjawab seluruh cerita, dan setiap `why_continue` menyebut nilai baru
  yang berbeda dari tahap sebelumnya.
- `validate_review()` menolak:
  - `repeated_why_continue` — dua tahap memakai alasan lanjut yang identik;
  - `promise_not_in_opening` — kutipan janji diperkirakan muncul setelah 30 detik pertama
    (estimasi posisi relatif kutipan dalam teks part pertama, bukan angka retensi palsu).
- Kutipan tetap harus persis berasal dari transkrip; urutan `promise < context < development < payoff`
  dan batas durasi/bahan baru tidak dilonggarkan.

### 2. Retensi 30 detik benar-benar diukur (`backend/api.py`)

- Fungsi baru `youtube_audience_retention_snapshot()` memanggil laporan terpisah
  `youtubeanalytics/v2/reports` dengan `metrics=audienceRetention`,
  `dimensions=elapsedVideoTimeRatio`, difilter per video, maksimal 100 titik.
- `YouTubePerformanceSnapshot` dan `YouTubePerformanceUpdateRequest` menyimpan
  `retention_first_30_seconds` dan `retention_curve` (opsional, default `None`).
- Jika OAuth tidak ada, laporan ditolak, atau baris rusak → field dibiarkan kosong.
  Tidak ada estimasi, tidak ada angka yang dibuat-buat, dan snapshot utama tetap berhasil.
- `youtube_performance_diagnosis()` kini menyebut nilai terukur secara eksplisit
  ("bukan perkiraan") dan memberi saran konkret bila kurva turun >15 poin sebelum 35% durasi.
- Field baru ikut di-*carry forward* saat refresh data publik, sama seperti metrik lain.

### 3. Subscriber conversion

Tidak diubah: Long sudah memakai satu undangan subscribe bernilai setelah payoff terakhir
(`subscriber_conversion` di sidecar, diverifikasi oleh gate di `clipper.py:6151`).

## Yang tidak diubah

Semua gate lama tetap utuh: `source_profile`, `validate_compilation`, QC confidence 0.8,
hak sumber, satu QC aktif, batas dua proses per sumber, serta jaminan tidak ada owner produksi paralel.
Tidak ada angka penonton/subscriber yang direkayasa.

## Verifikasi

- `backend/tests/test_cron_long_strategy.py` — 28 pengujian, termasuk aturan janji terlambat dan
  `why_continue` berulang.
- `backend/tests/test_youtube_retention_measurement.py` — pengujian parsing kurva asli,
  kegagalan/403 tidak mengarang data, baris rusak dibuang, dan diagnosis memakai nilai terukur.
- `backend/tests/test_youtube_uploads.py`, `test_long_video_qc.py`, `test_long_compilation_fallback.py`
  tetap lolos.
- Hasil suite backend penuh dicatat pada sesi deployment berikutnya.
