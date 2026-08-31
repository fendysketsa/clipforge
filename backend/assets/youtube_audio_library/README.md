# YouTube Audio Library untuk Clip Pendek

Folder ini hanya untuk musik instrumental yang diunduh langsung dari YouTube
Studio > Koleksi audio > Musik dengan filter **Attribution not required**.

YouTube tidak menyediakan API publik untuk katalog Audio Library. Saat proses
Clip Pendek, backend sekarang mencoba membuka halaman Studio memakai sesi dari
fitur **Login Sekali**, memilih tab Musik, menerapkan filter
**Attribution not required**, memilih mood sesuai tema, lalu mengunduh satu track
ke katalog ini. Kegagalan login/UI tidak menggagalkan render: klip dilanjutkan
dengan audio asli atau fallback lokal yang aman.

Impor manual di bawah hanya jalur cadangan bila sinkronisasi otomatis tidak bisa
digunakan. Nilai `/path/ke/track.mp3`, judul, dan artis wajib diganti dengan file
serta metadata nyata:

```bash
python scripts/import-youtube-audio-track.py \
  --file "/path/ke/track.mp3" \
  --title "Judul dari Studio" \
  --artist "Nama artis dari Studio" \
  --theme inspiring \
  --mood inspirational --mood uplifting \
  --genre cinematic
```

Tema yang didukung: `mystery`, `islamic`, `warning`, `inspiring`, dan
`knowledge`. Satu track boleh memiliki beberapa `--theme`, `--mood`, dan
`--genre`.

Pipeline hanya menerima entri yang:

- berjenis musik dan instrumental;
- file audionya benar-benar tersedia di folder ini;
- memakai `YouTube Audio Library License`;
- ditandai `attribution_required: false`;
- memiliki sumber resmi YouTube Audio Library.

Clip Pendek kemudian memilih track berdasarkan tema/narasi, memotong atau
me-loop musik sepanjang klip, memberikan fade singkat, mencampur dialog pada
gain 80% dan musik maksimal 20%, serta menurunkan musik lagi ketika ada ucapan.
