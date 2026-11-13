# Analisis pertumbuhan RYUUNDY

Kesimpulan: bukti terkuat mengarah ke **Short cerita karakter yang berulang**, khususnya Yuta/Mio/Baby Selin, dengan distribusi besar melalui Feed Shorts. Ini pola yang layak diuji ulang; data observasional tidak membuktikan satu penyebab tunggal atau menjamin viral.

## Bukti Studio yang dibaca langsung

Periode channel: **15 Oktober–11 November 2026**. Pembacaan dilakukan pada 13 November melalui tab terpisah di sesi channel `UCAOZF9Qzj6DYoXKtLnP4UUQ`; tab dan posting pengguna tidak diubah.

| Metrik | Angka Studio |
|---|---:|
| Penayangan channel | 288,1 ribu, naik 135,1 ribu |
| Subscriber bersih channel | +253 |
| Penayangan Shorts | 286,4 ribu |
| Penayangan Shorts tak dilewati | 136,9 ribu |
| Feed Shorts sebagai sumber penayangan Shorts | 95,1% |
| Penelusuran YouTube sebagai sumber Shorts | 3,6% |
| Tetap menonton pada laporan Shorts | 52,1% |
| Melewati pada laporan Shorts | 47,9% |
| Penonton baru pada ringkasan audiens | 98% |
| Penonton rutin pada ringkasan | 0% sebagaimana dibulatkan Studio |

Tiga Short teratas: **Macet Karena Kamperfan…Kak Yuta…** (28,6 ribu), **Yuta larang beri es krim…Mio…** (17,3 ribu), dan **Mio dan Baby Selin Terjebak…** (10,5 ribu).

Video teratas `9kxgP070cBQ` berdurasi sekitar 39 detik. Laporan **sejak dipublikasikan** menunjukkan 72,1% tetap menonton, 215 suka, dan +30 subscriber. Angka 72,1% ini berjarak 20 poin persentase dari angka channel 52,1%, tetapi periode dan kelompok penontonnya berbeda, sehingga perbandingan ini merupakan petunjuk eksperimen, bukan estimasi sebab-akibat. Grafik retensi terlihat, tetapi nilai persentase tonton rata-rata tidak diperoleh; watch hours dibagi total views tidak diperlakukan sebagai metrik retensi resmi.

Evidence mentah: `overview.json`, `content.json`, `top-video.json`, dan `overview.png`. Sumber distribusi pada tab Shorts dipakai untuk menganalisis Shorts; angka distribusi pada ringkasan semua format tidak dicampur dengannya. Ringkasan otomatis Studio digunakan sebagai petunjuk dan diperiksa terhadap judul serta metrik video.

## Pemeriksaan catatan video

`upload-performance.json` memuat proyeksi terbatas dari 708 catatan upload, tanpa token/sesi/kredensial. Dari 580 catatan terkonfirmasi yang punya pengukuran, seluruh pengukuran berasal dari statistik publik; metrik retensi/subscriber per video belum tersedia dalam kolektor tersebut. Banyak catatan berstatus private, sehingga tidak boleh dianggap sebagai eksperimen publik yang gagal.

Evaluasi baru memakai video terkonfirmasi, publik menurut checkpoint, channel yang sama, identitas remote unik, publikasi berumur minimal 24 jam, pengukuran setelah umur minimum, dan snapshot maksimal tiga hari. Long serta lane News dipisahkan dari penilaian niche Short biasa. Status privasi remote tidak direkonsiliasi ulang untuk setiap catatan; pengecualian private bersifat konservatif.

Dengan jendela 28 hari, **156 Short memenuhi syarat**, termasuk **43 cerita karakter** dengan median **1.552 views**. Median keunggulan setelah dibandingkan dengan video kategori lain dalam kelompok usia tayang yang sama sekitar **1,79×**. Satu video yang kebetulan besar, beberapa duplikat retry, satu kategori dengan kurang dari tiga sampel, atau baseline private nol views tidak cukup untuk memilih niche unggulan. Pengukuran catatan ini berbeda cakupan/waktu dengan laporan Studio yang berakhir 11 November.

Hasil rinci: `growth-evidence.json`.

## Yang diterapkan pada kode dan konfigurasi

1. Preferensi cron tidak lagi hanya mengenali gaming versus semua konten lain. Kategori yang punya bukti berulang dapat menang, dengan lane opsional tetap mengikuti pengaturan aktifnya.
2. `.env`, contoh konfigurasi dan Compose diarahkan ke **75% prioritas niche terbukti / 25% eksplorasi**, jendela 28 hari dan umur minimum 24 jam. Ini aturan pemilihan lane biasa; bukan janji proporsi publikasi yang pasti, bukan kenaikan kuota upload, dan bukan pengubahan lane News terpisah.
3. Jika subseri karakter itu sendiri punya bukti unggul, pencarian dan `theme_focus` diarahkan ke cerita karakter tersebut. Keberhasilan gaming lain tidak otomatis memberi prioritas ke subseri yang lemah. Katalog generik tidak dimasukkan lagi ke daftar query batch pemenang.
4. Brief editor cron yang relevan meminta masalah/tindakan tokoh muncul pada dua detik pertama, nama dan konflik sesuai sumber, satu akibat/payoff tuntas, caption stabil, identitas seri konsisten, tanpa cliffhanger atau pemanjangan durasi. Ini hipotesis produksi untuk diuji, bukan klaim bahwa pembuka tertentu sudah terbukti sebagai satu-satunya penyebab.
5. Nama Yuta/Mio tidak disisipkan ke cerita lain, hashtag agama tidak diwariskan ke fiksi/game, dan gate hak/konteks/duplikasi tetap berlaku. Manual dan lane News tidak menerima brief karakter ini.
6. Endpoint baca `/api/automation/viral-cc/growth` menjelaskan sampel, pengecualian, kategori unggulan, umur pengukuran dan proporsi prioritas. Tidak ada retensi atau approval yang dikarang.

Hipotesis eksperimen berikutnya: gunakan seri dan tipe konflik yang sama, ubah pembuka saja, lalu bandingkan stayed-to-watch dan persentase tonton dengan video sejenis pada umur publikasi yang sama. Setelah itu evaluasi konversi subscriber dan penonton yang kembali. Jangan meniru hashtag atau menganggap semua video animasi akan punya hasil sama.

## Validasi dan aktivasi

**96 tes terarah lulus**, termasuk pemilihan niche, pemisahan private/Long, duplikasi remote, rentang usia/snapshot, outlier, subseri lemah, eksplorasi, penerusan query dan isolasi manual/News. Python compilation, `bash -n`, dan `git diff --check` lulus. Percobaan suite `test_api_budget.py` yang lebih luas dihentikan setelah lama tidak maju; suite lengkap itu tidak diklaim lulus. Bukti tes yang selesai ada di `focused-tests.xml`.

**Perubahan belum aktif di container.** Percobaan aktivasi berhenti pada `sudo: a password is required`. `activation.json` menyimpan release runtime, release sumber yang diharapkan dan status ini. Konfigurasi `.env` baru berlaku sesudah recreate.

```sh
sudo bash scripts/activate-ryuundy-growth.sh
```

Script membangun image, menunggu pekerjaan aktif selesai melalui guard yang sudah ada, mengaktifkan backend/bot, memverifikasi release dan endpoint growth, serta memulihkan sakelar cron sebelumnya. Hasil verifikasi runtime ditulis ke `reports/ryuundy-growth-activation.json`; build atau tes saja bukan bukti aktivasi.

Tidak ada email, perubahan video lama, pengunggahan ulang, pengubahan jadwal publikasi, atau jaminan pertumbuhan yang dibuat dalam analisis ini.

Referensi primer: [YouTube: search and discovery for Shorts](https://support.google.com/youtube/answer/11914225?co=YOUTUBE._YTVideoType%3Dshorts&hl=en) dan [definisi metrik konten YouTube](https://support.google.com/youtube/answer/12220281?hl=en). YouTube menjelaskan pemilihan menonton, durasi/persentase tonton, dan kepuasan penonton sebagai sinyal; format animasi bukan jaminan distribusi.
