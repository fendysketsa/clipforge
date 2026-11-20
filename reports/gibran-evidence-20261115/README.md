# Revisi konteks tanggal pernyataan Gibran

Hasil: [video revisi 36,5 detik](revision/gibran-context-review.mp4).
[Contoh bingkai kartu tanggal](revision-frame.jpg).

## Temuan yang terverifikasi

Video primer **RUU Perampasan Aset: Instrumen Kuat Melawan Korupsi** pada kanal
Gibran Rakabuming / GibranTV, ID kanal `UCVVOv7oy03CsTL0Pi0LSWgA`, diperiksa
langsung melalui halaman YouTube dan metadata pemutarnya:

- URL: https://www.youtube.com/watch?v=UYd82JiEfkE
- Metadata publikasi: `2026-02-12T22:30:59-08:00`, setara
  **13 Februari 2026, 13:30:59 WIB**.
- Halaman yang diperluas juga menampilkan **13 Feb 2026**.
- Ini tanggal publikasi video rujukan; tanggal rekaman tidak disebutkan.

[ANTARA, 13 Februari 2026](https://www.antaranews.com/berita/5414630/gibran-ruu-perampasan-aset-penting-pulihkan-kerugian-negara)
melaporkan pernyataan Gibran mengenai dorongan pengesahan RUU Perampasan Aset,
dengan merujuk GibranTV. Video rujukan dan pemberitaan itu tidak membuktikan
bahwa DPR kecewa, membenci Gibran, atau mempunyai motif tertentu. Komentar
pembicara dipertahankan sebagai komentar, dengan batas verifikasi terlihat.

Bukti primer: [primary-verification.json](primary-verification.json) dan
[official-watch-proof.png](official-watch-proof.png).

## Perlakuan video

- Sumber revisi adalah **Download resmi YouTube Studio** atas unggahan RYUUNDY
  `GXbnjrwSte0`, 720×1280, berdurasi 36,502 detik. Ini salinan publikasi yang
  diunduh kembali, bukan berkas kamera asli. Upaya capture parsial HD ditolak
  sebagai sumber revisi; versi akhir memakai salinan Studio yang lengkap.
- Kartu tanggal tampil **7,15–19,20 detik**, mengikuti kata “menyerukan” yang
  dikenali sekitar 7,28 detik. Kartu mencantumkan tanggal publikasi, penerbit,
  URL rujukan dan batas pengetahuan tentang tanggal rekaman.
- Satu aksen garis warna selama 0,28 detik, lalu teks diam untuk dibaca. Satu
  bunyi informasi buatan sendiri selama 0,32 detik, diturunkan di bawah narasi.
- Kartu menggantikan teks editorial generik pada ruang hitam atas; wajah,
  susunan gambar, watermark dan subtitle yang sudah tertanam dipertahankan.
- Catatan bawah sepanjang video: **Opini pembicara — reaksi DPR yang disebut
  pembicara belum diverifikasi dalam revisi ini**.
- Judul netral yang disiapkan: “Gibran dan RUU Perampasan Aset: konteks tanggal
  pernyataan”. Tidak ada judul atau postingan remote yang diubah.

## Pemeriksaan keluaran

- MP4 H.264, 1080×1920, 30 fps; AAC 48 kHz; durasi audio **36,502 detik**,
  video 36,500 detik. Gambar asal tetap memiliki detail sumber 720×1280.
- Decode seluruh keluaran berhasil. Wilayah gambar, watermark dan subtitle
  mempunyai SSIM **0,996151** terhadap sumber pada clock yang sama.
- Whisper pada audio keluaran mengenali kalimat pembatas penutup
  “mungkin, mungkin loh ya menurut saya”.
- **139 tes regresi lolos**, termasuk sumber/tanggal salah, perubahan hash,
  zona waktu, penyisipan teks, batas bidang gambar, durasi audio sampai akhir,
  bunyi nyata pada akhir fixture, dan alur Facebook terkait.
- Bukti: [encoded-media-verification.json](encoded-media-verification.json),
  [ending-audio-review.json](ending-audio-review.json),
  [source-picture-preservation.json](source-picture-preservation.json), dan
  [regressions.xml](regressions.xml).

Pemeriksaan juga menemukan pemotongan penutup pada graph audio yang menjalankan
`loudnorm` sebelum percabangan ducking dengan efek berdurasi terbatas. Perbaikan
menormalisasi narasi menjadi PCM lengkap terlebih dahulu, memastikan jumlah
sampelnya, lalu memakai input narasi dan sidechain yang independen. Output akhir
mempertahankan penutup, dan perbaikan sumber yang sama diterapkan untuk render
SFX Facebook berikutnya. `fps=30` juga mencegah penanda 1000 fps pada capture
browser menghasilkan duplikasi bingkai. Sumber final Studio sendiri sudah 30 fps.

## Status publikasi dan layanan

File revisi **sudah dirender dan diperiksa**, dengan publication hold untuk
ditinjau. Tidak ada keputusan `PASS_UPLOAD` atau klaim bahwa semua tuduhan dalam
klip sudah terbukti. Tidak ada upload, penghapusan remote, atau perubahan pada
unggahan YouTube/TikTok yang sudah ada.

Perbaikan mixer pada kode Facebook belum diaktifkan di layanan. Percobaan
perintah deployment standar berikut gagal karena sudo meminta password:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

Hambatan aktivasi layanan itu tidak membatalkan file revisi yang telah dibuat
langsung dan diverifikasi di atas.
