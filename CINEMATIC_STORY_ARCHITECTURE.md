# Artikel dan cerita menjadi film 5–10 menit

Generator mendukung artikel faktual, cerita fiksi, naskah terarah, dan beragam gaya visual. Referensi komisi ini adalah [video Jejolok](https://www.youtube.com/watch?v=_QuNFofjddw), durasi sumber 23:05. Bukti lokal dan batas pembacaannya disimpan di `outputs/cinematic-reference/`. Prinsip yang diterapkan adalah ilustrasi yang mendukung narasi, kesinambungan dunia, dan perpindahan perhatian yang tenang.

## Alur produksi

```text
Artikel / premis / naskah
        ↓
Klasifikasi materi dan arahan gaya
        ↓
Naskah narasi + struktur sebab-akibat
        ↓
Kontrak visual: karakter, lokasi, kamera, properti
        ↓
Narasi neural → pengukuran durasi → alokasi timeline
        ↓
Coverage adegan → gambar / footage yang sesuai kemampuan provider
        ↓
Pemeriksaan aset → cut / dissolve dengan overlap gambar
        ↓
Caption dari ucapan + suara yang kontinu + mixing
        ↓
Render MP4 → pemeriksaan teknis → tinjauan audiovisual
```

1. Pilih **Artikel → film cerita** untuk artikel yang faktanya perlu dipertahankan. Pilihan ini mengirim penanda `/film-artikel` ke perencana. Instruksi mengharuskan narator dan melarang dialog, tokoh, peristiwa, serta bukti faktual rekaan. Ini arahan perencanaan, bukan pemeriksa kebenaran otomatis; hasil tetap perlu diperiksa terhadap artikel.
2. Pilih **Cerita / naskah** untuk fiksi atau naskah yang sudah diarahkan. Genre, negara, zaman, spesies, gaya visual, dan ending berasal dari materi pengguna. Cerita tidak dipaksa menjadi drama keluarga tertentu.
3. **Artikel → presentasi** tetap tersedia untuk penjelasan dengan objek dan diagram melalui alur presenter yang sudah ada.

Tuliskan durasi, misalnya `Durasi: 5 menit`, `7,5 menit`, atau `5–10 menit`. Rentang memakai batas atas sebagai target. Antarmuka membatasi permintaan pada 600 detik; durasi akhir mengikuti jumlah ucapan dan tempo yang natural. Artikel pendek tidak diperpanjang dengan pengulangan atau keheningan untuk memenuhi angka.

Pilih format **16:9 · Film layar lebar** untuk film seperti komposisi referensi, atau **9:16 · Film vertikal**. Pilihan tersebut dibawa ke storyboard, keyframe, perintah worker, render, dan riwayat. Alur presenter/ranking ringkas tetap memakai format vertikalnya. Permintaan API lama tanpa pilihan rasio tetap terbaca sebagai 9:16.

## Struktur dan coverage

Untuk naskah baru, perencana menargetkan sekitar satu adegan per 20 detik, dengan batas 36 adegan. Target lima menit sekitar 15 adegan; sepuluh menit sekitar 30. Setiap adegan mengandung 2–3 momen visual tunggal dengan orientasi ruang, aksi, detail atau reaksi yang relevan. Jumlah aktual mengikuti materi dan respons perencana. Parser naskah terarah mempertahankan adegan ke-15 hingga ke-36 sehingga resolusi tidak hilang pada film panjang.

Lima kontrak visual disimpan bersama storyboard:

| Kontrak | Isinya |
| --- | --- |
| Art bible | Medium, tekstur, palet, kualitas cahaya, proporsi |
| Character bible | Identitas, usia, rambut, pakaian, ciri pembeda |
| Location bible | Geografi, tata ruang, cuaca dan perkembangan waktu |
| Director bible | Blocking, arah layar, eyeline, sumbu kamera, ritme |
| Property bible | Bahan, kondisi, posisi, pemilik, perubahan benda utama |

Prompt saja belum membuktikan identitas konsisten. Jalur gambar menyediakan referensi karakter bila provider mendukungnya; pemeriksaan histogram/wajah yang tersedia hanya menjadi sinyal awal. Tinjauan visual tetap menentukan apakah wajah, pakaian, properti dan geografi benar-benar terjaga.

## Gambar dan suara bertemu pada satu jam

TTS diukur sebelum durasi adegan ditetapkan. Caption, shot, dan batas adegan mengikuti pembulatan posisi kumulatif pada 30 fps. Membulatkan durasi setiap adegan secara terpisah dapat menggeser gambar terhadap suara dalam film panjang.

Cut menjaga kelanjutan aksi dan matching object. Dissolve dipakai pada perpindahan waktu/tempat. Gambar sebelumnya tetap terlihat di bawah gambar baru yang perlahan menjadi opak. Hanya lapisan masuk yang berubah opacity; tidak ada fade ganda yang menurunkan terang gambar. Overlap dibatasi setengah panjang kedua shot untuk menjaga insert singkat tetap terbaca. Overlap memperpanjang handle gambar, tanpa memindahkan batas narasi atau panjang film. Default handle 0,4 detik, dapat diatur melalui `LONG_ANIMATE_TRANSITION_SECONDS` sampai 0,8 detik.

Gerak kamera buatan digunakan pada gambar diam. Footage video mempertahankan gerak kamera sumbernya. Suara narasi tetap kontinu melintasi perpindahan gambar. Mixing musik dan SFX mengikuti aset berlisensi yang tersedia serta prioritas kejelasan ucapan.

## Kemampuan material dan hasil

Provider `local_free`/`off` dapat menghasilkan gambar orisinal dengan kamera bergerak. Itu belum berarti animasi tubuh, ekspresi atau lip-sync penuh. Provider Hypit yang sudah terhubung dapat menghasilkan footage; kemampuan dan durasi tiap request mengikuti model. Untuk kontinuitas karakter yang menuntut referensi gambar/video, gunakan kemampuan provider yang menerima referensi itu. Profil atau kredensial yang tersedia tidak dengan sendirinya mengotorisasi biaya baru.

Paket kerja menyimpan `story_outline.txt`, `production_script.txt`, `story.article.md`, `story.hypit.svml`, `video_plan.json`, `remotion_manifest.json`, dan aset adegan. Artikel merupakan narasi yang benar-benar dipakai, tanpa instruksi produksi dan tanpa penulisan ulang yang mengubah ending. Salinannya juga disimpan di folder klip sebagai `*_article.md` dan dirujuk oleh sidecar.

Tinjau opening, tiap transisi, perkembangan tengah, klimaks dan ending pada hasil encode. Pemeriksaan teknis memeriksa durasi, resolusi, audio 48 kHz dan sampel frame gelap di sekitar cut; hasil tersebut tidak menilai akting, anatomi, kebenaran isi atau kualitas suara secara menyeluruh. Film selesai setelah gambar dan suaranya ditinjau terhadap tujuan cerita.

## Contoh komisi ini

`outputs/cinematic-demo-20261102/story.md` adalah fiksi orisinal **Lampu Terakhir di Dermaga**, dengan satu karakter, 15 adegan, 30 shot terarah, dunia ilustrasi pesisir, dan satu narator. Sumber YouTube hanya menjadi referensi bentuk penyajian; gambar, karakter, dialog dan cerita sumber tidak dimasukkan ke contoh.
