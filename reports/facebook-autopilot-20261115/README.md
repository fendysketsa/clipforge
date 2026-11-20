# FB Pro otomatis dan prioritas bonus US$1

Pekerjaan sumber disiapkan pada 15 November 2026. Fitur ini **belum aktif pada
container produksi**, dan **belum ada publikasi Facebook** dari pengujian ini.

## Perilaku yang disiapkan

- Worker Facebook terpisah berjalan dari startup backend normal. Jadwal dasar
  13 Reel dan 7 cerita per minggu, Asia/Jakarta, dengan jeda minimal tiga jam.
  Slot hari sebelumnya tidak dikejar dalam satu ledakan publikasi.
- Selama bonus masih terbaca aktif dan publikasi awal belum cukup, Reel
  didahulukan dari Story. Maksimal dua slot Reel sehari, termasuk Minggu selama
  prioritas bonus. Tidak ada perubahan pada target YouTube/TikTok.
- Syarat bonus dibaca dari bukti akun: tiga Reel, minimal 10 detik, dan minimal
  10 tayangan memenuhi syarat pada satu Reel. Tanggal bonus yang terbaca adalah
  12–19 Nov. Jam cutoff tidak dikarang. Bukti kedaluwarsa tidak diprioritaskan.
- Jumlah publikasi terkonfirmasi, jumlah Reel yang diakui Facebook, dan status
  pemberian bonus adalah tiga bidang berbeda. Tiga upload lokal tidak otomatis
  mengubah bonus menjadi tercapai. Setelah publikasi, pembacaan akun disegarkan;
  selama fokus bonus, pemeriksaan berlangsung paling cepat setiap 30 menit.
- Produksi berupa naskah dan demonstrasi digital asli, berlabel simulasi,
  bernarasi Indonesia. Tidak memakai footage atau musik pihak lain. Penulis
  naskah berpijak pada objek serta operasi simulasi, dan menahan naskah identik.
- Render portrait 1080×1920, 26–55 detik, subtitle frasa stabil, watermark
  RYUUNDY versi yang sama dengan Short. Bahan dan hak penggunaan tetap tercatat
  secara internal; caption publik tanpa sumber atau URL.
- QC independen memeriksa bingkai, audio hasil render, transkrip/timing dan
  konteks. Hanya PASS_UPLOAD yang terikat pada file, sidecar, subtitle, sumber,
  dan identitas job yang dapat masuk jalur upload otomatis. Checkbox manual
  tidak dapat melewati gate ini. Perbaikan caption dibatasi sekali.
- Sumber yang ditolak QC dipensiunkan; ringkasan audit dipertahankan. Respons
  kosong atau layanan AI tidak tersedia tetap menahan file untuk pemeriksaan
  ulang. Penolakan provider tidak dialihkan menjadi pass.
- Upload menyimpan batas sebelum Post. Percobaan yang ambigu tidak diunggah
  ulang. Story memerlukan audiens Publik yang terbukti dan ID dari respons
  pembuatan Story pada aktor yang sesuai. Tidak mengubah privasi akun diam-diam.
- Dashboard menyediakan progres FB, rencana, tahapan, jeda/lanjutkan, tugas
  native Facebook, bonus, dan hasil. Produksi FB tidak bercampur pada riwayat
  utama YouTube/TikTok. Rekaman manual merupakan opsi tambahan.

## Bukti yang sudah tersedia

- Sesi Facebook target diperiksa dan terverifikasi melalui browser sosial
  bersama. Collector aktivitas hanya menyimpan label, angka dan timestamp.
- `activity-snapshot.json`: tugas Facebook saat dibaca adalah 0/7 postingan,
  0/2 Reel, 0/10 pengikut, dan 120/900 tayangan. Angka ini berbeda dari sasaran
  13/7 pada screenshot pengguna, sehingga tidak disamakan dengan rencana lokal.
- `original-demo/facebook_original.mp4`: demo mengurutkan ukuran file,
  **27.144 detik, 1080×1920**, decode media penuh lulus. QC aktual PASS_UPLOAD,
  confidence 0.95; hasilnya ada di `original-demo-qc.json`.
- `end-to-end/outputs/facebook_autopilot/fb-original-verification/`:
  demo salin/pindah dengan naskah baru, **32.666667 detik, 1080×1920**. QC
  sempat tertahan karena respons layanan kosong, lalu recheck aktual memberikan
  PASS_UPLOAD 0.95. Worker berhasil melanjutkan file yang sama ke callback
  antrean lokal tanpa review manusia palsu atau publikasi. Lihat
  `end-to-end/qc-recheck.json` dan `end-to-end/verification.json`.
- Pemeriksaan Story nyata membuktikan video dapat masuk composer dan audiens
  Publik sudah dipilih. Pengaturan tidak diubah dan Bagikan tidak ditekan.
  `story-audience-verification.json` mencatat hasil ini. Publikasi dan respons
  create-Story belum diuji pada akun sebenarnya.
- `settings-verification.json`: otomasi disimpan enabled untuk startup normal;
  ledger upload, binding sesi dan pengaturan terdahulu dipertahankan. Pada
  pemeriksaan tersebut API Facebook runtime masih HTTP 404.
- TypeScript dan kompilasi Python akhir lulus. `bonus-offline-verification.json`
  membuktikan secara offline urutan Reel sebelum Story, batas jadwal, pemisahan
  upload dari penghargaan bonus, dan penahanan bukti bonus kedaluwarsa.
- Pengujian sebelumnya: 123 regresi dan 20 tes worker terarah lulus. Percobaan
  regresi luas terakhir mencatat 450 lulus dan satu fixture pemeriksa aset
  frontend perlu diperbarui untuk marker fitur baru. Fixture sudah diperbaiki;
  re-run final API/pytest belum dapat dijalankan.
- UI sebelum perubahan prioritas bonus terakhir diperiksa pada 1440, 1280,
  390 dan 320 piksel, mode gelap/terang, jeda/lanjutkan, pemisahan riwayat dan
  backend tidak tersedia. Tidak ada overflow atau error halaman. Bukti ada di
  `ui-verification.json` dan gambar `autopilot-*.png`. Banner bonus terbaru
  sudah lolos typecheck, tetapi belum melalui build dan screenshot final.

## Yang masih terhalang

Peninjauan izin otomatis untuk pemeriksaan akhir gagal karena batas penggunaan
Codex. Tool menyebut dapat dicoba lagi pukul 14.26 WIB. Tindakan yang diminta
tidak dieksekusi; kegagalan ini bukan keputusan bahwa tindakannya tidak aman.
Pemeriksaan jaringan/API, build final dan deployment tidak dicoba melalui jalur
lain untuk melewati peninjauan tersebut.

Deployment sebelumnya juga tertahan autentikasi sudo. Perintah standar tetap:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

Build, pemeriksaan source dan readiness telah terintegrasi pada jalur normal
Docker. Setelah akses tersedia, jalankan regresi akhir, build/UI final, lalu
deployment standar pada waktu aman untuk pekerjaan aktif dan periksa layanan
berjalan sebelum menyatakan fitur aktif. Tidak diperlukan skrip aktivasi lain.

Bonus US$1 belum diklaim tercapai. Status bonus, kelayakan tayangan dan penghasilan
aktual tetap harus dibuktikan oleh Facebook. Tidak ada janji US$1 juta atau
waktu pencairan.
