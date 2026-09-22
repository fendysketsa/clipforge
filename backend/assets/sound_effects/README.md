# Pustaka efek suara lokal

Folder ini berisi efek suara pendek CC0 yang dipakai langsung dari disk. Render
tidak pernah mengunduh audio. `catalog.json` adalah allowlist: loader menolak
file dengan hash, lisensi, tipe, atau domain sumber yang tidak cocok.

Efek dipilih dari cue transkrip, bukan secara acak:

- `laugh.ogg` untuk tawa yang memang terdeteksi pada dialog;
- `shock-bong.wav` untuk kejutan/peringatan;
- `pop.wav` untuk penekanan ringan, pertanyaan, dan loop.

Mode editorial yang harus tetap khidmat atau mempertahankan punchline asli
tetap dapat menonaktifkan SFX. Semua efek dibatasi volumenya di bawah dialog dan
limiter akhir tetap aktif. Jika aset lokal hilang/tidak valid, renderer memakai
accent sintetis ringan—bukan mengakses jaringan.

| File | Judul — pembuat | Lisensi/sumber |
| --- | --- | --- |
| `laugh.ogg` | Do You Remember Laughter? — Supergeek | [CC0 / OpenGameArt](https://opengameart.org/content/do-you-remember-laughter) |
| `shock-bong.wav` | Bong 1 — BMacZero | [CC0 / OpenGameArt](https://opengameart.org/content/metal-impact-sounds) |
| `pop.wav` | Pop 1 — EZduzziteh | [CC0 / OpenGameArt](https://opengameart.org/content/pop-sounds-0) |

Teks lisensi: <https://creativecommons.org/publicdomain/zero/1.0/>.
