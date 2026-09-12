# YouTube Audio Library manual (legacy)

Folder ini tidak lagi dibaca oleh pipeline Clip Pendek dan tidak disinkronkan
saat render. Pustaka aktif ada di `../background_music`; unduhan terkurasi hanya
berjalan melalui langkah setup/rebuild.

Folder ini hanya untuk musik instrumental yang diunduh langsung dari YouTube
Studio > Koleksi audio > Musik dengan filter **Attribution not required**.

YouTube tidak menyediakan API publik untuk katalog Audio Library. Script lama
di folder `scripts/` dipertahankan hanya sebagai alat impor manual dan tidak
pernah dipanggil oleh backend.

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

Entri legacy di folder ini tidak dipakai oleh Clip Pendek.
