# Audit menyeluruh setelah rebuild (26 Nov 2026)

## Status runtime

Deploy terverifikasi: release id cocok dengan source, `source_verified: true`,
health `ok`, scheduler `enabled`/`scheduler_running`. Aturan hapus lokal setelah
upload terverifikasi sudah aktif: 744 upload confirmed semuanya punya
`clip_deleted_at`, tidak ada yang tertinggal.

## Temuan kritis dan perbaikan

Render Long `2e9bc535…` gagal dengan `NameError: name 'segments' is not defined`.
Itu berasal dari pemasangan aksen hidup yang saya tambahkan sebelumnya: di scope
`export_clip` variabel yang benar adalah `clip_segments`, bukan `segments`.
Sudah diperbaiki dan ditambah tes regresi yang memeriksa teks pemanggilan di
`clipper.py`. 13 tes liveliness lolos.

Hash sementara `671073888ec37510bd8d4c3f14ba6a01b955f745fcd8b8a5f0bf5fb0b34701c8`
sudah digantikan oleh perbaikan berikut.

## Perbaikan lanjutan

1. **Stok sumber cron habis** — ditambah pencarian terakhir yang hanya melebarkan
   kueri editorial dan duration filter, tanpa mengubah gate hak/QC dan tanpa
   memasukkan lagi URL yang sudah diproses. Tes regresi ditambahkan; tes lama
   yang mengcapture fallback disesuaikan agar tetap memeriksa request fallback
   yang benar.
2. **Upload diblokir "Sudut Editorial dan Makna Utama pada dua waktu berbeda"** —
   ditemukan kontradiksi: `source_caption_clearance` mematikan
   `visible_editorial_framing` padahal `transformation_contract.passed=true`,
   sehingga kartu tidak dirender dan gate menolak. Renderer sebenarnya sudah
   punya jalur aman (`hook_y=320` + backdrop) untuk source dengan subtitle
   bawaan. Kini framing tetap aktif dan overlay diizinkan pada jalur tersebut.
   Tes: `test_source_caption_clearance_keeps_two_editorial_windows_visible`.

Hash source final:
`c3173433aee24bdb9246afea52996e6ca16c97756c89c24c8141e084f279282f`.

Validasi: 874 tes terarah lolos; `py_compile` dan `git diff --check` lolos.

## Masih memerlukan keputusan manusia

Tiga clip `needs_remote_verification` memiliki `video_url` tetapi
`upload_confirmed=false` dan verifikasi pasca-restart sempat stall. Saya tidak
memaksa `upload_confirmed`; itu harus diverifikasi lewat jalur verifikasi resmi
/ UI. File lokal sengaja dipertahankan sampai verifikasi selesai.

## Sisa kendala yang masih teramati

1. Antrean upload YouTube/TikTok: 0 queued, 0 running — tidak ada yang macet di antrean.
2. Job: 11 completed, 1 running (Long baru `267c37e3…`, tahap transkrip), 1 failed
   (job Long yang kena NameError; workspace sudah dibersihkan otomatis).
3. Run terakhir gagal karena backend restart, retry dijadwalkan 5 menit kemudian.
4. Run-run lain gagal karena "semua sumber yang pernah diproses tetap dilewati"
   dan video hasil search sudah tidak tersedia / age-gated.
5. `manual_review_holds`: 0. `upload_attention.items`: 0. Tidak ada hold baru.
6. Operator upload: 3 clip `needs_remote_verification` — menunggu verifikasi
   manusia karena upload sebelumnya terputus restart; file lokal sengaja aman.
7. Kapasitas: backlog scheduled 52/57, batas 7 Short per hari WIB.
8. Antrean publikasi memang panjang: 51 upload dijadwalkan sampai 6 Desember.

Perlu deploy ulang dengan perintah standar agar seluruh perbaikan aktif:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

Verifikasi: release id `c3173433aee24bdb9246afea52996e6ca16c97756c89c24c8141e084f279282f`,
health ok, render Long baru tidak menghasilkan `NameError`, run cron berikutnya
tidak lagi berhenti karena "tidak ada kandidat aman", dan Short dengan subtitle
bawaan tetap memiliki dua kartu editorial yang terekam di sidecar.
