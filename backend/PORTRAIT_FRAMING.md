# Landscape dan percakapan di dalam portrait

Ekspor Short tetap 1080×1920. Sumber landscape pada mode `auto_fyp` dan
`speaker_split` sekarang ditempatkan dalam panel landscape di atas kanvas solid.
Seluruh lebar frame terlihat, termasuk pada sumber 4K. Kanvas tidak diisi dengan
crop portrait yang membuang pembicara, tulisan, atau objek di sisi gambar.

Jika dua wajah terlihat bersamaan secara cukup konsisten dan berjauhan,
renderer dapat membagi satu frame sumber menjadi dua panel landscape atas dan
bawah. Keduanya memakai timestamp yang sama dan satu audio sumber. Deteksi
posisi wajah bukan diarization audio dan tidak menyatakan siapa yang sedang
berbicara. Kelompok lebih besar, deteksi tidak pasti, posisi berdekatan, atau
klip dengan panel bukti menggunakan frame landscape utuh sebagai fallback.

Penentuan framing dilakukan untuk setiap klip, termasuk batch dengan satu
kandidat. Alur otomatis tidak mengambil klip pendamping dari waktu lain.
Parameter helper lama dipertahankan untuk kompatibilitas pemanggil, tetapi
ekspor portrait mengabaikan klip pendamping tersebut.

Saat framing ini aktif, layout host virtual/kartu sosial tidak menimpa video,
background tidak diganti, dan efek zoom/crop kamera tambahan tidak memotong
frame lagi. Judul serta catatan editorial menggunakan ruang atas kanvas.
Panel bukti yang memiliki screenshot mendapat ruang atas, dengan moving video
di bawahnya. Mode streamer dan ekspor kompilasi landscape memakai alur tersendiri.

Sidecar mencatat `portrait_framing`, `layout`, `full_source_frame_visible`,
`all_panels_synchronized`, dan `uses_other_timeline_clips` agar hasilnya bisa
ditinjau. Implementasi berada di `portrait_framing.py` dan `clipper.py`.

Validasi meliputi pixel dari render FFmpeg untuk kedua sisi frame, perubahan
warna pada timestamp yang sama di dua panel, dan ekspor lengkap dengan efek
edit aktif. Contoh visual berlabel simulasi tersedia di
`productions/portrait-framing-review`.

Perubahan sumber ini memerlukan aktivasi container sebelum digunakan oleh
layanan yang berjalan. File hasil render sebelumnya tidak otomatis berubah.
