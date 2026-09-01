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
against `TELEGRAM_OWNER_ID` for every message and button callback.

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
- H.264 MP4, CRF 16 untuk preset Jernih dan CRF 14 untuk Maksimal
- source download mencoba sampai 2160p pada preset Jernih/Maksimal (`bestvideo+bestaudio`)
- source YouTube memakai Deno + `yt-dlp-ejs` untuk challenge JavaScript terbaru dan otomatis retry melalui `WEB_EMBEDDED_PLAYER` bila URL media default ditolak 403
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
- intisari ucapan asli disimpan di metadata; mode clean-detail tidak menutup wajah dengan kartu intisari besar
- kandidat wajib punya point utama, batas kalimat tuntas, dan payoff dekat ending
- micro-thesis 20–32 detik mendapat jalur khusus bila benar-benar memiliki dilema → nuansa → batas risiko/etika → kesimpulan tidak menghakimi; renderer memilih `restrained_authority` dengan maksimal dua reframe, tanpa reaction sticker/asap, dan tidak menyalin pembicara, branding, wording, atau footage referensi
- anekdot sosial 18–32 detik mendapat jalur `story_punchline` bila memiliki konflik sosial nyata → urutan kejadian → pembanding/reveal → punchline kepada diri sendiri; renderer memakai kartu konteks 1,9 detik dan reframe face-safe bertempo, tanpa sticker, asap, SFX, backsound, atau hinaan buatan
- treatment loop hanya aktif saat payoff benar-benar terhubung ke hook
- semua sidecar mencatat eksperimen pertumbuhan: Short menargetkan 20K views + 20 subscriber dengan checkpoint 1K/5K/10K/20K, sedangkan long-form mempertahankan baseline 5K + 20 subscriber; stabil berarti minimal tiga dari lima upload seformat dan seseri mencapai kedua target, dibandingkan rolling median 10 upload sebanding
- record upload menyimpan maksimal 24 snapshot performa aktual dan diagnosis reach/retention/konversi relatif terhadap seri; endpoint refresh memakai YouTube Analytics OAuth bila tersedia, lalu fallback ke statistik publik YouTube Data API
- Long Story Director mengambil teaser tuntas 10–22 detik dari beat terkuat, menghapus bagian teaser dari posisi asal agar tidak duplikat, lalu menyusun konteks, perkembangan, penjelasan, dan kesimpulan mengikuti kronologi sumber tanpa filler durasi
- mode `long_animate` menerima naskah orisinal, menyusunnya menjadi storyboard dan art bible, membuat visual berbeda untuk tiap scene, memberikan motion kamera, voice-over Indonesia, subtitle, musik prosedural, thumbnail, serta chapter, lalu menggabungkannya menjadi video 16:9 utuh
- Narasi Long Animate memakai `id-ID-ArdiNeural` dengan delivery tegas (`+8%`), pitch lebih terang (`+2Hz`), dan volume boost (`+8%`) agar artikulasi Indonesia terdengar sigap dan jelas. Profil `LONG_ANIMATE_TTS_PROFILE=islamic_indonesian` menormalkan pelafalan istilah seperti Allah/allah/ALLAH/الله, Al-Qur'an, ustadz, makhraj, wudhu, dzikir, SWT, dan SAW hanya pada input suara; naskah serta subtitle asli tidak diubah. Tempo, pitch, dan volume dapat disetel melalui `LONG_ANIMATE_VOICE_RATE`, `LONG_ANIMATE_VOICE_PITCH`, dan `LONG_ANIMATE_VOICE_VOLUME`.
- Long Animate memakai Ollama lokal untuk storyboard dan Z-Image-Turbo Q3 berlisensi Apache 2.0 melalui stable-diffusion.cpp untuk gambar shot; tidak ada fallback OpenAI dan tidak ada biaya API gambar. Default aman untuk GPU 4 GB adalah `1024x576`, PNG, 8 step, Vulkan, flash attention, CPU offload, VRAM budgeting, layer streaming, dan bobot memory-mapped. Jika worker lokal sempat berhenti, renderer menunggu service pulih, mencoba sampai empat kali, serta menurunkan resolusi lalu menormalkan hasil ke Full HD. Real-ESRGAN `realesrgan-x4plus` berjalan pada skala native x4 dan diberi penajaman adaptif. Parser `Scene`/`Adegan` memisahkan `VISUAL`, `NARASI`, dan `TEKS LAYAR`; aksi berurutan dapat dipecah menjadi 1–3 shot tanpa mengulang narasi. Character, immutable style, dan location bible dibawa ke semua prompt. Vision QA memeriksa frame kosong, ketajaman, jumlah wajah, style drift, dan kemiripan referensi karakter lalu mencoba regenerate otomatis. `LONG_ANIMATE_IMAGE_STRICT=true` menghentikan render bila model lokal tetap gagal setelah seluruh pemulihan, sehingga placeholder tidak dianggap hasil berkualitas. Upload diwajibkan Private lebih dulu dan disclosure AI diaktifkan secara konservatif.
- Timing Long Animate bersifat audio-first: seluruh TTS dibuat, silence tepi dipangkas, dan durasinya diukur. `LONG_ANIMATE_TARGET_DURATION_SECONDS=180` menjadi target maksimum alami; naskah pendek menghasilkan video lebih pendek dan suara tidak pernah diperlambat untuk mengisi tiga menit. Narasi padat dibatasi sekitar `LONG_ANIMATE_MAX_SPEECH_TEMPO=1.18`, dengan jeda scene `LONG_ANIMATE_SCENE_BREATH_SECONDS=0.35`. Storyboard mengikuti hook, konteks, perkembangan, bukti/contoh, hikmah, dan payoff; tiap scene memakai variasi shot serta gerak kamera/ambience halus dan menghindari pose tangan stok. Shot dirender tanpa audio/fade hitam, digabung dengan crossfade `LONG_ANIMATE_TRANSITION_SECONDS=0.12`, kemudian narasi, music ducking, SFX transisi, subtitle, AAC stereo 48 kHz, dan loudness normalization diproses pada master final. `LONG_ANIMATE_OUTPUT_ASPECT_RATIO` menerima `16:9` atau `9:16`; final QC memverifikasi durasi, resolusi, sample rate, dan frame hitam di sekitar cut.
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

Untuk membuat video Long Animate dari naskah:

```powershell
.\.venv\Scripts\python.exe clipper.py --clip-mode long_animate --script-file ".\naskah.txt" --output outputs --ai-enabled --ai-base-url http://localhost:11434/v1 --ai-model llama3.2-id:latest
```

If CPU feels too slow, use a smaller model:

```powershell
.\.venv\Scripts\python.exe clipper.py "URL" --model Systran/faster-whisper-base
```

## Notes

- This service is local-first. Add auth, rate limiting, and quotas before public deployment.
- Do not commit `outputs/`, `.env`, or `jobs.json`.
- Process only videos you have rights or permission to use.
- Mode `original_rebuild` memakai sumber hanya sebagai bahan riset transkrip dan tidak pernah menjadikan transkrip mentah sebagai naskah output. Brief riset disampel merata sepanjang timeline serta dibatasi oleh `ORIGINAL_REBUILD_RESEARCH_MAX_CHARS=7000` agar instruksi tidak terpotong pada context window model lokal. Pipeline menerima JSON standar, alias field Indonesia/nested JSON, mencoba plain text, lalu memperbaiki draft hampir-valid secara terarah. Naskah diperiksa panjang, anti-verbatim, kekhususan topik, jumlah beat, dan pengulangan; bila AI tetap hanya menghasilkan tulisan generik, render dihentikan alih-alih menerbitkan fallback kosong. Semua jalur menolak rentetan lebih dari `ORIGINAL_REBUILD_MAX_VERBATIM_WORDS` kata sumber. Media download, audio ekstraksi, dan transkrip penuh dibersihkan sebelum `long_animate` membuat media baru; sidecar tetap mewajibkan review fakta, hak provider, disclosure AI, upload Private, dan YouTube Checks.
- `AUTO_REBUILD_HIGH_RISK_CC_SOURCES=true` membedakan heuristik pra-download dari claim nyata: job Clip Pendek/Long Story dengan metadata CC tetapi sinyal broadcaster/reupload otomatis dicoba ulang sebagai Original Rebuild 9:16 tanpa audio atau piksel sumber. Durasi rebuild otomatis mengikuti batas Short dari request awal (25-180 detik); Original Rebuild manual tetap memakai aspect/durasi Scene Cinema yang dikonfigurasi. Filter HD dan durasi sumber tidak dianggap bukti hak atau hasil Content ID.
- `AUTO_REBUILD_CLAIMED_CLIPS=true` membuat satu job Original Rebuild 9:16 pengganti hanya untuk klip yang benar-benar mendapat claim pada YouTube Studio Checks. Sibling dari source job yang sama tidak dibatalkan dan diperiksa sendiri-sendiri. Hasil rebuild tetap tidak auto-upload agar manusia dapat memeriksa fakta, aset provider, dan packaging terlebih dahulu.
- Original Rebuild dari UI berjalan sebagai `automatic_topic_rebuild`: AI menentukan sudut editorial baru tanpa form tambahan, media sumber dibersihkan sebelum render, dan auto-upload dimatikan sampai review manusia. API/CLI manual lama tetap menerima perspektif manusia serta referensi bukti hak sumber/provider. Renderer menyimpan `asset_license_ledger` per kelas aset dan `channel_authenticity_contract`; preflight membandingkan shingle narasi dengan maksimal 20 upload terakhir dan menolak kemiripan di atas `YOUTUBE_GENERATED_CONTENT_MAX_SIMILARITY` (default 0,58). Musik dibuat prosedural tanpa rekaman pihak ketiga—bukan diklaim sebagai Audio Library—sehingga Checks tetap wajib. Semua upload otomatis dipaksa Private-first meskipun request meminta public.
- Scene Cinema memakai `LONG_ANIMATE_DEFAULT_VISUAL_STYLE=cinematic_realistic` bila naskah tidak meminta gaya lain: tampilan dokumenter sinematik yang realistis, bukan karakter kartun generik. Prompt setiap shot mengunci subjek-aksi-objek-lokasi dari narasi, memilih komposisi/motion berdasarkan aksi (air, berjalan, membaca, terbang, reveal, atau payoff), menolak pose tangan/kerumunan buatan AI yang tidak diminta pengguna, dan memperlakukan sapaan seperti “saya mengajak kalian” sebagai narasi abstrak—bukan izin membuat orang mengangkat tangan. Adegan anak mandi/berenang selalu diberi pakaian sopan yang menutup tubuh dan framing wide/medium tanpa ketelanjangan, pakaian transparan, sensualisasi, voyeuristic angle, atau close-up tubuh. Profile `LONG_ANIMATE_TTS_PROFILE=islamic_indonesian` hanya mengubah teks khusus suara: `Allah SWT`, `Muhamad/Muhammad SAW`, serta simbol honorifik dibaca lengkap; subtitle dan naskah sumber tetap asli.
