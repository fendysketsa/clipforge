# Penyelesaian jalur Reel animasi Facebook

## Bukti dan perubahan

Reel yang terkonfirmasi sebelumnya, `1844917023309992`, berasal dari renderer
lama. Aktivasi renderer baru tidak mengganti media yang sudah diposting.
Tutorial tanggal dan preview salin file mendapat penolakan safety HTTP 422
dari provider lama. Keduanya tetap terminal; tidak dikirim ulang atau dialihkan
ke model lain. Preview salin telah diberi catatan penolakan di sidecar auditnya.

Untuk **sumber baru berikutnya**, model khusus Facebook dapat dipilih lewat
`backend/data/facebook_qc_provider.json`. Kredensial, penyedia, izin ekspor dan
mode audio tetap mengikuti pengaturan proyek. Model YouTube/Long tetap sama.
Model gratis `inclusionai/ling-3.2-flash:free` berhasil mengidentifikasi gambar
uji biru netral. Ini hanya bukti kemampuan koneksi dan vision, bukan PASS video.

QC Facebook sekarang mengikat fingerprint ke model yang benar-benar dipakai.
Penolakan safety yang sudah tercatat tidak dapat diperiksa ulang setelah model
diganti. Seluruh gerbang hak, media, makna, konteks dan kualitas tetap wajib;
ambang keyakinan FB tetap 0,90.

`POST /api/facebook/originals` menerima request ID 32 karakter hex dan topik
opsional untuk memulai sumber baru melalui worker normal. ID yang sama tidak
membuat produksi kedua, termasuk bila produksi pertama dihentikan QC. Endpoint
mempertahankan publication hold, batas dua proses, jeda tiga jam dan penolakan
unggahan ambigu. Dashboard mendapat tombol “Buat Reel animasi”.

Worker startup normal juga dapat mengonsumsi permintaan operator satu kali dari
`backend/data/facebook_requests/<request_id>.json`. Reservasi disimpan sebelum
berkas antrean dilepas, sehingga rebuild melanjutkan identitas yang sama. Tidak
ada activation script atau worker host tambahan.

## Validasi

283 tes Facebook/deployment/cleanup dan QC Long lolos. TypeScript,
build produksi frontend dan pemeriksaan aset build berhasil. Build lokal:
`fe0IYNRgakiejSxOxNTSU`. Peringatan deprecation FastAPI yang sudah ada masih muncul.

[Tutorial baru 33 detik](new-group-original/facebook_original.mp4) dibuat dengan
naskah, objek dan SFX baru: dua foto berpindah dari Dokumen ke Foto kegiatan,
sedangkan satu catatan tetap di Dokumen. [Bingkai MP4](new-group-original/encoded-storyboard.jpg)
memperlihatkan tindakan dan hasil. Ini sumber berbeda dari tanggal/salin file
yang sudah ditolak. Keputusan QC independennya disimpan di samping MP4 setelah
audit selesai; render dan koneksi vision saja tidak mengizinkan upload.

Percobaan QC pertama tutorial grup berstatus pending karena provider tidak
menghasilkan review. Ini bukan penolakan sumber. Pemeriksaan bukti yang sama
dapat dilanjutkan pada model yang sama. Kapasitas output khusus Facebook kini
eksplisit; respons kosong tetap tidak dapat memberikan izin upload. Bukti
Whisper disimpan terpisah dengan hash MP4, subtitle dan jendela audio, sehingga
retry layanan tidak perlu mengulang transkripsi media yang identik.

Satu permintaan Reel baru sudah masuk antrean startup normal. Request ID tetap
tersimpan di `startup-request.json`; rebuild mengambil permintaan itu satu kali,
menjalankan produksi/QC, dan hanya mengunggah jika memperoleh PASS yang valid.
Ini bukan instruksi mengunggah preview yang ditolak atau melewati QC.

## Aktivasi dan publikasi

Deployment standar sudah dicoba:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

Perintah berhenti karena sudo membutuhkan password operator. Fitur permintaan
produksi baru belum terlihat pada API live saat pemeriksaan 21.30 WIB. Status
render, PASS QC, aktivasi, dan upload terkonfirmasi harus dibaca terpisah.
Belum ada Reel animasi baru yang terkonfirmasi terbit pada tahap ini.

Bukti: [regresi akhir](regressions-final.xml), [QC Long](shared-qc-tests.xml),
[status implementasi](implementation-status.json),
[penolakan sumber salin file](copy-demo-auto-qc.json),
[pemeriksaan vision sumber uji baru](future-model-health-results.json).
