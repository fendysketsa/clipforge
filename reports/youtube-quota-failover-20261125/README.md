# Diagnosis upload mandek 6 Short (25 Nov 2026)

## Gejala

`daily_plan`: target 30, `total_uploaded` 6, `total_used` 11. Run aktif
`23aa08ae…` baru sampai sumber 2/17 setelah ±30 menit. Antrean upload kosong,
scheduler sehat, tidak ada `last_error`.

## Akar masalah terukur

Dari 241 error pada 40 run hari ini:

- ~80 kegagalan discovery terkait YouTube Data API, mayoritas **HTTP 429 /
  quotaExceeded** pada satu-satunya key aktif (fingerprint `f29bf59a`).
- 33 video hasil pencarian sudah **tidak tersedia**.
- 18 run berakhir tanpa kandidat aman karena stok sumber terpakai dan filter
  umur adaptif 90 hari.
- Sumber yang dipilih mayoritas **>20 menit** (`over_20`), sehingga tiap sumber
  butuh ±23 menit untuk unduh + transkrip + penilaian kandidat.
- Batas struktural: maksimal **7 Short/WIB hari** (hard cap di kode) dan
  backlog scheduled **56/57**.

Ketiga key yang terdaftar di `.env` diuji dengan satu `videos.list` dan
semuanya valid; dua key cadangan tidak sedang kena kuota.

## Perbaikan yang diterapkan

- `youtube_data_api_keys()` mengurai `YOUTUBE_DATA_API_KEYS` (utama + cadangan,
  dedup, urutan dijaga).
- `youtube_data_api_get()` melakukan **failover otomatis** saat HTTP 429 atau
  `quotaExceeded`/`rateLimitExceeded`/`dailyLimitExceeded`/
  `userRateLimitExceeded`, dan hanya melempar error setelah semua key habis.
- Cache discovery tidak lagi di-key oleh fingerprint, jadi hasil dari key
  pertama bisa dipakai key cadangan tanpa mengulang request.
- Error non-kuota tetap gagal segera (tidak disembunyikan dengan retry).
- `VIRAL_CC_QUOTA_FALLBACK_METADATA_CHECKS` 8 → 40 agar fallback yt-dlp
  mendapat kandidat lebih banyak.
- `.env`, `.env.example`, dan Compose meneruskan variabel baru.

Tidak ada gate hak, QC, kurasi, atau publication hold yang dilonggarkan.

## Validasi

5 tes failover (urutan key, 429→backup, cache lintas key, non-429 tidak retry,
error habis tanpa membocorkan key) lolos. 377 tes terarah lolos termasuk
deployment guard dan API budget. `py_compile`, `git diff --check`, dan
`docker-compose config` lolos.

Hash source baru yang diharapkan:
`337f223becd85574f83de31f3696d12ac32730b3e8718ac4539f9bb7ceea9194`.

## Aktivasi

Belum aktif. Sesi ini tidak memiliki sudo interaktif. Jalankan perintah standar:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

Sebaiknya tunggu run aktif selesai lebih dulu: restart di tengah run pernah
menyebabkan `Automation terhenti karena backend restart`.

Verifikasi: release id = hash di atas, health ok, lalu error `HTTP 429`
tidak lagi muncul di `errors` run baru dan `total_uploaded` naik.

## Yang tidak diubah

Batas 7 Short/WIB hari dan backlog 57 sengaja dipertahankan. Keduanya adalah
guard agar tidak membanjiri kanal. Jika target upload harian memang harus naik,
itu keputusan editorial terpisah dan harus disetujui operator.
