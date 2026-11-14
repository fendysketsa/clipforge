# Analisis dan perubahan cron Long — 14 November 2026

## Kesimpulan

Long perlu dipilih sebagai cerita/penjelasan utuh: pertanyaan atau tujuan yang jelas, konteks, perkembangan, bukti/konsekuensi, lalu jawaban. Sumber Short yang berhasil belum membuktikan bahwa versi panjangnya layak. Target 1.000+ views adalah sasaran eksperimen; hasil dan retensi tidak dapat dijamin dari metadata atau penilaian AI.

## Pembanding publik yang diverifikasi

Angka dibaca langsung melalui metadata publik YouTube pada 14 November 2026; dapat berubah. Detail tersedia di `public-metadata.json`.

| Video | Durasi | Views saat diperiksa | Hipotesis editorial dari kemasan |
|---|---:|---:|---|
| [Yuta Mio Bekerja 7 Hari Merawat Kucing…](https://www.youtube.com/watch?v=KSoxmvwkcuY) | 23:04 | 1.474.029 | Tujuan konkret, perjalanan tujuh hari, tokoh seri yang dikenal; perkembangan bisa menjadi alasan mengikuti sampai akhir. |
| [Yuta Sakit Tapi Mio & Baby Celine Tidak Peduli…](https://www.youtube.com/watch?v=LxW9LbzkvCE) | 28:23 | 2.322.594 | Konflik hubungan yang spesifik dan pertanyaan bagaimana tokoh merespons. |
| [LANTAI DUA — KHW PART 403](https://www.youtube.com/watch?v=Jr2AVxsP3Vk) | 33:23 | 14.276.607 | Identitas seri berulang dan satu misteri; pengenalan cerita serta pengungkapan perlu dinilai dari isi, bukan judul saja. |

Ini analisis permintaan publik dan kemasan, bukan audit isi video penuh. Pengambilan subtitle ketiganya gagal karena respons kosong/HTTP 429. Kurva retensi, CTR, demografi dan sumber trafik kreator tersebut tidak tersedia. Dua sampel berasal dari kreator yang sama, sampel dipilih dari video populer, dan tidak ada kelompok kontrol; tidak dapat menyimpulkan sebab keberhasilan atau memindahkan hasilnya ke kanal ini. Materi kreator pembanding tidak otomatis boleh dipakai ulang.

YouTube menjelaskan bahwa retensi awal menunjukkan berapa banyak penonton masih menonton pada detik 30, termasuk kecocokan isi dengan janji judul/thumbnail. Dips dan spikes membantu menentukan bagian yang perlu diperbaiki; views saja tidak menjelaskan alasannya. [Panduan retensi resmi](https://support.google.com/youtube/answer/9314415?hl=en).

## Bukti dari kanal sendiri

Snapshot lokal `youtube_uploads.json` memiliki 54 catatan Long, 29 dengan pengukuran. Sebanyak 17 catatan berstatus publik, upload terkonfirmasi dan memiliki snapshot; tidak ada yang mencapai 1.000 views pada snapshot terakhir. Tidak ada snapshot Long yang berisi `average_view_percentage`. Ini kondisi catatan historis lokal, bukan pengukuran ulang seluruh video di YouTube hari ini. Data belum cukup untuk menyatakan pola Long kanal sendiri sudah terbukti.

API lokal saat diperiksa sehat, cron aktif, jalur Long aktif dengan target satu per hari dan QC aktif. Dua percobaan Long terbaru ditolak QC: satu penolakan konten provider, satu ketidakcocokan audio-caption. Penolakan tersebut tidak dilepas oleh perubahan strategi ini.

## Perubahan yang disiapkan

1. Khusus pekerjaan Long cron baru: wajib sumber berdurasi minimal 300 detik dan mempunyai bukti minimal 1.000 views publik. Metadata terbaru diperiksa lagi sebelum download; sumber live/belum selesai ditahan. Angka minimum ini kebijakan editorial internal, bukan ketentuan atau prediktor algoritma YouTube.
2. Pemilihan di jalur Long mempertimbangkan permintaan publik Long antarsumber, bukan sekadar Short terbaru. Ini masih menggunakan kumpulan sumber yang ditemukan cron; belum menjadi pencarian Long yang sepenuhnya terpisah.
3. Brief dan penilaian bagian Long dipisahkan dari brief FYP/loop/pembuka dua detik Shorts. Konsepnya perjalanan atau penjelasan utuh dengan informasi baru, bukan memperpanjang satu momen.
4. Sebelum render bagian video, AI harus menilai koherensi, perkembangan, penyelesaian, nilai tambahan, ketiadaan filler dan kesesuaian janji. Empat tahap alur wajib memiliki kutipan persis dari bagian output terkait. Kutipan atau nomor bagian rekaan tidak lolos.
5. Minimal 180 detik bahan output dan 60% durasi di luar rentang Short. Pemeriksaan ini memastikan tambahan bahan secara durasi; nilai tambah semantiknya tetap diperiksa terpisah. Teaser dan caption mengikuti sistem Long yang sudah ada.
6. Bukti tidak lengkap, JSON rusak, provider gagal atau AI dimatikan menahan render. QC dan gerbang upload juga mewajibkan bukti audit Long untuk pekerjaan baru tersebut. Izin sumber, pemeriksaan makna, audio, caption dan aturan publikasi yang ada tetap berlaku.

Setelah video dipublikasikan, evaluasi Long terhadap Long dengan topik, durasi, usia publikasi dan trafik sebanding: impresi/CTR, retensi detik 30, durasi tonton rata-rata, persentase ditonton, dips/spikes, penonton kembali dan views. Jangan memindahkan kesimpulan performa Shorts ke Long. Data tersebut belum tersedia cukup untuk menjanjikan hasil.

## Validasi dan aktivasi

Validasi akhir: 228 tes strategi/produksi/QC/seleksi/pemisahan format lulus (`tests.xml`), ditambah 32 tes API terkait pasangan Long, mode compilation dan perintah worker (`api-regression-tests.xml`). Total 260 tes terpilih lulus; ini bukan klaim seluruh suite proyek lulus. Pemeriksaan sintaks Python, sintaks Bash dan `git diff --check` juga lulus. Dependensi tes yang belum tersedia disiapkan dalam venv sementara di `/tmp`, tanpa mengubah lingkungan produksi. Belum ada render percobaan dengan strategi baru, sehingga belum ada bukti kualitas audiovisual hasil baru.

Aktivasi belum dilakukan: akses socket Docker ditolak dan `sudo -n` memerlukan kata sandi. Pemeriksaan ulang API lokal (`runtime-status.json`) mengonfirmasi backend sehat, cron/Long aktif, belum ada `long_strategy` pada runtime dan tidak ada pekerjaan Long aktif saat diperiksa. Cron runtime yang berjalan masih memakai implementasi sebelumnya. Skrip aktivasi telah ditambah pemeriksaan hash modul strategi baru.

Perintah baku deployment dengan akses administrator (sesuai instruksi pengguna):

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

Dockerfile menyertakan modul strategi dan profil tema; entrypoint memverifikasi source image; healthcheck memeriksa kontrak strategi Long versi 2. Tidak diperlukan skrip aktivasi terpisah. Perintah `--force-recreate` dapat menghentikan pekerjaan aktif; pengecekan startup tidak menjamin proses render/upload sedang kosong. Pilihan operator dan checkpoint yang tersimpan tetap dipertahankan. Sesudah deployment periksa `/api/automation/viral-cc/long-strategy`: `version=2`, pekerjaan Long baru memiliki `request.cron_long_strategy=true`, dan hasil audit tersimpan sebelum menyatakan strategi sudah digunakan produksi.
