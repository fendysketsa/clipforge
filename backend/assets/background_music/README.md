# Pustaka backsound lokal

Folder ini berisi musik instrumental terkurasi yang dipakai langsung dari disk.
Proses render klip **tidak pernah mengunduh musik**. `catalog.json` menjadi
allowlist: loader hanya menerima file lokal dengan lisensi, URL sumber, dan
SHA-256 yang cocok.

Koleksi awal memakai CC0 1.0 karena atribusi tidak diwajibkan dan karyanya boleh
disalin, dimodifikasi, didistribusikan, serta digunakan secara komersial. Meski
demikian, klaim Content ID yang keliru masih mungkin terjadi pada platform apa
pun; pemeriksaan copyright platform tetap harus dijalankan sebelum publikasi.

| File | Judul — pembuat | Tema | Bukti lisensi |
| --- | --- | --- | --- |
| `calm-theme.ogg` | Calm Theme — pebonius | knowledge, islamic | <https://opengameart.org/content/calm-music-0> |
| `happy-moments.ogg` | Happy Moments — Centurion_of_war | inspiring | <https://opengameart.org/content/happy-moments> |
| `suspense.ogg` | Suspense — wipics | mystery, warning | <https://opengameart.org/content/suspense-0> |

Teks resmi CC0 1.0: <https://creativecommons.org/publicdomain/zero/1.0/>.

Untuk menambah lagu, audit halaman sumber dan rekam metadata lengkap di
`catalog.json`, termasuk URL unduhan HTTPS dan SHA-256. Kemudian jalankan:

```bash
python scripts/sync-background-music-library.py
```

Sinkronisasi hanya mengunduh entri yang hilang/rusak dan menolak lisensi selain
CC0, domain yang tidak diizinkan, ekstensi asing, redirect lintas domain, atau
hash yang berbeda. `scripts/recreate-compose-up.sh` menjalankan sinkronisasi ini
sebelum rebuild; kegagalan jaringan tidak menghapus cache yang sudah valid dan
tidak memindahkan unduhan ke waktu render.
