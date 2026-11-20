# Audit dan pemulihan upload — 20 November 2026

Pemeriksaan terakhir: 2026-11-20T07:19:56.874964+00:00. Status antrean di bawah adalah snapshot, bukan janji bahwa pekerjaan tertunda telah selesai.

## Hasil terverifikasi

- YouTube: 9 catatan upload pulih; ID video, playlist dan hasil penyimpanan terkonfirmasi. Tidak ada transfer file baru.
- YouTube: 0 pemulihan masih antre/berjalan; 8 tetap tertahan. Semua menggunakan ID tersimpan.
- Audit native akhir sembilan video: metadata dan nilai visibilitas native cocok; tujuh Dijadwalkan dan dua sudah Publik. Keanggotaan playlist dikonfirmasi dari checkbox native ketika ringkasan hanya menampilkan Pilih/2 playlist. Dua jadwal lokal lama tidak diterapkan ulang pada video yang sudah Publik.
- TikTok: satu catatan gagal direkonsiliasi lewat URL, caption lengkap, akun dan privasi yang sama: https://www.tiktok.com/@titikbalikislami/video/7706909029460708629 . Tidak ada klik Post baru.
- Downloader cron yatim dihentikan via API cancel setelah file parsial tidak bertambah sekitar 38 menit; kedua proses miliknya terbukti berhenti. Checkpoint induk dipertahankan.

## Perbaikan sumber

- Playlist YouTube memakai kolom judul yang terlihat dan dialog native sebagai bukti kesiapan; satu klik Create lalu wajib verifikasi nama persis. Playlist yang sudah ada digunakan ulang.
- Playlist Keluarga dan Rumah Tangga, Animasi, Podcast dan Sejarah, Geografi & Budaya Nusantara kini terverifikasi ada di kanal tujuan. Lucu sudah ada dan digunakan ulang.
- Verifikasi visibilitas memakai nilai native yang tepat, sehingga kata Publik dalam deskripsi atau Tidak Publik tidak disalahartikan. Enam URL gagal lokal ternyata sudah Publik. Lima judul cocok dan satu judul berbeda dari catatan lokal; konflik target Private/metadata ditahan tanpa mengubah publikasi.
- Pembukaan draft dibatasi 30 detik terpisah dari waktu pemrosesan video; progres dilaporkan dan ID yang tidak cocok tetap ditahan.
- Input FFmpeg untuk unduhan jaringan memiliki batas tunggu baca 25 detik; resolusi, durasi sehat dan proses pemilihan kompleks dipertahankan. Uji FFmpeg nyata terhadap HTTP lokal yang macet berhenti setelah 25.29 detik (Connection timed out).
- Pemulihan TikTok hanya menambah kasus kegagalan navigasi profil yang persis, akun lama cocok, belum ada file/Post, dan sesi baru tervalidasi. Batas tiga retry, hash, QC, hak sumber dan privasi tetap diperiksa.
- Penanda kepemilikan tab YouTube kini bertahan pada navigasi/reload, hanya untuk halaman otomasi. Pemulihan berikutnya membersihkan tab otomasi lama yang memiliki penanda; tab tanpa bukti kepemilikan tidak ditutup.
- Petunjuk bonus Facebook tidak lagi mengasumsikan tiga Reel.

Validasi: 450 tes lulus, nol kegagalan; 63 modul backend berhasil dikompilasi tanpa eksekusi. Rincian suite ada di test-results.json. Tes API sempat tersangkut di sandbox dan berhasil diulang dengan izin yang sesuai.

## Facebook: bonus dan hambatan nyata

- Akun monetisasi aktif dan status kebijakan clear menurut dashboard native.
- Bonus US$2 periode 19–26 November: 6 Reel berdurasi minimal 10 detik; minimal satu Reel mendapat 10 tayangan memenuhi syarat. Progres resmi 0/6, 7 hari pada saat pemeriksaan; belum awarded.
- Pendapatan November saat diperiksa US$0.00. Pencairan belum terverifikasi. Jumlah unggahan lokal bukan bukti bonus atau uang diterima.
- Reel aktif “Tanggal yang mudah diurutkan”, 31.536 detik, 1080×1920: checksum media/rencana cocok dan full decode berhasil. Bingkai pembuka, tengah, payoff, akhir dan timestamp QC diperiksa lokal.
- Aturan audit: [clipforge-ai-qc](/home/fcn88/.codex/skills/clipforge-ai-qc/SKILL.md) menyatakan: “If only optional AI service access is unavailable, preserve the deterministic QC hold; never guess a pass.” Karena itu layanan QC yang unavailable tidak diluluskan.
- Audit independen tetap pending HTTP 429: inclusionai/ling-3.2-flash:free sedang dibatasi upstream. Tidak ada PASS_UPLOAD buatan atau penghapusan hold.
- Audit persetujuan otomatis menolak percobaan mengirim thumbnail Reel ke OpenRouter karena izin ekspor data proyek/akun belum eksplisit. Permintaan izin frame/transkrip sudah diajukan; belum ada jawaban. Tidak ada pengiriman media oleh audit lokal ini.
- Lima Reel lama tercatat terkonfirmasi, di luar periode bonus baru. Tiga Story gagal sebelum Share karena audiens Public belum terbukti dan telah mencapai batas percobaan; Story tidak dihitung untuk syarat enam Reel.

## Kasus yang dipertahankan

- Enam kegagalan TikTok tersisa: dua memiliki catatan sukses lain untuk file yang sama; tiga percobaan Post belum dapat dicocokkan dengan ID/caption/privasi yang pasti; satu file 39.56 detik tersedia dan checksum/decode valid tetapi retry perbaikan navigasinya menunggu deployment. Sesi akun tujuan telah diperiksa ulang dan valid.
- Audit Posts TikTok membaca 176 baris. Tidak ditemukan bukan berarti posting tidak ada; kasus ambigu tidak dikirim ulang.
- Metadata lama pada xJH98mFTjzA mengandung indikasi ASR/konteks agama yang perlu dicocokkan dengan rekaman sumber sebelum koreksi atau promosi; y5_Wt18PKdI mempunyai judul native yang berbeda. Tidak ada metadata Publik yang ditimpa berdasarkan tebakan.
- Banyak kegagalan YouTube lama sudah kehilangan media lokal. Identitas remote, bukti Post, catatan sukses duplikat dan hold dipertahankan. Sebagian jadwal publik lama tidak diaktifkan ulang.
- Long dea786e7bdad4e25aeb43d536f35efea selesai render lalu ditolak QC provider HTTP 422 pada 07:14 UTC. Bukti audit dipertahankan dan artefak dibersihkan sebagai long_qc_drop_source; tidak diupload, tidak dicoba ke provider lain. Cron kemudian mulai sumber lain.
- Satu Short lokal belum diupload karena render-QC perlu review, hak sumber belum terverifikasi dan konteks agama berisiko tinggi. Long berstatus review-only tetap ditahan sesuai pengaturannya.

## Aktivasi

- Optimisasi versi 1, frontend terverifikasi dan scheduler cron aktif pada runtime lama.
- Perbaikan sumber dalam laporan ini belum dibangun/diaktifkan: sudo meminta kata sandi. Rilis sumber dan rilis aktif berbeda; lihat activation-current.json.
- Setelah antrean/pekerjaan aktif aman untuk rebuild, gunakan hanya perintah deployment standar berikut, lalu periksa ulang rilis aktif dan kesehatan layanan.

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

## Bukti pemulihan YouTube

| ID video | Status | Playlist terkonfirmasi | Privasi | Jadwal |
|---|---|---|---|---|
| https://www.youtube.com/watch?v=IBSgcUTKQsM | completed | True | public | 2026-11-30T03:00:00+00:00 |
| https://www.youtube.com/watch?v=_CejE0u0Nhc | completed | True | public | 2026-11-30T00:00:00+00:00 |
| https://www.youtube.com/watch?v=vZY655l5HSU | completed | True | public | 2026-11-29T12:00:00+00:00 |
| https://www.youtube.com/watch?v=ON5RPHp2mFY | completed | True | public | 2026-11-29T09:00:00+00:00 |
| https://www.youtube.com/watch?v=BSfrtwAVttg | completed | True | public | - |
| https://www.youtube.com/watch?v=K8Kt3qKZ_Xw | failed | False | private | - |
| https://www.youtube.com/watch?v=le-kao5zNxY | completed | True | public | 2026-11-24T09:00:00+00:00 |
| https://www.youtube.com/watch?v=uQJB_5e7Qw0 | completed | True | public | - |
| https://www.youtube.com/watch?v=V_SitOyPadM | failed | False | private | - |
| https://www.youtube.com/watch?v=IcM64SoGKIM | completed | True | public | 2026-11-24T00:00:00+00:00 |
| https://www.youtube.com/watch?v=Okv2OMQjE5U | completed | True | public | 2026-11-23T12:00:00+00:00 |
| https://www.youtube.com/watch?v=n78PT_rFml8 | failed | False | private | - |
| https://www.youtube.com/watch?v=y5_Wt18PKdI | failed | False | private | - |
| https://www.youtube.com/watch?v=TaceZjq3jkw | failed | False | private | - |
| https://www.youtube.com/watch?v=lelcpmm6Xxc | failed | True | private | - |
| https://www.youtube.com/watch?v=xJH98mFTjzA | failed | False | private | - |
| https://www.youtube.com/watch?v=qBr4jJb2ILM | failed | False | private | - |
