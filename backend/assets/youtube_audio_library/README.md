# YouTube Audio Library untuk Clip Pendek

Folder ini hanya untuk musik instrumental yang diunduh langsung dari YouTube
Studio > Koleksi audio > Musik dengan filter **Attribution not required**.

YouTube tidak menyediakan API publik untuk katalog Audio Library. Karena itu,
renderer tidak melakukan scraping halaman Studio atau mengunduh musik dari
channel pihak ketiga. Unduh MP3 dari Studio sekali, lalu impor dengan:

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
