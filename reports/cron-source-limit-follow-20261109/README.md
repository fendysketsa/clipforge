# Batas pemrosesan sumber dan ajakan follow cron

Implementasi siap dan pengujian lulus. **Belum aktif di produksi:** API live masih tidak memiliki penanda cron_source_process_limit dan cron_follow_cta_adaptive. Sudo membutuhkan password interaktif; tidak ada restart atau perubahan antrean produksi pada pekerjaan ini.

## Batas sumber

Maksimal dua proses per sumber. Cron melewati calon proses ketiga dan melanjutkan kandidat lain. Short dan Long merupakan proses terpisah; satu proses yang menghasilkan beberapa klip dihitung sekali. Upload ulang tidak menambah hitungan. Pemulihan job ID yang sama tidak dihitung lagi. Worker yang sudah mulai namun gagal tetap dihitung, sedangkan review-only dan pembatalan sebelum worker tidak dihitung.

Sumber dinormalisasi menjadi video YouTube yang sama walaupun memakai youtu.be, watch, parameter playlist, atau timestamp berbeda. Data lifetime di backend/data/source_process_attempts.json tidak mengikuti pemangkasan card atau masa cooldown. Bootstrap memakai riwayat penggunaan, arsip bulanan, jobs, dan checkpoint campaign yang masih tersedia. Bukti historis yang sudah dihapus dari seluruh tempat sebelum fitur ini dibuat tidak dapat direkonstruksi.

Gate ada pada pencarian, pemilihan kandidat, pembuatan antrean, dan awal worker; pencatatan terakhir dikunci lintas thread/proses. Ledger rusak tidak dianggap kosong. Pemrosesan manual eksplisit tetap dapat melewati batas; hasil prosesnya masuk hitungan saat cron mempertimbangkan sumber tersebut.

Jika sumber mencapai batas saat Short selesai, Long pasangannya dilewati dan Short tetap diproses untuk upload sesuai gate yang sudah ada. Operator Long mandiri mencari Short dari sumber lain. Tidak ada penghapusan video, pengubahan visibility, atau upload baru sebagai bagian dari penerapan source policy ini.

Audit baca-saja menemukan 510 sumber yang masih mempunyai bukti di riwayat, termasuk 78 sumber dengan minimal dua job pemrosesan berbeda; lihat [audit](source-history-audit.json). Ini snapshot sebelum aktivasi, bukan bukti bahwa runtime sudah menerapkan batas.

## Ajakan follow

Satu CTA singkat tanpa ucapan tambahan. Copy mengikuti tema sumber: gameplay, kuliner, hikmah, tips, pembahasan atau cerita umum. Tidak menjanjikan part lanjutan yang belum ada. Waktu memilih batas segmen setelah nilai awal, atau ending jika payoff aman; jendela statement/efek sutradara dihindari. Layout terlindungi dan klip yang terlalu pendek dapat melewati overlay. Long tetap mempunyai ajakan ending dengan copy sesuai tema.

- [Video contoh lokal](follow-preview.mp4)
- [Frame CTA](follow-frame.jpg)
- [Rencana CTA](follow-plan.json)
- [Bukti ekspor vertikal penuh 26 detik](full-export-verification.json)
- [Hasil pemeriksaan](verification.json)

Pratinjau dibuat dari salinan lokal dan tidak diunggah. Video asli tidak diubah. CTA pada ekspor penuh tampil sekali pada detik 9.12–10.87, sedangkan durasi keluaran tetap 26 detik.

## Validasi dan aktivasi

362 pengujian source policy, efek, caption, deployment, dan Long lulus. 86 pengujian relevan API/YouTube tambahan lulus (403 lainnya tidak dipilih). Pengujian mencakup batas persis 1/2/3, URL alias, restart, penghapusan card, bootstrap arsip, ledger rusak, admission bersamaan, worker lama, dan campaign/Long yang meneruskan sumber lain. Syntax/kompilasi dan git diff --check lulus.

```sh
sudo bash /www/wwwroot/clipper/clipforge/scripts/activate-cron-director-effects.sh
```

Skrip membangun dan memverifikasi modul, menunggu pekerjaan aktif sebelum restart, mempertahankan browser upload, memulihkan sakelar cron, dan memastikan API live melaporkan batas sumber 2, CTA adaptif aktif, serta director policy versi 2. Perubahan berlaku untuk render cron baru dan gate worker pada antrean yang dimulai setelah aktivasi. Video lama tidak dirender atau diunggah ulang.
