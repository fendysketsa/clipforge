# Backend siap aktivasi — 10 November 2026

500 tes TikTok upload/retry, deployment, YouTube same-ID verification, director effects dan source cap lulus. Python compilation, shell syntax, dan whitespace diff lulus. Produksi belum aktif: endpoint jadwal belum memiliki penanda fitur baru; sudo -n memerlukan password.

TikTok retry memakai ID upload, hash file, caption, akun, dan visibility yang sama. Maksimal tiga retry dengan jeda 60, 180, dan 600 detik. Hanya error yang terbukti sebelum Post yang layak; intent/acceptance/remote result yang belum pasti memblokir transfer baru. Reservasi retry disimpan sebelum antrean dimulai dan budget tidak direset dengan membuat record otomatis baru. Login, CAPTCHA, rights/QC hold, file berbeda, dan posting terkonfirmasi tidak diulang. Caption diisi melalui kontrol asli dan dibaca kembali; tidak memakai force-click menembus dialog.

Aktivasi semua modul beserta efek cron, statement, CTA follow, batas dua proses sumber, uploader/browser recovery, klasifikasi sumber versi 3, dan pemulihan hasil QC ke job gagal:

```sh
sudo bash /www/wwwroot/clipper/clipforge/scripts/activate-cron-director-effects.sh
```

Skrip menunggu render/upload aktif selesai, mempertahankan browser, memulihkan status sakelar cron, serta memeriksa hash modul dan penanda API live. Jangan masukkan password sudo ke chat.

Dua sumber gagal masih dalam analisis ulang terpisah. Catatan gagal dan sumber asli tidak dihapus selama penyelidikan.

Pembaruan setelah pemeriksaan dua sumber: kategori umum tidak lagi dipaksa menjadi Kajian. Caption retry bertemplate agama yang tidak sesuai disesuaikan hanya sebelum Post, dengan caption lama dipertahankan sebagai audit. Manifest pemulihan operator hanya mengadopsi hasil dengan hash tepat, source-job/source-URL tepat, izin asli, dan PASS_UPLOAD.
