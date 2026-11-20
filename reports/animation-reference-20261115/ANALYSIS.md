# Analisis pengembangan animasi edukasi ClipForge

Lanjutan setelah izin implementasi: lihat
[hasil pengembangan dan video contoh](../facebook-motion-20261115/README.md).
Catatan di bawah merekam tahap analisis sebelumnya.

Status: **analisis saja**, sesuai permintaan. Tidak mengubah renderer, pengaturan,
cron, video hasil, atau postingan. Tidak menjalankan produksi maupun deployment.

## Bukti referensi

[Referensi YouTube](https://www.youtube.com/watch?v=Mw_cS6UmG8o), kanal Andicha
Channel, diperiksa lewat browser: durasi sekitar 5 menit 22 detik. Pemeriksaan
meliputi 14 sampel sepanjang durasi, 9 sampel detail gerak dan 43 segmen transkrip
otomatis. Ini bukan klaim telah menonton seluruh durasi secara waktu nyata atau
melakukan audit audio menyeluruh. Transkrip ASR membantu membaca alur, bukan
menjadi bukti bahwa seluruh penjelasan ilmiahnya akurat.

Temuan visual langsung:

- Sekitar 00:09–00:20: susunan tata surya diikuti fokus ke objek yang dibahas.
- Sekitar 01:48–01:52: fokus berpindah ke Bumi, kemudian penanda siang/malam
  muncul. Penonton melihat objek dan konteksnya, bukan hanya paragraf.
- Sekitar 02:58–03:02: Bulan berpindah mengelilingi Bumi pada jalur yang terlihat;
  identitas objek tetap mudah diikuti. Label ikut miring pada sebagian gerak.
- Bagian akhir memakai pertanyaan dan jeda jawaban. Tempo ini perlu diadaptasi
  jika format target hanya sekitar 30 detik.

Bukti gambar: [detail gerak](motion-comparison.jpg),
[sampel bagian awal](contact-sheet-1.jpg),
[sampel bagian akhir](contact-sheet-2.jpg).

## Mengapa hasil kita masih terasa kaku

1. **Renderer FB masih berupa panel antarmuka.**
   `backend/facebook_originals.py:frame()` memakai tata letak tetap dan empat
   fase. Gerak baris tertentu sekitar 12 piksel, sementara beberapa operasi
   langsung mengganti keadaan objek. Belum ada tindakan mengambil, membawa,
   menaruh dan memperlihatkan hasil secara berurutan. Ini temuan kode yang
   disiapkan, bukan bukti versi tersebut sudah aktif di container.
2. **Revisi Gibran adalah perbaikan konteks.**
   `backend/evidence_revision.py` menambah kartu tanggal, catatan opini dan satu
   aksen suara. Ia tidak membuat pementasan objek atau animasi edukasi baru.
3. **Presenter sudah punya fondasi, tetapi tindakan masih terbatas.**
   `backend/remotion/src/presenter.jsx` mendukung simbol, garis hubungan,
   partikel bergerak, putaran, pertumbuhan dan gerak kecil. Banyak posisi
   masih ditentukan oleh susunan tetap; hubungan belum selalu mengikuti
   perubahan keadaan konkret pada kata kerja narasi.

## Arah pengembangan yang disarankan

Gunakan panggung animasi 2D yang mempunyai objek beridentitas tetap. Setiap
gagasan harus memiliki **keadaan awal → tindakan yang terlihat → akibat yang
bisa dibandingkan**. Kata kerja narasi menjadi pemicu peristiwa: memilih,
menyalin, membawa, membuka, membagi, mengelompokkan, dan membuktikan hasil.

Sistem yang perlu ditambah kemudian:

- Objek berlapis dengan bagian yang bisa bergerak: tutup folder, dokumen,
  tombol, penunjuk, tangan atau karakter sederhana bila berguna.
- Urutan tindakan per objek, dengan identitas tetap ketika berpindah atau
  menghasilkan salinan. Gerakan punya ancang-ancang, perjalanan dan berhenti
  yang wajar; hasil tidak menghilang sebelum sempat dipahami.
- Waktu tindakan mengikuti narasi terukur, bukan satu gerakan berulang
  sepanjang adegan. Durasi membaca subtitle dan kalimat penutup dipertahankan.
- Pergantian fokus yang beralasan: mendekati objek, mengikuti tindakan, lalu
  menampilkan perbandingan. Gerak latar dan kedalaman hanya mendukung fokus.
- SFX pada sentuhan, gerakan dan hasil, dengan prioritas suara narasi. Gunakan
  perbaikan mixer yang sudah disiapkan agar penutup ucapan tetap lengkap.
- Komposisi portrait yang dirancang dari awal untuk animasi asli, dengan
  label tetap tegak, kontras konsisten, teks ringkas dan area aman subtitle.

Ini dapat menjadi pengembangan jalur animasi edukasi dalam ClipForge, tidak
perlu mengganti keseluruhan dashboard atau memulai aplikasi baru. Presenter/
Remotion adalah fondasi yang relevan; renderer simulasi FB perlu diperluas atau
menggunakan komponen adegan yang sama.

## Contoh treatment untuk niche FB yang sudah dipilih

Topik: **Apa yang terjadi saat berkas disalin?** Durasi rancangan sekitar
30–32 detik; waktu final tetap mengikuti narasi aktual. Antarmuka diberi label
simulasi, tanpa mengaku sebagai rekaman aplikasi tertentu.

| Waktu rancangan | Tindakan visual | Informasi yang dipahami |
| --- | --- | --- |
| 0–2 dtk | Satu dokumen dan dua folder muncul dalam satu ruang; pertanyaan singkat | Mengenali masalah |
| 2–6 dtk | Penunjuk mendekati dokumen di folder Asal; folder Cadangan masih kosong | Keadaan awal jelas |
| 6–13 dtk | Dokumen menghasilkan salinan; salinan menempuh jalur menuju Cadangan; dokumen asal tetap terlihat | Proses menyalin diperagakan |
| 13–21 dtk | Tutup folder terbuka, salinan masuk, penghitung Cadangan berubah dari nol ke satu | Hasil tindakan terlihat |
| 21–27 dtk | Kedua folder terbuka berdampingan, masing-masing memperlihatkan satu dokumen | Berkas asal masih ada |
| 27–32 dtk | Hasil bertahan, narasi menyimpulkan satu gagasan | Penonton mendapat jawaban lengkap |

Kepadatan gerak mengikuti tindakan tersebut; tidak perlu mengganti adegan
secara paksa setiap dua detik. Karakter, jika dipakai, berinteraksi dengan objek
yang menjelaskan informasi dan tidak sekadar mengangguk di samping teks.

Untuk klip berita Gibran, pola yang sesuai berbeda: timeline publikasi, kartu
rujukan yang terbuka, penunjuk pada tanggal, dan pemisahan bukti dengan opini.
Jangan membuat adegan DPR bereaksi atau tokoh mengucapkan dialog baru untuk
mengisi animasi; hal itu belum didukung bukti yang ditemukan.

## Cara menilai target lebih baik

Targetnya lebih jelas, lebih hidup dan lebih mudah diikuti pada layar HP:

- Manfaat terlihat dalam dua detik pertama untuk versi pendek.
- Setiap gagasan penting mempunyai tindakan dan hasil visual yang nyata.
- Objek konsisten antarbabak; label tetap terbaca saat objek bergerak.
- Sebelum/sesudah dapat dipahami tanpa membaca paragraf panjang.
- Gerakan, narasi dan SFX mengacu pada peristiwa yang sama.
- Tidak ada suara penutup terpotong, teks berkedip, tumpukan objek, atau label
  keluar layar. Penilaian dilakukan pada hasil encode, bukan hanya kode.

Belum ada render baru, sehingga belum ada klaim bahwa hasil pengembangan telah
melampaui referensi. Langkah implementasi berikutnya yang paling informatif
adalah satu contoh lengkap bertema menyalin berkas, lalu perbandingan visual
dan audio terhadap kriteria ini sebelum menjadi template cron.
