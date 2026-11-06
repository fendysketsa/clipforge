# RYUUNDY: belajar dari referensi clipper dan memperjelas nilai kanal

Status: reference learning, cooldown penolakan seleksi, dan renderer motion
terverifikasi aktif pada 6 November 2026 pukul 14:56 WIB. Kelima hash source
cocok dengan laporan aktivasi terbaru; API sehat dan scheduler kembali aktif.
Aktivasi 11:27 WIB merupakan versi sebelumnya. Bukti terbaru berada di
`ryuundy-motion-completion-20261106.json`; detail insiden dan renderer tersedia
di `selection-rejection-incident-20261106.md` dan
`ryuundy-motion-implementation-20261106.md`.
Tidak ada referensi yang diunggah ulang atau kuota yang ditambah.

## Cakupan bukti

Pencarian yang diberikan pengguna menghasilkan 25 entri Shorts dan 10 video
biasa pada halaman awal publik, tanpa login, dengan bahasa/wilayah Indonesia.
Ini snapshot, bukan seluruh hasil dan bukan salinan persis hasil personalisasi
pengguna. Enam halaman player diperiksa untuk metadata; empat frame pembuka
diperiksa secara visual. Caption terdaftar pada lima sampel tetapi endpoint
mengembalikan respons kosong. Percobaan yt-dlp pada satu sampel juga gagal
mengekstrak format. Tidak ada klaim bahwa seluruh video atau pacing sudah
ditonton/didengar.

Metadata dan batas bukti disimpan di
`ryuundy-reference-research-20261106.json`. Angka views kumulatif berikut adalah
snapshot publik, tanpa normalisasi usia video, distribusi, atau ukuran kanal.

| Referensi | Snapshot | Yang terlihat / dapat dipelajari | Batas kesimpulan |
| --- | --- | --- | --- |
| [Transisi clipper](https://www.youtube.com/shorts/vjFvay-hd9k) | 13 dtk; 120.550 views | Judul menyebut satu keterampilan spesifik; frame pembuka berupa gradien dengan satu kata. | Tidak membuktikan transisinya menyebabkan views. |
| [Clip podcast](https://www.youtube.com/shorts/E2A60-7Yjk8) | 46 dtk; 107.384 views | Wajah pembicara dominan, kredit sumber di atas, caption kecil di bawah. | Judul "cara viral" tidak membuktikan isinya tutorial; frame menunjukkan podcast. |
| [Tiga jenis hook](https://www.youtube.com/shorts/0TqrYC8ftq0) | 60 dtk; 236.665 views | Headline topik dan wajah segera terlihat. | Klaim FYP pada judul merupakan klaim kreator. |
| [Subtitle smooth](https://www.youtube.com/shorts/YYvtrczzwjo) | 47 dtk; 52.393 views | Judul menawarkan solusi masalah editing yang spesifik. | Frame pembuka hanya gradien; gerak subtitle belum terverifikasi. |
| [Pertanyaan niche](https://www.youtube.com/shorts/VT5jDggdyDY) | 31 dtk; 1.763 views | Deskripsi membahas memahami bidang untuk memilih momen bermakna. | Informasi dari deskripsi kreator, bukan transkrip yang telah ditinjau. |
| [Definisi clipper](https://www.youtube.com/shorts/4gFxhw9x5bo) | 2 dtk; 23 views | Pembanding bahwa hasil pencarian juga memuat konten kecil/berbeda. | Bukan bukti bahwa dua detik selalu gagal atau durasi tertentu selalu menang. |

Hasil ini kebanyakan tutorial dan promosi profesi clipper. Klaim pendapatan,
angka besar, judul "viral", dan efek populer tidak dijadikan rumus otomatis
untuk RYUUNDY. Tidak tersedia analytics retensi kreator-kreator tersebut.

## Arah RYUUNDY yang diterapkan

Brief editorial: **satu momen, satu makna**. Penonton mendapat sesuatu yang
jelas: memahami alasan, melihat akibat pilihan, atau mempelajari satu langkah.
Ini arahan internal editor, bukan slogan yang ditempelkan pada setiap klip.
Tema yang sudah ada tetap memiliki konteks masing-masing.

1. **Manfaat praktis:** masalah yang dikenali -> tindakan konkret dari sumber ->
   hasil atau batasan spesifik. Jika terdeteksi pada Short pengetahuan, nama
   seri yang disarankan adalah **Satu Masalah, Satu Langkah**.
2. **Cerita/game:** keputusan -> konsekuensi -> makna. Reaksi asli dan humor
   boleh menjadi pengantar; gameplay datar tidak otomatis menjadi cerita.
3. **Agama/berita:** konteks, atribusi, dan batas klaim tetap dipertahankan.
   News Hot mempertahankan brief serta review khususnya, dan belum diaktifkan.

Contoh ilustrasi buatan untuk menjelaskan format, bukan kutipan referensi:
"Kenapa subtitle sulit dibaca?" -> pemisahan baris sesuai kalimat -> penjelasan
hasil keterbacaan dan batasnya. Sistem hanya menandai pola semacam ini jika
semua bagian benar-benar tersedia dalam transkrip klip yang sedang diproses.

## Perubahan sistem

- `ryuundy_reference_learning.py` memisahkan sinyal topik dari URL, handle,
  footer promosi, angka lepas, dan kata umum. Misalnya `com`, `www`, `jangan`,
  dan `sampai` tidak lagi memberi bonus tren pada metadata. Kata subjek seperti
  `roblox`, `subtitle`, dan nama pembicara tetap dapat dikenali.
- `api.py` memakai pencocokan bersih pada ranking tren cron dan discovery API.
  Brief RYUUNDY ditambahkan pada tema cron biasa; perspektif manual serta brief
  News tidak diganti. Batas topik, hak sumber, dan kelayakan tetap berlaku.
- `clipper.py` memberikan preferensi ranking kecil, maksimum 3 poin, untuk
  pola praktis lengkap 18–65 detik. Skor ekspor asli tidak dinaikkan dan syarat
  minimum skor, retensi, batas kalimat, konteks, serta review tidak dilonggarkan.
  Bukti masalah/tindakan/hasil ikut diberikan kepada AI dan tersimpan pada
  blueprint pertumbuhan. Bukti visual dan kebenaran klaim tetap belum dianggap
  terverifikasi oleh diagnostik transkrip ini.
- Caption/zoom/transisi tidak diganti mengikuti template referensi. Brief
  meminta visual yang membantu isi dan caption stabil; perubahan ini bukan
  implementasi atau audit audiovisual baru.

## Pengukuran pertumbuhan

Views tinggi menjadi hasil yang diuji, bukan janji. Gunakan publikasi baru
dalam jadwal yang sudah ada, tanpa mengunggah varian hampir sama berulang kali.
Bandingkan dengan median 10 Short dari seri, format, dan usia tayang sebanding.
Uji satu variabel per percobaan: pembuka yang lebih spesifik atau urutan
penjelasan, bukan mengganti semuanya sekaligus.

- Sekitar 6 jam: shown in feed dan chose-to-view; jika sampel terlalu sedikit,
  tunggu data tambahan sebelum menyatakan hook gagal.
- Sekitar 48 jam: engaged views, average view duration, average percentage
  viewed, dan lokasi drop-off. Pisahkan distribusi kecil dari penonton yang
  memilih menonton tetapi cepat keluar.
- Setelah 7/28 hari: subscriber yang didapat, share, dan penonton kembali.
  Ulangi topik/pendekatan yang menunjukkan respons baik pada beberapa episode.

Alasan menggunakan metrik tersebut: [panduan discovery Shorts YouTube](https://support.google.com/youtube/answer/11914225?co=YOUTUBE._YTVideoType%3Dshorts&hl=en)
menguraikan pilihan menonton, durasi menonton, persentase ditonton, dan kepuasan.
[Panduan Analytics Shorts](https://support.google.com/youtube/answer/12942217?co=YOUTUBE._YTVideoType%3Dshorts&hl=en)
menyarankan perbandingan format sejenis dan memeriksa pola, bukan menjadikan
satu viral hit sebagai ukuran semua video.

[Kebijakan monetisasi](https://support.google.com/youtube/answer/1311392) dan
[pembaruan orisinalitas Shorts TeamYouTube, 1 Oktober 2026](https://support.google.com/youtube/blog/470890423/prioritizing-original-content-on-shorts?hl=en)
mendukung penambahan perspektif, cerita, atau komentar yang bermakna.
Mengganti subtitle/efek saja tidak dijadikan bukti otomatis bahwa konten sudah
orisinal, berizin, atau pasti mendapatkan monetisasi.

## Aktivasi

Validasi: 129 tes untuk modul baru, seleksi AI, News, dan pengaman deployment
lulus; 39 tes discovery/tren/cron terkait juga lulus (total 168). Python, shell,
enam blok Python dalam script aktivasi, serta `git diff --check` lolos.
Dependency pengujian dipasang di virtual environment sementara `/tmp`; file
state pengujian dipisahkan dari state produksi sebelum import aplikasi.
Percobaan suite lebih luas dihentikan ketika tertahan pada tes streaming
storyboard yang tidak terkait perubahan ini; hasil 168 di atas berasal dari
suite terarah yang selesai, bukan klaim seluruh suite aplikasi lulus.

Percobaan aktivasi noninteraktif awal berhenti pada `sudo: a password is required`,
sebelum script berjalan. Setelah itu muncul laporan aktivasi berhasil pukul
11:27 WIB, dengan hash runtime dan scheduler terverifikasi. Laporan tersebut
memuat versi reference learning sebelum patch cooldown penolakan seleksi.

```bash
sudo bash /www/wwwroot/clipper/clipforge/scripts/activate-ryuundy-reference-learning.sh
```

Script memakai pengaman aktivasi yang sudah ada: build backend, verifikasi
image, pause peluncuran cron baru, tunggu job/upload serta proses media idle,
stage dan compile modul, periksa idle sekali lagi, lalu restart backend yang
sama. Jadwal cron semula dipulihkan dan hash runtime diperiksa. Dependency
modul baru ikut diverifikasi; frontend tidak memerlukan rebuild.

Gunakan `--skip-build` hanya setelah image baru selesai dibangun. Image dengan
source lama akan ditolak sebelum cron dipause. Bukti aktivasi ditulis ke
`reports/ryuundy-reference-learning-activation.json`. Hash dalam laporan harus
cocok dengan versi source yang dimaksud; laporan 11:27 WIB tidak membuktikan
bahwa patch cooldown yang dibuat sesudahnya sudah aktif.
