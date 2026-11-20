# Cleanup otomatis tiga upload yang ditolak

21 November 2026, Asia/Jakarta.

## Hasil live

Tiga catatan gagal pada screenshot sudah diarsipkan dan dihapus dari antrean melalui API lokal:

| Upload ID | Judul | Keputusan |
| --- | --- | --- |
| `c62a3a771edf47549916f9ae4a613349` | Apa yang membuat 30 tahun masih lahir ulama? | DROP_SOURCE |
| `9332975dac33445aa9d6e9635e8633ae` | Rencong, Senjata Wanita untuk Pertahanan Dekat | DROP_SOURCE |
| `9aae9796b57a4121880809d317a1014b` | Apa Kabar? Aku Baru Turun Kapal | DROP_SOURCE |

Ketiganya mempunyai marker eksplisit `CLAIMED_UPLOAD_ABORTED`, status failed, upload_confirmed=false, dan bukti cleanup lokal sebelumnya. File, referensi klip pada job, dan upload aktif yang memakai klip yang sama diperiksa ulang sebelum setiap penghapusan.

Antrean **Ditahan: 0** sudah dibuktikan melalui API dan browser production. Semua catatan upload YouTube/TikTok terverifikasi yang ada sebelum cleanup tetap mempunyai identitas dan status konfirmasi yang sama sesudahnya. Tidak ada upload ulang, perubahan visibilitas, atau mutasi remote dalam tindakan ini.

Bukti:

- `live-cleanup.json`: ID, keputusan, arsip, jumlah catatan yang dihapus, dan hasil pemeriksaan sesudah cleanup.
- `browser-production-review.json`: ketiga judul tidak ada lagi, Ditahan=0, tanpa error JavaScript atau overflow mobile, tanpa request mutasi dari browser pemeriksaan.
- `queue-after-cleanup-desktop.png` dan `queue-after-cleanup-mobile.png`: tampilan production setelah cleanup.
- Arsip privat berada di `backend/data/rejected_uploads/youtube/<upload-id>.json`, izin 0600; indeks `by-sha256/<hash>.json` mempertahankan penolakan untuk byte video yang sama.

Ketiga catatan lama tidak menyimpan ID video remote. Karena itu laporan ini menyatakan penghapusan catatan antrean dan kebersihan media lokal, bukan penghapusan video remote yang tidak teridentifikasi. Metadata, marker penolakan, hash, serta identitas upload aslinya tetap tersimpan di arsip.

## Akar masalah dan perubahan

Worker lama sudah menghapus file dan memberi `clip_deleted_at`, tetapi catatan gagal tetap tersimpan. Startup melewati semua klaim yang sudah mempunyai timestamp tersebut. Upload attention juga mengklasifikasikannya sebagai hold tanpa pemeriksaan berikutnya. Akibatnya, penolakan yang sebenarnya sudah selesai menjadi tiga kartu Ditahan permanen.

Perbaikan source:

- Klaim yang terbukti mendapat aksi `drop_source`, bukan hold tanpa batas. Teks error umum seperti kata copyright saja tidak cukup untuk memicu penghapusan otomatis.
- Startup melanjutkan penyelesaian klaim failed/cancelled meskipun media sudah ditandai terhapus.
- Worker attention menjadwalkan cleanup klaim pada setiap siklus, sebelum pemeriksaan browser. Pekerjaan lokal ini tidak menghabiskan anggaran retry upload dan tidak tertahan oleh antrean verifikasi remote atau browser sosial yang sibuk.
- Catatan penolakan diarsipkan secara atomik sebelum kartu antrean dihapus. Pesan log dibersihkan dari kredensial dan query URL bertanda tangan. Jika penyimpanan arsip atau antrean gagal, catatan aktif dipertahankan/dikembalikan.
- Timestamp terhapus tidak dianggap sebagai bukti tunggal: fungsi memeriksa file nyata, referensi klip, proses render/upload, dan upload platform lain yang masih aktif. File yatim yang masih ada tidak dilaporkan sudah terhapus.
- Hash media yang pernah ditolak tetap diblokir melalui indeks arsip setelah kartu hilang. Klip lain dan upload platform lain yang berhasil dipertahankan. Arsip rusak menunda upload, bukan memberi kelulusan.
- Copy UI baru menjelaskan bahwa klip lolos dilanjutkan dan klip ditolak dibersihkan. Copy ini hanya ditampilkan bila backend mengumumkan kemampuan cleanup baru.
- Readiness deployment normal memeriksa versi cleanup, keputusan DROP_SOURCE, kemampuan arsip, dan marker frontend baru. Tidak ada dependency baru atau perintah aktivasi tambahan.

Kebijakan memakai hard gate skill `clipforge-ai-qc`: klaim yang belum terselesaikan menghasilkan DROP_SOURCE. Tidak ada statement atau disclaimer yang dijadikan pengganti kelulusan pemeriksaan. Alur upload yang sudah ada tetap memerlukan bukti QC dan konfirmasi platform; posting dengan status belum pasti tetap dicocokkan sebelum keputusan retry.

## Pengujian dan aktivasi

- Backend: **351 pengujian lulus** pada rejected upload cleanup, upload attention, YouTube uploads, Compose deployment, automatic output cleanup, dan source download.
- Frontend: **74 pengujian lulus**, TypeScript/lint lulus, production build lulus.
- Build frontend `do8v5CVG8knXaZ8uL-cZL`; pemeriksaan build dan kecocokan source melalui deployment-health prepare lulus.
- Python compilation dan `git diff --check` lulus.

Pembersihan tiga item sudah berlaku live. Perbaikan kode otomatis untuk kejadian berikutnya **belum aktif**. Pemeriksaan production masih tidak mengumumkan `rejected_upload_cleanup_version`. API health OK, worker attention lama aktif, dan cron/scheduler berjalan. Rincian ada pada `runtime-before-deployment.json`.

Saat pemeriksaan aktivasi, cron sedang menjalankan produksi `212a1112dfea4e65a74151dc63dd1d7c`. Proses tidak dihentikan. Pemeriksaan akses `sudo -n -l` juga gagal dengan `sudo: a password is required`, sehingga deployment tidak dapat dijalankan dari sesi ini. Perintah standar yang sama tetap menjadi satu-satunya jalur deployment ketika produksi idle:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

Tidak ada hot patch, pengubahan file state antrean secara langsung, atau deployment alternatif. Aktivasi kode baru harus dibuktikan melalui readiness dan fingerprint layanan setelah perintah tersebut berhasil.
