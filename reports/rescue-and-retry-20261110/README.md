# Pemulihan dua sumber dan retry TikTok — 10 November 2026

Dua sumber yang gagal dipilih ulang dari transkrip bertimestamp dan frame sumber, lalu dirender, diperbaiki satu kali, serta diaudit. Hasil lokal siap; backend produksi terakhir masih versi lama. Uji kontrol caption langsung berhasil pada draft tersembunyi tanpa file dipilih, tab baru, atau tombol Post diklik.

## Hasil pemulihan

| Sumber | Rentang asli | Durasi hasil | Bukti |
| --- | --- | --- | --- |
| DAKio0d-_LQ — demonstrasi scanner Minecraft | 88.20–148.55 detik | 60.367 detik | [output](DAKio0d-_LQ/recovered-output.json), [QC](DAKio0d-_LQ/qc-final.json) |
| Y65eFkC2nS0 — prank bunyi drum | 26.20–55.50 detik | 29.30 detik | [output](Y65eFkC2nS0/recovered-output.json), [QC](Y65eFkC2nS0/qc-final.json) |

Setiap video memakai satu adegan utuh. Minecraft mempertahankan penjelasan alat, pengujian dan hasil ponsel di inventory, dengan konteks bahwa ini adegan di dalam game. Komedi mempertahankan satu prank yang sama; tidak menyambung lelucon acak. Rail dekoratif kompilasi dipisahkan dari area video; kredit asli tetap dipertahankan sebagai atribusi. Musik dan suara sumber tidak diganti dengan suara sintetis atau musik tambahan.

Keputusan QC lokal keduanya PASS_UPLOAD. Izin sumber menggunakan konfirmasi eksplisit yang sudah tercatat pada job asli; kontrak hak tidak diverifikasi ulang secara independen. Decode video/audio, resolusi 1080×1920, exposure, sharpness dan preflight upload lokal lulus. Ini tidak menjamin penerimaan platform atau monetisasi.

Analisis awal dan pilihan ada pada analysis_manifest.json dan selected_clips.json di masing-masing folder. Source asli tetap utuh. Input unduhan/preview besar diabaikan oleh Git; hasil akhir berada di backend/outputs/manual-rescue-20261110.

## Pemulihan Riwayat dan antrean

Manifest operator backend/data/reviewed_recovery_outputs.json berisi dua ID job gagal asli, URL clip, hash, dan kandidat bertimestamp. Worker backend baru mengadopsi hanya file yang cocok dengan sumber, hash, izin asli dan QC PASS_UPLOAD. Tidak ada penulisan langsung ke jobs.json milik backend aktif. [Uji integrasi terisolasi](adoption-integration-check.json) berhasil memulihkan kedua job dan mengonfirmasi preflight tanpa blocker.

Dua sumber tersebut tercatat dua proses pada ledger lifetime, termasuk putaran pemulihan ini. Tidak akan dipakai lagi oleh cron setelah kode baru aktif. Scope intake Private yang sudah diaktifkan ditambah hanya dua job pemulihan yang diminta pengguna. Video remote yang terkonfirmasi tidak dihapus atau diunggah ulang.

## TikTok

Bukti kegagalan lama: video sudah sampai pada draft, tidak ada dialog penghalang, caption masih nama file. Editor DraftJS gagal pada interaksi klik di tab latar belakang. Perbaikan menunggu kesiapan, memakai input kontrol asli, lalu membaca ulang isinya. [Uji live](live-caption-control-check.json) berhasil dengan visibility_state=hidden dan post_clicked=false.

Retry bertahap: maksimal tiga kali pada ID/file/account/visibility yang sama, jeda 60/180/600 detik. Hash, gate upload, sibling success dan intent/acceptance posting diperiksa. Unknown post tetap ditahan, bukan ditransfer ulang. Budget disimpan sebelum antrean dimulai dan tidak direset lewat ID upload baru. Kasus login, CAPTCHA, klaim/rights/QC, file berbeda atau posting terkonfirmasi tidak diulang.

Klasifikasi versi 3 memilih gaming, komedi, kuliner, konteks publik atau umum berdasarkan sumber; label agama memerlukan bukti konteks agama. Saat retry pre-Post, template caption agama yang keliru dapat diperbaiki dengan caption lama tetap tersimpan sebagai audit. Ini tidak mengubah media yang sudah terunggah.

## Verifikasi dan aktivasi

500 tes terkait ditambah 66 tes API relevan lulus. Kompilasi Python, syntax shell dan git diff whitespace lulus. [Status terstruktur](verification.json).

```sh
sudo bash /www/wwwroot/clipper/clipforge/scripts/activate-cron-director-effects.sh
```

Paket bertambah setelah pemeriksaan klip: klasifikasi sumber versi 3 dan pemulihan output ke job gagal. Build dari sebelum pembaruan akan ditolak pemeriksaan hash; gunakan paket terbaru dengan perintah di atas. Sudo di sesi agen memerlukan password, sehingga aktivasi tidak dapat diselesaikan oleh agen. Snapshot terakhir menunjukkan belum ada penanda kemampuan baru di API dan tidak ada proses aktivasi yang terlihat. Jangan kirim password ke chat.

Skrip menunggu pekerjaan aktif selesai, mempertahankan browser, memulihkan sakelar cron, dan memeriksa hash sumber/kemampuan live. Pemulihan card dan retry posting baru berjalan setelah backend terbaru aktif. Upload dua klip pemulihan belum dikonfirmasi.
