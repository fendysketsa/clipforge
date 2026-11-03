# Review arahan bukti: klip OBRAS

Preview lokal: `review.mp4`, 1080×1920, 37,75 detik. Preview menggunakan hasil
klip yang sudah ada, dengan audio disalin tanpa encoding ulang. Video asal dan
hasil pada halaman Results tidak ditimpa. Ini contoh treatment warning ketika
sumber persis belum bisa diperiksa, bukan video dengan bukti lengkap.

Sumber video: https://www.youtube.com/watch?v=hLL7-hrsRpY

| Waktu di klip | Ucapan pemicu | Perlakuan |
| --- | --- | --- |
| 0,08–5,21 | Admin punya masalah sama Indonesia sepertinya. | Penilaian pembicara; motif belum dibuktikan. |
| 5,36–10,86 | Menuliskan berita paragraf pertama itu motifnya apa? | Warning sumber tulisan belum terverifikasi; Astro Awani disebut sebagai atribusi dari pembicara. |
| 19,97–25,47 | Dari Instagram klubnya Emil Audero, | Warning unggahan asli belum terverifikasi. |

Konteks media berasal dari transkrip sumber pada 943,13 detik: pembicara menyebut
Astro Awani. Ini atribusi dalam video, bukan konfirmasi bahwa media itu benar
menulis kalimat yang dipersoalkan.

## Hasil penelusuran sesi ini

- Artikel pembanding ditemukan di [Stadium Astro](https://stadiumastro.com/sukan/panas-kontroversi-aksi-dihentikan-serta-merta-tanda-protes-terhadap-pemilik).
  Isinya membahas protes terhadap pengelolaan klub dan penghormatan untuk Audero.
  Artikel ini belum dapat dipastikan sebagai unggahan Astro Awani persis yang
  dikritik. Tidak ditempel sebagai bukti asli.
- [Format Relay](https://formatrelay.com/leaderboard/la-liga/rayo-vallecano)
  mencantumkan tautan [unggahan Instagram Rayo Vallecano](https://www.instagram.com/rayovallecano/p/DeUGgO1NvyX/)
  tentang penghormatan kepada Audero. Halaman Instagram langsung gagal diakses
  melalui alat web (cache miss), sehingga statusnya masih kandidat.
- Pencarian langsung dari Python menghasilkan `URLError: Connection refused`.
  Hasil tersebut dicatat sebagai `search_unavailable`, bukan bukti tidak adanya
  artikel atau unggahan.

`direction.json` mencatat timestamp dan status. Frame 01, 07, dan 22 disediakan
untuk pemeriksaan visual. Frame 07 dan 22 sudah diperiksa: panel terbaca dan
tidak menutup wajah atau subtitle. Preview belum ditinjau lewat playback audio.

Validasi kode: 234 pengujian lulus untuk caption, creative director, handoff,
validasi bukti, dan kompilasi filter FFmpeg dengan teks serta gambar.
Hash paket audio sumber dan preview sama:
`d541b94c6512c0e1f71a34378b44cac2136abb10e57723958f816edb6660ff65`.
SHA-256 video sumber setelah preview dibuat:
`3b1d84f7a4cb5c1b959a8f0b5610291dbd8a759c34f35c8093fb76371b7c5926`.

Perubahan kode belum diaktifkan di container produksi. Akses socket Docker
ditolak dan `sudo -n docker ps` memerlukan sandi. Hasil Results yang lama tetap
berupa file sebelumnya; preview baru berada di folder produksi ini.
