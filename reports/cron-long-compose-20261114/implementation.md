# Cron Long RYUUNDY dan perintah deployment baku

Instruksi pengguna 14 November 2026 telah dicatat di `AGENTS.md` dan catatan memori: seluruh perubahan harus mengikuti satu perintah deployment ini:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

Tidak diperlukan skrip aktivasi fitur tambahan. Dockerfile sudah memasukkan semua modul Python dan menghasilkan manifest source. Entrypoint memverifikasi manifest dan source yang dipasang sebagai input verifikasi; pemeriksaan kesehatan backend kini juga mewajibkan endpoint strategi Long versi 2, audit alur, lima topik yang diminta, serta kebijakan review politik. Telegram memakai image backend yang sama dan menunggu layanan sehat. Pilihan cron/Long, QC, upload dan status publikasi yang tersimpan tidak ditulis ulang oleh deployment.

## Tema dan konsep

| Tema | Pendekatan Long |
|---|---|
| Misteri | Kronologi, bukti atau cerita narasumber, batas pengetahuan, penutup jujur tanpa mengarang solusi. Jalur sudah ada; hashtag tidak lagi mengklaim otomatis sebagai kisah nyata. |
| Legenda / cerita rakyat | Latar budaya, pilihan tokoh, akibat, akhir cerita dan makna. Legenda tidak dinyatakan sebagai fakta sejarah yang terverifikasi. |
| Politik dalam negeri | Pertanyaan publik, kronologi, atribusi fakta/opini/tuduhan, tanggapan dan dampak masyarakat. Profil `domestic_politics` terpisah dari News Hot yang tetap khusus pendek. Render diizinkan; upload/publikasi otomatis ditahan untuk review manusia. Tidak memaksa QC menghapus render hanya karena menunggu review politik. |
| Makanan sehat | Kebutuhan memilih menu, bahan/porsi/cara masak, perbandingan yang tersedia dan kesimpulan. Pengalaman makan dibedakan dari klaim gizi/kesehatan; tanpa angka gizi atau manfaat medis rekaan. |
| Makanan enak / kuliner | Cerita tempat/proses, rasa/tekstur/porsi/harga berdasarkan sumber, kelebihan/kekurangan dan untuk siapa makanan cocok. Rasa tetap penilaian pengulas. |

Empat profil baru masuk rotasi cron, memiliki query penelusuran, sinyal relevansi, hashtag dan peran Short/Long tersendiri. Sumber yang tidak cocok ditolak oleh gate tema. Audit semantik Long menerima arahan tema editor selain kutipan dari bagian output. Sumber tetap harus lolos permintaan publik, durasi, hak penggunaan, struktur cerita dan QC; semua genre tidak otomatis layak. Tema baru belum memiliki bukti performa kanal atau retensi sendiri.

## Bukti validasi

- 329 tes terarah lulus: deployment Compose, profil tema, propagasi ke kedua format, gate sumber, review politik, News Hot, sejarah, produksi Long, strategi Long, seleksi AI, pertumbuhan, QC dan routing playlist (`tests.xml`).
- 32 tes regresi API terkait Long/compilation/pasangan/perintah worker lulus (`api-regression-tests.xml`).
- Total 361 tes terpilih lulus. Pemeriksaan sintaks Python, shell entrypoint dan `git diff --check` lulus.
- Belum ada render audiovisual percobaan baru atau bukti hasil views.

Pemeriksaan runtime pada akhir pekerjaan: backend sehat tetapi `/api/automation/viral-cc/long-strategy` masih HTTP 404. `sudo -n true` masih meminta kata sandi; perintah Compose baku belum dijalankan oleh sesi ini. Strategi versi 2 dan profil tema baru belum terverifikasi aktif di produksi. Lihat `runtime-status.json`.
