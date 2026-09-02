# Fendy Clipper Backend

FastAPI service and CLI for generating vertical 9:16 clips from YouTube videos.

Pipeline:

1. Fetch metadata and download source video with `yt-dlp`.
2. Extract mono 16 kHz audio with FFmpeg.
3. Transcribe audio locally with `faster-whisper`.
4. Score transcript windows into clip candidates.
5. Export MP4 clips, SRT subtitles, and JSON metadata.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## CLI

```powershell
.\.venv\Scripts\python.exe clipper.py "https://youtu.be/RPTFTa8fgNs?si=TEDG1jDjGRgI9_Cz"
```

## API

```powershell
.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8010
```

Main API:

```text
GET  /api/health
POST /api/jobs
GET  /api/jobs
GET  /api/jobs/{job_id}
DELETE /api/jobs
GET  /outputs/<generated-file>
```

## Telegram Bot

Run the bot after the API is available:

```powershell
$env:TELEGRAM_BOT_TOKEN="<token>"
$env:TELEGRAM_OWNER_ID="<numeric-user-id>"
$env:BACKEND_API_BASE="http://127.0.0.1:8010"
.\.venv\Scripts\python.exe telegram_bot.py
```

The Docker Compose setup starts this process automatically. Access is checked
against `TELEGRAM_OWNER_ID` for every message and button callback. The primary
flow accepts a pasted YouTube link, checks whether it was processed before,
offers **Clip Pendek 9:16** and **Long Story 16:9**, then records the explicit
source-rights confirmation when the owner starts the job.

Common CLI options:

```powershell
.\.venv\Scripts\python.exe clipper.py "URL" --top 5 --min 25 --max 180
```

Test cepat tanpa transcribe full video:

```powershell
.\.venv\Scripts\python.exe clipper.py "URL" --model Systran/faster-whisper-base --analyze-seconds 180 --top 1
```

Output:

```text
outputs/
  <judul-video>/
    metadata.json
    audio.wav
    transcript.json
    candidates.json
    clips/
      clip_01_*.mp4
      clip_01_*.srt
      clip_01_*.json
```

Default output video:

- vertical `1080x1920`
- H.264 MP4; jalur default Standar memakai `veryfast`/CRF 20, preset Jernih memakai `fast`/CRF 18, dan Maksimal tetap `slow`/CRF 14
- source download mencoba sampai 2160p pada preset Jernih/Maksimal (`bestvideo+bestaudio`)
- hingga tiga job dapat berjalan dari tab berbeda; jatah CPU per job dibatasi lewat `FENDY_CLIPPER_CPU_THREADS_PER_JOB` agar Whisper dan FFmpeg tidak saling memenuhi seluruh core
- source YouTube memakai Deno + `yt-dlp-ejs` untuk challenge JavaScript terbaru; downloader mencoba jalur default, audio-video muxed, web-embedded/EJS, lalu HLS dengan partial file terpisah bila URL media awal ditolak
- subtitle burned-in
- caption dinamis menyorot kata penting dari ucapan asli, dengan timing berbobot jumlah kata dan margin aman agar tidak tertutup action rail/judul UI Shorts; file SRT bersih tetap dibuat untuk accessibility
- caption ringkas dengan outline/shadow tanpa gradient band agar wajah dan piksel sumber tetap bersih
- frame cover Shorts 9:16 ditanam pada opening sebagai kartu konteks ringkas berbasis hook transcript; badge, warna aksen, dan variasi layout mengikuti tema klip agar batch tidak tampak seperti template identik; preview sekitar 0,78 detik menjadi panduan untuk menggeser timeline lewat aplikasi YouTube. Keyframe tidak dianggap dapat memaksa tiga saran otomatis YouTube, dan Shorts tidak menerima upload gambar thumbnail kustom seperti long-form
- CTA kontekstual berbentuk pertanyaan mengikuti tema klip dan muncul singkat di atas payoff yang masih bergerak; voice-over template dinonaktifkan secara default agar dialog asli dan loop tetap utuh
- CTA Subscribe memberi alasan yang mengikuti tema setelah payoff (misalnya hikmah, cek fakta, atau pelajaran berikutnya); Short menggabungkannya dengan pertanyaan komentar, sedangkan long-form hanya menampilkannya sekali pada bab terakhir tanpa reward atau urgensi palsu
- seluruh output short dan kompilasi long-form mendapat kabut asap putih bergerak yang halus di tepi bawah/sudut; overlay dibuat prosedural pada resolusi rendah, divariasikan dari isi cerita, dan dirender di bawah subtitle/watermark agar wajah serta teks tetap jelas
- guardrail kebijakan Shorts dicatat di sidecar render: batas resmi dan rentang produksi maksimum 180 detik, pemilihan durasi adaptif tanpa filler, kebijakan upload nol-klaim untuk setiap Content ID tanpa memandang durasi/dampak saat ini, strategi thumbnail frame-tertanam, metadata CC yang tidak dianggap sebagai bukti rantai hak, serta kewajiban review hak/orisinalitas dan inauthentic-content; snapshot aturan memiliki tanggal review dan otomatis ditandai kedaluwarsa agar proses 2027+ tidak menganggap aturan lama masih pasti berlaku
- mode `YOUTUBE_STRICT_ZERO_CLAIM=true` menonaktifkan jalur cepat Checks untuk upload Private: Studio wajib memberi hasil pemeriksaan final dan status diperiksa ulang tiga kali sebelum Simpan. Klaim audio-visual hanya menggagalkan klip yang cocok; klip saudara tetap antre dan menjalani Checks masing-masing.
- setiap upload membuka, mencari, dan memverifikasi checkbox playlist secara eksplisit; antrean hanya menerima konfirmasi sukses setelah dialog tertutup dan ringkasan playlist cocok, dengan retry lokal tanpa melompati job berikutnya
- setiap Short dan long-form hanya menampilkan watermark halus `ryuundyofficial`; ID audit deterministik, metadata provenance Fendy Clipper di MP4, dan hash SHA-256 tetap disimpan tanpa memenuhi layar video; klaim dibatasi pada kontribusi editorial, bukan kepemilikan materi sumber
- setiap output menyimpan `codex_growth_blueprint`: identitas seri berdasarkan tema, promise–payoff retention, CTA setelah value, jalur Short menuju related long-form, rencana A/B title–thumbnail khusus long-form, serta metrik evaluasi 7/28/90 hari tanpa menjanjikan view atau subscriber
- skor FYP 80 dipakai sebagai target antrean otomatis, bukan sebagai klaim algoritma YouTube; clip di bawah target tetap tersedia untuk review tetapi diarahkan ke `Perbaiki Otomatis`, yang memakai hanya MP4 clip tersebut sebagai input `top=1`, mempertahankan atribusi sumber, dan tidak membaca ulang video penuh atau clip saudara
- setiap Short dan long-form mendapat deskripsi siap-upload yang rapi dan informatif: ringkasan spesifik isi, manfaat menonton, pertanyaan diskusi, dukungan Like/Share/Subscribe yang natural, handle channel, catatan konteks editorial, serta hashtag topikal terdeduplikasi; long-form memakai tiga poin manfaat dan chapter valid tanpa `#Shorts`
- cleanup upload terkonfirmasi menghapus video beserta thumbnail, caption, subtitle, sidecar, source/WAV sementara, workspace, dan folder UUID kosong; startup juga menyapu root output orphan berumur minimal satu jam sambil melindungi semua job serta upload yang masih tercatat
- Auto Search frontend membandingkan isu Muslim terkini dan empat master niche evergreen Islami (mental health, halal wealth, fiqih harian, dan sejarah Islam), lalu menampilkan Top 3 CC Indonesia berdasarkan kecocokan niche + views/hari + engagement + freshness
- hook visual/audio, reaction kontekstual, dan pattern interrupt
- Clip Pendek otomatis memilih backsong instrumental YouTube Studio Audio Library berdasarkan tema/mood. Jika katalog lokal belum punya pasangan, browser headless memakai sesi `Login Sekali`, memverifikasi filter `Attribution not required`, mengunduh satu track, menyimpan hash/lisensi, lalu me-cache hasilnya. Dialog memakai gain 80%, musik maksimal 20%, dan sidechain ducking menurunkannya lagi ketika ada ucapan. Kegagalan sesi atau perubahan UI Studio tidak menggagalkan render; klip Islami masih dapat memakai fallback orisinal CC0 "Cahaya Hikmah". `scripts/import-youtube-audio-track.py` hanya jalur impor manual cadangan.
- mode visual tunggal `auto_fyp` dipakai untuk short dan long-form: basis clean-detail sinematik memilih aksen depth 3D, arsip TV, reframe, atau speaker split secara selektif dari isi cerita
- batch Short mendeteksi beberapa wajah yang benar-benar muncul bersamaan; layout tiga panel hanya dialokasikan ke 1 klip pada batch kecil atau maksimal 2 pada batch besar, dengan frame besar memakai klip aktif dan dua panel kecil wajib memakai dua kandidat klip lain yang tersebar di timeline—bukan tiga crop dari frame sumber yang sama
- nama mode visual lama tetap dapat dibaca untuk kompatibilitas, tetapi otomatis dimigrasikan ke `auto_fyp`
- background asli dipertahankan secara default; pembersihan backdrop dan panel speaker-split tetap tersedia sebagai pilihan khusus
- pembersihan watermark sumber memakai konsensus edge multi-frame konservatif (persistence minimal 0,78), menolak pola subtitle bawah dan detail non-text, lalu menjalankan delogo + feather di koordinat sumber sebelum virtual-camera agar logo tetap tertutup saat cut wide/close-up tanpa kotak gelap atau seam keras
- mode clean-detail menanam dua kartu ringkas berbasis isi di upper safe area: `SUDUT EDITORIAL` pada pertengahan cerita dan `MAKNA UTAMA` menjelang akhir; audit v8 mensyaratkan analisis memakai konsep sumber sekaligus menambah bahasa interpretatif baru, takeaway tetap terbukti dari sumber, dan dua window benar-benar dirender. Crop/blur/speed/watermark/subtitle-only tidak dihitung
- kandidat wajib punya point utama, batas kalimat tuntas, dan payoff dekat ending
- micro-thesis 20–32 detik mendapat jalur khusus bila benar-benar memiliki dilema → nuansa → batas risiko/etika → kesimpulan tidak menghakimi; renderer memilih `restrained_authority` dengan maksimal dua reframe, tanpa reaction sticker/asap, dan tidak menyalin pembicara, branding, wording, atau footage referensi
- anekdot sosial 18–32 detik mendapat jalur `story_punchline` bila memiliki konflik sosial nyata → urutan kejadian → pembanding/reveal → punchline kepada diri sendiri; renderer memakai kartu konteks 1,9 detik dan reframe face-safe bertempo, tanpa sticker, asap, SFX, backsound, atau hinaan buatan
- treatment loop hanya aktif saat payoff benar-benar terhubung ke hook
- semua sidecar mencatat eksperimen pertumbuhan: Short menargetkan 20K views + 20 subscriber dengan checkpoint 1K/5K/10K/20K, sedangkan long-form mempertahankan baseline 5K + 20 subscriber; stabil berarti minimal tiga dari lima upload seformat dan seseri mencapai kedua target, dibandingkan rolling median 10 upload sebanding
- record upload menyimpan maksimal 24 snapshot performa aktual dan diagnosis reach/retention/konversi relatif terhadap seri; endpoint refresh memakai YouTube Analytics OAuth bila tersedia, lalu fallback ke statistik publik YouTube Data API
- Long Story Director mengambil teaser tuntas 10–22 detik dari beat terkuat, menghapus bagian teaser dari posisi asal agar tidak duplikat, lalu menyusun konteks, perkembangan, penjelasan, dan kesimpulan mengikuti kronologi sumber tanpa filler durasi
- mode produksi aktif hanya `short` dan `highlight_5m`; kegagalan atau klaim tidak pernah mengubah job menjadi mode generatif lain
- log sumber sukses memakai indeks cepat untuk deteksi duplikat dan arsip audit fisik `data/source_usage/YYYY/MM/source_usage.json`; event lama dibackfill otomatis dan dideduplikasi berdasarkan job + format
- short menjalani auto-repair hook/ending pada shortlist yang lebih luas sebelum seleksi final; hanya kandidat FYP minimal 78 yang diekspor dan preflight YouTube menahan output lama di bawah ambang tersebut
- variasi motion dipilih deterministik dari isi cerita (bukan nomor urut export) agar rangkaian upload tidak terlihat seperti template massal yang identik
- audit monetisasi v2 hanya meloloskan upload Private bila alur hook–pesan inti–payoff utuh dan edit kamera/emphasis/audio benar-benar mengikuti transcript; hasil audit bukan jaminan diterima YPP
- metadata/chapter container sumber tidak diwariskan ke MP4 hasil; bukti lisensi tetap disimpan lokal
- transcript lokal accuracy-first via `Systran/faster-whisper-medium`, beam search,
  VAD, word timestamps, dan cache yang terikat model/bahasa
- nama orang/brand/istilah khusus dapat diprioritaskan melalui
  `FENDY_CLIPPER_TRANSCRIPTION_HOTWORDS` (pisahkan dengan koma)
- durasi clip pendek adaptif 25–180 detik; jendela di atas 60 detik harus memiliki perkembangan informasi dan payoff yang utuh
- mode `short` tidak merender kompilasi tambahan

Untuk membuat satu Long Story sinematik 5–10 menit (bukan Short), pilih target 300–600 detik:

```powershell
.\.venv\Scripts\python.exe clipper.py "URL" --clip-mode highlight_5m --compilation-target 600 --min 30 --max 90 --visual-mode auto_fyp --ai-enabled
```

If CPU feels too slow, use a smaller model:

```powershell
.\.venv\Scripts\python.exe clipper.py "URL" --model Systran/faster-whisper-base
```

## Notes

- This service is local-first. Add auth, rate limiting, and quotas before public deployment.
- Do not commit `outputs/`, `.env`, or `jobs.json`.
- Process only videos you have rights or permission to use.
