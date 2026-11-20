# Implementasi animasi edukasi Facebook

15 November 2026. [Video contoh 27,744 detik](demo/facebook_original.mp4),
[storyboard dari MP4](encoded-storyboard.jpg).

## Hasil yang sudah dibuat

Renderer edukasi FB sekarang memakai objek 2D yang mempertahankan identitas
selama tindakan berlangsung. Contoh berkas salinan benar-benar bergerak ke
folder Cadangan, sedangkan berkas Asal tetap terlihat. Kedua lokasi kemudian
diperiksa bergantian, dan salinan diperbesar saat narasi meminta pemeriksaan.
Folder, kertas, penunjuk dan karakter pemandu dibuat langsung sebagai objek
gambar; tidak memakai footage referensi atau layanan gambar berbayar.

Format: 1080×1920, 30 fps, H.264/AAC 48 kHz. Narasi baru berbahasa Indonesia,
subtitle frasa stabil, watermark RYUUNDY yang sama, dan lima SFX buatan sendiri
yang mengikuti masuknya adegan, pemilihan, perjalanan, kedatangan dan pemeriksaan.
Volume terukur sekitar -16,3 dBFS rata-rata, puncak -1,9 dBFS. Kalimat penutup
tetap dikenali sampai kata terakhir; audio berdurasi penuh 27,744 detik.

## Kode yang terintegrasi

- `backend/facebook_motion.py`: model objek dan timeline, tindakan, gambar,
  pemandu, komposisi portrait, serta label yang tetap tegak.
- `backend/facebook_originals.py`: rencana baru otomatis memilih motion v1,
  merender 30 fps dan menyimpan bukti animasi dalam sidecar. Saved plan lama
  tanpa versi motion tetap memakai renderer lama. Checkpoint, ID upload dan
  publication hold tidak dimigrasikan secara spekulatif.
- Sepuluh topik tersedia: salin, kelompokkan, pulihkan, urut ukuran/tanggal/
  nomor, ganti nama, ekstensi, pencarian dan lokasi berbeda. Operasi pemindahan
  tidak menciptakan duplikat; pencarian tidak menghapus berkas; nama sama pada
  folder berbeda tetap mempunyai isi yang berbeda.
- Pengurutan memakai jalur terpisah sebelum menukar posisi, lalu kembali ke
  susunan hasil. Label objek tidak saling menembus ketika bertukar tempat.
- `facebook_creative.py`: SFX membaca timeline tindakan yang sama dengan gambar.
  Waktu frasa TTS diukur; posisi kata kerja di dalam frasa merupakan estimasi,
  dan dicatat demikian. Clock sumber tidak diperpanjang atau dipotong.
- API dan kesiapan startup mensyaratkan `educational_motion_version=1`.
  Frontend menyebut animasi objek 2D; build normal memeriksa keberadaan UI itu.

Perubahan ini khusus jalur edukasi Facebook yang dibahas. Renderer Article
Presenter, berita Gibran dan video Long tidak diubah menjadi format baru ini.
Contoh adalah simulasi berlabel, bukan rekaman perangkat atau aplikasi nyata.

## Validasi

**217 tes regresi lolos**, dengan 24 peringatan deprecation FastAPI yang sudah
ada. Termasuk konservasi jumlah/identitas file, copy versus move, pengurutan
tanpa tumpang tindih pada 101 posisi gerak per topik, filter pencarian, semua
sepuluh topik, plan lama, cleanup, audio penutup dan kontrak deployment.

MP4 didekode menyeluruh dan bingkai hasil encode diperiksa pada pembukaan,
pemilihan, perjalanan, kedatangan dan pemeriksaan akhir. Whisper pada audio
MP4 mengenali kalimat penutup sampai “pekerjaanmu”. Build frontend produksi
berhasil: `Xa_3Z9Y0QljdBARtTNS9U`. Python compilation dan `git diff --check` lolos.

Bukti: [regressions.xml](regressions.xml),
[encoded-verification.json](encoded-verification.json),
[audio-review.json](audio-review.json).

Contoh merupakan **preview untuk ditinjau**, belum diunggah dan tidak diberi
keputusan otomatis `PASS_UPLOAD`. Gate QC independen cron tetap berlaku dan
bukti gerak masuk ke timestamp pemeriksaan; tidak ada bypass provider/QC.
Belum ada klaim hasil ini mengalahkan referensi menurut pengukuran audiens.

## Aktivasi layanan terverifikasi

Perintah standar deployment proyek:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

Percobaan sebelumnya tertahan autentikasi sudo. Pemeriksaan lanjutan pada
15 November 2026 pukul 20.33 WIB menemukan **versi baru sudah aktif**:
`/api/health` sehat, API Facebook melaporkan `educational_motion_version=1`,
dan scheduler Facebook mengirim heartbeat baru. Fingerprint seluruh sumber
backend cocok dengan rilis startup yang berjalan, demikian juga fingerprint
frontend dengan rilis yang disajikan. Aset JavaScript live memuat seluruh
penanda wajib dashboard, termasuk animasi objek 2D dan pembersihan file lokal.
Build frontend live: `NZLB10Cbgvo-gPC99h7jG`.

Tidak diperlukan restart tambahan untuk mengaktifkan kode ini. Tidak ada
postingan remote yang dibuat atau diubah pada pemeriksaan lanjutan. Laporan
startup Telegram memakai rilis backend yang sama; status proses Telegram
terkini tidak diperiksa langsung karena akses Docker memerlukan autentikasi.

Produksi otomatis terakhir ditolak QC provider pada pemeriksaan keselamatan
konten. Sumber tersebut tetap dihentikan dan tidak diulang. Aktivasi animasi
bukan bukti upload berhasil. Snapshot bonus Facebook terbaru masih 1 dari
3 Reel; bonus belum dinyatakan tercapai. Preview di atas belum dipublikasikan,
dan produksi berikutnya tetap harus melewati QC independen.

Status terbaru tersimpan di [runtime-verification.json](runtime-verification.json).

## Keluhan Reel tidak bergerak

Pemeriksaan berikutnya mencocokkan satu-satunya Reel terkonfirmasi,
`1844917023309992`, dengan rencana produksi `d3c240acaab44c53b518732a21a2a61b`.
Rencana itu tidak mempunyai `motion_version` dan memakai renderer lama.
Mengaktifkan renderer baru tidak mengganti media yang sudah terbit di Facebook.
Produksi berikutnya sudah memakai motion v1, tetapi ditolak QC provider dan
tidak dipublikasikan. Hasil Story yang masih muncul di dashboard juga merupakan
produksi lama; unggahannya belum berhasil.

MP4 contoh baru memperlihatkan gerak salinan pada 9,051–12,251 detik. Pengukuran
bingkai encode pada area objek (di luar subtitle) menemukan 73.273 dan 101.891
piksel berubah pada dua selang tindakan, sehingga bukan gambar diam dengan
subtitle berubah saja. Video ini tetap preview terpisah yang belum diterbitkan.
Identitas dan bukti tersimpan di [reel-motion-diagnosis.json](reel-motion-diagnosis.json).
Tidak ada postingan yang dihapus, ditimpa, atau diunggah ulang untuk diagnosis.
