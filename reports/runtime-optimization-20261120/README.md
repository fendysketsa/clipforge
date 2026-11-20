# Optimasi ClipForge — 20 November 2026

Optimasi sumber selesai dan diuji. Runtime aktif belum memakai perubahan ini:
`/api/runtime/optimization` masih HTTP 404, sementara backend dan frontend HTTP
200. Pemeriksaan sudo terakhir gagal dengan `sudo: a password is required`.
Cron masih ON dan Long aktif sedang mengerjakan momen kompilasi 8 dari 8.

## Temuan dan perubahan

1. Dashboard sebelumnya mengambil seluruh riwayat upload YouTube sekitar
   10,49 MB per GET. Timer cleanup 250 ms berjalan bersamaan dengan polling
   upload reguler. Timer duplikat dihapus; polling upload 1.500 ms tetap ada.
   Siklus polling yang lambat tidak boleh menumpuk, dan tab tersembunyi
   melewati polling aktif yang sering. Saat tab kembali aktif, refresh global
   yang sudah ada tetap mengambil keadaan terbaru.
2. View `?dashboard=true` menyediakan record dengan ID/urutan/metadata remote
   yang sama, tanpa array histori performa yang tidak digunakan UI. Log upload
   aktif tetap lengkap. Log terminal menyertakan delapan baris terakhir dan
   seluruh penanda lama yang dipakai UI untuk klaim, thumbnail, transfer dan
   submission TikTok. Riwayat lengkap tetap tersimpan; list default dan detail
   YouTube tetap menyediakan bukti lengkap. Data bukan dihapus dari storage.
3. Permintaan GET frontend yang benar-benar bersamaan ke URL sama menggunakan
   satu fetch. Respons selesai/gagal tidak dicache, sehingga polling berikutnya
   membaca keadaan baru. Timeout membatasi permintaan status yang tersangkut.
   POST admission/reconcile dan reservasi pencegah upload ganda tidak diubah.
4. Empat checkpoint store menggunakan serializer JSON native Pydantic untuk
   menghindari membangun seluruh struktur dict Python lalu meng-encode ulang.
   Penulisan tetap langsung, memakai lock dan strategi atomic-replace/fallback
   bind-mount yang sudah ada. Tidak ada debounce yang menunda checkpoint.
5. Snapshot perhitungan kuota hanya menyalin ID, ownership, tanggal, status,
   dan field clip yang digunakan perhitungan; request lengkap, sumber panjang,
   dan snapshot Short penuh tidak diserialisasi pada setiap pemeriksaan kuota.
6. Render worker baru memakai session proses sendiri. Saat dibatalkan, gagal,
   atau selesai, proses encoder/renderer turunannya dilepas, termasuk anak yang
   mengabaikan SIGTERM. Worker lama tanpa session milik sendiri tetap memakai
   terminasi parent; process group bersama tidak disinyal. Shared Chrome yang
   dipakai login/upload berada di luar session renderer tersebut.
7. Callback/props/import/state frontend yang tidak terhubung ke UI dihapus.
   Pemeriksaan TypeScript dengan `noUnusedLocals` dan `noUnusedParameters`
   sekarang lulus. Endpoint upload dan generasi manual yang tersedia tetap ada.

## Pengukuran

[benchmark.json](benchmark.json) menggunakan satu snapshot data nyata dalam
proses terisolasi, tujuh pengulangan per pengukuran, tanpa menulis checkpoint
produksi. Angka ini bukan bukti peningkatan kecepatan render MP4 atau aktivasi
container.

| Jalur | Sebelum | Sesudah | Hasil |
| --- | ---: | ---: | --- |
| Respons dashboard YouTube, 740 record | 10.485.909 byte | 3.493.312 byte | 66,69% lebih kecil |
| Respons dashboard TikTok, 132 record | 514.374 byte | 374.028 byte | 27,28% lebih kecil |
| Serialisasi checkpoint YouTube, median | 290,166 ms | 83,268 ms | 3,48× lebih cepat |
| Serialisasi checkpoint TikTok, median | 7,976 ms | 1,514 ms | 5,27× lebih cepat |
| Snapshot/perhitungan kuota harian, median | 36,271 ms | 26,825 ms | 1,35× lebih cepat |

JSON checkpoint sebelum/sesudah dibandingkan secara semantik dan setara.
Rencana kuota dihitung menggunakan fungsi lama dari Git dan fungsi baru pada
snapshot/waktu yang sama: hasilnya identik. Seluruh ID record dan urutannya
tetap tersedia pada view dashboard.

Profil lokal daftar job menunjukkan banyak pembacaan metadata, tetapi totalnya
sekitar 88 ms pada proses terisolasi; latensi API produksi sempat 3,659 detik
ketika render/discovery aktif. Perbedaan itu tidak diperlakukan sebagai bukti
bahwa semua keterlambatan berasal dari fungsi daftar job. Cache keputusan QC
tidak ditambahkan, agar perubahan bukti/hold tetap langsung terbaca.

## Pembersihan proses dan data

Proses Clipper yang terlihat pada pemeriksaan runtime merupakan anak backend
dan sedang merender Long aktif. Keempat folder output dengan ID job masih
direferensikan oleh state persisten. Tidak ada penghentian render produksi atau
penghapusan folder tersebut. Bagian yang benar-benar dibuang adalah timer
duplikat dan kode frontend yang tak terhubung; penanganan proses turunan kini
mencegah render baru meninggalkan encoder setelah selesai/dibatalkan.

Kualitas render, resolusi, FPS, alur kompleks generate, pemilihan sumber, QC,
jumlah target harian, review politik/agama, pengaturan operator, serta identitas
upload remote tidak dikurangi untuk mendapatkan angka benchmark.

## Validasi dan aktivasi

- 716 tes backend lulus; enam tes storyboard/stream di luar cakupan dikecualikan.
- Tujuh tes coalescing/polling, 21 tes admission/recovery upload, dan enam tes
  queue frontend dijalankan langsung dan lulus: total 34 tes frontend.
- Pengujian session proses nyata membuktikan worker dan anak yang mengabaikan
  SIGTERM berhenti, sementara proses lain tetap hidup.
- Build produksi Next.js dan TypeScript ketat untuk variabel/parameter tidak
  terpakai lulus. Seluruh 63 modul backend lolos kompilasi.
- `git diff --check` lulus. [verification.json](verification.json) berisi
  ringkasan tes dan hash sumber; [runtime-status.json](runtime-status.json)
  mencatat layanan/proses yang sedang berjalan.

Modul baru masuk manifest image normal, dan startup memeriksa kapabilitas
optimasi melalui kontrak runtime. Tidak ada skrip aktivasi tambahan. Setelah
pekerjaan aktif selesai dan akses sudo tersedia, gunakan perintah standar:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

Build frontend lokal dan pengujian sumber bukan deployment. Ketiga layanan,
release/hash runtime, endpoint optimasi, dan status scheduler masih perlu
diverifikasi setelah deployment standar tersebut.
