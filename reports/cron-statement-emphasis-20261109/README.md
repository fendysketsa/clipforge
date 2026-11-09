# Penajaman statement sesuai klip — cron director v2

Status: implementasi siap dan teruji; belum aktif di backend produksi. API live masih tidak mengembalikan penanda versi cron director. Aktivasi memerlukan sudo interaktif.

## Perilaku

Statement merupakan salah satu variasi aksen dalam anggaran 1–2 efek yang sudah ada, maksimal satu per Short. Ia bukan teks wajib pada setiap sumber. AI director dapat mengusulkan 2–8 kata dari transkrip asli; pemilih lokal dapat menegaskan kalimat pendek lengkap yang relevan. Semua usulan diperiksa terhadap kata sumber. Tidak ada slogan atau klaim baru.

Kata penyangkalan, atribusi, ketidakpastian, dan kondisi harus tetap ada. Contohnya “belum berhasil” tidak menjadi “berhasil”; “menurut dia ini enak” tidak menjadi “ini enak”. Pertanyaan dan konteks sensitif tidak dijadikan statement. Fragmen yang menggantung juga dilewati. Jika tidak sesuai, efek visual sebelumnya tetap tersedia.

Tipografi berwarna, outline, bayangan, dan rays lokal dapat mengikuti suasana; topik biasa memakai gaya lebih bersih. Animasi masuk sekali lalu hold, tanpa flashing kata. Posisi diperiksa terpisah dengan kotak lebar terhadap wajah, subtitle, dan area terlindungi. Evidence/split layout atau area penuh melewati teks. Long tetap memakai maksimal dua aksen pada bab terpilih. Pekerjaan manual tidak mengaktifkan sistem ini.

## Bukti

- [Video dari salinan klip lokal](statement-preview.mp4): “Sebisa mungkin jangan cari masalah deh”, sesuai ucapan sumber. Tidak diunggah dan video asli tidak diubah.
- [Frame video](statement-frame.jpg)
- [Lembar contoh gaya](statement-styles.jpg): demonstrasi tipografi, bukan klaim bahwa semua kalimat berasal dari video pratinjau.
- [Rencana render](preview-plan.json)
- [Ekspor penuh clipper.export_clip](full-export-verification.json): video sintetis delapan detik benar-benar melewati encode, efek statement, audio mix, mux, dan audit; statement_rendered=true.
- [Verifikasi terstruktur](verification.json)

55 pengujian fitur efek saat ini lulus. Sebelumnya 333 pengujian gabungan efek, caption, Long, dan deployment lulus, mencakup 49 pengujian efek sebelum enam kasus qualifier/fragmen terakhir ditambahkan. Encoding nyata pada 30 dan 30000/1001 fps memverifikasi jumlah frame, dimensi, durasi, hash paket audio, dan area terlindungi. Kompilasi Python, sintaks shell, dan whitespace diff lulus.

## Aktivasi

```sh
sudo bash /www/wwwroot/clipper/clipforge/scripts/activate-cron-director-effects.sh
```

Skrip menunggu pekerjaan aktif selesai dan mempertahankan browser upload. Verifikasi akhir wajib menemukan cron_director_effects_policy_version=2. Efek berlaku untuk render cron baru setelah aktivasi; hasil lama tidak dirender ulang atau diunggah ulang.

Waktu frasa diperkirakan dalam segmen transkrip; posisi memakai deteksi wajah opsional dan guard geometris, bukan pelacakan objek semantik.
