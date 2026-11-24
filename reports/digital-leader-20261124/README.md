# Pimpinan Digital & konten moral anak — 24 November 2026

## Peran pimpinan digital

Modul baru `backend/ai_office_director.py` menjadikan Kantor AI dipimpin oleh **Pimpinan Digital RYUUNDY** (`director.model='digital_leader'`), bukan sekadar pengamat. Pimpinan:

- Menetapkan strategi: literasi dan kebiasaan baik anak sekolah lewat cerita edukasi yang aman, orisinal, dekat dengan kehidupan sehari-hari.
- Menerbitkan enam arahan persisten ke departemen yang sudah ada: produksi edukasi, Original Facebook edukasi, distribusi ke semua platform aktif, QC naskah/video edukasi, penutupan bukti pengiriman, dan kebersihan hasil terminal.
- Menyimpan arahan beserta bukti observasi (job, antrean, QC, upload, Status Facebook) agar UI membedakan arahan aktif dari arahan yang menunggu syarat.

Pimpinan **tidak** membuat job, merender, mengupload, mengubah setelan operator, atau membuat bukti QC. Eksekusi tetap pada worker pemilik (`safe_delegate_only`, `no_parallel_production_owner`). `control_version` sengaja tetap `2` dan journal lama tetap kompatibel.

Strategi dapat diperhalus operator lewat `POST /api/ai-office/strategy`, tetapi tidak bisa menambah hak publikasi.

## Upload lintas platform yang lebih lancar

`execute_social_upload()` dulu memegang giliran browser bersama selama menunggu `SOCIAL_UPLOAD_MIN_GAP_SECONDS`. Jeda itu adalah timer, bukan aksi browser, sehingga platform lain ikut tertahan. Sekarang jeda dijalankan **di luar** giliran; giliran hanya dipegang saat memeriksa antrean dan menjalankan upload. Bukti antrean tetap diperiksa ulang setiap detik dan setelah jeda, sehingga entri yang dibatalkan tidak pernah dikirim.

Tes regresi: `test_cooldown_wait_releases_the_shared_browser_turn`.

## Konten Facebook edukasi & moral anak

- Gaya baru `moral_anak` ("Cerita Moral Anak") di bank cerita: panel `Keadaan` → `Pilihan baik`, palet khusus di `motlab/story-scene.mjs`, narasi cadangan yang ramah anak.
- 11 topik sekolah/kehidupan sehari-hari: jujur di kantin, minta maaf, berbagi alat tulis, terima kasih pada guru, antre, menolong teman, merapikan meja, mendengarkan guru, mengakui lupa PR, menyapa tetangga, merapikan meja makan di rumah.
- Prompt penulis naskah kini meminta kalimat pendek, satu kebiasaan baik, contoh di sekolah/rumah, tanpa menakut-nakuti, menghakimi, atau memaksakan keyakinan.
- Semua batas lama dipertahankan: 26–55 detik, naskah orisinal, tanpa footage/musik pihak ketiga, QC independen wajib lolos, tidak ada bukti palsu.

## Sebelas skill `/yt-*` (daftar pasti dari operator)

Daftar yang diberikan operator: `/yt-script`, `/yt-package`, `/yt-edit`, `/yt-comment`,
`/yt-plan`, `/yt-viral`, `/yt-retention`, `/yt-shorts`, `/yt-seo`, `/yt-chapters`, `/yt-audit`.

Semua diimplementasikan sebagai kapabilitas nyata di `backend/yt_skills.py`:

| Skill | Fungsi | Keluaran |
|---|---|---|
| `yt-script` | `yt_script` | Naskah 4 tahap dari bank topik/gaya |
| `yt-package` | `yt_package` | Judul, deskripsi, tag, tagar yang disanitasi |
| `yt-edit` | `yt_edit` | Rencana pacing 60 detik per tahap |
| `yt-comment` | `yt_comment` | Draf balasan aman, tanpa engagement bait |
| `yt-plan` | `yt_plan` | Slot mingguan 13 Reel + 7 Story, tanpa catch-up |
| `yt-viral` | `yt_viral` | Sudut/hook narasi, tanpa janji views |
| `yt-retention` | `yt_retention` | Heuristik pacing naskah, bukan analitik palsu |
| `yt-shorts` | `yt_shorts` | Format Shorts maksimal 55 detik |
| `yt-seo` | `yt_seo` | Kata kunci + judul/deskripsi, tanpa klaim peringkat |
| `yt-chapters` | `yt_chapters` | Bab bertanda waktu dari durasi tahap |
| `yt-audit` | `yt_audit` | Verdict `hold`/`ready` hanya dari bukti yang diberikan |

Manifes dapat dibaca di `GET /api/ai-office/yt-skills`, dijalankan lewat
`POST /api/ai-office/yt-skills/{id}/run`, dan diverifikasi saat deployment oleh
`backend_contract()`. Tidak ada skill yang mempublikasi, mengubah setelan operator,
membuat angka penonton, atau membuat bukti QC.

## Verifikasi

- `backend/tests/test_ai_office_director.py` — 12 pengujian strategi, arahan, dan integrasi koordinator.
- `backend/tests/test_facebook_moral_stories.py` — 14 pengujian gaya/topik moral dan protokol naskah ramah anak.
- `backend/tests/test_social_upload_spacing.py` — 16 pengujian, termasuk giliran browser tidak tertahan saat jeda.
- `npm run typecheck` lolos; 13 berkas tes Node lolos (94 asersi).
- `npm run build` + `node scripts/deployment-health.cjs build` lolos dengan penanda UI baru (`Arahan Pimpinan Digital`, `officeLeaderBrief`, `officeDirectiveList`).
- Hasil suite backend penuh: lihat `suite.json`.

## Langkah produksi

Perubahan memerlukan perintah deployment standar. Setelah image aktif, arahkan seri otomasi Facebook ke bank `topik` agar topik moral anak dipilih otomatis oleh penjadwal (setelan tersimpan tetap dihormati; arahan ini diberikan atas permintaan operator).
