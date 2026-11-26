# Hapus file lokal setelah upload terverifikasi (26 Nov 2026)

## Keputusan operator

Setelah video ada di platform — termasuk yang dijadwalkan — file lokal tidak
pernah disimpan. Berlaku untuk job manual maupun cron. Tidak ada pengecualian
berdasarkan lane atau tanggal tayang.

## Temuan

Mekanisme `schedule_completed_upload_cleanup` memang sudah berjalan untuk upload
baru: 7 upload terakhir (25–26 Nov) semuanya memiliki `clip_deleted_at`, termasuk
yang `publish_at`-nya 27 Nov, 29 Nov, dan 6 Des.

Namun ada **42 upload lama** yang sudah `completed` + `upload_confirmed` +
punya `video_url`, tetapi tidak memiliki `clip_delete_after` maupun
`clip_deleted_at`. Worker cleanup lama langsung berhenti karena penanda itu
tidak ada, sehingga file lokal mereka tidak pernah dibersihkan. Worker lama
hanya memproses upload yang memiliki penanda tersebut.

## Perubahan

- `api.py`: `schedule_confirmed_upload_cleanup_backfill()` mencari upload
  terverifikasi tanpa penanda cleanup, memasang `clip_delete_after`, lalu
  menjalankan worker cleanup yang sama seperti upload baru.
- Dipanggil dari startup event backend, jadi berjalan sebagai bagian dari
  deployment normal — bukan script aktivasi terpisah.
- Tidak menyentuh status upload, video remote, jadwal tayang, kwitansi, atau
  publication hold. Upload gagal/queued/dry-run tidak disentuh.

## Validasi

Tes baru memastikan backfill hanya memilih upload terverifikasi tanpa penanda,
termasuk yang dijadwalkan, dan idempoten. 115 tes terarah lolos; `py_compile`
dan `git diff --check` lolos.

Hash source baru yang diharapkan:
`c47d9d1a2bcee16f92434337598844d35959cf986ea9fb4b44fb6c34ecc06b19`.

## Aktivasi

Perlu perintah standar:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

Verifikasi: release id sesuai hash di atas, health ok, lalu hitung ulang
upload terverifikasi tanpa `clip_deleted_at` — harus turun dari 42 menuju 0
dalam beberapa menit setelah worker selesai.
